"""Dependency Injection Container.

This module provides a minimal dependency injection container implementation
to resolve import issues in the application.
"""

from typing import Any, Dict, TypeVar, Type, Optional
from enum import Enum

T = TypeVar("T")


class ServiceLifetime(Enum):
    """Service lifetime enumeration."""
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"


class DIContainer:
    """
    Simple dependency injection container with basic lifetime support.

    The container supports registering singletons, factory functions and
    pre‑instantiated instances.  For backward compatibility it also accepts
    a `register` method similar to more advanced DI frameworks.  Lifetime
    values are ignored in this minimal implementation – singletons are
    instantiated once and factories are invoked on every request.
    """

    def __init__(self) -> None:
        # Mapping from interface to either an instance or a type/factory.
        self._instances: Dict[Type, Any] = {}
        self._providers: Dict[Type, callable] = {}

    def register_singleton(self, service_type: Type[T], implementation: Type[T]) -> None:
        """
        Register a concrete implementation as a singleton.  The class is
        instantiated immediately and reused for all requests.
        """
        # Instantiate eagerly to ensure consistent state.
        self._instances[service_type] = implementation()  # type: ignore[arg-type]

    def register_factory(self, service_type: Type[T], factory: callable) -> None:
        """
        Register a factory function for a service.  The factory will be
        invoked each time the service is requested.
        """
        self._providers[service_type] = factory

    def register_instance(self, service_type: Type[T], instance: T) -> None:
        """Register a pre‑constructed instance for a service."""
        self._instances[service_type] = instance

    # Backwards‑compatible registration method supporting a lifetime argument.
    def register(self, service_type: Type[T], implementation: Type[T], *args, **kwargs) -> None:
        """
        Register a service with an optional lifetime.  In this simple
        container, the lifetime argument is ignored and treated as a
        singleton registration.
        """
        self.register_singleton(service_type, implementation)

    def get(self, service_type: Type[T]) -> Optional[T]:
        """
        Retrieve a service instance.  If a singleton or instance is
        registered, it will be returned.  Otherwise the factory will be
        invoked to create a new instance.  The return value may be a
        coroutine; callers are responsible for awaiting it when needed.
        """
        if service_type in self._instances:
            return self._instances[service_type]  # type: ignore[return-value]
        if service_type in self._providers:
            return self._providers[service_type]()  # type: ignore[return-value]
        return None


# Global container instance
container = DIContainer()
