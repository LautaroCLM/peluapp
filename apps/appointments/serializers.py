from rest_framework import serializers

from apps.catalog.models import Barber, Service

from .models import Appointment


class AvailabilityQuerySerializer(serializers.Serializer):
    barber = serializers.PrimaryKeyRelatedField(queryset=Barber.objects.filter(is_active=True))
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.filter(is_active=True))
    date = serializers.DateField()


class SlotSerializer(serializers.Serializer):
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()


class AvailabilitySerializer(serializers.Serializer):
    barber = serializers.IntegerField()
    service = serializers.IntegerField()
    date = serializers.DateField()
    slots = SlotSerializer(many=True)


class AppointmentSerializer(serializers.ModelSerializer):
    """Representación de lectura de un turno."""

    class Meta:
        model = Appointment
        fields = [
            "id",
            "client",
            "barber",
            "service",
            "start_at",
            "end_at",
            "status",
            "price",
            "cancelled_at",
            "created_at",
        ]
        read_only_fields = fields


class AppointmentCreateSerializer(serializers.Serializer):
    """Entrada para reservar. El cliente NO envía end_at, price ni client:
    los define el servidor (reglas 3 y 5)."""

    barber = serializers.PrimaryKeyRelatedField(queryset=Barber.objects.filter(is_active=True))
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.filter(is_active=True))
    start_at = serializers.DateTimeField()
