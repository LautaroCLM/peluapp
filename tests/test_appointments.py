from datetime import time, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.appointments.models import Appointment, AppointmentStatus
from apps.catalog.models import Barber, WorkingHours

pytestmark = pytest.mark.django_db


def results(response):
    return response.data["results"]


def make(client, barber, service, start, status=AppointmentStatus.PENDING):
    return Appointment.objects.create(
        client=client,
        barber=barber,
        service=service,
        start_at=start,
        end_at=start + timedelta(minutes=service.duration_minutes),
        status=status,
        price=service.price,
    )


@pytest.fixture
def book(auth_client, barber, service):
    """Hace POST /api/appointments/ como `user` en la hora `start`."""

    def _book(user, start, **overrides):
        payload = {"barber": barber.id, "service": service.id, "start_at": start.isoformat()}
        payload.update(overrides)
        return auth_client(user).post(reverse("appointment-list"), payload, format="json")

    return _book


# ======================================================================
# Crear turno: reglas 1, 2 y 3
# ======================================================================


def test_create_appointment_sets_server_side_fields(
    book, client_user, service, monday_hours, next_monday
):
    start = next_monday.replace(hour=10)
    r = book(client_user, start)
    assert r.status_code == 201
    assert r.data["status"] == "pending"
    assert r.data["client"] == client_user.id
    assert Decimal(r.data["price"]) == service.price
    # Regla 3: end_at = start_at + duración del servicio.
    appt = Appointment.objects.get(pk=r.data["id"])
    assert appt.end_at - appt.start_at == timedelta(minutes=service.duration_minutes)


def test_client_cannot_override_end_at_price_or_client(
    book, client_user, other_client, service, monday_hours, next_monday
):
    start = next_monday.replace(hour=10)
    r = book(
        client_user,
        start,
        end_at=(start + timedelta(hours=5)).isoformat(),
        price="1.00",
        client=other_client.id,
        status="completed",
    )
    assert r.status_code == 201
    appt = Appointment.objects.get(pk=r.data["id"])
    assert appt.client == client_user
    assert appt.price == service.price
    assert appt.status == AppointmentStatus.PENDING
    assert appt.end_at - appt.start_at == timedelta(minutes=service.duration_minutes)


def test_create_requires_authentication(client, barber, service, next_monday):
    r = client.post(reverse("appointment-list"), {})
    assert r.status_code == 401


def test_create_in_the_past_is_rejected(book, client_user, monday_hours, next_monday):
    r = book(client_user, next_monday.replace(hour=10) - timedelta(days=30))
    assert r.status_code == 400


def test_create_outside_working_hours_is_rejected(book, client_user, monday_hours, next_monday):
    # Antes de abrir (9:00), y empezando a las 20:00 (cerrado).
    assert book(client_user, next_monday.replace(hour=7)).status_code == 400
    assert book(client_user, next_monday.replace(hour=20)).status_code == 400


def test_create_must_end_inside_working_hours(book, client_user, monday_hours, next_monday):
    # Cierra 18:00 y el servicio dura 30 min: 17:45 terminaría 18:15.
    assert book(client_user, next_monday.replace(hour=17, minute=45)).status_code == 400
    assert book(client_user, next_monday.replace(hour=17, minute=30)).status_code == 201


def test_create_on_day_without_hours_is_rejected(book, client_user, monday_hours, next_monday):
    tuesday = next_monday + timedelta(days=1)
    assert book(client_user, tuesday.replace(hour=10)).status_code == 400


def test_create_cannot_span_lunch_break(book, client_user, barber, next_monday):
    WorkingHours.objects.create(barber=barber, weekday=0, start_time=time(9), end_time=time(12))
    WorkingHours.objects.create(barber=barber, weekday=0, start_time=time(15), end_time=time(18))
    assert book(client_user, next_monday.replace(hour=11, minute=45)).status_code == 400
    assert book(client_user, next_monday.replace(hour=12)).status_code == 400
    assert book(client_user, next_monday.replace(hour=15)).status_code == 201


def test_overlapping_appointment_is_rejected_with_409(
    book, client_user, other_client, monday_hours, next_monday
):
    start = next_monday.replace(hour=10)
    assert book(client_user, start).status_code == 201
    assert book(other_client, start).status_code == 409
    assert book(other_client, start + timedelta(minutes=15)).status_code == 409
    assert book(other_client, start - timedelta(minutes=15)).status_code == 409


def test_back_to_back_appointments_are_allowed(
    book, client_user, other_client, monday_hours, next_monday
):
    start = next_monday.replace(hour=10)
    assert book(client_user, start).status_code == 201
    assert book(other_client, start + timedelta(minutes=30)).status_code == 201
    assert book(other_client, start - timedelta(minutes=30)).status_code == 201


def test_cancelled_slot_can_be_booked_again(
    book, client_user, other_client, auth_client, monday_hours, next_monday
):
    start = next_monday.replace(hour=10)
    appt_id = book(client_user, start).data["id"]
    assert (
        auth_client(client_user).post(reverse("appointment-cancel", args=[appt_id])).status_code
        == 200
    )
    assert book(other_client, start).status_code == 201


def test_two_barbers_can_have_the_same_time(
    book, client_user, other_client, barber, monday_hours, next_monday
):
    other = Barber.objects.create(first_name="Ana", last_name="Gómez")
    WorkingHours.objects.create(barber=other, weekday=0, start_time=time(9), end_time=time(18))
    start = next_monday.replace(hour=10)
    assert book(client_user, start).status_code == 201
    assert book(other_client, start, barber=other.id).status_code == 201


def test_inactive_barber_or_service_is_rejected(
    book, client_user, barber, service, monday_hours, next_monday
):
    start = next_monday.replace(hour=10)
    barber.is_active = False
    barber.save()
    assert book(client_user, start).status_code == 400
    barber.is_active = True
    barber.save()
    service.is_active = False
    service.save()
    assert book(client_user, start).status_code == 400


def test_availability_reflects_new_booking(
    book, auth_client, client_user, barber, service, monday_hours, next_monday
):
    start = next_monday.replace(hour=10)
    book(client_user, start)
    r = auth_client(client_user).get(
        reverse("availability"),
        {"barber": barber.id, "service": service.id, "date": next_monday.date()},
    )
    starts = [s["start"] for s in r.data["slots"]]
    assert not any(s.startswith(start.strftime("%Y-%m-%dT10:00")) for s in starts)


# ======================================================================
# Regla 5: cada cliente ve y modifica solo lo suyo
# ======================================================================


def test_client_lists_only_own_appointments(
    auth_client, client_user, other_client, barber, service, next_monday
):
    make(client_user, barber, service, next_monday.replace(hour=10))
    make(other_client, barber, service, next_monday.replace(hour=11))
    r = auth_client(client_user).get(reverse("appointment-list"))
    assert r.status_code == 200
    assert [a["client"] for a in results(r)] == [client_user.id]


def test_admin_lists_all_appointments(
    auth_client, admin_user, client_user, other_client, barber, service, next_monday
):
    make(client_user, barber, service, next_monday.replace(hour=10))
    make(other_client, barber, service, next_monday.replace(hour=11))
    assert len(results(auth_client(admin_user).get(reverse("appointment-list")))) == 2


def test_client_cannot_see_someone_elses_appointment(
    auth_client, client_user, other_client, barber, service, next_monday
):
    appt = make(other_client, barber, service, next_monday.replace(hour=10))
    r = auth_client(client_user).get(reverse("appointment-detail", args=[appt.id]))
    assert r.status_code == 404


def test_admin_can_see_any_appointment(
    auth_client, admin_user, other_client, barber, service, next_monday
):
    appt = make(other_client, barber, service, next_monday.replace(hour=10))
    assert (
        auth_client(admin_user).get(reverse("appointment-detail", args=[appt.id])).status_code
        == 200
    )


def test_client_cannot_cancel_or_change_others(
    auth_client, client_user, other_client, barber, service, next_monday
):
    appt = make(other_client, barber, service, next_monday.replace(hour=10))
    api = auth_client(client_user)
    assert api.post(reverse("appointment-cancel", args=[appt.id])).status_code == 404
    assert api.patch(
        reverse("appointment-detail", args=[appt.id]), {"status": "completed"}
    ).status_code in (404, 405)
    appt.refresh_from_db()
    assert appt.status == AppointmentStatus.PENDING


def test_appointments_cannot_be_updated_or_deleted_via_api(
    auth_client, client_user, barber, service, next_monday
):
    appt = make(client_user, barber, service, next_monday.replace(hour=10))
    api = auth_client(client_user)
    url = reverse("appointment-detail", args=[appt.id])
    assert api.put(url, {}).status_code == 405
    assert api.patch(url, {}).status_code == 405
    assert api.delete(url).status_code == 405


# ======================================================================
# Regla 4: cancelación con anticipación mínima
# ======================================================================


def test_client_can_cancel_with_enough_notice(
    auth_client, client_user, barber, service, next_monday
):
    appt = make(client_user, barber, service, next_monday.replace(hour=10))  # ≥ 7 días
    r = auth_client(client_user).post(reverse("appointment-cancel", args=[appt.id]))
    assert r.status_code == 200
    assert r.data["status"] == "cancelled"
    assert r.data["cancelled_at"] is not None


def test_client_cannot_cancel_too_late(auth_client, client_user, barber, service):
    from django.utils import timezone

    appt = make(client_user, barber, service, timezone.now() + timedelta(hours=2))
    r = auth_client(client_user).post(reverse("appointment-cancel", args=[appt.id]))
    assert r.status_code == 400
    appt.refresh_from_db()
    assert appt.status == AppointmentStatus.PENDING


def test_minimum_notice_is_configurable(settings, auth_client, client_user, barber, service):
    from django.utils import timezone

    appt = make(client_user, barber, service, timezone.now() + timedelta(hours=30))
    settings.CANCELLATION_MIN_HOURS = 48
    assert (
        auth_client(client_user).post(reverse("appointment-cancel", args=[appt.id])).status_code
        == 400
    )
    settings.CANCELLATION_MIN_HOURS = 24
    assert (
        auth_client(client_user).post(reverse("appointment-cancel", args=[appt.id])).status_code
        == 200
    )


def test_notice_boundary_is_inclusive(auth_client, client_user, barber, service):
    from django.utils import timezone

    # Un poco más de 24 h de anticipación: permitido.
    appt = make(client_user, barber, service, timezone.now() + timedelta(hours=24, minutes=1))
    assert (
        auth_client(client_user).post(reverse("appointment-cancel", args=[appt.id])).status_code
        == 200
    )


def test_admin_can_cancel_without_notice(auth_client, admin_user, client_user, barber, service):
    from django.utils import timezone

    appt = make(client_user, barber, service, timezone.now() + timedelta(hours=1))
    r = auth_client(admin_user).post(reverse("appointment-cancel", args=[appt.id]))
    assert r.status_code == 200


def test_cannot_cancel_twice_or_cancel_completed(
    auth_client, client_user, barber, service, next_monday
):
    cancelled = make(
        client_user, barber, service, next_monday.replace(hour=10), AppointmentStatus.CANCELLED
    )
    completed = make(
        client_user, barber, service, next_monday.replace(hour=11), AppointmentStatus.COMPLETED
    )
    api = auth_client(client_user)
    assert api.post(reverse("appointment-cancel", args=[cancelled.id])).status_code == 409
    assert api.post(reverse("appointment-cancel", args=[completed.id])).status_code == 409


# ======================================================================
# Confirmar y completar (solo administrador)
# ======================================================================


def test_admin_confirms_then_completes(
    auth_client, admin_user, client_user, barber, service, next_monday
):
    appt = make(client_user, barber, service, next_monday.replace(hour=10))
    api = auth_client(admin_user)
    assert api.post(reverse("appointment-confirm", args=[appt.id])).data["status"] == "confirmed"
    assert api.post(reverse("appointment-complete", args=[appt.id])).data["status"] == "completed"


def test_client_cannot_confirm_or_complete(auth_client, client_user, barber, service, next_monday):
    appt = make(client_user, barber, service, next_monday.replace(hour=10))
    api = auth_client(client_user)
    assert api.post(reverse("appointment-confirm", args=[appt.id])).status_code == 403
    assert api.post(reverse("appointment-complete", args=[appt.id])).status_code == 403


def test_invalid_transitions_return_409(
    auth_client, admin_user, client_user, barber, service, next_monday
):
    pending = make(client_user, barber, service, next_monday.replace(hour=10))
    cancelled = make(
        client_user, barber, service, next_monday.replace(hour=11), AppointmentStatus.CANCELLED
    )
    api = auth_client(admin_user)
    # No se puede completar un turno que no está confirmado.
    assert api.post(reverse("appointment-complete", args=[pending.id])).status_code == 409
    # No se puede confirmar uno cancelado.
    assert api.post(reverse("appointment-confirm", args=[cancelled.id])).status_code == 409


def test_confirmed_appointment_still_blocks_the_slot(
    book, auth_client, admin_user, client_user, other_client, monday_hours, next_monday
):
    start = next_monday.replace(hour=10)
    appt_id = book(client_user, start).data["id"]
    auth_client(admin_user).post(reverse("appointment-confirm", args=[appt_id]))
    assert book(other_client, start).status_code == 409


# ======================================================================
# Filtros, orden y paginación
# ======================================================================


def test_filters_by_status_barber_and_dates(auth_client, client_user, barber, service, next_monday):
    other = Barber.objects.create(first_name="Ana", last_name="Gómez")
    a = make(client_user, barber, service, next_monday.replace(hour=10))
    b = make(client_user, other, service, next_monday.replace(hour=11), AppointmentStatus.CANCELLED)
    c = make(client_user, barber, service, next_monday.replace(hour=12) + timedelta(days=7))
    api = auth_client(client_user)
    url = reverse("appointment-list")

    ids = lambda r: {x["id"] for x in results(r)}  # noqa: E731
    assert ids(api.get(url, {"status": "cancelled"})) == {b.id}
    assert ids(api.get(url, {"barber": other.id})) == {b.id}
    assert ids(api.get(url, {"start_to": (next_monday + timedelta(days=1)).isoformat()})) == {
        a.id,
        b.id,
    }
    assert ids(api.get(url, {"start_from": (next_monday + timedelta(days=3)).isoformat()})) == {
        c.id
    }


def test_ordering_and_pagination(auth_client, client_user, barber, service, next_monday):
    for i in range(25):
        make(client_user, barber, service, next_monday + timedelta(days=i, hours=9))
    api = auth_client(client_user)
    r = api.get(reverse("appointment-list"), {"ordering": "start_at"})
    assert r.data["count"] == 25
    assert len(r.data["results"]) == 20
    starts = [a["start_at"] for a in r.data["results"]]
    assert starts == sorted(starts)
    assert len(api.get(r.data["next"]).data["results"]) == 5
