import asyncio

import pytest
import pytest_asyncio

from resync.core.cache_hierarchy import (
    CacheHierarchy,
    CacheMetrics,
    L1Cache,
)


class TestL1Cache:
    """Test L1 cache functionality."""

    @pytest_asyncio.fixture
    async def l1_cache(self):
        """Create L1 cache instance for testing."""
        return L1Cache(max_size=100)

    @pytest.mark.asyncio
    async def test_l1_basic_get_set(self, l1_cache):
        """Test basic get/set operations."""
        await l1_cache.set("test_key", "test_value")
        assert l1_cache.size() == 1
        value = await l1_cache.get("test_key")
        assert value == "test_value"
        value = await l1_cache.get("nonexistent")
        assert value is None

    @pytest.mark.asyncio
    async def test_l1_concurrent_access(self, l1_cache):
        """Test concurrent access to L1 cache."""
        await l1_cache.set("key1", "value1")

        async def getter():
            return await l1_cache.get("key1")

        async def setter():
            await l1_cache.set("key2", "value2")
            return await l1_cache.get("key2")

        results = await asyncio.gather(getter(), getter(), setter())
        assert results[0] == "value1"
        assert results[1] == "value1"
        assert results[2] == "value2"
        assert l1_cache.size() == 2

    @pytest.mark.asyncio
    async def test_l1_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        small_cache = L1Cache(max_size=3)
        await small_cache.set("key1", "value1")
        await small_cache.set("key2", "value2")
        await small_cache.set("key3", "value3")
        assert small_cache.size() == 3

        await small_cache.get("key1")
        await small_cache.set("key4", "value4")
        assert small_cache.size() == 3
        assert await small_cache.get("key2") is None
        assert await small_cache.get("key1") == "value1"
        assert await small_cache.get("key3") == "value3"
        assert await small_cache.get("key4") == "value4"

    @pytest.mark.asyncio
    async def test_l1_delete_operations(self, l1_cache):
        """Test delete operations."""
        await l1_cache.set("key1", "value1")
        await l1_cache.set("key2", "value2")
        assert l1_cache.size() == 2
        result = await l1_cache.delete("key1")
        assert result is True
        assert l1_cache.size() == 1
        result = await l1_cache.delete("nonexistent")
        assert result is False
        assert l1_cache.size() == 1
        assert await l1_cache.get("key2") == "value2"

    @pytest.mark.asyncio
    async def test_l1_clear_operations(self, l1_cache):
        """Test clear operations."""
        await l1_cache.set("key1", "value1")
        await l1_cache.set("key2", "value2")
        assert l1_cache.size() == 2
        await l1_cache.clear()
        assert l1_cache.size() == 0
        assert await l1_cache.get("key1") is None
        assert await l1_cache.get("key2") is None


class TestCacheMetrics:
    """Test cache metrics functionality."""

    def test_metrics_calculations(self):
        """Test metrics calculations."""
        metrics = CacheMetrics()
        assert metrics.l1_hit_ratio == 0.0
        assert metrics.l2_hit_ratio == 0.0
        assert metrics.overall_hit_ratio == 0.0
        metrics.l1_hits = 80
        metrics.l1_misses = 20
        metrics.l2_hits = 15
        metrics.l2_misses = 5
        metrics.total_gets = 120
        assert metrics.l1_hit_ratio == 0.8
        assert metrics.l2_hit_ratio == 0.75
        assert metrics.overall_hit_ratio == (80 + 15) / 120


class TestCacheHierarchy:
    """Test cache hierarchy functionality."""

    @pytest_asyncio.fixture
    async def cache_hierarchy(self):
        """Create cache hierarchy instance for testing."""
        cache = CacheHierarchy(
            l1_max_size=100, l2_ttl_seconds=30, l2_cleanup_interval=10
        )
        await cache.start()
        yield cache
        await cache.stop()

    @pytest.mark.asyncio
    async def test_hierarchy_basic_operations(self, cache_hierarchy):
        """Test basic get/set operations in hierarchy."""
        await cache_hierarchy.set("test_key", "test_value")
        assert cache_hierarchy.metrics.total_sets == 1
        value = await cache_hierarchy.get("test_key")
        assert value == "test_value"
        assert cache_hierarchy.metrics.total_gets == 1
        assert cache_hierarchy.metrics.l1_hits == 1

    @pytest.mark.asyncio
    async def test_hierarchy_write_through(self, cache_hierarchy):
        """Test write-through pattern."""
        await cache_hierarchy.set("write_key", "write_value")
        l1_size, l2_size = cache_hierarchy.size()
        assert l1_size >= 1
        assert l2_size >= 1
        value = await cache_hierarchy.get("write_key")
        assert value == "write_value"

    @pytest.mark.asyncio
    async def test_hierarchy_miss_scenario(self, cache_hierarchy):
        """Test cache miss scenario."""
        value = await cache_hierarchy.get("nonexistent")
        assert value is None
        assert cache_hierarchy.metrics.l1_misses >= 1
        assert cache_hierarchy.metrics.l2_misses >= 1

    @pytest.mark.asyncio
    async def test_hierarchy_set_from_source(self, cache_hierarchy):
        """Test set_from_source method."""
        await cache_hierarchy.set_from_source(
            "source_key", "source_value", ttl_seconds=60
        )
        value = await cache_hierarchy.get("source_key")
        assert value == "source_value"
        assert cache_hierarchy.metrics.total_sets == 1

    @pytest.mark.asyncio
    async def test_hierarchy_delete_operations(self, cache_hierarchy):
        """Test delete operations."""
        await cache_hierarchy.set("delete_key", "delete_value")
        value = await cache_hierarchy.get("delete_key")
        assert value == "delete_value"
        result = await cache_hierarchy.delete("delete_key")
        assert result is True
        value = await cache_hierarchy.get("delete_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_hierarchy_clear_operations(self, cache_hierarchy):
        """Test clear operations."""
        await cache_hierarchy.set("key1", "value1")
        await cache_hierarchy.set("key2", "value2")
        assert cache_hierarchy.metrics.total_sets == 2
        await cache_hierarchy.clear()
        assert await cache_hierarchy.get("key1") is None
        assert await cache_hierarchy.get("key2") is None

    @pytest.mark.asyncio
    async def test_hierarchy_l1_eviction_with_l2_persistence(self):
        """Test L1 eviction while L2 retains data."""
        small_cache = CacheHierarchy(l1_max_size=2, l2_ttl_seconds=30)
        await small_cache.start()
        try:
            await small_cache.set("key1", "value1")
            await small_cache.set("key2", "value2")
            await small_cache.set("key3", "value3")
            l1_size, l2_size = small_cache.size()
            assert l1_size == 2
            assert l2_size == 3
            value = await small_cache.get("key1")
            assert value == "value1"
            l1_size, l2_size = small_cache.size()
            assert l1_size == 2
        finally:
            await small_cache.stop()


class TestCacheHierarchyStress:
    """Stress tests for cache hierarchy."""

    @pytest.mark.asyncio
    async def test_high_concurrency(self):
        """Test cache hierarchy under high concurrency."""
        cache = CacheHierarchy(l1_max_size=1000)
        await cache.start()
        try:

            async def worker(worker_id: int):
                for i in range(100):
                    key = f"worker_{worker_id}_key_{i}"
                    value = f"worker_{worker_id}_value_{i}"
                    try:
                        await cache.set(key, value)
                        result = await cache.get(key)
                        assert result == value
                    except ValueError:
                        # This is expected if the L2 cache fills up during stress testing
                        pass
                    if i % 10 == 0:
                        await cache.delete(key)
                return worker_id

            tasks = [worker(i) for i in range(10)]
            results = await asyncio.gather(*tasks)
            assert len(results) == 10
            assert len(set(results)) == 10
            l1_size, l2_size = cache.size()
            assert l1_size > 0
            assert l2_size > 0
        finally:
            await cache.stop()




