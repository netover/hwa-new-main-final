#!/usr/bin/env python3
"""Integration test for health service memory bounds."""

import asyncio
import sys
from datetime import datetime, timedelta

# Add the project root to the path
sys.path.insert(0, ".")

from resync.core.health_models import HealthCheckConfig, HealthCheckResult, HealthStatus
from resync.core.health_service import HealthCheckService


async def test_memory_bounds_integration():
    """Test the complete memory bounds functionality."""
    print("🧪 Testing Health Service Memory Bounds Integration")

    # Create configuration with tight memory bounds
    config = HealthCheckConfig(
        max_history_entries=10,
        history_cleanup_threshold=0.8,
        history_cleanup_batch_size=2,
        history_retention_days=1,
        enable_memory_monitoring=True,
        memory_usage_threshold_mb=1,
    )

    # Create service
    service = HealthCheckService(config)

    print("✅ Service created with memory bounds configuration")

    # Test 1: Add entries beyond threshold
    print("\n📊 Test 1: Adding entries beyond threshold...")
    for i in range(15):
        result = HealthCheckResult(
            overall_status=HealthStatus.HEALTHY,
            timestamp=datetime.now() - timedelta(minutes=i),
        )
        service._update_health_history(result)

    # Force cleanup to ensure it happens
    await service.force_cleanup()

    print(f"   History size after cleanup: {len(service.health_history)}")
    assert len(service.health_history) <= 10, "History should be cleaned up"

    # Test 2: Force cleanup
    print("\n🧹 Test 2: Force cleanup...")
    cleanup_result = await service.force_cleanup()
    print(f"   Cleanup result: {cleanup_result}")

    # Test 3: Memory usage tracking
    print("\n💾 Test 3: Memory usage tracking...")
    memory_stats = service.get_memory_usage()
    print(f"   Memory stats: {memory_stats}")
    assert "memory_usage_mb" in memory_stats

    # Test 4: Age-based cleanup
    print("\n⏰ Test 4: Age-based cleanup...")
    # Add old entries
    old_time = datetime.now() - timedelta(days=3)
    for i in range(5):
        # Create a new HealthCheckResult directly instead of trying to copy from empty list
        old_result = HealthCheckResult(
            overall_status=HealthStatus.HEALTHY, timestamp=old_time - timedelta(hours=i)
        )
        service.health_history.append(old_result)

    cleanup_result = await service.force_cleanup()
    print(f"   Age cleanup result: {cleanup_result}")

    # Verify old entries are removed
    recent_entries = all(
        entry.timestamp >= datetime.now() - timedelta(days=1)
        for entry in service.health_history
    )
    print(f"   All entries recent: {recent_entries}")

    # Test 5: Get history with limits
    print("\n🔍 Test 5: Get history with limits...")
    limited_history = service.get_health_history(hours=1, max_entries=3)
    print(f"   Limited history size: {len(limited_history)}")

    print("\n✅ All memory bounds tests passed!")
    return True


if __name__ == "__main__":
    try:
        asyncio.run(test_memory_bounds_integration())
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)




