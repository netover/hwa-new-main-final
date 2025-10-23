from pathlib import Path

from pydantic import Field

from .base import Settings


class DevelopmentSettings(Settings):
    TWS_MOCK_MODE: bool = True
    TWS_VERIFY_SSL: bool = False  # SSL verification disabled for development
    # Cache hierarchy settings
    CACHE_HIERARCHY_L1_MAX_SIZE: int = 1000
    CACHE_HIERARCHY_L2_TTL: int = 300
    CACHE_HIERARCHY_L2_CLEANUP_INTERVAL: int = 30
    CACHE_HIERARCHY_NUM_SHARDS: int = 8
    CACHE_HIERARCHY_MAX_WORKERS: int = 4
    # Override other settings for development if needed
    # For example, a local LLM endpoint
    # LLM_ENDPOINT: str = "http://localhost:8001/v1"

    # Knowledge Base and Protection Settings
    KNOWLEDGE_BASE_DIRS: list[Path] = Field(
        default=[Settings.BASE_DIR / "resync/RAG"],
        description="Directories included in the knowledge base (includes all RAG subdirectories)",
    )
    PROTECTED_DIRECTORIES: list[Path] = Field(
        default=[Settings.BASE_DIR / "resync/RAG/BASE"],
        description="Core knowledge base directory protected from deletion",
    )

    # --- CORS Configuration for Development ---
    CORS_ALLOWED_ORIGINS: str = Field(
        default="*",  # Permissive for development
        description="Comma-separated list of allowed origins for CORS in development.",
    )
    CORS_ALLOW_CREDENTIALS: bool = Field(
        default=True,  # Permissive for development
        description="Allow credentials in CORS requests (enabled by default in development).",
    )
    CORS_LOG_VIOLATIONS: bool = Field(
        default=True,  # Log violations even in development
        description="Log CORS violations for debugging in development.",
    )
