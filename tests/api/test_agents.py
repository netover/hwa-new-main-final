from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from resync.models.agents import AgentConfig, AgentType
from resync.core.fastapi_di import get_agent_manager

# --- Sample Data for Mocking ---
sample_agent_config_1 = AgentConfig(
    id="test-agent-1",
    name="Test Agent 1",
    agent_type=AgentType.CHAT,
    role="Tester",
    goal="To be tested",
    backstory="Born in a test",
    tools=["tws_status_tool"],
    model_name="test-model",
    max_rpm=60,
)

sample_agent_config_2 = AgentConfig(
    id="test-agent-2",
    name="Test Agent 2",
    agent_type=AgentType.TASK,
    role="Another Tester",
    goal="To also be tested",
    backstory="Born in another test",
    tools=["tws_troubleshooting_tool"],
    model_name="test-model-2",
    max_rpm=30,
)


@pytest.fixture
def client(mock_agent_manager: AsyncMock) -> TestClient:
    """Create a TestClient for the FastAPI app."""
    from resync.api.agents import agents_router
    from resync.api.exception_handlers import register_exception_handlers
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(agents_router, prefix="/api/v1/agents")
    app.dependency_overrides[get_agent_manager] = lambda: mock_agent_manager
    register_exception_handlers(app)
    return TestClient(app)


@pytest.fixture
def mock_agent_manager() -> AsyncMock:
    """
    Fixture to provide a mock agent manager.
    """
    return AsyncMock()


def test_list_all_agents_success(client: TestClient, mock_agent_manager: AsyncMock) -> None:
    """
    Tests GET /api/v1/agents/ - successful retrieval of all agent configs.
    """
    # Arrange: Configure the mock to return a list of agent configs
    mock_agent_manager.get_all_agents.return_value = [
        sample_agent_config_1,
        sample_agent_config_2,
    ]

    # Act: Make a request to the endpoint
    response = client.get("/api/v1/agents/all")

    # Assert: Check the response
    assert response.status_code == 200
    response_data: list[dict[str, Any]] = response.json()
    assert len(response_data) == 2
    assert response_data[0]["id"] == "test-agent-1"
    assert response_data[1]["id"] == "test-agent-2"


def test_get_agent_details_success(client: TestClient, mock_agent_manager: AsyncMock) -> None:
    """
    Tests GET /api/v1/agents/{agent_id} - successful retrieval of a single agent.
    """
    # Arrange: Configure the mock to return a specific agent config
    mock_agent_manager.get_agent_config.return_value = sample_agent_config_1

    # Act
    response = client.get("/api/v1/agents/test-agent-1")

    # Assert
    assert response.status_code == 200
    assert response.json()["id"] == "test-agent-1"
    mock_agent_manager.get_agent_config.assert_called_once_with("test-agent-1")


def test_get_agent_details_not_found(client: TestClient, mock_agent_manager: AsyncMock) -> None:
    """
    Tests GET /api/v1/agents/{agent_id} - when the agent is not found.
    Should return 404 with standardized error response format.
    """
    # Arrange: Configure the mock to return None, simulating a not-found agent
    mock_agent_manager.get_agent_config.return_value = None

    # Act
    response = client.get("/api/v1/agents/non-existent-agent")

    # Assert: Should return 404 Not Found with proper error format
    assert response.status_code == 404
    response_data: dict[str, Any] = response.json()

    # Assert the problem detail response format (RFC 7807)
    assert "detail" in response_data
    assert "status" in response_data
    assert "title" in response_data
    assert "instance" in response_data
    assert "type" in response_data

    # Check specific values for the NotFoundError
    assert response_data["status"] == 404
    assert "not found" in response_data["detail"].lower()
    assert response_data["title"] == "Not Found Error"
