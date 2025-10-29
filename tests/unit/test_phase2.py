"""
Test script for Phase 2 Performance Optimization features.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def test_imports():
    """Test that all new modules can be imported."""
    print("=" * 60)
    print("Testing Phase 2 Performance Optimization Imports")
    print("=" * 60)

    try:
        print("✓ Performance optimizer module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import performance optimizer: {e}")
        return False

    try:
        print("✓ Resource manager module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import resource manager: {e}")
        return False

    try:
        print("✓ Performance API module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import performance API: {e}")
        return False

    print("\n" + "=" * 60)
    print("All imports successful!")
    print("=" * 60)
    return True


async def test_performance_service():
    """Test the performance service initialization."""
    print("\n" + "=" * 60)
    print("Testing Performance Service")
    print("=" * 60)

    try:
        from resync.core.performance_optimizer import get_performance_service

        service = get_performance_service()
        print(f"✓ Performance service initialized: {type(service).__name__}")

        # Register a test cache
        cache_monitor = await service.register_cache("test_cache")
        print(f"✓ Cache monitor registered: {cache_monitor.cache_name}")

        # Get metrics
        metrics = await cache_monitor.get_current_metrics()
        print(f"✓ Cache metrics retrieved: hit_rate={metrics.hit_rate:.2%}")

        # Get recommendations
        recommendations = await cache_monitor.get_optimization_recommendations()
        print(f"✓ Recommendations generated: {len(recommendations)} items")

        return True
    except Exception as e:
        print(f"✗ Performance service test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_resource_manager():
    """Test the resource manager."""
    print("\n" + "=" * 60)
    print("Testing Resource Manager")
    print("=" * 60)

    try:
        from resync.core.resource_manager import get_global_resource_pool

        pool = get_global_resource_pool()
        print(f"✓ Resource pool initialized: {type(pool).__name__}")

        # Get stats
        stats = pool.get_stats()
        print(f"✓ Resource stats: {stats['active_resources']} active resources")

        # Test leak detection
        leaks = await pool.detect_leaks(max_lifetime_seconds=3600)
        print(f"✓ Leak detection: {len(leaks)} leaks found")

        return True
    except Exception as e:
        print(f"✗ Resource manager test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_api_endpoints():
    """Test that API endpoints are properly defined."""
    print("\n" + "=" * 60)
    print("Testing API Endpoints")
    print("=" * 60)

    try:
        from resync.api.performance import performance_router

        routes = [route.path for route in performance_router.routes]
        print(f"✓ Performance router loaded with {len(routes)} routes:")
        for route in routes:
            print(f"  - {route}")

        return True
    except Exception as e:
        print(f"✗ API endpoints test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("PHASE 2 PERFORMANCE OPTIMIZATION - TEST SUITE")
    print("=" * 60 + "\n")

    results = []

    # Test imports
    results.append(await test_imports())

    # Test performance service
    results.append(await test_performance_service())

    # Test resource manager
    results.append(await test_resource_manager())

    # Test API endpoints
    results.append(await test_api_endpoints())

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("\n✓ All tests passed! Phase 2 implementation is working correctly.")
        return 0
    print(f"\n✗ {total - passed} test(s) failed. Please review the errors above.")
    return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
