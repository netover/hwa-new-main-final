"""
Global Health Service Manager

This module provides singleton management for the global health check service,
ensuring thread-safe initialization and proper lifecycle management.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from resync.core.health_models import HealthCheckConfig

logger = structlog.get_logger(__name__)


class GlobalHealthServiceManager:
    """
    Manages the global health check service singleton instance.

    This class implements the async double-checked locking pattern to prevent
    race conditions during singleton initialization while maintaining performance.
    """

    def __init__(self):
        """Initialize the global health service manager."""
        self._health_service: Any | None = None
        self._lock = asyncio.Lock()

    async def get_service(
        self, service_factory_func, config: HealthCheckConfig | None = None
    ) -> Any:
        """
        Get the global health check service instance with thread-safe initialization.

        Args:
            service_factory_func: Function that creates a new service instance
            config: Health check configuration (uses default if None)

        Returns:
            The global health check service instance
        """
        # First check (without lock) for performance
        if self._health_service is not None:
            return self._health_service

        # Acquire lock for thread-safe initialization
        async with self._lock:
            # Second check (with lock) to prevent race condition
            if self._health_service is None:
                logger.info("initializing_global_health_service")
                self._health_service = await service_factory_func(config)
                logger.info("global_health_service_initialized")

        return self._health_service

    async def shutdown_service(self) -> None:
        """
        Shutdown the global health check service gracefully.

        This function ensures proper cleanup of the health check service,
        including stopping monitoring and releasing resources.
        """
        if self._health_service is not None:
            try:
                logger.info("shutting_down_global_health_service")
                await self._health_service.stop_monitoring()
                self._health_service = None
                logger.info("global_health_service_shutdown_completed")
            except Exception as e:
                logger.error("error_during_health_service_shutdown", error=str(e))
                raise
        else:
            logger.debug("health_service_already_shutdown_or_never_initialized")

    def get_current_service(self) -> Any | None:
        """
        Get the current health service instance without initialization.

        Returns:
            Current service instance or None if not initialized
        """
        return self._health_service

    def is_initialized(self) -> bool:
        """
        Check if the global health service has been initialized.

        Returns:
            True if service is initialized, False otherwise
        """
        return self._health_service is not None


# Global instance for application-wide use
_global_health_manager = GlobalHealthServiceManager()


async def get_global_health_service(
    service_factory_func, config: HealthCheckConfig | None = None
) -> Any:
    """
    Convenience function to get the global health service instance.

    Args:
        service_factory_func: Function that creates a new service instance
        config: Health check configuration (uses default if None)

    Returns:
        The global health check service instance
    """
    return await _global_health_manager.get_service(service_factory_func, config)


async def shutdown_global_health_service() -> None:
    """
    Convenience function to shutdown the global health service.
    """
    await _global_health_manager.shutdown_service()


def get_current_global_health_service() -> Any | None:
    """
    Get the current global health service instance without initialization.

    Returns:
        Current service instance or None if not initialized
    """
    return _global_health_manager.get_current_service()


def is_global_health_service_initialized() -> bool:
    """
    Check if the global health service has been initialized.

    Returns:
        True if service is initialized, False otherwise
    """
    return _global_health_manager.is_initialized()
