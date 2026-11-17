"""Regla 7: condiciones de carrera al reservar.

Usan transaction=True porque cada hilo abre su propia conexión y necesita
ver los datos ya confirmados (commit) por el test."""

import threading
from datetime import time, timedelta

import pytest
from django.db import connection, connections

from apps.accounts.models import User
from apps.appointments.exceptions import SlotUnavailable
from apps.appointments.models import ACTIVE_STATUSES, Appointment
from apps.appointments.services import create_appointment
from apps.catalog.models import WorkingHours

pytestmark = pytest.mark.django_db(transaction=True)

THREADS = 8


def run_concurrently(target, n=THREADS):
    """Lanza n hilos que arrancan al mismo tiempo y devuelve la lista de resultados."""
    barrier = threading.Barrier(n)
    outcomes = [None] * n

    def worker(i):
        try:
            barrier.wait()
            outcomes[i] = target(i)
        except Exception as exc:  # noqa: BLE001 - queremos ver cualquier resultado
            outcomes[i] = exc
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return outcomes


def test_only_one_of_many_concurrent_bookings_wins(barber, service, next_monday):
    WorkingHours.objects.create(barber=barber, weekday=0, start_time=time(9), end_time=time(18))
    users = [User.objects.create_user(f"u{i}@example.com", "pass12345") for i in range(THREADS)]
    start = next_monday.replace(hour=10)
    connection.close()  # el hilo principal no debe mantener transacciones abiertas

    def book(i):
        return create_appointment(client=users[i], barber=barber, service=service, start_at=start)

    outcomes = run_concurrently(book)

    winners = [o for o in outcomes if isinstance(o, Appointment)]
    losers = [o for o in outcomes if isinstance(o, SlotUnavailable)]
    unexpected = [o for o in outcomes if not isinstance(o, Appointment | SlotUnavailable)]

    assert unexpected == []
    assert len(winners) == 1
    assert len(losers) == THREADS - 1
    assert (
        Appointment.objects.filter(
            barber=barber, start_at=start, status__in=ACTIVE_STATUSES
        ).count()
        == 1
    )


def test_concurrent_bookings_of_different_slots_all_succeed(barber, service, next_monday):
    """El lock serializa por peluquero pero no debe rechazar horarios distintos."""
    WorkingHours.objects.create(barber=barber, weekday=0, start_time=time(9), end_time=time(18))
    users = [User.objects.create_user(f"u{i}@example.com", "pass12345") for i in range(THREADS)]
    base = next_monday.replace(hour=9)
    connection.close()

    def book(i):
        start = base + timedelta(minutes=30 * i)
        return create_appointment(client=users[i], barber=barber, service=service, start_at=start)

    outcomes = run_concurrently(book)

    assert all(isinstance(o, Appointment) for o in outcomes), outcomes
    assert Appointment.objects.filter(barber=barber).count() == THREADS


def test_overlapping_but_not_identical_concurrent_bookings(barber, service, next_monday):
    """Rangos que se pisan parcialmente (no solo idénticos): a lo sumo uno entra."""
    WorkingHours.objects.create(barber=barber, weekday=0, start_time=time(9), end_time=time(18))
    users = [User.objects.create_user(f"u{i}@example.com", "pass12345") for i in range(THREADS)]
    base = next_monday.replace(hour=10)
    connection.close()

    def book(i):
        start = base + timedelta(minutes=3 * i)  # 10:00 ... 10:21, todos se pisan entre sí
        return create_appointment(client=users[i], barber=barber, service=service, start_at=start)

    outcomes = run_concurrently(book)

    assert [o for o in outcomes if not isinstance(o, Appointment | SlotUnavailable)] == []
    assert sum(isinstance(o, Appointment) for o in outcomes) == 1
