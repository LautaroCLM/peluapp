from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminRole

from . import services
from .availability import get_available_slots
from .filters import AppointmentFilter
from .models import Appointment
from .serializers import (
    AppointmentCreateSerializer,
    AppointmentSerializer,
    AvailabilityQuerySerializer,
    AvailabilitySerializer,
)


class AvailabilityView(APIView):
    """Horarios disponibles de un peluquero para una fecha y un servicio."""

    @extend_schema(
        tags=["availability"],
        summary="Horarios disponibles",
        parameters=[
            OpenApiParameter("barber", int, description="ID del peluquero"),
            OpenApiParameter("service", int, description="ID del servicio"),
            OpenApiParameter("date", str, description="Fecha en formato YYYY-MM-DD"),
        ],
        responses=AvailabilitySerializer,
    )
    def get(self, request):
        query = AvailabilityQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        barber = query.validated_data["barber"]
        service = query.validated_data["service"]
        day = query.validated_data["date"]

        slots = get_available_slots(barber, day, service)
        payload = {
            "barber": barber.id,
            "service": service.id,
            "date": day,
            "slots": [{"start": s, "end": e} for s, e in slots],
        }
        return Response(AvailabilitySerializer(payload).data)


class AppointmentViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Turnos. No hay PUT/PATCH/DELETE: el cliente cancela con la acción `cancel`
    y para cambiar de horario se cancela y se reserva de nuevo."""

    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = AppointmentFilter
    filter_backends = [*viewsets.GenericViewSet.filter_backends, filters.OrderingFilter]
    ordering_fields = ["start_at", "created_at", "price"]

    def get_queryset(self):
        # Regla 5: el cliente solo ve sus turnos; el administrador ve todos.
        # Los ajenos responden 404 (no se revela que existen).
        # drf-spectacular genera el schema sin usuario real: evitamos fallar ahí.
        if getattr(self, "swagger_fake_view", False):
            return Appointment.objects.none()
        qs = Appointment.objects.select_related("barber", "service", "client")
        user = self.request.user
        if not user.is_admin_role:
            qs = qs.filter(client=user)
        return qs

    @extend_schema(
        tags=["appointments"],
        request=AppointmentCreateSerializer,
        responses={201: AppointmentSerializer},
    )
    def create(self, request, *args, **kwargs):
        data = AppointmentCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        appointment = services.create_appointment(client=request.user, **data.validated_data)
        return Response(AppointmentSerializer(appointment).data, status=status.HTTP_201_CREATED)

    @extend_schema(tags=["appointments"], request=None, responses=AppointmentSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        appointment = services.cancel_appointment(self.get_object(), user=request.user)
        return Response(AppointmentSerializer(appointment).data)

    @extend_schema(tags=["appointments"], request=None, responses=AppointmentSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsAdminRole])
    def confirm(self, request, pk=None):
        appointment = services.confirm_appointment(self.get_object())
        return Response(AppointmentSerializer(appointment).data)

    @extend_schema(tags=["appointments"], request=None, responses=AppointmentSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsAdminRole])
    def complete(self, request, pk=None):
        appointment = services.complete_appointment(self.get_object())
        return Response(AppointmentSerializer(appointment).data)
