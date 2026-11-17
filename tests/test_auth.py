import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.accounts.permissions import IsAdminRole, IsOwnerOrAdmin

pytestmark = pytest.mark.django_db

PASSWORD = "pass12345"


@pytest.fixture
def api():
    return APIClient()


def test_register_creates_client(api):
    r = api.post(
        reverse("auth-register"),
        {"email": "Nuevo@Example.com", "password": "UnaClaveSegura77", "first_name": "Ana"},
    )
    assert r.status_code == 201
    assert "password" not in r.data
    user = User.objects.get(email="nuevo@example.com")
    assert user.role == Role.CLIENT
    assert user.check_password("UnaClaveSegura77")


def test_register_ignores_role_field(api):
    r = api.post(
        reverse("auth-register"),
        {"email": "x@example.com", "password": "UnaClaveSegura77", "role": "admin"},
    )
    assert r.status_code == 201
    assert User.objects.get(email="x@example.com").role == Role.CLIENT


def test_register_rejects_duplicate_email(api, client_user):
    r = api.post(
        reverse("auth-register"),
        {"email": client_user.email.upper(), "password": "UnaClaveSegura77"},
    )
    assert r.status_code == 400
    assert "email" in r.data


def test_register_rejects_weak_password(api):
    r = api.post(reverse("auth-register"), {"email": "d@example.com", "password": "123"})
    assert r.status_code == 400
    assert "password" in r.data


def test_login_returns_access_and_refresh(api, client_user):
    r = api.post(reverse("auth-login"), {"email": client_user.email, "password": PASSWORD})
    assert r.status_code == 200
    assert {"access", "refresh"} <= set(r.data)


def test_login_wrong_password_is_rejected(api, client_user):
    r = api.post(reverse("auth-login"), {"email": client_user.email, "password": "mal"})
    assert r.status_code == 401


def test_refresh_returns_new_access(api, client_user):
    tokens = api.post(
        reverse("auth-login"), {"email": client_user.email, "password": PASSWORD}
    ).data
    r = api.post(reverse("auth-refresh"), {"refresh": tokens["refresh"]})
    assert r.status_code == 200
    assert "access" in r.data


def test_access_token_authenticates_requests(api, client_user):
    tokens = api.post(
        reverse("auth-login"), {"email": client_user.email, "password": PASSWORD}
    ).data
    from rest_framework_simplejwt.authentication import JWTAuthentication

    request = type("R", (), {"META": {"HTTP_AUTHORIZATION": f"Bearer {tokens['access']}"}})()
    user, _ = JWTAuthentication().authenticate(request)
    assert user == client_user


class _Req:
    def __init__(self, user):
        self.user = user


class _Obj:
    def __init__(self, client_id):
        self.client_id = client_id


def test_is_admin_role_permission(client_user, admin_user):
    perm = IsAdminRole()
    assert perm.has_permission(_Req(admin_user), None)
    assert not perm.has_permission(_Req(client_user), None)


def test_is_owner_or_admin_permission(client_user, other_client, admin_user):
    perm = IsOwnerOrAdmin()
    obj = _Obj(client_user.id)
    assert perm.has_object_permission(_Req(client_user), None, obj)
    assert perm.has_object_permission(_Req(admin_user), None, obj)
    assert not perm.has_object_permission(_Req(other_client), None, obj)


def test_swagger_docs_are_available(api):
    assert api.get("/api/docs/").status_code == 200
    assert api.get("/api/schema/").status_code == 200
