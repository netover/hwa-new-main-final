
"""
Core configuration for FastAPI application
"""
from pydantic import BaseSettings
from typing import Optional, List
import os

class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Server settings
    server_host: str = "127.0.0.1"
    server_port: int = 8000

    # Environment
    environment: str = "development"
    debug: bool = True

    # Security
    secret_key: str = "your-secret-key-here"  # TODO: Move to environment variable
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Redis settings
    redis_url: str = "redis://localhost:6379"
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # TWS settings (Trading Workstation)
    tws_host: str = "localhost"
    tws_port: int = 31111
    tws_user: str = "twsuser"
    tws_password: str = "twspass"

    # File upload settings
    upload_dir: str = "uploads"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: List[str] = [".txt", ".pdf", ".docx", ".md", ".json"]

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds

    # Logging
    log_level: str = "INFO"
    structured_logging: bool = True

    # CORS settings
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]

    class Config:
        env_file = ".env"
        case_sensitive = False

# Global settings instance
settings = Settings()
