import django_filters

from .models import Appointment


class AppointmentFilter(django_filters.FilterSet):
    start_from = django_filters.IsoDateTimeFilter(field_name="start_at", lookup_expr="gte")
    start_to = django_filters.IsoDateTimeFilter(field_name="start_at", lookup_expr="lte")

    class Meta:
        model = Appointment
        fields = ["status", "barber", "service", "client", "start_from", "start_to"]
