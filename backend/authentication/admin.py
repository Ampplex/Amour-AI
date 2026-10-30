from django.contrib import admin
from .models import User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "namespace", "auth_provider", "verified_email", "created_at")
    search_fields = ("email", "name", "namespace", "id")
    list_filter = ("auth_provider", "verified_email", "is_staff", "is_active")
    readonly_fields = ("id", "namespace", "created_at", "updated_at", "last_login")
    ordering = ("-created_at",)
