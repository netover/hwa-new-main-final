import pytest
import asyncio

from resync.core.pools.base_pool import ConnectionPoolConfig
from resync.core.pools.pool_manager import (
    get_connection_pool_manager,
    reset_connection_pool_manager,
)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def pool_config():
    """Standard pool configuration for tests."""
    return ConnectionPoolConfig(
        pool_name="test_pool",
        min_size=2,
        max_size=5,
        idle_timeout=300,
        connection_timeout=5,
        health_check_interval=60,
        max_lifetime=1800,
    )


@pytest.fixture(autouse=True)
async def cleanup_manager():
    """Cleanup connection pool manager after each test."""
    yield
    await reset_connection_pool_manager()


# ============================================================================
# RACE CONDITION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_singleton_race_condition():
    """Test that singleton is thread-safe under concurrent access."""

    async def get_manager():
        return await get_connection_pool_manager()

    # Create 100 concurrent tasks
    tasks = [get_manager() for _ in range(100)]
    managers = await asyncio.gather(*tasks)

    # All should be the same instance
    assert len(set(id(m) for m in managers)) == 1
