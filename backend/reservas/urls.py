from rest_framework.routers import DefaultRouter

from .views import BarberoViewSet, ReservaViewSet, ServicioViewSet

router = DefaultRouter()
router.register("barberos", BarberoViewSet, basename="barbero")
router.register("servicios", ServicioViewSet, basename="servicio")
router.register("reservas", ReservaViewSet, basename="reserva")

urlpatterns = router.urls
