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
from typing import Any, Literal
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
# Legacy properties were removed as part of cleanup
# SettingsLegacyProperties no longer exists
# Import shared types, validators and legacy properties from separate modules
from resync.settings.settings_types import Environment
from resync.settings.settings_validators import SettingsValidators
class Settings(BaseSettings, SettingsValidators):
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
    # SIMPLE LOGGING CONFIGURATION
    # ============================================================================
    log_file: str = Field(default="resync.log", description="Path to log file")
    log_max_bytes: int = Field(
        default=10 * 1024 * 1024,  # 10MB
        description="Maximum log file size before rotation",
    )
    log_backup_count: int = Field(
        default=3, description="Number of backup log files to keep"
    )
    log_console_output: bool = Field(
        default=True,
        description="Whether to output logs to console"
    )
    service_name: str = Field(
        default="resync", description="Nome do serviço para logs"
    )
    description: str = Field(
        default="Real-time monitoring dashboard for HCL Workload Automation",
        description="Descrição do projeto",
    )
    base_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[1],
        description="Diretório base da aplicação",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = (
        Field(default="INFO", description="Nível de logging")
    )
    # ============================================================================
    # BANCO DE DADOS - NEO4J
    # ============================================================================
    neo4j_uri: str = Field(
        default="neo4j://127.0.0.1:7687", description="URI de conexão Neo4j"
    )
    neo4j_user: str = Field(
        default="neo4j", min_length=1, description="Usuário Neo4j"
    )
    neo4j_password: SecretStr = Field(
        default=SecretStr(""),
        min_length=0,
        description="Senha Neo4j (deve ser fornecida via variável de ambiente)",
        validation_alias="NEO4J_PASSWORD",
        exclude=True,
        repr=False,
    )
    # Connection Pool - Neo4j (Optimized for 20 users: 5-7 concurrent, peaks to 15)
    db_pool_min_size: int = Field(default=2, ge=1, le=10)  # ✅ Reduced from 20
    db_pool_max_size: int = Field(
        default=8, ge=1, le=20
    )  # ? Reduced from 100
    db_pool_recommended_max_size: int = Field(
        default=8,
        ge=1,
        le=20,
        description="Recommended upper bound for the database pool size used in validations",
    )
    db_expected_users: int = Field(
        default=20,
        ge=1,
        description="Expected number of users for validation scenarios",
    )
    db_validation_url: str = Field(
        default="sqlite+aiosqlite:///:memory:",
        description="Database URL used by the validation harness",
    )
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
    # Connection Pool - Redis (Optimized for 20 users: caching operations)
    redis_pool_min_size: int = Field(
        default=2, ge=1, le=15
    )  # ✅ Reduced from 5
    redis_pool_max_size: int = Field(
        default=6, ge=1, le=15
    )  # ? Reduced from 20
    redis_pool_recommended_max_size: int = Field(
        default=6,
        ge=1,
        le=15,
        description="Recommended maximum pool size for Redis validations",
    )
    redis_pool_idle_timeout: int = Field(default=300, ge=60)
    redis_pool_connect_timeout: int = Field(default=30, ge=5)
    redis_pool_health_check_interval: int = Field(default=60, ge=10)
    redis_pool_max_lifetime: int = Field(default=1800, ge=300)
    redis_host: str = Field(
        default="localhost",
        description="Redis host for validation workflows",
    )
    redis_port: int = Field(
        default=6379,
        ge=1,
        le=65535,
        description="Redis port for validation workflows",
    )
    redis_password: str | None = Field(
        default=None,
        description="Redis password used during validation",
    )
    redis_db: int = Field(
        default=0,
        ge=0,
        description="Redis database index used during validation",
    )
    redis_socket_timeout: float = Field(
        default=5.0,
        gt=0,
        description="Socket timeout (seconds) for Redis validation",
    )
    redis_socket_connect_timeout: float = Field(
        default=5.0,
        gt=0,
        description="Connect timeout (seconds) for Redis validation",
    )
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
        default=5,
        ge=1,
        description="Interval for Redis connection health checks",
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
        default=SecretStr(""),
        min_length=0,
        description=(
            "Chave de API do LLM (NVIDIA). Deve ser configurada via variável de ambiente."
        ),
        validation_alias="LLM_API_KEY",
        exclude=True,
        repr=False,
    )
    llm_timeout: float = Field(
        default=60.0,
        gt=0,
        description="Timeout para chamadas LLM em segundos",
        alias="LLM_TIMEOUT",
    )
    @property
    def LLM_TIMEOUT(self) -> float:
        return self.llm_timeout
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
        default=True,
        description="Enable cache mutex to prevent duplicate computations",
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
    # Connection Pool - HTTP (Optimized for 20 users: TWS API calls)
    http_pool_min_size: int = Field(default=3, ge=1)  # ✅ Reduced from 10
    http_pool_max_size: int = Field(default=12, ge=1)  # ? Reduced from 100
    http_pool_recommended_max_size: int = Field(
        default=12,
        ge=1,
        description="Recommended upper bound for HTTP connection pools during validation",
    )
    http_pool_idle_timeout: int = Field(default=300, ge=60)
    http_pool_connect_timeout: int = Field(default=10, ge=1)
    http_pool_health_check_interval: int = Field(default=60, ge=10)
    http_pool_max_lifetime: int = Field(default=1800, ge=300)
    http_pool_validation_endpoint: str | None = Field(
        default=None,
        description="Optional HTTP endpoint targeted by validation checks",
    )
    http_validation_request_count: int = Field(
        default=3,
        ge=1,
        le=50,
        description="Number of requests issued during HTTP validation",
    )
    # ============================================================================
    # SEGURANÇA
    # ============================================================================
    admin_username: str = Field(
        default="admin",
        min_length=3,
        description="Nome de usuário do administrador",
    )
    admin_password: SecretStr | None = Field(
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
        default="127.0.0.1",
        description="Host do servidor (padrão: localhost apenas)",
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
    @property
    def RAG_SERVICE_URL(self) -> str:
        return self.rag_service_url
    @property
    def RAG_SERVICE_TIMEOUT(self) -> int:
        return self.rag_service_timeout
    @property
    def RAG_SERVICE_MAX_RETRIES(self) -> int:
        return self.rag_service_max_retries
    @property
    def RAG_SERVICE_RETRY_BACKOFF(self) -> float:
        return self.rag_service_retry_backoff
    # ============================================================================
    # BACKWARD COMPATIBILITY PROPERTIES
    # ============================================================================
    # Legacy properties are now imported from settings_legacy.py
    # End of legacy block
    # ============================================================================
    # MIGRATION GRADUAL - FEATURE FLAGS
    # ============================================================================
    # Controle de migração para novos componentes
    MIGRATION_USE_NEW_CACHE: bool = Field(
        default=False,
        description="Usar ImprovedAsyncCache ao invés de AsyncTTLCache",
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
        default=True,
        description="Habilitar métricas de migração e monitoramento",
    )
    # ============================================================================
    # HEALTH CHECK CONFIGURATION
    # ============================================================================
    health_check_interval_seconds: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Intervalo em segundos para verificações de saúde (padrão: 300s/5min)",
    )
    # Flags para desativar componentes pesados de health check
    health_enable_proactive: bool = Field(
        default=False,
        description="Habilitar monitoramento proativo de saúde (recurso intensivo)",
    )
    health_enable_predictive: bool = Field(
        default=False,
        description="Habilitar análise preditiva de saúde (recurso intensivo)",
    )
    # ============================================================================
    # DYNAMIC CONNECTION POOL SCALING
    # ============================================================================
    # Smart Pooling Configuration - Dynamic scaling limits for AutoScalingManager
    # Database Pool - Dynamic scaling for batch processing peaks
    db_pool_max_dynamic: int = Field(
        default=15,
        ge=8,
        le=25,
        description="Maximum connections for dynamic scaling (batch processing)",
    )
    # Redis Pool - Dynamic scaling for high cache load
    redis_pool_max_dynamic: int = Field(
        default=15,
        ge=6,
        le=30,
        description="Maximum connections for dynamic Redis scaling",
    )
    # HTTP Pool - Dynamic scaling for API burst loads
    http_pool_max_dynamic: int = Field(
        default=25,
        ge=12,
        le=50,
        description="Maximum connections for dynamic HTTP scaling",
    )
    # Auto-scaling thresholds and timing
    pool_scale_up_threshold: float = Field(
        default=0.7,
        ge=0.5,
        le=0.9,
        description="Utilization threshold to trigger scale up (70%)",
    )
    pool_scale_down_threshold: float = Field(
        default=0.3,
        ge=0.1,
        le=0.5,
        description="Utilization threshold to trigger scale down (30%)",
    )
    pool_scale_up_cooldown: int = Field(
        default=300,
        ge=60,
        le=1800,
        description="Cooldown period before scaling up again (seconds)",
    )
    pool_scale_down_cooldown: int = Field(
        default=600,
        ge=120,
        le=3600,
        description="Cooldown period before scaling down again (seconds)",
    )
    # Predictive scaling
    enable_predictive_scaling: bool = Field(
        default=True, description="Enable predictive scaling based on trends"
    )
    scaling_prediction_window: int = Field(
        default=5,
        ge=1,
        le=15,
        description="Time window for scaling predictions (minutes)",
    )
    # Gradual scaling configuration
    gradual_scaling_enabled: bool = Field(
        default=True,
        description="Enable gradual scaling instead of abrupt changes",
    )
    scaling_step_size: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Number of connections to add/remove per scaling step",
    )
    # Circuit breaker integration
    pool_circuit_breaker_enabled: bool = Field(
        default=True, description="Enable circuit breaker protection for pools"
    )
    pool_circuit_breaker_error_threshold: float = Field(
        default=0.2,
        ge=0.05,
        le=0.5,
        description="Error rate threshold to trigger circuit breaker (20%)",
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
