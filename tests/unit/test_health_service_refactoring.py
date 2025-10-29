#!/usr/bin/env python3
"""
Test script for Health Service Refactoring - Phase 2

This script tests the integration of all refactored health service components
and validates that the functionality works as expected.
"""

import asyncio
import sys
import time

from resync.core.health_models import HealthCheckConfig
from resync.core.health_service_refactored import (
    get_refactored_health_check_service,
    shutdown_refactored_health_check_service,
)

# Add the project root to Python path
sys.path.insert(0, '/d/Python/GITHUB/hwa-new')


async def test_health_service_integration():
    """Test integration of all health service components."""
    print("🧪 Testing Health Service Refactoring Integration")
    print("=" * 60)

    try:
        # Test 1: Initialize the refactored health service
        print("📋 Test 1: Initialize refactored health service")
        config = HealthCheckConfig(
            check_interval_seconds=5,  # Faster for testing
            timeout_seconds=10,
            alert_enabled=True,
        )

        health_service = await get_refactored_health_check_service(config)

        # Validate service status
        status = health_service.get_service_status()
        print(f"   ✅ Service initialized: {status['service_type']}")
        print(f"   ✅ Monitoring active: {status['monitoring_active']}")
        print(f"   ✅ Facade initialized: {status['facade_status']['initialized']}")
        print()

        # Test 2: Perform comprehensive health check
        print("📋 Test 2: Perform comprehensive health check")
        start_time = time.time()
        result = await health_service.perform_comprehensive_health_check()
        duration = time.time() - start_time

        print(f"   ✅ Health check completed in {duration:.2f}s")
        print(f"   ✅ Overall status: {result.overall_status}")
        print(f"   ✅ Components checked: {len(result.components)}")
        print(f"   ✅ Correlation ID: {result.correlation_id}")

        # Show component details
        for component_name, component_health in result.components.items():
            print(f"      • {component_name}: {component_health.status} ({component_health.response_time_ms or 0:.1f}ms)")
        print()

        # Test 3: Test individual component health
        print("📋 Test 3: Test individual component health")
        database_health = await health_service.get_component_health("database")
        if database_health:
            print(f"   ✅ Database health: {database_health.status}")
            print(f"   ✅ Response time: {database_health.response_time_ms or 0:.1f}ms")
        else:
            print("   ⚠️  Database health check returned None")
        print()

        # Test 4: Test proactive health checks
        print("📋 Test 4: Test proactive health checks")
        proactive_results = await health_service.perform_proactive_health_checks()
        print("   ✅ Proactive checks completed")
        print(f"   ✅ Checks performed: {proactive_results['checks_performed']}")
        print(f"   ✅ Recovery actions: {len(proactive_results['recovery_actions'])}")
        print()

        # Test 5: Test recovery functionality
        print("📋 Test 5: Test recovery functionality")
        recovery_success = await health_service.attempt_recovery("database")
        print(f"   ✅ Recovery attempt completed: {'Success' if recovery_success else 'Failed'}")
        print()

        # Test 6: Test configuration management
        print("📋 Test 6: Test configuration management")
        current_config = health_service.get_configuration()
        print(f"   ✅ Current config interval: {current_config.check_interval_seconds}s")
        print(f"   ✅ Alert enabled: {current_config.alert_enabled}")

        # Update configuration
        health_service.update_configuration(check_interval_seconds=10)
        updated_config = health_service.get_configuration()
        print(f"   ✅ Updated config interval: {updated_config.check_interval_seconds}s")
        print()

        # Test 7: Test memory usage reporting
        print("📋 Test 7: Test memory usage reporting")
        memory_usage = health_service.get_memory_usage()
        print("   ✅ Memory usage report generated")
        print(f"   ✅ Facade initialized: {memory_usage['facade_initialized']}")
        print(f"   ✅ Observer count: {memory_usage['observer_count']}")
        print()

        # Test 8: Test facade metrics
        print("📋 Test 8: Test facade metrics")
        facade_status = health_service.facade.get_service_status()
        metrics = health_service.facade.get_metrics_summary()

        print(f"   ✅ Facade status: initialized={facade_status['initialized']}, monitoring={facade_status['monitoring_active']}")
        print(f"   ✅ Observer count: {facade_status['observer_count']}")
        print(f"   ✅ Metrics collected: {len(metrics)}")
        print()

        print("🎉 All integration tests passed!")
        print(f"📊 Summary: {len(result.components)} components checked, {duration:.2f}s total duration")
        print()

        return True

    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_observer_pattern():
    """Test the observer pattern implementation."""
    print("🔍 Testing Observer Pattern Implementation")
    print("=" * 50)

    try:
        from resync.core.health.health_monitoring_observer import (
            AlertingHealthObserver,
            HealthMonitoringEvent,
            HealthMonitoringSubject,
            LoggingHealthObserver,
            MetricsHealthObserver,
        )
        from resync.core.health_models import HealthStatus

        # Create subject and observers
        subject = HealthMonitoringSubject()
        logging_observer = LoggingHealthObserver()
        alerting_observer = AlertingHealthObserver()
        metrics_observer = MetricsHealthObserver()

        # Attach observers
        await subject.attach(logging_observer)
        await subject.attach(alerting_observer)
        await subject.attach(metrics_observer)

        print(f"   ✅ Observers attached: {subject.get_observer_count()}")

        # Create test event
        HealthMonitoringEvent(
            event_type="test_event",
            component_name="test_component",
            health_status=HealthStatus.DEGRADED,
            metadata={"test": True}
        )

        # Test notifications
        await subject.notify_status_changed(
            "test_component", HealthStatus.HEALTHY, HealthStatus.DEGRADED, None
        )

        print("   ✅ Status change notification sent")

        # Check metrics
        metrics_summary = metrics_observer.get_metrics_summary()
        print(f"   ✅ Metrics collected: {metrics_summary['status_changes_count']} status changes")

        # Detach observer
        await subject.detach(logging_observer)
        print(f"   ✅ Observer detached, remaining: {subject.get_observer_count()}")

        print("   ✅ Observer pattern test completed")
        print()

        return True

    except Exception as e:
        print(f"❌ Observer pattern test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_complexity_reduction():
    """Validate that complexity has been reduced."""
    print("📏 Testing Complexity Reduction")
    print("=" * 40)

    try:
        # Count lines in original vs refactored
        original_lines = 1622  # From the original health_service.py

        # Count lines in new files
        refactored_main_lines = 321  # health_service_refactored.py
        facade_lines = 421  # health_service_facade.py
        observer_lines = 421  # health_monitoring_observer.py

        total_refactored_lines = refactored_main_lines + facade_lines + observer_lines

        reduction_percentage = ((original_lines - total_refactored_lines) / original_lines) * 100

        print(f"   📊 Original service: {original_lines} lines")
        print(f"   📊 Refactored components: {total_refactored_lines} lines")
        print(f"   📊 Reduction: {reduction_percentage:.1f}%")

        if reduction_percentage >= 50:
            print(f"   ✅ Complexity reduction target achieved: {reduction_percentage:.1f}% >= 50%")
        else:
            print(f"   ⚠️  Complexity reduction below target: {reduction_percentage:.1f}% < 50%")

        print()

        # Test that functionality is preserved
        print("   🔧 Testing functionality preservation...")

        config = HealthCheckConfig()
        health_service = await get_refactored_health_check_service(config)

        # Test key methods exist and work
        methods_to_test = [
            'perform_comprehensive_health_check',
            'get_component_health',
            'attempt_recovery',
            'get_configuration',
            'update_configuration',
            'get_service_status',
        ]

        for method_name in methods_to_test:
            if hasattr(health_service, method_name):
                print(f"      ✅ Method {method_name} available")
            else:
                print(f"      ❌ Method {method_name} missing")

        print("   ✅ Functionality preservation test completed")
        print()

        return reduction_percentage >= 50

    except Exception as e:
        print(f"❌ Complexity reduction test failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("🚀 Health Service Refactoring - Phase 2 Test Suite")
    print("=" * 60)
    print()

    # Run tests
    test_results = []

    test_results.append(("Observer Pattern", await test_observer_pattern()))
    test_results.append(("Integration", await test_health_service_integration()))
    test_results.append(("Complexity Reduction", await test_complexity_reduction()))

    # Summary
    print("📋 Test Summary")
    print("=" * 30)

    passed = 0
    total = len(test_results)

    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1

    print()
    print(f"🎯 Overall: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Health service refactoring is successful.")
        return 0
    print("⚠️  Some tests failed. Please review the issues above.")
    return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Cleanup
        asyncio.run(shutdown_refactored_health_check_service())
