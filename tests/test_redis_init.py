"""
Unit and integration tests for RedisInitializer.
"""

import pytest
from unittest.mock import AsyncMock, patch
from resync.core.redis_init import RedisInitializer
from resync.settings import settings

# Soft import for redis (optional dependency for testing)
try:
    import redis.asyncio as redis
    import redis.exceptions
except ImportError:
    redis = None
    redis.exceptions = None


@pytest.mark.skipif(redis is None, reason="redis not available")
@pytest.mark.asyncio
async def test_redis_initializer_basic():
    """
    Test basic Redis initialization functionality with mocking.
    """
    # Mock Redis client and connection
    mock_client = AsyncMock(spec=redis.Redis)
    mock_client.ping = AsyncMock(return_value=True)
    mock_client.set = AsyncMock(return_value=True)  # Allow multiple set calls
    mock_client.get = AsyncMock(return_value="ok")
    mock_client.delete = AsyncMock(return_value=True)
    mock_client.connection_pool = AsyncMock()
    mock_client.connection_pool.max_connections = 50

    initializer = RedisInitializer()
    with patch("resync.core.redis_init.redis.Redis.from_url", return_value=mock_client), \
         patch("resync.core.redis_init.os.getenv", return_value=None), \
         patch.object(initializer, "_initialize_idempotency", return_value=None):

        # Initialize Redis
        client = await initializer.initialize(
            redis_url="redis://mock:6379",
            max_retries=settings.redis_max_startup_retries,
            base_backoff=settings.redis_startup_backoff_base,
            max_backoff=settings.redis_startup_backoff_max,
            health_check_interval=settings.redis_health_check_interval,
        )

        # Verify client is initialized
        assert client is not None, "Redis client should be initialized"

        # Verify mock calls
        mock_client.ping.assert_called_once()
        assert (
            mock_client.set.call_count >= 2
        ), "Set should be called for lock and test key (at least 2 times)"
        mock_client.get.assert_called_once()
        assert (
            mock_client.delete.call_count >= 1
        ), "Delete should be called for test key (at least 1 time)"


@pytest.mark.asyncio
async def test_redis_initializer_retry_logic():
    """
    Test Redis initialization accepts retry parameters.
    """
    # Mock successful Redis client
    mock_client = AsyncMock(spec=redis.Redis)
    mock_client.ping = AsyncMock(return_value=True)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.get = AsyncMock(return_value="ok")
    mock_client.delete = AsyncMock(return_value=True)
    mock_client.connection_pool = AsyncMock()
    mock_client.connection_pool.max_connections = 50

    initializer = RedisInitializer()
    with patch("resync.core.redis_init.redis.Redis.from_url", return_value=mock_client), \
         patch("resync.core.redis_init.os.getenv", return_value=None), \
         patch.object(initializer, "_initialize_idempotency", return_value=None):

        # Initialize Redis with different retry parameters
        client = await initializer.initialize(
            redis_url="redis://mock:6379",
            max_retries=5,  # Different from default
            base_backoff=0.05,
            max_backoff=2.0,
        )

        # Verify client is initialized
        assert client is not None, "Redis client should be initialized with custom retries"
        mock_client.ping.assert_called_once()


@pytest.mark.asyncio
async def test_redis_initializer_health_check():
    """
    Test Redis health check mechanism with mocking.
    """
    # Mock Redis client
    mock_client = AsyncMock(spec=redis.Redis)
    mock_client.ping = AsyncMock(return_value=True)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.get = AsyncMock(return_value="ok")
    mock_client.delete = AsyncMock(return_value=True)
    mock_client.connection_pool = AsyncMock()
    mock_client.connection_pool.max_connections = 50

    initializer = RedisInitializer()
    with (
        patch("resync.core.redis_init.redis.Redis.from_url", return_value=mock_client),
        patch("resync.core.redis_init.asyncio.create_task") as mock_create_task,
        patch("resync.core.redis_init.os.getenv", return_value=None),
        patch.object(initializer, "_initialize_idempotency", return_value=None),
    ):

        # Initialize Redis
        client = await initializer.initialize(
            redis_url="redis://mock:6379",
            max_retries=settings.redis_max_startup_retries,
            base_backoff=settings.redis_startup_backoff_base,
            max_backoff=settings.redis_startup_backoff_max,
            health_check_interval=1,  # Short interval for testing
        )

        # Verify health check task was created
        mock_create_task.assert_called_once()

        # Verify initialization status
        assert initializer.initialized, "Redis should remain initialized"

        # Verify mock calls
        mock_client.ping.assert_called_once()
