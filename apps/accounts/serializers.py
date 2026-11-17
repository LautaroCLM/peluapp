from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Role, User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ["id", "email", "password", "first_name", "last_name", "role"]
        # El rol nunca lo elige quien se registra: evita escalar a administrador.
        read_only_fields = ["id", "role"]

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Ya existe un usuario con ese email.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        return User.objects.create_user(role=Role.CLIENT, **validated_data)
