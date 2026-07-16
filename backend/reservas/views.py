import threading

from django.db import IntegrityError, transaction
from rest_framework import status, viewsets
from rest_framework.response import Response

from .emails import send_confirmation_email
from .models import Barbero, Reserva, Servicio
from .serializers import BarberoSerializer, ReservaSerializer, ServicioSerializer


class BarberoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Barbero.objects.filter(activo=True)
    serializer_class = BarberoSerializer
    http_method_names = ["get", "head", "options"]


class ServicioViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Servicio.objects.filter(activo=True)
    serializer_class = ServicioSerializer
    http_method_names = ["get", "head", "options"]


class ReservaViewSet(viewsets.ModelViewSet):
    queryset = Reserva.objects.select_related("barbero", "servicio").all()
    serializer_class = ReservaSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

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
