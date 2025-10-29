from unittest.mock import AsyncMock, patch

import pytest

from ..exceptions import AuditError, DatabaseError, LLMError
from ..ia_auditor import analyze_and_flag_memories, analyze_memory

# Marks all tests in this file as async
pytestmark = pytest.mark.asyncio


@pytest.fixture
def sample_memory():
    """Provides a sample memory dictionary for testing."""
    return {
        "id": "test-mem-123",
        "user_query": "How do I fix this?",
        "agent_response": "Try restarting it.",
        "rating": 1,
    }


@patch("resync.core.ia_auditor.audit_lock")
@patch(
    "resync.core.ia_auditor._validate_memory_for_analysis", return_value=True
)
@patch("resync.core.ia_auditor.call_llm", new_callable=AsyncMock)
async def test_analyze_memory_returns_none_on_llm_failure(
    mock_call_llm, mock_validate, mock_lock, sample_memory, caplog
):
    """
    Ensures analyze_memory handles LLMError gracefully by returning None.
    """
    # Arrange: Simulate an LLM failure
    mock_call_llm.side_effect = LLMError("LLM is unavailable")
    mock_lock.acquire.return_value.__aenter__.return_value = (
        None  # Mock async context
    )

    # Act
    result = await analyze_memory(sample_memory)

    # Assert
    assert result is None
    assert "Skipping memory test-mem-123 due to LLM failure" in caplog.text


@patch("resync.core.ia_auditor.audit_lock")
async def test_analyze_memory_returns_none_on_lock_timeout(
    mock_lock, sample_memory, caplog
):
    """
    Ensures analyze_memory handles AuditError (lock timeout) gracefully.
    """
    # Arrange: Simulate a lock acquisition failure
    mock_lock.acquire.side_effect = AuditError("Failed to acquire lock")

    # Act
    result = await analyze_memory(sample_memory)

    # Assert
    assert result is None
    assert "Could not acquire lock for memory test-mem-123" in caplog.text


@patch("resync.core.ia_auditor.audit_lock")
@patch(
    "resync.core.ia_auditor._validate_memory_for_analysis",
    new_callable=AsyncMock,
)
async def test_analyze_memory_returns_none_on_database_error(
    mock_validate, mock_lock, sample_memory, caplog
):
    """
    Ensures analyze_memory handles DatabaseError during validation gracefully.
    """
    # Arrange: Simulate a database failure during the validation step
    mock_validate.side_effect = DatabaseError("DB connection lost")
    mock_lock.acquire.return_value.__aenter__.return_value = None

    # Act
    result = await analyze_memory(sample_memory)

    # Assert
    assert result is None
    assert (
        "Database or KnowledgeGraph error analyzing memory test-mem-123"
        in caplog.text
    )


@patch("resync.core.ia_auditor._fetch_recent_memories", new_callable=AsyncMock)
async def test_analyze_and_flag_memories_handles_fetch_error(
    mock_fetch, caplog
):
    """
    Ensures the main loop handles errors when fetching memories from the DB.
    """
    # Arrange: Simulate a failure when fetching memories
    mock_fetch.return_value = None

    # Act
    result = await analyze_and_flag_memories()

    # Assert
    assert result["error"] == "database_fetch_failed"
