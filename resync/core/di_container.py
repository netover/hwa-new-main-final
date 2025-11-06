"""Lightweight dependency injection container with async-aware factories."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Type, TypeVar

T = TypeVar("T")


class ServiceScope(Enum):
    """Lifecycle for registered services."""

    SINGLETON = "singleton"
    TRANSIENT = "transient"


@dataclass
class _Provider:
    factory: Callable[[], Any]
    scope: ServiceScope


class DIContainer:
    """Minimal DI container supporting async factories and singleton caching."""

    def __init__(self) -> None:
        self._instances: Dict[Type[Any], Any] = {}
        self._providers: Dict[Type[Any], _Provider] = {}

    # --------------------------------------------------------------------- #
    # Registration helpers
    # --------------------------------------------------------------------- #
    def register_singleton(
        self,
        service_type: Type[T],
        implementation: Type[T] | Callable[[], T] | T,
    ) -> None:
        """Register a concrete implementation as an eager singleton."""
        instance = self._instantiate(implementation)
        self._store_instance(service_type, instance)

    def register_factory(
        self,
        service_type: Type[T],
        factory: Callable[[], Any],
        scope: ServiceScope = ServiceScope.TRANSIENT,
    ) -> None:
        """Register a factory for creating instances on demand."""
        self._providers[service_type] = _Provider(factory=factory, scope=scope)
        if scope == ServiceScope.SINGLETON and service_type in self._instances:
            # Reset cached instance to honour new factory registration.
            self._instances.pop(service_type, None)

    def register_instance(self, service_type: Type[T], instance: T) -> None:
        """Register a pre-built instance."""
        self._store_instance(service_type, instance)

    def register(
        self,
        service_type: Type[T],
        implementation: Type[T] | Callable[[], T] | T,
        scope: ServiceScope = ServiceScope.SINGLETON,
    ) -> None:
        """Backwards compatible registration helper."""
        if scope == ServiceScope.SINGLETON:
            self.register_singleton(service_type, implementation)
        else:
            factory = (
                implementation
                if callable(implementation)
                else lambda: implementation  # type: ignore[return-value]
            )
            self.register_factory(service_type, factory, scope)

    # --------------------------------------------------------------------- #
    # Resolution
    # --------------------------------------------------------------------- #
    async def get(self, service_type: Type[T]) -> T:
        """Resolve a service instance, awaiting async factories when needed."""
        if service_type in self._instances:
            return self._instances[service_type]  # type: ignore[return-value]

        provider = self._providers.get(service_type)
        if provider is None:
            raise KeyError(f"Service {service_type!r} not registered in container")

        result = provider.factory()
        if inspect.isawaitable(result):
            result = await result  # type: ignore[assignment]

        if provider.scope == ServiceScope.SINGLETON:
            self._store_instance(service_type, result)
            return self._instances[service_type]  # type: ignore[return-value]

        return result  # type: ignore[return-value]

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _instantiate(
        self, implementation: Type[T] | Callable[[], T] | T
    ) -> T:
        if inspect.isclass(implementation):
            return implementation()  # type: ignore[call-arg]
        if callable(implementation):
            return implementation()  # type: ignore[call-arg]
        return implementation

    def _store_instance(self, service_type: Type[Any], instance: Any) -> None:
        self._instances[service_type] = instance
        # Also allow lookup by the concrete type.
        self._instances[type(instance)] = instance


# Global default container used throughout the application
container = DIContainer()

__all__ = ["DIContainer", "ServiceScope", "container"]
