from rest_framework import serializers
from .models import Persona

class PersonaSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source="creator.name", read_only=True, default="Anonymous")

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
            "creator_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
