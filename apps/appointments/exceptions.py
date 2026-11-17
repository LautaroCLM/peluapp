from rest_framework import status
from rest_framework.exceptions import APIException


class BusinessRuleViolation(APIException):
    """El pedido es válido en forma pero incumple una regla de negocio (400)."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "business_rule_violation"
    default_detail = "Se incumple una regla de negocio."


class SlotUnavailable(APIException):
    """El horario ya está ocupado: conflicto con el estado actual (409)."""

    status_code = status.HTTP_409_CONFLICT
    default_code = "slot_unavailable"
    default_detail = "El peluquero ya tiene un turno en ese horario."


class InvalidTransition(APIException):
    """El turno no puede pasar al estado pedido desde el actual (409)."""

    status_code = status.HTTP_409_CONFLICT
    default_code = "invalid_transition"
    default_detail = "El turno no puede cambiar a ese estado."
