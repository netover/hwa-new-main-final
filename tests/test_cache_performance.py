"""
Testes de performance para validar que as melhorias não impactam negativamente o desempenho.
"""
import asyncio
import time
import pytest

from resync.core.cache.async_cache_refactored import AsyncTTLCache


@pytest.fixture
async def cache():
    """Create a fresh AsyncTTLCache instance for each test."""
    cache = AsyncTTLCache(ttl_seconds=60, cleanup_interval=60, num_shards=16)
    yield cache
    # Ensure cleanup task is stopped
    if cache.cleanup_task and not cache.cleanup_task.done():
        cache.cleanup_task.cancel()
        try:
            await cache.cleanup_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_set_performance(cache):
    """Test that set operations perform well with the new exception handling."""
    num_operations = 1000
    
    start_time = time.time()
    
    # Perform many set operations
    for i in range(num_operations):
        await cache.set(f"key_{i}", f"value_{i}")
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    # Calculate operations per second
    ops_per_sec = num_operations / elapsed_time
    
    # Should be able to perform at least 1000 ops/sec (adjust as needed)
    assert ops_per_sec > 1000, f"Performance too slow: {ops_per_sec:.2f} ops/sec"
    
    # Verify all values were set
    assert cache.size() == num_operations


@pytest.mark.asyncio
async def test_get_performance(cache):
    """Test that get operations perform well with the new exception handling."""
    # Pre-populate the cache
    num_operations = 1000
    for i in range(num_operations):
        await cache.set(f"key_{i}", f"value_{i}")
    
    start_time = time.time()
    
    # Perform many get operations
    for i in range(num_operations):
        value = await cache.get(f"key_{i}")
        assert value == f"value_{i}"
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    # Calculate operations per second
    ops_per_sec = num_operations / elapsed_time
    
    # Should be able to perform at least 5000 ops/sec (gets should be faster than sets)
    assert ops_per_sec > 5000, f"Get performance too slow: {ops_per_sec:.2f} ops/sec"


@pytest.mark.asyncio
async def test_mixed_operations_performance(cache):
    """Test performance with mixed operations."""
    num_operations = 500
    
    start_time = time.time()
    
    # Perform mixed operations
    for i in range(num_operations):
        # Set operation
        await cache.set(f"key_{i}", f"value_{i}")
        
        # Get operation
        value = await cache.get(f"key_{i}")
        assert value == f"value_{i}"
        
        # Delete operation for half of the keys
        if i % 2 == 0:
            await cache.delete(f"key_{i}")
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    # Calculate operations per second (3 operations per iteration)
    total_ops = num_operations * 3
    ops_per_sec = total_ops / elapsed_time
    
    # Should be able to perform at least 1500 ops/sec
    assert ops_per_sec > 1500, f"Mixed operations performance too slow: {ops_per_sec:.2f} ops/sec"


@pytest.mark.asyncio
async def test_concurrent_operations_performance(cache):
    """Test performance with concurrent operations."""
    num_operations = 200
    num_tasks = 10
    
    async def worker_task(task_id):
        """Worker task that performs cache operations."""
        for i in range(num_operations):
            key = f"task_{task_id}_key_{i}"
            await cache.set(key, f"value_{task_id}_{i}")
            value = await cache.get(key)
            assert value == f"value_{task_id}_{i}"
    
    start_time = time.time()
    
    # Run multiple tasks concurrently
    tasks = [worker_task(i) for i in range(num_tasks)]
    await asyncio.gather(*tasks)
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    # Calculate operations per second (2 operations per iteration per task)
    total_ops = num_operations * 2 * num_tasks
    ops_per_sec = total_ops / elapsed_time
    
    # Should be able to perform at least 2000 ops/sec concurrently
    assert ops_per_sec > 2000, f"Concurrent operations performance too slow: {ops_per_sec:.2f} ops/sec"
    
    # Verify cache size
    assert cache.size() == num_operations * num_tasks


@pytest.mark.asyncio
async def test_metrics_overhead(cache):
    """Test that metrics collection doesn't add significant overhead."""
    # First, measure performance without detailed metrics
    num_operations = 100
    
    start_time = time.time()
    for i in range(num_operations):
        await cache.set(f"key_{i}", f"value_{i}")
    baseline_time = time.time() - start_time
    
    # Clear cache
    await cache.clear()
    
    # Now measure performance with detailed metrics collection
    start_time = time.time()
    for i in range(num_operations):
        await cache.set(f"key_{i}", f"value_{i}")
        # Get detailed metrics every 10 operations
        if i % 10 == 0:
            metrics = cache.get_detailed_metrics()
            assert "lock_contention" in metrics
            assert "hot_shards" in metrics
    
    metrics_time = time.time() - start_time
    
    # Metrics collection should not add more than 50% overhead
    overhead_ratio = metrics_time / baseline_time
    assert overhead_ratio < 1.5, f"Metrics overhead too high: {overhead_ratio:.2f}x"


@pytest.mark.asyncio
async def test_hot_shards_detection_performance(cache):
    """Test that hot shards detection doesn't impact performance."""
    # Pre-populate the cache
    num_operations = 1000
    for i in range(num_operations):
        await cache.set(f"key_{i}", f"value_{i}")
    
    # Measure time for hot shards detection
    start_time = time.time()
    hot_shards = cache.get_hot_shards()
    detection_time = time.time() - start_time
    
    # Detection should be very fast (less than 10ms)
    assert detection_time < 0.01, f"Hot shards detection too slow: {detection_time * 1000:.2f}ms"
    
    # Should return a list
    assert isinstance(hot_shards, list)