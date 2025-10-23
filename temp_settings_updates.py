from __future__ import annotations

import os
from pathlib import Path

from dynaconf import Dynaconf
from pydantic import BaseModel, Field, field_validator

from resync.core.exceptions import ConfigurationError

# --- Dynamic Configuration with Dynaconf ---
# Load settings from TOML files and environment variables
settings: Dynaconf = Dynaconf(
    envvar_prefix="APP",  # Prefix for environment variables (e.g., APP_TWS_HOST)
    settings_files=[
        "settings.toml",  # Base settings
        f"settings.{os.environ.get('APP_ENV', 'development')}.toml",  # Environment-specific overrides
    ],
    environments=True,  # Enable environment-specific loading
    load_dotenv=False,  # Disable automatic .env loading for CI/CD compatibility
    env_switcher="APP_ENV",  # Use APP_ENV to switch environments
)

# --- Type Definitions (for backward compatibility) ---
ModelEndpoint = str

# Post-process settings for type conversion and dynamic path resolution
# Set BASE_DIR dynamically based on current working directory if not already set
if not hasattr(settings, "BASE_DIR") or not settings.BASE_DIR:
    # Use current working directory as base
    current_dir = Path.cwd()
    settings.BASE_DIR = current_dir

# Ensure BASE_DIR is a Path object and resolve to absolute path
settings.BASE_DIR = Path(settings.BASE_DIR).resolve()


class ApplicationSettings(BaseModel):
    """Pydantic model for application settings validation"""

    neo4j_uri: str = Field(..., alias="NEO4J_URI")
    neo4j_user: str = Field(..., alias="NEO4J_USER")
    neo4j_password: str = Field(..., alias="NEO4J_PASSWORD")
    redis_url: str = Field(..., alias="REDIS_URL")
    llm_endpoint: str = Field(..., alias="LLM_ENDPOINT")
    llm_api_key: str = Field(..., alias="LLM_API_KEY")
    admin_username: str = Field(..., alias="ADMIN_USERNAME")
    admin_password: str = Field(..., alias="ADMIN_PASSWORD")
    tws_mock_mode: bool = Field(default=False, alias="TWS_MOCK_MODE")
    tws_host: str | None = Field(default=None, alias="TWS_HOST")
    tws_port: int | str | None = Field(default=None, alias="TWS_PORT")
    tws_user: str | None = Field(default=None, alias="TWS_USER")
    tws_password: str | None = Field(default=None, alias="TWS_PASSWORD")
    base_dir: Path = Field(default_factory=lambda: Path.cwd, alias="BASE_DIR")

    @field_validator("tws_host", "tws_port", "tws_user", "tws_password")
    @classmethod
    def validate_tws_required_fields(cls, v, values):
        """Validate TWS credentials are provided unless in mock mode"""
        if not values.data.get("tws_mock_mode", False):
            if v is None or (isinstance(v, str) and not v.strip()):
                raise ValueError("TWS credentials are required unless in mock mode")
        return v


def validate_settings(config: Dynaconf) -> None:
    """
    Validates that all critical settings are present and not empty.
    This ensures the application fails fast at startup if misconfigured.

    Args:
        config: The Dynaconf settings object.

    Raises:
        ConfigurationError: If a required setting is missing or empty.
    """
    required_keys = [
        "NEO4J_URI",
        "NEO4J_USER",
        "NEO4J_PASSWORD",
        "REDIS_URL",
        "LLM_ENDPOINT",
        "LLM_API_KEY",
        "ADMIN_USERNAME",
        "ADMIN_PASSWORD",
    ]

    # TWS credentials are only required if not in mock mode.
    if not config.get("TWS_MOCK_MODE", False):
        required_keys.extend(["TWS_HOST", "TWS_PORT", "TWS_USER", "TWS_PASSWORD"])

    missing_keys = [key for key in required_keys if not config.get(key)]

    if missing_keys:
        raise ConfigurationError(
            f"Missing or empty required settings: {', '.join(missing_keys)}. "
            "Please check your .env file or environment variables."
        )


# Run validation immediately after loading settings
validate_settings(settings)
