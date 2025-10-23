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
    mock_client.get = AsyncMock(return_value=b"ok")
    mock_client.delete = AsyncMock(return_value=True)
    mock_client.connection_pool = AsyncMock()
    mock_client.connection_pool.max_connections = 50

    with patch("resync.core.redis_init.redis.Redis.from_url", return_value=mock_client):
        initializer = RedisInitializer()

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
            mock_client.set.call_count == 2
        ), "Set should be called twice (lock and test key)"
        mock_client.get.assert_called_once()
        assert (
            mock_client.delete.call_count == 2
        ), "Delete should be called twice (lock and test key)"


@pytest.mark.asyncio
async def test_redis_initializer_retry_logic():
    """
    Test Redis initialization retry logic with mocking.
    """
    # Simulate connection failures
    mock_client = AsyncMock(spec=redis.Redis)
    mock_client.ping = AsyncMock(
        side_effect=[
            redis.exceptions.ConnectionError("First attempt failed"),
            redis.exceptions.ConnectionError("Second attempt failed"),
            True,
        ]
    )
    mock_client.set = AsyncMock(return_value=True)
    mock_client.get = AsyncMock(return_value=b"ok")
    mock_client.delete = AsyncMock(return_value=True)
    mock_client.connection_pool = AsyncMock()
    mock_client.connection_pool.max_connections = 50

    with patch("resync.core.redis_init.redis.Redis.from_url", return_value=mock_client):
        initializer = RedisInitializer()

        # Initialize Redis with retry
        client = await initializer.initialize(
            redis_url="redis://mock:6379",
            max_retries=3,
            base_backoff=0.1,
            max_backoff=1.0,
        )

        # Verify client is initialized after retries
        assert client is not None, "Redis client should be initialized after retries"

        # Verify retry behavior
        assert mock_client.ping.call_count == 3, "Should have retried 3 times"


@pytest.mark.asyncio
async def test_redis_initializer_health_check():
    """
    Test Redis health check mechanism with mocking.
    """
    # Mock Redis client
    mock_client = AsyncMock(spec=redis.Redis)
    mock_client.ping = AsyncMock(return_value=True)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.get = AsyncMock(return_value=b"ok")
    mock_client.delete = AsyncMock(return_value=True)
    mock_client.connection_pool = AsyncMock()
    mock_client.connection_pool.max_connections = 50

    with (
        patch("resync.core.redis_init.redis.Redis.from_url", return_value=mock_client),
        patch("resync.core.redis_init.asyncio.create_task") as mock_create_task,
    ):
        initializer = RedisInitializer()

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
