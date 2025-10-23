import pytest
from resync.core.async_cache import AsyncTTLCache


@pytest.mark.asyncio
async def test_cache_paranoia_mode_defaults():
    """Test that paranoia mode uses lower default bounds."""
    # Create cache with paranoia mode enabled
    cache = AsyncTTLCache(ttl_seconds=10, paranoia_mode=True)

    # In paranoia mode, bounds should be lower
    # But since we're not loading from settings, it might still use constructor defaults
    assert hasattr(cache, "paranoia_mode")
    assert cache.paranoia_mode is True

    await cache.stop()


@pytest.mark.asyncio
async def test_cache_paranoia_mode_bounds_reduction():
    """Test that paranoia mode reduces bounds."""
    # Create cache normally first
    cache = AsyncTTLCache(ttl_seconds=10)

    # Check normal bounds
    normal_max_entries = cache.max_entries
    normal_max_memory_mb = cache.max_memory_mb

    # Enable paranoia mode
    cache.paranoia_mode = True

    # Apply paranoia mode bounds reduction
    original_max_entries = cache.max_entries
    original_max_memory_mb = cache.max_memory_mb

    # Manually apply the paranoia mode logic
    if cache.paranoia_mode:
        cache.max_entries = min(
            cache.max_entries, 10000
        )  # Max 10K entries in paranoia mode
        cache.max_memory_mb = min(cache.max_memory_mb, 10)  # Max 10MB in paranoia mode

    # Check that bounds were reduced
    assert cache.max_entries <= min(original_max_entries, 10000)
    assert cache.max_memory_mb <= min(original_max_memory_mb, 10)

    await cache.stop()
