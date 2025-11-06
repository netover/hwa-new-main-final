"""Config watcher utilities for broadcasting agent configuration changes."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Iterable, List, cast

from resync.core.agent_manager import AgentManager
from resync.core.connection_manager import ConnectionManager
from resync.core.di_container import container
from resync.utils.interfaces import IAgentManager, IConnectionManager
from resync.utils.simple_logger import get_logger

logger = get_logger(__name__)
_config_lock = asyncio.Lock()


async def _resolve_dependency(interface: Any) -> Any:
    """Resolve a dependency from the global DI container."""
    return await container.get(interface)


def _serialise_agents(agents: Iterable[Any]) -> List[Dict[str, Any]]:
    serialised: List[Dict[str, Any]] = []
    for agent in agents:
        agent_id = getattr(agent, "id", None)
        agent_name = getattr(agent, "name", None)
        if agent_id is None or agent_name is None:
            continue
        serialised.append({"id": str(agent_id), "name": str(agent_name)})
    return serialised


async def handle_config_change() -> None:
    """Reload agent configuration and broadcast updates to connected clients."""

    async with _config_lock:
        try:
            agent_manager_dep = await _resolve_dependency(IAgentManager)
            connection_manager_dep = await _resolve_dependency(IConnectionManager)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(  # type: ignore
                "dependency_resolution_failed",
                extra={"error": str(exc)},
                exc_info=True,
            )
            return

        agent_manager = cast(AgentManager, agent_manager_dep)
        connection_manager = cast(ConnectionManager, connection_manager_dep)

        try:
            await agent_manager.load_agents_from_config("config.yaml")
        except Exception as exc:
            logger.error(  # type: ignore
                "error_handling_config_change",
                extra={"stage": "load_agents", "error": str(exc)},
                exc_info=False,
            )
            return

        try:
            agents = await agent_manager.get_all_agents()
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(  # type: ignore
                "error_handling_config_change",
                extra={"stage": "get_all_agents", "error": str(exc)},
                exc_info=False,
            )
            agents = []

        payload = {
            "type": "config_update",
            "message": "Agent configuration reloaded successfully.",
            "agents": _serialise_agents(agents),
        }

        try:
            await connection_manager.broadcast(json.dumps(payload))
        except Exception as exc:
            logger.error(  # type: ignore
                "broadcast_failure",
                extra={"error": str(exc)},
                exc_info=False,
            )
        else:
            logger.info(  # type: ignore
                "config_change_broadcasted",
                extra={"agent_count": len(payload["agents"])},
            )
