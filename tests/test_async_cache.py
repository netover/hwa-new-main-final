import asyncio
import pytest
import time

from resync.core.async_cache import AsyncTTLCache


@pytest.fixture
async def cache():
    """Create a fresh AsyncTTLCache instance for each test."""
    cache = AsyncTTLCache(ttl_seconds=1, cleanup_interval=1, num_shards=4)
    yield cache
    # Ensure cleanup task is stopped
    if cache.cleanup_task and not cache.cleanup_task.done():
        cache.cleanup_task.cancel()
        try:
            await cache.cleanup_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_get_nonexistent_key(cache):
    """Test that getting a non-existent key returns None."""
    result = await cache.get("nonexistent_key")
    assert result is None


@pytest.mark.asyncio
async def test_set_and_get(cache):
    """Test basic set and get operations."""
    await cache.set("test_key", "test_value")
    result = await cache.get("test_key")
    assert result == "test_value"


@pytest.mark.asyncio
async def test_get_expired_key(cache):
    """Test that getting an expired key returns None."""
    await cache.set("expiring_key", "expiring_value", ttl_seconds=0.1)
    # Wait for the key to expire
    await asyncio.sleep(0.2)
    result = await cache.get("expiring_key")
    assert result is None


@pytest.mark.asyncio
async def test_delete_existing_key(cache):
    """Test deleting an existing key."""
    await cache.set("delete_key", "delete_value")
    result = await cache.delete("delete_key")
    assert result is True
    # Verify the key is gone
    assert await cache.get("delete_key") is None


@pytest.mark.asyncio
async def test_delete_nonexistent_key(cache):
    """Test deleting a non-existent key."""
    result = await cache.delete("nonexistent_key")
    assert result is False


@pytest.mark.asyncio
async def test_ttl_override(cache):
    """Test TTL override functionality."""
    await cache.set("ttl_key", "ttl_value", ttl_seconds=0.1)
    # Wait less than the TTL
    await asyncio.sleep(0.05)
    # Key should still exist
    result = await cache.get("ttl_key")
    assert result == "ttl_value"

    # Wait for the key to expire
    await asyncio.sleep(0.1)
    result = await cache.get("ttl_key")
    assert result is None


@pytest.mark.asyncio
async def test_cache_size(cache):
    """Test cache size tracking."""
    initial_size = cache.size()
    assert initial_size == 0

    await cache.set("key1", "value1")
    await cache.set("key2", "value2")
    current_size = cache.size()
    assert current_size == 2


@pytest.mark.asyncio
async def test_clear_cache(cache):
    """Test clearing the entire cache."""
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")
    assert cache.size() == 2

    await cache.clear()
    assert cache.size() == 0
    assert await cache.get("key1") is None
    assert await cache.get("key2") is None


@pytest.mark.asyncio
async def test_input_validation_key_none(cache):
    """Test input validation for None key."""
    with pytest.raises(TypeError):
        await cache.get(None)


@pytest.mark.asyncio
async def test_input_validation_key_empty(cache):
    """Test input validation for empty key."""
    with pytest.raises(ValueError):
        await cache.get("")


@pytest.mark.asyncio
async def test_input_validation_key_too_long(cache):
    """Test input validation for overly long key."""
    long_key = "x" * 1001  # More than 1000 chars
    with pytest.raises(ValueError):
        await cache.get(long_key)


@pytest.mark.asyncio
async def test_input_validation_control_chars(cache):
    """Test input validation for control characters in key."""
    with pytest.raises(ValueError):
        await cache.get("key\n")

    with pytest.raises(ValueError):
        await cache.get("key\r")

    with pytest.raises(ValueError):
        await cache.get("key\x00")  # null byte


@pytest.mark.asyncio
async def test_value_validation_none(cache):
    """Test input validation for None value."""
    with pytest.raises(ValueError):
        await cache.set("key", None)


@pytest.mark.asyncio
async def test_ttl_validation_negative(cache):
    """Test input validation for negative TTL."""
    with pytest.raises(ValueError):
        await cache.set("key", "value", ttl_seconds=-1)


@pytest.mark.asyncio
async def test_ttl_validation_too_large(cache):
    """Test input validation for overly large TTL."""
    with pytest.raises(ValueError):
        await cache.set("key", "value", ttl_seconds=86400 * 366)  # More than 1 year


@pytest.mark.asyncio
async def test_background_cleanup(cache):
    """Test automatic cleanup of expired entries."""
    await cache.set("expiring_key", "expiring_value", ttl_seconds=0.1)
    # Wait for cleanup interval + TTL
    await asyncio.sleep(0.2)
    # Verify the key has been cleaned up
    result = await cache.get("expiring_key")
    assert result is None


@pytest.mark.asyncio
async def test_lru_eviction(cache):
    """Test LRU eviction when cache bounds are exceeded."""
    # Set cache with smaller bounds for testing
    small_cache = AsyncTTLCache(ttl_seconds=10, num_shards=1, max_entries=2)

    # Add more items than the cache can hold
    await small_cache.set("key1", "value1")
    await small_cache.set("key2", "value2")
    # Access key1 to make it more recently used
    await small_cache.get("key1")
    # Add another key which should evict key2 (least recently used)
    await small_cache.set("key3", "value3")

    # key1 should still be there (recently used)
    assert await small_cache.get("key1") == "value1"
    # key2 should be evicted
    assert await small_cache.get("key2") is None
    # key3 should be there
    assert await small_cache.get("key3") == "value3"

    # Cleanup
    if small_cache.cleanup_task and not small_cache.cleanup_task.done():
        small_cache.cleanup_task.cancel()
        try:
            await small_cache.cleanup_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_memory_bounds_check(cache):
    """Test memory bounds checking functionality."""
    # Test with a small number of items to stay within memory bounds
    result = cache._check_memory_usage_bounds(1)  # 1 item
    assert result is True  # Should be within bounds with just 1 item


@pytest.mark.asyncio
async def test_cache_metrics(cache):
    """Test cache metrics updates."""
    initial_hits = cache.get_detailed_metrics()["hits"]
    initial_misses = cache.get_detailed_metrics()["misses"]

    # Miss operation
    await cache.get("nonexistent")
    after_miss_hits = cache.get_detailed_metrics()["hits"]
    after_miss_misses = cache.get_detailed_metrics()["misses"]

    # Verify miss was recorded
    assert after_miss_hits == initial_hits
    assert after_miss_misses == initial_misses + 1

    # Hit operation
    await cache.set("test_key", "test_value")
    await cache.get("test_key")
    after_hit_hits = cache.get_detailed_metrics()["hits"]
    after_hit_misses = cache.get_detailed_metrics()["misses"]

    # Verify hit was recorded
    assert after_hit_hits == initial_hits + 1
    assert after_hit_misses == initial_misses + 1


@pytest.mark.asyncio
async def test_concurrent_access(cache):
    """Test concurrent access to the cache."""

    async def set_and_get(key, value):
        await cache.set(key, value)
        return await cache.get(key)

    # Run multiple concurrent operations
    tasks = [set_and_get(f"key_{i}", f"value_{i}") for i in range(10)]

    results = await asyncio.gather(*tasks)

    # Verify all operations succeeded
    for i, result in enumerate(results):
        assert result == f"value_{i}"


@pytest.mark.asyncio
async def test_health_check(cache):
    """Test cache health check functionality."""
    health_result = await cache.health_check()

    # Verify health check returns a result with status
    assert "status" in health_result

    # If it's a critical error, the structure will be different
    if health_result["status"] == "critical":
        assert "error" in health_result
        assert "component" in health_result
    else:
        # Otherwise, check for regular fields
        assert "num_shards" in health_result
        assert "hit_rate" in health_result
        assert health_result["size"] >= 0
        # The status might be "healthy", "warning" or "error" depending on environment
        assert health_result["status"] in ["healthy", "warning", "error"]


@pytest.mark.asyncio
async def test_snapshot_and_restore(cache):
    """Test snapshot and restore functionality."""
    # Add some data to the cache
    await cache.set("snap_key1", "snap_value1", ttl_seconds=10)
    await cache.set("snap_key2", "snap_value2", ttl_seconds=10)

    # Create a snapshot
    snapshot = cache.create_backup_snapshot()

    # Verify snapshot contains the data
    assert snapshot["_metadata"]["total_entries"] == 2

    # Clear the cache
    await cache.clear()
    assert cache.size() == 0

    # Restore from snapshot
    restore_result = await cache.restore_from_snapshot(snapshot)
    assert restore_result is True

    # Verify data is restored
    assert await cache.get("snap_key1") == "snap_value1"
    assert await cache.get("snap_key2") == "snap_value2"


@pytest.mark.asyncio
async def test_rollback_transaction(cache):
    """Test transaction rollback functionality."""
    # This tests the rollback functionality with some basic operations
    operations = [
        {
            "operation": "set",
            "key": "rollback_key1",
            "value": "rollback_value1",
            "previous_value": None,
        },
        {
            "operation": "set",
            "key": "rollback_key2",
            "value": "rollback_value2",
            "previous_value": None,
        },
    ]

    # Perform the operations first
    await cache.set("rollback_key1", "rollback_value1")
    await cache.set("rollback_key2", "rollback_value2")

    # Then test rollback - though this is slightly complex to fully test
    # without more detailed rollback state tracking
    result = await cache.rollback_transaction(operations)
    assert result is True  # Should complete without error


@pytest.mark.asyncio
async def test_stop_cleanup_task(cache):
    """Test stopping the cleanup task."""
    # Ensure cleanup task is running
    cache._start_cleanup_task()
    assert cache.is_running is True

    # Stop the cleanup task
    await cache.stop()
    assert cache.is_running is False


@pytest.mark.asyncio
async def test_cache_bounds_enforcement():
    """Test cache bounds enforcement with too many items."""
    # Use a cache with a small size limit for this test
    cache = AsyncTTLCache(ttl_seconds=10, num_shards=2, max_entries=5)
    try:
        # Add items up to the limit
        for i in range(5):
            await cache.set(f"bound_key_{i}", f"bound_value_{i}")

        assert cache.size() == 5

        # Adding another item should work and trigger eviction
        await cache.set("bound_key_5", "bound_value_5")

        # The size should not exceed the max_entries limit
        assert cache.size() == 5

        # Check that the new key is present.
        assert await cache.get("bound_key_5") == "bound_value_5"
    finally:
        # Stop the cache's background task
        await cache.stop()


@pytest.mark.asyncio
async def test_memory_estimation(cache):
    """Test memory usage estimation functionality."""
    # Add some data to the cache
    await cache.set("mem_key1", "mem_value1")
    await cache.set("mem_key2", "mem_value2")

    # Call the memory bounds check method directly
    result = cache._check_memory_usage_bounds(2)  # 2 items

    # Should return True if within bounds
    assert result is True


@pytest.mark.asyncio
async def test_shard_distribution(cache):
    """Test that keys are distributed across shards."""
    # Add several keys
    for i in range(20):
        await cache.set(f"shard_test_key_{i}", f"value_{i}")

    # Check that shards are being used (not all in one shard)
    shard_distribution = cache.get_detailed_metrics()["shard_distribution"]

    # At least some shards should have entries
    non_empty_shards = sum(1 for count in shard_distribution if count > 0)

    # With 4 shards and 20 items, we expect multiple shards to be used
    assert non_empty_shards >= 2  # Should use at least 2 shards


@pytest.mark.asyncio
async def test_persistence_wal_simulation():
    """Simulate WAL/persistence functionality by testing snapshot mechanism."""
    # The current implementation doesn't have explicit WAL, but uses snapshots
    cache = AsyncTTLCache(ttl_seconds=30, num_shards=2)

    try:
        # Add some persistent data
        await cache.set("persistent_key1", {"data": "value1", "timestamp": time.time()})
        await cache.set("persistent_key2", {"data": "value2", "timestamp": time.time()})

        # Create a snapshot (simulating WAL log)
        snapshot = cache.create_backup_snapshot()
        assert len(snapshot) > 0
        assert "_metadata" in snapshot
        assert snapshot["_metadata"]["total_entries"] == 2

        # Simulate a crash by creating a new cache instance
        new_cache = AsyncTTLCache(ttl_seconds=30, num_shards=2)

        # Restore from snapshot (simulating recovery)
        restore_result = await new_cache.restore_from_snapshot(snapshot)
        assert restore_result is True

        # Verify data was recovered
        recovered_val1 = await new_cache.get("persistent_key1")
        recovered_val2 = await new_cache.get("persistent_key2")

        assert recovered_val1 is not None
        assert recovered_val2 is not None
        assert recovered_val1["data"] == "value1"
        assert recovered_val2["data"] == "value2"

        # Cleanup
        if cache.cleanup_task and not cache.cleanup_task.done():
            cache.cleanup_task.cancel()
            try:
                await cache.cleanup_task
            except asyncio.CancelledError:
                pass

        if new_cache.cleanup_task and not new_cache.cleanup_task.done():
            new_cache.cleanup_task.cancel()
            try:
                await new_cache.cleanup_task
            except asyncio.CancelledError:
                pass
    except Exception as e:
        # Cleanup in case of error
        if cache.cleanup_task and not cache.cleanup_task.done():
            cache.cleanup_task.cancel()
            try:
                await cache.cleanup_task
            except asyncio.CancelledError:
                pass
        raise e


if __name__ == "__main__":
    pytest.main([__file__])