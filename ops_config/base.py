from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel as AgnoSettings
from pydantic import ConfigDict, Field

# --- Environment Setup ---
# Load environment variables from .env file if it exists
# This is crucial for local development and testing
env_path = Path(".") / ".env"
if env_path.is_file():
    load_dotenv(dotenv_path=env_path)

# --- Type Definitions ---
# Define a union type for flexibility in specifying model endpoints
ModelEndpoint = str  # For now, just a string, can be a Union of Literals later


# --- Core Application Settings ---
class Settings(AgnoSettings):
    """
    Primary settings class for the Resync application.
    Inherits from Agno's base settings and adds application-specific configurations.
    """

    # --- Project Metadata ---
    PROJECT_NAME: str = "Resync"
    PROJECT_VERSION: str = "1.0.0"
    DESCRIPTION: str = "Real-time monitoring dashboard for HCL Workload Automation"
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    # --- Agent and Model Configuration ---
    # Path to the agent configuration file
    AGENT_CONFIG_PATH: Path = BASE_DIR / "ops_config" / "agents.json"

    # Configuration for the Language Model (LLM)
    # Using Field for default values and clear documentation
    LLM_MODEL_PATH: str = Field(
        default=os.environ.get(
            "LLM_MODEL_PATH", "models/Meta-Llama-3-8B-Instruct.Q4_K_M.gguf"
        ),
        description="Path to the GGUF model file for the LLM.",
    )
    LLM_ENDPOINT: ModelEndpoint = Field(
        default=os.environ.get("LLM_ENDPOINT", "http://localhost:8001/v1"),
        description="Endpoint for the LLM API.",
    )
    LLM_API_KEY: str = Field(
        default=os.environ.get("LLM_API_KEY", ""),
        description=(
            "API key for the LLM service. Must be provided via environment "
            "variable LLM_API_KEY; no hard‑coded default is stored in the repo for "
            "security reasons."
        ),
    )
    AUDITOR_MODEL_NAME: str = Field(
        default=os.environ.get("AUDITOR_MODEL_NAME", "gpt-4o-mini"),
        description="Model to be used by the IA Auditor.",
    )
    LLM_N_GPU_LAYERS: int = Field(
        default=int(os.environ.get("LLM_N_GPU_LAYERS", -1)),
        description="Number of GPU layers to offload (-1 for all).",
    )

    # --- Knowledge Graph (Mem0) Configuration ---
    MEM0_EMBEDDING_PROVIDER: str = Field(
        default=os.environ.get("MEM0_EMBEDDING_PROVIDER", "openai")
    )
    MEM0_EMBEDDING_MODEL: str = Field(
        default=os.environ.get("MEM0_EMBEDDING_MODEL", "text-embedding-3-small")
    )
    MEM0_LLM_PROVIDER: str = Field(
        default=os.environ.get("MEM0_LLM_PROVIDER", "openai")
    )
    MEM0_LLM_MODEL: str = Field(default=os.environ.get("MEM0_LLM_MODEL", "gpt-4o-mini"))
    MEM0_STORAGE_PROVIDER: str = Field(
        default=os.environ.get("MEM0_STORAGE_PROVIDER", "qdrant")
    )
    MEM0_STORAGE_HOST: str = Field(
        default=os.environ.get("MEM0_STORAGE_HOST", "localhost")
    )
    MEM0_STORAGE_PORT: int = Field(
        default=int(os.environ.get("MEM0_STORAGE_PORT", 6333))
    )
    # --- Redis Configuration (for Audit Queue) ---
    REDIS_URL: str = Field(
        default=os.environ.get("REDIS_URL", "redis://localhost:6379"),
        description="Redis connection URL for audit queue and caching.",
    )
    USE_REDIS_AUDIT_STREAMS: bool = Field(
        default=os.environ.get("USE_REDIS_AUDIT_STREAMS", "false").lower() == "true",
        description="Enable Redis Streams for audit queue instead of SQLite.",
    )

    # --- TWS Environment Configuration ---
    TWS_MOCK_MODE: bool = Field(
        default=bool(os.environ.get("TWS_MOCK_MODE", False)),
        description="Enable mock mode for TWS client to use local data instead of a live connection.",
    )
    TWS_CACHE_TTL: int = Field(
        default=int(os.environ.get("TWS_CACHE_TTL", 60)),  # Default to 60 seconds
        description="Time-To-Live (TTL) for TWS API responses in cache (in seconds).",
    )

    # --- Cache Hierarchy Configuration ---
    CACHE_HIERARCHY_L1_MAX_SIZE: int = Field(
        default=int(
            os.environ.get("CACHE_HIERARCHY_L1_MAX_SIZE", 5000)
        ),  # 5K for 4M jobs/month
        description="Maximum number of entries in L1 cache before LRU eviction.",
    )
    CACHE_HIERARCHY_L2_TTL: int = Field(
        default=int(
            os.environ.get("CACHE_HIERARCHY_L2_TTL", 600)
        ),  # 10 min for 4M jobs/month
        description="Time-To-Live (TTL) for L2 cache entries in seconds.",
    )
    CACHE_HIERARCHY_L2_CLEANUP_INTERVAL: int = Field(
        default=int(
            os.environ.get("CACHE_HIERARCHY_L2_CLEANUP_INTERVAL", 60)
        ),  # 1 min for production
        description="Cleanup interval for L2 cache in seconds.",
    )

    # Production-specific settings for 4M jobs/month environment
    CACHE_HIERARCHY_NUM_SHARDS: int = Field(
        default=int(os.environ.get("CACHE_HIERARCHY_NUM_SHARDS", 8)),
        description="Number of shards for production cache (8 for 15 users).",
    )
    CACHE_HIERARCHY_MAX_WORKERS: int = Field(
        default=int(os.environ.get("CACHE_HIERARCHY_MAX_WORKERS", 4)),
        description="Max workers for production cache (4 for 15 users).",
    )
    ASYNC_CACHE_CONCURRENCY_THRESHOLD: int = Field(
        default=int(os.environ.get("ASYNC_CACHE_CONCURRENCY_THRESHOLD", 5)),
        description="Concurrency threshold for adaptive sharding.",
    )

    # --- Async Cache Configuration ---
    ASYNC_CACHE_TTL: int = Field(
        default=int(os.environ.get("ASYNC_CACHE_TTL", 60)),
        description="Default TTL for async cache entries in seconds.",
    )
    ASYNC_CACHE_CLEANUP_INTERVAL: int = Field(
        default=int(os.environ.get("ASYNC_CACHE_CLEANUP_INTERVAL", 30)),
        description="Cleanup interval for async cache in seconds.",
    )
    ASYNC_CACHE_NUM_SHARDS: int = Field(
        default=int(os.environ.get("ASYNC_CACHE_NUM_SHARDS", 8)),
        description="Number of shards for async cache.",
    )
    ASYNC_CACHE_MAX_WORKERS: int = Field(
        default=int(os.environ.get("ASYNC_CACHE_MAX_WORKERS", 4)),
        description="Max workers for async cache operations.",
    )

    # --- KeyLock Configuration ---
    KEY_LOCK_MAX_LOCKS: int = Field(
        default=int(os.environ.get("KEY_LOCK_MAX_LOCKS", 2048)),
        description="Maximum number of locks to maintain in KeyLock manager.",
    )
    # These settings are critical for connecting to the HCL Workload Automation server
    # They MUST be provided in the .env file for security
    TWS_HOST: str = Field(
        default="", description="Hostname or IP address of the TWS server."
    )
    TWS_PORT: int = Field(
        default=31111, description="Port number for the TWS server connection."
    )
    TWS_USER: str = Field(default="", description="Username for TWS authentication.")
    TWS_PASSWORD: str = Field(
        default="", description="Password for TWS authentication."
    )
    TWS_ENGINE_NAME: str = Field(
        default="tws-engine",
        description="Name of the TWS engine to connect to.",
    )
    TWS_ENGINE_OWNER: str = Field(
        default="tws-owner", description="Owner of the TWS engine."
    )

    # --- Connection Pool Configuration ---
    # Database Connection Pool Settings
    DB_POOL_MIN_SIZE: int = Field(
        default=int(os.environ.get("DB_POOL_MIN_SIZE", 5)),
        description="Minimum number of database connections in the pool.",
    )
    DB_POOL_MAX_SIZE: int = Field(
        default=int(os.environ.get("DB_POOL_MAX_SIZE", 20)),
        description="Maximum number of database connections in the pool.",
    )
    DB_POOL_TIMEOUT: int = Field(
        default=int(os.environ.get("DB_POOL_TIMEOUT", 30)),
        description="Timeout in seconds for acquiring a database connection from the pool.",
    )
    DB_POOL_RETRY_ATTEMPTS: int = Field(
        default=int(os.environ.get("DB_POOL_RETRY_ATTEMPTS", 3)),
        description="Number of retry attempts for database connection acquisition.",
    )
    DB_POOL_RETRY_DELAY: int = Field(
        default=int(os.environ.get("DB_POOL_RETRY_DELAY", 1)),
        description="Delay in seconds between database connection retry attempts.",
    )
    DB_POOL_HEALTH_CHECK_INTERVAL: int = Field(
        default=int(os.environ.get("DB_POOL_HEALTH_CHECK_INTERVAL", 60)),
        description="Interval in seconds for database connection health checks.",
    )
    DB_POOL_IDLE_TIMEOUT: int = Field(
        default=int(os.environ.get("DB_POOL_IDLE_TIMEOUT", 300)),
        description="Timeout in seconds before idle database connections are closed.",
    )

    # Redis Connection Pool Settings
    REDIS_POOL_MIN_SIZE: int = Field(
        default=int(os.environ.get("REDIS_POOL_MIN_SIZE", 5)),
        description="Minimum number of Redis connections in the pool.",
    )
    REDIS_POOL_MAX_SIZE: int = Field(
        default=int(os.environ.get("REDIS_POOL_MAX_SIZE", 20)),
        description="Maximum number of Redis connections in the pool.",
    )
    REDIS_POOL_TIMEOUT: int = Field(
        default=int(os.environ.get("REDIS_POOL_TIMEOUT", 30)),
        description="Timeout in seconds for acquiring a Redis connection from the pool.",
    )
    REDIS_POOL_RETRY_ATTEMPTS: int = Field(
        default=int(os.environ.get("REDIS_POOL_RETRY_ATTEMPTS", 3)),
        description="Number of retry attempts for Redis connection acquisition.",
    )
    REDIS_POOL_RETRY_DELAY: int = Field(
        default=int(os.environ.get("REDIS_POOL_RETRY_DELAY", 1)),
        description="Delay in seconds between Redis connection retry attempts.",
    )
    REDIS_POOL_HEALTH_CHECK_INTERVAL: int = Field(
        default=int(os.environ.get("REDIS_POOL_HEALTH_CHECK_INTERVAL", 60)),
        description="Interval in seconds for Redis connection health checks.",
    )
    REDIS_POOL_IDLE_TIMEOUT: int = Field(
        default=int(os.environ.get("REDIS_POOL_IDLE_TIMEOUT", 300)),
        description="Timeout in seconds before idle Redis connections are closed.",
    )

    # HTTP/TWS Connection Pool Settings
    TWS_CONNECT_TIMEOUT: int = Field(
        default=int(os.environ.get("TWS_CONNECT_TIMEOUT", 10)),
        description="Timeout in seconds for establishing TWS connections.",
    )
    TWS_READ_TIMEOUT: int = Field(
        default=int(os.environ.get("TWS_READ_TIMEOUT", 30)),
        description="Timeout in seconds for reading TWS responses.",
    )
    TWS_WRITE_TIMEOUT: int = Field(
        default=int(os.environ.get("TWS_WRITE_TIMEOUT", 30)),
        description="Timeout in seconds for writing TWS requests.",
    )
    TWS_POOL_TIMEOUT: int = Field(
        default=int(os.environ.get("TWS_POOL_TIMEOUT", 30)),
        description="Timeout in seconds for acquiring TWS connections from the pool.",
    )
    TWS_MAX_CONNECTIONS: int = Field(
        default=int(os.environ.get("TWS_MAX_CONNECTIONS", 100)),
        description="Maximum number of TWS connections in the pool.",
    )
    TWS_MAX_KEEPALIVE: int = Field(
        default=int(os.environ.get("TWS_MAX_KEEPALIVE", 20)),
        description="Maximum number of keep-alive TWS connections.",
    )
    TWS_POOL_RETRY_ATTEMPTS: int = Field(
        default=int(os.environ.get("TWS_POOL_RETRY_ATTEMPTS", 3)),
        description="Number of retry attempts for TWS connection acquisition.",
    )
    TWS_POOL_RETRY_DELAY: int = Field(
        default=int(os.environ.get("TWS_POOL_RETRY_DELAY", 1)),
        description="Delay in seconds between TWS connection retry attempts.",
    )

    # WebSocket Connection Pool Settings
    WS_POOL_MAX_SIZE: int = Field(
        default=int(os.environ.get("WS_POOL_MAX_SIZE", 1000)),
        description="Maximum number of WebSocket connections.",
    )
    WS_POOL_CLEANUP_INTERVAL: int = Field(
        default=int(os.environ.get("WS_POOL_CLEANUP_INTERVAL", 60)),
        description="Interval in seconds for WebSocket connection cleanup.",
    )
    WS_CONNECTION_TIMEOUT: int = Field(
        default=int(os.environ.get("WS_CONNECTION_TIMEOUT", 30)),
        description="Timeout in seconds for WebSocket connections.",
    )

    # --- Logging Configuration ---
    LOG_LEVEL: str = Field(
        default=os.environ.get("LOG_LEVEL", "INFO"),
        description="Default logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).",
    )
    LOG_FORMAT: str = Field(
        default=os.environ.get(
            "LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ),
        description="Log format string.",
    )
    LOG_FILE_PATH: str = Field(
        default=os.environ.get("LOG_FILE_PATH", "logs/resync.log"),
        description="Path to log file.",
    )

    # --- CORS Configuration ---
    CORS_ENABLED: bool = Field(
        default=bool(os.environ.get("CORS_ENABLED", True)),
        description="Enable CORS middleware.",
    )
    CORS_ENVIRONMENT: str = Field(
        default=os.environ.get("CORS_ENVIRONMENT", "development"),
        description="CORS environment (development, production, test).",
    )
    CORS_ALLOWED_ORIGINS: str = Field(
        default=os.environ.get("CORS_ALLOWED_ORIGINS", ""),
        description="Comma-separated list of allowed origins for CORS.",
    )
    CORS_ALLOW_CREDENTIALS: bool = Field(
        default=bool(os.environ.get("CORS_ALLOW_CREDENTIALS", False)),
        description="Allow credentials in CORS requests.",
    )
    CORS_LOG_VIOLATIONS: bool = Field(
        default=bool(os.environ.get("CORS_LOG_VIOLATIONS", True)),
        description="Log CORS violations for security monitoring.",
    )
    model_config = ConfigDict()




