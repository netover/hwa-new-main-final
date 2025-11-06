#!/usr/bin/env python3
"""
Simple test for refactored cache components without full application dependencies.
"""

import asyncio
import os
import sys
import traceback

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import components at module level
from resync.core.cache.memory_manager import CacheEntry, CacheMemoryManager
from resync.core.cache.persistence_manager import CachePersistenceManager
from resync.core.cache.transaction_manager import CacheTransactionManager


async def test_cache_components():
    """Test the cache components directly."""
    print("Testing cache components...")

    try:
        print("✓ All cache components imported successfully")

        # Test CacheMemoryManager
        CacheMemoryManager(max_entries=100, max_memory_mb=10)
        print("✓ CacheMemoryManager created")

        # Test CachePersistenceManager
        CachePersistenceManager(snapshot_dir="./test_snapshots")
        print("✓ CachePersistenceManager created")

        # Test CacheTransactionManager
        CacheTransactionManager()
        print("✓ CacheTransactionManager created")

        # Test CacheEntry
        entry = CacheEntry(data="test", timestamp=1234567890.0, ttl=60.0)
        print(f"✓ CacheEntry created: {entry}")

        # Test refactored cache
        from resync.core._deprecated.async_cache_refactored import AsyncTTLCache

        cache = AsyncTTLCache(
            ttl_seconds=60,
            num_shards=2,
            max_entries=100,
            max_memory_mb=1,
            enable_wal=False  # Disable WAL to avoid dependencies
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

        await cache.stop()
        print("✓ All cache component tests passed")

        return True

    except Exception as e:
        print(f"✗ Cache component test failed: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_cache_components())
    sys.exit(0 if success else 1)




