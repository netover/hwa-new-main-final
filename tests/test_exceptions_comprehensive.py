"""
Comprehensive tests for the exceptions module.

This module provides extensive test coverage for all exception classes,
ensuring proper initialization, error codes, status codes, and serialization.
"""

from datetime import datetime
from resync.core.exceptions import *


class TestErrorEnums:
    """Test cases for ErrorCode and ErrorSeverity enums."""

    def test_error_code_enum_values(self):
        """Test that all error codes have correct string values."""
        assert ErrorCode.VALIDATION_ERROR.value == "VALIDATION_ERROR"
        assert ErrorCode.AUTHENTICATION_FAILED.value == "AUTHENTICATION_FAILED"
        assert ErrorCode.INTERNAL_ERROR.value == "INTERNAL_ERROR"
        assert ErrorCode.TWS_CONNECTION_ERROR.value == "TWS_CONNECTION_ERROR"
        assert ErrorCode.CACHE_ERROR.value == "CACHE_ERROR"

    def test_error_severity_enum_values(self):
        """Test that all error severities have correct string values."""
        assert ErrorSeverity.CRITICAL.value == "critical"
        assert ErrorSeverity.ERROR.value == "error"
        assert ErrorSeverity.WARNING.value == "warning"
        assert ErrorSeverity.INFO.value == "info"


class TestBaseAppException:
    """Test cases for the base exception class."""

    def test_basic_initialization(self):
        """Test basic exception initialization."""
        exc = BaseAppException(
            message="Test error",
            error_code=ErrorCode.INTERNAL_ERROR,
            status_code=500
        )

        assert exc.message == "Test error"
        assert exc.error_code == ErrorCode.INTERNAL_ERROR
        assert exc.status_code == 500
        assert exc.details == {}
        assert exc.correlation_id is None
        assert exc.severity == ErrorSeverity.ERROR
        assert isinstance(exc.timestamp, datetime)

    def test_full_initialization(self):
        """Test exception initialization with all parameters."""
        details = {"key": "value"}
        correlation_id = "test-correlation-id"

        exc = BaseAppException(
            message="Test error with details",
            error_code=ErrorCode.VALIDATION_ERROR,
            status_code=400,
            details=details,
            correlation_id=correlation_id,
            severity=ErrorSeverity.WARNING,
            original_exception=ValueError("Original error")
        )

        assert exc.message == "Test error with details"
        assert exc.error_code == ErrorCode.VALIDATION_ERROR
        assert exc.status_code == 400
        assert exc.details == details
        assert exc.correlation_id == correlation_id
        assert exc.severity == ErrorSeverity.WARNING
        assert isinstance(exc.original_exception, ValueError)

    def test_to_dict_method(self):
        """Test the to_dict serialization method."""
        exc = BaseAppException(
            message="Test error",
            error_code=ErrorCode.INTERNAL_ERROR,
            status_code=500,
            details={"test": "data"},
            correlation_id="test-id"
        )

        result = exc.to_dict()

        assert result["message"] == "Test error"
        assert result["error_code"] == "INTERNAL_ERROR"
        assert result["status_code"] == 500
        assert result["details"] == {"test": "data"}
        assert result["correlation_id"] == "test-id"
        assert result["severity"] == "error"
        assert "timestamp" in result
        assert isinstance(result["timestamp"], str)

    def test_str_representation(self):
        """Test string representation of exception."""
        exc = BaseAppException(
            message="Test error",
            error_code=ErrorCode.VALIDATION_ERROR,
            status_code=400,
            correlation_id="test-id"
        )

        str_repr = str(exc)

        assert "BaseAppException" in str_repr
        assert "Test error" in str_repr
        assert "VALIDATION_ERROR" in str_repr
        assert "400" in str_repr
        assert "test-id" in str_repr


class TestClientErrors:
    """Test cases for client error exceptions (4xx)."""

    def test_validation_error(self):
        """Test ValidationError exception."""
        exc = ValidationError(
            message="Invalid input data",
            details={"field": "email", "issue": "invalid_format"},
            correlation_id="test-id"
        )

        assert exc.message == "Invalid input data"
        assert exc.error_code == ErrorCode.VALIDATION_ERROR
        assert exc.status_code == 400
        assert exc.severity == ErrorSeverity.WARNING
        assert exc.details["field"] == "email"

    def test_authentication_error(self):
        """Test AuthenticationError exception."""
        exc = AuthenticationError(
            message="Invalid credentials",
            details={"reason": "password_mismatch"}
        )

        assert exc.message == "Invalid credentials"
        assert exc.error_code == ErrorCode.AUTHENTICATION_FAILED
        assert exc.status_code == 401
        assert exc.severity == ErrorSeverity.WARNING

    def test_authorization_error(self):
        """Test AuthorizationError exception."""
        exc = AuthorizationError(
            message="Insufficient permissions",
            details={"required_role": "admin", "user_role": "user"}
        )

        assert exc.message == "Insufficient permissions"
        assert exc.error_code == ErrorCode.AUTHORIZATION_FAILED
        assert exc.status_code == 403
        assert exc.severity == ErrorSeverity.WARNING

    def test_resource_not_found_error(self):
        """Test ResourceNotFoundError exception."""
        exc = ResourceNotFoundError(
            message="User not found",
            resource_type="user",
            resource_id="123"
        )

        assert exc.message == "User not found"
        assert exc.error_code == ErrorCode.RESOURCE_NOT_FOUND
        assert exc.status_code == 404
        assert exc.severity == ErrorSeverity.INFO
        assert exc.details["resource_type"] == "user"
        assert exc.details["resource_id"] == "123"

    def test_resource_conflict_error(self):
        """Test ResourceConflictError exception."""
        exc = ResourceConflictError(
            message="Resource already exists",
            details={"conflict_field": "email"}
        )

        assert exc.message == "Resource already exists"
        assert exc.error_code == ErrorCode.RESOURCE_CONFLICT
        assert exc.status_code == 409
        assert exc.severity == ErrorSeverity.WARNING

    def test_business_error(self):
        """Test BusinessError exception."""
        exc = BusinessError(
            message="Operation not allowed in current state",
            details={"current_state": "pending", "required_state": "active"}
        )

        assert exc.message == "Operation not allowed in current state"
        assert exc.error_code == ErrorCode.BUSINESS_RULE_VIOLATION
        assert exc.status_code == 422
        assert exc.severity == ErrorSeverity.WARNING

    def test_rate_limit_error(self):
        """Test RateLimitError exception."""
        exc = RateLimitError(
            message="Too many requests",
            retry_after=60,
            details={"limit": 100, "window": "1h"}
        )

        assert exc.message == "Too many requests"
        assert exc.error_code == ErrorCode.RATE_LIMIT_EXCEEDED
        assert exc.status_code == 429
        assert exc.severity == ErrorSeverity.WARNING
        assert exc.details["retry_after"] == 60


class TestServerErrors:
    """Test cases for server error exceptions (5xx)."""

    def test_internal_error(self):
        """Test InternalError exception."""
        exc = InternalError(
            message="Unexpected error occurred",
            details={"component": "database"}
        )

        assert exc.message == "Unexpected error occurred"
        assert exc.error_code == ErrorCode.INTERNAL_ERROR
        assert exc.status_code == 500
        assert exc.severity == ErrorSeverity.ERROR

    def test_integration_error(self):
        """Test IntegrationError exception."""
        exc = IntegrationError(
            message="External service unavailable",
            service_name="payment_gateway",
            details={"timeout": True}
        )

        assert exc.message == "External service unavailable"
        assert exc.error_code == ErrorCode.INTEGRATION_ERROR
        assert exc.status_code == 502
        assert exc.severity == ErrorSeverity.ERROR
        assert exc.details["service_name"] == "payment_gateway"

    def test_service_unavailable_error(self):
        """Test ServiceUnavailableError exception."""
        exc = ServiceUnavailableError(
            message="Service temporarily down",
            retry_after=300
        )

        assert exc.message == "Service temporarily down"
        assert exc.error_code == ErrorCode.SERVICE_UNAVAILABLE
        assert exc.status_code == 503
        assert exc.severity == ErrorSeverity.ERROR
        assert exc.details["retry_after"] == 300

    def test_circuit_breaker_error(self):
        """Test CircuitBreakerError exception."""
        exc = CircuitBreakerError(
            message="Circuit breaker is open",
            service_name="external_api"
        )

        assert exc.message == "Circuit breaker is open"
        assert exc.error_code == ErrorCode.CIRCUIT_BREAKER_OPEN
        assert exc.status_code == 503
        assert exc.severity == ErrorSeverity.ERROR
        assert exc.details["service_name"] == "external_api"

    def test_timeout_error(self):
        """Test TimeoutError exception."""
        exc = TimeoutError(
            message="Operation timed out",
            timeout_seconds=30.0
        )

        assert exc.message == "Operation timed out"
        assert exc.error_code == ErrorCode.OPERATION_TIMEOUT
        assert exc.status_code == 504
        assert exc.severity == ErrorSeverity.ERROR
        assert exc.details["timeout_seconds"] == 30.0


class TestDomainSpecificErrors:
    """Test cases for domain-specific exceptions."""

    def test_configuration_error(self):
        """Test ConfigurationError exception."""
        exc = ConfigurationError(
            message="Invalid configuration",
            config_key="database_url"
        )

        assert exc.message == "Invalid configuration"
        assert exc.error_code == ErrorCode.CONFIGURATION_ERROR
        assert exc.status_code == 500
        assert exc.severity == ErrorSeverity.CRITICAL
        assert exc.details["config_key"] == "database_url"

    def test_cache_error(self):
        """Test CacheError exception."""
        exc = CacheError(
            message="Cache operation failed",
            cache_key="user:123",
            correlation_id="test-id"
        )

        assert exc.message == "Cache operation failed"
        assert exc.error_code == ErrorCode.CACHE_ERROR
        assert exc.status_code == 500
        assert exc.severity == ErrorSeverity.ERROR
        assert exc.details["cache_key"] == "user:123"

    def test_redis_error(self):
        """Test RedisError exception."""
        exc = RedisError(
            message="Redis operation failed",
            details={"operation": "SET"}
        )

        assert exc.message == "Redis operation failed"
        assert exc.error_code == ErrorCode.REDIS_ERROR
        assert exc.status_code == 500
        assert exc.severity == ErrorSeverity.ERROR

    def test_tws_connection_error(self):
        """Test TWSConnectionError exception."""
        exc = TWSConnectionError(
            message="TWS connection failed",
            details={"host": "api.tws.com"}
        )

        assert exc.message == "TWS connection failed"
        assert exc.error_code == ErrorCode.TWS_CONNECTION_ERROR
        assert exc.status_code == 502  # From IntegrationError
        assert exc.severity == ErrorSeverity.ERROR
        assert exc.details["service_name"] == "TWS"

    def test_llm_error(self):
        """Test LLMError exception."""
        exc = LLMError(
            message="LLM request failed",
            model_name="gpt-4",
            details={"tokens": 1500}
        )

        assert exc.message == "LLM request failed"
        assert exc.error_code == ErrorCode.LLM_ERROR
        assert exc.status_code == 502  # From IntegrationError
        assert exc.severity == ErrorSeverity.ERROR
        assert exc.details["service_name"] == "LLM"
        assert exc.details["model_name"] == "gpt-4"

    def test_database_error(self):
        """Test DatabaseError exception."""
        exc = DatabaseError(
            message="Database query failed",
            query="SELECT * FROM users WHERE id = ?",
            details={"connection": "primary"}
        )

        assert exc.message == "Database query failed"
        assert exc.error_code == ErrorCode.DATABASE_ERROR
        assert exc.status_code == 500
        assert exc.severity == ErrorSeverity.ERROR
        # Query should be sanitized for security
        assert exc.details["query_type"] == "SELECT"

    def test_file_processing_error(self):
        """Test FileProcessingError exception."""
        exc = FileProcessingError(
            message="Failed to process file",
            filename="document.pdf",
            details={"size": "10MB"}
        )

        assert exc.message == "Failed to process file"
        assert exc.error_code == ErrorCode.FILE_PROCESSING_ERROR
        assert exc.status_code == 500
        assert exc.severity == ErrorSeverity.ERROR
        assert exc.details["filename"] == "document.pdf"


class TestUtilities:
    """Test cases for utility functions."""

    def test_get_exception_by_error_code(self):
        """Test the get_exception_by_error_code function."""
        # Test known error codes
        assert get_exception_by_error_code(ErrorCode.VALIDATION_ERROR) == ValidationError
        assert get_exception_by_error_code(ErrorCode.AUTHENTICATION_FAILED) == AuthenticationError
        assert get_exception_by_error_code(ErrorCode.INTERNAL_ERROR) == InternalError
        assert get_exception_by_error_code(ErrorCode.CACHE_ERROR) == CacheError

        # Test that function handles all known error codes without error
        for error_code in ErrorCode:
            exception_class = get_exception_by_error_code(error_code)
            assert exception_class is not None
            assert issubclass(exception_class, BaseAppException)


class TestExceptionChaining:
    """Test cases for exception chaining and original exception preservation."""

    def test_original_exception_preserved(self):
        """Test that original exception is preserved in exception chain."""
        original = ValueError("Original error")
        exc = ValidationError(
            message="Validation failed",
            original_exception=original
        )

        assert exc.original_exception is original

    def test_exception_chain_in_dict(self):
        """Test that exception chain info is included in to_dict."""
        original = ValueError("Original error")
        exc = ValidationError(
            message="Validation failed",
            original_exception=original,
            correlation_id="test-id"
        )

        result = exc.to_dict()

        # Should include all standard fields
        assert result["message"] == "Validation failed"
        assert result["error_code"] == "VALIDATION_ERROR"
        assert result["status_code"] == 400
        assert result["correlation_id"] == "test-id"
        assert "timestamp" in result


class TestErrorSeverity:
    """Test cases for error severity levels."""

    def test_severity_levels(self):
        """Test that different exception types have appropriate severity levels."""
        # Client errors should be WARNING or INFO
        validation_exc = ValidationError("Invalid input")
        assert validation_exc.severity == ErrorSeverity.WARNING

        not_found_exc = ResourceNotFoundError("Not found")
        assert not_found_exc.severity == ErrorSeverity.INFO

        # Server errors should be ERROR
        internal_exc = InternalError("Server error")
        assert internal_exc.severity == ErrorSeverity.ERROR

        # Configuration errors should be CRITICAL
        config_exc = ConfigurationError("Config error")
        assert config_exc.severity == ErrorSeverity.CRITICAL


class TestCorrelationId:
    """Test cases for correlation ID propagation."""

    def test_correlation_id_propagation(self):
        """Test that correlation ID is properly set and propagated."""
        correlation_id = "test-correlation-123"

        exc = BaseAppException(
            message="Test error",
            correlation_id=correlation_id
        )

        assert exc.correlation_id == correlation_id

        # Should be included in to_dict
        result = exc.to_dict()
        assert result["correlation_id"] == correlation_id

    def test_correlation_id_optional(self):
        """Test that correlation ID is optional."""
        exc = BaseAppException(
            message="Test error without correlation ID"
        )

        assert exc.correlation_id is None

        result = exc.to_dict()
        assert result["correlation_id"] is None


class TestExceptionInheritance:
    """Test cases for exception inheritance and polymorphism."""

    def test_inheritance_hierarchy(self):
        """Test that exception inheritance works correctly."""
        # Test that specific exceptions are instances of base class
        validation_exc = ValidationError("Test")
        assert isinstance(validation_exc, BaseAppException)
        assert isinstance(validation_exc, Exception)

        # Test that domain-specific exceptions inherit correctly
        tws_exc = TWSConnectionError("TWS error")
        assert isinstance(tws_exc, IntegrationError)
        assert isinstance(tws_exc, BaseAppException)

        # Test Redis error inheritance
        redis_conn_exc = RedisConnectionError("Connection failed")
        assert isinstance(redis_conn_exc, RedisInitializationError)
        assert isinstance(redis_conn_exc, RedisError)
        assert isinstance(redis_conn_exc, BaseAppException)

    def test_polymorphic_behavior(self):
        """Test that exceptions behave correctly polymorphically."""
        exceptions = [
            ValidationError("Validation failed"),
            AuthenticationError("Auth failed"),
            InternalError("Server error"),
            ConfigurationError("Config error")
        ]

        for exc in exceptions:
            # All should be BaseAppException instances
            assert isinstance(exc, BaseAppException)

            # All should have to_dict method
            result = exc.to_dict()
            assert isinstance(result, dict)
            assert "message" in result
            assert "error_code" in result
            assert "status_code" in result


class TestEdgeCases:
    """Test cases for edge cases and error conditions."""

    def test_empty_message(self):
        """Test exception with empty message."""
        exc = BaseAppException(message="")
        assert exc.message == ""
        assert str(exc) is not None  # Should not fail

    def test_none_details(self):
        """Test exception with None details."""
        exc = BaseAppException(
            message="Test",
            details=None
        )
        assert exc.details == {}

    def test_large_details_dict(self):
        """Test exception with large details dictionary."""
        large_details = {f"key_{i}": f"value_{i}" for i in range(100)}

        exc = BaseAppException(
            message="Test with large details",
            details=large_details
        )

        assert exc.details == large_details
        result = exc.to_dict()
        assert result["details"] == large_details

    def test_special_characters_in_message(self):
        """Test exception with special characters in message."""
        special_message = "Error with spécial çharácters: àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ"

        exc = BaseAppException(message=special_message)
        assert exc.message == special_message

        result = exc.to_dict()
        assert result["message"] == special_message

    def test_very_long_correlation_id(self):
        """Test exception with very long correlation ID."""
        long_id = "x" * 1000

        exc = BaseAppException(
            message="Test",
            correlation_id=long_id
        )

        assert exc.correlation_id == long_id

        result = exc.to_dict()
        assert result["correlation_id"] == long_id