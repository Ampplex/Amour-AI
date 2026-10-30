import os
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "Amour AI Backend"
    API_V1_STR: str = "/api"
    
    # PostgreSQL Configuration
    # Uses local PostgreSQL by default, easily overridden by setting DATABASE_URL in .env
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://ankeshkumar@localhost:5432/amour_db"
    )
    
    # JWT Authentication
    SECRET_KEY: str = os.getenv("SECRET_KEY", "amour-ai-super-secret-production-key-2026-secure-jwt")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30  # 30 days
    
    # Google OAuth Client IDs (Web & Android)
    GOOGLE_CLIENT_IDS: List[str] = [
        "665738151857-0f765nnvu4no6qhbdbua132vfv2iu10k.apps.googleusercontent.com",  # Web Client ID
        "665738151857-epjtqdvodprak901bkmi2k9t68t15830.apps.googleusercontent.com",  # Android Client ID
    ]

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
