"""Testes para o módulo de exceções customizadas."""

from datetime import datetime

import pytest

from resync.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BaseAppException,
    BusinessError,
    CacheError,
    CircuitBreakerError,
    ConfigurationError,
    DatabaseError,
    ErrorCode,
    ErrorSeverity,
    IntegrationError,
    InternalError,
    LLMError,
    RateLimitError,
    ResourceConflictError,
    ResourceNotFoundError,
    ServiceUnavailableError,
    TimeoutError,
    TWSConnectionError,
    ValidationError,
    get_exception_by_error_code,
)


class TestBaseAppException:
    """Testes para a exceção base."""

    def test_basic_initialization(self):
        """Testa inicialização básica."""
        exc = BaseAppException(
            message="Test error", error_code=ErrorCode.INTERNAL_ERROR
        )

        assert exc.message == "Test error"
        assert exc.error_code == ErrorCode.INTERNAL_ERROR
        assert exc.status_code == 500
        assert exc.details == {}
        assert exc.correlation_id is None
        assert exc.severity == ErrorSeverity.ERROR
        assert isinstance(exc.timestamp, datetime)

    def test_full_initialization(self):
        """Testa inicialização com todos os parâmetros."""
        details = {"key": "value"}
        correlation_id = "test-correlation-id"
        original_exc = ValueError("Original error")

        exc = BaseAppException(
            message="Test error",
            error_code=ErrorCode.VALIDATION_ERROR,
            status_code=400,
            details=details,
            correlation_id=correlation_id,
            severity=ErrorSeverity.WARNING,
            original_exception=original_exc,
        )

        assert exc.message == "Test error"
        assert exc.error_code == ErrorCode.VALIDATION_ERROR
        assert exc.status_code == 400
        assert exc.details == details
        assert exc.correlation_id == correlation_id
        assert exc.severity == ErrorSeverity.WARNING
        assert exc.original_exception == original_exc

    def test_to_dict(self):
        """Testa conversão para dicionário."""
        exc = BaseAppException(
            message="Test error",
            error_code=ErrorCode.INTERNAL_ERROR,
            correlation_id="test-id",
        )

        result = exc.to_dict()

        assert result["message"] == "Test error"
        assert result["error_code"] == "INTERNAL_ERROR"
        assert result["status_code"] == 500
        assert result["correlation_id"] == "test-id"
        assert result["severity"] == "error"
        assert "timestamp" in result

    def test_str_representation(self):
        """Testa representação em string."""
        exc = BaseAppException(
            message="Test error",
            error_code=ErrorCode.INTERNAL_ERROR,
            correlation_id="test-id",
        )

        str_repr = str(exc)

        assert "BaseAppException" in str_repr
        assert "Test error" in str_repr
        assert "INTERNAL_ERROR" in str_repr
        assert "500" in str_repr
        assert "test-id" in str_repr


class TestClientErrors:
    """Testes para exceções de cliente (4xx)."""

    def test_validation_error(self):
        """Testa ValidationError."""
        exc = ValidationError(
            message="Invalid input",
            details={"field": "email"},
            correlation_id="test-id",
        )

        assert exc.status_code == 400
        assert exc.error_code == ErrorCode.VALIDATION_ERROR
        assert exc.severity == ErrorSeverity.WARNING
        assert exc.details["field"] == "email"

    def test_authentication_error(self):
        """Testa AuthenticationError."""
        exc = AuthenticationError(
            message="Invalid credentials", correlation_id="test-id"
        )

        assert exc.status_code == 401
        assert exc.error_code == ErrorCode.AUTHENTICATION_FAILED
        assert exc.severity == ErrorSeverity.WARNING

    def test_authorization_error(self):
        """Testa AuthorizationError."""
        exc = AuthorizationError(
            message="Insufficient permissions", correlation_id="test-id"
        )

        assert exc.status_code == 403
        assert exc.error_code == ErrorCode.AUTHORIZATION_FAILED
        assert exc.severity == ErrorSeverity.WARNING

    def test_resource_not_found_error(self):
        """Testa ResourceNotFoundError."""
        exc = ResourceNotFoundError(
            message="User not found",
            resource_type="User",
            resource_id="123",
            correlation_id="test-id",
        )

        assert exc.status_code == 404
        assert exc.error_code == ErrorCode.RESOURCE_NOT_FOUND
        assert exc.severity == ErrorSeverity.INFO
        assert exc.details["resource_type"] == "User"
        assert exc.details["resource_id"] == "123"

    def test_resource_conflict_error(self):
        """Testa ResourceConflictError."""
        exc = ResourceConflictError(
            message="Resource already exists", correlation_id="test-id"
        )

        assert exc.status_code == 409
        assert exc.error_code == ErrorCode.RESOURCE_CONFLICT
        assert exc.severity == ErrorSeverity.WARNING

    def test_business_error(self):
        """Testa BusinessError."""
        exc = BusinessError(message="Business rule violated", correlation_id="test-id")

        assert exc.status_code == 422
        assert exc.error_code == ErrorCode.BUSINESS_RULE_VIOLATION
        assert exc.severity == ErrorSeverity.WARNING

    def test_rate_limit_error(self):
        """Testa RateLimitError."""
        exc = RateLimitError(
            message="Too many requests", retry_after=60, correlation_id="test-id"
        )

        assert exc.status_code == 429
        assert exc.error_code == ErrorCode.RATE_LIMIT_EXCEEDED
        assert exc.severity == ErrorSeverity.WARNING
        assert exc.details["retry_after"] == 60


class TestServerErrors:
    """Testes para exceções de servidor (5xx)."""

    def test_internal_error(self):
        """Testa InternalError."""
        exc = InternalError(message="Unexpected error", correlation_id="test-id")

        assert exc.status_code == 500
        assert exc.error_code == ErrorCode.INTERNAL_ERROR
        assert exc.severity == ErrorSeverity.ERROR

    def test_integration_error(self):
        """Testa IntegrationError."""
        exc = IntegrationError(
            message="External service failed",
            service_name="PaymentGateway",
            correlation_id="test-id",
        )

        assert exc.status_code == 502
        assert exc.error_code == ErrorCode.INTEGRATION_ERROR
        assert exc.severity == ErrorSeverity.ERROR
        assert exc.details["service_name"] == "PaymentGateway"

    def test_service_unavailable_error(self):
        """Testa ServiceUnavailableError."""
        exc = ServiceUnavailableError(
            message="Service down", retry_after=120, correlation_id="test-id"
        )

        assert exc.status_code == 503
        assert exc.error_code == ErrorCode.SERVICE_UNAVAILABLE
        assert exc.severity == ErrorSeverity.ERROR
        assert exc.details["retry_after"] == 120

    def test_circuit_breaker_error(self):
        """Testa CircuitBreakerError."""
        exc = CircuitBreakerError(
            message="Circuit breaker open",
            service_name="ExternalAPI",
            correlation_id="test-id",
        )

        assert exc.status_code == 503
        assert exc.error_code == ErrorCode.CIRCUIT_BREAKER_OPEN
        assert exc.severity == ErrorSeverity.ERROR
        assert exc.details["service_name"] == "ExternalAPI"

    def test_timeout_error(self):
        """Testa TimeoutError."""
        exc = TimeoutError(
            message="Operation timed out",
            timeout_seconds=30.0,
            correlation_id="test-id",
        )

        assert exc.status_code == 504
        assert exc.error_code == ErrorCode.OPERATION_TIMEOUT
        assert exc.severity == ErrorSeverity.ERROR
        assert exc.details["timeout_seconds"] == 30.0


class TestDomainSpecificErrors:
    """Testes para exceções específicas do domínio."""

    def test_configuration_error(self):
        """Testa ConfigurationError."""
        exc = ConfigurationError(
            message="Invalid config",
            config_key="database.url",
            correlation_id="test-id",
        )

        assert exc.status_code == 500
        assert exc.error_code == ErrorCode.CONFIGURATION_ERROR
        assert exc.severity == ErrorSeverity.CRITICAL
        assert exc.details["config_key"] == "database.url"

    def test_tws_connection_error(self):
        """Testa TWSConnectionError."""
        exc = TWSConnectionError(
            message="TWS connection failed", correlation_id="test-id"
        )

        assert exc.status_code == 502
        assert exc.error_code == ErrorCode.TWS_CONNECTION_ERROR
        assert exc.severity == ErrorSeverity.ERROR
        assert exc.details["service_name"] == "TWS"

    def test_llm_error(self):
        """Testa LLMError."""
        exc = LLMError(
            message="LLM request failed", model_name="gpt-4", correlation_id="test-id"
        )

        assert exc.status_code == 502
        assert exc.error_code == ErrorCode.LLM_ERROR
        assert exc.severity == ErrorSeverity.ERROR
        assert exc.details["service_name"] == "LLM"
        assert exc.details["model_name"] == "gpt-4"

    def test_database_error(self):
        """Testa DatabaseError."""
        exc = DatabaseError(
            message="Query failed",
            query="SELECT * FROM users",
            correlation_id="test-id",
        )

        assert exc.status_code == 500
        assert exc.error_code == ErrorCode.DATABASE_ERROR
        assert exc.severity == ErrorSeverity.ERROR
        assert exc.details["query_type"] == "SELECT"

    def test_cache_error(self):
        """Testa CacheError."""
        exc = CacheError(
            message="Cache operation failed",
            cache_key="user:123",
            correlation_id="test-id",
        )

        assert exc.status_code == 500
        assert exc.error_code == ErrorCode.CACHE_ERROR
        assert exc.severity == ErrorSeverity.WARNING
        assert exc.details["cache_key"] == "user:123"


class TestUtilities:
    """Testes para funções utilitárias."""

    def test_get_exception_by_error_code(self):
        """Testa get_exception_by_error_code."""
        assert (
            get_exception_by_error_code(ErrorCode.VALIDATION_ERROR) == ValidationError
        )
        assert (
            get_exception_by_error_code(ErrorCode.AUTHENTICATION_FAILED)
            == AuthenticationError
        )
        assert (
            get_exception_by_error_code(ErrorCode.RESOURCE_NOT_FOUND)
            == ResourceNotFoundError
        )
        assert (
            get_exception_by_error_code(ErrorCode.RATE_LIMIT_EXCEEDED) == RateLimitError
        )
        assert (
            get_exception_by_error_code(ErrorCode.INTEGRATION_ERROR) == IntegrationError
        )
        assert (
            get_exception_by_error_code(ErrorCode.CIRCUIT_BREAKER_OPEN)
            == CircuitBreakerError
        )
        assert get_exception_by_error_code(ErrorCode.DATABASE_ERROR) == DatabaseError

        # Código não mapeado deve retornar InternalError
        assert (
            get_exception_by_error_code(ErrorCode.UNHANDLED_EXCEPTION) == InternalError
        )


class TestExceptionChaining:
    """Testes para encadeamento de exceções."""

    def test_original_exception_preserved(self):
        """Testa que a exceção original é preservada."""
        original = ValueError("Original error")

        exc = ValidationError(message="Validation failed", original_exception=original)

        assert exc.original_exception == original
        assert isinstance(exc.original_exception, ValueError)

    def test_exception_chain_in_dict(self):
        """Testa que to_dict não inclui original_exception."""
        original = ValueError("Original error")

        exc = ValidationError(message="Validation failed", original_exception=original)

        result = exc.to_dict()

        # original_exception não deve estar no dict (pode conter dados sensíveis)
        assert "original_exception" not in result


class TestErrorSeverity:
    """Testes para níveis de severidade."""

    def test_severity_levels(self):
        """Testa diferentes níveis de severidade."""
        critical_exc = ConfigurationError(message="Config error")
        assert critical_exc.severity == ErrorSeverity.CRITICAL

        error_exc = InternalError(message="Internal error")
        assert error_exc.severity == ErrorSeverity.ERROR

        warning_exc = ValidationError(message="Validation error")
        assert warning_exc.severity == ErrorSeverity.WARNING

        info_exc = ResourceNotFoundError(message="Not found")
        assert info_exc.severity == ErrorSeverity.INFO


class TestCorrelationId:
    """Testes para correlation ID."""

    def test_correlation_id_propagation(self):
        """Testa que correlation ID é propagado."""
        correlation_id = "test-correlation-123"

        exc = ValidationError(message="Test error", correlation_id=correlation_id)

        assert exc.correlation_id == correlation_id

        # Deve estar no dict também
        result = exc.to_dict()
        assert result["correlation_id"] == correlation_id

    def test_correlation_id_optional(self):
        """Testa que correlation ID é opcional."""
        exc = ValidationError(message="Test error")

        assert exc.correlation_id is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
