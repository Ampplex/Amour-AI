import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        
        # Ensure user id is created if not supplied
        user_id = extra_fields.pop("id", str(uuid.uuid4()))
        # Set user id as their namespace
        namespace = extra_fields.pop("namespace", user_id)
        
        user = self.model(id=user_id, namespace=namespace, email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User Model for Amour AI.
    Every user id is their unique namespace in Reeve / Neo4j memory graph.
    """
    id = models.CharField(primary_key=True, max_length=128, default=uuid.uuid4, editable=False)
    # The unique memory namespace for Reeve Neo4j partition
    namespace = models.CharField(max_length=128, unique=True, db_index=True)
    
    email = models.EmailField(unique=True, db_index=True)
    username = models.CharField(max_length=64, unique=True, null=True, blank=True, db_index=True)
    name = models.CharField(max_length=255, blank=True, default="")
    given_name = models.CharField(max_length=128, blank=True, default="")
    family_name = models.CharField(max_length=128, blank=True, default="")
    picture = models.TextField(blank=True, default="")
    
    auth_provider = models.CharField(max_length=32, default="local")  # 'google' or 'local'
    google_sub = models.CharField(max_length=128, blank=True, default="", db_index=True)
    verified_email = models.BooleanField(default=False)
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def clean_username(self, candidate_username: str) -> str:
        """Sanitizes username: lowercase alphanumeric and underscores only."""
        import re
        clean = re.sub(r"[^a-zA-Z0-9_]", "", candidate_username.strip().lower())
        return clean or f"user_{uuid.uuid4().hex[:6]}"

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.namespace:
            self.namespace = self.id
        # Automatically generate default unique username from email if not set
        if not self.username and self.email:
            base_handle = self.clean_username(self.email.split("@")[0])
            candidate = base_handle
            counter = 1
            while User.objects.filter(username__iexact=candidate).exclude(id=self.id).exists():
                candidate = f"{base_handle}_{counter}"
                counter += 1
            self.username = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.email} ({self.namespace})"
