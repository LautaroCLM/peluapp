from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators
from django.db import models
from django.db.models import F, Func, Q

from apps.catalog.models import Barber, Service


class TsTzRange(Func):
    """Construye un tstzrange(start, end) en SQL para usarlo en la restricción."""

    function = "TSTZRANGE"
    output_field = DateTimeRangeField()


class AppointmentStatus(models.TextChoices):
    PENDING = "pending", "Pendiente"
    CONFIRMED = "confirmed", "Confirmado"
    CANCELLED = "cancelled", "Cancelado"
    COMPLETED = "completed", "Completado"


# Estados que ocupan el horario del peluquero. Un turno cancelado libera el hueco.
ACTIVE_STATUSES = (AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED)


class Appointment(models.Model):
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="appointments"
    )
    barber = models.ForeignKey(Barber, on_delete=models.PROTECT, related_name="appointments")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="appointments")
    start_at = models.DateTimeField()
    # end_at = start_at + duración del servicio; lo calcula el servidor, no el cliente.
    end_at = models.DateTimeField()
    status = models.CharField(
        max_length=10, choices=AppointmentStatus.choices, default=AppointmentStatus.PENDING
    )
    # Precio congelado al reservar: si el servicio cambia de precio, el turno no cambia.
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_at"]
        indexes = [
            models.Index(fields=["barber", "start_at"], name="appt_barber_start_idx"),
            models.Index(fields=["client", "start_at"], name="appt_client_start_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_at__gt=F("start_at")), name="appt_end_after_start"
            ),
            # Garantía final contra superposiciones, incluso con requests concurrentes:
            # PostgreSQL rechaza dos turnos activos del mismo peluquero con rangos que se pisan.
            ExclusionConstraint(
                name="appt_no_overlap_per_barber",
                expressions=[
                    ("barber", RangeOperators.EQUAL),
                    (TsTzRange("start_at", "end_at"), RangeOperators.OVERLAPS),
                ],
                condition=Q(status__in=[s.value for s in ACTIVE_STATUSES]),
            ),
        ]

    def __str__(self):
        return f"{self.client} con {self.barber} el {self.start_at:%Y-%m-%d %H:%M}"
