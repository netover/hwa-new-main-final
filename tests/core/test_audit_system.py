"""
Comprehensive tests for the audit system components.

This module includes tests for:
- Audit log persistence to database
- Connection pool initialization
- Audit event logging functionality
- Audit queue integration with audit logs
"""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import pytest_asyncio

from resync.core.audit_log import AuditLogManager
from resync.core.audit_queue import AsyncAuditQueue
from resync.core.connection_pool_manager import (
    ConnectionPoolManager,
    DatabaseConnectionPool,
    RedisConnectionPool,
)
from resync.core.logger import _sanitize_audit_details, log_audit_event


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path for testing."""
    return str(tmp_path / "test_audit_log.db")


@pytest.fixture
def audit_log_manager(temp_db_path):
    """Create an audit log manager for testing."""
    manager = AuditLogManager(db_path=temp_db_path)
    yield manager
    # Cleanup - no need to explicitly close SQLite connection


class TestAuditLogManager:
    """Test the AuditLogManager class."""

    def test_audit_log_manager_initialization(self, temp_db_path):
        """Test that the audit log manager initializes properly."""
        manager = AuditLogManager(db_path=temp_db_path)
        assert manager.db_path == temp_db_path
        assert manager.engine is not None

    def test_log_audit_event_success(self, audit_log_manager):
        """Test successful logging of an audit event."""
        details = {"test_key": "test_value", "number": 42}
        correlation_id = "test-correlation-id"

        audit_id = audit_log_manager.log_audit_event(
            action="test_action",
            user_id="test_user",
            details=details,
            correlation_id=correlation_id,
            source_component="test_component",
            severity="INFO",
        )

        assert audit_id is not None
        assert audit_id > 0

        # Verify the log was actually saved
        logs = audit_log_manager.query_audit_logs(action="test_action")
        assert len(logs) == 1
        log = logs[0]
        assert log.user_id == "test_user"
        assert log.action == "test_action"
        assert log.correlation_id == correlation_id
        assert log.source_component == "test_component"
        assert log.severity == "INFO"

        # Verify details were serialized as JSON
        details_dict = json.loads(log.details)
        assert details_dict["test_key"] == "test_value"
        assert details_dict["number"] == 42

    def test_log_audit_event_with_exception(self, audit_log_manager):
        """Test that logging handles exceptions gracefully."""
        # Mock the session to raise an exception
        with patch.object(audit_log_manager, "get_session") as mock_get_session:
            mock_get_session.side_effect = Exception("Database error")
            result = audit_log_manager.log_audit_event(
                action="test_action", user_id="test_user", details={"key": "value"}
            )
            assert result is None

    def test_query_audit_logs_with_filters(self, audit_log_manager):
        """Test querying audit logs with various filters."""
        # Add some test logs
        audit_log_manager.log_audit_event(
            "action1", "user1", {"data": "value1"}, severity="INFO"
        )
        audit_log_manager.log_audit_event(
            "action2", "user2", {"data": "value2"}, severity="WARNING"
        )
        audit_log_manager.log_audit_event(
            "action1", "user1", {"data": "value3"}, severity="ERROR"
        )

        # Test action filter
        logs = audit_log_manager.query_audit_logs(action="action1")
        assert len(logs) == 2
        for log in logs:
            assert log.action == "action1"

        # Test user filter
        logs = audit_log_manager.query_audit_logs(user_id="user1")
        assert len(logs) == 2
        for log in logs:
            assert log.user_id == "user1"

        # Test severity filter
        logs = audit_log_manager.query_audit_logs(severity="WARNING")
        assert len(logs) == 1
        assert logs[0].severity == "WARNING"

        # Test date range filter (recent logs)
        start_date = datetime.utcnow() - timedelta(hours=1)
        logs = audit_log_manager.query_audit_logs(start_date=start_date)
        assert len(logs) == 3  # All logs should be within the last hour

    def test_get_audit_metrics(self, audit_log_manager):
        """Test getting audit metrics."""
        # Add some test logs
        audit_log_manager.log_audit_event(
            "action1", "user1", {"data": "value1"}, severity="INFO"
        )
        audit_log_manager.log_audit_event(
            "action2", "user2", {"data": "value2"}, severity="WARNING"
        )
        audit_log_manager.log_audit_event(
            "action1", "user1", {"data": "value3"}, severity="INFO"
        )

        metrics = audit_log_manager.get_audit_metrics()

        assert metrics["total_logs"] == 3
        assert metrics["by_severity"]["INFO"] == 2
        assert metrics["by_severity"]["WARNING"] == 1
        assert metrics["by_action"]["action1"] == 2
        assert metrics["by_action"]["action2"] == 1


class TestLoggerIntegration:
    """Test the audit logger integration with the database."""

    def test_log_audit_event_persists_to_db(self, temp_db_path):
        """Test that log_audit_event also persists to database."""
        # Create a separate audit log manager to verify persistence
        db_manager = AuditLogManager(db_path=temp_db_path)

        # Patch the global get_audit_log_manager to use our test database
        with patch(
            "resync.core.audit_log.get_audit_log_manager", return_value=db_manager
        ):
            log_audit_event(
                action="test_integration",
                user_id="integration_user",
                details={"integration": "test", "value": 123},
                correlation_id="integration-test-123",
                severity="INFO",
            )

            # Verify the event was logged in the database
            logs = db_manager.query_audit_logs(action="test_integration")
            assert len(logs) == 1
            log = logs[0]
            assert log.action == "test_integration"
            assert log.user_id == "integration_user"
            assert log.correlation_id == "integration-test-123"
            assert log.severity == "INFO"

            # Verify details were properly stored
            details_dict = json.loads(log.details)
            assert details_dict["integration"] == "test"
            assert details_dict["value"] == 123

    def test_sanitize_audit_details(self):
        """Test the details sanitization function."""
        details = {
            "normal_field": "normal_value",
            "password": "secret123",
            "api_key": "key123",
            "user_data": {
                "credit_card": "1234-5678-9012-3456",
                "normal_subfield": "normal_value",
            },
            "token": "sensitive_token",
        }

        sanitized = _sanitize_audit_details(details)

        # Check that normal fields are preserved
        assert sanitized["normal_field"] == "normal_value"
        assert sanitized["user_data"]["normal_subfield"] == "normal_value"

        # Check that sensitive fields are redacted
        assert sanitized["password"] == "REDACTED"
        assert sanitized["api_key"] == "REDACTED"
        assert sanitized["user_data"]["credit_card"] == "REDACTED"
        assert sanitized["token"] == "REDACTED"


class TestConnectionPoolInitialization:
    """Test connection pool initialization and management."""

    @pytest_asyncio.fixture
    async def connection_pool_manager(self):
        """Create a connection pool manager for testing."""
        manager = ConnectionPoolManager()
        yield manager
        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_connection_pool_manager_initialization(self):
        """Test that connection pool manager initializes properly."""
        manager = ConnectionPoolManager()
        await manager.initialize()

        manager.get_all_pools()
        # Test that pools are created based on settings
        # At least Redis and Database pools should exist if properly configured

        await manager.shutdown()
        assert manager.is_healthy() is False  # Should be unhealthy after shutdown

    @pytest.mark.asyncio
    async def test_database_connection_pool(self):
        """Test the database connection pool."""
        from resync.core.connection_pool_manager import ConnectionPoolConfig

        # Use an in-memory SQLite database for testing
        config = ConnectionPoolConfig(
            pool_name="test_db_pool", min_size=1, max_size=5, timeout=10
        )
        db_pool = DatabaseConnectionPool(
            config, "sqlite:///file:memdb_test?mode=memory&cache=shared"
        )

        await db_pool.initialize()

        # Test getting a connection
        async with db_pool.get_connection() as session:
            assert session is not None

        await db_pool.shutdown()

    @pytest.mark.asyncio
    async def test_redis_connection_pool(self):
        """Test the Redis connection pool."""
        from resync.core.connection_pool_manager import ConnectionPoolConfig

        config = ConnectionPoolConfig(
            pool_name="test_redis_pool", min_size=1, max_size=5, timeout=10
        )
        redis_pool = RedisConnectionPool(config, "redis://localhost:6379")

        # Mock Redis connection to avoid actual connection
        with patch("redis.asyncio.ConnectionPool.from_url") as mock_from_url:
            mock_pool = MagicMock()
            mock_pool.disconnect = AsyncMock()
            mock_from_url.return_value = mock_pool

            await redis_pool._setup_pool()
            assert redis_pool._connection_pool is not None
            await redis_pool._cleanup_pool()


class TestAuditQueueIntegration:
    """Test the integration between audit queue and audit logging."""

    @pytest_asyncio.fixture
    async def mock_audit_queue(self):
        """Create a mocked audit queue for testing."""
        queue = AsyncMock(spec=AsyncAuditQueue)
        queue.get_all_audits_sync = Mock(return_value=[])
        queue.get_audits_by_status_sync = Mock(return_value=[])
        queue.get_audit_metrics_sync = Mock(
            return_value={"total": 0, "pending": 0, "approved": 0, "rejected": 0}
        )
        queue.update_audit_status_sync = Mock(return_value=True)
        return queue

    @pytest.mark.asyncio
    async def test_audit_api_logging(self, temp_db_path):
        """Test that audit API calls properly log to the audit log database."""
        import uuid
        from unittest.mock import AsyncMock

        from fastapi import Request

        from resync.api.audit import get_audit_metrics, get_flagged_memories

        # Create audit log manager and patch global function
        db_manager = AuditLogManager(db_path=temp_db_path)
        with patch(
            "resync.core.audit_log.get_audit_log_manager", return_value=db_manager
        ):
            # Mock request object
            mock_request = AsyncMock(spec=Request)
            mock_request.state.user_id = "test_user"
            mock_request.state.correlation_id = str(uuid.uuid4())

            # Mock dependencies
            mock_audit_queue = AsyncMock()
            mock_audit_queue.get_all_audits_sync.return_value = []
            mock_audit_queue.get_audits_by_status_sync.return_value = []
            mock_audit_queue.get_audit_metrics_sync.return_value = {
                "total": 0,
                "pending": 0,
                "approved": 0,
                "rejected": 0,
            }
            mock_audit_queue.update_audit_status_sync.return_value = True

            mock_kg = AsyncMock()
            mock_kg.client = AsyncMock()
            mock_kg.client.add_observations = AsyncMock()
            mock_kg.client.delete = AsyncMock()

            # Test get_flagged_memories
            result = get_flagged_memories(
                request=mock_request, audit_queue=mock_audit_queue
            )
            assert result == []

            # Check that audit event was logged
            logs = db_manager.query_audit_logs(action="retrieve_flagged_memories")
            assert len(logs) == 1
            assert logs[0].user_id == "test_user"

            # Test get_audit_metrics
            metrics_result = get_audit_metrics(
                request=mock_request, audit_queue=mock_audit_queue
            )
            assert metrics_result == {
                "total": 0,
                "pending": 0,
                "approved": 0,
                "rejected": 0,
            }

            # Check that audit event was logged
            logs = db_manager.query_audit_logs(action="retrieve_audit_metrics")
            assert len(logs) == 1
            assert logs[0].user_id == "test_user"


def test_audit_db_functions():
    """Test the audit_db functions directly."""
    import os
    import tempfile

    # Create a temporary database for testing
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        temp_db_path = tmp_file.name

    try:
        # Override the database path temporarily
        from resync.core import audit_db

        original_path = audit_db.DATABASE_PATH
        audit_db.DATABASE_PATH = temp_db_path

        # Reinitialize the database with the temp path
        audit_db.initialize_database()

        # Test adding an audit record
        memory = {
            "id": "test_memory_123",
            "user_query": "Test query",
            "agent_response": "Test response",
            "ia_audit_reason": "Test reason",
            "ia_audit_confidence": 0.85,
        }

        record_id = audit_db.add_audit_record(memory)
        assert record_id is not None

        # Test retrieving pending audits
        pending = audit_db.get_pending_audits()
        assert len(pending) == 1
        assert pending[0]["memory_id"] == "test_memory_123"
        assert pending[0]["status"] == "pending"

        # Test updating audit status
        success = audit_db.update_audit_status("test_memory_123", "approved")
        assert success is True

        # Verify the status was updated
        pending = audit_db.get_pending_audits()
        assert len(pending) == 0  # Should no longer be pending

        # Check if the memory is approved
        approved = audit_db.is_memory_approved("test_memory_123")
        assert approved is True

        # Test deleting audit record
        delete_success = audit_db.delete_audit_record("test_memory_123")
        assert delete_success is True

        # Verify deletion
        remaining = audit_db.get_pending_audits()
        assert len(remaining) == 0

    finally:
        # Cleanup
        audit_db.DATABASE_PATH = original_path
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])




