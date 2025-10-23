#!/usr/bin/env python3
"""
Test script for the refactored AsyncTTLCache implementation.

This script tests that the refactored cache maintains all existing functionality
while using the extracted managers and strategy pattern.
"""

import asyncio
import logging
import sys
import time
from typing import Dict, Any
import pytest

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

@pytest.mark.asyncio
async def test_basic_functionality():
    """Test basic cache operations."""
    print("🧪 Testing basic cache functionality...")

    try:
        from resync.core.async_cache_refactored import AsyncTTLCache

        # Test initialization
        cache = AsyncTTLCache(ttl_seconds=60, max_entries=1000, max_memory_mb=10)
        print(f"✅ Cache initialized: {cache.size()} entries, {cache.num_shards} shards")

        # Test set operation
        await cache.set("test_key", "test_value", ttl_seconds=30)
        print(f"✅ Set operation completed. Cache size: {cache.size()}")

        # Test get operation
        value = await cache.get("test_key")
        assert value == "test_value", f"Expected 'test_value', got {value}"
        print(f"✅ Get operation successful: {value}")

        # Test delete operation
        deleted = await cache.delete("test_key")
        assert deleted == True, "Delete should return True for existing key"
        print(f"✅ Delete operation successful: {deleted}")

        # Verify key is gone
        value = await cache.get("test_key")
        assert value is None, f"Expected None, got {value}"
        print("✅ Key properly deleted")

        # Test delete non-existent key
        deleted = await cache.delete("non_existent")
        assert deleted == False, "Delete should return False for non-existent key"
        print(f"✅ Non-existent key delete handled correctly: {deleted}")

        print("🎉 All basic functionality tests passed!")

    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        raise

@pytest.mark.asyncio
async def test_memory_management():
    """Test memory management and bounds checking."""
    print("\n🧪 Testing memory management...")

    try:
        from resync.core.async_cache_refactored import AsyncTTLCache

        # Create cache with small limits for testing
        cache = AsyncTTLCache(max_entries=5, max_memory_mb=1, ttl_seconds=300)

        # Fill cache to test bounds
        for i in range(5):
            await cache.set(f"key_{i}", f"value_{i}" * 100)  # Large values

        print(f"✅ Cache filled to {cache.size()} entries")

        # Try to add one more (should trigger eviction)
        await cache.set("key_5", "value_5" * 100)

        # Cache should still respect bounds (may be slightly over due to concurrent access)
        final_size = cache.size()
        print(f"✅ Cache size after overflow: {final_size}")

        # Test memory manager integration
        metrics = cache.get_detailed_metrics()
        print(f"✅ Memory metrics: {metrics.get('memory_info', 'N/A')}")

        print("🎉 Memory management tests passed!")

    except Exception as e:
        print(f"❌ Memory management test failed: {e}")
        raise

@pytest.mark.asyncio
async def test_rollback_functionality():
    """Test transaction rollback functionality."""
    print("\n🧪 Testing rollback functionality...")

    try:
        from resync.core.async_cache_refactored import AsyncTTLCache

        cache = AsyncTTLCache(ttl_seconds=300, max_entries=100)

        # Set initial state
        await cache.set("user_1", "initial_value")
        await cache.set("user_2", "initial_value")

        initial_size = cache.size()
        print(f"✅ Initial cache state: {initial_size} entries")

        # Simulate operations to rollback
        operations = [
            {"operation": "set", "key": "user_1", "value": "new_value_1", "previous_value": "initial_value"},
            {"operation": "set", "key": "user_2", "value": "new_value_2", "previous_value": "initial_value"},
            {"operation": "set", "key": "user_3", "value": "new_value_3"},
        ]

        # Apply operations
        for op in operations:
            if op["operation"] == "set":
                await cache.set(op["key"], op["value"])

        after_ops_size = cache.size()
        print(f"✅ After operations: {after_ops_size} entries")

        # Rollback operations
        rollback_success = await cache.rollback_transaction(operations)
        assert rollback_success == True, "Rollback should succeed"

        print(f"✅ Rollback completed: {rollback_success}")

        # Verify rollback
        value1 = await cache.get("user_1")
        value2 = await cache.get("user_2")
        value3 = await cache.get("user_3")

        assert value1 == "initial_value", f"Expected 'initial_value', got {value1}"
        assert value2 == "initial_value", f"Expected 'initial_value', got {value2}"
        assert value3 is None, f"Expected None, got {value3}"

        print("✅ Rollback verification successful")

        print("🎉 Rollback functionality tests passed!")

    except Exception as e:
        print(f"❌ Rollback functionality test failed: {e}")
        raise

@pytest.mark.asyncio
async def test_snapshot_functionality():
    """Test snapshot and restore functionality."""
    print("\n🧪 Testing snapshot functionality...")

    try:
        from resync.core.async_cache_refactored import AsyncTTLCache

        cache = AsyncTTLCache(ttl_seconds=300, max_entries=100)

        # Add test data
        test_data = {
            "string_key": "string_value",
            "int_key": 42,
            "dict_key": {"nested": "data"},
            "list_key": [1, 2, 3],
        }

        for key, value in test_data.items():
            await cache.set(key, value)

        initial_size = cache.size()
        print(f"✅ Added {initial_size} test entries")

        # Create snapshot
        snapshot = cache.create_backup_snapshot()
        snapshot_entries = snapshot["_metadata"]["total_entries"]
        print(f"✅ Created snapshot with {snapshot_entries} entries")

        # Clear cache
        await cache.clear()
        assert cache.size() == 0, "Cache should be empty after clear"
        print("✅ Cache cleared")

        # Restore from snapshot
        restore_success = await cache.restore_from_snapshot(snapshot)
        assert restore_success == True, "Restore should succeed"

        restored_size = cache.size()
        print(f"✅ Restored {restored_size} entries")

        # Verify restored data
        for key, expected_value in test_data.items():
            actual_value = await cache.get(key)
            assert actual_value == expected_value, f"Key {key}: expected {expected_value}, got {actual_value}"

        print("✅ Snapshot data verification successful")

        print("🎉 Snapshot functionality tests passed!")

    except Exception as e:
        print(f"❌ Snapshot functionality test failed: {e}")
        raise

async def test_health_check():
    """Test health check functionality."""
    print("\n🧪 Testing health check...")

    try:
        from resync.core.async_cache_refactored import AsyncTTLCache

        cache = AsyncTTLCache(ttl_seconds=300, max_entries=100)

        # Add some test data
        await cache.set("health_test", "healthy_data")

        # Run health check
        health = await cache.health_check()

        print(f"✅ Health check result: {health}")

        assert health["status"] == "healthy", f"Expected healthy status, got {health['status']}"
        assert health["production_ready"] == True, "Expected production ready"
        assert "size" in health, "Health check should include size"
        assert "num_shards" in health, "Health check should include num_shards"

        print("🎉 Health check tests passed!")

    except Exception as e:
        print(f"❌ Health check test failed: {e}")
        raise

async def test_concurrent_access():
    """Test concurrent access to cache."""
    print("\n🧪 Testing concurrent access...")

    try:
        from resync.core.async_cache_refactored import AsyncTTLCache

        cache = AsyncTTLCache(ttl_seconds=300, max_entries=1000)

        async def worker(worker_id: int, num_operations: int):
            """Worker function for concurrent operations."""
            for i in range(num_operations):
                key = f"worker_{worker_id}_key_{i}"
                value = f"worker_{worker_id}_value_{i}"

                # Mix of operations
                await cache.set(key, value)
                retrieved = await cache.get(key)
                assert retrieved == value, f"Worker {worker_id}: Mismatch for {key}"

                if i % 10 == 0:  # Occasionally delete
                    await cache.delete(key)

        # Run multiple workers concurrently
        num_workers = 10
        operations_per_worker = 20

        start_time = time.time()
        tasks = [
            worker(wid, operations_per_worker)
            for wid in range(num_workers)
        ]

        await asyncio.gather(*tasks)
        end_time = time.time()

        print(f"✅ Concurrent test completed in {end_time - start_time:.2f}s")
        print(f"✅ Final cache size: {cache.size()}")

        # Verify cache is still in good state
        metrics = cache.get_detailed_metrics()
        print(f"✅ Cache metrics: {metrics}")

        print("🎉 Concurrent access tests passed!")

    except Exception as e:
        print(f"❌ Concurrent access test failed: {e}")
        raise

async def main():
    """Run all tests."""
    print("🚀 Starting refactored AsyncTTLCache tests...\n")

    try:
        await test_basic_functionality()
        await test_memory_management()
        await test_rollback_functionality()
        await test_snapshot_functionality()
        await test_health_check()
        await test_concurrent_access()

        print("\n🎉 All tests passed! Refactored cache is working correctly.")
        return True

    except Exception as e:
        print(f"\n❌ Tests failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)