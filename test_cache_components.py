#!/usr/bin/env python3
"""
Simple test for the refactored cache components without full application dependencies.
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_cache_components():
    """Test the cache components directly."""
    print("Testing cache components...")

    try:
        # Test importing individual components
        from resync.core.cache.base_cache import BaseCache
        from resync.core.cache.memory_manager import CacheMemoryManager, CacheEntry
        from resync.core.cache.persistence_manager import CachePersistenceManager
        from resync.core.cache.transaction_manager import CacheTransactionManager

        print("✓ All cache components imported successfully")

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
        from resync.core.cache.async_cache_refactored import AsyncTTLCache

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
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_cache_components())
    sys.exit(0 if success else 1)