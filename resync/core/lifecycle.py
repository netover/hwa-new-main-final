"""
Manages the application's lifespan events (startup and shutdown).

This module is responsible for initializing and closing resources such as
database connections, background tasks, and service clients.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from fastapi import FastAPI

from resync.core.connection_pool_manager import (
    get_connection_pool_manager,
    shutdown_connection_pool_manager,
)
from resync.core.container import app_container
from resync.core.interfaces import IAgentManager, IKnowledgeGraph, ITWSClient

logger = logging.getLogger(__name__)


class ResourceManager:
    """
    Centralized resource manager to track and manage all application resources.
    """

    def __init__(self):
        self._resources: Dict[str, Any] = {}
        self._cleanup_tasks: List[callable] = []

    def register_resource(
        self, name: str, resource: Any, cleanup_func: callable = None
    ):
        """
        Register a resource with an optional cleanup function.

        Args:
            name: Name of the resource
            resource: The resource object
            cleanup_func: Function to call for cleanup (resource will be passed as argument)
        """
        self._resources[name] = resource

        if cleanup_func:
            self._cleanup_tasks.append(lambda: cleanup_func(resource))

    def get_resource(self, name: str):
        """
        Get a registered resource.

        Args:
            name: Name of the resource to retrieve

        Returns:
            The registered resource or None if not found
        """
        return self._resources.get(name)

    async def cleanup_all(self):
        """
        Clean up all registered resources in reverse order to handle dependencies properly.
        """
        logger.info(f"Starting cleanup of {len(self._cleanup_tasks)} resources")

        # Execute cleanup tasks in reverse order (last in, first out)
        for cleanup_task in reversed(self._cleanup_tasks):
            try:
                result = cleanup_task()
                # If the cleanup task returns a coroutine, await it
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Error during resource cleanup: {e}", exc_info=True)

        # Clear all registered resources and cleanup tasks
        self._resources.clear()
        self._cleanup_tasks.clear()

        logger.info("Resource cleanup completed")


# Global resource manager instance
resource_manager = ResourceManager()


async def validate_runtime_config() -> dict:
    """
    Validates the runtime configuration and returns validation results.

    Returns:
        dict: Validation results with status and any issues found
    """
    try:
        # Check if all required services are properly configured
        validation_results = {"status": "valid", "issues": [], "services": {}}

        # Validate agent manager
        try:
            await app_container.get(IAgentManager)
            validation_results["services"]["agent_manager"] = "configured"
        except Exception as e:
            validation_results["services"]["agent_manager"] = f"error: {str(e)}"
            validation_results["issues"].append(
                f"Agent manager configuration error: {str(e)}"
            )

        # Validate TWS client
        try:
            await app_container.get(ITWSClient)
            validation_results["services"]["tws_client"] = "configured"
        except Exception as e:
            validation_results["services"]["tws_client"] = f"error: {str(e)}"
            validation_results["issues"].append(
                f"TWS client configuration error: {str(e)}"
            )

        # Validate knowledge graph
        try:
            await app_container.get(IKnowledgeGraph)
            validation_results["services"]["knowledge_graph"] = "configured"
        except Exception as e:
            validation_results["services"]["knowledge_graph"] = f"error: {str(e)}"
            validation_results["issues"].append(
                f"Knowledge graph configuration error: {str(e)}"
            )

        # Update overall status based on issues
        if validation_results["issues"]:
            validation_results["status"] = "invalid"
        else:
            validation_results["status"] = "valid"

        return validation_results

    except Exception as e:
        logger.error(f"Runtime configuration validation failed: {e}", exc_info=True)
        return {
            "status": "error",
            "issues": [f"Validation system error: {str(e)}"],
            "services": {},
        }


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    """
    # --- Startup ---
    logger.info("Application startup: Initializing services...")

    # Import here to avoid circular imports
    from resync.core.audit_queue import migrate_from_sqlite

    # Run the migration from SQLite to Redis if needed
    try:
        await migrate_from_sqlite()
        logger.info("Audit queue migration completed.")
    except Exception as e:
        logger.error(f"Error during audit queue migration: {e}", exc_info=True)
        # Continue startup even if migration fails

    # Initialize connection pool manager
    try:
        connection_pool_manager = await get_connection_pool_manager()
        # Register with resource manager
        resource_manager.register_resource(
            "connection_pool_manager",
            connection_pool_manager,
            lambda r: asyncio.create_task(shutdown_connection_pool_manager()),
        )
        logger.info("Connection pool manager initialized and registered.")
    except Exception as e:
        logger.error(
            f"Failed to initialize connection pool manager: {e}", exc_info=True
        )
        # Continue startup even if connection pools fail to initialize

    # Initialize agent manager
    agent_manager = await app_container.get(IAgentManager)
    resource_manager.register_resource("agent_manager", agent_manager)
    await agent_manager.load_agents_from_config()

    # Initialize TWS client and register with resource manager
    tws_client = await app_container.get(ITWSClient)
    resource_manager.register_resource("tws_client", tws_client)

    # Initialize knowledge graph and register with resource manager
    knowledge_graph = await app_container.get(IKnowledgeGraph)
    resource_manager.register_resource("knowledge_graph", knowledge_graph)

    logger.info("Application startup complete.")

    yield

    # --- Shutdown ---
    logger.info("Application shutdown: Closing resources...")

    # Clean up all resources using the resource manager
    await resource_manager.cleanup_all()

    logger.info("Application shutdown complete.")
