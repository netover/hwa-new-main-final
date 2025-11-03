"""Health model shim.

This module exists solely to provide backwards compatibility for code
that imports from ``resync.core.health_models``.  The actual health
data classes and enumerations are defined in ``resync.models.health_models``.
Rather than duplicating those definitions, we re‑export them here.  If
additional helpers are needed in the future, they can also be added.
"""

from resync.models.health_models import (  # noqa: F401
    SystemHealthStatus,
    HealthStatus,
    ComponentType,
    ComponentHealth,
    HealthCheckResult,
    HealthCheckConfig,
    HealthStatusHistory,
    HealthCheckError,
    get_status_color,
    get_status_description,
    RecoveryResult,
)

__all__ = [
    "SystemHealthStatus",
    "HealthStatus",
    "ComponentType",
    "ComponentHealth",
    "HealthCheckResult",
    "HealthCheckConfig",
    "HealthStatusHistory",
    "HealthCheckError",
    "get_status_color",
    "get_status_description",
    "RecoveryResult",
]
