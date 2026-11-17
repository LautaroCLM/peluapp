from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AppointmentViewSet, AvailabilityView

router = DefaultRouter()
router.register("appointments", AppointmentViewSet, basename="appointment")

urlpatterns = [
    path("availability/", AvailabilityView.as_view(), name="availability"),
    *router.urls,
]
