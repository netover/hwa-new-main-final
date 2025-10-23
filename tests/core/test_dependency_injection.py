"""
Dependency Injection Tests

This module tests the dependency injection patterns implemented in the application,
ensuring proper AgentManager instance management and dependency resolution.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from resync.core.agent_manager import AgentManager
from resync.core.dependencies import get_tws_client
from resync.services.mock_tws_service import MockTWSClient


class TestDependencyInjection:
    """Test dependency injection patterns."""

    @pytest_asyncio.fixture(autouse=True)
    def reset_singleton(self):
        """Reset the AgentManager singleton before each test in this class."""
        # This is a robust way to reset the singleton used by the dependency injector
        if "resync.core.dependencies" in __import__("sys").modules:
            # Re-importing won't work due to caching, so we directly manipulate the singleton
            __import__("sys").modules[
                "resync.core.dependencies"
            ].agent_manager = AgentManager()
            AgentManager._instance = None

    @pytest.mark.asyncio
    async def test_tws_client_dependency_injection_real(self):
        """Test REAL TWS client dependency injection when TWS_MOCK_MODE is False."""
        mock_tws_client_instance = AsyncMock()

        with (
            patch("resync.core.dependencies.settings") as mock_settings,
            patch(
                "resync.core.dependencies.agent_manager._get_tws_client",
                return_value=mock_tws_client_instance,
            ) as mock_get_client,
        ):

            mock_settings.TWS_MOCK_MODE = False

            client = await anext(get_tws_client())

            assert client is mock_tws_client_instance
            mock_get_client.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_tws_client_dependency_injection_mock(self):
        """Test MOCK TWS client dependency injection when TWS_MOCK_MODE is True."""
        mock_tws_client_instance = MagicMock(spec=MockTWSClient)

        with (
            patch("resync.core.dependencies.settings") as mock_settings,
            patch(
                "resync.core.dependencies.agent_manager"
            ) as mock_agent_manager_module,
        ):

            mock_settings.TWS_MOCK_MODE = True
            mock_agent_manager_module._mock_tws_client = mock_tws_client_instance

            client = await anext(get_tws_client())

            assert client is mock_tws_client_instance

    @pytest.mark.asyncio
    async def test_dependency_error_handling(self):
        """Test error handling in dependency injection."""
        with (
            patch("resync.core.dependencies.settings") as mock_settings,
            patch(
                "resync.core.dependencies.agent_manager._get_tws_client",
                new_callable=AsyncMock,
            ) as mock_get_client,
        ):

            mock_settings.TWS_MOCK_MODE = False
            mock_get_client.side_effect = Exception("TWS client unavailable")

            with pytest.raises(Exception, match="TWS client unavailable"):
                await anext(get_tws_client())

    @pytest.mark.asyncio
    async def test_dependency_caching(self):
        """Test that dependencies are properly cached by the manager by mocking the constructor."""
        with patch("resync.core.dependencies.settings") as mock_settings:
            mock_settings.TWS_MOCK_MODE = False

            # Since get_tws_client uses the global agent_manager, we need to reset its client
            __import__("sys").modules[
                "resync.core.dependencies"
            ].agent_manager.tws_client = None

            with patch(
                "resync.core.agent_manager.OptimizedTWSClient"
            ) as MockClientClass:
                mock_instance = MagicMock()
                MockClientClass.return_value = mock_instance

                # First call should create and cache the client
                client1 = await anext(get_tws_client())
                MockClientClass.assert_called_once()
                assert client1 is mock_instance

                # Second call should return the cached client
                client2 = await anext(get_tws_client())
                MockClientClass.assert_called_once()

                assert client1 is client2


class TestAgentManagerDI:
    """Test AgentManager functionality within a DI context."""

    @pytest_asyncio.fixture
    def agent_manager(self):
        """Fixture to provide a clean instance of AgentManager for each test."""
        AgentManager._instance = None
        manager = AgentManager()
        with patch.object(manager, "load_agents_from_config", new_callable=AsyncMock):
            yield manager

    @pytest.mark.asyncio
    async def test_agent_manager_initialization(self, agent_manager):
        """Test AgentManager initialization."""
        assert agent_manager is not None
        assert agent_manager.agents == {}
        assert agent_manager.agent_configs == []

    @pytest.mark.asyncio
    async def test_agent_manager_singleton_behavior(self, agent_manager):
        """Test that AgentManager behaves as singleton."""
        manager1 = agent_manager
        manager2 = AgentManager()
        assert manager1 is manager2

    @pytest.mark.asyncio
    async def test_agent_manager_get_agent(self, agent_manager):
        """Test AgentManager get_agent method."""
        agent = await agent_manager.get_agent("nonexistent")
        assert agent is None

    @pytest.mark.asyncio
    async def test_agent_manager_get_all_agents(self, agent_manager):
        """Test AgentManager get_all_agents method."""
        agents = await agent_manager.get_all_agents()
        assert agents == []

    @pytest.mark.asyncio
    async def test_agent_manager_tools_discovery(self, agent_manager):
        """Test AgentManager tools discovery."""
        tools = agent_manager._discover_tools()
        assert isinstance(tools, dict)
        assert "tws_status_tool" in tools
        assert "tws_troubleshooting_tool" in tools
