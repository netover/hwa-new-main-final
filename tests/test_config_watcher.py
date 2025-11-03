"""
Comprehensive tests for ConfigWatcher functionality.

This test suite provides extensive coverage for the config watcher implementation,
including config change handling, dependency injection, error scenarios, and
broadcasting functionality.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from resync.core.config_watcher import handle_config_change


class MockAgent:
    """Mock agent for testing."""

    def __init__(self, agent_id: str, name: str):
        self.id = agent_id
        self.name = name


def create_mock_container(mock_agent_manager, mock_connection_manager):
    """Helper function to create properly configured mock container."""
    mock_container = MagicMock()

    def container_get_side_effect(interface):
        if 'IAgentManager' in str(interface):
            return mock_agent_manager
        if 'IConnectionManager' in str(interface):
            return mock_connection_manager
        return MagicMock()

    mock_container.get.side_effect = container_get_side_effect
    return mock_container


def create_mock_cast(mock_agent_manager, mock_connection_manager):
    """Helper function to create properly configured mock cast."""
    def cast_side_effect(type_to_cast, obj):
        if 'AgentManager' in str(type_to_cast):
            return mock_agent_manager
        if 'ConnectionManager' in str(type_to_cast):
            return mock_connection_manager
        return obj

    mock_cast = MagicMock()
    mock_cast.side_effect = cast_side_effect
    return mock_cast


class TestConfigWatcher:
    """Test config watcher functionality."""

    @pytest.mark.asyncio
    async def test_config_change_with_mock_dependencies(self):
        """Test successful config change handling."""
        # Mock dependencies
        mock_agent_manager = AsyncMock()
        mock_connection_manager = AsyncMock()

        # Mock agents
        mock_agents = [
            MockAgent("agent1", "Test Agent 1"),
            MockAgent("agent2", "Test Agent 2"),
        ]
        mock_agent_manager.get_all_agents.return_value = mock_agents

        # Mock DI container
        mock_container = MagicMock()
        mock_container.get.return_value = mock_agent_manager

        # Patch the container and its dependencies
        with patch('resync.core.config_watcher.container', mock_container), \
             patch('resync.core.config_watcher.cast') as mock_cast, \
             patch('resync.core.config_watcher.logger') as mock_logger:

            # Setup cast to return the mocked objects
            def cast_side_effect(type_to_cast, obj):
                if type_to_cast.__name__ == 'AgentManager':
                    return mock_agent_manager
                if type_to_cast.__name__ == 'ConnectionManager':
                    return mock_connection_manager
                return obj

            mock_cast.side_effect = cast_side_effect

            # Mock container.get to return appropriate managers
            def container_get_side_effect(interface):
                if 'IAgentManager' in interface.__name__:
                    return mock_agent_manager
                if 'IConnectionManager' in interface.__name__:
                    return mock_connection_manager
                return MagicMock()

            mock_container.get.side_effect = container_get_side_effect

            # Execute the function
            await handle_config_change()

            # Verify agent manager was called correctly
            mock_agent_manager.load_agents_from_config.assert_called_once()

            # Verify agents were retrieved
            mock_agent_manager.get_all_agents.assert_called_once()

            # Verify broadcast was called with correct data
            mock_connection_manager.broadcast.assert_called_once()
            broadcast_call_args = mock_connection_manager.broadcast.call_args[0][0]

            # Parse the broadcast message
            broadcast_data = json.loads(broadcast_call_args)
            assert broadcast_data["type"] == "config_update"
            assert "message" in broadcast_data
            assert "agents" in broadcast_data
            assert len(broadcast_data["agents"]) == 2
            assert broadcast_data["agents"][0]["id"] == "agent1"
            assert broadcast_data["agents"][0]["name"] == "Test Agent 1"
            assert broadcast_data["agents"][1]["id"] == "agent2"
            assert broadcast_data["agents"][1]["name"] == "Test Agent 2"

            # Verify logging
            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_config_change_with_no_agents(self):
        """Test config change handling when no agents are available."""
        # Mock dependencies
        mock_agent_manager = AsyncMock()
        mock_connection_manager = AsyncMock()

        # Mock empty agents list
        mock_agent_manager.get_all_agents.return_value = []

        # Mock DI container
        mock_container = MagicMock()
        mock_container.get.return_value = mock_agent_manager

        # Patch the container and its dependencies
        with patch('resync.core.config_watcher.container', mock_container), \
             patch('resync.core.config_watcher.cast') as mock_cast, \
             patch('resync.core.config_watcher.logger'):

            # Setup cast to return the mocked objects
            def cast_side_effect(type_to_cast, obj):
                if type_to_cast.__name__ == 'AgentManager':
                    return mock_agent_manager
                if type_to_cast.__name__ == 'ConnectionManager':
                    return mock_connection_manager
                return obj

            mock_cast.side_effect = cast_side_effect

            # Mock container.get to return appropriate managers
            def container_get_side_effect(interface):
                if 'IAgentManager' in interface.__name__:
                    return mock_agent_manager
                if 'IConnectionManager' in interface.__name__:
                    return mock_connection_manager
                return MagicMock()

            mock_container.get.side_effect = container_get_side_effect

            # Execute the function
            await handle_config_change()

            # Verify agent manager was called correctly
            mock_agent_manager.load_agents_from_config.assert_called_once()

            # Verify agents were retrieved
            mock_agent_manager.get_all_agents.assert_called_once()

            # Verify broadcast was called with empty agents list
            mock_connection_manager.broadcast.assert_called_once()
            broadcast_call_args = mock_connection_manager.broadcast.call_args[0][0]

            # Parse the broadcast message
            broadcast_data = json.loads(broadcast_call_args)
            assert broadcast_data["type"] == "config_update"
            assert broadcast_data["agents"] == []

    @pytest.mark.asyncio
    async def test_config_change_agent_load_failure(self):
        """Test config change handling when agent loading fails."""
        # Mock dependencies
        mock_agent_manager = AsyncMock()
        mock_connection_manager = AsyncMock()

        # Mock agent loading failure
        mock_agent_manager.load_agents_from_config.side_effect = Exception("Config file not found")

        # Mock DI container
        mock_container = MagicMock()
        mock_container.get.return_value = mock_agent_manager

        # Patch the container and its dependencies
        with patch('resync.core.config_watcher.container', mock_container), \
             patch('resync.core.config_watcher.cast') as mock_cast, \
             patch('resync.core.config_watcher.logger') as mock_logger:

            # Setup cast to return the mocked objects
            def cast_side_effect(type_to_cast, obj):
                if type_to_cast.__name__ == 'AgentManager':
                    return mock_agent_manager
                if type_to_cast.__name__ == 'ConnectionManager':
                    return mock_connection_manager
                return obj

            mock_cast.side_effect = cast_side_effect

            # Mock container.get to return appropriate managers
            def container_get_side_effect(interface):
                if 'IAgentManager' in interface.__name__:
                    return mock_agent_manager
                if 'IConnectionManager' in interface.__name__:
                    return mock_connection_manager
                return MagicMock()

            mock_container.get.side_effect = container_get_side_effect

            # Execute the function and expect it to handle the error gracefully
            await handle_config_change()

            # Verify agent manager load was attempted
            mock_agent_manager.load_agents_from_config.assert_called_once()

            # Verify error was logged
            mock_logger.error.assert_called_once()
            error_call_args = mock_logger.error.call_args
            assert "error_handling_config_change" in str(error_call_args)

    @pytest.mark.asyncio
    async def test_config_change_broadcast_failure(self):
        """Test config change handling when broadcast fails."""
        # Mock dependencies
        mock_agent_manager = AsyncMock()
        mock_connection_manager = AsyncMock()

        # Mock agents
        mock_agents = [MockAgent("agent1", "Test Agent 1")]
        mock_agent_manager.get_all_agents.return_value = mock_agents

        # Mock broadcast failure
        mock_connection_manager.broadcast.side_effect = Exception("WebSocket connection failed")

        # Mock DI container
        mock_container = MagicMock()
        mock_container.get.return_value = mock_agent_manager

        # Patch the container and its dependencies
        with patch('resync.core.config_watcher.container', mock_container), \
             patch('resync.core.config_watcher.cast') as mock_cast, \
             patch('resync.core.config_watcher.logger') as mock_logger:

            # Setup cast to return the mocked objects
            def cast_side_effect(type_to_cast, obj):
                if type_to_cast.__name__ == 'AgentManager':
                    return mock_agent_manager
                if type_to_cast.__name__ == 'ConnectionManager':
                    return mock_connection_manager
                return obj

            mock_cast.side_effect = cast_side_effect

            # Mock container.get to return appropriate managers
            def container_get_side_effect(interface):
                if 'IAgentManager' in interface.__name__:
                    return mock_agent_manager
                if 'IConnectionManager' in interface.__name__:
                    return mock_connection_manager
                return MagicMock()

            mock_container.get.side_effect = container_get_side_effect

            # Execute the function and expect it to handle the error gracefully
            await handle_config_change()

            # Verify all operations were attempted
            mock_agent_manager.load_agents_from_config.assert_called_once()
            mock_agent_manager.get_all_agents.assert_called_once()
            mock_connection_manager.broadcast.assert_called_once()

            # Verify error was logged
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_config_change_get_agents_failure(self):
        """Test config change handling when getting agents fails."""
        # Mock dependencies
        mock_agent_manager = AsyncMock()
        mock_connection_manager = AsyncMock()

        # Mock successful config load but failure getting agents
        mock_agent_manager.get_all_agents.side_effect = Exception("Database connection failed")

        # Mock DI container
        mock_container = MagicMock()
        mock_container.get.return_value = mock_agent_manager

        # Patch the container and its dependencies
        with patch('resync.core.config_watcher.container', mock_container), \
             patch('resync.core.config_watcher.cast') as mock_cast, \
             patch('resync.core.config_watcher.logger') as mock_logger:

            # Setup cast to return the mocked objects
            def cast_side_effect(type_to_cast, obj):
                if type_to_cast.__name__ == 'AgentManager':
                    return mock_agent_manager
                if type_to_cast.__name__ == 'ConnectionManager':
                    return mock_connection_manager
                return obj

            mock_cast.side_effect = cast_side_effect

            # Mock container.get to return appropriate managers
            def container_get_side_effect(interface):
                if 'IAgentManager' in interface.__name__:
                    return mock_agent_manager
                if 'IConnectionManager' in interface.__name__:
                    return mock_connection_manager
                return MagicMock()

            mock_container.get.side_effect = container_get_side_effect

            # Execute the function and expect it to handle the error gracefully
            await handle_config_change()

            # Verify operations were attempted
            mock_agent_manager.load_agents_from_config.assert_called_once()
            mock_agent_manager.get_all_agents.assert_called_once()

            # Verify error was logged
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_config_change_dependency_resolution_failure(self):
        """Test config change handling when dependency resolution fails."""
        # Mock DI container to raise exception
        mock_container = MagicMock()
        mock_container.get.side_effect = Exception("Dependency not registered")

        # Patch the container
        with patch('resync.core.config_watcher.container', mock_container), \
             patch('resync.core.config_watcher.logger') as mock_logger:

            # Execute the function and expect it to handle the error gracefully
            await handle_config_change()

            # Verify error was logged
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_config_change_with_special_characters_in_agent_names(self):
        """Test config change handling with special characters in agent names."""
        # Mock dependencies
        mock_agent_manager = AsyncMock()
        mock_connection_manager = AsyncMock()

        # Mock agents with special characters
        mock_agents = [
            MockAgent("agent1", "Agent with spëcial çharacters"),
            MockAgent("agent2", "Agent with émojis 🚀"),
            MockAgent("agent3", "Agent with \"quotes\" and 'apostrophes'"),
        ]
        mock_agent_manager.get_all_agents.return_value = mock_agents

        # Mock DI container
        mock_container = MagicMock()
        mock_container.get.return_value = mock_agent_manager

        # Patch the container and its dependencies
        with patch('resync.core.config_watcher.container', mock_container), \
             patch('resync.core.config_watcher.cast') as mock_cast, \
             patch('resync.core.config_watcher.logger'):

            # Setup cast to return the mocked objects
            def cast_side_effect(type_to_cast, obj):
                if type_to_cast.__name__ == 'AgentManager':
                    return mock_agent_manager
                if type_to_cast.__name__ == 'ConnectionManager':
                    return mock_connection_manager
                return obj

            mock_cast.side_effect = cast_side_effect

            # Mock container.get to return appropriate managers
            def container_get_side_effect(interface):
                if 'IAgentManager' in interface.__name__:
                    return mock_agent_manager
                if 'IConnectionManager' in interface.__name__:
                    return mock_connection_manager
                return MagicMock()

            mock_container.get.side_effect = container_get_side_effect

            # Execute the function
            await handle_config_change()

            # Verify broadcast was called with properly serialized data
            mock_connection_manager.broadcast.assert_called_once()
            broadcast_call_args = mock_connection_manager.broadcast.call_args[0][0]

            # Parse the broadcast message
            broadcast_data = json.loads(broadcast_call_args)

            # Verify all agents are included with their special characters
            assert len(broadcast_data["agents"]) == 3
            assert broadcast_data["agents"][0]["name"] == "Agent with spëcial çharacters"
            assert broadcast_data["agents"][1]["name"] == "Agent with émojis 🚀"
            assert broadcast_data["agents"][2]["name"] == "Agent with \"quotes\" and 'apostrophes'"

    @pytest.mark.asyncio
    async def test_config_change_with_large_number_of_agents(self):
        """Test config change handling with a large number of agents."""
        # Mock dependencies
        mock_agent_manager = AsyncMock()
        mock_connection_manager = AsyncMock()

        # Mock many agents
        mock_agents = [MockAgent(f"agent{i}", f"Agent {i}") for i in range(1000)]
        mock_agent_manager.get_all_agents.return_value = mock_agents

        # Mock DI container
        mock_container = MagicMock()
        mock_container.get.return_value = mock_agent_manager

        # Patch the container and its dependencies
        with patch('resync.core.config_watcher.container', mock_container), \
             patch('resync.core.config_watcher.cast') as mock_cast, \
             patch('resync.core.config_watcher.logger'):

            # Setup cast to return the mocked objects
            def cast_side_effect(type_to_cast, obj):
                if type_to_cast.__name__ == 'AgentManager':
                    return mock_agent_manager
                if type_to_cast.__name__ == 'ConnectionManager':
                    return mock_connection_manager
                return obj

            mock_cast.side_effect = cast_side_effect

            # Mock container.get to return appropriate managers
            def container_get_side_effect(interface):
                if 'IAgentManager' in interface.__name__:
                    return mock_agent_manager
                if 'IConnectionManager' in interface.__name__:
                    return mock_connection_manager
                return MagicMock()

            mock_container.get.side_effect = container_get_side_effect

            # Execute the function
            await handle_config_change()

            # Verify broadcast was called with all agents
            mock_connection_manager.broadcast.assert_called_once()
            broadcast_call_args = mock_connection_manager.broadcast.call_args[0][0]

            # Parse the broadcast message
            broadcast_data = json.loads(broadcast_call_args)

            # Verify all 1000 agents are included
            assert len(broadcast_data["agents"]) == 1000
            assert broadcast_data["agents"][0]["id"] == "agent0"
            assert broadcast_data["agents"][999]["id"] == "agent999"
            assert broadcast_data["agents"][500]["name"] == "Agent 500"

    @pytest.mark.asyncio
    async def test_config_change_with_malformed_agent_data(self):
        """Test config change handling with malformed agent data."""
        # Mock dependencies
        mock_agent_manager = AsyncMock()
        mock_connection_manager = AsyncMock()

        # Mock agents with missing attributes
        class MalformedAgent:
            def __init__(self):
                self.id = "malformed_agent"
                # Missing name attribute

        mock_agents = [
            MockAgent("agent1", "Valid Agent"),
            MalformedAgent(),  # This will cause issues when accessing .name
        ]
        mock_agent_manager.get_all_agents.return_value = mock_agents

        # Mock DI container
        mock_container = MagicMock()
        mock_container.get.return_value = mock_agent_manager

        # Patch the container and its dependencies
        with patch('resync.core.config_watcher.container', mock_container), \
             patch('resync.core.config_watcher.cast') as mock_cast, \
             patch('resync.core.config_watcher.logger'):

            # Setup cast to return the mocked objects
            def cast_side_effect(type_to_cast, obj):
                if type_to_cast.__name__ == 'AgentManager':
                    return mock_agent_manager
                if type_to_cast.__name__ == 'ConnectionManager':
                    return mock_connection_manager
                return obj

            mock_cast.side_effect = cast_side_effect

            # Mock container.get to return appropriate managers
            def container_get_side_effect(interface):
                if 'IAgentManager' in interface.__name__:
                    return mock_agent_manager
                if 'IConnectionManager' in interface.__name__:
                    return mock_connection_manager
                return MagicMock()

            mock_container.get.side_effect = container_get_side_effect

            # Execute the function and expect it to handle the error gracefully
            await handle_config_change()

            # Verify that the function attempted to process agents
            mock_agent_manager.load_agents_from_config.assert_called_once()
            mock_agent_manager.get_all_agents.assert_called_once()

            # The broadcast may or may not succeed depending on how the malformed data is handled
            # The important thing is that the function doesn't crash completely

    @pytest.mark.asyncio
    async def test_config_change_logging_behavior(self):
        """Test that config change handling produces appropriate log messages."""
        # Mock dependencies
        mock_agent_manager = AsyncMock()
        mock_connection_manager = AsyncMock()

        # Mock agents
        mock_agents = [MockAgent("agent1", "Test Agent")]
        mock_agent_manager.get_all_agents.return_value = mock_agents

        # Mock DI container
        mock_container = MagicMock()
        mock_container.get.return_value = mock_agent_manager

        # Patch the container and its dependencies
        with patch('resync.core.config_watcher.container', mock_container), \
             patch('resync.core.config_watcher.cast') as mock_cast, \
             patch('resync.core.config_watcher.logger') as mock_logger:

            # Setup cast to return the mocked objects
            def cast_side_effect(type_to_cast, obj):
                if type_to_cast.__name__ == 'AgentManager':
                    return mock_agent_manager
                if type_to_cast.__name__ == 'ConnectionManager':
                    return mock_connection_manager
                return obj

            mock_cast.side_effect = cast_side_effect

            # Mock container.get to return appropriate managers
            def container_get_side_effect(interface):
                if 'IAgentManager' in interface.__name__:
                    return mock_agent_manager
                if 'IConnectionManager' in interface.__name__:
                    return mock_connection_manager
                return MagicMock()

            mock_container.get.side_effect = container_get_side_effect

            # Execute the function
            await handle_config_change()

            # Verify appropriate log messages were generated
            log_calls = mock_logger.info.call_args_list

            # Should have logged configuration change detection
            config_change_logged = any(
                "Configuration change detected" in str(call)
                for call in log_calls
            )
            assert config_change_logged, "Should log configuration change detection"

            # Should have logged successful reload
            reload_logged = any(
                "reloaded successfully" in str(call).lower()
                for call in log_calls
            )
            assert reload_logged, "Should log successful reload"

            # Should have logged broadcast
            broadcast_logged = any(
                "Broadcasted config update" in str(call)
                for call in log_calls
            )
            assert broadcast_logged, "Should log broadcast completion"

    @pytest.mark.asyncio
    async def test_config_change_concurrent_calls(self):
        """Test that concurrent config change calls are handled properly."""
        # Mock dependencies
        mock_agent_manager = AsyncMock()
        mock_connection_manager = AsyncMock()

        # Mock agents
        mock_agents = [MockAgent("agent1", "Test Agent")]
        mock_agent_manager.get_all_agents.return_value = mock_agents

        # Mock DI container
        mock_container = MagicMock()
        mock_container.get.return_value = mock_agent_manager

        # Patch the container and its dependencies
        with patch('resync.core.config_watcher.container', mock_container), \
             patch('resync.core.config_watcher.cast') as mock_cast, \
             patch('resync.core.config_watcher.logger'):

            # Setup cast to return the mocked objects
            def cast_side_effect(type_to_cast, obj):
                if type_to_cast.__name__ == 'AgentManager':
                    return mock_agent_manager
                if type_to_cast.__name__ == 'ConnectionManager':
                    return mock_connection_manager
                return obj

            mock_cast.side_effect = cast_side_effect

            # Mock container.get to return appropriate managers
            def container_get_side_effect(interface):
                if 'IAgentManager' in interface.__name__:
                    return mock_agent_manager
                if 'IConnectionManager' in interface.__name__:
                    return mock_connection_manager
                return MagicMock()

            mock_container.get.side_effect = container_get_side_effect

            # Execute multiple concurrent calls
            tasks = [handle_config_change() for _ in range(10)]
            results = await asyncio.gather(*tasks)

            # All calls should succeed
            assert len(results) == 10

            # Verify that agent manager was called 10 times
            assert mock_agent_manager.load_agents_from_config.call_count == 10
            assert mock_agent_manager.get_all_agents.call_count == 10
            assert mock_connection_manager.broadcast.call_count == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])




