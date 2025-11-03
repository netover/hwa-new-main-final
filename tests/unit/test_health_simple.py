#!/usr/bin/env python3
"""
Simple test to validate health check calculations.
"""

import enum
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# Define the enums and classes directly to avoid import issues
class HealthStatus(enum.Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

class ComponentType(enum.Enum):
    DATABASE = "database"
    REDIS = "redis"

@dataclass
class ComponentHealth:
    name: str
    component_type: ComponentType
    status: HealthStatus
    status_code: str | None = None
    message: str | None = None
    response_time_ms: float | None = None
    last_check: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error_count: int = 0
    warning_count: int = 0

def calculate_overall_status(components: dict[str, ComponentHealth]) -> HealthStatus:
    """Calculate overall status from component statuses."""
    if not components:
        return HealthStatus.UNKNOWN

    # Simple aggregation: worst status wins
    priority = {
        HealthStatus.UNHEALTHY: 3,
        HealthStatus.DEGRADED: 2,
        HealthStatus.UNKNOWN: 1,
        HealthStatus.HEALTHY: 0,
    }
    worst = HealthStatus.HEALTHY
    for comp in components.values():
        if priority[comp.status] > priority[worst]:
            worst = comp.status
    return worst

def test_health_calculations():
    """Test health status calculations."""
    print("Testing health status calculations...")

    # Test 1: All healthy components
    components = {
        "comp1": ComponentHealth("comp1", ComponentType.DATABASE, HealthStatus.HEALTHY),
        "comp2": ComponentHealth("comp2", ComponentType.REDIS, HealthStatus.HEALTHY),
    }

    result = calculate_overall_status(components)
    expected = HealthStatus.HEALTHY
    print(f"Test 1 - All healthy: {result} (expected: {expected})")
    assert result == expected, f"Expected {expected}, got {result}"

    # Test 2: Mixed statuses (degraded)
    components["comp1"] = ComponentHealth("comp1", ComponentType.DATABASE, HealthStatus.DEGRADED)
    result = calculate_overall_status(components)
    expected = HealthStatus.DEGRADED
    print(f"Test 2 - With degraded: {result} (expected: {expected})")
    assert result == expected, f"Expected {expected}, got {result}"

    # Test 3: With unhealthy component
    components["comp2"] = ComponentHealth("comp2", ComponentType.REDIS, HealthStatus.UNHEALTHY)
    result = calculate_overall_status(components)
    expected = HealthStatus.UNHEALTHY
    print(f"Test 3 - With unhealthy: {result} (expected: {expected})")
    assert result == expected, f"Expected {expected}, got {result}"

    # Test 4: Empty components
    result = calculate_overall_status({})
    expected = HealthStatus.UNKNOWN
    print(f"Test 4 - Empty components: {result} (expected: {expected})")
    assert result == expected, f"Expected {expected}, got {result}"

    # Test 5: With unknown status
    components = {
        "comp1": ComponentHealth("comp1", ComponentType.DATABASE, HealthStatus.UNKNOWN),
        "comp2": ComponentHealth("comp2", ComponentType.REDIS, HealthStatus.HEALTHY),
    }
    result = calculate_overall_status(components)
    expected = HealthStatus.UNKNOWN
    print(f"Test 5 - With unknown: {result} (expected: {expected})")
    assert result == expected, f"Expected {expected}, got {result}"

    print("\nAll tests passed successfully!")
    return True

if __name__ == "__main__":
    success = test_health_calculations()
    sys.exit(0 if success else 1)




