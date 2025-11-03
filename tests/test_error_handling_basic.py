"""Basic unit tests for the standardized error handling system."""

import pytest
from fastapi.exceptions import RequestValidationError

from resync.core.exceptions import (
    InvalidConfigError,
    NotFoundError,
    ResyncException,
    TWSConnectionError,
)
from resync.core.utils.error_utils import (
    ErrorResponseBuilder,
    create_error_response_from_exception,
    extract_validation_errors,
    generate_correlation_id,
    get_error_status_code,
)
from resync.models.error_models import (
    AuthenticationErrorResponse,
    BaseErrorResponse,
    ErrorCategory,
    ErrorSeverity,
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
    assert error_response.correlation_id == "test-123"


def test_authentication_error_response_factories():
    """Test authentication error response factory methods."""
    unauthorized = AuthenticationErrorResponse.unauthorized(correlation_id="test-123")
    assert unauthorized.error_code == "UNAUTHORIZED"
    assert unauthorized.category == ErrorCategory.AUTHENTICATION


def test_error_response_builder():
    """Test error response builder functionality."""
    builder = ErrorResponseBuilder()
    builder.with_correlation_id("test-123")

    validation_errors = [
        {"loc": ["field1"], "msg": "Field required", "type": "missing"}
    ]
    error_response = builder.build_validation_error(validation_errors)

    assert error_response.error_code == "VALIDATION_ERROR"
    assert len(error_response.details) == 1
    assert error_response.correlation_id == "test-123"


def test_generate_correlation_id():
    """Test correlation ID generation."""
    correlation_id1 = generate_correlation_id()
    correlation_id2 = generate_correlation_id()

    assert correlation_id1 != correlation_id2
    assert len(correlation_id1) == 36  # UUID format


def test_extract_validation_errors():
    """Test extracting validation errors from RequestValidationError."""
    exc = RequestValidationError(
        [{"loc": ["field1"], "msg": "Field required", "type": "missing", "input": None}]
    )

    errors = extract_validation_errors(exc)
    assert len(errors) == 1
    assert errors[0]["loc"] == ["field1"]
    assert errors[0]["msg"] == "Field required"


@pytest.mark.parametrize(
    "error_category,expected_status",
    [
        (ErrorCategory.VALIDATION, 400),
        (ErrorCategory.AUTHENTICATION, 401),
        (ErrorCategory.AUTHORIZATION, 403),
        (ErrorCategory.BUSINESS_LOGIC, 404),
        (ErrorCategory.SYSTEM, 500),
        (ErrorCategory.EXTERNAL_SERVICE, 503),
        (ErrorCategory.RATE_LIMIT, 429),
    ],
)
def test_get_error_status_code(error_category, expected_status):
    """Test HTTP status code mapping from error categories."""
    assert get_error_status_code(error_category) == expected_status


def test_create_error_response_from_exception_resync_exceptions():
    """Test creating error responses from Resync exceptions."""
    # Test NotFoundError
    not_found_exc = NotFoundError("User", "user123")
    response = create_error_response_from_exception(not_found_exc)
    assert response.error_code == "RESOURCE_NOT_FOUND"
    assert response.category == ErrorCategory.BUSINESS_LOGIC

    # Test InvalidConfigError
    config_exc = InvalidConfigError("Invalid configuration")
    response = create_error_response_from_exception(config_exc)
    assert response.error_code == "VALIDATION_ERROR"

    # Test TWSConnectionError
    tws_exc = TWSConnectionError("Connection failed")
    response = create_error_response_from_exception(tws_exc)
    assert response.error_code == "EXTERNAL_SERVICE_ERROR"


def test_resync_exception_base_class():
    """Test enhanced ResyncException base class."""
    exc = ResyncException("Test message")

    assert exc.message == "Test message"
    assert exc.error_code == "RESYNC_EXCEPTION"
    assert exc.error_category == "SYSTEM"
    assert exc.severity == "MEDIUM"
    assert (
        exc.user_friendly_message == "An error occurred while processing your request."
    )
    assert len(exc.troubleshooting_hints) == 2
    assert exc.details == {}
    assert exc.timestamp is not None


def test_not_found_error_enhanced():
    """Test enhanced NotFoundError with resource information."""
    exc = NotFoundError("User", "user123")

    assert "User not found: user123" in exc.message
    assert exc.error_code == "NOT_FOUND_ERROR"
    assert exc.error_category == "BUSINESS_LOGIC"
    assert exc.details["resource"] == "User"
    assert exc.details["identifier"] == "user123"


def test_tws_connection_error_enhanced():
    """Test enhanced TWSConnectionError."""
    exc = TWSConnectionError("Connection failed")

    assert exc.error_code == "TWS_CONNECTION_ERROR"
    assert exc.error_category == "EXTERNAL_SERVICE"
    assert exc.severity == "HIGH"
    assert "Unable to connect to the TWS service" in exc.user_friendly_message
    assert len(exc.troubleshooting_hints) >= 3


if __name__ == "__main__":
    pytest.main([__file__])




