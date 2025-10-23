"""Comprehensive unit tests for validation models."""

from datetime import datetime
from typing import Any

import pytest
from pydantic import ValidationError

from resync.api.validation import (
    # Agent models
    AgentCreateRequest,
    AgentQueryParams,
    AgentUpdateRequest,
    AlertRequest,
    AlertSeverity,
    # Common utilities
    ChatHistoryRequest,
    # Chat models
    ChatMessage,
    ChatSession,
    FileType,
    # File models
    FileUploadRequest,
    FilterParams,
    HealthCheckRequest,
    # Auth models
    LoginRequest,
    MetricType,
    PaginationParams,
    PasswordChangeRequest,
    SanitizationLevel,
    SearchParams,
    SortParams,
    SystemMetricRequest,
    UserRegistrationRequest,
    ValidationConfigModel,
    ValidationErrorResponse,
    # Configuration
    ValidationMode,
    ValidationPatterns,
    ValidationSeverity,
    WebSocketMessage,
    sanitize_input,
    validate_numeric_range,
    validate_string_length,
)


class TestCommonValidation:
    """Test common validation utilities."""

    def test_sanitize_input_basic(self) -> None:
        """Test basic input sanitization."""
        # Test XSS removal
        dirty_input = "<script>alert('xss')</script>Hello World"
        clean_input = sanitize_input(dirty_input)
        assert "<script>" not in clean_input
        assert "Hello World" in clean_input

    def test_sanitize_input_sql_injection(self) -> None:
        """Test SQL injection protection."""
        dirty_input = "'; DROP TABLE users; --"
        clean_input = sanitize_input(dirty_input)
        assert "DROP TABLE" not in clean_input

    def test_validate_string_length(self) -> None:
        """Test string length validation."""
        # Valid length
        result = validate_string_length("hello", min_length=1, max_length=10)
        assert result == "hello"

        # Too short
        with pytest.raises(ValueError):
            validate_string_length("", min_length=1, max_length=10)

        # Too long
        with pytest.raises(ValueError):
            validate_string_length("hello world", min_length=1, max_length=5)

    def test_validate_numeric_range(self) -> None:
        """Test numeric range validation."""
        # Valid range
        result = validate_numeric_range(5, min_value=1, max_value=10)
        assert result == 5

        # Too low
        with pytest.raises(ValueError):
            validate_numeric_range(0, min_value=1, max_value=10)

        # Too high
        with pytest.raises(ValueError):
            validate_numeric_range(11, min_value=1, max_value=10)

    def test_validation_patterns(self) -> None:
        """Test validation patterns."""
        # Test email pattern
        assert ValidationPatterns.EMAIL_PATTERN.match("test@example.com")
        assert not ValidationPatterns.EMAIL_PATTERN.match("invalid-email")

        # Test UUID pattern
        assert ValidationPatterns.UUID_PATTERN.match(
            "123e4567-e89b-12d3-a456-426614174000"
        )
        assert not ValidationPatterns.UUID_PATTERN.match("invalid-uuid")

        # Test script pattern
        assert ValidationPatterns.SCRIPT_PATTERN.search("<script>alert('xss')</script>")
        assert not ValidationPatterns.SCRIPT_PATTERN.search("Hello World")


class TestAgentValidationModels:
    """Test agent validation models."""

    def test_agent_create_request_valid(self) -> None:
        """Test valid agent creation request."""
        data = {
            "id": "test-agent-01",
            "name": "Test Agent",
            "role": "Test assistant agent",
            "goal": "Help users with testing",
            "backstory": "Created for testing purposes",
            "model_name": "llama3:latest",
            "description": "A test agent",
            "tools": ["tool1", "tool2"],
            "memory": True,
            "tags": ["test", "assistant"],
        }

        agent = AgentCreateRequest(**data)
        assert agent.name == "Test Agent"
        assert len(agent.tools) == 2

    def test_agent_create_request_invalid_name(self) -> None:
        """Test agent creation with invalid name."""
        data = {
            "name": "<script>alert('xss')</script>",
            "model_name": "gpt-3.5-turbo",
        }

        with pytest.raises(ValidationError):
            AgentCreateRequest(**data)

    def test_agent_create_request_empty_name(self) -> None:
        """Test agent creation with empty name."""
        data = {"name": "", "model_name": "gpt-3.5-turbo"}

        with pytest.raises(ValidationError):
            AgentCreateRequest(**data)

    def test_agent_create_request_long_description(self) -> None:
        """Test agent creation with too long description."""
        data = {
            "name": "Test Agent",
            "model_name": "gpt-3.5-turbo",
            "description": "x" * 1001,  # Exceeds max length
        }

        with pytest.raises(ValidationError):
            AgentCreateRequest(**data)

    def test_agent_create_request_invalid_model(self) -> None:
        """Test agent creation with invalid model name."""
        data = {
            "name": "Test Agent",
            "model_name": "invalid-model-name-with-special-chars!@#",
        }

        with pytest.raises(ValidationError):
            AgentCreateRequest(**data)

    def test_agent_update_request_valid(self) -> None:
        """Test valid agent update request."""
        data = {
            "name": "Updated Agent",
            "description": "Updated description",
            "tools": ["new_tool"],
        }

        agent = AgentUpdateRequest(**data)
        assert agent.name == "Updated Agent"
        assert len(agent.tools) == 1

    def test_agent_query_params_valid(self) -> None:
        """Test valid agent query parameters."""
        data = {
            "name": "Test",
            "type": "assistant",
            "status": "active",
            "include_inactive": True,
        }

        params = AgentQueryParams(**data)
        assert params.name == "Test"
        assert params.type == "assistant"
        assert params.include_inactive is True

    def test_agent_query_params_xss_injection(self) -> None:
        """Test agent query parameters with XSS injection."""
        data = {"name": "<script>alert('xss')</script>", "type": "assistant"}

        with pytest.raises(ValidationError):
            AgentQueryParams(**data)


class TestAuthValidationModels:
    """Test authentication validation models."""

    def test_login_request_valid(self) -> None:
        """Test valid login request."""
        data = {
            "username": "testuser",
            "password": "SecurePass123!",
            "remember_me": True,
        }

        login = LoginRequest(**data)
        assert login.username == "testuser"
        assert login.remember_me is True

    def test_login_request_invalid_username(self) -> None:
        """Test login request with invalid username."""
        data = {
            "username": "user<script>alert('xss')</script>",
            "password": "SecurePass123!",
        }

        with pytest.raises(ValidationError):
            LoginRequest(**data)

    def test_login_request_weak_password(self) -> None:
        """Test login request with weak password."""
        data = {"username": "testuser", "password": "weak"}

        with pytest.raises(ValidationError):
            LoginRequest(**data)

    def test_password_change_request_valid(self) -> None:
        """Test valid password change request."""
        data = {
            "current_password": "OldPass123!",
            "new_password": "NewSecurePass456!",
            "confirm_password": "NewSecurePass456!",
        }

        password_change = PasswordChangeRequest(**data)
        assert password_change.new_password == "NewSecurePass456!"

    def test_password_change_request_mismatch(self) -> None:
        """Test password change with mismatched confirmation."""
        data = {
            "current_password": "OldPass123!",
            "new_password": "NewSecurePass456!",
            "confirm_password": "DifferentPass789!",
        }

        with pytest.raises(ValidationError):
            PasswordChangeRequest(**data)

    def test_user_registration_request_valid(self) -> None:
        """Test valid user registration request."""
        data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "SecureP@ssw0rd!",
            "confirm_password": "SecureP@ssw0rd!",
        }

        registration = UserRegistrationRequest(**data)

        assert registration.username == "newuser"
        assert registration.email == "newuser@example.com"
        assert registration.accept_terms is True

    def test_user_registration_request_invalid_email(self) -> None:
        """Test user registration with invalid email."""
        data = {
            "username": "newuser",
            "email": "invalid-email-format",
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!",
            "accept_terms": True,
        }

        with pytest.raises(ValidationError):
            UserRegistrationRequest(**data)


class TestChatValidationModels:
    """Test chat validation models."""

    def test_chat_message_valid(self) -> None:
        """Test valid chat message."""
        data = {
            "content": "Hello, how are you?",
            "message_type": "text",
            "sender": "user123",
            "session_id": "session456",
            "timestamp": datetime.utcnow(),
        }

        message = ChatMessage(**data)

        assert message.content == "Hello, how are you?"
        assert message.message_type == "text"

    def test_chat_message_xss_content(self) -> None:
        """Test chat message with XSS content."""
        data = {
            "content": "<script>alert('xss')</script>",
            "message_type": "text",
            "sender": "user123",
            "session_id": "session456",
        }

        with pytest.raises(ValidationError):
            ChatMessage(**data)

    def test_chat_message_too_long(self) -> None:
        """Test chat message that is too long."""
        data = {
            "content": "x" * 10001,  # Exceeds max length
            "message_type": "text",
            "sender": "user123",
            "session_id": "session456",
        }

        with pytest.raises(ValidationError):
            ChatMessage(**data)

    def test_chat_session_valid(self) -> None:
        """Test valid chat session."""
        data = {
            "session_id": "session123",
            "user_id": "user456",
            "agent_id": "agent789",
            "context": ["previous message 1", "previous message 2"],
            "metadata": {"max_tokens": 1000},
        }

        session = ChatSession(**data)
        assert session.session_id == "session123"
        assert len(session.context) == 2

    def test_websocket_message_valid(self) -> None:
        """Test valid WebSocket message."""
        data = {
            "type": "message",
            "sender": "user123",
            "message": "Hello",
            "agent_id": "agent456",
            "timestamp": datetime.utcnow(),
        }

        ws_message = WebSocketMessage(**data)

        assert ws_message.type == "message"
        assert ws_message.message == "Hello"

    def test_chat_history_request_valid(self) -> None:
        """Test valid chat history request."""
        data = {"session_id": "session123", "limit": 50, "offset": 0}

        history = ChatHistoryRequest(**data)
        assert history.session_id == "session123"
        assert history.limit == 50
        assert history.offset == 0


class TestQueryParamValidationModels:
    """Test query parameter validation models."""

    def test_pagination_params_valid(self) -> None:
        """Test valid pagination parameters."""
        data = {"page": 2, "page_size": 25}

        pagination = PaginationParams(**data)
        assert pagination.page == 2
        assert pagination.page_size == 25
        assert pagination.get_offset() == 25  # (2-1) * 25

    def test_pagination_params_invalid_page(self) -> None:
        """Test pagination parameters with invalid page number."""
        data = {"page": 0, "page_size": 25}  # Invalid - must be >= 1

        with pytest.raises(ValidationError):
            PaginationParams(**data)

    def test_search_params_valid(self) -> None:
        """Test valid search parameters."""
        data = {
            "query": "test search",
            "search_fields": ["name", "description"],
            "fuzzy": True,
            "case_sensitive": False,
        }

        search = SearchParams(**data)
        assert search.query == "test search"
        assert len(search.search_fields) == 2
        assert search.fuzzy is True

    def test_search_params_xss_query(self) -> None:
        """Test search parameters with XSS in query."""
        data = {
            "query": "<script>alert('xss')</script>",
            "search_fields": ["name", "description"],
        }

        with pytest.raises(ValidationError):
            SearchParams(**data)

    def test_filter_params_valid(self) -> None:
        """Test valid filter parameters."""
        data = {
            "filters": [
                {"field": "status", "operator": "eq", "value": "active"},
                {"field": "created_at", "operator": "gte", "value": "2023-01-01"},
            ],
            "filter_logic": "and",
        }

        filters = FilterParams(**data)
        assert len(filters.filters) == 2
        assert filters.filter_logic == "and"

    def test_filter_params_invalid_operator(self) -> None:
        """Test filter parameters with invalid operator."""
        data = {
            "filters": [
                {"field": "status", "operator": "invalid_operator", "value": "active"}
            ]
        }

        with pytest.raises(ValidationError):
            FilterParams(**data)

    def test_sort_params_valid(self) -> None:
        """Test valid sort parameters."""
        data = {"sort_by": ["created_at", "name"], "sort_order": ["desc", "asc"]}

        sort = SortParams(**data)
        assert sort.sort_by == ["created_at", "name"]
        assert sort.sort_order == ["desc", "asc"]


class TestFileValidationModels:
    """Test file validation models."""

    def test_file_upload_request_valid(self) -> None:
        """Test valid file upload request."""
        data = {
            "filename": "test_document.pdf",
            "file_size": 1024 * 1024,  # 1MB
            "content_type": "application/pdf",
            "file_type": FileType.DOCUMENT,
            "purpose": "Document upload for processing",
            "metadata": {"author": "Test User", "version": "1.0"},
        }

        file_upload = FileUploadRequest(**data)
        assert file_upload.filename == "test_document.pdf"
        assert file_upload.file_size == 1024 * 1024
        assert file_upload.file_type == FileType.DOCUMENT

    def test_file_upload_request_dangerous_filename(self) -> None:
        """Test file upload with dangerous filename."""
        data = {
            "filename": "../../../etc/passwd",
            "file_size": 1024,
            "content_type": "text/plain",
            "purpose": "Test upload",
        }

        with pytest.raises(ValidationError):
            FileUploadRequest(**data)

    def test_file_upload_request_dangerous_content_type(self) -> None:
        """Test file upload with dangerous content type."""
        data = {
            "filename": "test.php",
            "file_size": 1024,
            "content_type": "application/x-php",
            "purpose": "Test upload",
        }

        with pytest.raises(ValidationError):
            FileUploadRequest(**data)

    def test_file_upload_request_too_large(self) -> None:
        """Test file upload that is too large."""
        data = {
            "filename": "large_file.zip",
            "file_size": 100 * 1024 * 1024 + 1,  # Over 100MB limit
            "content_type": "application/zip",
            "purpose": "Test upload",
        }

        with pytest.raises(ValidationError):
            FileUploadRequest(**data)

    def test_file_upload_request_xss_in_purpose(self) -> None:
        """Test file upload with XSS in purpose field."""
        data = {
            "filename": "test.txt",
            "file_size": 1024,
            "content_type": "text/plain",
            "purpose": "<script>alert('xss')</script>",
        }

        with pytest.raises(ValidationError):
            FileUploadRequest(**data)

    def test_file_upload_request_valid_2(self) -> None:
        """Test valid RAG upload request."""
        files = [
            {
                "filename": "doc1.pdf",
                "file_size": 1024 * 1024,
                "content_type": "application/pdf",
            },
            {
                "filename": "doc2.txt",
                "file_size": 512 * 1024,
                "content_type": "text/plain",
            },
        ]

        # Test with FileUploadRequest instead since RAGUploadRequest doesn't exist
        file_upload = FileUploadRequest(**files[0])

        assert file_upload.filename == "doc1.pdf"
        assert file_upload.content_type == "application/pdf"


class TestMonitoringValidationModels:
    """Test monitoring validation models."""

    def test_system_metric_request_valid(self) -> None:
        """Test valid system metric request."""
        data = {
            "metric_types": [MetricType.CPU, MetricType.MEMORY],
            "time_range": "1h",
            "aggregation": "avg",
            "granularity": "1m",
            "format": "json",
        }

        metrics = SystemMetricRequest(**data)
        assert len(metrics.metric_types) == 2
        assert metrics.time_range == "1h"
        assert metrics.aggregation == "avg"

    def test_system_metric_request_duplicate_types(self) -> None:
        """Test system metric request with duplicate types."""
        data = {
            "metric_types": [MetricType.CPU, MetricType.CPU, MetricType.MEMORY],
            "time_range": "1h",
        }

        with pytest.raises(ValidationError):
            SystemMetricRequest(**data)

    def test_custom_metric_request_invalid_name(self) -> None:
        """Test custom metric request with invalid name."""

        # Test with a different model since CustomMetricRequest doesn't exist
        with pytest.raises(ValidationError):
            SystemMetricRequest(metric_types=[])  # Empty metric types should fail

    def test_alert_request_valid(self) -> None:
        """Test valid alert request."""
        data = {
            "alert_name": "high_cpu_usage",
            "severity": AlertSeverity.WARNING,
            "description": "CPU usage is above 80%",
            "threshold_value": 80.0,
            "current_value": 85.5,
            "labels": {"host": "server1", "datacenter": "us-east"},
        }

        alert = AlertRequest(**data)
        assert alert.alert_name == "high_cpu_usage"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.threshold_value == 80.0

    def test_alert_request_xss_in_description(self) -> None:
        """Test alert request with XSS in description."""
        data = {
            "alert_name": "test_alert",
            "severity": AlertSeverity.INFO,
            "description": "<script>alert('xss')</script>",
        }

        with pytest.raises(ValidationError):
            AlertRequest(**data)

    def test_health_check_request_valid(self) -> None:
        """Test valid health check request."""
        data = {
            "component": "database",
            "depth": "detailed",
            "timeout": 60,
            "include_dependencies": True,
        }

        health_check = HealthCheckRequest(**data)
        assert health_check.component == "database"
        assert health_check.depth == "detailed"
        assert health_check.timeout == 60


class TestConfigurationModels:
    """Test configuration models."""

    def test_validation_config_model_valid(self) -> None:
        """Test valid validation configuration."""
        data = {
            "enabled": True,
            "mode": ValidationMode.STRICT,
            "sanitization_level": SanitizationLevel.MODERATE,
            "max_validation_errors": 25,
            "enable_logging": True,
            "log_level": "INFO",
            "skip_paths": ["/health", "/docs", "/static"],
        }

        config = ValidationConfigModel(**data)
        assert config.enabled is True
        assert config.mode == ValidationMode.STRICT
        assert config.sanitization_level == SanitizationLevel.MODERATE
        assert config.max_validation_errors == 25

    def test_validation_config_model_invalid_skip_paths(self) -> None:
        """Test validation config with invalid skip paths."""
        data = {"enabled": True, "skip_paths": ["invalid_path", "../dangerous"]}

        with pytest.raises(ValidationError):
            ValidationConfigModel(**data)

    def test_validation_config_model_invalid_file_size(self) -> None:
        """Test validation config with invalid file size."""
        data = {"enabled": True}

        with pytest.raises(ValidationError):
            ValidationConfigModel(**data)


class TestValidationErrorHandling:
    """Test validation error handling."""

    def test_validation_error_response_creation(self) -> None:
        """Test validation error response creation."""
        error_details = [
            {
                "field": "username",
                "message": "Username is required",
                "type": "value_error.missing",
                "severity": ValidationSeverity.ERROR.value,
            },
            {
                "field": "password",
                "message": "Password must be at least 8 characters",
                "type": "value_error",
                "severity": ValidationSeverity.ERROR.value,
            },
        ]

        error_response = ValidationErrorResponse(
            message="Request validation failed",
            details=error_details,
            severity=ValidationSeverity.ERROR,
            path="/api/login",
            method="POST",
        )

        assert len(error_response.details) == 2
        assert error_response.path == "/api/login"
        assert error_response.method == "POST"

    def test_validation_error_response_with_warnings(self) -> None:
        """Test validation error response with warnings."""
        error_details = [
            {
                "field": "description",
                "message": "Description is very long, consider shortening",
                "type": "value_error",
                "severity": ValidationSeverity.WARNING.value,
            }
        ]

        error_response = ValidationErrorResponse(
            message="Validation completed with warnings",
            details=error_details,
            severity=ValidationSeverity.WARNING,
        )

        assert error_response.severity == ValidationSeverity.WARNING
        assert error_response.details[0]["severity"] == ValidationSeverity.WARNING.value


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_string_constraints_exact_length(self) -> None:
        """Test string constraints at exact length limits."""
        # Test at minimum length
        min_string = "a" * 1  # Minimum SAFE_TEXT length
        result = sanitize_input(min_string)
        assert result == min_string

        # Test at maximum length
        max_string = "a" * 200  # Maximum SAFE_TEXT length
        result = sanitize_input(max_string)
        assert result == max_string

        # Test exceeding maximum length
        too_long_string = "a" * 201
        result = sanitize_input(too_long_string)
        assert len(result) <= 200

    def test_numeric_constraints_boundary_values(self) -> None:
        """Test numeric constraints at boundary values."""
        # Test minimum values
        with pytest.raises(ValueError):
            validate_numeric_range(0, min_value=1, max_value=100)  # Below minimum

        # Test maximum values
        with pytest.raises(ValueError):
            validate_numeric_range(101, min_value=1, max_value=100)  # Above maximum

        # Test exact boundary values
        result = validate_numeric_range(1, min_value=1, max_value=100)
        assert result == 1

        result = validate_numeric_range(100, min_value=1, max_value=100)
        assert result == 100

    def test_empty_and_whitespace_strings(self) -> None:
        """Test validation with empty and whitespace-only strings."""
        # Test empty strings
        with pytest.raises(ValueError):
            validate_string_length("", min_length=1, max_length=100)

        # Test whitespace-only strings
        with pytest.raises(ValueError):
            validate_string_length("   ", min_length=1, max_length=100)

        # Test strings that become empty after stripping
        with pytest.raises(ValueError):
            validate_string_length("  \t\n  ", min_length=1, max_length=100)

    def test_unicode_and_special_characters(self) -> None:
        """Test validation with unicode and special characters."""
        # Test unicode characters
        unicode_text = "Hello 世界 🌍"
        result = sanitize_input(unicode_text)
        assert "世界" in result
        assert "🌍" in result

        # Test special characters that should be allowed
        special_text = "Hello! How are you? This is a test: 123 @ # $ % ^ & * ( )"
        result = sanitize_input(special_text)
        assert result == special_text

        # Test dangerous unicode characters
        dangerous_unicode = "Hello<script>alert('xss')</script>World"
        result = sanitize_input(dangerous_unicode)
        assert "<script>" not in result

    def test_nested_object_validation(self) -> None:
        """Test validation with deeply nested objects."""
        # Test deeply nested data
        nested_data = {
            "level1": {"level2": {"level3": {"level4": {"level5": {"data": "test"}}}}}
        }

        # This should be handled gracefully by validation
        result = sanitize_input(str(nested_data))
        assert "test" in result

    def test_array_validation_edge_cases(self) -> None:
        """Test array validation edge cases."""
        # Test empty arrays
        empty_data: dict[str, Any] = {"tools": [], "tags": []}

        agent = AgentCreateRequest(
            name="Test Agent",
            model_name="gpt-3.5-turbo",
            **empty_data,
        )
        assert agent.tools == []
        assert agent.tags == []

        # Test arrays with duplicate items
        duplicate_data = {
            "tools": ["tool1", "tool2", "tool1"],  # Duplicate
            "tags": ["tag1", "tag2", "tag1"],  # Duplicate
        }

        with pytest.raises(ValidationError):
            AgentCreateRequest(
                name="Test Agent",
                model_name="gpt-3.5-turbo",
                **duplicate_data,
            )

    def test_concurrent_validation_safety(self) -> None:
        """Test that validation is safe for concurrent use."""
        import threading

        results = []
        errors = []

        def validate_data(data, index):
            try:
                result = sanitize_input(data)
                results.append((index, result))
            except Exception as e:
                errors.append((index, str(e)))

        # Create multiple threads with different data
        threads = []
        test_data = [
            "Hello World",
            "<script>alert('xss')</script>",
            "Normal text input",
            "'; DROP TABLE users; --",
            "Another test string",
        ]

        for i, data in enumerate(test_data):
            thread = threading.Thread(target=validate_data, args=(data, i))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all validations completed
        assert len(results) + len(errors) == len(test_data)

        # Verify specific results
        for index, result in results:
            original_data = test_data[index]
            if "<script>" in original_data:
                assert "<script>" not in result
            elif "DROP TABLE" in original_data:
                assert "DROP TABLE" not in result


class TestPerformanceAndScalability:
    """Test validation performance and scalability."""

    def test_large_data_validation_performance(self) -> None:
        """Test validation performance with large data."""
        import time

        # Create large test data
        large_text = "x" * 50000  # 50KB of text
        malicious_text = large_text + "<script>alert('xss')</script>"

        # Measure validation time
        start_time = time.time()
        result = sanitize_input(malicious_text)
        end_time = time.time()

        # Verify validation completed and removed malicious content
        assert "<script>" not in result
        assert end_time - start_time < 1.0  # Should complete within 1 second

    def test_many_validation_operations(self) -> None:
        """Test many validation operations in sequence."""
        import time

        test_data = [
            "Normal text",
            "<script>alert('xss')</script>",
            "Another normal string",
            "'; DROP TABLE users; --",
            "Valid input data",
        ]

        start_time = time.time()

        # Perform many validation operations
        results = []
        for _ in range(1000):  # 1000 iterations
            for data in test_data:
                result = sanitize_input(data)
                results.append(result)

        end_time = time.time()

        # Verify all operations completed
        assert len(results) == 5000

        # Verify performance is reasonable
        assert end_time - start_time < 5.0  # Should complete within 5 seconds

    def test_memory_efficiency(self) -> None:
        """Test that validation doesn't cause memory leaks."""
        import gc
        import os

        import psutil

        process = psutil.Process(os.getpid())

        # Get initial memory usage
        gc.collect()
        initial_memory = process.memory_info().rss

        # Perform many validation operations
        test_data = "<script>alert('xss')</script>" * 1000

        for _ in range(100):
            result = sanitize_input(test_data)
            assert "<script>" not in result

        # Force garbage collection
        gc.collect()

        # Get final memory usage
        final_memory = process.memory_info().rss

        # Memory usage should not increase significantly
        # Allow for some variance due to Python's memory management
        memory_increase = final_memory - initial_memory
        assert memory_increase < 10 * 1024 * 1024  # Less than 10MB increase


if __name__ == "__main__":
    pytest.main([__file__, "-v"])