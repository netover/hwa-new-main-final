"""Integration test for Teams integration with DI container."""

from unittest.mock import AsyncMock, patch

import pytest

from resync.core.di_container import DIContainer, ServiceScope
from resync.core.teams_integration import TeamsConfig, TeamsIntegration


@pytest.mark.asyncio
async def test_teams_integration_di_registration():
    """Test Teams integration registration with DI container."""
    # Create a test container
    container = DIContainer()

    # Register Teams integration with factory
    async def teams_factory():
        config = TeamsConfig(
            enabled=True,
            webhook_url="https://test.webhook.office.com/webhook",
            channel_name="Test Channel",
            bot_name="Test Bot",
        )
        return TeamsIntegration(config)

    container.register_factory(TeamsIntegration, teams_factory, ServiceScope.SINGLETON)

    # Get service from container
    teams_service = await container.get(TeamsIntegration)

    # Verify service is correctly instantiated
    assert isinstance(teams_service, TeamsIntegration)
    assert teams_service.config.enabled is True
    assert teams_service.config.webhook_url == "https://test.webhook.office.com/webhook"
    assert teams_service.config.channel_name == "Test Channel"
    assert teams_service.config.bot_name == "Test Bot"


@pytest.mark.asyncio
async def test_teams_integration_multiple_resolutions():
    """Test that Teams integration returns the same instance for singleton scope."""
    # Create a test container
    container = DIContainer()

    # Counter to track factory calls
    factory_call_count = 0

    # Register Teams integration with factory that tracks calls
    async def teams_factory():
        nonlocal factory_call_count
        factory_call_count += 1
        config = TeamsConfig(
            enabled=True, webhook_url="https://test.webhook.office.com/webhook"
        )
        return TeamsIntegration(config)

    container.register_factory(TeamsIntegration, teams_factory, ServiceScope.SINGLETON)

    # Get service multiple times
    teams_service1 = await container.get(TeamsIntegration)
    teams_service2 = await container.get(TeamsIntegration)
    teams_service3 = await container.get(TeamsIntegration)

    # Verify all services are the same instance (singleton)
    assert teams_service1 is teams_service2
    assert teams_service2 is teams_service3

    # Verify factory was only called once
    assert factory_call_count == 1


@pytest.mark.asyncio
async def test_teams_integration_shutdown():
    """Test Teams integration shutdown."""
    # Create Teams integration
    config = TeamsConfig(
        enabled=True, webhook_url="https://test.webhook.office.com/webhook"
    )
    teams_integration = TeamsIntegration(config)

    # Mock the aiohttp session
    with patch("aiohttp.ClientSession") as mock_session_class:
        mock_session = AsyncMock()
        mock_session_class.return_value = mock_session

        # Initialize session by making a call
        await teams_integration._get_session()

        # Verify session was created
        assert teams_integration.session is not None

        # Shutdown integration
        await teams_integration.shutdown()

        # Verify session was closed
        mock_session.close.assert_called_once()
        assert teams_integration.session is None


if __name__ == "__main__":
    pytest.main([__file__])




