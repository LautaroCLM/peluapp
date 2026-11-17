from datetime import time, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.appointments.availability import get_available_slots
from apps.appointments.models import Appointment, AppointmentStatus
from apps.catalog.models import Barber, Service, WorkingHours

pytestmark = pytest.mark.django_db


def book(client, barber, service, start, status=AppointmentStatus.PENDING):
    return Appointment.objects.create(
        client=client,
        barber=barber,
        service=service,
        start_at=start,
        end_at=start + timedelta(minutes=service.duration_minutes),
        status=status,
        price=service.price,
    )


def starts(slots):
    return [s.strftime("%H:%M") for s, _ in slots]


# ---------- Algoritmo ----------


def test_no_working_hours_means_no_slots(barber, service, next_monday):
    assert get_available_slots(barber, next_monday.date(), service) == []


def test_day_without_working_hours_has_no_slots(barber, service, monday_hours, next_monday):
    tuesday = (next_monday + timedelta(days=1)).date()
    assert get_available_slots(barber, tuesday, service) == []


def test_slots_cover_the_whole_block(barber, service, monday_hours, next_monday):
    slots = get_available_slots(barber, next_monday.date(), service)
    # Bloque 09:00-18:00, servicio de 30 min, paso de 15 min: 09:00 ... 17:30.
    assert starts(slots)[0] == "09:00"
    assert starts(slots)[-1] == "17:30"
    assert len(slots) == 35
    # La duración del slot la define el servicio.
    assert all(e - s == timedelta(minutes=30) for s, e in slots)


def test_service_longer_than_block_has_no_slots(barber, monday_hours, next_monday):
    long_service = Service.objects.create(name="Larga", duration_minutes=600, price=Decimal("1"))
    assert get_available_slots(barber, next_monday.date(), long_service) == []


def test_slot_must_fit_entirely_in_block(barber, monday_hours, next_monday):
    service_45 = Service.objects.create(name="45", duration_minutes=45, price=Decimal("1"))
    slots = get_available_slots(barber, next_monday.date(), service_45)
    # El último que termina a las 18:00 en punto arranca a las 17:15.
    assert starts(slots)[-1] == "17:15"


def test_lunch_break_between_blocks(barber, service, next_monday):
    WorkingHours.objects.create(barber=barber, weekday=0, start_time=time(9), end_time=time(12))
    WorkingHours.objects.create(barber=barber, weekday=0, start_time=time(15), end_time=time(18))
    result = starts(get_available_slots(barber, next_monday.date(), service))
    assert "11:30" in result
    assert "11:45" not in result  # terminaría 12:15, fuera del bloque
    assert "12:00" not in result and "14:45" not in result
    assert "15:00" in result


def test_existing_appointment_blocks_overlapping_slots(
    barber, service, monday_hours, client_user, next_monday
):
    book(client_user, barber, service, next_monday.replace(hour=10))  # 10:00-10:30
    result = starts(get_available_slots(barber, next_monday.date(), service))
    # 09:45-10:15 y 10:15-10:45 se pisan; 09:30-10:00 y 10:30-11:00 no.
    assert "09:30" in result
    assert "09:45" not in result
    assert "10:00" not in result
    assert "10:15" not in result
    assert "10:30" in result


def test_cancelled_appointment_does_not_block(
    barber, service, monday_hours, client_user, next_monday
):
    book(
        client_user,
        barber,
        service,
        next_monday.replace(hour=10),
        status=AppointmentStatus.CANCELLED,
    )
    assert "10:00" in starts(get_available_slots(barber, next_monday.date(), service))


def test_confirmed_appointment_blocks_slots(
    barber, service, monday_hours, client_user, next_monday
):
    book(
        client_user,
        barber,
        service,
        next_monday.replace(hour=10),
        status=AppointmentStatus.CONFIRMED,
    )
    assert "10:00" not in starts(get_available_slots(barber, next_monday.date(), service))


def test_other_barbers_appointments_do_not_matter(
    barber, service, monday_hours, client_user, next_monday
):
    other = Barber.objects.create(first_name="Ana", last_name="Gómez")
    book(client_user, other, service, next_monday.replace(hour=10))
    assert "10:00" in starts(get_available_slots(barber, next_monday.date(), service))


def test_past_slots_are_excluded(barber, service, monday_hours, next_monday):
    now = next_monday.replace(hour=12, minute=0)
    result = starts(get_available_slots(barber, next_monday.date(), service, now=now))
    assert result[0] == "12:15"  # las 12:00 ya no son futuro


def test_past_date_has_no_slots(barber, service, monday_hours, next_monday):
    now = next_monday + timedelta(days=1)
    assert get_available_slots(barber, next_monday.date(), service, now=now) == []


def test_custom_step_minutes(barber, service, monday_hours, next_monday):
    slots = get_available_slots(barber, next_monday.date(), service, step_minutes=30)
    assert starts(slots)[:3] == ["09:00", "09:30", "10:00"]


# ---------- Endpoint ----------


def url_for(barber, service, day):
    return f"{reverse('availability')}?barber={barber.id}&service={service.id}&date={day}"


def test_availability_requires_authentication(client, barber, service, next_monday):
    assert client.get(url_for(barber, service, next_monday.date())).status_code == 401


def test_availability_endpoint_returns_slots(
    auth_client, client_user, barber, service, monday_hours, next_monday
):
    r = auth_client(client_user).get(url_for(barber, service, next_monday.date()))
    assert r.status_code == 200
    assert r.data["barber"] == barber.id
    assert len(r.data["slots"]) == 35
    assert r.data["slots"][0]["start"].startswith(next_monday.strftime("%Y-%m-%dT09:00:00"))


def test_availability_missing_params_is_400(auth_client, client_user):
    r = auth_client(client_user).get(reverse("availability"))
    assert r.status_code == 400
    assert {"barber", "service", "date"} <= set(r.data)


def test_availability_invalid_date_is_400(auth_client, client_user, barber, service):
    r = auth_client(client_user).get(url_for(barber, service, "no-es-fecha"))
    assert r.status_code == 400


def test_availability_inactive_barber_or_service_is_400(
    auth_client, client_user, barber, service, next_monday
):
    barber.is_active = False
    barber.save()
    r = auth_client(client_user).get(url_for(barber, service, next_monday.date()))
    assert r.status_code == 400
    assert "barber" in r.data
