"""Shared types for settings module.

This module contains shared types used by multiple settings-related modules
to avoid circular imports.
"""

from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import Any


class Environment(str, Enum):
    """Ambientes suportados."""

    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TEST = "test"


class CacheHierarchyConfig:
    """Configuration object for cache hierarchy settings (snake_case internally).

    Backward-compatible UPPERCASE aliases are exposed as read-only properties.
    """

    def __init__(
        self,
        l1_max_size: int,
        l2_ttl_seconds: int,
        l2_cleanup_interval: int,
        num_shards: int = 8,
        max_workers: int = 4,
        key_prefix: str = "cache:",
    ) -> None:
        # canonical snake_case
        self.l1_max_size = l1_max_size
        self.l2_ttl_seconds = l2_ttl_seconds
        self.l2_cleanup_interval = l2_cleanup_interval
        self.num_shards = num_shards
        self.max_workers = max_workers
        self.cache_key_prefix = key_prefix

    # --- Legacy UPPERCASE aliases (read-only) ---
    # pylint: disable=invalid-name
    @property
    def L1_MAX_SIZE(self) -> int:
        """Legacy alias for l1_max_size."""
        return self.l1_max_size

    @property
    def L2_TTL_SECONDS(self) -> int:
        """Legacy alias for l2_ttl_seconds."""
        return self.l2_ttl_seconds

    @property
    def L2_CLEANUP_INTERVAL(self) -> int:
        """Legacy alias for l2_cleanup_interval."""
        return self.l2_cleanup_interval

    @property
    def NUM_SHARDS(self) -> int:
        """Legacy alias for num_shards."""
        return self.num_shards

    @property
    def MAX_WORKERS(self) -> int:
        """Legacy alias for max_workers."""
        return self.max_workers

    @property
    def CACHE_KEY_PREFIX(self) -> str:
        """Legacy alias for cache_key_prefix."""
        return self.cache_key_prefix

    # pylint: enable=invalid-name


class SettingsLegacyProperties:
    """Collection of legacy properties for backward compatibility."""

    # pylint: disable=invalid-name
    @property
    def RAG_SERVICE_URL(self) -> str:
        """Legacy alias for rag_service_url."""
        return getattr(self, "rag_service_url")

    @property
    def BASE_DIR(self) -> Path:
        """Legacy alias for base_dir."""
        return getattr(self, "base_dir")

    @property
    def PROJECT_NAME(self) -> str:
        """Legacy alias for project_name."""
        return getattr(self, "project_name")

    @property
    def PROJECT_VERSION(self) -> str:
        """Legacy alias for project_version."""
        return getattr(self, "project_version")

    @property
    def DESCRIPTION(self) -> str:
        """Legacy alias for description."""
        return getattr(self, "description")

    @property
    def LOG_LEVEL(self) -> str:
        """Legacy alias for log_level."""
        return getattr(self, "log_level")

    @property
    def ENVIRONMENT(self) -> str:
        """Legacy alias for environment."""
        env = getattr(self, "environment")
        return env.value if hasattr(env, "value") else str(env)

    @property
    def DEBUG(self) -> bool:
        """Legacy alias: True when environment == DEVELOPMENT."""
        env = getattr(self, "environment")
        return env == Environment.DEVELOPMENT

    @property
    def NEO4J_URI(self) -> str:
        """Legacy alias for neo4j_uri."""
        return getattr(self, "neo4j_uri")

    @property
    def NEO4J_USER(self) -> str | None:
        """Legacy alias for neo4j_user."""
        return getattr(self, "neo4j_user")

    @property
    def NEO4J_PASSWORD(self) -> Any:  # SecretStr | None
        """Legacy alias for neo4j_password."""
        return getattr(self, "neo4j_password")

    @property
    def REDIS_URL(self) -> str:
        """Legacy alias for redis_url."""
        return getattr(self, "redis_url")

    @property
    def LLM_ENDPOINT(self) -> str | None:
        """Legacy alias for llm_endpoint."""
        return getattr(self, "llm_endpoint")

    @property
    def LLM_API_KEY(self) -> Any:  # SecretStr | None
        """Legacy alias for llm_api_key."""
        return getattr(self, "llm_api_key")

    @property
    def LLM_TIMEOUT(self) -> float:
        """Legacy alias for llm_timeout."""
        return getattr(self, "llm_timeout")

    @property
    def ADMIN_USERNAME(self) -> str:
        """Legacy alias for admin_username."""
        return getattr(self, "admin_username")

    @property
    def ADMIN_PASSWORD(self) -> Any:  # SecretStr | None
        """Legacy alias for admin_password."""
        return getattr(self, "admin_password")

    @property
    def TWS_MOCK_MODE(self) -> bool:
        """Legacy alias for tws_mock_mode."""
        return getattr(self, "tws_mock_mode")

    @property
    def TWS_HOST(self) -> str | None:
        """Legacy alias for tws_host."""
        return getattr(self, "tws_host")

    @property
    def TWS_PORT(self) -> int | None:
        """Legacy alias for tws_port."""
        return getattr(self, "tws_port")

    @property
    def TWS_USER(self) -> str | None:
        """Legacy alias for tws_user."""
        return getattr(self, "tws_user")

    @property
    def TWS_PASSWORD(self) -> Any:  # SecretStr | None
        """Legacy alias for tws_password."""
        return getattr(self, "tws_password")

    @property
    def SERVER_HOST(self) -> str:
        """Legacy alias for server_host."""
        return getattr(self, "server_host")

    @property
    def SERVER_PORT(self) -> int:
        """Legacy alias for server_port."""
        return getattr(self, "server_port")

    @property
    def CORS_ALLOWED_ORIGINS(self) -> list[str]:
        """Legacy alias for cors_allowed_origins."""
        return getattr(self, "cors_allowed_origins")

    @property
    def CORS_ALLOW_CREDENTIALS(self) -> bool:
        """Legacy alias for cors_allow_credentials."""
        return getattr(self, "cors_allow_credentials")

    @property
    def CORS_ALLOW_METHODS(self) -> list[str]:
        """Legacy alias for cors_allow_methods."""
        return getattr(self, "cors_allow_methods")

    @property
    def CORS_ALLOW_HEADERS(self) -> list[str]:
        """Legacy alias for cors_allow_headers."""
        return getattr(self, "cors_allow_headers")

    @property
    def STATIC_CACHE_MAX_AGE(self) -> int:
        """Legacy alias for static_cache_max_age."""
        return getattr(self, "static_cache_max_age")

    @property
    def JINJA2_TEMPLATE_CACHE_SIZE(self) -> int:
        """Legacy alias derived from environment."""
        env = getattr(self, "environment")
        return 400 if env == Environment.PRODUCTION else 0

    @property
    def AGENT_CONFIG_PATH(self) -> Path:
        """Legacy alias computed from base_dir."""
        base_dir = getattr(self, "base_dir")
        return base_dir / "config" / "agents.json"

    @property
    def MAX_CONCURRENT_AGENT_CREATIONS(self) -> int:
        """Legacy constant for compatibility."""
        return 5

    @property
    def TWS_ENGINE_NAME(self) -> str:
        """Legacy constant for compatibility."""
        return "TWS"

    @property
    def TWS_ENGINE_OWNER(self) -> str:
        """Legacy constant for compatibility."""
        return "twsuser"

    @property
    def TWS_REQUEST_TIMEOUT(self) -> float:
        """Legacy alias for tws_request_timeout."""
        return getattr(self, "tws_request_timeout")

    @property
    def AUDITOR_MODEL_NAME(self) -> str:
        """Legacy alias for auditor_model_name."""
        return getattr(self, "auditor_model_name")

    @property
    def AGENT_MODEL_NAME(self) -> str:
        """Legacy alias for agent_model_name."""
        return getattr(self, "agent_model_name")

    @cached_property
    def CACHE_HIERARCHY(self) -> Any:
        """Legacy alias exposing cache hierarchy configuration object."""
        return CacheHierarchyConfig(
            l1_max_size=getattr(self, "cache_hierarchy_l1_max_size"),
            l2_ttl_seconds=getattr(self, "cache_hierarchy_l2_ttl"),
            l2_cleanup_interval=getattr(self, "cache_hierarchy_l2_cleanup_interval"),
            num_shards=getattr(self, "cache_hierarchy_num_shards"),
            max_workers=getattr(self, "cache_hierarchy_max_workers"),
        )

    # Connection pool properties (legacy)
    @property
    def DB_POOL_MIN_SIZE(self) -> int:
        """Legacy alias for db_pool_min_size."""
        return getattr(self, "db_pool_min_size")

    @property
    def DB_POOL_MAX_SIZE(self) -> int:
        """Legacy alias for db_pool_max_size."""
        return getattr(self, "db_pool_max_size")

    @property
    def DB_POOL_IDLE_TIMEOUT(self) -> int:
        """Legacy alias for db_pool_idle_timeout."""
        return getattr(self, "db_pool_idle_timeout")

    @property
    def DB_POOL_CONNECT_TIMEOUT(self) -> int:
        """Legacy alias for db_pool_connect_timeout."""
        return getattr(self, "db_pool_connect_timeout")

    @property
    def DB_POOL_HEALTH_CHECK_INTERVAL(self) -> int:
        """Legacy alias for db_pool_health_check_interval."""
        return getattr(self, "db_pool_health_check_interval")

    @property
    def DB_POOL_MAX_LIFETIME(self) -> int:
        """Legacy alias for db_pool_max_lifetime."""
        return getattr(self, "db_pool_max_lifetime")

    @property
    def REDIS_POOL_MIN_SIZE(self) -> int:
        """Legacy alias for redis_pool_min_size."""
        return getattr(self, "redis_pool_min_size")

    @property
    def REDIS_POOL_MAX_SIZE(self) -> int:
        """Legacy alias for redis_pool_max_size."""
        return getattr(self, "redis_pool_max_size")

    @property
    def REDIS_POOL_IDLE_TIMEOUT(self) -> int:
        """Legacy alias for redis_pool_idle_timeout."""
        return getattr(self, "redis_pool_idle_timeout")

    @property
    def REDIS_POOL_CONNECT_TIMEOUT(self) -> int:
        """Legacy alias for redis_pool_connect_timeout."""
        return getattr(self, "redis_pool_connect_timeout")

    @property
    def REDIS_POOL_HEALTH_CHECK_INTERVAL(self) -> int:
        """Legacy alias for redis_pool_health_check_interval."""
        return getattr(self, "redis_pool_health_check_interval")

    @property
    def REDIS_POOL_MAX_LIFETIME(self) -> int:
        """Legacy alias for redis_pool_max_lifetime."""
        return getattr(self, "redis_pool_max_lifetime")

    @property
    def HTTP_POOL_MIN_SIZE(self) -> int:
        """Legacy alias for http_pool_min_size."""
        return getattr(self, "http_pool_min_size")

    @property
    def HTTP_POOL_MAX_SIZE(self) -> int:
        """Legacy alias for http_pool_max_size."""
        return getattr(self, "http_pool_max_size")

    @property
    def HTTP_POOL_IDLE_TIMEOUT(self) -> int:
        """Legacy alias for http_pool_idle_timeout."""
        return getattr(self, "http_pool_idle_timeout")

    @property
    def HTTP_POOL_CONNECT_TIMEOUT(self) -> int:
        """Legacy alias for http_pool_connect_timeout."""
        return getattr(self, "http_pool_connect_timeout")

    @property
    def HTTP_POOL_HEALTH_CHECK_INTERVAL(self) -> int:
        """Legacy alias for http_pool_health_check_interval."""
        return getattr(self, "http_pool_health_check_interval")

    @property
    def HTTP_POOL_MAX_LIFETIME(self) -> int:
        """Legacy alias for http_pool_max_lifetime."""
        return getattr(self, "http_pool_max_lifetime")

    # pylint: disable=invalid-name
    @property
    def KNOWLEDGE_BASE_DIRS(self) -> list[Path]:
        """Legacy alias for knowledge_base_dirs."""
        return getattr(self, "knowledge_base_dirs")

    @property
    def PROTECTED_DIRECTORIES(self) -> list[Path]:
        """Legacy alias for protected_directories."""
        return getattr(self, "protected_directories")

    # pylint: enable=invalid-name
