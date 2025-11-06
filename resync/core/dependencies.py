"""Dependency helpers for FastAPI-compatible generators."""

from __future__ import annotations

from typing import AsyncIterator, Any

from resync.settings.settings import settings
from resync.core.agent_manager import AgentManager
from resync.services.mock_tws_service import MockTWSClient

agent_manager = AgentManager()


async def get_tws_client() -> AsyncIterator[Any]:
    if getattr(settings, "TWS_MOCK_MODE", False):
        client = getattr(agent_manager, "_mock_tws_client", None)
        if client is None:
            client = MockTWSClient()
            agent_manager._mock_tws_client = client  # type: ignore[attr-defined]
        yield client
    else:
        try:
            if getattr(agent_manager, "tws_client", None) is None:
                agent_manager.tws_client = await agent_manager.get_tws_client()  # type: ignore
            yield agent_manager.tws_client
        except Exception:
            raise


__all__ = ["get_tws_client", "agent_manager"]




