from django.contrib import admin
from .models import (
    Persona,
    PersonaLike,
    PublisherFollow,
    PersonaChatMessage,
    PersonaRelationshipState,
    UserMemoryKeyBackup,
)


@admin.register(Persona)
class PersonaAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "publisher_name",
        "visibility",
        "is_community",
        "likes_count",
        "chats_count",
        "age",
        "created_at",
    )
    search_fields = ("name", "tagline", "publisher_name", "publisher_handle", "greeting", "memory_prompt")
    list_filter = ("visibility", "is_community", "created_at")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-created_at",)
    fieldsets = (
        ("Basic Info", {
            "fields": ("id", "name", "tagline", "age", "border_color", "image_url")
        }),
        ("Roleplay & Memory Prompts", {
            "fields": ("greeting", "memory_prompt")
        }),
        ("Community & Stats", {
            "fields": ("visibility", "is_community", "creator", "publisher_name", "publisher_handle", "publisher_avatar", "likes_count", "chats_count")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at")
        }),
    )


@admin.register(PersonaChatMessage)
class PersonaChatMessageAdmin(admin.ModelAdmin):
    list_display = (
        "sender",
        "user_identifier",
        "persona_identifier",
        "conflict_stage",
        "short_text",
        "created_at",
    )
    search_fields = ("text", "user_identifier", "persona_identifier", "client_message_id", "namespace")
    list_filter = ("sender", "conflict_stage", "created_at")
    readonly_fields = ("id", "created_at")
    ordering = ("-created_at",)

    def short_text(self, obj):
        return obj.text[:80] + ("..." if len(obj.text) > 80 else "")
    short_text.short_description = "Message"


@admin.register(PersonaRelationshipState)
class PersonaRelationshipStateAdmin(admin.ModelAdmin):
    list_display = (
        "user_identifier",
        "persona_identifier",
        "conflict_stage",
        "conflict_reason",
        "updated_at",
    )
    search_fields = ("user_identifier", "persona_identifier", "conflict_reason")
    list_filter = ("conflict_stage", "created_at", "updated_at")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(PersonaLike)
class PersonaLikeAdmin(admin.ModelAdmin):
    list_display = ("user_identifier", "persona", "poster_identifier", "created_at")
    search_fields = ("user_identifier", "poster_identifier", "persona__name")
    list_filter = ("created_at",)
    readonly_fields = ("id", "created_at")


@admin.register(PublisherFollow)
class PublisherFollowAdmin(admin.ModelAdmin):
    list_display = ("publisher_handle", "user_identifier", "created_at")
    search_fields = ("publisher_handle", "user_identifier")
    list_filter = ("created_at",)
    readonly_fields = ("id", "created_at")


@admin.register(UserMemoryKeyBackup)
class UserMemoryKeyBackupAdmin(admin.ModelAdmin):
    list_display = ("user_identifier", "created_at", "updated_at")
    search_fields = ("user_identifier",)
    readonly_fields = ("id", "created_at", "updated_at")
