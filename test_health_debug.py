#!/usr/bin/env python3
"""
Debug script to test health check functionality directly.
"""

import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_health_calculations():
    """Test health status calculations directly."""
    try:
        # Test imports
        from resync.core.health_models import HealthStatus, ComponentHealth, ComponentType
        from resync.core.health_service import HealthCheckService

        print("OK Imports successful")

        # Create test service
        service = HealthCheckService()

        # Test 1: All healthy components
        components = {
            "comp1": ComponentHealth("comp1", ComponentType.DATABASE, HealthStatus.HEALTHY),
            "comp2": ComponentHealth("comp2", ComponentType.REDIS, HealthStatus.HEALTHY),
        }

        result = service._calculate_overall_status(components)
        expected = HealthStatus.HEALTHY
        print(f"OK Test 1 - All healthy: {result} (expected: {expected})")
        assert result == expected, f"Expected {expected}, got {result}"

        # Test 2: Mixed statuses (degraded)
        components["comp1"] = ComponentHealth("comp1", ComponentType.DATABASE, HealthStatus.DEGRADED)
        result = service._calculate_overall_status(components)
        expected = HealthStatus.DEGRADED
        print(f"OK Test 2 - With degraded: {result} (expected: {expected})")
        assert result == expected, f"Expected {expected}, got {result}"

        # Test 3: With unhealthy component
        components["comp2"] = ComponentHealth("comp2", ComponentType.REDIS, HealthStatus.UNHEALTHY)
        result = service._calculate_overall_status(components)
        expected = HealthStatus.UNHEALTHY
        print(f"OK Test 3 - With unhealthy: {result} (expected: {expected})")
        assert result == expected, f"Expected {expected}, got {result}"

        # Test 4: Empty components
        result = service._calculate_overall_status({})
        expected = HealthStatus.UNKNOWN
        print(f"OK Test 4 - Empty components: {result} (expected: {expected})")
        assert result == expected, f"Expected {expected}, got {result}"

        # Test 5: With unknown status
        components = {
            "comp1": ComponentHealth("comp1", ComponentType.DATABASE, HealthStatus.UNKNOWN),
            "comp2": ComponentHealth("comp2", ComponentType.REDIS, HealthStatus.HEALTHY),
        }
        result = service._calculate_overall_status(components)
        expected = HealthStatus.UNKNOWN  # UNKNOWN should be considered degraded
        print(f"OK Test 5 - With unknown: {result} (expected: {expected})")
        assert result == expected, f"Expected {expected}, got {result}"

        print("\nAll tests passed successfully!")
        return True

    except Exception as e:
        print(f"ERROR Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Running health check tests directly...")
    success = test_health_calculations()
    sys.exit(0 if success else 1)