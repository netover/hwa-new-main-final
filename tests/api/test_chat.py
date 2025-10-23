from unittest.mock import AsyncMock, MagicMock

import pytest

from resync.api.chat import _handle_agent_interaction
from resync.core.fastapi_di import (
    get_agent_manager,
    get_connection_manager,
    get_knowledge_graph,
)
pytestmark = pytest.mark.asyncio


@pytest.fixture
def client():
    """Create a TestClient for the FastAPI app."""
    from resync.api.chat import chat_router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(chat_router)
    return TestClient(app)


async def test_handle_agent_interaction_mocks_async_iterator(client):
    """
    Verifies that _handle_agent_interaction correctly processes chunks
    from a mocked async iterator (agent.stream).
    """
    # 1. Arrange
    mock_websocket = AsyncMock()
    mock_agent = MagicMock(spec=["stream"])
    mock_kg = AsyncMock()

    # This is the key part: Mocking the async iterator.
    # We create a list of chunks to be "streamed".
    stream_chunks = ["Hello", ", ", "world", "!"]
    # We configure the mock's __aiter__ method to return an async iterator
    # that yields our chunks.
    mock_agent.stream = AsyncMock()
    mock_agent.stream.return_value.__aiter__.return_value = stream_chunks

    # 2. Act
    await _handle_agent_interaction(
        websocket=mock_websocket,
        agent=mock_agent,
        agent_id="test-agent",
        knowledge_graph=mock_kg,
        data="user message",
    )

    # 3. Assert
    # Check that the stream method was called.
    mock_agent.stream.assert_called_once()

    # Check that send_json was called for each chunk in the stream.
    stream_calls = [
        call
        for call in mock_websocket.send_json.call_args_list
        if call.args[0]["type"] == "stream"
    ]
    assert len(stream_calls) == len(stream_chunks)
    assert stream_calls[0].args[0]["message"] == "Hello"
    assert stream_calls[3].args[0]["message"] == "!"

    # Verify the final message was sent correctly.
    final_call = mock_websocket.send_json.call_args_list[-1]
    assert final_call.args[0]["type"] == "message"
    assert final_call.args[0]["is_final"] is True
    assert final_call.args[0]["message"] == "Hello, world!"
