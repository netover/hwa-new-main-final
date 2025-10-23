"""
Application settings and configuration management.

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

from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Ambientes suportados."""

    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TEST = "test"


class CacheHierarchyConfig:
    """Configuration object for cache hierarchy settings."""

    def __init__(
        self,
        l1_max_size: int,
        l2_ttl_seconds: int,
        l2_cleanup_interval: int,
        num_shards: int = 8,
        max_workers: int = 4,
        enable_encryption: bool = False,
        key_prefix: str = "cache:",
    ) -> None:

        self.L1_MAX_SIZE = l1_max_size
        self.L2_TTL_SECONDS = l2_ttl_seconds
        self.L2_CLEANUP_INTERVAL = l2_cleanup_interval
        self.NUM_SHARDS = num_shards
        self.MAX_WORKERS = max_workers
        self.CACHE_ENCRYPTION_ENABLED = enable_encryption
        self.CACHE_KEY_PREFIX = key_prefix


class Settings(BaseSettings):
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
        validate_default=True
    )


    # ============================================================================
    # APLICAÇÃO
    # ============================================================================

    environment: Environment = Field(
        default=Environment.DEVELOPMENT, description="Ambiente de execução"
    )


    project_name: str = Field(
        default="Resync", min_length=1, description="Nome do projeto"
    )


    project_version: str = Field(
        default="1.0.0",
        pattern=r"^\d+\.\d+\.\d+$",
        description="Versão do projeto (semver)"
    )


    description: str = Field(
        default="Real-time monitoring dashboard for HCL Workload Automation",
        description="Descrição do projeto"
    )


    base_dir: Path = Field(
        default_factory=Path.cwd, description="Diretório base da aplicação"
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

    neo4j_password: str = Field(
        default="",
        min_length=0,
        description="Senha Neo4j (deve ser fornecida via variável de ambiente)",
        env="NEO4J_PASSWORD",
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
        description="Timeout for distributed Redis initialization lock"
    )

    redis_health_check_interval: int = Field(
        default=5, ge=1, description="Interval for Redis connection health checks"
    )


    # Robust Cache Configuration
    robust_cache_max_items: int = Field(
        default=100_000, ge=100, description="Maximum number of items in robust cache"
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
        description="Endpoint da API LLM (NVIDIA)"
    )


    llm_api_key: str = Field(
        default="",
        min_length=0,
        description="Chave de API do LLM (NVIDIA). Deve ser configurada via variável de ambiente.",
        env="LLM_API_KEY",
    )


    llm_timeout: float = Field(
        default=60.0, gt=0, description="Timeout para chamadas LLM em segundos"
    )


    auditor_model_name: str = Field(default="gpt-3.5-turbo")
    agent_model_name: str = Field(default="gpt-4o")

    # ============================================================================
    # CACHE CONFIGURATION

    # Cache Hierarchy Configuration
    cache_hierarchy_l1_max_size: int = Field(
        default=5000,
        description="Maximum number of entries in L1 cache"
    )

    cache_hierarchy_l2_ttl: int = Field(
        default=600,
        description="Time-To-Live for L2 cache entries in seconds"
    )

    cache_hierarchy_l2_cleanup_interval: int = Field(
        default=60,
        description="Cleanup interval for L2 cache in seconds"
    )

    cache_hierarchy_num_shards: int = Field(
        default=8,
        description="Number of shards for cache"
    )

    cache_hierarchy_max_workers: int = Field(
        default=4,
        description="Max workers for cache operations"
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
        env="TWS_USER",
        description="Usuário do TWS (obrigatório se não estiver em modo mock)"
    )

    tws_password: str | None = Field(
        default=None,
        env="TWS_PASSWORD",
        description="Senha do TWS (obrigatório se não estiver em modo mock)",
        exclude=True  # Não incluir em logs ou serializações
    )

    tws_base_url: str = Field(default="http://localhost:31111")
    tws_request_timeout: float = Field(
        default=30.0, description="Timeout for TWS requests in seconds"
    )

    tws_ca_bundle: str | None = Field(
        default=None, description="CA bundle for TWS TLS verification (ignored if tws_verify=False)"
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


    admin_password: str = Field(
        default="",
        min_length=0,
        description="Senha do administrador. Deve ser configurada via variável de ambiente.",
        env="ADMIN_PASSWORD",
    )


    # CORS
    cors_allowed_origins: list[str] = Field(default=["*"])
    cors_allow_credentials: bool = Field(default=True)
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
    rate_limit_storage_uri: str = Field(default="redis://localhost:6379")
    rate_limit_key_prefix: str = Field(default="resync:ratelimit:")
    rate_limit_sliding_window: bool = Field(default=True)

    # ============================================================================
    # COMPUTED FIELDS
    # ============================================================================

    # File Ingestion Settings
    knowledge_base_dirs: list[Path] = Field(
        default_factory=lambda: [Path.cwd() / "resync/RAG"],
        description="Directories included in the knowledge base"
    )

    protected_directories: list[Path] = Field(
        default_factory=lambda: [Path.cwd() / "resync/RAG/BASE"],
        description="Protected directories that should not be modified"
    )


    # ============================================================================
    # RAG MICROSERVICE CONFIGURATION
    # ============================================================================

    rag_service_url: str = Field(
        default="http://localhost:8003",
        description="URL base do microserviço RAG (ex: http://rag-service:8000)"
    )

    rag_service_timeout: int = Field(
        default=300,
        description="Timeout para requisições ao microserviço RAG (segundos)"
    )

    rag_service_max_retries: int = Field(
        default=3,
        description="Número máximo de tentativas para requisições ao microserviço RAG"
    )

    rag_service_retry_backoff: float = Field(
        default=1.0,
        description="Fator de backoff exponencial para tentativas de requisição ao microserviço RAG"
    )

    # ============================================================================
    # BACKWARD COMPATIBILITY PROPERTIES
    # ============================================================================

    @property
    def RAG_SERVICE_URL(self) -> str:
        """Backward compatibility property for RAG_SERVICE_URL."""
        return self.rag_service_url


    # ============================================================================
    # BACKWARD COMPATIBILITY PROPERTIES
    # ============================================================================

    @property
    def BASE_DIR(self) -> Path:
        """Backward compatibility property for dynaconf-style access."""
        return self.base_dir

    @property
    def PROJECT_NAME(self) -> str:
        """Backward compatibility property for dynaconf-style access."""
        return self.project_name

    @property
    def PROJECT_VERSION(self) -> str:
        """Backward compatibility property for dynaconf-style access."""
        return self.project_version

    @property
    def DESCRIPTION(self) -> str:
        """Backward compatibility property for dynaconf-style access."""
        return self.description

    @property
    def LOG_LEVEL(self) -> str:
        """Backward compatibility property for dynaconf-style access."""
        return self.log_level

    @property
    def ENVIRONMENT(self) -> str:
        """Backward compatibility property for dynaconf-style access."""
        return self.environment.value

    @property
    def DEBUG(self) -> bool:
        """Backward compatibility property for dynaconf-style access."""
        return self.environment == Environment.DEVELOPMENT

    @property
    def NEO4J_URI(self) -> str:
        return self.neo4j_uri

    @property
    def NEO4J_USER(self) -> str | None:
        return self.neo4j_user

    @property
    def NEO4J_PASSWORD(self) -> str | None:
        return self.neo4j_password

    @property
    def REDIS_URL(self) -> str:
        return self.redis_url

    @property
    def LLM_ENDPOINT(self) -> str | None:
        return self.llm_endpoint

    @property
    def LLM_API_KEY(self) -> str | None:
        return self.llm_api_key

    @property
    def LLM_TIMEOUT(self) -> float:
        return self.llm_timeout

    @property
    def ADMIN_USERNAME(self) -> str:
        return self.admin_username

    @property
    def ADMIN_PASSWORD(self) -> str:
        return self.admin_password

    @property
    def TWS_MOCK_MODE(self) -> bool:
        return self.tws_mock_mode

    @property
    def TWS_HOST(self) -> str | None:
        return self.tws_host

    @property
    def TWS_PORT(self) -> int | None:
        return self.tws_port

    @property
    def TWS_USER(self) -> str | None:
        return self.tws_user

    @property
    def TWS_PASSWORD(self) -> str | None:
        return self.tws_password

    @property
    def SERVER_HOST(self) -> str:
        return self.server_host

    @property
    def SERVER_PORT(self) -> int:
        return self.server_port

    @property
    def CORS_ALLOWED_ORIGINS(self) -> list[str]:
        return self.cors_allowed_origins

    @property
    def CORS_ALLOW_CREDENTIALS(self) -> bool:
        return self.cors_allow_credentials

    @property
    def CORS_ALLOW_METHODS(self) -> list[str]:
        return self.cors_allow_methods

    @property
    def CORS_ALLOW_HEADERS(self) -> list[str]:
        return self.cors_allow_headers

    @property
    def STATIC_CACHE_MAX_AGE(self) -> int:
        return self.static_cache_max_age

    @property
    def JINJA2_TEMPLATE_CACHE_SIZE(self) -> int:
        return 400 if self.environment == Environment.PRODUCTION else 0

    @property
    def AGENT_CONFIG_PATH(self) -> Path:
        return self.base_dir / "config" / "agents.json"

    @property
    def MAX_CONCURRENT_AGENT_CREATIONS(self) -> int:
        return 5

    @property
    def TWS_ENGINE_NAME(self) -> str:
        return "TWS"

    @property
    def TWS_ENGINE_OWNER(self) -> str:
        return "twsuser"

    @property
    def TWS_REQUEST_TIMEOUT(self) -> float:
        return self.tws_request_timeout

    @property
    def AUDITOR_MODEL_NAME(self) -> str:
        return self.auditor_model_name

    @property
    def AGENT_MODEL_NAME(self) -> str:
        return self.agent_model_name

    @cached_property
    def CACHE_HIERARCHY(self) -> Any:
        """Cache hierarchy configuration object."""
        return CacheHierarchyConfig(
            l1_max_size=self.cache_hierarchy_l1_max_size,
            l2_ttl_seconds=self.cache_hierarchy_l2_ttl,
            l2_cleanup_interval=self.cache_hierarchy_l2_cleanup_interval,
            num_shards=self.cache_hierarchy_num_shards,
            max_workers=self.cache_hierarchy_max_workers
        )


    # Connection pool properties
    @property
    def DB_POOL_MIN_SIZE(self) -> int:
        """Backward compatibility property for DB_POOL_MIN_SIZE."""
        return self.db_pool_min_size

    @property
    def DB_POOL_MAX_SIZE(self) -> int:
        return self.db_pool_max_size

    @property
    def DB_POOL_IDLE_TIMEOUT(self) -> int:
        return self.db_pool_idle_timeout

    @property
    def DB_POOL_CONNECT_TIMEOUT(self) -> int:
        return self.db_pool_connect_timeout

    @property
    def DB_POOL_HEALTH_CHECK_INTERVAL(self) -> int:
        return self.db_pool_health_check_interval

    @property
    def DB_POOL_MAX_LIFETIME(self) -> int:
        return self.db_pool_max_lifetime

    @property
    def REDIS_POOL_MIN_SIZE(self) -> int:
        return self.redis_pool_min_size

    @property
    def REDIS_POOL_MAX_SIZE(self) -> int:
        return self.redis_pool_max_size

    @property
    def REDIS_POOL_IDLE_TIMEOUT(self) -> int:
        return self.redis_pool_idle_timeout

    @property
    def REDIS_POOL_CONNECT_TIMEOUT(self) -> int:
        return self.redis_pool_connect_timeout

    @property
    def REDIS_POOL_HEALTH_CHECK_INTERVAL(self) -> int:
        return self.redis_pool_health_check_interval

    @property
    def REDIS_POOL_MAX_LIFETIME(self) -> int:
        return self.redis_pool_max_lifetime

    @property
    def HTTP_POOL_MIN_SIZE(self) -> int:
        return self.http_pool_min_size

    @property
    def HTTP_POOL_MAX_SIZE(self) -> int:
        return self.http_pool_max_size

    @property
    def HTTP_POOL_IDLE_TIMEOUT(self) -> int:
        return self.http_pool_idle_timeout

    @property
    def HTTP_POOL_CONNECT_TIMEOUT(self) -> int:
        return self.http_pool_connect_timeout

    @property
    def HTTP_POOL_HEALTH_CHECK_INTERVAL(self) -> int:
        return self.http_pool_health_check_interval

    @property
    def HTTP_POOL_MAX_LIFETIME(self) -> int:
        return self.http_pool_max_lifetime

    # ============================================================================
    # MIGRATION GRADUAL - FEATURE FLAGS
    # ============================================================================

    # Controle de migração para novos componentes
    MIGRATION_USE_NEW_CACHE: bool = Field(
        default=False, description="Usar ImprovedAsyncCache ao invés de AsyncTTLCache"
    )

    MIGRATION_USE_NEW_TWS: bool = Field(
        default=False,
        description="Usar TWSClientFactory ao invés de implementação direta"
    )

    MIGRATION_USE_NEW_RATE_LIMIT: bool = Field(
        default=False,
        description="Usar RateLimiterManager ao invés de implementação básica"
    )

    MIGRATION_ENABLE_METRICS: bool = Field(
        default=True, description="Habilitar métricas de migração e monitoramento"
    )


    # ============================================================================
    # VALIDADORES
    # ============================================================================

    @property
    def KNOWLEDGE_BASE_DIRS(self) -> list[Path]:
        """Backward compatibility property for KNOWLEDGE_BASE_DIRS."""
        return self.knowledge_base_dirs

    @property
    def PROTECTED_DIRECTORIES(self) -> list[Path]:
        """Backward compatibility property for PROTECTED_DIRECTORIES."""
        return self.protected_directories

    @field_validator("base_dir")
    @classmethod
    def validate_base_dir(cls, v: Path) -> Path:
        """Resolve base_dir para path absoluto."""
        return v.resolve()

    @field_validator("db_pool_max_size")
    @classmethod
    def validate_db_pool_sizes(cls, v: int, info: ValidationInfo) -> int:
        """Valida que max_size >= min_size."""
        min_size = info.data.get("db_pool_min_size", 0)
        if v < min_size:
            raise ValueError(
                f"db_pool_max_size ({v}) must be >= db_pool_min_size ({min_size})"
            )

        return v

    @field_validator("redis_pool_max_size")
    @classmethod
    def validate_redis_pool_sizes(cls, v: int, info: ValidationInfo) -> int:
        """Valida que max_size >= min_size."""
        min_size = info.data.get("redis_pool_min_size", 0)
        if v < min_size:
            raise ValueError(
                f"redis_pool_max_size ({v}) must be >= redis_pool_min_size ({min_size})"
            )

        return v

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        """Valida formato da URL Redis."""
        if not v.startswith("redis://"):
            raise ValueError(
                "REDIS_URL deve começar com 'redis://'. "
                "Exemplo: redis://localhost:6379 ou redis://:senha@localhost:6379"
            )

        return v

    @field_validator("admin_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Valida força mínima da senha."""
        # Apenas validação básica para ambiente local
        if len(v) < 8:
            raise ValueError("Senha deve ter no mínimo 8 caracteres")
        return v

    @field_validator("admin_password")
    @classmethod
    def validate_production_password(cls, v: str, info: ValidationInfo) -> str:
        """Valida senha em produção."""
        env = info.data.get("environment")
        if env == Environment.PRODUCTION:
            insecure_passwords = {
                "change_me_please",
                "change_me_immediately",
                "admin",
                "password",
                "12345678",
            }
            if v.lower() in insecure_passwords:
                raise ValueError("Insecure admin password not allowed in production")
        return v

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_production_cors(cls, v: list[str], info: ValidationInfo) -> list[str]:
        """Valida CORS em produção."""
        env = info.data.get("environment")
        if env == Environment.PRODUCTION and "*" in v:
            raise ValueError("Wildcard CORS origins not allowed in production")
        return v

    @field_validator("llm_api_key")
    @classmethod
    def validate_llm_api_key(cls, v: str, info: ValidationInfo) -> str:
        """Valida chave da API em produção."""
        env = info.data.get("environment")
        if env == Environment.PRODUCTION:
            if v == "dummy_key_for_development":
                raise ValueError("LLM_API_KEY must be set to a valid key in production")
        return v

    @field_validator("tws_user", "tws_password")
    @classmethod
    def validate_tws_credentials(
        cls, v: str | None, info: ValidationInfo
    ) -> str | None:
        """Valida credenciais TWS quando não está em mock mode."""
        if info.field_name == "tws_password" and v:
            # Validar força da senha em produção
            env = info.data.get("environment")
            if env == Environment.PRODUCTION:
                if len(v) < 12:
                    raise ValueError(
                        "TWS_PASSWORD must be at least 12 characters in production"
                    )

                # Verificar se não é uma senha padrão
                common_passwords = {"password", "twsuser", "tws_password", "change_me"}
                if v.lower() in common_passwords:
                    raise ValueError("TWS_PASSWORD cannot be a common/default password")
        return v

    def model_post_init(self, __context: Any) -> None:
        """Validações pós-inicialização."""
        # Validar TWS quando não está em mock mode
        if not self.tws_mock_mode:
            required_tws = {
                "tws_host": self.tws_host,
                "tws_port": self.tws_port,
                "tws_user": self.tws_user,
                "tws_password": self.tws_password,
            }
            missing = [k for k, v in required_tws.items() if not v]
            if missing:
                raise ValueError(
                    f"TWS credentials required when not in mock mode: {missing}"
                )


    # SSL/TLS
    # >>> Explicitly disable certificate validation <<<
    TWS_VERIFY: bool | str = False  # Global disable for TWS
    TWS_CA_BUNDLE: str | None = None


# Instância global singleton
settings = Settings()


def get_settings() -> Settings:
    """Factory para obter settings (útil para dependency injection)."""
    return settings


def load_settings() -> Settings:
    """Load application settings.

    This function provides backward compatibility for code that expects
    a load_settings function. It returns the global settings instance.

    Returns:
        Settings: The global settings instance
    """
    return settings


# --- PEP 562 Lazy Imports ---
_LAZY_IMPORTS = {}
_LOADED_IMPORTS = {}

def __getattr__(name):
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
