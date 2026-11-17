"""Reglas de negocio de los turnos.

Las vistas solo traducen HTTP; todo lo que es "regla" vive acá para poder
testearlo sin pasar por la API y reutilizarlo (comando de seed, admin, etc.).
"""

from datetime import datetime, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.catalog.models import Barber, Service, WorkingHours

from .exceptions import BusinessRuleViolation, InvalidTransition, SlotUnavailable
from .models import ACTIVE_STATUSES, Appointment, AppointmentStatus


def _fits_in_working_hours(barber: Barber, start_at: datetime, end_at: datetime) -> bool:
    """True si [start_at, end_at] cabe entero dentro de un bloque laboral del peluquero."""
    local_start = timezone.localtime(start_at)
    local_end = timezone.localtime(end_at)
    if local_start.date() != local_end.date():
        return False  # cruzaría la medianoche
    return WorkingHours.objects.filter(
        barber=barber,
        weekday=local_start.weekday(),
        start_time__lte=local_start.time(),
        end_time__gte=local_end.time(),
    ).exists()


def create_appointment(
    *,
    client,
    barber: Barber,
    service: Service,
    start_at: datetime,
    now: datetime | None = None,
) -> Appointment:
    """Reserva un turno aplicando las reglas 1, 2, 3 y 7.

    Concurrencia: dentro de una transacción se bloquea la fila del peluquero con
    SELECT ... FOR UPDATE, de modo que dos reservas del mismo peluquero se
    serializan. Aun así la restricción de exclusión de la base es la garantía
    final: si algo se escapara, PostgreSQL rechaza la inserción.
    """
    now = now or timezone.now()

    if not barber.is_active or not service.is_active:
        raise BusinessRuleViolation("El peluquero o el servicio no están disponibles.")

    # Regla 2 (parte futuro)
    if start_at <= now:
        raise BusinessRuleViolation("El turno debe ser en el futuro.")

    # Regla 3: la duración la define el servicio, nunca el cliente.
    end_at = start_at + timedelta(minutes=service.duration_minutes)

    try:
        with transaction.atomic():
            # Regla 7: serializa las reservas concurrentes del mismo peluquero.
            Barber.objects.select_for_update().get(pk=barber.pk)

            # Regla 2 (parte horario laboral)
            if not _fits_in_working_hours(barber, start_at, end_at):
                raise BusinessRuleViolation(
                    "El turno debe estar dentro del horario laboral del peluquero."
                )

            # Regla 1: chequeo explícito para dar un error claro...
            overlaps = Appointment.objects.filter(
                barber=barber,
                status__in=ACTIVE_STATUSES,
                start_at__lt=end_at,
                end_at__gt=start_at,
            ).exists()
            if overlaps:
                raise SlotUnavailable()

            return Appointment.objects.create(
                client=client,
                barber=barber,
                service=service,
                start_at=start_at,
                end_at=end_at,
                price=service.price,  # precio congelado
            )
    except IntegrityError as exc:
        # ...y la restricción de la base como red de seguridad.
        raise SlotUnavailable() from exc


def _lock(appointment: Appointment) -> Appointment:
    """Relee el turno bloqueando su fila: evita que dos cambios de estado
    simultáneos (ej: cancelar y confirmar) se pisen. Debe llamarse dentro de atomic()."""
    return Appointment.objects.select_for_update().get(pk=appointment.pk)


def cancel_appointment(appointment: Appointment, *, user, now: datetime | None = None):
    """Cancela un turno. El cliente debe respetar la anticipación mínima (regla 4);
    el administrador puede cancelar siempre."""
    now = now or timezone.now()

    with transaction.atomic():
        appointment = _lock(appointment)

        if appointment.status not in ACTIVE_STATUSES:
            raise InvalidTransition("Solo se pueden cancelar turnos pendientes o confirmados.")

        if not user.is_admin_role:
            min_notice = timedelta(hours=settings.CANCELLATION_MIN_HOURS)
            if appointment.start_at - now < min_notice:
                raise BusinessRuleViolation(
                    f"Solo se puede cancelar con al menos {settings.CANCELLATION_MIN_HOURS} "
                    "horas de anticipación."
                )

        appointment.status = AppointmentStatus.CANCELLED
        appointment.cancelled_at = now
        appointment.save(update_fields=["status", "cancelled_at"])
    return appointment


def confirm_appointment(appointment: Appointment) -> Appointment:
    with transaction.atomic():
        appointment = _lock(appointment)
        if appointment.status != AppointmentStatus.PENDING:
            raise InvalidTransition("Solo se pueden confirmar turnos pendientes.")
        appointment.status = AppointmentStatus.CONFIRMED
        appointment.save(update_fields=["status"])
    return appointment


def complete_appointment(appointment: Appointment) -> Appointment:
    with transaction.atomic():
        appointment = _lock(appointment)
        if appointment.status != AppointmentStatus.CONFIRMED:
            raise InvalidTransition("Solo se pueden completar turnos confirmados.")
        appointment.status = AppointmentStatus.COMPLETED
        appointment.save(update_fields=["status"])
    return appointment
