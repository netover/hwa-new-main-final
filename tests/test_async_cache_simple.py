"""
Simple tests for AsyncTTLCache to verify basic functionality.
"""

import pytest
from resync.core.async_cache import AsyncTTLCache


class TestBasicCacheOperations:
    """Test basic cache operations."""

    @pytest.fixture
    def cache(self):
        """Create a fresh cache instance for each test."""
        return AsyncTTLCache(ttl_seconds=60, cleanup_interval=1, num_shards=4)

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache):
        """Test basic set and get operations."""
        await cache.set("key1", "value1")
        result = await cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, cache):
        """Test getting a key that doesn't exist."""
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, cache):
        """Test deleting a key."""
        await cache.set("key1", "value1")
        deleted = await cache.delete("key1")
        assert deleted is True
        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_size(self, cache):
        """Test cache size tracking."""
        assert cache.size() == 0

        await cache.set("key1", "value1")
        assert cache.size() == 1

        await cache.set("key2", "value2")
        assert cache.size() == 2

        await cache.clear()
        assert cache.size() == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])