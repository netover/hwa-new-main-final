import json
from pathlib import Path

import pytest

from ..agent_manager import AgentManager
from ..exceptions import InvalidConfigError, MissingConfigError, ParsingError

# Marks all tests in this file as async
pytestmark = pytest.mark.asyncio


@pytest.fixture
def agent_manager():
    """Provides a fresh instance of AgentManager for each test."""
    # Reset the singleton for test isolation
    AgentManager._instance = None
    return AgentManager()


async def test_load_agents_raises_missing_config_error(agent_manager):
    """
    Ensures MissingConfigError is raised when the config file does not exist.
    """
    non_existent_path = Path("/tmp/non_existent_config.json")
    with pytest.raises(MissingConfigError):
        await agent_manager.load_agents_from_config(config_path=non_existent_path)


async def test_load_agents_raises_parsing_error_for_malformed_json(
    agent_manager, tmp_path
):
    """
    Ensures ParsingError is raised for a config file with invalid JSON.
    """
    config_path = tmp_path / "agents.json"
    config_path.write_text("{'invalid_json': True,}")  # Malformed JSON

    with pytest.raises(ParsingError):
        await agent_manager.load_agents_from_config(config_path=config_path)


async def test_load_agents_raises_invalid_config_error_for_bad_data(
    agent_manager, tmp_path
):
    """
    Ensures InvalidConfigError is raised when JSON is valid but data
    does not match the Pydantic model.
    """
    config_path = tmp_path / "agents.json"
    # 'agents' key is present, but the agent object is missing required fields like 'id'
    invalid_data = {"agents": [{"name": "test-agent"}]}
    config_path.write_text(json.dumps(invalid_data))

    with pytest.raises(InvalidConfigError):
        await agent_manager.load_agents_from_config(config_path=config_path)


async def test_load_agents_returns_when_path_does_not_exist_and_no_raise(
    agent_manager, mocker
):
    """Tests that the method returns gracefully if the default path doesn't exist."""
    mocker.patch(
        "resync.settings.AGENT_CONFIG_PATH", Path("/tmp/non_existent_path.json")
    )
    # Should not raise an exception, just log an error and return
    await agent_manager.load_agents_from_config()
    assert agent_manager.agents == {}
    assert agent_manager.agent_configs == []
