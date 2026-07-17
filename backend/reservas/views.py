import threading

from django.contrib.auth import authenticate
from django.db import IntegrityError, transaction
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .emails import send_confirmation_email
from .models import Barbero, Reserva, Servicio
from .serializers import BarberoSerializer, ReservaSerializer, ServicioSerializer


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
        if self.action in ("create", "horarios_ocupados"):
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(detail=False, methods=["get"])
    def horarios_ocupados(self, request):
        # Endpoint publico pensado para booking.js: el cliente sin login
        # necesita saber que horarios estan tomados para pintar el
        # calendario, pero NO debe poder ver nombre/telefono de otros
        # clientes (eso es lo que exponia el /reservas/ (list) publico
        # antes de este cambio). Se devuelve solo lo minimo indispensable.
        qs = self.get_queryset().exclude(estado=Reserva.Estado.CANCELADA)
        data = list(qs.values("barbero_id", "fecha", "hora"))
        return Response(data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

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
