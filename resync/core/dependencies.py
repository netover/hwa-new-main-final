from __future__ import annotations

import logging
from typing import AsyncGenerator

from resync.core.agent_manager import agent_manager
from resync.services.mock_tws_service import MockTWSClient
from resync.services.tws_service import OptimizedTWSClient
from resync.settings import settings

# --- Logging Setup ---
logger = logging.getLogger(__name__)


async def get_tws_client() -> AsyncGenerator[OptimizedTWSClient | MockTWSClient, None]:
    """
    Async dependency injector for the TWS client.

    This function provides a reliable way to get the singleton TWS client
    instance, either the real OptimizedTWSClient or a MockTWSClient based on settings.

    Yields:
        The singleton instance of the TWS client.
    """
    client = None
    try:
        logger.debug("Dependency 'get_tws_client' called.")

        if settings.TWS_MOCK_MODE:
            logger.info("TWS_MOCK_MODE is enabled. Returning MockTWSClient.")
            if (
                not hasattr(agent_manager, "_mock_tws_client")
                or agent_manager._mock_tws_client is None
            ):
                agent_manager._mock_tws_client = MockTWSClient()
            client = agent_manager._mock_tws_client
        else:
            # The agent_manager is responsible for lazily initializing the real client
            if not agent_manager._initialized:
                await agent_manager.load_agents_from_config()
            client = await agent_manager._get_tws_client()

        yield client
    except Exception as e:
        logger.error("failed_to_retrieve_TWS_client", error=str(e), exc_info=True)
        raise
    finally:
        # This is where teardown logic would go, if any was needed.
        logger.debug("TWS client dependency lifetime finished.")
