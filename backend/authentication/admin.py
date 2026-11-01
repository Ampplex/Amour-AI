from django.contrib import admin
from .models import User, EmailVerificationToken

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "username",
        "name",
        "auth_provider",
        "is_active",
        "verified_email",
        "is_staff",
        "is_superuser",
        "created_at",
    )
    search_fields = ("email", "username", "name", "id", "namespace", "google_sub")
    list_filter = ("auth_provider", "is_active", "verified_email", "is_staff", "is_superuser")
    readonly_fields = ("id", "namespace", "google_sub", "created_at", "updated_at", "last_login")
    ordering = ("-created_at",)
    
    fieldsets = (
        ("Account Identification", {
            "fields": ("id", "namespace", "email", "username", "auth_provider", "google_sub")
        }),
        ("Personal Profile", {
            "fields": ("name", "given_name", "family_name", "picture")
        }),
        ("Security & Permissions", {
            "fields": ("is_active", "verified_email", "is_staff", "is_superuser", "groups", "user_permissions")
        }),
        ("Timestamps", {
            "fields": ("last_login", "created_at", "updated_at")
        }),
    )


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ("email", "code", "token_type", "is_used", "created_at", "expires_at")
    search_fields = ("email", "code", "token")
    list_filter = ("token_type", "is_used")
    readonly_fields = ("id", "created_at")

