"""
Simplified Structured Logging Configuration

This module provides a simpler structured logging implementation that works with current structlog versions.
"""

import logging
import logging.config
import sys
import uuid
from typing import Optional

try:
    import structlog
except ImportError:
    print("structlog not installed. Please install with: pip install structlog>=23.2.0")
    sys.exit(1)

# Configure standard library logging
logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": "%(message)s",
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

# Configure structlog with a simpler approach
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

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
def log_request_start(method: str, endpoint: str, request_id: Optional[str] = None) -> None:
    """Log the start of a request."""
    with LoggingContext(
        request_type="start",
        method=method,
        endpoint=endpoint,
        request_id=request_id or str(uuid.uuid4())
    ):
        logger.info("Request started")

def log_request_end(method: str, endpoint: str, status_code: int, duration: float, request_id: Optional[str] = None) -> None:
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
    # Use a different context variable name to avoid conflicts
    context_vars = dict(kwargs)
    context_vars["error_type"] = type(error).__name__
    with LoggingContext(**context_vars):
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