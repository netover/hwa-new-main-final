"""Minimal agent manager implementation.

The original project defined a sophisticated agent management system
responsible for loading, configuring, and orchestrating AI agents.  In
this cleaned and simplified version of the codebase, the full
implementation has been removed to eliminate unnecessary complexity.

This module provides a small subset of the original interface so that
API endpoints and services depending on an ``AgentManager`` can
continue to import it without failure.  The manager holds no state and
returns empty values for all queries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class AgentConfig:
    """Configuration data for an AI agent.

    This dataclass mirrors the fields of the original ``AgentConfig``
    from the full implementation.  Additional fields can be added as
    needed without affecting the simplified manager's functionality.
    """

    id: str
    name: str
    role: str
    goal: str
    model_name: str
    tools: List[str] = field(default_factory=list)
    memory: Optional[Any] = None
    backstory: str = ""


class AgentManager:
    """Trivial agent manager stub.

    Provides asynchronous methods to retrieve agent configurations.  All
    methods return empty values, indicating that no agents are
    configured.  This satisfies type checks and avoids runtime errors
    when the agent subsystem is not required.
    """

    def __init__(self) -> None:
        # The full implementation would load agent definitions from a
        # configuration file or database.  We initialise an empty list here.
        self._agents: List[AgentConfig] = []

    async def get_all_agents(self) -> List[AgentConfig]:
        """Return a list of all configured agents.

        Returns an empty list in this simplified implementation.
        """
        return list(self._agents)

    async def get_agent_config(self, agent_id: str) -> Optional[AgentConfig]:
        """Return the configuration for a single agent.

        Always returns ``None`` in this simplified implementation to
        indicate that no agent with the given ID exists.
        """
        for agent in self._agents:
            if agent.id == agent_id:
                return agent
        return None



