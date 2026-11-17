from django.db.models import ProtectedError
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters, status, viewsets
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminRole

from .filters import BarberFilter, ServiceFilter, WorkingHoursFilter
from .models import Barber, Service, WorkingHours
from .serializers import BarberSerializer, ServiceSerializer, WorkingHoursSerializer


class SafeDeleteMixin:
    """Si el objeto tiene turnos asociados (on_delete=PROTECT) responde 409
    en vez de romper con un 500, y sugiere desactivarlo."""

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {
                    "detail": (
                        "Tiene turnos asociados y no puede borrarse. "
                        "Desactivalo con is_active=false."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )


class ReadAuthenticatedWriteAdminMixin:
    """Cualquier usuario autenticado puede consultar (los clientes necesitan ver
    servicios y peluqueros para reservar); solo el administrador puede modificar.
    Los clientes solo ven registros activos."""

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and not user.is_admin_role:
            qs = qs.filter(is_active=True)
        return qs


@extend_schema_view(list=extend_schema(tags=["services"]))
class ServiceViewSet(SafeDeleteMixin, ReadAuthenticatedWriteAdminMixin, viewsets.ModelViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    filterset_class = ServiceFilter
    filter_backends = [
        *viewsets.ModelViewSet.filter_backends,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["name"]
    ordering_fields = ["name", "price", "duration_minutes"]


@extend_schema_view(list=extend_schema(tags=["barbers"]))
class BarberViewSet(SafeDeleteMixin, ReadAuthenticatedWriteAdminMixin, viewsets.ModelViewSet):
    queryset = Barber.objects.all()
    serializer_class = BarberSerializer
    filterset_class = BarberFilter
    filter_backends = [
        *viewsets.ModelViewSet.filter_backends,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["first_name", "last_name"]
    ordering_fields = ["first_name", "last_name"]


@extend_schema_view(list=extend_schema(tags=["working-hours"]))
class WorkingHoursViewSet(viewsets.ModelViewSet):
    """Gestión de horarios laborales: solo administrador."""

    queryset = WorkingHours.objects.select_related("barber")
    serializer_class = WorkingHoursSerializer
    permission_classes = [IsAdminRole]
    filterset_class = WorkingHoursFilter
