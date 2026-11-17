from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Barber, Service, WorkingHours


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["id", "name", "duration_minutes", "price", "is_active"]

    def validate_duration_minutes(self, value):
        if value <= 0:
            raise serializers.ValidationError("La duración debe ser mayor a 0.")
        return value


class BarberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Barber
        fields = ["id", "first_name", "last_name", "is_active"]


class WorkingHoursSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkingHours
        fields = ["id", "barber", "weekday", "start_time", "end_time"]

    def validate(self, attrs):
        # Reutilizamos WorkingHours.clean() (fin > inicio y sin bloques superpuestos),
        # armando una instancia con los datos nuevos mezclados con los existentes.
        instance = self.instance or WorkingHours()
        for field in ("barber", "weekday", "start_time", "end_time"):
            setattr(instance, field, attrs.get(field, getattr(instance, field, None)))
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return attrs
