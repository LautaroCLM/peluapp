from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class Role(models.TextChoices):
    CLIENT = "client", "Cliente"
    ADMIN = "admin", "Administrador"


class UserManager(BaseUserManager):
    """Manager que usa el email como identificador en lugar de username."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("El email es obligatorio")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("role", Role.CLIENT)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("role", Role.ADMIN)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    # Se inicia sesión con el email, no hay username.
    username = None
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.CLIENT)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    @property
    def is_admin_role(self) -> bool:
        return self.role == Role.ADMIN

    def __str__(self):
        return self.email
