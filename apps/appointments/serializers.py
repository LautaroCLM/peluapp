from rest_framework import serializers

from apps.catalog.models import Barber, Service


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
