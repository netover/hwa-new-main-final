"""Agent manager with minimal functionality for tests and runtime."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from resync.settings.settings import settings
from resync.services.mock_tws_service import MockTWSClient
from resync.tool_definitions.tws_tools import (
    tws_status_tool,
    tws_troubleshooting_tool,
)


class AgentConfig(BaseModel):
    """Configuration for a single agent."""

    id: str
    name: str
    role: str
    goal: str
    model_name: str
    tools: List[str] = Field(default_factory=list)
    backstory: str = ""
    memory: Any = None
    verbose: bool = False


class AgentsConfig(BaseModel):
    """Collection of agent configurations."""

    agents: List[AgentConfig] = Field(default_factory=list)


class AgentManager:
    """Lightweight singleton manager capable of loading agent configs."""

    _instance: "AgentManager" | None = None
    _initialised: bool = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._initialised = False
        return cls._instance

    def __init__(self) -> None:
        if self.__class__._initialised:
            return
        self.__class__._initialised = True
        self.agents: Dict[str, AgentConfig] = {}
        self.agent_configs: List[AgentConfig] = []
        self.tws_client: Any | None = None
        self._mock_tws_client: Any | None = None

    async def get_all_agents(self) -> List[AgentConfig]:
        return list(self.agent_configs)

    async def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
        return self.agents.get(agent_id)

    async def get_agent_config(self, agent_id: str) -> Optional[AgentConfig]:
        return await self.get_agent(agent_id)

    async def load_agents_from_config(self, config_path: Path | str) -> None:
        path = Path(config_path)
        try:
            raw = path.read_text()
        except FileNotFoundError:
            return
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
        config = AgentsConfig.model_validate(data)
        self.agent_configs = list(config.agents)
        self.agents = {agent.id: agent for agent in config.agents}

    def _discover_tools(self) -> Dict[str, Any]:
        return {
            "tws_status_tool": tws_status_tool,
            "tws_troubleshooting_tool": tws_troubleshooting_tool,
        }

    async def get_agent_with_tool(
        self, agent_id: str, tool_name: str
    ) -> Tuple[AgentConfig, Any]:
        agent = await self.get_agent(agent_id)
        if agent is None:
            raise ValueError(f"Agent {agent_id} not found")
        tools = self._discover_tools()
        if tool_name not in tools:
            raise ValueError(f"Tool {tool_name} not found for agent {agent_id}")
        if tool_name not in agent.tools:
            raise ValueError(f"Tool {tool_name} not assigned to agent {agent_id}")
        return agent, tools[tool_name]

    async def get_tws_client(self) -> Any:
        if self.tws_client is None:
            self.tws_client = await _get_tws_client()
        return self.tws_client


async def _get_tws_client() -> Any:
    try:
        from resync.services.tws_service import OptimizedTWSClient

        password = getattr(settings, "TWS_PASSWORD", "")
        if hasattr(password, "get_secret_value"):
            password = password.get_secret_value()

        return OptimizedTWSClient(
            hostname=getattr(settings, "TWS_HOST", "localhost"),
            port=getattr(settings, "TWS_PORT", 0),
            username=getattr(settings, "TWS_USER", ""),
            password=password,
            engine_name=getattr(settings, "TWS_ENGINE_NAME", "tws-engine"),
            engine_owner=getattr(settings, "TWS_ENGINE_OWNER", "tws-owner"),
        )
    except Exception:
        return MockTWSClient()


__all__ = ["AgentConfig", "AgentsConfig", "AgentManager"]




