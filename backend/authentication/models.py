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

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.namespace:
            self.namespace = self.id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.email} ({self.namespace})"
