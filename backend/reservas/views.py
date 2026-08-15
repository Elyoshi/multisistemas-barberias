import threading
import uuid
from datetime import time as time_type

from django.conf import settings
from django.contrib.auth import authenticate
from django.db import IntegrityError, transaction
from django.http import HttpResponse, HttpResponseNotFound
from django.middleware.csrf import get_token
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .emails import (
    send_confirmation_email,
    send_confirmation_email_cliente,
    send_confirmation_email_multiple,
    send_notificacion_barbero,
)
from .models import Barbero, BloqueoHorario, DisponibilidadBarbero, Reserva, Servicio
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


def _links_confirmacion(request, token):
    confirm_url = request.build_absolute_uri(reverse("reserva-confirmar", args=[token]))
    cancel_url = request.build_absolute_uri(reverse("reserva-cancelar", args=[token]))
    return confirm_url, cancel_url


def _pagina_confirmacion_html(titulo, mensaje, reservas=None, form_html=""):
    # HTML minimo a proposito: esta pagina la abre el cliente/barbero desde
    # el link del email, no es parte del SPA (booking.js/admin.js).
    detalle = ""
    if reservas:
        primera = reservas[0]
        items = "".join(
            f"<li>{r.servicio.nombre} a las {r.hora.strftime('%H:%M')}</li>" for r in reservas
        )
        detalle = (
            f"<p><strong>Cliente:</strong> {primera.cliente_nombre}</p>"
            f"<ul>{items}</ul>"
            f"<p><strong>Fecha:</strong> {primera.fecha.strftime('%d-%m-%Y')}</p>"
        )
    return (
        "<!DOCTYPE html>"
        '<html lang="es"><head><meta charset="utf-8">'
        f"<title>{titulo}</title></head>"
        '<body style="font-family: sans-serif; max-width: 480px; margin: 40px auto; text-align: center;">'
        f"<h1>{titulo}</h1><p>{mensaje}</p>{detalle}{form_html}"
        "</body></html>"
    )


def _form_accion_html(request, accion_url, boton_texto):
    # get_token() arma un token CSRF real ligado a la sesion/cookie del
    # visitante (misma proteccion que {% csrf_token %} en un template) y
    # marca la respuesta para que el middleware setee la cookie -- no es
    # HTML "a mano" sin proteccion, solo no pasa por el motor de templates.
    csrf_token = get_token(request)
    return (
        f'<form method="POST" action="{accion_url}">'
        f'<input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">'
        f'<button type="submit" style="padding: 10px 24px; font-size: 1rem; margin-top: 16px;">'
        f"{boton_texto}</button>"
        "</form>"
    )


@require_http_methods(["GET", "POST"])
def confirmar_reserva(request, token):
    """Endpoint publico (sin login) que se abre desde el link del email al
    cliente/barbero. Confirma TODAS las Reserva con ese token_confirmacion
    a la vez -- comparten token cuando vienen de multiples() (combo de la
    misma visita). Solo mueve pendiente -> confirmada; una cancelada no
    se revive.

    GET solo muestra el detalle y un boton -- no debe mutar nada, porque
    los scanners de seguridad de email (Outlook Safe Links, Barracuda,
    etc.) visitan el link solo por abrirlo, sin que el humano haya hecho
    click todavia. La transicion real solo ocurre en POST, disparada por
    el <form> de esa misma pagina.
    """
    if not settings.HABILITAR_CONFIRMACION_EMAIL:
        return HttpResponseNotFound()

    reservas = list(
        Reserva.objects.select_related("barbero", "servicio").filter(token_confirmacion=token)
    )
    if not reservas:
        html = _pagina_confirmacion_html(
            "Reserva no encontrada", "No encontramos ninguna reserva con ese enlace."
        )
        return HttpResponse(html, status=404)

    pendientes = [r for r in reservas if r.estado == Reserva.Estado.PENDIENTE]

    if request.method == "POST":
        if not pendientes:
            return HttpResponse(_pagina_resultado_no_confirmable(reservas))
        for reserva in pendientes:
            reserva.estado = Reserva.Estado.CONFIRMADA
            reserva.save(update_fields=["estado"])
        threading.Thread(
            target=send_confirmation_email_cliente, args=(reservas,), daemon=True
        ).start()
        html = _pagina_confirmacion_html("Hora confirmada", "Tu hora fue confirmada con éxito.", reservas)
        return HttpResponse(html)

    if not pendientes:
        return HttpResponse(_pagina_resultado_no_confirmable(reservas))

    form = _form_accion_html(request, reverse("reserva-confirmar", args=[token]), "Sí, confirmar esta reserva")
    html = _pagina_confirmacion_html(
        "Confirmar tu hora", "Revisa el detalle y confirma tu hora.", reservas, form_html=form
    )
    return HttpResponse(html)


def _pagina_resultado_no_confirmable(reservas):
    if all(r.estado == Reserva.Estado.CONFIRMADA for r in reservas):
        return _pagina_confirmacion_html(
            "Ya estaba confirmada", "Esta hora ya había sido confirmada anteriormente.", reservas
        )
    return _pagina_confirmacion_html(
        "No se puede confirmar",
        f"Esta hora no se puede confirmar (estado actual: {reservas[0].get_estado_display()}).",
        reservas,
    )


@require_http_methods(["GET", "POST"])
def cancelar_reserva(request, token):
    """Igual que confirmar_reserva pero para cancelar: GET solo muestra el
    detalle y el boton, POST ejecuta la transicion. Permite cancelar desde
    pendiente o confirmada; una ya cancelada queda igual.
    """
    if not settings.HABILITAR_CONFIRMACION_EMAIL:
        return HttpResponseNotFound()

    reservas = list(
        Reserva.objects.select_related("barbero", "servicio").filter(token_confirmacion=token)
    )
    if not reservas:
        html = _pagina_confirmacion_html(
            "Reserva no encontrada", "No encontramos ninguna reserva con ese enlace."
        )
        return HttpResponse(html, status=404)

    cancelables = [
        r for r in reservas if r.estado in (Reserva.Estado.PENDIENTE, Reserva.Estado.CONFIRMADA)
    ]

    if request.method == "POST":
        if not cancelables:
            return HttpResponse(_pagina_resultado_no_cancelable(reservas))
        for reserva in cancelables:
            reserva.estado = Reserva.Estado.CANCELADA
            reserva.save(update_fields=["estado"])
        html = _pagina_confirmacion_html("Hora cancelada", "Tu hora fue cancelada.", reservas)
        return HttpResponse(html)

    if not cancelables:
        return HttpResponse(_pagina_resultado_no_cancelable(reservas))

    form = _form_accion_html(request, reverse("reserva-cancelar", args=[token]), "Sí, cancelar esta reserva")
    html = _pagina_confirmacion_html(
        "Cancelar tu hora", "Revisa el detalle y cancela tu hora.", reservas, form_html=form
    )
    return HttpResponse(html)


def _pagina_resultado_no_cancelable(reservas):
    if all(r.estado == Reserva.Estado.CANCELADA for r in reservas):
        return _pagina_confirmacion_html(
            "Ya estaba cancelada", "Esta hora ya había sido cancelada anteriormente.", reservas
        )
    return _pagina_confirmacion_html(
        "No se puede cancelar",
        f"Esta hora no se puede cancelar (estado actual: {reservas[0].get_estado_display()}).",
        reservas,
    )


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
        if self.action in ("create", "horarios_ocupados", "multiples", "disponibilidad"):
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(detail=False, methods=["get"])
    def disponibilidad(self, request):
        # Override del horario base para un barbero en una fecha puntual
        # (ver DisponibilidadBarbero). Capa ENCIMA del sistema existente: si
        # no hay filas para ese barbero+fecha, se devuelve [] y booking.js
        # sigue usando su hoursList base sin ningun cambio de comportamiento.
        # Si hay filas, booking.js genera los horarios candidatos SOLO
        # dentro de esas ventanas -- el chequeo de superposicion contra
        # horarios_ocupados (reservas + bloqueos) sigue aplicandose igual,
        # despues, sin importar de donde salieron las horas candidatas.
        barbero_id = request.query_params.get("barbero_id")
        fecha = request.query_params.get("fecha")
        if not barbero_id or not fecha:
            return Response(
                {"detail": "Se requieren los parámetros 'barbero_id' y 'fecha'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ventanas = DisponibilidadBarbero.objects.filter(barbero_id=barbero_id, fecha=fecha).values(
            "hora_inicio", "hora_fin"
        )
        return Response(list(ventanas))

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

        # Token compartido entre todas las reservas de este combo -- asi un
        # solo link de email confirma/cancela toda la visita, no servicio
        # por servicio. Ver confirmar_reserva/cancelar_reserva.
        token = uuid.uuid4()

        reservas = []
        try:
            with transaction.atomic():
                for serializer in serializers_list:
                    reservas.append(serializer.save(token_confirmacion=token))
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

        if settings.HABILITAR_CONFIRMACION_EMAIL:
            confirm_url, cancel_url = _links_confirmacion(request, token)
            transaction.on_commit(
                lambda: threading.Thread(
                    target=send_notificacion_barbero,
                    args=(reservas, confirm_url, cancel_url),
                    daemon=True,
                ).start()
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

        token = uuid.uuid4()
        try:
            with transaction.atomic():
                reserva = serializer.save(token_confirmacion=token)
        except IntegrityError:
            return Response(
                {"detail": "Ese horario ya fue reservado. Por favor elige otro."},
                status=status.HTTP_409_CONFLICT,
            )

        if settings.HABILITAR_CONFIRMACION_EMAIL:
            confirm_url, cancel_url = _links_confirmacion(request, token)
            transaction.on_commit(
                lambda: threading.Thread(
                    target=send_notificacion_barbero,
                    args=([reserva], confirm_url, cancel_url),
                    daemon=True,
                ).start()
            )

        transaction.on_commit(
            lambda: threading.Thread(
                target=send_confirmation_email, args=(reserva,), daemon=True
            ).start()
        )

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
