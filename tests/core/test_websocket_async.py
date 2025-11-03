"""
WebSocket tests using TestClient properly to avoid event loop conflicts.
This file demonstrates the proper way to test WebSocket endpoints with dependency injection.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from resync.core.fastapi_di import (
    get_agent_manager,
    get_connection_manager,
    get_knowledge_graph,
)
from resync.core.interfaces import IAgentManager, IConnectionManager, IKnowledgeGraph
from tests.async_iterator_mock import create_text_stream


@pytest.fixture(scope="function")
def client_with_mocks(test_app: FastAPI):
    """
    Provides a TestClient with fresh mocks for each test function,
    using the App Factory pattern to ensure correct configuration loading.
    """
    mock_agent_manager = AsyncMock(spec=IAgentManager)
    mock_connection_manager = AsyncMock(spec=IConnectionManager)
    mock_knowledge_graph = AsyncMock(spec=IKnowledgeGraph)

    # Apply overrides to the app instance provided by the factory
    test_app.dependency_overrides[get_agent_manager] = lambda: mock_agent_manager
    test_app.dependency_overrides[get_connection_manager] = (
        lambda: mock_connection_manager
    )
    test_app.dependency_overrides[get_knowledge_graph] = lambda: mock_knowledge_graph

    with TestClient(test_app) as test_client:
        yield {
            "client": test_client,
            "agent_manager": mock_agent_manager,
            "connection_manager": mock_connection_manager,
            "knowledge_graph": mock_knowledge_graph,
        }

    # Fixture teardown is handled by pytest, no need to restore overrides manually


class TestWebSocketAsync:
    """Test WebSocket endpoints using a properly configured TestClient."""

    def test_websocket_connection_agent_not_found(self, client_with_mocks):
        """Test WebSocket connection when the requested agent is not found."""
        client = client_with_mocks["client"]
        mock_manager = client_with_mocks["agent_manager"]
        mock_manager.get_agent.return_value = None  # Simulate agent not found

        with pytest.raises(WebSocketDisconnect) as excinfo:
            with client.websocket_connect("/ws/nonexistent-agent") as websocket:
                websocket.receive_json()  # Connection should be closed by server

        assert excinfo.value.code == 4004
        mock_manager.get_agent.assert_called_once_with("nonexistent-agent")

    def test_websocket_send_message_stream_works(self, client_with_mocks):
        """Test sending a message and receiving a stream from a mocked agent."""
        client = client_with_mocks["client"]
        mock_manager = client_with_mocks["agent_manager"]
        mock_kg = client_with_mocks["knowledge_graph"]

        mock_agent = AsyncMock()
        mock_agent.stream = MagicMock(return_value=create_text_stream("Hello World"))

        mock_manager.get_agent.return_value = mock_agent

        with client.websocket_connect("/ws/test-agent") as websocket:
            websocket.send_text("test message")

            full_response = ""
            # Loop to receive all parts of the stream
            while True:
                try:
                    data = websocket.receive_json()
                    if data.get("type") == "stream_end":
                        break
                    assert data.get("type") == "stream"
                    full_response += data.get("data", "")
                except WebSocketDisconnect:
                    break  # The server might just close the connection at the end

        assert full_response == "Hello World"
        mock_kg.add_conversation.assert_called_once_with(
            user_query="test message",
            agent_response="Hello World",
            agent_id="test-agent",
            context={"agent_name": "Unknown Agent", "agent_description": "No description", "model_used": "Unknown Model"},
        )

    def test_websocket_disconnect(self, client_with_mocks):
        """Test WebSocket disconnection handling."""
        client = client_with_mocks["client"]
        mock_conn_manager = client_with_mocks["connection_manager"]
        mock_agent_manager = client_with_mocks["agent_manager"]

        # A valid agent must be returned for the connection to be fully established
        mock_agent_manager.get_agent.return_value = AsyncMock()

        with client.websocket_connect("/ws/test-agent"):
            # Connection is established and then immediately closed by the 'with' block
            pass

        mock_conn_manager.connect.assert_called_once()
        mock_conn_manager.disconnect.assert_called_once()




