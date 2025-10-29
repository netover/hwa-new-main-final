"""
Unit tests for the IA Auditor module.
"""

from unittest.mock import AsyncMock, patch

import pytest

from resync.core.exceptions import DatabaseError, LLMError
from resync.core.ia_auditor import (
    _analyze_memories_concurrently,
    _cleanup_locks,
    _fetch_recent_memories,
    _process_analysis_results,
    analyze_and_flag_memories,
    analyze_memory,
)


@pytest.fixture
def mock_dependencies():
    """Fixture to mock all external dependencies for the ia_auditor module."""
    with (
        patch(
            "resync.core.ia_auditor.audit_lock", new_callable=AsyncMock
        ) as mock_audit_lock,
        patch(
            "resync.core.ia_auditor.knowledge_graph", new_callable=AsyncMock
        ) as mock_kg,
        patch(
            "resync.core.ia_auditor.audit_queue", new_callable=AsyncMock
        ) as mock_audit_queue,
        patch("resync.core.ia_auditor.call_llm") as mock_call_llm,
        patch("resync.core.ia_auditor.parse_llm_json_response") as mock_parse_json,
    ):

        # Configure default behaviors
        mock_audit_lock.acquire.return_value.__aenter__.return_value = None
        mock_kg.get_all_recent_conversations.return_value = []
        mock_audit_queue.add_audit_record.return_value = True

        yield {
            "audit_lock": mock_audit_lock,
            "kg": mock_kg,
            "audit_queue": mock_audit_queue,
            "call_llm": mock_call_llm,
            "parse_json": mock_parse_json,
        }


@pytest.mark.asyncio
class TestIAAuditor:
    """Test suite for the IA Auditor functions."""

    async def test_cleanup_locks_handles_exception(self, mock_dependencies):
        """Test that _cleanup_locks logs a warning and continues on exception."""
        mock_dependencies["audit_lock"].cleanup_expired_locks.side_effect = Exception(
            "Cleanup failed"
        )
        await _cleanup_locks()
        # Test passes if no exception is raised

    async def test_fetch_recent_memories_success(self, mock_dependencies):
        """Test that _fetch_recent_memories returns data on success."""
        mock_memories = [{"id": "mem1"}]
        mock_dependencies["kg"].get_all_recent_conversations.return_value = (
            mock_memories
        )
        result = await _fetch_recent_memories()
        assert result == mock_memories

    async def test_fetch_recent_memories_failure(self, mock_dependencies):
        """Test that _fetch_recent_memories returns None on database error."""
        mock_dependencies["kg"].get_all_recent_conversations.side_effect = (
            DatabaseError("DB down")
        )
        result = await _fetch_recent_memories()
        assert result is None

    @patch("resync.core.ia_auditor.analyze_memory", new_callable=AsyncMock)
    async def test_analyze_memories_concurrently(
        self, mock_analyze_memory, mock_dependencies
    ):
        """Test that memories are analyzed concurrently."""
        memories = [{"id": "mem1"}, {"id": "mem2"}]
        mock_analyze_memory.side_effect = [("flag", {}), ("delete", "mem2")]

        results = await _analyze_memories_concurrently(memories)

        assert mock_analyze_memory.call_count == 2
        assert results == [("flag", {}), ("delete", "mem2")]

    async def test_process_analysis_results(self, mock_dependencies):
        """Test that analysis results are correctly processed and sorted."""
        results = [
            ("flag", {"id": "mem1"}),
            ("delete", "mem2"),
            None,
            ("flag", {"id": "mem3"}),
        ]
        to_delete, to_flag = await _process_analysis_results(results)

        assert to_delete == ["mem2"]
        assert to_flag == [{"id": "mem1"}, {"id": "mem3"}]
        assert mock_dependencies["audit_queue"].add_audit_record.call_count == 3

    async def test_analyze_and_flag_memories_full_flow(self, mock_dependencies):
        """Test the main orchestrator function with a successful flow."""
        # Arrange
        mock_memories = [{"id": "mem1", "user_query": "q", "agent_response": "a"}]
        mock_dependencies["kg"].get_all_recent_conversations.return_value = (
            mock_memories
        )

        # Mock the analyze_memory call within the main function
        with patch(
            "resync.core.ia_auditor.analyze_memory", new_callable=AsyncMock
        ) as mock_analyze:
            mock_analyze.return_value = ("delete", "mem1")

            # Act
            result = await analyze_and_flag_memories()

            # Assert
            mock_dependencies["audit_lock"].cleanup_expired_locks.assert_called_once()
            mock_dependencies["kg"].get_all_recent_conversations.assert_called_once()
            mock_analyze.assert_called_once_with(mock_memories[0])
            mock_dependencies["kg"].delete_memory.assert_called_once_with("mem1")
            assert result == {"deleted": 1, "flagged": 0}

    async def test_analyze_and_flag_memories_no_memories(self, mock_dependencies):
        """Test the main function when no memories are fetched."""
        mock_dependencies["kg"].get_all_recent_conversations.return_value = []

        result = await analyze_and_flag_memories()

        mock_dependencies["kg"].delete_memory.assert_not_called()
        assert result == {"deleted": 0, "flagged": 0}

    async def test_analyze_and_flag_memories_db_fetch_fails(self, mock_dependencies):
        """Test the main function when fetching memories fails."""
        mock_dependencies["kg"].get_all_recent_conversations.return_value = None

        result = await analyze_and_flag_memories()

        assert result == {"deleted": 0, "flagged": 0, "error": "database_fetch_failed"}

    async def test_analyze_memory_skips_if_invalid(self, mock_dependencies):
        """Test that analyze_memory skips processing if validation fails."""
        with patch(
            "resync.core.ia_auditor._validate_memory_for_analysis",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.return_value = False
            result = await analyze_memory({"id": "mem1"})
            assert result is None
            mock_dependencies["call_llm"].assert_not_called()

    async def test_analyze_memory_handles_llm_error(self, mock_dependencies):
        """Test that analyze_memory returns None if the LLM call fails."""
        mock_dependencies["kg"].is_memory_already_processed.return_value = False
        mock_dependencies["kg"].is_memory_flagged.return_value = False
        mock_dependencies["kg"].is_memory_approved.return_value = False
        mock_dependencies["call_llm"].side_effect = LLMError("API is down")

        result = await analyze_memory(
            {"id": "mem1", "user_query": "q", "agent_response": "a"}
        )

        assert result is None
