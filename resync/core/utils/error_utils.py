"""Utility helpers for standardized error responses."""

from __future__ import annotations

import uuid
from typing import Any, Iterable, List

try:  # FastAPI is optional for some runtimes
    from fastapi.exceptions import RequestValidationError
except ImportError:  # pragma: no cover
    RequestValidationError = None  # type: ignore

from resync.models.error_models import (
    AuthenticationErrorResponse,
    BaseErrorResponse,
    ErrorCategory,
    ErrorSeverity,
    ValidationErrorResponse,
)
from resync.utils.exceptions import (
    BaseAppException,
    ErrorCode,
    ErrorSeverity as ExceptionSeverity,
    InvalidConfigError,
    NotFoundError,
    ResyncException,
    TWSConnectionError,
)


ERROR_CATEGORY_STATUS_MAP: dict[ErrorCategory, int] = {
    ErrorCategory.VALIDATION: 400,
    ErrorCategory.AUTHENTICATION: 401,
    ErrorCategory.AUTHORIZATION: 403,
    ErrorCategory.BUSINESS_LOGIC: 404,
    ErrorCategory.RATE_LIMIT: 429,
    ErrorCategory.EXTERNAL_SERVICE: 503,
    ErrorCategory.SYSTEM: 500,
}

ERROR_CODE_CATEGORY_MAP: dict[ErrorCode, ErrorCategory] = {
    ErrorCode.VALIDATION_ERROR: ErrorCategory.VALIDATION,
    ErrorCode.INVALID_INPUT: ErrorCategory.VALIDATION,
    ErrorCode.INVALID_CONFIGURATION: ErrorCategory.VALIDATION,
    ErrorCode.CONFIGURATION_ERROR: ErrorCategory.SYSTEM,
    ErrorCode.MISSING_CONFIGURATION: ErrorCategory.SYSTEM,
    ErrorCode.RESOURCE_NOT_FOUND: ErrorCategory.BUSINESS_LOGIC,
    ErrorCode.BUSINESS_RULE_VIOLATION: ErrorCategory.BUSINESS_LOGIC,
    ErrorCode.EXTERNAL_SERVICE_ERROR: ErrorCategory.EXTERNAL_SERVICE,
    ErrorCode.TWS_CONNECTION_ERROR: ErrorCategory.EXTERNAL_SERVICE,
    ErrorCode.RATE_LIMIT_EXCEEDED: ErrorCategory.RATE_LIMIT,
    ErrorCode.SERVICE_UNAVAILABLE: ErrorCategory.EXTERNAL_SERVICE,
    ErrorCode.INTERNAL_ERROR: ErrorCategory.SYSTEM,
}


def generate_correlation_id() -> str:
    """Generate a new correlation identifier."""
    return str(uuid.uuid4())


def get_error_status_code(category: ErrorCategory) -> int:
    """Map an error category to an HTTP status code."""
    return ERROR_CATEGORY_STATUS_MAP.get(category, 500)


def extract_validation_errors(
    exc: RequestValidationError | Exception,
) -> List[dict[str, Any]]:
    """Extract validation errors from a FastAPI RequestValidationError."""
    if RequestValidationError is not None and isinstance(
        exc, RequestValidationError
    ):
        return exc.errors()
    return []


def _map_severity(severity: ExceptionSeverity | None) -> ErrorSeverity:
    if severity is None:
        return ErrorSeverity.MEDIUM
    try:
        return ErrorSeverity[severity.name]
    except KeyError:
        return ErrorSeverity.MEDIUM


def _resolve_category(error_code: ErrorCode | None) -> ErrorCategory:
    if error_code is None:
        return ErrorCategory.SYSTEM
    return ERROR_CODE_CATEGORY_MAP.get(error_code, ErrorCategory.SYSTEM)


def create_error_response_from_exception(
    exc: Exception,
    *,
    correlation_id: str | None = None,
) -> BaseErrorResponse:
    """Create a standardized error response from an exception."""
    correlation_id = correlation_id or generate_correlation_id()

    if isinstance(exc, NotFoundError):
        return BaseErrorResponse(
            error_code=ErrorCode.RESOURCE_NOT_FOUND.value,
            message=str(exc),
            correlation_id=correlation_id,
            category=ErrorCategory.BUSINESS_LOGIC,
            severity=_map_severity(getattr(exc, "severity", None)),
            user_friendly_message="Resource not found.",
            troubleshooting_hints=["Verify the provided identifier."],
        )

    if isinstance(exc, InvalidConfigError):
        return ValidationErrorResponse(
            error_code="VALIDATION_ERROR",
            message=str(exc),
            correlation_id=correlation_id,
            category=ErrorCategory.VALIDATION,
            details=[],
            severity=ErrorSeverity.MEDIUM,
            user_friendly_message="Invalid configuration detected.",
            troubleshooting_hints=["Review configuration values."],
        )

    if isinstance(exc, TWSConnectionError):
        return BaseErrorResponse(
            error_code="EXTERNAL_SERVICE_ERROR",
            message=str(exc),
            correlation_id=correlation_id,
            category=ErrorCategory.EXTERNAL_SERVICE,
            severity=_map_severity(getattr(exc, "severity", None)),
            user_friendly_message="External service is unavailable.",
            troubleshooting_hints=["Check TWS connectivity.", "Retry later."],
        )

    if isinstance(exc, BaseAppException):
        error_code = (
            exc.error_code.value
            if isinstance(exc.error_code, ErrorCode)
            else str(exc.error_code)
        )
        category = _resolve_category(
            exc.error_code if isinstance(exc.error_code, ErrorCode) else None
        )
        severity = _map_severity(getattr(exc, "severity", None))
        hints = None
        details = getattr(exc, "details", {})
        if isinstance(details, dict):
            hints = details.get("troubleshooting_hints")
        return BaseErrorResponse(
            error_code=error_code,
            message=str(exc),
            correlation_id=exc.correlation_id or correlation_id,
            category=category,
            severity=severity,
            user_friendly_message=getattr(
                exc, "user_friendly_message", str(exc)
            ),
            troubleshooting_hints=hints,
        )

    if isinstance(exc, ResyncException):  # pragma: no cover - alias safety
        return BaseErrorResponse(
            error_code="RESYNC_EXCEPTION",
            message=str(exc),
            correlation_id=correlation_id,
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.MEDIUM,
        )

    # Fallback for generic exceptions
    return BaseErrorResponse(
        error_code="INTERNAL_ERROR",
        message=str(exc),
        correlation_id=correlation_id,
        category=ErrorCategory.SYSTEM,
        severity=ErrorSeverity.MEDIUM,
        user_friendly_message="An unexpected error occurred.",
    )


class ErrorResponseBuilder:
    """Helper for building standardized error responses with shared context."""

    def __init__(self, correlation_id: str | None = None) -> None:
        self._correlation_id = correlation_id or generate_correlation_id()
        self._path: str | None = None
        self._method: str | None = None

    @property
    def correlation_id(self) -> str:
        return self._correlation_id

    def with_correlation_id(self, correlation_id: str) -> "ErrorResponseBuilder":
        self._correlation_id = correlation_id
        return self

    def with_request_context(
        self, *, path: str | None = None, method: str | None = None
    ) -> "ErrorResponseBuilder":
        self._path = path
        self._method = method
        return self

    def build_validation_error(
        self, errors: Iterable[dict[str, Any]]
    ) -> ValidationErrorResponse:
        """Build a validation error response from Pydantic-style errors."""
        error_list = list(errors)
        return ValidationErrorResponse.from_pydantic_errors(
            error_list,
            correlation_id=self._correlation_id,
            path=self._path,
            method=self._method,
        )

    def build_authentication_error(self) -> AuthenticationErrorResponse:
        """Build an authentication error response."""
        return AuthenticationErrorResponse.unauthorized(
            correlation_id=self._correlation_id,
            path=self._path,
            method=self._method,
        )


__all__ = [
    "ErrorResponseBuilder",
    "create_error_response_from_exception",
    "extract_validation_errors",
    "generate_correlation_id",
    "get_error_status_code",
]
