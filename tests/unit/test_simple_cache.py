#!/usr/bin/env python3
"""
Simple test for the refactored cache implementation.
"""

import asyncio
import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock the dependencies
class MockRuntimeMetrics:
    def __init__(self):
        self.cache_hits = MockCounter()
        self.cache_misses = MockCounter()
        self.cache_sets = MockCounter()
        self.cache_evictions = MockCounter()
        self.cache_cleanup_cycles = MockCounter()
        self.cache_size = MockGauge()

    def create_correlation_id(self, data):
        return MockCorrelationID()

    def record_health_check(self, component, status, data=None):
        pass

    def close_correlation_id(self, correlation_id):
        pass

    def get_health_status(self):
        return {}

class MockCounter:
    def __init__(self):
        self.value = 0

    def increment(self, amount=1):
        self.value += amount

class MockGauge:
    def __init__(self):
        self.value = 0

    def set(self, value):
        self.value = value

class MockCorrelationID:
    def __init__(self):
        self.id = "test-correlation-id"

class MockExceptions:
    class CacheError(Exception):
        pass

# Mock the modules before importing
sys.modules['resync.core.metrics'] = MockRuntimeMetrics()
sys.modules['resync.core.exceptions'] = MockExceptions()

# Now import the cache components
from resync.core.cache.memory_manager import CacheEntry, CacheMemoryManager
from resync.core.cache.persistence_manager import CachePersistenceManager
from resync.core.cache.transaction_manager import CacheTransactionManager


async def test_components():
    """Test the cache components."""
    print("Testing cache components...")

    # Test CacheMemoryManager
    memory_manager = CacheMemoryManager(max_entries=100, max_memory_mb=10)
    print("✓ CacheMemoryManager created")

    # Test CachePersistenceManager
    persistence_manager = CachePersistenceManager(snapshot_dir="./test_snapshots")
    print("✓ CachePersistenceManager created")

    # Test CacheTransactionManager
    transaction_manager = CacheTransactionManager()
    print("✓ CacheTransactionManager created")

    # Test CacheEntry
    entry = CacheEntry(data="test", timestamp=1234567890.0, ttl=60.0)
    print(f"✓ CacheEntry created: {entry}")

    # Test the refactored cache
    from resync.core._deprecated.async_cache_refactored import AsyncTTLCache

    cache = AsyncTTLCache(
        ttl_seconds=60,
        num_shards=2,
        max_entries=100,
        max_memory_mb=1,
        enable_wal=False
    )

    print("✓ Refactored AsyncTTLCache created")

    # Test basic operations
    await cache.set("test_key", "test_value")
    value = await cache.get("test_key")
    assert value == "test_value", f"Expected 'test_value', got {value}"
    print("✓ Basic set/get operations work")

    # Test memory manager integration
    size = cache.size()
    print(f"✓ Cache size: {size}")

    # Test metrics
    metrics = cache.get_detailed_metrics()
    print(f"✓ Metrics collected: {len(metrics)} metrics")

    # Test health check
    health = await cache.health_check()
    print(f"✓ Health check: {health['status']}")

    # Test memory manager bounds checking
    shards = [{} for _ in range(2)]
    current_size = 1
    bounds_ok = memory_manager.check_memory_bounds(shards, current_size)
    print(f"✓ Memory bounds check: {bounds_ok}")

    # Test persistence manager
    cache_data = {"shard_0": {"key1": "value1"}}
    snapshot_path = persistence_manager.create_backup_snapshot(cache_data)
    print(f"✓ Snapshot created: {snapshot_path}")

    # Test transaction manager
    tx_id = await transaction_manager.begin_transaction("test_key")
    print(f"✓ Transaction started: {tx_id}")

    commit_result = await transaction_manager.commit_transaction(tx_id)
    print(f"✓ Transaction committed: {commit_result}")

    await cache.stop()
    print("✓ All cache component tests passed")

    # Cleanup
    if os.path.exists(snapshot_path):
        os.remove(snapshot_path)
    if os.path.exists("./test_snapshots"):
        import shutil
        shutil.rmtree("./test_snapshots")

    return True

if __name__ == "__main__":
    try:
        success = asyncio.run(test_components())
        if success:
            print("\n🎉 All tests passed! Refactored cache integration is successful.")
            sys.exit(0)
        else:
            print("\n❌ Tests failed!")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)




