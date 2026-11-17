from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.appointments.models import Appointment
from apps.catalog.models import Barber, Service, WorkingHours

pytestmark = pytest.mark.django_db


def results(response):
    return response.data["results"]


# ---------- Autenticación real de punta a punta ----------


def test_protected_endpoint_requires_token(client_user):
    api = APIClient()
    assert api.get(reverse("service-list")).status_code == 401

    tokens = api.post(
        reverse("auth-login"), {"email": client_user.email, "password": "pass12345"}
    ).data
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    assert api.get(reverse("service-list")).status_code == 200


# ---------- Servicios ----------


def test_admin_can_crud_services(auth_client, admin_user):
    api = auth_client(admin_user)
    r = api.post(
        reverse("service-list"),
        {"name": "Barba", "duration_minutes": 20, "price": "3000.00"},
    )
    assert r.status_code == 201
    url = reverse("service-detail", args=[r.data["id"]])
    assert api.patch(url, {"price": "3500.00"}).data["price"] == "3500.00"
    assert api.delete(url).status_code == 204


def test_client_cannot_write_services(auth_client, client_user, service):
    api = auth_client(client_user)
    payload = {"name": "X", "duration_minutes": 10, "price": "1"}
    assert api.post(reverse("service-list"), payload).status_code == 403
    url = reverse("service-detail", args=[service.id])
    assert api.patch(url, {"price": "1"}).status_code == 403
    assert api.delete(url).status_code == 403


def test_client_can_read_only_active_services(auth_client, client_user, admin_user, service):
    Service.objects.create(name="Viejo", duration_minutes=10, price=Decimal("1"), is_active=False)
    assert len(results(auth_client(client_user).get(reverse("service-list")))) == 1
    assert len(results(auth_client(admin_user).get(reverse("service-list")))) == 2


def test_service_duration_must_be_positive(auth_client, admin_user):
    r = auth_client(admin_user).post(
        reverse("service-list"), {"name": "Cero", "duration_minutes": 0, "price": "10"}
    )
    assert r.status_code == 400


def test_service_filters_search_and_ordering(auth_client, admin_user):
    Service.objects.create(name="Corte", duration_minutes=30, price=Decimal("5000"))
    Service.objects.create(name="Barba", duration_minutes=20, price=Decimal("3000"))
    Service.objects.create(name="Tintura", duration_minutes=90, price=Decimal("12000"))
    api = auth_client(admin_user)
    url = reverse("service-list")

    names = [s["name"] for s in results(api.get(url, {"min_price": 4000, "ordering": "price"}))]
    assert names == ["Corte", "Tintura"]
    assert [s["name"] for s in results(api.get(url, {"search": "bar"}))] == ["Barba"]


def test_pagination_envelope(auth_client, admin_user):
    for i in range(25):
        Service.objects.create(name=f"S{i:02}", duration_minutes=10, price=Decimal("1"))
    r = auth_client(admin_user).get(reverse("service-list"))
    assert r.data["count"] == 25
    assert len(r.data["results"]) == 20
    assert r.data["next"] is not None


def test_cannot_delete_service_with_appointments(
    auth_client, admin_user, client_user, barber, service, next_monday
):
    start = next_monday.replace(hour=10)
    Appointment.objects.create(
        client=client_user,
        barber=barber,
        service=service,
        start_at=start,
        end_at=start + timedelta(minutes=30),
        price=service.price,
    )
    r = auth_client(admin_user).delete(reverse("service-detail", args=[service.id]))
    assert r.status_code == 409
    assert Service.objects.filter(id=service.id).exists()


# ---------- Peluqueros ----------


def test_admin_can_crud_barbers(auth_client, admin_user):
    api = auth_client(admin_user)
    r = api.post(reverse("barber-list"), {"first_name": "Ana", "last_name": "Gómez"})
    assert r.status_code == 201
    url = reverse("barber-detail", args=[r.data["id"]])
    assert api.patch(url, {"is_active": False}).data["is_active"] is False
    assert api.delete(url).status_code == 204


def test_client_cannot_write_barbers(auth_client, client_user, barber):
    api = auth_client(client_user)
    payload = {"first_name": "A", "last_name": "B"}
    assert api.post(reverse("barber-list"), payload).status_code == 403
    assert api.delete(reverse("barber-detail", args=[barber.id])).status_code == 403


def test_barber_search_and_active_filter(auth_client, admin_user, barber):
    Barber.objects.create(first_name="Ana", last_name="Gómez", is_active=False)
    api = auth_client(admin_user)
    url = reverse("barber-list")
    assert len(results(api.get(url, {"is_active": "true"}))) == 1
    assert len(results(api.get(url, {"search": "gómez"}))) == 1


# ---------- Horarios laborales ----------


def test_working_hours_are_admin_only(auth_client, client_user, barber):
    api = auth_client(client_user)
    assert api.get(reverse("working-hours-list")).status_code == 403
    payload = {"barber": barber.id, "weekday": 0, "start_time": "09:00", "end_time": "13:00"}
    assert api.post(reverse("working-hours-list"), payload).status_code == 403


def test_admin_can_create_multiple_blocks_same_day(auth_client, admin_user, barber):
    api = auth_client(admin_user)
    url = reverse("working-hours-list")
    for start, end in [("09:00", "13:00"), ("15:00", "20:00")]:
        r = api.post(url, {"barber": barber.id, "weekday": 0, "start_time": start, "end_time": end})
        assert r.status_code == 201
    assert WorkingHours.objects.filter(barber=barber).count() == 2


def test_overlapping_working_hours_are_rejected(auth_client, admin_user, barber):
    api = auth_client(admin_user)
    url = reverse("working-hours-list")
    base = {"barber": barber.id, "weekday": 0}
    assert api.post(url, {**base, "start_time": "09:00", "end_time": "13:00"}).status_code == 201
    r = api.post(url, {**base, "start_time": "12:00", "end_time": "16:00"})
    assert r.status_code == 400


def test_working_hours_end_must_be_after_start(auth_client, admin_user, barber):
    r = auth_client(admin_user).post(
        reverse("working-hours-list"),
        {"barber": barber.id, "weekday": 0, "start_time": "18:00", "end_time": "09:00"},
    )
    assert r.status_code == 400


def test_updating_a_block_does_not_conflict_with_itself(auth_client, admin_user, monday_hours):
    r = auth_client(admin_user).patch(
        reverse("working-hours-detail", args=[monday_hours.id]), {"end_time": "19:00"}
    )
    assert r.status_code == 200


def test_working_hours_filters(auth_client, admin_user, barber, monday_hours):
    other = Barber.objects.create(first_name="Ana", last_name="Gómez")
    WorkingHours.objects.create(barber=other, weekday=1, start_time="09:00", end_time="12:00")
    api = auth_client(admin_user)
    url = reverse("working-hours-list")
    assert len(results(api.get(url, {"barber": barber.id}))) == 1
    assert len(results(api.get(url, {"weekday": 1}))) == 1
