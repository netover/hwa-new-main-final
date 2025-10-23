"""Cache management API endpoints.

This module provides REST API endpoints for cache management operations,
including cache statistics, cache clearing, and cache health monitoring.
It supports both memory and Redis-based caching with detailed metrics.
"""

import logging
import secrets
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
try:
    from redis import Redis
    from redis.exceptions import ConnectionError, TimeoutError
except ImportError:
    # Handle case where redis is not available (e.g., in test environments)
    Redis = None
    ConnectionError = None
    TimeoutError = None

# Original imports (now wrapped in try/except)
# from redis import Redis
# from redis.exceptions import ConnectionError, TimeoutError
from pydantic import BaseModel
from redis import Redis
from redis.exceptions import ConnectionError, TimeoutError

from resync.core.fastapi_di import get_tws_client
from resync.core.interfaces import ITWSClient
from resync.core.rate_limiter import authenticated_rate_limit
from resync.settings import settings

logger = logging.getLogger(__name__)

cache_router = APIRouter()

# Define o esquema de segurança: espera credenciais Basic Auth.
security = HTTPBasic()

# Module-level dependencies to avoid B008 errors
security_dependency = Depends(security)
tws_client_dependency = Depends(get_tws_client)


class CacheInvalidationResponse(BaseModel):
    status: str
    detail: str


class CacheStats(BaseModel):
    hits: int
    misses: int
    hit_rate: float
    size: int


class ConnectionPoolValidator:
    """Validates connection pool settings for database connections."""

    @staticmethod
    def validate_connection_pool(
        min_connections: int, max_connections: int, timeout: float
    ) -> bool:
        """
        Validates connection pool parameters.

        Args:
            min_connections: Minimum number of connections in the pool
            max_connections: Maximum number of connections in the pool
            timeout: Connection timeout in seconds

        Returns:
            True if the configuration is valid, False otherwise
        """
        if min_connections < 0:
            logger.error("Minimum connections must be non-negative")
            return False

        if max_connections <= 0:
            logger.error("Maximum connections must be positive")
            return False

        if min_connections > max_connections:
            logger.error("Minimum connections must not exceed maximum connections")
            return False

        if timeout <= 0:
            logger.error("Timeout must be positive")
            return False

        logger.info(
            f"Connection pool validation passed: min={min_connections}, "
            f"max={max_connections}, timeout={timeout}s"
        )
        return True


def get_redis_connection() -> Optional[Redis]:
    """
    Get a Redis connection using connection pooling and validation.

    Returns:
        Redis connection object or None if connection fails
    """
    try:
        redis_client = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        # Test the connection
        redis_client.ping()
        logger.info("Successfully connected to Redis")
        return redis_client
    except (ConnectionError, TimeoutError) as e:
        logger.error(f"Failed to connect to Redis: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error when connecting to Redis: {e}")
        return None


class RedisCacheManager:
    """
    Enhanced Redis cache manager with optimized caching strategies.
    """

    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client

    def get(self, key: str) -> Optional[str]:
        """
        Retrieve a value from Redis cache.

        Args:
            key: The cache key

        Returns:
            Cached value or None if not found
        """
        try:
            value = self.redis_client.get(key)
            if value is not None:
                logger.debug(f"Cache hit for key: {key}")
            else:
                logger.debug(f"Cache miss for key: {key}")
            return value
        except Exception as e:
            logger.error(f"Error retrieving from cache: {e}")
            return None

    def set(self, key: str, value: str, expire: int = 3600) -> bool:
        """
        Set a value in Redis cache.

        Args:
            key: The cache key
            value: The value to cache
            expire: Expiration time in seconds (default 1 hour)

        Returns:
            True if successful, False otherwise
        """
        try:
            self.redis_client.setex(key, expire, value)
            logger.debug(f"Set cache key: {key} with expire: {expire}")
            return True
        except Exception as e:
            logger.error(f"Error setting cache: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete a key from Redis cache.

        Args:
            key: The cache key to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            deleted = self.redis_client.delete(key)
            logger.debug(f"Deleted cache key: {key}, count: {deleted}")
            return bool(deleted)
        except Exception as e:
            logger.error(f"Error deleting cache: {e}")
            return False

    def clear_pattern(self, pattern: str) -> int:
        """
        Delete multiple keys matching a pattern.

        Args:
            pattern: The pattern to match (e.g., "tws:*")

        Returns:
            Number of keys deleted
        """
        try:
            # Use SCAN to avoid blocking Redis in production
            total_deleted = 0
            for key in self.redis_client.scan_iter(match=pattern, count=1000):
                total_deleted += int(self.redis_client.delete(key))
            logger.debug(f"Cleared {total_deleted} keys matching pattern: {pattern}")
            return total_deleted
        except Exception as e:
            logger.error(f"Error clearing pattern: {e}")
            return 0

    def get_cache_stats(self) -> CacheStats:
        """
        Get cache statistics.

        Returns:
            CacheStats object with statistics
        """
        info = self.redis_client.info()
        keyspace = info.get("Keyspace", {})  # {'db0': {'keys': 123, ...}}
        hits = int(info.get("keyspace_hits", 0))
        misses = int(info.get("keyspace_misses", 0))
        total = hits + misses
        hit_rate = (hits / total) if total > 0 else 0.0
        size = sum(int(db_info.get("keys", 0)) for db_info in keyspace.values())

        return CacheStats(hits=hits, misses=misses, hit_rate=hit_rate, size=size)


# Global Redis cache manager instance
redis_manager: Optional[RedisCacheManager] = None


def validate_connection_pool() -> bool:
    """
    Function to validate connection pool settings as specified in the implementation plan.

    Returns:
        True if validation passes, False otherwise
    """
    # Use settings from the application configuration
    try:
        min_conn = settings.redis_min_connections
        max_conn = settings.redis_max_connections
        timeout = settings.redis_timeout
    except (TypeError, ValueError) as e:
        logger.error(f"Error parsing Redis connection settings: {e}")
        return False

    return ConnectionPoolValidator.validate_connection_pool(min_conn, max_conn, timeout)


async def verify_admin_credentials(
    creds: HTTPBasicCredentials = security_dependency,
) -> None:
    """
    Dependência para verificar as credenciais de administrador usando Basic Auth.

    Esta função é usada como uma dependência de segurança para endpoints
    administrativos. Ela valida o nome de usuário e a senha fornecidos
    contra as credenciais definidas no sistema.

    Utiliza `secrets.compare_digest` para uma comparação segura que previne
    ataques de timing.

    Args:
        creds: Credenciais HTTPBasic injetadas pelo FastAPI.

    Raises:
        HTTPException: Lança um erro 401 Unauthorized se as credenciais
                       forem inválidas.
    """
    # Busca as credenciais de administrador a partir das configurações da aplicação.
    admin_user = settings.ADMIN_USERNAME
    admin_pass = settings.ADMIN_PASSWORD

    # Garante que as credenciais de administrador estão configuradas no servidor.
    if not admin_user or not admin_pass:
        logger.error("Admin credentials not configured on the server")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="As credenciais de administrador não estão configuradas no servidor.",
        )

    correct_username = secrets.compare_digest(creds.username, admin_user)
    correct_password = secrets.compare_digest(creds.password, admin_pass)

    if not (correct_username and correct_password):
        logger.warning(
            f"Failed admin authentication attempt for user: {creds.username}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais de administrador inválidas ou ausentes.",
            headers={"WWW-Authenticate": "Basic"},
        )

    logger.info(f"Successful admin authentication for user: {creds.username}")


@cache_router.post(
    "/invalidate",
    summary="Invalidate TWS Cache",
    response_model=CacheInvalidationResponse,
)
@authenticated_rate_limit
async def invalidate_tws_cache(
    request: Request,
    scope: str = "system",  # 'system', 'jobs', 'workstations'
    tws_client: ITWSClient = tws_client_dependency,
    # Call verify_admin_credentials inside the function to handle rate limiting properly
    creds: HTTPBasicCredentials = security_dependency,
) -> CacheInvalidationResponse:
    """
    Invalidates the TWS data cache based on the specified scope.
    Requires administrator credentials via HTTP Basic Auth for authorization.

    - **scope='system'**: Invalidates all TWS-related caches.
    - **scope='jobs'**: Invalidates only the main job list cache.
    - **scope='workstations'**: Invalidates only the workstation list cache.
    """
    try:
        # Verify admin credentials (await async dependency)
        await verify_admin_credentials(creds)

        # Log the cache invalidation request for security auditing
        logger.info(
            f"Cache invalidation requested by user '{creds.username}' with scope '{scope}'"
        )

        # Initialize Redis manager if not already done
        global redis_manager
        if redis_manager is None:
            redis_client = get_redis_connection()
            if redis_client:
                redis_manager = RedisCacheManager(redis_client)
            else:
                logger.warning(
                    "Could not connect to Redis, proceeding with TWS client invalidation only"
                )

        if scope == "system":
            # Use Redis manager to clear all TWS-related keys if available
            if redis_manager:
                redis_manager.clear_pattern("tws:*")

            await tws_client.invalidate_system_cache()
            logger.info("Full TWS system cache invalidated successfully")
            return CacheInvalidationResponse(
                status="success", detail="Full TWS system cache invalidated."
            )
        elif scope == "jobs":
            # Use Redis manager to clear job-related keys if available
            if redis_manager:
                redis_manager.clear_pattern("tws:jobs:*")

            await tws_client.invalidate_all_jobs()
            logger.info("All jobs list cache invalidated successfully")
            return CacheInvalidationResponse(
                status="success", detail="All jobs list cache invalidated."
            )
        elif scope == "workstations":
            # Use Redis manager to clear workstation-related keys if available
            if redis_manager:
                redis_manager.clear_pattern("tws:workstations:*")

            await tws_client.invalidate_all_workstations()
            logger.info("All workstations list cache invalidated successfully")
            return CacheInvalidationResponse(
                status="success", detail="All workstations list cache invalidated."
            )
        else:
            logger.warning(f"Invalid scope '{scope}' provided for cache invalidation")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid scope '{scope}'. Must be 'system', 'jobs', or 'workstations'.",
            )
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error during cache invalidation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invalidate cache due to server error.",
        ) from e


@cache_router.get("/stats", summary="Get cache statistics", response_model=CacheStats)
@authenticated_rate_limit
async def get_cache_stats(
    request: Request, creds: HTTPBasicCredentials = security_dependency
) -> CacheStats:
    """
    Get cache statistics including hit rate, size, etc.
    """
    # Verify admin credentials
    await verify_admin_credentials(creds)

    # Initialize Redis manager if not already done
    global redis_manager
    if redis_manager is None:
        redis_client = get_redis_connection()
        if redis_client:
            redis_manager = RedisCacheManager(redis_client)
        else:
            logger.error("Could not connect to Redis for stats")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not connect to Redis for cache statistics.",
            )

    # Get and return cache stats
    stats = redis_manager.get_cache_stats()
    logger.info(
        f"Cache stats retrieved: hits={stats.hits}, misses={stats.misses}, "
        f"hit_rate={stats.hit_rate:.2%}, size={stats.size}"
    )

    return stats


def get_database_connection(
    min_connections: int = 1, max_connections: int = 10, timeout: float = 30.0
) -> Union[object, None]:
    """
    Get a database connection with pool validation.

    Args:
        min_connections: Minimum number of connections in the pool
        max_connections: Maximum number of connections in the pool
        timeout: Connection timeout in seconds

    Returns:
        Database connection object or None if validation fails
    """
    if not ConnectionPoolValidator.validate_connection_pool(
        min_connections, max_connections, timeout
    ):
        logger.error("Connection pool validation failed")
        return None

    # In a real implementation, this would return an actual database connection
    # based on the validated pool parameters
    logger.info("Database connection retrieved successfully after pool validation")
    return object()  # Placeholder for actual connection
