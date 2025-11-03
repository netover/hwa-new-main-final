"""
Simplified Health Service Manager

This module provides a simplified health service manager that maintains API compatibility
while removing circuit breakers and thread pools. It uses pure asyncio for concurrency.
"""

from __future__ import annotations

import asyncio

import structlog

# Import the simplified health service
from .health_service_simplified import SimplifiedHealthService

logger = structlog.get_logger(__name__)


class SimplifiedHealthServiceManager:
    """
    Simplified health service manager without circuit breakers or thread pools.

    This class provides:
    - Singleton pattern for health service instances
    - Service lifecycle management (startup/shutdown)
    - Configuration management for health services
    - Pure asyncio implementation (no thread pools)
    """

    def __init__(self):
        """Initialize the simplified health service manager."""
        self._health_service: SimplifiedHealthService | None = None
        self._service_lock = asyncio.Lock()
        self._initialized = False

    async def initialize_service(self) -> SimplifiedHealthService:
        """
        Initialize and get simplified health service instance.

        Returns:
            SimplifiedHealthService: The global health service instance
        """
        if self._health_service is not None:
            return self._health_service

        async with self._service_lock:
            # Double-check pattern for thread safety
            if self._health_service is None:
                logger.info("Initializing global simplified health service")
                self._health_service = SimplifiedHealthService()
                await self._health_service.start_monitoring()
                self._initialized = True
                logger.info(
                    "Global simplified health service initialized and monitoring started"
                )

        return self._health_service

    async def get_service(self) -> SimplifiedHealthService | None:
        """
        Get the simplified health service instance.

        Returns:
            SimplifiedHealthService or None if not initialized
        """
        return self._health_service

    async def shutdown_service(self) -> None:
        """
        Shutdown the simplified health service gracefully.
        """
        if self._health_service is not None:
            try:
                logger.info("Shutting down global simplified health service")
                await self._health_service.stop_monitoring()
                self._health_service = None
                logger.info(
                    "Global simplified health service shutdown completed"
                )
            except Exception as e:
                logger.error(
                    "Error during simplified health service shutdown",
                    error=str(e),
                )
                raise
        else:
            logger.debug(
                "Simplified health service already shutdown or never initialized"
            )

    def is_initialized(self) -> bool:
        """
        Check if the health service is initialized.

        Returns:
            True if service is initialized, False otherwise
        """
        return self._initialized or (self._health_service is not None)

    def get_service_status(self) -> dict:
        """
        Get status of the managed service.

        Returns:
            Dictionary with service status information
        """
        return {
            "initialized": self._initialized,
            "service_active": self._health_service is not None,
            "service_lock_held": self._service_lock.locked(),
        }


# Global service manager instance
_health_service_manager: SimplifiedHealthServiceManager | None = None
_manager_lock = asyncio.Lock()


async def get_simplified_health_service_manager() -> (
    SimplifiedHealthServiceManager
):
    """
    Get the global simplified health service manager instance.

    Returns:
        SimplifiedHealthServiceManager: The global health service manager instance
    """
    global _health_service_manager
    if _health_service_manager is not None:
        return _health_service_manager

    async with _manager_lock:
        # Double-check pattern for thread safety
        if _health_service_manager is not None:
            return _health_service_manager

        # Create new instance
        _health_service_manager = SimplifiedHealthServiceManager()
        return _health_service_manager


async def initialize_simplified_health_service() -> SimplifiedHealthService:
    """
    Initialize and get the simplified health service.

    Returns:
        SimplifiedHealthService: The global simplified health service instance
    """
    manager = await get_simplified_health_service_manager()
    return await manager.initialize_service()


async def get_simplified_health_service() -> SimplifiedHealthService | None:
    """
    Get the simplified health service instance if initialized.

    Returns:
        SimplifiedHealthService or None if not initialized
    """
    manager = await get_simplified_health_service_manager()
    return await manager.get_service()


async def shutdown_simplified_health_service() -> None:
    """
    Shutdown simplified health service gracefully.

    This function ensures proper cleanup of health service,
    including stopping monitoring and releasing resources.
    """
    global _health_service_manager

    if _health_service_manager is not None:
        await _health_service_manager.shutdown()
        _health_service_manager = None
        logger.info("Simplified health service shutdown completed")


def get_simplified_service_manager_status() -> dict:
    """
    Get status of the global simplified service manager.

    Returns:
        Dictionary with service manager status
    """
    if _health_service_manager:
        return _health_service_manager.get_service_status()
    return {
        "initialized": False,
        "service_active": False,
        "service_lock_held": False,
    }




