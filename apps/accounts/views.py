from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import RegisterSerializer


@extend_schema(tags=["auth"], summary="Registro de cliente")
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes: list = []


@extend_schema(tags=["auth"], summary="Login: devuelve access y refresh JWT")
class LoginView(TokenObtainPairView):
    pass


@extend_schema(tags=["auth"], summary="Renueva el access token con el refresh")
class RefreshView(TokenRefreshView):
    pass
