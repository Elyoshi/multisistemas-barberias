from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    BarberoViewSet,
    LoginView,
    ReservaViewSet,
    ServicioViewSet,
    cancelar_reserva,
    confirmar_reserva,
)

router = DefaultRouter()
router.register("barberos", BarberoViewSet, basename="barbero")
router.register("servicios", ServicioViewSet, basename="servicio")
router.register("reservas", ReservaViewSet, basename="reserva")

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    # Publicos (AllowAny), pensados para abrirse desde un navegador, no
    # desde el SPA. 404 si HABILITAR_CONFIRMACION_EMAIL esta apagado --
    # ver confirmar_reserva/cancelar_reserva en views.py.
    path("reservas/confirmar/<uuid:token>/", confirmar_reserva, name="reserva-confirmar"),
    path("reservas/cancelar/<uuid:token>/", cancelar_reserva, name="reserva-cancelar"),
] + router.urls
