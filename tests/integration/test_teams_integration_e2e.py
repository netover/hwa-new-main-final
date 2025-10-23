"""End-to-end test for Teams integration with FastAPI DI."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from resync.core.di_container import DIContainer, ServiceScope
from resync.core.fastapi_di import inject_container
from resync.core.teams_integration import TeamsConfig, TeamsIntegration


@pytest.fixture
def test_app():
    """Create a test FastAPI app with DI container."""
    app = FastAPI()

    # Create a test container
    test_container = DIContainer()

    # Configure container with Teams integration
    async def teams_factory():
        config = TeamsConfig(
            enabled=True,
            webhook_url="https://test.webhook.office.com/webhook",
            channel_name="Test Channel",
        )
        return TeamsIntegration(config)

    test_container.register_factory(
        TeamsIntegration, teams_factory, ServiceScope.SINGLETON
    )

    # Inject container into app
    inject_container(app, test_container)

    return app


@pytest.fixture
def client(test_app):
    """Create a test client."""
    return TestClient(test_app)


def test_teams_integration_fixture():
    """Test that Teams integration fixture works correctly."""
    # Create test container
    test_container = DIContainer()

    # Configure with Teams integration
    async def teams_factory():
        config = TeamsConfig(
            enabled=True, webhook_url="https://test.webhook.office.com/webhook"
        )
        return TeamsIntegration(config)

    test_container.register_factory(
        TeamsIntegration, teams_factory, ServiceScope.SINGLETON
    )

    # Verify Teams integration can be resolved
    async def test_resolution():
        teams_service = await test_container.get(TeamsIntegration)
        assert isinstance(teams_service, TeamsIntegration)
        assert teams_service.config.enabled is True

    # Run async test
    asyncio.run(test_resolution())


@patch("aiohttp.ClientSession")
def test_teams_integration_http_endpoints(mock_session_class):
    """Test Teams integration through HTTP endpoints."""
    # Setup mock session
    mock_session = AsyncMock()
    mock_session.post.return_value.__aenter__.return_value.status = 200
    mock_session_class.return_value = mock_session

    # Create FastAPI app
    app = FastAPI()

    # Create test container
    test_container = DIContainer()

    # Configure container with Teams integration
    async def teams_factory():
        config = TeamsConfig(
            enabled=True, webhook_url="https://test.webhook.office.com/webhook"
        )
        return TeamsIntegration(config)

    test_container.register_factory(
        TeamsIntegration, teams_factory, ServiceScope.SINGLETON
    )

    # Inject container
    inject_container(app, test_container)

    # Create test client
    client = TestClient(app)

    # Test that app starts correctly
    client.get("/health")  # This should work even though endpoint doesn't exist
    # We're just testing that the container is properly configured


def test_teams_integration_dependency_injection():
    """Test Teams integration dependency injection."""
    # Create test container
    test_container = DIContainer()

    # Configure with Teams integration
    async def teams_factory():
        config = TeamsConfig(
            enabled=True, webhook_url="https://test.webhook.office.com/webhook"
        )
        return TeamsIntegration(config)

    test_container.register_factory(
        TeamsIntegration, teams_factory, ServiceScope.SINGLETON
    )

    # Test async resolution
    async def test_async_resolution():
        teams_service = await test_container.get(TeamsIntegration)
        assert isinstance(teams_service, TeamsIntegration)
        assert (
            teams_service.config.webhook_url
            == "https://test.webhook.office.com/webhook"
        )

    # Run the async test
    asyncio.run(test_async_resolution())


if __name__ == "__main__":
    pytest.main([__file__])
