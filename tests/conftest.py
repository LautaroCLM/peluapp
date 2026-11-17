from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from apps.accounts.models import Role, User
from apps.catalog.models import Barber, Service, WorkingHours

TZ = ZoneInfo("America/Argentina/Buenos_Aires")


@pytest.fixture
def client_user(db):
    return User.objects.create_user("cliente@example.com", "pass12345", role=Role.CLIENT)


@pytest.fixture
def other_client(db):
    return User.objects.create_user("otro@example.com", "pass12345", role=Role.CLIENT)


@pytest.fixture
def admin_user(db):
    return User.objects.create_user("admin@example.com", "pass12345", role=Role.ADMIN)


@pytest.fixture
def barber(db):
    return Barber.objects.create(first_name="Juan", last_name="Pérez")


@pytest.fixture
def service(db):
    return Service.objects.create(name="Corte", duration_minutes=30, price=Decimal("5000"))


@pytest.fixture
def next_monday():
    """Primer lunes futuro, al menos 7 días adelante, a medianoche local."""
    d = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=7)
    while d.weekday() != 0:
        d += timedelta(days=1)
    return d


@pytest.fixture
def monday_hours(barber):
    return WorkingHours.objects.create(
        barber=barber, weekday=0, start_time=time(9, 0), end_time=time(18, 0)
    )
