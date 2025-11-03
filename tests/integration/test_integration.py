"""
End-to-end integration tests for the Resync system.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, WebSocketDisconnect
from fastapi.testclient import TestClient

from resync.core.exceptions import DatabaseError
from resync.core.fastapi_di import (
    get_agent_manager,
    get_connection_manager,
    get_knowledge_graph,
)
from resync.core.ia_auditor import analyze_and_flag_memories
from resync.core.interfaces import (
    IAgentManager,
    IAuditQueue,
    IConnectionManager,
    IKnowledgeGraph,
)
from tests.async_iterator_mock import create_text_stream

# Note: The old module-scoped client fixture has been removed.
# Tests should now use the 'client' fixture from conftest.py, which uses the App Factory pattern.


@pytest.mark.di
class TestAsyncKnowledgeGraph:
    """Test that knowledge graph methods are truly async and non-blocking."""

    @pytest.fixture
    def mock_driver(self):
        """Provides a mock for the neo4j driver."""
        with patch(
            "resync.core.knowledge_graph.AsyncGraphDatabase.driver"
        ) as mock_driver_class:
            mock_driver_instance = AsyncMock()
            mock_session = AsyncMock()
            mock_result = AsyncMock()

            async def mock_single_result(*args, **kwargs):
                return {"uuid": "mock_memory_id_123"}

            mock_result.single.return_value = asyncio.Future()
            mock_result.single.return_value.set_result({"uuid": "mock_memory_id_123"})

            mock_session.run.return_value = mock_result

            mock_session_context = AsyncMock()
            mock_session_context.__aenter__.return_value = mock_session

            # The .session() call is now an async def function that returns the context manager
            async def mock_get_session(*args, **kwargs):
                return mock_session_context

            mock_driver_instance.session = mock_get_session

            mock_driver_class.return_value = mock_driver_instance
            yield mock_driver_instance

    @pytest.mark.asyncio
    async def test_async_knowledge_graph_non_blocking(self, mock_driver):
        """Test that knowledge graph operations don't block the event loop."""
        # This test now uses the patched driver directly
        from resync.core.knowledge_graph import AsyncKnowledgeGraph

        kg = AsyncKnowledgeGraph()

        tasks = [
            kg.add_conversation(
                user_query=f"Test query {i}",
                agent_response=f"Test response {i}",
                agent_id=f"agent_{i}",
            )
            for i in range(5)
        ]
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        end_time = time.time()

        assert end_time - start_time < 0.5  # Should be very fast
        assert len(results) == 5
        assert mock_driver.session.call_count == 5


class TestIaAuditorIntegration:
    """
    Integration tests for the IA Auditor flow.
    These tests verify the logic of the auditor function by patching its dependencies.
    """

    @pytest.fixture
    def mock_kg(self):
        """Create a mock knowledge graph for testing the auditor."""
        kg = AsyncMock(spec=IKnowledgeGraph)
        # Add required fields for validation
        kg.get_all_recent_conversations.return_value = [
            {
                "id": "mem_1",
                "rating": 5,
                "user_query": "q1",
                "agent_response": "r1",
            },  # Skipped (high rating)
            {
                "id": "mem_2",
                "rating": 2,
                "user_query": "q2",
                "agent_response": "r2",
            },  # Processed
            {
                "id": "mem_3",
                "rating": 1,
                "user_query": "q3",
                "agent_response": "r3",
            },  # Processed
        ]
        kg.is_memory_already_processed.return_value = False
        kg.is_memory_approved.return_value = False
        kg.is_memory_flagged.return_value = False
        kg.atomic_check_and_delete.return_value = True
        kg.atomic_check_and_flag.return_value = True
        return kg

    @pytest.fixture
    def mock_aq(self):
        """Create a mock audit queue for testing."""
        return AsyncMock(spec=IAuditQueue)

    @pytest.fixture
    def mock_lock(self):
        """Create a mock distributed lock for testing."""
        lock = AsyncMock()
        # Mock the async context manager protocol
        lock.acquire.return_value.__aenter__.return_value = None
        return lock

    @pytest.mark.asyncio
    async def test_ia_auditor_delete_flow(self, mock_kg, mock_aq, mock_lock):
        """Test the auditor flow where a memory is deleted."""
        mock_llm = AsyncMock(
            return_value='{"is_incorrect": true, "confidence": 0.95, "reason": "Bad"}'
        )

        # Only mem_3 should be deleted as others have high ratings
        mock_kg.get_all_recent_conversations.return_value = [
            {"id": "mem_1", "rating": 5, "user_query": "q1", "agent_response": "r1"},
            {"id": "mem_2", "rating": 4, "user_query": "q2", "agent_response": "r2"},
            {"id": "mem_3", "rating": 1, "user_query": "q3", "agent_response": "r3"},
        ]

        with (
            patch("resync.core.ia_auditor.call_llm", mock_llm),
            patch("resync.core.ia_auditor.knowledge_graph", mock_kg),
            patch("resync.core.ia_auditor.audit_queue", mock_aq),
            patch("resync.core.ia_auditor.audit_lock", mock_lock),
        ):
            result = await analyze_and_flag_memories()

            assert result["deleted"] == 1
            assert result["flagged"] == 0
            mock_kg.delete_memory.assert_called_once_with("mem_3")
            mock_kg.add_observations.assert_not_called()
            mock_aq.add_audit_record_sync.assert_not_called()

    @pytest.mark.asyncio
    async def test_ia_auditor_flag_flow(self, mock_kg, mock_aq, mock_lock):
        """Test the auditor flow where a memory is flagged for review."""
        mock_llm = AsyncMock(
            return_value='{"is_incorrect": true, "confidence": 0.7, "reason": "Needs review"}'
        )

        # mem_2 and mem_3 should be processed and flagged
        with (
            patch("resync.core.ia_auditor.call_llm", mock_llm),
            patch("resync.core.ia_auditor.knowledge_graph", mock_kg),
            patch("resync.core.ia_auditor.audit_queue", mock_aq),
            patch("resync.core.ia_auditor.audit_lock", mock_lock),
        ):
            result = await analyze_and_flag_memories()

            assert result["deleted"] == 0
            assert result["flagged"] == 2
            mock_kg.delete_memory.assert_not_called()
            assert mock_kg.add_observations.call_count == 2
            assert mock_aq.add_audit_record_sync.call_count == 2

    @pytest.mark.asyncio
    async def test_knowledge_graph_failure(self, mock_aq, mock_lock):
        """Test behavior when knowledge graph fails."""
        mock_kg_fail = AsyncMock(spec=IKnowledgeGraph)
        mock_kg_fail.get_all_recent_conversations.side_effect = DatabaseError(
            "DB error"
        )

        with (
            patch("resync.core.ia_auditor.knowledge_graph", mock_kg_fail),
            patch("resync.core.ia_auditor.audit_queue", mock_aq),
            patch("resync.core.ia_auditor.audit_lock", mock_lock),
        ):
            result = await analyze_and_flag_memories()

        assert result["deleted"] == 0
        assert result["flagged"] == 0
        assert result.get("error") == "database_fetch_failed"

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_memory_stress_test(self, mock_aq, mock_lock):
        """Test system behavior under high memory load."""
        mock_kg_stress = AsyncMock(spec=IKnowledgeGraph)
        mock_llm = AsyncMock(return_value='{"is_incorrect": false, "confidence": 0.9}')

        # Use a rating that will be processed
        large_memory_batch = [
            {"id": f"mem_{i}", "rating": 2, "user_query": "q", "agent_response": "r"}
            for i in range(500)
        ]
        mock_kg_stress.get_all_recent_conversations.return_value = large_memory_batch
        mock_kg_stress.is_memory_already_processed.return_value = False
        mock_kg_stress.is_memory_approved.return_value = False
        mock_kg_stress.is_memory_flagged.return_value = False

        with (
            patch("resync.core.ia_auditor.call_llm", mock_llm),
            patch("resync.core.ia_auditor.knowledge_graph", mock_kg_stress),
            patch("resync.core.ia_auditor.audit_queue", mock_aq),
            patch("resync.core.ia_auditor.audit_lock", mock_lock),
        ):
            start_time = time.time()
            result = await analyze_and_flag_memories()
            end_time = time.time()

            assert end_time - start_time < 30.0
            # Since LLM says is_incorrect: false, nothing should be flagged or deleted
            assert result["deleted"] == 0
            assert result["flagged"] == 0
            assert mock_llm.call_count == 500


class TestEndToEndIntegration:
    """Complete end-to-end integration tests simulating full user interaction flow."""

    @pytest.mark.asyncio
    async def test_complete_user_interaction_flow(
        self, test_app: FastAPI, client: TestClient
    ):
        """Test the complete user interaction flow: WebSocket → AgentManager → ... → Auditor."""
        mock_agent = AsyncMock()
        mock_agent.stream = MagicMock(return_value=create_text_stream("Test response"))

        mock_agent_manager = AsyncMock(spec=IAgentManager)
        mock_agent_manager.get_agent.return_value = mock_agent

        mock_kg = AsyncMock(spec=IKnowledgeGraph)

        test_app.dependency_overrides[get_agent_manager] = lambda: mock_agent_manager
        test_app.dependency_overrides[get_knowledge_graph] = lambda: mock_kg

        with patch("resync.api.chat.run_auditor_safely") as mock_run_auditor:
            with client.websocket_connect("/ws/test-agent") as websocket:
                websocket.send_text("How do I restart a job?")
                response = websocket.receive_text()
                assert "Test response" in response

        mock_kg.add_conversation.assert_called_once()
        mock_run_auditor.assert_called_once()

    @pytest.mark.asyncio
    async def test_end_to_end_agent_not_found(
        self, test_app: FastAPI, client: TestClient
    ):
        """Test end-to-end flow when an agent is not found."""
        mock_agent_manager = AsyncMock(spec=IAgentManager)
        mock_agent_manager.get_agent.return_value = None
        test_app.dependency_overrides[get_agent_manager] = lambda: mock_agent_manager

        with pytest.raises(WebSocketDisconnect) as excinfo:
            with client.websocket_connect("/ws/non-existent-agent") as websocket:
                # The connection should be closed by the server with a code
                websocket.receive_json()

        assert excinfo.value.code == 4004
        # To check the reason, you'd typically need to inspect the close frame,
        # but TestClient doesn't expose it easily. The code is sufficient here.

    @pytest.mark.asyncio
    async def test_concurrent_websocket_connections(
        self, test_app: FastAPI, client: TestClient
    ):
        """Test handling multiple concurrent WebSocket connections."""
        mock_conn_manager = AsyncMock(spec=IConnectionManager)
        test_app.dependency_overrides[get_connection_manager] = (
            lambda: mock_conn_manager
        )

        async def simulate_connection(user_id):
            # Each connection needs its own TestClient instance to be isolated
            with TestClient(test_app) as local_client, local_client.websocket_connect(
                "/ws/test-agent"
            ) as websocket:
                websocket.send_text(f"Question from {user_id}")
                data = websocket.receive_text()
                assert "Test response" in data

        tasks = [simulate_connection(i) for i in range(5)]
        await asyncio.gather(*tasks)

        assert mock_conn_manager.connect.call_count == 5
        assert mock_conn_manager.disconnect.call_count == 5




