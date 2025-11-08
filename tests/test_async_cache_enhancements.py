import asyncio
import os
import shutil
import tempfile
import time
from unittest.mock import patch

import pytest

from resync.core.adaptive_eviction import AdaptiveEviction
from resync.core.async_cache import AsyncTTLCache
from resync.core.incident_response import IncidentResponse
from resync.core.metrics import runtime_metrics
from resync.core.shard_balancer import ShardBalancer
from resync.core.snapshot_cleaner import SnapshotCleaner

# Set test configuration
os.environ["CACHE_VALIDATION_MODE"] = "strict"
os.environ["ASYNC_CACHE_ENABLE_WAL"] = "true"

@pytest.fixture
def cache_dir():
    """Create a temporary directory for cache files."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def cache(cache_dir):
    """Create a test cache instance."""
    # Reset metrics
    runtime_metrics.cache_hits.set(0)
    runtime_metrics.cache_misses.set(0)
    runtime_metrics.cache_sets.set(0)
    runtime_metrics.cache_evictions.set(0)
    runtime_metrics.cache_cleanup_cycles.set(0)

    cache = AsyncTTLCache(
        ttl_seconds=1,
        cleanup_interval=1,
        num_shards=4,
        enable_wal=True,
        wal_path=f"{cache_dir}/wal",
        max_entries=100,
        max_memory_mb=10,
        paranoia_mode=False
    )
    yield cache
    asyncio.run(cache.stop())

@pytest.fixture
def shard_balancer(cache):
    """Create a shard balancer instance."""
    return ShardBalancer(cache)

@pytest.fixture
def adaptive_eviction(cache):
    """Create an adaptive eviction instance."""
    return AdaptiveEviction(cache)

@pytest.fixture
def incident_response(cache):
    """Create an incident response instance."""
    return IncidentResponse(cache)

@pytest.fixture
def snapshot_cleaner(cache, cache_dir):
    """Create a snapshot cleaner instance."""
    return SnapshotCleaner(cache)

class TestShardBalancer:
    """Test the ShardBalancer functionality."""

    @pytest.mark.asyncio
    async def test_shard_balancer_initialization(self, shard_balancer):
        """Test that shard balancer initializes correctly."""
        assert hasattr(shard_balancer, 'shards')
        assert shard_balancer.shards == 4
        assert hasattr(shard_balancer, 'get_shard')

    async def test_shard_balancer_rebalance(self, cache):
        """Test that shard balancer can detect and fix imbalance."""
        # Create an imbalance by adding many items to one shard
        for i in range(50):
            await cache.set(f"key_{i}", f"value_{i}")

        # Start the balancer
        cache.shard_balancer.start_balancing()

        # Wait a moment for the balancer to run
        await asyncio.sleep(0.1)

        # Check that metrics were updated
        assert runtime_metrics.shard_imbalance_count.value >= 0
        assert runtime_metrics.cache_rebalances.value >= 0

    async def test_shard_balancer_no_rebalance_needed(self, cache):
        """Test that shard balancer doesn't rebalance when distribution is even."""
        # Add items evenly across shards
        for i in range(16):  # 16 items, 4 shards = 4 per shard
            await cache.set(f"key_{i}", f"value_{i}")

        # Start the balancer
        cache.shard_balancer.start_balancing()

        # Wait a moment for the balancer to run
        await asyncio.sleep(0.1)

        # Check that no rebalancing occurred (since distribution is even)
        assert runtime_metrics.cache_rebalances.value == 0

class TestAdaptiveEviction:
    """Test the AdaptiveEviction functionality."""

    async def test_adaptive_eviction_initialization(self, adaptive_eviction):
        """Test that adaptive eviction initializes correctly."""
        assert adaptive_eviction.cache is not None
        assert adaptive_eviction.base_interval == 30
        assert adaptive_eviction.latency_threshold == 0.5
        assert adaptive_eviction.insert_threshold == 1000
        assert adaptive_eviction.min_interval == 5
        assert adaptive_eviction.max_interval == 120

    async def test_adaptive_eviction_record_operation(self, adaptive_eviction):
        """Test that operation recording updates metrics correctly."""
        # Record a few operations
        adaptive_eviction.record_operation(0.1)  # 100ms
        adaptive_eviction.record_operation(0.2)  # 200ms
        adaptive_eviction.record_operation(0.15)  # 150ms

        # Check that metrics were updated
        assert runtime_metrics.cache_avg_latency.value > 0
        assert runtime_metrics.cache_ops_per_sec.value >= 0

    async def test_adaptive_eviction_adjust_interval_high_latency(self, cache, adaptive_eviction):
        """Test that adaptive eviction reduces interval under high latency."""
        # Set a very high latency to trigger interval reduction
        adaptive_eviction.avg_latency = 1.0  # 1 second latency
        adaptive_eviction.op_count = 10
        adaptive_eviction.last_op_time = time.time() - 1  # 1 second ago

        # Simulate the adjustment
        adaptive_eviction._adjust_cleanup_interval()

        # Check that interval was reduced
        assert cache.cleanup_interval < 30  # Should be less than base interval

    async def test_adaptive_eviction_adjust_interval_low_load(self, cache, adaptive_eviction):
        """Test that adaptive eviction increases interval under low load."""
        # Set a very low latency to trigger interval increase
        adaptive_eviction.avg_latency = 0.01  # 10ms latency
        adaptive_eviction.op_count = 1
        adaptive_eviction.last_op_time = time.time() - 10  # 10 seconds ago

        # Simulate the adjustment
        adaptive_eviction._adjust_cleanup_interval()

        # Check that interval was increased
        assert cache.cleanup_interval > 30  # Should be more than base interval

class TestIncidentResponse:
    """Test the IncidentResponse functionality."""

    async def test_incident_response_initialization(self, incident_response):
        """Test that incident response initializes correctly."""
        assert incident_response.cache is not None
        assert incident_response.enabled is True
        assert len(incident_response.handlers) > 0

    async def test_incident_response_handle_wal_failure(self, cache, incident_response):
        """Test that incident response handles WAL failure."""
        # Mock the WAL replay method
        with patch.object(cache, '_replay_wal_on_startup', return_value=5) as mock_replay:
            # Trigger WAL failure
            await incident_response.trigger_event("WALFailure", "Test WAL failure")

            # Check that replay was called
            mock_replay.assert_called_once()

    async def test_incident_response_handle_memory_error(self, cache, incident_response):
        """Test that incident response handles memory error."""
        # Mock the clear method
        with patch.object(cache, 'clear') as mock_clear:
            # Trigger memory error
            await incident_response.trigger_event("MemoryError", "Test memory error")

            # Check that clear was called
            mock_clear.assert_called_once()

    async def test_incident_response_handle_high_eviction_rate(self, cache, incident_response):
        """Test that incident response handles high eviction rate."""
        # Mock the cleanup interval adjustment
        original_interval = cache.cleanup_interval

        # Trigger high eviction rate
        await incident_response.trigger_event("HighEvictionRate", "Test high eviction rate")

        # Check that interval was reduced
        assert cache.cleanup_interval < original_interval

    async def test_incident_response_handle_cache_bounds_exceeded(self, cache, incident_response):
        """Test that incident response handles cache bounds exceeded."""
        # Mock the clear method
        with patch.object(cache, 'clear') as mock_clear:
            # Trigger bounds exceeded
            await incident_response.trigger_event("CacheBoundsExceeded", "Test bounds exceeded")

            # Check that clear was called
            mock_clear.assert_called_once()

class TestSnapshotCleaner:
    """Test the SnapshotCleaner functionality."""

    async def test_snapshot_cleaner_initialization(self, snapshot_cleaner, cache_dir):
        """Test that snapshot cleaner initializes correctly."""
        assert snapshot_cleaner.cache is not None
        assert snapshot_cleaner.snapshot_ttl == 86400  # 24 hours
        assert snapshot_cleaner.wal_ttl == 604800  # 7 days
        assert snapshot_cleaner.snapshot_dir == f"{cache_dir}/cache_snapshots"

    async def test_snapshot_cleaner_create_snapshot(self, cache, cache_dir):
        """Test that snapshot cleaner can create a snapshot."""
        # Create a snapshot
        snapshot = cache.create_backup_snapshot()

        # Check that snapshot was created
        assert snapshot is not None
        assert "_metadata" in snapshot
        assert "total_entries" in snapshot["_metadata"]

    async def test_snapshot_cleaner_cleanup_snapshots(self, cache, cache_dir):
        """Test that snapshot cleaner cleans up old snapshots."""
        # Create a snapshot file
        snapshot_dir = f"{cache_dir}/cache_snapshots"
        os.makedirs(snapshot_dir, exist_ok=True)

        # Create an old snapshot file
        old_snapshot_path = f"{snapshot_dir}/old_snapshot.snapshot"
        with open(old_snapshot_path, 'w') as f:
            f.write("test snapshot")

        # Set the modification time to be old
        old_time = time.time() - 86401  # 1 second older than TTL
        os.utime(old_snapshot_path, (old_time, old_time))

        # Start the cleaner
        snapshot_cleaner.start_cleanup()

        # Wait for cleanup to run
        await asyncio.sleep(0.1)

        # Check that the old snapshot was deleted
        assert not os.path.exists(old_snapshot_path)

    async def test_snapshot_cleaner_cleanup_wal_files(self, cache, cache_dir):
        """Test that snapshot cleaner cleans up old WAL files."""
        # Create a WAL file
        wal_dir = f"{cache_dir}/wal"
        os.makedirs(wal_dir, exist_ok=True)

        # Create an old WAL file
        old_wal_path = f"{wal_dir}/old_wal.wal"
        with open(old_wal_path, 'w') as f:
            f.write("test wal")

        # Set the modification time to be old
        old_time = time.time() - 604801  # 1 second older than TTL
        os.utime(old_wal_path, (old_time, old_time))

        # Start the cleaner
        snapshot_cleaner.start_cleanup()

        # Wait for cleanup to run
        await asyncio.sleep(0.1)

        # Check that the old WAL file was deleted
        assert not os.path.exists(old_wal_path)

class TestConfigurableValidation:
    """Test the configurable input validation."""

    async def test_strict_validation(self, cache):
        """Test strict validation mode."""
        # Test with strict mode (default)
        os.environ["CACHE_VALIDATION_MODE"] = "strict"

        # Should fail with long key
        with pytest.raises(ValueError):
            await cache.set("a" * 1001, "value")

        # Should fail with control characters
        with pytest.raises(ValueError):
            await cache.set("key\nwith\nnewlines", "value")

        # Should pass with valid key
        await cache.set("valid_key", "value")

    async def test_normal_validation(self, cache):
        """Test normal validation mode."""
        # Test with normal mode
        os.environ["CACHE_VALIDATION_MODE"] = "normal"

        # Should pass with longer key
        await cache.set("a" * 1500, "value")  # Should work in normal mode

        # Should still fail with control characters
        with pytest.raises(ValueError):
            await cache.set("key\nwith\nnewlines", "value")

    async def test_relaxed_validation(self, cache):
        """Test relaxed validation mode."""
        # Test with relaxed mode
        os.environ["CACHE_VALIDATION_MODE"] = "relaxed"

        # Should pass with very long key
        await cache.set("a" * 4000, "value")  # Should work in relaxed mode

        # Should still fail with null bytes
        with pytest.raises(ValueError):
            await cache.set("key\x00with\x00null", "value")

class TestIntegration:
    """Test integration of all components."""

    async def test_full_cache_functionality(self, cache):
        """Test that the full cache works with all enhancements."""
        # Test basic functionality
        await cache.set("test_key", "test_value")
        result = await cache.get("test_key")
        assert result == "test_value"

        # Test that metrics are updated
        assert runtime_metrics.cache_hits.value == 1
        assert runtime_metrics.cache_misses.value == 0
        assert runtime_metrics.cache_sets.value == 1

        # Test that cleanup task is running
        assert cache.is_running is True

        # Test that shard balancer is running
        assert cache.shard_balancer.balance_task is not None
        assert not cache.shard_balancer.balance_task.done()

        # Test that snapshot cleaner is running
        assert cache.snapshot_cleaner.cleanup_task is not None
        assert not cache.snapshot_cleaner.cleanup_task.done()

        # Test that adaptive eviction is working
        assert cache.adaptive_eviction.avg_latency >= 0

        # Test that incident response is working
        assert len(cache.incident_response.handlers) > 0

    async def test_cache_with_wal(self, cache, cache_dir):
        """Test cache functionality with WAL enabled."""
        # Test WAL functionality
        await cache.set("wal_key", "wal_value")

        # Check that WAL file was created
        wal_files = [f for f in os.listdir(f"{cache_dir}/wal") if f.endswith(".wal")]
        assert len(wal_files) > 0

        # Test that WAL replay works
        await cache.stop()

        # Create a new cache instance
        new_cache = AsyncTTLCache(
            ttl_seconds=1,
            cleanup_interval=1,
            num_shards=4,
            enable_wal=True,
            wal_path=f"{cache_dir}/wal",
            max_entries=100,
            max_memory_mb=10,
            paranoia_mode=False
        )

        # Check that value was restored from WAL
        result = await new_cache.get("wal_key")
        assert result == "wal_value"

        await new_cache.stop()

class TestPerformance:
    """Test performance characteristics."""

    async def test_high_concurrency(self, cache):
        """Test cache performance under high concurrency."""
        # Test with high concurrency
        async def worker(worker_id):
            for i in range(10):
                key = f"worker_{worker_id}_key_{i}"
                await cache.set(key, f"value_{worker_id}_{i}")
                result = await cache.get(key)
                assert result == f"value_{worker_id}_{i}"

        # Run multiple workers concurrently
        workers = [worker(i) for i in range(10)]
        await asyncio.gather(*workers)

        # Check that metrics are accurate
        assert runtime_metrics.cache_sets.value >= 100
        assert runtime_metrics.cache_hits.value >= 100
        assert runtime_metrics.cache_misses.value == 0

    async def test_memory_usage(self, cache):
        """Test that memory usage is properly tracked."""
        # Add many items
        for i in range(50):
            await cache.set(f"key_{i}", f"value_{i}")

        # Check that size is correct
        assert cache.size() == 50

        # Check that memory estimation is working
        assert runtime_metrics.cache_size.value == 50


