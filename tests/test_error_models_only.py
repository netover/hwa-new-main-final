"""Unit tests for error models only, without importing the full application."""

import pytest

from resync.models.error_models import (
    AuthenticationErrorResponse,
    AuthorizationErrorResponse,
    BaseErrorResponse,
    BusinessLogicErrorResponse,
    ErrorCategory,
    ErrorSeverity,
    ExternalServiceErrorResponse,
    RateLimitErrorResponse,
    SystemErrorResponse,
    ValidationErrorDetail,
    ValidationErrorResponse,
)


def test_base_error_response_creation():
    """Test basic error response creation."""
    error = BaseErrorResponse(
        error_code="TEST_ERROR",
        message="Test error message",
        category=ErrorCategory.SYSTEM,
    )

    assert error.error_code == "TEST_ERROR"
    assert error.message == "Test error message"
    assert error.category == ErrorCategory.SYSTEM
    assert error.severity == ErrorSeverity.MEDIUM
    assert error.timestamp is not None
    assert len(error.correlation_id) == 36  # UUID format


def test_validation_error_response_from_pydantic_errors():
    """Test validation error response creation from Pydantic errors."""
    pydantic_errors = [
        {"loc": ["field1"], "msg": "Field required", "type": "missing", "input": None}
    ]

    error_response = ValidationErrorResponse.from_pydantic_errors(
        pydantic_errors, correlation_id="test-123"
    )

    assert error_response.error_code == "VALIDATION_ERROR"
    assert len(error_response.details) == 1
    assert error_response.details[0].field == "field1"
    assert error_response.details[0].message == "Field required"
    assert error_response.correlation_id == "test-123"
    assert error_response.category == ErrorCategory.VALIDATION


def test_authentication_error_response_factories():
    """Test authentication error response factory methods."""
    unauthorized = AuthenticationErrorResponse.unauthorized(correlation_id="test-123")
    assert unauthorized.error_code == "UNAUTHORIZED"
    assert unauthorized.category == ErrorCategory.AUTHENTICATION
    assert unauthorized.correlation_id == "test-123"

    invalid_creds = AuthenticationErrorResponse.invalid_credentials(
        correlation_id="test-456"
    )
    assert invalid_creds.error_code == "INVALID_CREDENTIALS"
    assert invalid_creds.category == ErrorCategory.AUTHENTICATION
    assert len(invalid_creds.troubleshooting_hints) >= 1


def test_authorization_error_response_factories():
    """Test authorization error response factory methods."""
    forbidden = AuthorizationErrorResponse.forbidden("users", correlation_id="test-123")
    assert forbidden.error_code == "FORBIDDEN"
    assert forbidden.category == ErrorCategory.AUTHORIZATION
    assert "users" in forbidden.message

    insufficient = AuthorizationErrorResponse.insufficient_permissions(
        ["admin", "write"], ["read"], correlation_id="test-456"
    )
    assert insufficient.error_code == "INSUFFICIENT_PERMISSIONS"
    assert insufficient.required_permissions == ["admin", "write"]
    assert insufficient.user_permissions == ["read"]


def test_business_logic_error_response_factories():
    """Test business logic error response factory methods."""
    not_found = BusinessLogicErrorResponse.resource_not_found(
        "User", "user123", correlation_id="test-123"
    )
    assert not_found.error_code == "RESOURCE_NOT_FOUND"
    assert not_found.category == ErrorCategory.BUSINESS_LOGIC
    assert "User not found: user123" in not_found.message
    assert not_found.entity_type == "User"
    assert not_found.entity_id == "user123"

    invalid_state = BusinessLogicErrorResponse.invalid_state(
        "Order", "order456", "cancelled", correlation_id="test-456"
    )
    assert invalid_state.error_code == "INVALID_STATE"
    assert invalid_state.category == ErrorCategory.BUSINESS_LOGIC
    assert invalid_state.entity_type == "Order"
    assert invalid_state.entity_id == "order456"


def test_system_error_response_factories():
    """Test system error response factory methods."""
    internal_error = SystemErrorResponse.internal_error(
        "database", correlation_id="test-123"
    )
    assert internal_error.error_code == "INTERNAL_SERVER_ERROR"
    assert internal_error.category == ErrorCategory.SYSTEM
    assert internal_error.component == "database"
    assert len(internal_error.troubleshooting_hints) >= 1

    config_error = SystemErrorResponse.configuration_error(
        "cache", "redis_url", correlation_id="test-456"
    )
    assert config_error.error_code == "CONFIGURATION_ERROR"
    assert config_error.category == ErrorCategory.SYSTEM
    assert config_error.component == "cache"


def test_external_service_error_response_factories():
    """Test external service error response factory methods."""
    service_unavailable = ExternalServiceErrorResponse.service_unavailable(
        "TWS", correlation_id="test-123"
    )
    assert service_unavailable.error_code == "SERVICE_UNAVAILABLE"
    assert service_unavailable.category == ErrorCategory.EXTERNAL_SERVICE
    assert service_unavailable.service_name == "TWS"

    service_error = ExternalServiceErrorResponse.service_error(
        "TWS", "CONNECTION_TIMEOUT", "Connection timed out", correlation_id="test-456"
    )
    assert service_error.error_code == "EXTERNAL_SERVICE_ERROR"
    assert service_error.service_name == "TWS"
    assert service_error.service_error_code == "CONNECTION_TIMEOUT"
    assert service_error.service_error_message == "Connection timed out"


def test_rate_limit_error_response_factories():
    """Test rate limit error response factory methods."""
    rate_limit = RateLimitErrorResponse.rate_limit_exceeded(
        100, "1 hour", 1800, correlation_id="test-123"
    )
    assert rate_limit.error_code == "RATE_LIMIT_EXCEEDED"
    assert rate_limit.category == ErrorCategory.RATE_LIMIT
    assert rate_limit.limit == 100
    assert rate_limit.window == "1 hour"
    assert rate_limit.retry_after == 1800


def test_error_response_json_serialization():
    """Test error response JSON serialization."""
    error = BaseErrorResponse(
        error_code="TEST_ERROR",
        message="Test error message",
        category=ErrorCategory.SYSTEM,
        correlation_id="test-123",
    )

    json_data = error.model_dump()
    assert json_data["error_code"] == "TEST_ERROR"
    assert json_data["message"] == "Test error message"
    assert json_data["category"] == "SYSTEM"
    assert json_data["correlation_id"] == "test-123"
    assert "timestamp" in json_data


def test_validation_error_detail():
    """Test validation error detail model."""
    detail = ValidationErrorDetail(
        field="username", message="Field required", value=None, location="body"
    )

    assert detail.field == "username"
    assert detail.message == "Field required"
    assert detail.value is None
    assert detail.location == "body"


if __name__ == "__main__":
    pytest.main([__file__])




