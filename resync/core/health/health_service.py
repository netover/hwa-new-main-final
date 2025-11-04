"""Compatibility wrapper exposing consolidated health service helpers."""

from __future__ import annotations

from resync.core.health.health_service_consolidated import (
    get_consolidated_health_service as _get_consolidated_health_service,
)

__all__ = ["get_consolidated_health_service"]


async def get_consolidated_health_service():
    """Return the singleton consolidated health service instance."""
    return await _get_consolidated_health_service()
