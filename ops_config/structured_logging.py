"""
Structured Logging Configuration

This module configures structured logging with JSON format for improved
observability. It integrates with the existing logging infrastructure and
provides contextual information.
"""

import logging
import logging.config
import sys
import time
import uuid
from contextlib import AbstractContextManager
from types import TracebackType
from typing import Any, MutableMapping, cast

try:
    import structlog
except ImportError:
    print("structlog not installed. Please install with: "
          "pip install structlog>=23.2.0")
    sys.exit(1)

# Configure standard library logging to avoid duplicate messages
logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": structlog.processors.JSONRenderer,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "json",
                "filename": "logs/app.log",
                "maxBytes": 10 * 1024 * 1024,  # 10MB
                "backupCount": 14,
            },
        },
        "loggers": {
            "": {
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": True,
            },
        },
    },
)


# Configure structlog


def configure_structlog() -> None:
    """Configure structlog with JSON rendering and contextual information."""

    def add_timestamp(
        _: Any,
        __: str,
        event_dict: MutableMapping[str, Any],
    ) -> MutableMapping[str, Any]:
        """Add timestamp to log entries."""
        event_dict["timestamp"] = time.time()
        return event_dict

    def add_correlation_id(
        _: Any,
        __: str,
        event_dict: MutableMapping[str, Any],
    ) -> MutableMapping[str, Any]:
        """Add correlation ID to log entries."""
        correlation_id = event_dict.get("correlation_id")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
            event_dict["correlation_id"] = correlation_id
        return event_dict

    def add_request_id(
        _: Any,
        __: str,
        event_dict: MutableMapping[str, Any],
    ) -> MutableMapping[str, Any]:
        """Add request ID to log entries if available."""
        # This will be populated by middleware/context managers
        request_id = event_dict.get("request_id")
        if request_id:
            event_dict["request_id"] = request_id
        return event_dict

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            add_timestamp,
            add_correlation_id,
            add_request_id,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


# Initialize structured logging
configure_structlog()


# Create the main logger
logger = structlog.get_logger("app")


# Context manager for adding request-specific information
class LoggingContext:
    """Context manager for adding contextual information to logs."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__()
        self.context: dict[str, Any] = kwargs
        self.token: AbstractContextManager[Any] | None = None

    def __enter__(self) -> "LoggingContext":
        token = structlog.contextvars.merge_contextvars(**self.context)
        self.token = cast(AbstractContextManager[Any], token)
        self.token.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        if self.token is not None:
            return self.token.__exit__(exc_type, exc_val, exc_tb)
        return None

# Utility functions for common logging patterns


def log_request_start(
    method: str,
    endpoint: str,
    request_id: str | None = None,
) -> None:
    """Log the start of a request."""
    with LoggingContext(
        request_type="start",
        method=method,
        endpoint=endpoint,
        request_id=request_id or str(uuid.uuid4()),
    ):
        logger.info("Request started")


def log_request_end(
    method: str,
    endpoint: str,
    status_code: int,
    duration: float,
    request_id: str | None = None,
) -> None:
    """Log the end of a request."""
    with LoggingContext(
        request_type="end",
        method=method,
        endpoint=endpoint,
        status_code=status_code,
        duration=duration,
        request_id=request_id,
    ):
        logger.info(
            "Request completed",
            status_code=status_code,
            duration_ms=round(duration * 1000, 2),
        )


def log_error(
    error: Exception,
    message: str = "An error occurred",
    **kwargs: Any,
) -> None:
    """Log an error with structured information."""
    with LoggingContext(error_type=type(error).__name__, **kwargs):
        logger.error(message, exc_info=error)


def log_debug(message: str, **kwargs: Any) -> None:
    """Log a debug message with structured information."""
    logger.debug(message, **kwargs)


def log_info(message: str, **kwargs: Any) -> None:
    """Log an info message with structured information."""
    logger.info(message, **kwargs)


def log_warning(message: str, **kwargs: Any) -> None:
    """Log a warning message with structured information."""
    logger.warning(message, **kwargs)


def log_critical(message: str, **kwargs: Any) -> None:
    """Log a critical message with structured information."""
    logger.critical(message, **kwargs)
