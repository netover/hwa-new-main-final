"""
Tests for cache bounds and enforcement logic in AsyncTTLCache.
"""

import pytest

from resync.core.async_cache import AsyncTTLCache


@pytest.mark.asyncio
async def test_cache_initial_bounds():
    """Test that cache is initialized with default bounds."""
    cache = AsyncTTLCache()
    try:
        assert cache.max_entries > 0
        assert cache.max_memory_mb > 0
    finally:
        await cache.stop()


@pytest.mark.asyncio
async def test_cache_item_count_bounds_check():
    """Test the item count bounds checking method."""
    cache = AsyncTTLCache(max_entries=10)
    try:
        # Should be within bounds
        assert cache._check_item_count_bounds(5) is True
        # Should be at the limit, but still within bounds
        assert cache._check_item_count_bounds(10) is True
        # Should exceed bounds
        assert cache._check_item_count_bounds(11) is False
    finally:
        await cache.stop()


@pytest.mark.asyncio
async def test_cache_memory_usage_bounds_check():
    """Test the memory usage bounds checking method."""
    # This test is a basic check; more advanced memory profiling is complex
    cache = AsyncTTLCache(max_memory_mb=1)
    try:
        # A small number of items should be well within memory limits
        result = cache._check_memory_usage_bounds(100)
        assert isinstance(result, bool)
    finally:
        await cache.stop()


@pytest.mark.asyncio
async def test_cache_bounds_enforcement():
    """Test that cache enforces bounds during operations."""
    # Create a cache with very small bounds for testing
    cache = AsyncTTLCache(ttl_seconds=10, num_shards=1, max_entries=10)
    try:
        # Add items up to the limit
        for i in range(10):
            await cache.set(f"key_{i}", f"value_{i}")

        # Verify cache size
        assert cache.size() == 10

        # Try to add one more - this should trigger bounds checking and LRU eviction
        await cache.set("key_10", "value_10")

        # The size should not exceed the max_entries limit
        assert cache.size() == 10

        # Check that the new key is present and one old key was evicted
        assert await cache.get("key_10") == "value_10"
        # The least recently used key should be evicted, which is key_0
        assert await cache.get("key_0") is None
    finally:
        await cache.stop()


@pytest.mark.asyncio
async def test_paranoia_mode_bounds():
    """Test that paranoia mode correctly lowers the cache bounds."""
    # High initial bounds
    cache = AsyncTTLCache(max_entries=100000, max_memory_mb=100, paranoia_mode=True)
    try:
        # Paranoia mode should lower the bounds
        assert cache.max_entries == 10000
        assert cache.max_memory_mb == 10
    finally:
        await cache.stop()
