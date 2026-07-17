from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import BarberoViewSet, LoginView, ReservaViewSet, ServicioViewSet

router = DefaultRouter()
router.register("barberos", BarberoViewSet, basename="barbero")
router.register("servicios", ServicioViewSet, basename="servicio")
router.register("reservas", ReservaViewSet, basename="reserva")

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="auth-login"),
] + router.urls
