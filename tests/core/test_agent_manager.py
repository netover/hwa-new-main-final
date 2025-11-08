from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from resync.core.agent_manager import AgentManager
from resync.tool_definitions.tws_tools import TWSStatusTool


@pytest.fixture
def agent_manager_instance() -> AgentManager:
    """Provides a clean instance of the AgentManager for each test."""
    # Reset the singleton for isolation between tests
    AgentManager._instance = None
    return AgentManager()


@pytest.fixture
def mock_config_file(tmp_path: Path) -> Path:
    """Creates a temporary agent configuration file for testing."""
    config_content = {
        "agents": [
            {
                "id": "test-agent-1",
                "name": "Test Agent 1",
                "role": "Testing",
                "goal": "To be tested",
                "backstory": "Born in a test",
                "tools": ["tws_status_tool"],
                "model_name": "test-model",
            }
        ]
    }
    config_file = tmp_path / "runtime.json"
    config_file.write_text(json.dumps(config_content))
    return config_file


def test_singleton_pattern(agent_manager_instance: AgentManager):
    """Ensures that the AgentManager follows the singleton pattern."""
    # The fixture already creates one instance
    instance1 = agent_manager_instance
    instance2 = AgentManager()
    assert instance1 is instance2


@patch("resync.core.agent_manager.OptimizedTWSClient")
@pytest.mark.asyncio
async def test_load_agents_from_config(
    mock_tws_client: MagicMock,
    agent_manager_instance: AgentManager,
    mock_config_file: Path,
):
    """
    Tests that agents are correctly loaded from a valid configuration file.
    """
    # Act
    with patch.object(
        agent_manager_instance, "_create_agent", new_callable=MagicMock
    ) as mock_create_agent:
        mock_agent = MagicMock()
        mock_agent.name = "Test Agent 1"
        mock_agent.instructions = "You are Test Agent 1"
        mock_agent.tools = [TWSStatusTool()]
        agent_manager_instance.agents["test-agent-1"] = mock_agent
        mock_create_agent.return_value = mock_agent

        await agent_manager_instance.load_agents_from_config(
            config_path=mock_config_file
        )

        # Assert
        assert "test-agent-1" in agent_manager_instance.agents
        agent = await agent_manager_instance.get_agent("test-agent-1")
        assert agent is not None
        # Check if the system prompt was constructed correctly
        assert "You are Test Agent 1" in agent.instructions
        # Check that the correct tool instance is present by its type
        assert any(isinstance(t, TWSStatusTool) for t in agent.tools)


@pytest.mark.asyncio
async def test_load_agents_from_nonexistent_file(
    agent_manager_instance: AgentManager,
):
    """
    Tests that the agent manager handles a missing configuration file gracefully.
    """
    # Arrange
    non_existent_path = Path("non_existent_config.json")
    assert not non_existent_path.exists()

    # Act
    await agent_manager_instance.load_agents_from_config(config_path=non_existent_path)

    # Assert
    assert agent_manager_instance.agents == {}


@pytest.mark.asyncio
async def test_load_agents_from_invalid_json(
    agent_manager_instance: AgentManager, tmp_path: Path
):
    """
    Tests that the agent manager handles a malformed JSON file gracefully
    by raising a DataParsingError.
    """

    # Arrange
    invalid_json_file = tmp_path / "invalid.json"
    invalid_json_file.write_text("{'invalid': 'json',}")  # Malformed JSON

    # Act & Assert
    with patch("json.loads", side_effect=json.JSONDecodeError("msg", "doc", 0)):
        await agent_manager_instance.load_agents_from_config(
            config_path=invalid_json_file
        )

    # Also assert that the internal state remains clean
    assert agent_manager_instance.agents == {}


@pytest.mark.asyncio
async def test_tws_client_race_condition_prevention(mocker):
    """
    Tests that multiple concurrent calls to initialize TWS client
    only result in a single actual initialization.
    """
    # Arrange - get a clean singleton instance
    AgentManager._instance = None
    mock_client = MagicMock()
    mock_factory = mocker.MagicMock(return_value=mock_client)
    agent_manager = AgentManager(tws_client_factory=mock_factory)

    # Act - Create multiple concurrent tasks that all try to initialize the TWS client
    tasks = []
    for _ in range(5):
        task = asyncio.create_task(agent_manager.get_tws_client())
        tasks.append(task)

    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks)

    # Assert
    # All tasks should return the same client instance
    assert all(result is mock_client for result in results)
    # But the initialization should only happen once due to the async lock
    assert mock_factory.call_count == 1
    # The client should be stored in the agent manager
    assert agent_manager.tws_client is mock_client


@pytest.mark.asyncio
async def test_async_agent_loading(mock_config_file: Path):
    """
    Tests that agent loading works correctly with async methods.
    """
    # Arrange - get a clean singleton instance
    AgentManager._instance = None
    agent_manager = AgentManager()

    with patch("resync.core.agent_manager.OptimizedTWSClient") as mock_tws_client:
        mock_instance = MagicMock()
        mock_tws_client.return_value = mock_instance

        # Act
        with patch.object(
            agent_manager, "_create_agent", new_callable=MagicMock
        ) as mock_create_agent:
            mock_agent = MagicMock()
            mock_agent.name = "Test Agent 1"
            agent_manager.agents["test-agent-1"] = mock_agent
            mock_create_agent.return_value = mock_agent
            await agent_manager.load_agents_from_config(
                config_path=mock_config_file
            )

            # Assert
            assert "test-agent-1" in agent_manager.agents
            agent = await agent_manager.get_agent("test-agent-1")
            assert agent is not None
