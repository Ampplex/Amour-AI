import uuid
from django.db import models
from django.conf import settings

class Persona(models.Model):
    """
    Persona model stored in PostgreSQL (Neon).
    Represents user-created or community avatars with custom identity, 
    border palette, roleplay greeting, and synthesized memory prompt.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="personas",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=120)
    tagline = models.CharField(max_length=255, blank=True, default="")
    border_color = models.CharField(max_length=32, default="#F43F5E")
    image_url = models.TextField(blank=True, default="")
    greeting = models.TextField(blank=True, default="")
    memory_prompt = models.TextField(blank=True, default="")
    visibility = models.CharField(max_length=20, default="private")  # 'private' or 'public'
    is_community = models.BooleanField(default=False)
    likes_count = models.IntegerField(default=0)
    chats_count = models.IntegerField(default=0)
    publisher_name = models.CharField(max_length=120, blank=True, default="Amour Creator")
    publisher_handle = models.CharField(max_length=120, blank=True, default="@creator")
    publisher_avatar = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.visibility})"


class PersonaLike(models.Model):
    """
    Tracks likes on community personas.
    Explicitly connects the liking user ID to the persona and the persona poster/creator ID.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    persona = models.ForeignKey(Persona, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="persona_likes",
    )
    user_identifier = models.CharField(max_length=120, db_index=True)
    poster = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_persona_likes",
    )
    poster_identifier = models.CharField(max_length=120, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("persona", "user_identifier")

    def __str__(self):
        return f"{self.user_identifier} liked {self.persona.name} (posted by {self.poster_identifier})"


class PublisherFollow(models.Model):
    """
    Tracks publisher follow relationships.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    publisher_handle = models.CharField(max_length=120, db_index=True)
    user_identifier = models.CharField(max_length=120, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("publisher_handle", "user_identifier")

