"""
Health Service Manager

This module provides global service management functionality for health services,
including singleton pattern implementation and service lifecycle management.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import structlog

from resync.core.health_models import HealthCheckConfig

from .enhanced_health_service import EnhancedHealthService

# Import the health services
from .health_check_service import HealthCheckService

logger = structlog.get_logger(__name__)


class HealthServiceManager:
    """
    Manages global health service instances with thread-safe singleton pattern.

    This class provides:
    - Thread-safe singleton initialization for health services
    - Service lifecycle management (startup/shutdown)
    - Configuration management for health services
    - Service discovery and access
    """

    def __init__(self):
        """Initialize the health service manager."""
        self._health_check_service: Optional[HealthCheckService] = None
        self._enhanced_health_service: Optional[EnhancedHealthService] = None
        self._service_lock = asyncio.Lock()
        self._initialized = False

    async def initialize_basic_service(
        self, config: Optional[HealthCheckConfig] = None
    ) -> HealthCheckService:
        """
        Initialize and get the basic health check service instance.

        Args:
            config: Optional health check configuration

        Returns:
            HealthCheckService: The global health check service instance
        """
        if self._health_check_service is not None:
            return self._health_check_service

        async with self._service_lock:
            # Double-check pattern for thread safety
            if self._health_check_service is None:
                logger.info("Initializing global basic health check service")
                self._health_check_service = HealthCheckService()
                self._initialized = True
                logger.info("Global basic health check service initialized")

        return self._health_check_service

    async def initialize_enhanced_service(
        self, config: Optional[HealthCheckConfig] = None
    ) -> EnhancedHealthService:
        """
        Initialize and get the enhanced health service instance.

        Args:
            config: Optional health check configuration

        Returns:
            EnhancedHealthService: The global enhanced health service instance
        """
        if self._enhanced_health_service is not None:
            return self._enhanced_health_service

        async with self._service_lock:
            # Double-check pattern for thread safety
            if self._enhanced_health_service is None:
                logger.info("Initializing global enhanced health service")
                self._enhanced_health_service = EnhancedHealthService(config)
                await self._enhanced_health_service.start_monitoring()
                self._initialized = True
                logger.info(
                    "Global enhanced health service initialized and monitoring started"
                )

        return self._enhanced_health_service

    async def get_basic_service(self) -> Optional[HealthCheckService]:
        """
        Get the basic health check service instance.

        Returns:
            HealthCheckService or None if not initialized
        """
        return self._health_check_service

    async def get_enhanced_service(self) -> Optional[EnhancedHealthService]:
        """
        Get the enhanced health service instance.

        Returns:
            EnhancedHealthService or None if not initialized
        """
        return self._enhanced_health_service

    async def shutdown_basic_service(self) -> None:
        """
        Shutdown the basic health check service gracefully.
        """
        if self._health_check_service is not None:
            try:
                logger.info("Shutting down global basic health check service")
                # Note: The basic HealthCheckService doesn't have stop_monitoring method
                # This is a placeholder for future implementation
                self._health_check_service = None
                logger.info("Global basic health check service shutdown completed")
            except Exception as e:
                logger.error(
                    "Error during basic health check service shutdown", error=str(e)
                )
                raise
        else:
            logger.debug(
                "Basic health check service already shutdown or never initialized"
            )

    async def shutdown_enhanced_service(self) -> None:
        """
        Shutdown the enhanced health service gracefully.
        """
        if self._enhanced_health_service is not None:
            try:
                logger.info("Shutting down global enhanced health service")
                await self._enhanced_health_service.stop_monitoring()
                self._enhanced_health_service = None
                logger.info("Global enhanced health service shutdown completed")
            except Exception as e:
                logger.error(
                    "Error during enhanced health service shutdown", error=str(e)
                )
                raise
        else:
            logger.debug(
                "Enhanced health service already shutdown or never initialized"
            )

    async def shutdown_all_services(self) -> None:
        """
        Shutdown all health services gracefully.
        """
        logger.info("Shutting down all health services")

        # Shutdown enhanced service first (it has monitoring)
        await self.shutdown_enhanced_service()

        # Shutdown basic service
        await self.shutdown_basic_service()

        self._initialized = False
        logger.info("All health services shutdown completed")

    def is_initialized(self) -> bool:
        """
        Check if any health service is initialized.

        Returns:
            True if any service is initialized, False otherwise
        """
        return (
            self._initialized
            or (self._health_check_service is not None)
            or (self._enhanced_health_service is not None)
        )

    def get_service_status(self) -> dict:
        """
        Get status of all managed services.

        Returns:
            Dictionary with service status information
        """
        return {
            "initialized": self._initialized,
            "basic_service_active": self._health_check_service is not None,
            "enhanced_service_active": self._enhanced_health_service is not None,
            "service_lock_held": self._service_lock.locked(),
        }


# Global service manager instance
_health_service_manager: Optional[HealthServiceManager] = None
_manager_lock = asyncio.Lock()


async def get_health_service_manager() -> HealthServiceManager:
    """
    Get the global health service manager instance.

    Returns:
        HealthServiceManager: The global health service manager instance
    """
    global _health_service_manager

    if _health_service_manager is not None:
        return _health_service_manager

    async with _manager_lock:
        # Double-check pattern for thread safety
        if _health_service_manager is None:
            logger.info("Creating global health service manager")
            _health_service_manager = HealthServiceManager()
            logger.info("Global health service manager created")

    return _health_service_manager


async def initialize_basic_health_service(
    config: Optional[HealthCheckConfig] = None,
) -> HealthCheckService:
    """
    Initialize and get the basic health check service.

    Args:
        config: Optional health check configuration

    Returns:
        HealthCheckService: The global basic health check service instance
    """
    manager = await get_health_service_manager()
    return await manager.initialize_basic_service(config)


async def initialize_enhanced_health_service(
    config: Optional[HealthCheckConfig] = None,
) -> EnhancedHealthService:
    """
    Initialize and get the enhanced health service.

    Args:
        config: Optional health check configuration

    Returns:
        EnhancedHealthService: The global enhanced health service instance
    """
    manager = await get_health_service_manager()
    return await manager.initialize_enhanced_service(config)


async def get_basic_health_service() -> Optional[HealthCheckService]:
    """
    Get the basic health check service instance if initialized.

    Returns:
        HealthCheckService or None if not initialized
    """
    manager = await get_health_service_manager()
    return await manager.get_basic_service()


async def get_enhanced_health_service() -> Optional[EnhancedHealthService]:
    """
    Get the enhanced health service instance if initialized.

    Returns:
        EnhancedHealthService or None if not initialized
    """
    manager = await get_health_service_manager()
    return await manager.get_enhanced_service()


async def shutdown_all_health_services() -> None:
    """
    Shutdown all health services gracefully.

    This function ensures proper cleanup of all health services,
    including stopping monitoring and releasing resources.
    """
    global _health_service_manager

    if _health_service_manager is not None:
        try:
            await _health_service_manager.shutdown_all_services()
            _health_service_manager = None
            logger.info("Global health service manager shutdown completed")
        except Exception as e:
            logger.error(
                "Error during global health service manager shutdown", error=str(e)
            )
            raise
    else:
        logger.debug("Health service manager already shutdown or never initialized")


def get_service_manager_status() -> dict:
    """
    Get status of the global service manager.

    Returns:
        Dictionary with service manager status
    """
    if _health_service_manager:
        return _health_service_manager.get_service_status()
    else:
        return {
            "initialized": False,
            "basic_service_active": False,
            "enhanced_service_active": False,
            "service_lock_held": False,
        }
