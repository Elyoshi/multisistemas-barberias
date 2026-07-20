import threading
from datetime import time as time_type

from django.contrib.auth import authenticate
from django.db import IntegrityError, transaction
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .emails import send_confirmation_email, send_confirmation_email_multiple
from .models import Barbero, BloqueoHorario, Reserva, Servicio
from .serializers import BarberoSerializer, ReservaSerializer, ServicioSerializer


def _bloqueo_que_choca(barbero_id, fecha, hora_inicio, duracion_minutos):
    """Devuelve el BloqueoHorario de ese barbero/fecha que se superpone con
    [hora_inicio, hora_inicio + duracion_minutos), o None si no hay ninguno.

    Mismo criterio de superposicion que usa booking.js (renderTimeSlots): un
    bloqueo de dia completo (hora_inicio/hora_fin null) se trata como si
    cubriera 00:00-24:00 completo. El UniqueConstraint de Reserva no sirve
    aca -- un bloqueo no es una Reserva, asi que sin este chequeo explicito
    nada en la base de datos impide crear una reserva en un horario bloqueado.
    """
    inicio_reserva = hora_inicio.hour * 60 + hora_inicio.minute
    fin_reserva = inicio_reserva + duracion_minutos
    for bloqueo in BloqueoHorario.objects.filter(barbero_id=barbero_id, fecha=fecha):
        if bloqueo.hora_inicio is None:
            inicio_bloqueo, fin_bloqueo = 0, 24 * 60
        else:
            inicio_bloqueo = bloqueo.hora_inicio.hour * 60 + bloqueo.hora_inicio.minute
            fin_bloqueo = bloqueo.hora_fin.hour * 60 + bloqueo.hora_fin.minute
        if inicio_reserva < fin_bloqueo and fin_reserva > inicio_bloqueo:
            return bloqueo
    return None


def _mensaje_bloqueo(bloqueo):
    if bloqueo.motivo:
        return f"Ese barbero no está disponible ese día ({bloqueo.motivo})."
    return "Ese barbero no está disponible ese día."


class LoginView(APIView):
    """POST {username, password} -> {token} para el panel admin (admin.js)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"detail": "Usuario y contraseña son requeridos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {"detail": "Usuario o contraseña incorrectos."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key})


class BarberoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Barbero.objects.filter(activo=True)
    serializer_class = BarberoSerializer
    http_method_names = ["get", "head", "options"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAuthenticated()]


class ServicioViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Servicio.objects.filter(activo=True)
    serializer_class = ServicioSerializer
    http_method_names = ["get", "head", "options"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAuthenticated()]


class ReservaViewSet(viewsets.ModelViewSet):
    queryset = Reserva.objects.select_related("barbero", "servicio").all()
    serializer_class = ReservaSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_permissions(self):
        if self.action in ("create", "horarios_ocupados", "multiples"):
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(detail=False, methods=["get"])
    def horarios_ocupados(self, request):
        # Endpoint publico pensado para booking.js: el cliente sin login
        # necesita saber que horarios estan tomados para pintar el
        # calendario, pero NO debe poder ver nombre/telefono de otros
        # clientes (eso es lo que exponia el /reservas/ (list) publico
        # antes de este cambio). Se devuelve solo lo minimo indispensable.
        # duracion_minutos va incluida porque el frontend la necesita para
        # saber si un bloque (2 servicios, o un bloqueo) cabe completo, no
        # solo si el primer instante esta libre.
        #
        # Se combina en una sola lista, con la MISMA forma, reservas activas
        # y bloqueos de horario -- asi el frontend no necesita distinguir
        # entre "ocupado por una reserva" y "bloqueado por el barbero", el
        # mismo chequeo de superposicion de booking.js sirve para ambos.
        # Un bloqueo de dia completo (hora_inicio/hora_fin null) se emite
        # como hora=00:00 + duracion=1440 (24hs), asi cubre cualquier slot
        # de la grilla sin que el frontend necesite un caso especial.
        qs = self.get_queryset().exclude(estado=Reserva.Estado.CANCELADA)
        data = [
            {
                "barbero_id": r["barbero_id"],
                "fecha": r["fecha"],
                "hora": r["hora"],
                "duracion_minutos": r["servicio__duracion_minutos"],
            }
            for r in qs.values("barbero_id", "fecha", "hora", "servicio__duracion_minutos")
        ]

        for bloqueo in BloqueoHorario.objects.all():
            if bloqueo.hora_inicio is None:
                hora, duracion = time_type(0, 0), 24 * 60
            else:
                inicio_min = bloqueo.hora_inicio.hour * 60 + bloqueo.hora_inicio.minute
                fin_min = bloqueo.hora_fin.hour * 60 + bloqueo.hora_fin.minute
                hora, duracion = bloqueo.hora_inicio, fin_min - inicio_min
            data.append(
                {
                    "barbero_id": bloqueo.barbero_id,
                    "fecha": bloqueo.fecha,
                    "hora": hora,
                    "duracion_minutos": duracion,
                }
            )

        return Response(data)

    @action(detail=False, methods=["post"])
    def multiples(self, request):
        # Reserva de 1-2 servicios consecutivos en la misma visita (mismo
        # barbero, misma fecha). El modelo Reserva no cambia -- esto sigue
        # creando un registro por servicio, pero todos dentro de UNA sola
        # transaccion: si el horario de cualquiera choca, se revierten
        # todos (no debe quedar una reserva "a medias" con solo el primer
        # servicio). El frontend ya calculo la hora de inicio de cada
        # bloque sumando duraciones -- este endpoint no la recalcula.
        servicios_data = request.data.get("servicios")
        if not isinstance(servicios_data, list) or not servicios_data:
            return Response(
                {"detail": "Se requiere una lista 'servicios' con al menos un elemento."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        base = {
            "barbero": request.data.get("barbero"),
            "cliente_nombre": request.data.get("cliente_nombre"),
            "cliente_telefono": request.data.get("cliente_telefono"),
            "cliente_email": request.data.get("cliente_email", ""),
            "fecha": request.data.get("fecha"),
        }

        serializers_list = []
        for item in servicios_data:
            payload = {**base, "servicio": item.get("servicio"), "hora": item.get("hora")}
            serializer = self.get_serializer(data=payload)
            serializer.is_valid(raise_exception=True)
            serializers_list.append(serializer)

        # Chequeo de bloqueos ANTES de tocar la base de datos: si cualquiera
        # de los servicios cae en un horario bloqueado, se rechaza todo el
        # combo -- no debe quedar ninguna reserva a medias.
        for serializer in serializers_list:
            bloqueo = _bloqueo_que_choca(
                serializer.validated_data["barbero"].id,
                serializer.validated_data["fecha"],
                serializer.validated_data["hora"],
                serializer.validated_data["servicio"].duracion_minutos,
            )
            if bloqueo:
                return Response({"detail": _mensaje_bloqueo(bloqueo)}, status=status.HTTP_409_CONFLICT)

        reservas = []
        try:
            with transaction.atomic():
                for serializer in serializers_list:
                    reservas.append(serializer.save())
        except IntegrityError:
            # reservas solo tiene los guardados exitosos antes del choque,
            # asi que su longitud es el indice del serializer que fallo.
            conflicto = serializers_list[len(reservas)]
            servicio = conflicto.validated_data["servicio"]
            hora = conflicto.validated_data["hora"].strftime("%H:%M")
            return Response(
                {
                    "detail": f"El horario para {servicio.nombre} ({hora}) ya fue reservado. "
                    f"Por favor elige otro."
                },
                status=status.HTTP_409_CONFLICT,
            )

        if len(reservas) == 1:
            transaction.on_commit(
                lambda: threading.Thread(
                    target=send_confirmation_email, args=(reservas[0],), daemon=True
                ).start()
            )
        else:
            transaction.on_commit(
                lambda: threading.Thread(
                    target=send_confirmation_email_multiple, args=(reservas,), daemon=True
                ).start()
            )

        result_serializer = self.get_serializer(reservas, many=True)
        headers = self.get_success_headers(result_serializer.data)
        return Response(result_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        bloqueo = _bloqueo_que_choca(
            serializer.validated_data["barbero"].id,
            serializer.validated_data["fecha"],
            serializer.validated_data["hora"],
            serializer.validated_data["servicio"].duracion_minutos,
        )
        if bloqueo:
            return Response({"detail": _mensaje_bloqueo(bloqueo)}, status=status.HTTP_409_CONFLICT)

        try:
            with transaction.atomic():
                reserva = serializer.save()
        except IntegrityError:
            return Response(
                {"detail": "Ese horario ya fue reservado. Por favor elige otro."},
                status=status.HTTP_409_CONFLICT,
            )

        transaction.on_commit(
            lambda: threading.Thread(
                target=send_confirmation_email, args=(reserva,), daemon=True
            ).start()
        )

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
