"""Cálculo de horarios disponibles de un peluquero (regla de negocio 6)."""

from datetime import date, datetime, timedelta

from django.conf import settings
from django.utils import timezone

from apps.catalog.models import Barber, Service, WorkingHours

from .models import ACTIVE_STATUSES, Appointment


def _local_datetime(day: date, t) -> datetime:
    """Combina fecha + hora y la interpreta en la zona horaria del proyecto."""
    return datetime.combine(day, t, tzinfo=timezone.get_current_timezone())


def get_available_slots(
    barber: Barber,
    day: date,
    service: Service,
    *,
    now: datetime | None = None,
    step_minutes: int | None = None,
) -> list[tuple[datetime, datetime]]:
    """Devuelve la lista de (inicio, fin) en los que se puede reservar `service`
    con `barber` el día `day`.

    Un horario es válido si:
      1. entra completo dentro de un bloque de trabajo del peluquero ese día,
      2. no se superpone con un turno activo (pendiente o confirmado),
      3. empieza en el futuro.

    Los candidatos arrancan al inicio de cada bloque y avanzan de a `step_minutes`.
    `now` se puede inyectar para testear sin depender del reloj.
    """
    now = now or timezone.now()
    step = timedelta(minutes=step_minutes or settings.SLOT_STEP_MINUTES)
    duration = timedelta(minutes=service.duration_minutes)

    blocks = WorkingHours.objects.filter(barber=barber, weekday=day.weekday())
    if not blocks:
        return []

    # Una sola consulta con los turnos activos que tocan este día.
    day_start = _local_datetime(day, datetime.min.time())
    day_end = day_start + timedelta(days=1)
    busy = list(
        Appointment.objects.filter(
            barber=barber,
            status__in=ACTIVE_STATUSES,
            start_at__lt=day_end,
            end_at__gt=day_start,
        ).values_list("start_at", "end_at")
    )

    slots = []
    for block in blocks:
        block_end = _local_datetime(day, block.end_time)
        start = _local_datetime(day, block.start_time)
        while start + duration <= block_end:
            end = start + duration
            # Dos intervalos se superponen si cada uno empieza antes de que termine el otro.
            overlaps = any(start < b_end and b_start < end for b_start, b_end in busy)
            if start > now and not overlaps:
                slots.append((start, end))
            start += step
    return sorted(slots)
