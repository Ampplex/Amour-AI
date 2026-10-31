from rest_framework import serializers
from .models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "namespace",
            "email",
            "username",
            "name",
            "given_name",
            "family_name",
            "picture",
            "auth_provider",
            "google_sub",
            "verified_email",
            "created_at",
            "last_login",
        ]
        read_only_fields = ["id", "namespace", "created_at", "last_login"]

class GoogleAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField(required=False, allow_blank=True)
    profile = serializers.DictField(required=False)

class SignupSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=6, write_only=True)

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

class ConfirmEmailSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    code = serializers.CharField(required=False, allow_blank=True)
    token = serializers.CharField(required=False, allow_blank=True)

class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    code = serializers.CharField(required=False, allow_blank=True)
    token = serializers.CharField(required=False, allow_blank=True)
    new_password = serializers.CharField(min_length=6, write_only=True)

class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()

