"""Compatibility shim for settings with legacy aliases."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict

from pydantic import Field

from resync.config.settings import Settings as CoreSettings

try:  # pragma: no cover - make Environment optional during docs builds
    from resync.config.settings_types import Environment  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    from enum import Enum

    class Environment(str, Enum):  # type: ignore[override]
        DEVELOPMENT = "development"
        TESTING = "testing"
        STAGING = "staging"
        PRODUCTION = "production"


LegacyResolver = Callable[[CoreSettings], Any]

LEGACY_ALIASES: Dict[str, LegacyResolver] = {
    # Basic metadata
    "BASE_DIR": lambda s: s.base_dir,
    "PROJECT_NAME": lambda s: s.project_name,
    "PROJECT_VERSION": lambda s: s.project_version,
    "DESCRIPTION": lambda s: s.description,
    "LOG_LEVEL": lambda s: s.log_level,
    "ENVIRONMENT": lambda s: s.environment.value,
    "DEBUG": lambda s: s.environment == Environment.DEVELOPMENT,
    # Databases
    "NEO4J_URI": lambda s: s.neo4j_uri,
    "NEO4J_USER": lambda s: s.neo4j_user,
    "NEO4J_PASSWORD": lambda s: s.neo4j_password,
    # Redis
    "REDIS_URL": lambda s: s.redis_url,
    # LLM + admin
    "LLM_ENDPOINT": lambda s: s.llm_endpoint,
    "LLM_API_KEY": lambda s: s.llm_api_key,
    "ADMIN_USERNAME": lambda s: s.admin_username,
    "ADMIN_PASSWORD": lambda s: s.admin_password,
    # TWS
    "TWS_MOCK_MODE": lambda s: s.tws_mock_mode,
    "TWS_HOST": lambda s: s.tws_host,
    "TWS_PORT": lambda s: s.tws_port,
    "TWS_USER": lambda s: s.tws_user,
    "TWS_PASSWORD": lambda s: s.tws_password,
    # Server
    "SERVER_HOST": lambda s: s.server_host,
    "SERVER_PORT": lambda s: s.server_port,
    # CORS
    "CORS_ALLOWED_ORIGINS": lambda s: s.cors_allowed_origins,
    "CORS_ALLOW_CREDENTIALS": lambda s: s.cors_allow_credentials,
    "CORS_ALLOW_METHODS": lambda s: s.cors_allow_methods,
    "CORS_ALLOW_HEADERS": lambda s: s.cors_allow_headers,
    # Static files
    "STATIC_CACHE_MAX_AGE": lambda s: s.static_cache_max_age,
    # Model names
    "AUDITOR_MODEL_NAME": lambda s: s.auditor_model_name,
    "AGENT_MODEL_NAME": lambda s: s.agent_model_name,
    # DB pool
    "DB_POOL_MIN_SIZE": lambda s: s.db_pool_min_size,
    "DB_POOL_MAX_SIZE": lambda s: s.db_pool_max_size,
    "DB_POOL_IDLE_TIMEOUT": lambda s: s.db_pool_idle_timeout,
    "DB_POOL_CONNECT_TIMEOUT": lambda s: s.db_pool_connect_timeout,
    "DB_POOL_HEALTH_CHECK_INTERVAL": lambda s: s.db_pool_health_check_interval,
    "DB_POOL_MAX_LIFETIME": lambda s: s.db_pool_max_lifetime,
    # Redis pool
    "REDIS_POOL_MIN_SIZE": lambda s: s.redis_pool_min_size,
    "REDIS_POOL_MAX_SIZE": lambda s: s.redis_pool_max_size,
    "REDIS_POOL_IDLE_TIMEOUT": lambda s: s.redis_pool_idle_timeout,
    "REDIS_POOL_CONNECT_TIMEOUT": lambda s: s.redis_pool_connect_timeout,
    "REDIS_POOL_HEALTH_CHECK_INTERVAL": lambda s: s.redis_pool_health_check_interval,
    "REDIS_POOL_MAX_LIFETIME": lambda s: s.redis_pool_max_lifetime,
    # HTTP pool
    "HTTP_POOL_MIN_SIZE": lambda s: s.http_pool_min_size,
    "HTTP_POOL_MAX_SIZE": lambda s: s.http_pool_max_size,
    "HTTP_POOL_IDLE_TIMEOUT": lambda s: s.http_pool_idle_timeout,
    "HTTP_POOL_CONNECT_TIMEOUT": lambda s: s.http_pool_connect_timeout,
    "HTTP_POOL_HEALTH_CHECK_INTERVAL": lambda s: s.http_pool_health_check_interval,
    "HTTP_POOL_MAX_LIFETIME": lambda s: s.http_pool_max_lifetime,
    # RAG service
    "RAG_SERVICE_URL": lambda s: s.rag_service_url,
    "RAG_SERVICE_TIMEOUT": lambda s: s.rag_service_timeout,
    "RAG_SERVICE_MAX_RETRIES": lambda s: s.rag_service_max_retries,
    "RAG_SERVICE_RETRY_BACKOFF": lambda s: s.rag_service_retry_backoff,
    # Additional legacy constants
    "JINJA2_TEMPLATE_CACHE_SIZE": lambda s: 400
    if s.environment == Environment.PRODUCTION
    else 0,
    "AGENT_CONFIG_PATH": lambda s: Path(s.base_dir) / "config" / "agents.json",
    "MAX_CONCURRENT_AGENT_CREATIONS": lambda s: 5,
    "TWS_ENGINE_NAME": lambda s: "TWS",
    "TWS_ENGINE_OWNER": lambda s: "twsuser",
}


class Settings(CoreSettings):
    """Extend the core settings with legacy properties and guards."""

    redis_pool_min_size: int = Field(
        default=CoreSettings.model_fields["redis_pool_min_size"].default, ge=1
    )
    redis_pool_max_size: int = Field(
        default=CoreSettings.model_fields["redis_pool_max_size"].default, ge=1
    )
    log_sensitive_data_redaction: bool = Field(default=True)

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self._validate_legacy_invariants()

    # ------------------------------------------------------------------
    def _validate_legacy_invariants(self) -> None:
        """Perform additional legacy-only validations."""
        if self.environment == Environment.PRODUCTION:
            insecure_key = "dummy_key_for_development"
            raw_env_key = os.getenv("APP_LLM_API_KEY") or os.getenv("LLM_API_KEY") or ""
            current_key = ""
            try:
                current_key = self.llm_api_key.get_secret_value()
            except AttributeError:
                pass
            if (
                raw_env_key.strip().lower() == insecure_key
                or current_key.strip().lower() == insecure_key
            ):
                raise ValueError("LLM_API_KEY must be set to a valid key in production")

    # ------------------------------------------------------------------
    def __getattr__(self, name: str) -> Any:
        alias = LEGACY_ALIASES.get(name)
        if alias is not None:
            value = alias(self)
            object.__setattr__(self, name, value)
            return value
        return super().__getattr__(name)

    def __repr__(self) -> str:
        base = super().__repr__()
        pattern = re.compile(r"\b\w*(?:password|api_key)\w*\s*=\s*[^,)]*(?:, )?", re.IGNORECASE)
        redacted = pattern.sub("", base)
        # Remove potential leftover double spaces or trailing commas before closing parenthesis
        redacted = re.sub(r",\s*\)", ")", redacted)
        redacted = re.sub(r"\s{2,}", " ", redacted)
        return redacted.strip()


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


BaseSettings = Settings

__all__ = ["settings", "Settings", "Environment", "get_settings", "BaseSettings"]
