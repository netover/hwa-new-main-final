"""
Test module for audit logging functionality.

This module tests the log_audit_event function and its integration with the audit database.
"""

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from resync.core.audit_log import AuditLogManager, get_audit_log_manager
from resync.core.logger import _sanitize_audit_details, log_audit_event


def test_log_audit_event_functionality():
    """Test the log_audit_event function with database persistence."""
    # Create a temporary database for testing
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        temp_db_path = tmp_file.name

    try:
        # Create an audit log manager using the temp database
        manager = AuditLogManager(db_path=temp_db_path)

        # Replace the global instance with our test instance
        get_audit_log_manager()
        with patch("resync.core.audit_log._audit_log_manager", manager):
            # Test the log_audit_event function
            log_audit_event(
                action="test_action",
                user_id="test_user",
                details={"key1": "value1", "key2": 123},
                correlation_id="test-correlation-123",
                severity="INFO",
            )

            # Query the database to verify the log was created
            logs = manager.query_audit_logs(action="test_action")
            assert len(logs) == 1

            log_entry = logs[0]
            assert log_entry.action == "test_action"
            assert log_entry.user_id == "test_user"
            assert log_entry.correlation_id == "test-correlation-123"
            assert log_entry.severity == "INFO"

            # Verify the details were properly stored as JSON
            details_dict = json.loads(log_entry.details)
            assert details_dict["key1"] == "value1"
            assert details_dict["key2"] == 123

    finally:
        # Cleanup
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)


def test_log_audit_event_sensitivity():
    """Test that sensitive information is properly redacted."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        temp_db_path = tmp_file.name

    try:
        # Create an audit log manager using the temp database
        manager = AuditLogManager(db_path=temp_db_path)

        # Replace the global instance with our test instance
        with patch("resync.core.audit_log._audit_log_manager", manager):
            # Test with sensitive information
            log_audit_event(
                action="sensitive_action",
                user_id="sensitive_user",
                details={
                    "password": "secret123",
                    "api_key": "key456",
                    "normal_field": "normal_value",
                    "nested": {
                        "credit_card": "1234-5678-9012-3456",
                        "safe_data": "not_sensitive",
                    },
                },
                correlation_id="sensitive-correlation",
                severity="WARNING",
            )

            # Query the database to verify the log was created
            logs = manager.query_audit_logs(action="sensitive_action")
            assert len(logs) == 1

            log_entry = logs[0]
            details_dict = json.loads(log_entry.details)

            # Verify sensitive data was redacted
            assert details_dict["password"] == "REDACTED"
            assert details_dict["api_key"] == "REDACTED"
            assert details_dict["nested"]["credit_card"] == "REDACTED"

            # Verify non-sensitive data was preserved
            assert details_dict["normal_field"] == "normal_value"
            assert details_dict["nested"]["safe_data"] == "not_sensitive"

    finally:
        # Cleanup
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)


def test_audit_log_manager_query_filters():
    """Test the audit log manager's query filtering capabilities."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        temp_db_path = tmp_file.name

    try:
        manager = AuditLogManager(db_path=temp_db_path)

        # Add several test entries with different properties
        manager.log_audit_event("action1", "user1", {"data": 1}, severity="INFO")
        manager.log_audit_event("action2", "user2", {"data": 2}, severity="WARNING")
        manager.log_audit_event("action1", "user1", {"data": 3}, severity="ERROR")
        manager.log_audit_event("action3", "user3", {"data": 4}, severity="INFO")

        # Test action filtering
        action1_logs = manager.query_audit_logs(action="action1")
        assert len(action1_logs) == 2
        for log in action1_logs:
            assert log.action == "action1"

        # Test user filtering
        user1_logs = manager.query_audit_logs(user_id="user1")
        assert len(user1_logs) == 2
        for log in user1_logs:
            assert log.user_id == "user1"

        # Test severity filtering
        warning_logs = manager.query_audit_logs(severity="WARNING")
        assert len(warning_logs) == 1
        assert warning_logs[0].severity == "WARNING"

        # Test multiple filters
        action1_error_logs = manager.query_audit_logs(
            action="action1", severity="ERROR"
        )
        assert len(action1_error_logs) == 1
        assert action1_error_logs[0].action == "action1"
        assert action1_error_logs[0].severity == "ERROR"

        # Test limit and offset
        all_logs = manager.query_audit_logs(limit=2, offset=0)
        assert len(all_logs) == 2
        all_logs_offset = manager.query_audit_logs(limit=2, offset=2)
        assert len(all_logs_offset) == 2
        # Ensure no overlap between the two queries
        all_log_ids = [log.id for log in all_logs]
        offset_log_ids = [log.id for log in all_logs_offset]
        assert not set(all_log_ids).intersection(set(offset_log_ids))

    finally:
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)


def test_audit_log_manager_metrics():
    """Test the audit log manager's metrics functionality."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        temp_db_path = tmp_file.name

    try:
        manager = AuditLogManager(db_path=temp_db_path)

        # Add test entries
        manager.log_audit_event("action1", "user1", {"data": 1}, severity="INFO")
        manager.log_audit_event("action2", "user2", {"data": 2}, severity="WARNING")
        manager.log_audit_event("action1", "user1", {"data": 3}, severity="INFO")
        manager.log_audit_event("action1", "user3", {"data": 4}, severity="ERROR")

        metrics = manager.get_audit_metrics()

        # Verify total count
        assert metrics["total_logs"] == 4

        # Verify severity counts
        assert metrics["by_severity"]["INFO"] == 2
        assert metrics["by_severity"]["WARNING"] == 1
        assert metrics["by_severity"]["ERROR"] == 1

        # Verify action counts
        assert metrics["by_action"]["action1"] == 3
        assert metrics["by_action"]["action2"] == 1

    finally:
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)


def test_sanitize_audit_details():
    """Test the _sanitize_audit_details function directly."""
    test_details = {
        "normal_field": "normal_value",
        "password": "secret123",
        "API_KEY": "api123",  # Test case-insensitive matching
        "nested": {
            "credit_card": "1234-5678-9012-3456",
            "cvv": "123",
            "safe_nested": "safe_value",
        },
        "partially_sensitive_field": "password_value",  # Should not be redacted
        "safe_field": "safe_value",
    }

    sanitized = _sanitize_audit_details(test_details)

    # Verify normal fields are preserved
    assert sanitized["normal_field"] == "normal_value"
    assert sanitized["safe_field"] == "safe_value"
    assert sanitized["nested"]["safe_nested"] == "safe_value"
    assert (
        sanitized["partially_sensitive_field"] == "password_value"
    )  # Should not be redacted

    # Verify sensitive fields are redacted
    assert sanitized["password"] == "REDACTED"
    assert sanitized["API_KEY"] == "REDACTED"  # Case insensitive
    assert sanitized["nested"]["credit_card"] == "REDACTED"
    assert sanitized["nested"]["cvv"] == "REDACTED"


def test_audit_log_manager_error_handling():
    """Test error handling in audit log manager."""
    manager = AuditLogManager()

    # Test query with invalid parameters (should not crash)
    logs = manager.query_audit_logs(action="nonexistent_action")
    assert len(logs) == 0

    # Test metrics when database has issues
    metrics = manager.get_audit_metrics()
    assert "total_logs" in metrics
    assert "by_severity" in metrics
    assert "by_action" in metrics


if __name__ == "__main__":
    pytest.main([__file__, "-v"])




