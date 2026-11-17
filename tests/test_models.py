from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.appointments.models import Appointment, AppointmentStatus
from apps.catalog.models import Service, WorkingHours

pytestmark = pytest.mark.django_db


def make_appointment(client, barber, service, start, minutes=30, status="pending"):
    return Appointment.objects.create(
        client=client,
        barber=barber,
        service=service,
        start_at=start,
        end_at=start + timedelta(minutes=minutes),
        status=status,
        price=service.price,
    )


def test_overlapping_appointments_are_rejected_by_database(
    client_user, other_client, barber, service, next_monday
):
    start = next_monday.replace(hour=10)
    make_appointment(client_user, barber, service, start)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_appointment(other_client, barber, service, start + timedelta(minutes=15))


def test_back_to_back_appointments_are_allowed(
    client_user, other_client, barber, service, next_monday
):
    start = next_monday.replace(hour=10)
    make_appointment(client_user, barber, service, start)
    make_appointment(other_client, barber, service, start + timedelta(minutes=30))


def test_cancelled_appointment_frees_the_slot(
    client_user, other_client, barber, service, next_monday
):
    start = next_monday.replace(hour=10)
    make_appointment(client_user, barber, service, start, status=AppointmentStatus.CANCELLED)
    make_appointment(other_client, barber, service, start)


def test_same_time_different_barbers_is_allowed(
    client_user, other_client, barber, service, next_monday
):
    from apps.catalog.models import Barber

    other_barber = Barber.objects.create(first_name="Ana", last_name="Gómez")
    start = next_monday.replace(hour=10)
    make_appointment(client_user, barber, service, start)
    make_appointment(other_client, other_barber, service, start)


def test_appointment_end_must_be_after_start(client_user, barber, service, next_monday):
    start = next_monday.replace(hour=10)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_appointment(client_user, barber, service, start, minutes=0)


def test_service_duration_must_be_positive(db):
    with pytest.raises(IntegrityError), transaction.atomic():
        Service.objects.create(name="Mal", duration_minutes=0, price=Decimal("1"))


def test_working_hours_end_must_be_after_start(barber):
    from datetime import time

    with pytest.raises(IntegrityError), transaction.atomic():
        WorkingHours.objects.create(barber=barber, weekday=0, start_time=time(18), end_time=time(9))


def test_working_hours_overlap_fails_validation(barber, monday_hours):
    from datetime import time

    overlapping = WorkingHours(barber=barber, weekday=0, start_time=time(17), end_time=time(20))
    with pytest.raises(ValidationError):
        overlapping.clean()
