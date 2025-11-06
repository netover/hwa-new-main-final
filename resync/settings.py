"""Application settings and configuration management.

This module defines all application settings using Pydantic BaseSettings,
providing centralized configuration management with environment variable
support, validation, and type safety.

Settings are organized into logical groups:
- Database and Redis configuration
- TWS integration settings
- Security and authentication
- Logging and monitoring
- AI/ML model configurations
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Import shared types, validators and legacy properties from separate modules
from .settings_types import Environment, SettingsLegacyProperties
from .settings_validators import SettingsValidators


class Settings(BaseSettings, SettingsValidators, SettingsLegacyProperties):
    """
    Configurações da aplicação com validação type-safe.

    Todas as configurações podem ser sobrescritas via variáveis de ambiente
    com o prefixo APP_ (ex: APP_ENVIRONMENT=production).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow",
        env_prefix="APP_",
        # Desligar validação global para evitar problemas com defaults
        validate_default=False,
    )

    # ============================================================================
    # APLICAÇÃO
    # ============================================================================
    environment: Environment = Field(
        default=Environment.DEVELOPMENT, description="Ambiente de execução"
    )

    project_name: str = Field(
        default="Resync",
        min_length=1,
        description="Nome do projeto",
    )

    project_version: str = Field(
        default="1.0.0",
        pattern=(
            r"^\d+\.\d+\.\d+(?:-(?:(?:0|[1-9]\d*|[a-zA-Z-][0-9a-zA-Z-]*)"
            r"(?:\.(?:0|[1-9]\d*|[a-zA-Z-][0-9a-zA-Z-]*))*))?"
            r"(?:\+(?:[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
        ),
        description="Versão do projeto (semver com pre-release e build metadata)",
    )

    # ============================================================================
    # LOGGING CONFIGURATION
    # ============================================================================
    log_format: Literal["text", "json"] = Field(
        default="json", description="Formato dos logs: text ou json"
    )

    service_name: str = Field(default="resync", description="Nome do serviço para logs")

    log_sensitive_data_redaction: bool = Field(
        default=True,
        description=(
            "Enable redaction of sensitive data in logs (passwords, tokens, etc.)"
        ),
    )

    description: str = Field(
        default="Real-time monitoring dashboard for HCL Workload Automation",
        description="Descrição do projeto",
    )

    base_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[1],
        description="Diretório base da aplicação",
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Nível de logging"
    )

    # ============================================================================
    # BANCO DE DADOS - NEO4J
    # ============================================================================
    neo4j_uri: str = Field(
        default="neo4j://127.0.0.1:7687", description="URI de conexão Neo4j"
    )

    neo4j_user: str = Field(default="neo4j", min_length=1, description="Usuário Neo4j")

    neo4j_password: SecretStr = Field(
        default=SecretStr(""),
        min_length=0,
        description="Senha Neo4j (deve ser fornecida via variável de ambiente)",
        validation_alias="NEO4J_PASSWORD",
        exclude=True,
        repr=False,
    )

    # Connection Pool - Neo4j
    db_pool_min_size: int = Field(default=20, ge=1, le=100)
    db_pool_max_size: int = Field(default=100, ge=1, le=1000)
    db_pool_idle_timeout: int = Field(default=1200, ge=60)
    db_pool_connect_timeout: int = Field(default=60, ge=5)
    db_pool_health_check_interval: int = Field(default=60, ge=10)
    db_pool_max_lifetime: int = Field(default=1800, ge=300)

    # ============================================================================
    # REDIS
    # ============================================================================
    redis_url: str = Field(
        default="redis://localhost:6379/0", description="URL de conexão Redis"
    )

    redis_min_connections: int = Field(default=1, ge=1, le=100)
    redis_max_connections: int = Field(default=10, ge=1, le=1000)
    redis_timeout: float = Field(default=30.0, gt=0)

    # Connection Pool - Redis
    redis_pool_min_size: int = Field(default=5, ge=1, le=100)
    redis_pool_max_size: int = Field(default=20, ge=1, le=1000)
    redis_pool_idle_timeout: int = Field(default=300, ge=60)
    redis_pool_connect_timeout: int = Field(default=30, ge=5)
    redis_pool_health_check_interval: int = Field(default=60, ge=10)
    redis_pool_max_lifetime: int = Field(default=1800, ge=300)

    # Redis Initialization
    redis_max_startup_retries: int = Field(default=3, ge=1, le=10)
    redis_startup_backoff_base: float = Field(default=0.1, gt=0)
    redis_startup_backoff_max: float = Field(default=10.0, gt=0)
    redis_startup_lock_timeout: int = Field(
        default=30,
        ge=5,
        description="Timeout for distributed Redis initialization lock",
    )

    redis_health_check_interval: int = Field(
        default=5, ge=1, description="Interval for Redis connection health checks"
    )

    # Robust Cache Configuration
    robust_cache_max_items: int = Field(
        default=100_000,
        ge=100,
        description="Maximum number of items in robust cache",
    )
    robust_cache_max_memory_mb: int = Field(
        default=100, ge=10, description="Maximum memory usage for robust cache"
    )
    robust_cache_eviction_batch_size: int = Field(
        default=100, ge=1, description="Number of items to evict in one batch"
    )
    robust_cache_enable_weak_refs: bool = Field(
        default=True, description="Enable weak references for large objects"
    )
    robust_cache_enable_wal: bool = Field(
        default=False, description="Enable Write-Ahead Logging for cache"
    )
    robust_cache_wal_path: str | None = Field(
        default=None, description="Path for cache Write-Ahead Log"
    )

    # ============================================================================
    # LLM
    # ============================================================================
    llm_endpoint: str = Field(
        default="https://integrate.api.nvidia.com/v1",
        description="Endpoint da API LLM (NVIDIA)",
    )

    llm_api_key: SecretStr = Field(
        default="",
        min_length=0,
        description=(
            "Chave de API do LLM (NVIDIA). Deve ser configurada via variável de ambiente."
        ),
        validation_alias="LLM_API_KEY",
        exclude=True,
        repr=False,
    )

    llm_timeout: float = Field(
        default=60.0, gt=0, description="Timeout para chamadas LLM em segundos"
    )

    auditor_model_name: str = Field(default="gpt-3.5-turbo")
    agent_model_name: str = Field(default="gpt-4o")

    # ============================================================================
    # CACHE CONFIGURATION
    # ============================================================================
    # Cache Hierarchy Configuration
    cache_hierarchy_l1_max_size: int = Field(
        default=5000, description="Maximum number of entries in L1 cache"
    )
    cache_hierarchy_l2_ttl: int = Field(
        default=600, description="Time-To-Live for L2 cache entries in seconds"
    )
    # Cache Configuration
    enable_cache_swr: bool = Field(
        default=True, description="Enable cache stampede write protection"
    )
    cache_ttl_jitter_ratio: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Ratio of TTL to use as jitter to prevent thundering herd",
    )
    enable_cache_mutex: bool = Field(
        default=True, description="Enable cache mutex to prevent duplicate computations"
    )
    cache_hierarchy_l2_cleanup_interval: int = Field(
        default=60, description="Cleanup interval for L2 cache in seconds"
    )
    cache_hierarchy_num_shards: int = Field(
        default=8, description="Number of shards for cache"
    )
    cache_hierarchy_max_workers: int = Field(
        default=4, description="Max workers for cache operations"
    )

    # ============================================================================
    # TWS (Workload Automation)
    # ============================================================================
    tws_mock_mode: bool = Field(
        default=True, description="Usar modo mock para TWS (desenvolvimento)"
    )

    tws_host: str | None = Field(default=None)
    tws_port: int | None = Field(default=None, ge=1, le=65535)
    tws_user: str | None = Field(
        default=None,
        validation_alias="TWS_USER",
        description="Usuário do TWS (obrigatório se não estiver em modo mock)",
    )
    tws_password: SecretStr | None = Field(
        default=None,
        validation_alias="TWS_PASSWORD",
        description="Senha do TWS (obrigatório se não estiver em modo mock)",
        exclude=True,
        repr=False,
    )
    tws_base_url: str = Field(default="http://localhost:31111")
    tws_request_timeout: float = Field(
        default=30.0, description="Timeout for TWS requests in seconds"
    )
    tws_verify: bool | str = Field(
        default=False,
        description=(
            "TWS SSL verification (False/True/path to CA bundle). "
            "Warning: False disables security"
        ),
    )
    tws_ca_bundle: str | None = Field(
        default=None,
        description=(
            "CA bundle for TWS TLS verification (ignored if tws_verify=False)"
        ),
    )

    # Connection Pool - HTTP
    http_pool_min_size: int = Field(default=10, ge=1)
    http_pool_max_size: int = Field(default=100, ge=1)
    http_pool_idle_timeout: int = Field(default=300, ge=60)
    http_pool_connect_timeout: int = Field(default=10, ge=1)
    http_pool_health_check_interval: int = Field(default=60, ge=10)
    http_pool_max_lifetime: int = Field(default=1800, ge=300)

    # ============================================================================
    # SEGURANÇA
    # ============================================================================
    admin_username: str = Field(
        default="admin", min_length=3, description="Nome de usuário do administrador"
    )
    admin_password: Optional[SecretStr] = Field(
        default=None,
        # Reads from ADMIN_PASSWORD (without APP_ prefix)
        validation_alias="ADMIN_PASSWORD",
        description=(
            "Senha do administrador. Deve ser configurada via variável de ambiente."
        ),
        exclude=True,
        repr=False,
    )

    # CORS
    cors_allowed_origins: list[str] = Field(default=["http://localhost:3000"])
    cors_allow_credentials: bool = Field(default=False)
    cors_allow_methods: list[str] = Field(default=["*"])
    cors_allow_headers: list[str] = Field(default=["*"])

    # Static Files
    static_cache_max_age: int = Field(default=3600, ge=0)

    # ============================================================================
    # SERVIDOR
    # ============================================================================
    server_host: str = Field(
        default="127.0.0.1", description="Host do servidor (padrão: localhost apenas)"
    )
    server_port: int = Field(
        default=8000, ge=1024, le=65535, description="Porta do servidor"
    )

    # ============================================================================
    # RATE LIMITING
    # ============================================================================
    rate_limit_public_per_minute: int = Field(default=100, ge=1)
    rate_limit_authenticated_per_minute: int = Field(default=1000, ge=1)
    rate_limit_critical_per_minute: int = Field(default=50, ge=1)
    rate_limit_error_handler_per_minute: int = Field(default=15, ge=1)
    rate_limit_websocket_per_minute: int = Field(default=30, ge=1)
    rate_limit_dashboard_per_minute: int = Field(default=10, ge=1)
    rate_limit_storage_uri: str = Field(default="redis://localhost:6379/1")
    rate_limit_key_prefix: str = Field(default="resync:ratelimit:")
    rate_limit_sliding_window: bool = Field(default=True)

    # ============================================================================
    # COMPUTED FIELDS
    # ============================================================================
    # File Ingestion Settings
    knowledge_base_dirs: list[Path] = Field(
        default_factory=lambda: [Path.cwd() / "resync/RAG"],
        description="Directories included in the knowledge base",
    )
    protected_directories: list[Path] = Field(
        default_factory=lambda: [Path.cwd() / "resync/RAG/BASE"],
        description="Protected directories that should not be modified",
    )

    # ============================================================================
    # RAG MICROSERVICE CONFIGURATION
    # ============================================================================
    rag_service_url: str = Field(
        default="http://localhost:8003",
        description="URL base do microserviço RAG (ex: http://rag-service:8000)",
    )
    rag_service_timeout: int = Field(
        default=300,
        description="Timeout para requisições ao microserviço RAG (segundos)",
    )
    rag_service_max_retries: int = Field(
        default=3,
        description="Número máximo de tentativas para requisições ao microserviço RAG",
    )
    rag_service_retry_backoff: float = Field(
        default=1.0,
        description=(
            "Fator de backoff exponencial para tentativas de requisição ao "
            "microserviço RAG"
        ),
    )

    # ============================================================================
    # BACKWARD COMPATIBILITY PROPERTIES
    # ============================================================================
    # Legacy properties are inherited from SettingsLegacyProperties in settings_types.py

    # End of legacy block

    # ============================================================================
    # MIGRATION GRADUAL - FEATURE FLAGS
    # ============================================================================
    # Controle de migração para novos componentes
    MIGRATION_USE_NEW_CACHE: bool = Field(
        default=False, description="Usar ImprovedAsyncCache ao invés de AsyncTTLCache"
    )
    MIGRATION_USE_NEW_TWS: bool = Field(
        default=False,
        description="Usar TWSClientFactory ao invés de implementação direta",
    )
    MIGRATION_USE_NEW_RATE_LIMIT: bool = Field(
        default=False,
        description="Usar RateLimiterManager ao invés de implementação básica",
    )
    MIGRATION_ENABLE_METRICS: bool = Field(
        default=True, description="Habilitar métricas de migração e monitoramento"
    )

    # ============================================================================
    # VALIDADORES
    # ============================================================================
    # Validators are now imported from settings_validators.py

    # SSL/TLS (compat-shims; não usados diretamente por Pydantic)
    # >>> Explicitly disable certificate validation <<<
    TWS_VERIFY: bool | str = False  # Global disable for TWS
    TWS_CA_BUNDLE: str | None = None

    def __repr__(self) -> str:
        """Representation that excludes sensitive fields from the output."""
        fields: dict[str, Any] = {}
        for name, field_info in self.__class__.model_fields.items():
            if field_info.exclude:
                continue
            fields[name] = getattr(self, name, None)

        parts = [f"{name}={value!r}" for name, value in fields.items()]
        return f"{self.__class__.__name__}({', '.join(parts)})"


# -----------------------------------------------------------------------------
# Instância global (lazy) + helpers
# -----------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Factory para obter settings (útil para dependency injection)."""
    return Settings()


def clear_settings_cache() -> None:
    """Clear the cached settings instance (useful for testing)."""
    get_settings.cache_clear()


class _SettingsProxy:
    """Proxy de conveniência para manter compatibilidade."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_settings(), name)


settings = _SettingsProxy()


# -----------------------------------------------------------------------------
# Backward helper retained
# -----------------------------------------------------------------------------
def load_settings() -> Settings:
    """Load application settings (backward-compat shim)."""
    return settings  # type: ignore[return-value]


# -----------------------------------------------------------------------------
# PEP 562 Lazy Imports (kept if other modules expect them from this namespace)
# -----------------------------------------------------------------------------
_LAZY_IMPORTS: dict[str, tuple[str, str]] = {}
_LOADED_IMPORTS: dict[str, Any] = {}


def __getattr__(name: str) -> Any:
    """PEP 562 __getattr__ for lazy imports to avoid circular dependencies."""
    if name in _LAZY_IMPORTS:
        if name not in _LOADED_IMPORTS:
            try:
                module_name, attr = _LAZY_IMPORTS[name]
                module = __import__(module_name, fromlist=[attr])
                _LOADED_IMPORTS[name] = getattr(module, attr)
            except ImportError:
                _LOADED_IMPORTS[name] = None
        return _LOADED_IMPORTS[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
