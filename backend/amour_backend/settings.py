import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("SECRET_KEY", "amour-ai-django-fallback-secret-key-2026")
DEBUG = os.environ.get("DEBUG", "True").lower() == "true"

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    # Amour AI apps
    "authentication",
    "memory",
    "response_generator",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "amour_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "amour_backend.wsgi.application"

# PostgreSQL Database Configuration
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "amour_db"),
        "USER": os.environ.get("DB_USER", "ankeshkumar"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

# Auto-configure from cloud DATABASE_URL (Neon, Render, Supabase, AWS RDS)
# Best practice per Neon skill: Use direct unpooled connection for migrations, pooled for web app
import sys
is_migrating = any(cmd in sys.argv for cmd in ["migrate", "makemigrations", "inspectdb", "dbshell", "test"])
target_db_url = os.environ.get("DATABASE_URL_UNPOOLED") if is_migrating else os.environ.get("DATABASE_URL")
if not target_db_url:
    target_db_url = os.environ.get("DATABASE_URL")

if target_db_url:
    try:
        import dj_database_url
        is_pooler = "-pooler" in target_db_url
        DATABASES["default"] = dj_database_url.parse(
            target_db_url,
            conn_max_age=0 if is_pooler else 600,
            conn_health_checks=not is_pooler,
            ssl_require=True,
        )
    except ImportError:
        pass

# Custom User Model
AUTH_USER_MODEL = "authentication.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# CSRF Trusted Origins for cloud deployments
CSRF_TRUSTED_ORIGINS = [
    "https://*.onrender.com",
    "https://*.up.railway.app",
    "https://*.fly.dev",
    "https://*.apprunner.aws",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CORS Settings (Mobile friendly)
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# Django REST Framework Settings
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

# SimpleJWT Settings
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=90),
    "ROTATE_REFRESH_TOKENS": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Reeve & Google OAuth Settings
REEVE_API_KEY = os.environ.get("REEVE_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen/qwen3.8-27b")
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "bedrock")
GOOGLE_CLIENT_IDS = [
    os.environ.get("GOOGLE_WEB_CLIENT_ID", "665738151857-0f765nnvu4no6qhbdbua132vfv2iu10k.apps.googleusercontent.com"),
    os.environ.get("GOOGLE_ANDROID_CLIENT_ID", "665738151857-epjtqdvodprak901bkmi2k9t68t15830.apps.googleusercontent.com"),
]

# Brevo Email Service & Public App URL
BREVO_API_KEY = os.environ.get(
    "BREVO_API_KEY",
    "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",
)
BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL", "ankesh3905222@gmail.com")
BREVO_SENDER_NAME = os.environ.get("BREVO_SENDER_NAME", "Amour AI")
BACKEND_PUBLIC_URL = os.environ.get(
    "BACKEND_PUBLIC_URL",
    os.environ.get("RENDER_EXTERNAL_URL", "https://amour-ai-d6a8.onrender.com")
)

