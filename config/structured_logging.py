"""
Structured Logging Configuration

This module configures structured logging with JSON format for improved observability.
It integrates with the existing logging infrastructure and provides contextual information.
"""

import logging
import logging.config
import sys
import time
import uuid

try:
    import structlog
except ImportError:
    print("structlog not installed. Please install with: pip install structlog>=23.2.0")
    sys.exit(1)

# Configure standard library logging to avoid duplicate messages
logging.config.dictConfig({
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
            "maxBytes": 10*1024*1024,  # 10MB
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
})

# Configure structlog
def configure_structlog():
    """Configure structlog with JSON rendering and contextual information."""

    def add_timestamp(_, __, event_dict):
        """Add timestamp to log entries."""
        event_dict["timestamp"] = time.time()
        return event_dict

    def add_correlation_id(_, __, event_dict):
        """Add correlation ID to log entries."""
        correlation_id = event_dict.get("correlation_id")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
            event_dict["correlation_id"] = correlation_id
        return event_dict

    def add_request_id(_, __, event_dict):
        """Add request ID to log entries if available."""
        # This will be populated by middleware/context managers
        request_id = event_dict.get("request_id")
        if request_id:
            event_dict["request_id"] = request_id
        return event_dict

    def add_logger_name(logger, method_name, event_dict):
        """Add logger name and method to log entries."""
        event_dict["logger"] = logger.name
        event_dict["level"] = method_name
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

    def __init__(self, **kwargs):
        self.context = kwargs
        self.token = None

    def __enter__(self):
        self.token = structlog.contextvars.merge_contextvars(**self.context)
        self.token.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.token.__exit__(exc_type, exc_val, exc_tb)

# Utility functions for common logging patterns
def log_request_start(method: str, endpoint: str, request_id: str | None = None) -> None:
    """Log the start of a request."""
    with LoggingContext(
        request_type="start",
        method=method,
        endpoint=endpoint,
        request_id=request_id or str(uuid.uuid4())
    ):
        logger.info("Request started")

def log_request_end(method: str, endpoint: str, status_code: int, duration: float, request_id: str | None = None) -> None:
    """Log the end of a request."""
    with LoggingContext(
        request_type="end",
        method=method,
        endpoint=endpoint,
        status_code=status_code,
        duration=duration,
        request_id=request_id
    ):
        logger.info("Request completed", status_code=status_code, duration_ms=round(duration * 1000, 2))

def log_error(error: Exception, message: str = "An error occurred", **kwargs) -> None:
    """Log an error with structured information."""
    with LoggingContext(error_type=type(error).__name__, **kwargs):
        logger.error(message, exc_info=error)

def log_debug(message: str, **kwargs) -> None:
    """Log a debug message with structured information."""
    logger.debug(message, **kwargs)

def log_info(message: str, **kwargs) -> None:
    """Log an info message with structured information."""
    logger.info(message, **kwargs)

def log_warning(message: str, **kwargs) -> None:
    """Log a warning message with structured information."""
    logger.warning(message, **kwargs)

def log_critical(message: str, **kwargs) -> None:
    """Log a critical message with structured information."""
    logger.critical(message, **kwargs)




