from rest_framework.routers import DefaultRouter

from .views import BarberViewSet, ServiceViewSet, WorkingHoursViewSet

router = DefaultRouter()
router.register("services", ServiceViewSet, basename="service")
router.register("barbers", BarberViewSet, basename="barber")
router.register("working-hours", WorkingHoursViewSet, basename="working-hours")

urlpatterns = router.urls
