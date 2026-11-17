from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class Barber(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Service(models.Model):
    name = models.CharField(max_length=100, unique=True)
    # La duración del turno la define el servicio (regla de negocio 3).
    duration_minutes = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(duration_minutes__gt=0), name="service_duration_positive"
            ),
            models.CheckConstraint(condition=Q(price__gte=0), name="service_price_non_negative"),
        ]

    def __str__(self):
        return self.name


class WorkingHours(models.Model):
    """Un bloque horario de trabajo de un peluquero en un día de la semana.

    Un peluquero puede tener varios bloques el mismo día (ej: 9-13 y 15-20).
    """

    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Lunes"
        TUESDAY = 1, "Martes"
        WEDNESDAY = 2, "Miércoles"
        THURSDAY = 3, "Jueves"
        FRIDAY = 4, "Viernes"
        SATURDAY = 5, "Sábado"
        SUNDAY = 6, "Domingo"

    barber = models.ForeignKey(Barber, on_delete=models.CASCADE, related_name="working_hours")
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["barber", "weekday", "start_time"]
        verbose_name_plural = "working hours"
        constraints = [
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")), name="wh_end_after_start"
            ),
            models.CheckConstraint(
                condition=Q(weekday__gte=0, weekday__lte=6), name="wh_weekday_range"
            ),
        ]

    def __str__(self):
        return f"{self.barber} - {self.get_weekday_display()} {self.start_time}-{self.end_time}"

    def clean(self):
        # Evita bloques que se pisan para el mismo peluquero y día.
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError("La hora de fin debe ser posterior a la de inicio.")
        overlapping = WorkingHours.objects.filter(
            barber_id=self.barber_id,
            weekday=self.weekday,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time,
        ).exclude(pk=self.pk)
        if overlapping.exists():
            raise ValidationError("El bloque se superpone con otro horario del peluquero.")
