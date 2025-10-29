"""FastAPI Integration for Dependency Injection

This module provides utilities for integrating the DIContainer with FastAPI's
dependency injection system. It includes functions for creating FastAPI dependencies
that resolve services from the container.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, get_type_hints

from fastapi import FastAPI, Request, Response
from resync.core.agent_manager import AgentManager
from resync.core.audit_queue import AsyncAuditQueue
from resync.core.connection_manager import ConnectionManager
from resync.core.di_container import DIContainer, ServiceLifetime, container
from resync.core.file_ingestor import create_file_ingestor
from resync.core.knowledge_graph import AsyncKnowledgeGraph
from resync.core.teams_integration import TeamsIntegration
from resync_new.config.settings import settings
from resync_new.utils.interfaces import (
    IAgentManager,
    IAuditQueue,
    IConnectionManager,
    IFileIngestor,
    IKnowledgeGraph,
    ITWSClient,
)

# --- Logging Setup ---
from resync_new.utils.simple_logger import get_logger
from starlette.middleware.base import BaseHTTPMiddleware

from resync.services.mock_tws_service import MockTWSClient
from resync.services.tws_service import OptimizedTWSClient

logger = get_logger(__name__)

# --- Type Variables ---
T = TypeVar("T")


def get_tws_client_factory():
    """
    Factory function to create a TWS client based on settings.

    Returns:
        Either a real OptimizedTWSClient or a MockTWSClient.
    """
    if settings.TWS_MOCK_MODE:
        logger.info("TWS_MOCK_MODE is enabled. Creating MockTWSClient.")
        return MockTWSClient()
    logger.info("Creating OptimizedTWSClient.")
    return OptimizedTWSClient(
        hostname=settings.TWS_HOST,
        port=settings.TWS_PORT,
        username=settings.TWS_USER,
        password=settings.TWS_PASSWORD,
        engine_name=settings.TWS_ENGINE_NAME,
        engine_owner=settings.TWS_ENGINE_OWNER,
    )


def get_teams_integration_factory():
    """
    Factory function to create Teams integration service.

    Returns:
        TeamsIntegration service instance.
    """
    logger.info("Creating TeamsIntegration service.")
    # This will create a singleton instance
    return TeamsIntegration()


def configure_container(app_container: DIContainer = container) -> DIContainer:
    """
    Configure the DI container with all service registrations.

    Args:
        app_container: The container to configure (default: global container).

    Returns:
        The configured container.
    """
    try:
        # Register interfaces and implementations
        # Lazy import to avoid circular dependency
        app_container.register(
            IAgentManager, AgentManager, ServiceLifetime.SINGLETON
        )
        app_container.register(
            IConnectionManager, ConnectionManager, ServiceLifetime.SINGLETON
        )
        app_container.register(
            IKnowledgeGraph, AsyncKnowledgeGraph, ServiceLifetime.SINGLETON
        )
        app_container.register(
            IAuditQueue, AsyncAuditQueue, ServiceLifetime.SINGLETON
        )

        # Register TWS client with factory
        app_container.register_factory(
            ITWSClient, get_tws_client_factory, ServiceLifetime.SINGLETON
        )

        # Register Teams integration with factory
        app_container.register_factory(
            TeamsIntegration,
            get_teams_integration_factory,
            ServiceLifetime.SINGLETON,
        )

        # Register FileIngestor - depends on KnowledgeGraph
        # Using a factory function to ensure dependencies are properly resolved
        async def file_ingestor_factory():
            knowledge_graph = await app_container.get(IKnowledgeGraph)
            return create_file_ingestor(knowledge_graph)

        app_container.register_factory(
            IFileIngestor, file_ingestor_factory, ServiceLifetime.SINGLETON
        )

        # Register concrete types (for when concrete type is requested directly)
        app_container.register(
            ConnectionManager, ConnectionManager, ServiceLifetime.SINGLETON
        )
        app_container.register(
            AsyncKnowledgeGraph, AsyncKnowledgeGraph, ServiceLifetime.SINGLETON
        )
        app_container.register(
            AsyncAuditQueue, AsyncAuditQueue, ServiceLifetime.SINGLETON
        )
        app_container.register_factory(
            OptimizedTWSClient,
            get_tws_client_factory,
            ServiceLifetime.SINGLETON,
        )

        logger.info("DI container configured with all service registrations")
    except Exception as e:
        logger.error("error_configuring_di_container", error=str(e))
        raise

    return app_container


def get_service(service_type: type[T]) -> Callable[[], T]:
    """
    Create a FastAPI dependency that resolves a service from the container.

    Args:
        service_type: The type of service to resolve.

    Returns:
        A callable that resolves the service from the container.
    """

    async def _get_service() -> T:
        try:
            return await container.get(service_type)
        except KeyError as exc:
            logger.error(
                "service_not_registered_in_container",
                service_type=service_type.__name__,
            )
            raise RuntimeError(
                f"Required service {service_type.__name__} is not available in the DI container"
            ) from exc
        except Exception as e:
            logger.error(
                "error_resolving_service",
                service_type=service_type.__name__,
                error=str(e),
            )
            raise RuntimeError(
                f"Error resolving service {service_type.__name__}: {str(e)}"
            ) from e

    # Set the return annotation for FastAPI to use
    _get_service.__annotations__ = {"return": service_type}
    return _get_service


# Create specific dependencies for common services
def get_agent_manager() -> IAgentManager:
    """Get the agent manager from the container."""
    return get_service(IAgentManager)()


def get_connection_manager_dependency():
    """Get the connection manager from the container."""
    return get_service(IConnectionManager)()


def get_knowledge_graph_dependency():
    """Get the knowledge graph from the container."""
    return get_service(IKnowledgeGraph)()


def get_audit_queue_dependency():
    """Get the audit queue from the container."""
    return get_service(IAuditQueue)()


def get_tws_client_dependency():
    """Get the TWS client from the container."""
    return get_service(ITWSClient)()


def get_file_ingestor_dependency():
    """Get the file ingestor from the container."""
    return get_service(IFileIngestor)()


def get_teams_integration_dependency():
    """Get the teams integration from the container."""
    return get_service(TeamsIntegration)()


class DIMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures the DI container is properly initialized and
    available for each request.
    """

    def __init__(
        self, app: FastAPI, container_instance: DIContainer = container
    ):
        """
        Initialize the middleware with the application and container.

        Args:
            app: The FastAPI application.
            container_instance: The DI container to use.
        """
        super().__init__(app)
        self.container = container_instance
        logger.info("DIMiddleware initialized")

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """
        Process the request and attach the container to it.

        Args:
            request: The incoming request.
            call_next: The next middleware or route handler.

        Returns:
            The response from the next handler.
        """
        try:
            # Attach the container to the request state
            request.state.container = self.container

            # Continue processing the request
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error("error_in_DIMiddleware_dispatch", error=str(e))
            # Re-raise the exception to be handled by other error handlers
            raise


def inject_container(
    app: FastAPI, container_instance: DIContainer | None = None
) -> None:
    """
    Configure the application to use the DI container.

    This function:
    1. Configures the container with all service registrations
    2. Adds the DIMiddleware to the application

    Args:
        app: The FastAPI application.
        container_instance: The DI container to use (default: global container).
    """
    # Use the provided container or the global one
    container_to_use = container_instance or container

    # Configure the container
    configure_container(container_to_use)

    # Add the middleware
    app.add_middleware(DIMiddleware, container_instance=container_to_use)

    logger.info("DI container injected into FastAPI application")


def with_injection(func: Callable) -> Callable:
    """
    Decorator that injects dependencies into a function from the container.

    This decorator inspects the function's signature and resolves dependencies
    from the container based on type annotations. It now correctly handles
    both synchronous and asynchronous functions.

    Args:
        func: The function to inject dependencies into.

    Returns:
        A wrapper function that resolves dependencies from the container.
    """
    signature = inspect.signature(func)
    parameters = list(signature.parameters.values())
    type_hints = get_type_hints(func)

    async def inject_dependencies(kwargs: dict[str, Any]) -> None:
        """Helper to inject dependencies into kwargs."""
        for param in parameters:
            if param.name in kwargs:
                continue
            if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                continue
            param_type = type_hints.get(param.name, Any)
            try:
                kwargs[param.name] = await container.get(param_type)
            except KeyError:
                if param.default is not param.empty:
                    kwargs[param.name] = param.default

    if inspect.iscoroutinefunction(func):

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            await inject_dependencies(kwargs)
            return await func(*args, **kwargs)

        return async_wrapper

    @wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        # This is a synchronous function, so we need to run the async inject_dependencies
        # function in an event loop.
        async def run_injection():
            await inject_dependencies(kwargs)

        asyncio.run(run_injection())
        return func(*args, **kwargs)

    return sync_wrapper
