from __future__ import annotations

import asyncio
from enum import Enum
from typing import Any, Callable, Dict, TypeVar

# --- Logging Setup ---
from resync.core.structured_logger import get_logger

logger = get_logger(__name__)

# --- Type Variables ---
T = TypeVar("T")
TInterface = TypeVar("TInterface")
TImplementation = TypeVar("TImplementation")


class ServiceLifetime(Enum):
    """Defines the lifecycle scope of a registered service."""

    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"


class ServiceScope:
    """Context manager for scoped service lifetimes."""

    def __init__(self):
        self._services: Dict[type, Any] = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Clean up scoped services
        self._services.clear()

    def get_service(self, interface: type[T]) -> T | None:
        """Get service from current scope."""
        return self._services.get(interface)

    def set_service(self, interface: type[T], instance: T):
        """Set service in current scope."""
        self._services[interface] = instance


class DIContainer:
    """Thread-safe DI container with proper lifecycle management."""

    def __init__(self):
        self._factories: Dict[type, tuple[Callable, ServiceLifetime]] = {}
        self._singletons: Dict[type, Any] = {}
        self._locks: Dict[type, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()
        self.current_scope: ServiceScope | None = None

    def register(
        self,
        interface: type[T],
        factory: Callable[[], T],
        lifetime: ServiceLifetime = ServiceLifetime.SINGLETON,
    ):
        """Register service factory."""
        self._factories[interface] = (factory, lifetime)
        if lifetime == ServiceLifetime.SINGLETON:
            self._locks[interface] = asyncio.Lock()

    def register_instance(self, interface: type[T], instance: T):
        """Register pre-created instance."""
        self._singletons[interface] = instance
        self._factories[interface] = (lambda: instance, ServiceLifetime.SINGLETON)

    def register_factory(
        self,
        interface: type[T],
        factory: Callable[..., T],
        lifetime: ServiceLifetime = ServiceLifetime.SINGLETON,
    ):
        """Register a factory function to create service instances."""
        self._factories[interface] = (factory, lifetime)
        if lifetime == ServiceLifetime.SINGLETON:
            self._locks[interface] = asyncio.Lock()

    async def get(self, interface: type[T]) -> T:
        """
        Resolve service with double-checked locking pattern.
        """
        if interface not in self._factories:
            raise ValueError(f"Service {interface.__name__} not registered")

        factory, lifetime = self._factories[interface]

        if lifetime == ServiceLifetime.SINGLETON:
            # Double-checked locking for singletons
            if interface in self._singletons:
                return self._singletons[interface]

            async with self._locks[interface]:
                # Check again after acquiring lock
                if interface in self._singletons:
                    return self._singletons[interface]

                instance = await self._create_instance(factory)
                self._singletons[interface] = instance
                return instance

        elif lifetime == ServiceLifetime.TRANSIENT:
            # Always create new instance
            return await self._create_instance(factory)

        else:  # SCOPED
            # Get from current scope (request context)
            scope = self._get_current_scope()
            service = scope.get_service(interface)
            if not service:
                service = await self._create_instance(factory)
                scope.set_service(interface, service)
            return service

    async def _create_instance(self, factory: Callable) -> Any:
        """Create instance handling async factories."""
        if asyncio.iscoroutinefunction(factory):
            return await factory()
        return factory()

    def _get_current_scope(self) -> ServiceScope:
        """Get or create scope for current request/context."""
        # Use context vars for scope isolation
        # Implementation depends on your framework
        # For now, return a new dict for each call
        if self.current_scope is None:
            self.current_scope = ServiceScope()
        return self.current_scope


# --- Global Container Instance ---
# This is the default container used by the application.
# It can be replaced with a custom container if needed.
container = DIContainer()


def register_default_services():
    """Register default services with the container."""
    from resync.core.audit_queue import AsyncAuditQueue, IAuditQueue

    container.register(IAuditQueue, AsyncAuditQueue, lifetime=ServiceLifetime.SINGLETON)


def get_container() -> DIContainer:
    """Get the global DI container instance."""
    return container
