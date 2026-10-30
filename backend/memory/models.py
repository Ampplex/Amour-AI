import uuid
from django.db import models
from django.conf import settings

class Persona(models.Model):
    """
    Persona model stored in PostgreSQL (Neon).
    Represents user-created or system avatars with custom identity, 
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
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.visibility})"
