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
            "is_active",
            "is_staff",
            "is_superuser",
            "created_at",
            "updated_at",
            "last_login",
        ]
        read_only_fields = ["id", "namespace", "created_at", "updated_at", "last_login"]


class AdminUserSerializer(serializers.ModelSerializer):
    personas_count = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()

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
            "is_active",
            "is_staff",
            "is_superuser",
            "created_at",
            "updated_at",
            "last_login",
            "personas_count",
            "likes_count",
        ]
        read_only_fields = ["id", "namespace", "created_at", "updated_at", "last_login"]

    def get_personas_count(self, obj):
        try:
            return obj.personas.count()
        except Exception:
            return 0

    def get_likes_count(self, obj):
        try:
            return obj.persona_likes.count()
        except Exception:
            return 0


class AdminUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = User
        fields = [
            "email",
            "password",
            "username",
            "name",
            "given_name",
            "family_name",
            "picture",
            "auth_provider",
            "verified_email",
            "is_active",
            "is_staff",
            "is_superuser",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        user = User.objects.create_user(password=password, **validated_data)
        return user

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

