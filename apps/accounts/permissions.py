from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """Solo usuarios autenticados con rol de administrador."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_admin_role)


class IsOwnerOrAdmin(BasePermission):
    """A nivel objeto: el dueño del turno (campo `client`) o un administrador."""

    def has_object_permission(self, request, view, obj):
        user = request.user
        return user.is_admin_role or obj.client_id == user.id
