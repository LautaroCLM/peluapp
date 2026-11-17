import django_filters

from .models import Barber, Service, WorkingHours


class ServiceFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")

    class Meta:
        model = Service
        fields = ["is_active", "min_price", "max_price"]


class BarberFilter(django_filters.FilterSet):
    class Meta:
        model = Barber
        fields = ["is_active"]


class WorkingHoursFilter(django_filters.FilterSet):
    class Meta:
        model = WorkingHours
        fields = ["barber", "weekday"]
