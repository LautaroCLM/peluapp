"""Carga datos de ejemplo para probar la API: `python manage.py seed_demo`.

Es idempotente: se puede ejecutar varias veces sin duplicar datos.
"""

import os
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.appointments.models import Appointment, AppointmentStatus
from apps.appointments.services import (
    cancel_appointment,
    confirm_appointment,
    create_appointment,
)
from apps.catalog.models import Barber, Service, WorkingHours

ADMIN_EMAIL = "admin@peluqueria.test"
CLIENT_PASSWORD = "cliente12345"
CLIENTS = [
    ("lucia@peluqueria.test", "Lucía", "Fernández"),
    ("martin@peluqueria.test", "Martín", "Suárez"),
    ("sofia@peluqueria.test", "Sofía", "Romero"),
]
SERVICES = [
    ("Corte de pelo", 30, "5000.00"),
    ("Barba", 20, "3000.00"),
    ("Corte y barba", 45, "7500.00"),
    ("Lavado y peinado", 25, "4000.00"),
    ("Tintura", 90, "12000.00"),
]
BARBERS = [("Juan", "Pérez"), ("Carolina", "Gómez"), ("Diego", "Ruiz")]

# Martes a viernes: mañana y tarde (con pausa de almuerzo). Sábado: solo mañana.
WEEK_BLOCKS = {weekday: [(time(9), time(13)), (time(15), time(20))] for weekday in (1, 2, 3, 4)}
WEEK_BLOCKS[5] = [(time(9), time(14))]


def local_dt(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=timezone.get_current_timezone())


def next_weekday(weekday: int, *, min_days_ahead: int) -> date:
    day = timezone.localdate() + timedelta(days=min_days_ahead)
    while day.weekday() != weekday:
        day += timedelta(days=1)
    return day


def previous_weekday(weekday: int) -> date:
    day = timezone.localdate() - timedelta(days=1)
    while day.weekday() != weekday:
        day -= timedelta(days=1)
    return day


class Command(BaseCommand):
    help = "Carga datos de ejemplo (administrador, clientes, servicios, peluqueros y turnos)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--admin-password",
            default=os.environ.get("SEED_ADMIN_PASSWORD", "admin12345"),
            help="Contraseña del administrador demo (o variable SEED_ADMIN_PASSWORD).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        admin = self._create_admin(options["admin_password"])
        clients = self._create_clients()
        services = self._create_services()
        barbers = self._create_barbers()
        self._create_working_hours(barbers)
        created = self._create_appointments(clients, barbers, services)

        self.stdout.write(self.style.SUCCESS("Datos de ejemplo listos."))
        self.stdout.write(f"  Administrador: {admin.email} (contraseña: --admin-password)")
        emails = ", ".join(email for email, *_ in CLIENTS)
        self.stdout.write(f"  Clientes: {emails} (contraseña: {CLIENT_PASSWORD})")
        self.stdout.write(f"  Servicios: {len(services)} | Peluqueros: {len(barbers)}")
        self.stdout.write(f"  Turnos creados en esta corrida: {created}")

    def _create_admin(self, password):
        admin, created = User.objects.get_or_create(
            email=ADMIN_EMAIL,
            defaults={
                "role": Role.ADMIN,
                "is_staff": True,
                "is_superuser": True,
                "first_name": "Admin",
            },
        )
        if created:
            admin.set_password(password)
            admin.save()
        return admin

    def _create_clients(self):
        clients = []
        for email, first, last in CLIENTS:
            user, created = User.objects.get_or_create(
                email=email, defaults={"first_name": first, "last_name": last}
            )
            if created:
                user.set_password(CLIENT_PASSWORD)
                user.save()
            clients.append(user)
        return clients

    def _create_services(self):
        return [
            Service.objects.get_or_create(
                name=name, defaults={"duration_minutes": minutes, "price": Decimal(price)}
            )[0]
            for name, minutes, price in SERVICES
        ]

    def _create_barbers(self):
        return [
            Barber.objects.get_or_create(first_name=first, last_name=last)[0]
            for first, last in BARBERS
        ]

    def _create_working_hours(self, barbers):
        for barber in barbers:
            if barber.working_hours.exists():
                continue
            WorkingHours.objects.bulk_create(
                WorkingHours(barber=barber, weekday=weekday, start_time=start, end_time=end)
                for weekday, blocks in WEEK_BLOCKS.items()
                for start, end in blocks
            )

    def _create_appointments(self, clients, barbers, services):
        # Solo se cargan turnos si los clientes demo todavía no tienen ninguno.
        if Appointment.objects.filter(client__in=clients).exists():
            return 0

        corte, barba, combo, lavado, tintura = services
        juan, carolina, diego = barbers
        lucia, martin, sofia = clients
        tuesday = next_weekday(1, min_days_ahead=3)
        wednesday = next_weekday(2, min_days_ahead=3)

        # Historial pasado: se inserta directo porque la API no permite reservar en el pasado.
        for client, barber, service, day, hour in [
            (lucia, juan, corte, previous_weekday(1), 10),
            (martin, carolina, combo, previous_weekday(2), 11),
        ]:
            start = local_dt(day, hour)
            Appointment.objects.create(
                client=client,
                barber=barber,
                service=service,
                start_at=start,
                end_at=start + timedelta(minutes=service.duration_minutes),
                status=AppointmentStatus.COMPLETED,
                price=service.price,
            )

        # Turnos futuros: pasan por las reglas de negocio reales.
        booked = [
            create_appointment(
                client=lucia, barber=juan, service=corte, start_at=local_dt(tuesday, 10)
            ),
            create_appointment(
                client=martin, barber=juan, service=barba, start_at=local_dt(tuesday, 10, 30)
            ),
            create_appointment(
                client=sofia, barber=carolina, service=tintura, start_at=local_dt(wednesday, 9)
            ),
            create_appointment(
                client=lucia, barber=diego, service=lavado, start_at=local_dt(wednesday, 16)
            ),
        ]
        confirm_appointment(booked[0])
        confirm_appointment(booked[2])
        # Un turno cancelado de ejemplo (libera el horario).
        cancelled = create_appointment(
            client=sofia, barber=diego, service=corte, start_at=local_dt(tuesday, 17)
        )
        cancel_appointment(cancelled, user=sofia)
        return 2 + len(booked) + 1
