"""Enhanced exception classes with error codes and categories for standardized error handling."""

from datetime import datetime
from typing import Any, Dict, Optional


class ResyncException(Exception):
    """Enhanced base class for all custom exceptions in Resync with error codes and categories."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        error_category: Optional[str] = None,
        severity: Optional[str] = None,
        user_friendly_message: Optional[str] = None,
        troubleshooting_hints: Optional[list[str]] = None,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ):
        """
        Initialize the exception with enhanced error information.

        Args:
            message: Technical error message for logging/debugging
            error_code: Unique error code for identification
            error_category: Error category (validation, authentication, business_logic, etc.)
            severity: Error severity level (low, medium, high, critical)
            user_friendly_message: User-friendly error message for API responses
            troubleshooting_hints: List of troubleshooting suggestions
            details: Additional error details
            original_exception: The original exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self._generate_error_code()
        self.error_category = error_category or self._get_default_category()
        self.severity = severity or self._get_default_severity()
        self.user_friendly_message = (
            user_friendly_message or self._get_default_user_message()
        )
        self.troubleshooting_hints = (
            troubleshooting_hints or self._get_default_troubleshooting_hints()
        )
        self.details = details or {}
        self.original_exception = original_exception
        self.timestamp = datetime.utcnow()

    def _generate_error_code(self) -> str:
        """Generate a default error code based on the exception class name."""
        class_name = self.__class__.__name__
        # Convert CamelCase to UPPER_SNAKE_CASE
        import re

        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", class_name)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).upper()

    def _get_default_category(self) -> str:
        """Get the default error category for this exception type."""
        return "SYSTEM"

    def _get_default_severity(self) -> str:
        """Get the default severity for this exception type."""
        return "MEDIUM"

    def _get_default_user_message(self) -> str:
        """Get the default user-friendly message for this exception type."""
        return "An error occurred while processing your request."

    def _get_default_troubleshooting_hints(self) -> list[str]:
        """Get default troubleshooting hints for this exception type."""
        return ["Please try again later.", "Contact support if the issue persists."]

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for serialization."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "error_category": self.error_category,
            "severity": self.severity,
            "user_friendly_message": self.user_friendly_message,
            "troubleshooting_hints": self.troubleshooting_hints,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "exception_type": self.__class__.__name__,
        }


class ConfigurationError(ResyncException):
    """Exception for configuration errors."""

    def _get_default_category(self) -> str:
        return "BUSINESS_LOGIC"

    def _get_default_severity(self) -> str:
        return "HIGH"

    def _get_default_user_message(self) -> str:
        return "Configuration error. Please check your settings."


class InvalidConfigError(ConfigurationError):
    """Exception for invalid configuration data errors."""

    def _get_default_user_message(self) -> str:
        return "Invalid configuration data provided."


class MissingConfigError(ConfigurationError):
    """Exception for when a configuration file is not found."""

    def _get_default_user_message(self) -> str:
        return "Required configuration is missing."


class AgentError(ResyncException):
    """Exception for errors related to agent creation or management."""

    def _get_default_category(self) -> str:
        return "BUSINESS_LOGIC"

    def _get_default_severity(self) -> str:
        return "MEDIUM"

    def _get_default_user_message(self) -> str:
        return "An error occurred while processing the agent."


class TWSConnectionError(ResyncException):
    """Exception for TWS API connection errors."""

    def _get_default_category(self) -> str:
        return "EXTERNAL_SERVICE"

    def _get_default_severity(self) -> str:
        return "HIGH"

    def _get_default_user_message(self) -> str:
        return "Unable to connect to the TWS service."

    def _get_default_troubleshooting_hints(self) -> list[str]:
        return [
            "Check if the TWS service is running.",
            "Verify the TWS connection settings.",
            "Ensure network connectivity to the TWS server.",
        ]


class AgentExecutionError(ResyncException):
    """Exception for errors during AI agent execution."""

    def _get_default_category(self) -> str:
        return "BUSINESS_LOGIC"

    def _get_default_severity(self) -> str:
        return "MEDIUM"

    def _get_default_user_message(self) -> str:
        return "An error occurred while executing the AI agent."


class ToolExecutionError(ResyncException):
    """Exception for errors during tool execution."""

    def _get_default_category(self) -> str:
        return "BUSINESS_LOGIC"

    def _get_default_severity(self) -> str:
        return "MEDIUM"

    def _get_default_user_message(self) -> str:
        return "An error occurred while executing a tool."


class ToolConnectionError(ToolExecutionError):
    """Exception for connection errors within a tool."""

    def _get_default_category(self) -> str:
        return "EXTERNAL_SERVICE"

    def _get_default_user_message(self) -> str:
        return "Unable to connect to an external service required by the tool."


class ToolTimeoutError(ToolExecutionError):
    """Exception for timeouts during tool execution."""

    def _get_default_severity(self) -> str:
        return "MEDIUM"

    def _get_default_user_message(self) -> str:
        return "The tool execution timed out."


class ToolProcessingError(ToolExecutionError):
    """Exception for data processing errors within a tool."""

    def _get_default_user_message(self) -> str:
        return "An error occurred while processing data in the tool."


class KnowledgeGraphError(ResyncException):
    """Exception for Knowledge Graph related errors (e.g., Mem0)."""

    def _get_default_category(self) -> str:
        return "EXTERNAL_SERVICE"

    def _get_default_severity(self) -> str:
        return "MEDIUM"

    def _get_default_user_message(self) -> str:
        return "An error occurred with the knowledge graph service."


class AuditError(ResyncException):
    """Exception for errors in the audit system (queue, lock, etc.)."""

    def _get_default_category(self) -> str:
        return "SYSTEM"

    def _get_default_severity(self) -> str:
        return "HIGH"

    def _get_default_user_message(self) -> str:
        return "An error occurred in the audit system."


class FileIngestionError(ResyncException):
    """Exception for errors during file ingestion."""

    def _get_default_category(self) -> str:
        return "BUSINESS_LOGIC"

    def _get_default_severity(self) -> str:
        return "MEDIUM"

    def _get_default_user_message(self) -> str:
        return "An error occurred while ingesting the file."


class LLMError(ResyncException):
    """Exception for errors in communication with the Large Language Model."""

    def _get_default_category(self) -> str:
        return "EXTERNAL_SERVICE"

    def _get_default_severity(self) -> str:
        return "HIGH"

    def _get_default_user_message(self) -> str:
        return "An error occurred while communicating with the AI service."

    def _get_default_troubleshooting_hints(self) -> list[str]:
        return [
            "Check if the LLM service is available.",
            "Verify the LLM API credentials.",
            "Ensure the LLM endpoint is correctly configured.",
        ]


class ParsingError(ResyncException):
    """Exception for data parsing errors (JSON, etc.)."""

    def _get_default_category(self) -> str:
        return "VALIDATION"

    def _get_default_severity(self) -> str:
        return "MEDIUM"

    def _get_default_user_message(self) -> str:
        return "Invalid data format provided."


class NetworkError(ResyncException):
    """Exception for generic network errors."""

    def _get_default_category(self) -> str:
        return "SYSTEM"

    def _get_default_severity(self) -> str:
        return "HIGH"

    def _get_default_user_message(self) -> str:
        return "A network error occurred."


class WebSocketError(ResyncException):
    """Exception for WebSocket specific errors."""

    def _get_default_category(self) -> str:
        return "SYSTEM"

    def _get_default_severity(self) -> str:
        return "MEDIUM"

    def _get_default_user_message(self) -> str:
        return "A WebSocket communication error occurred."


class DatabaseError(ResyncException):
    """Exception for database interaction errors."""

    def _get_default_category(self) -> str:
        return "SYSTEM"

    def _get_default_severity(self) -> str:
        return "CRITICAL"

    def _get_default_user_message(self) -> str:
        return "A database error occurred."

    def _get_default_troubleshooting_hints(self) -> list[str]:
        return [
            "Check database connectivity.",
            "Verify database credentials.",
            "Ensure the database service is running.",
        ]


class CacheError(ResyncException):
    """Exception for errors related to the cache system."""

    def _get_default_category(self) -> str:
        return "SYSTEM"

    def _get_default_severity(self) -> str:
        return "MEDIUM"

    def _get_default_user_message(self) -> str:
        return "A cache error occurred."


class NotFoundError(ResyncException):
    """Exception for when a resource is not found."""

    def _get_default_category(self) -> str:
        return "BUSINESS_LOGIC"

    def _get_default_severity(self) -> str:
        return "MEDIUM"

    def _get_default_user_message(self) -> str:
        return "The requested resource was not found."

    def __init__(self, resource: str, identifier: Optional[str] = None, **kwargs):
        """
        Initialize NotFoundError with resource information.

        Args:
            resource: Type/name of the resource that was not found
            identifier: Specific identifier of the resource
            **kwargs: Additional arguments passed to parent class
        """
        message = f"{resource} not found"
        if identifier:
            message += f": {identifier}"

        details = {"resource": resource}
        if identifier:
            details["identifier"] = identifier

        super().__init__(message=message, details=details, **kwargs)


# Exception factory for creating exceptions with consistent patterns
class ExceptionFactory:
    """Factory for creating exceptions with consistent error codes and categories."""

    @staticmethod
    def create_validation_error(
        field: str,
        message: str,
        value: Optional[Any] = None,
        error_code: Optional[str] = None,
    ) -> ParsingError:
        """Create a validation error with field information."""
        details = {"field": field}
        if value is not None:
            details["value"] = value

        return ParsingError(
            message=f"Validation error in field '{field}': {message}",
            error_code=error_code or "VALIDATION_ERROR",
            details=details,
        )

    @staticmethod
    def create_resource_not_found(
        resource: str,
        identifier: Optional[str] = None,
        error_code: Optional[str] = None,
    ) -> NotFoundError:
        """Create a resource not found error."""
        return NotFoundError(
            resource=resource,
            identifier=identifier,
            error_code=error_code or "RESOURCE_NOT_FOUND",
        )

    @staticmethod
    def create_external_service_error(
        service: str, message: str, error_code: Optional[str] = None
    ) -> TWSConnectionError:
        """Create an external service error."""
        return TWSConnectionError(
            message=f"External service '{service}' error: {message}",
            error_code=error_code or f"{service.upper()}_SERVICE_ERROR",
            details={"service": service},
        )

    @staticmethod
    def create_rate_limit_error(
        limit: int, window: str, error_code: Optional[str] = None
    ) -> ResyncException:
        """Create a rate limit error."""
        return ResyncException(
            message=f"Rate limit exceeded: {limit} requests per {window}",
            error_code=error_code or "RATE_LIMIT_EXCEEDED",
            error_category="RATE_LIMIT",
            severity="MEDIUM",
            user_friendly_message="Too many requests. Please try again later.",
            details={"limit": limit, "window": window},
        )
