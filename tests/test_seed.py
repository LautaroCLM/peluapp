from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.appointments.models import Appointment, AppointmentStatus
from apps.catalog.models import Barber, Service, WorkingHours

pytestmark = pytest.mark.django_db


def seed(**kwargs):
    call_command("seed_demo", stdout=StringIO(), **kwargs)


def counts():
    return (User.objects.count(), Appointment.objects.count(), WorkingHours.objects.count())


def test_seed_creates_expected_data():
    seed(admin_password="una-clave-de-prueba")
    assert Service.objects.count() == 5
    assert Barber.objects.count() == 3
    # 3 peluqueros x (4 días x 2 bloques + 1 sábado)
    assert WorkingHours.objects.count() == 27
    admin = User.objects.get(email="admin@peluqueria.test")
    assert admin.is_admin_role
    assert admin.check_password("una-clave-de-prueba")
    statuses = set(Appointment.objects.values_list("status", flat=True))
    assert statuses == {
        AppointmentStatus.COMPLETED,
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.PENDING,
        AppointmentStatus.CANCELLED,
    }


def test_seed_is_idempotent():
    seed()
    before = counts()
    seed()
    assert counts() == before


def test_seeded_users_can_log_in():
    seed(admin_password="una-clave-de-prueba")
    api = APIClient()
    r = api.post(
        reverse("auth-login"),
        {"email": "lucia@peluqueria.test", "password": "cliente12345"},
    )
    assert r.status_code == 200
    r = api.post(
        reverse("auth-login"),
        {"email": "admin@peluqueria.test", "password": "una-clave-de-prueba"},
    )
    assert r.status_code == 200
