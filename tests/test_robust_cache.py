"""
Unit and integration tests for RobustCacheManager.
"""

import asyncio

import pytest

from resync.core.cache import RobustCacheManager
from resync.settings import settings


@pytest.mark.asyncio
async def test_robust_cache_basic_operations():
    """
    Test basic cache operations: set, get, and delete.
    """
    cache = RobustCacheManager(
        max_items=settings.robust_cache_max_items,
        max_memory_mb=settings.robust_cache_max_memory_mb,
        eviction_batch_size=settings.robust_cache_eviction_batch_size,
        enable_weak_refs=settings.robust_cache_enable_weak_refs,
        enable_wal=settings.robust_cache_enable_wal,
    )

    # Test set and get
    key = "test_key"
    value = {"data": "test_value"}

    set_result = await cache.set(key, value)
    assert set_result, "Cache set should succeed"

    retrieved_value = await cache.get(key)
    assert retrieved_value == value, "Retrieved value should match original"

    # Test metrics
    metrics = cache.get_metrics()
    assert metrics["items"] == 1, "Cache should have one item"
    assert metrics["hits"] > 0, "Cache hits should be recorded"


@pytest.mark.asyncio
async def test_robust_cache_memory_bounds():
    """
    Test cache memory bounds and LRU eviction.
    """
    cache = RobustCacheManager(
        max_items=5, max_memory_mb=1, eviction_batch_size=2  # Very small memory limit
    )

    # Add multiple items to trigger eviction
    for i in range(10):
        key = f"key_{i}"
        value = {"data": f"value_{i}" * 1000}  # Large value to consume memory
        await cache.set(key, value)

    # Check metrics
    metrics = cache.get_metrics()
    assert metrics["items"] <= 5, "Cache should respect max_items limit"
    assert metrics["memory_mb"] <= 1, "Cache should respect memory limit"
    assert metrics["evictions"] > 0, "LRU eviction should have occurred"


@pytest.mark.asyncio
async def test_robust_cache_ttl():
    """
    Test cache entry time-to-live (TTL) functionality.
    """
    from datetime import timedelta

    cache = RobustCacheManager()

    key = "ttl_test_key"
    value = {"data": "temporary_value"}
    ttl = timedelta(seconds=1)

    await cache.set(key, value, ttl)

    # Retrieve immediately
    retrieved_value = await cache.get(key)
    assert retrieved_value == value, "Value should be retrievable before TTL expires"

    # Wait for TTL to expire
    await asyncio.sleep(2)

    # Retrieve after TTL
    retrieved_value = await cache.get(key)
    assert retrieved_value is None, "Value should not be retrievable after TTL expires"


@pytest.mark.asyncio
async def test_robust_cache_weak_references():
    """
    Test weak reference handling for large objects.
    """
    cache = RobustCacheManager(
        max_memory_mb=1, enable_weak_refs=True  # Very small memory limit
    )

    # Create a large object that supports weak references
    class LargeObject:
        def __init__(self, data):
            self.data = data

    large_object = LargeObject("x" * 10_000_000)  # 10MB object

    # Attempt to set large object
    key = "large_object_key"
    set_result = await cache.set(key, large_object)

    # Check metrics
    metrics = cache.get_metrics()
    assert set_result, "Large object set should succeed with weak references"
    assert metrics["weak_refs"] > 0, "Weak references should be used for large objects"




