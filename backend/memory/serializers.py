from rest_framework import serializers
from .models import Persona, PersonaChatMessage


class PersonaChatMessageSerializer(serializers.ModelSerializer):
    user_id = serializers.CharField(source="user_identifier", read_only=True)
    persona_id = serializers.CharField(source="persona_identifier", read_only=True)

    class Meta:
        model = PersonaChatMessage
        fields = [
            "id",
            "user_id",
            "persona_id",
            "namespace",
            "sender",
            "text",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class PersonaSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source="creator.name", read_only=True, default="Anonymous")
    creator_id = serializers.CharField(source="creator.id", read_only=True, default=None)

    class Meta:
        model = Persona
        fields = [
            "id",
            "name",
            "tagline",
            "border_color",
            "image_url",
            "greeting",
            "memory_prompt",
            "visibility",
            "is_community",
            "likes_count",
            "chats_count",
            "publisher_name",
            "publisher_handle",
            "publisher_avatar",
            "creator_name",
            "creator_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
