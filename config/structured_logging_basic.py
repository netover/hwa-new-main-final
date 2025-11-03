"""
Basic Structured Logging Configuration

This module provides a basic structured logging implementation that works reliably.
"""

import json
import logging
import logging.config
import uuid


# Configure standard library logging with JSON format
class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def __init__(self):
        super().__init__()
        self.default_fields = {
            'timestamp': None,
            'level': None,
            'logger': None,
            'correlation_id': None,
            'request_id': None,
        }

    def format(self, record):
        # Create log entry with standard fields
        log_entry = {
            'timestamp': self.formatTime(record, '%Y-%m-%d %H:%M:%S'),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }

        # Add correlation ID if available
        if hasattr(record, 'correlation_id') and record.correlation_id:
            log_entry['correlation_id'] = record.correlation_id

        # Add request ID if available
        if hasattr(record, 'request_id') and record.request_id:
            log_entry['request_id'] = record.request_id

        # Add any extra fields from the record
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                          'filename', 'module', 'lineno', 'funcName', 'created', 'msecs',
                          'relativeCreated', 'thread', 'threadName', 'processName', 'process',
                          'getMessage', 'exc_info', 'exc_text', 'stack_info', 'correlation_id',
                          'request_id']:
                log_entry[key] = value

        return json.dumps(log_entry)

# Configure logging
logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": JSONFormatter,
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

# Create the main logger
logger = logging.getLogger("app")

# Global correlation ID for request tracking
_current_correlation_id = None
_current_request_id = None

def set_correlation_id(correlation_id: str):
    """Set the current correlation ID."""
    global _current_correlation_id
    _current_correlation_id = correlation_id

def set_request_id(request_id: str):
    """Set the current request ID."""
    global _current_request_id
    _current_request_id = request_id

def get_correlation_id() -> str:
    """Get or generate a correlation ID."""
    global _current_correlation_id
    if _current_correlation_id is None:
        _current_correlation_id = str(uuid.uuid4())
    return _current_correlation_id

def get_request_id() -> str:
    """Get or generate a request ID."""
    global _current_request_id
    if _current_request_id is None:
        _current_request_id = str(uuid.uuid4())
    return _current_request_id

class StructuredLogger:
    """Structured logger with contextual information."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def _log_with_context(self, level, message, **kwargs):
        """Log with contextual information."""
        # Create a LogRecord with extra fields
        extra_fields = {
            'correlation_id': get_correlation_id(),
            'request_id': get_request_id(),
        }
        extra_fields.update(kwargs)

        # Create the log record
        record = self.logger.makeRecord(
            name=self.logger.name,
            level=level,
            fn="",
            lno=0,
            msg=message,
            args=(),
            exc_info=None
        )

        # Add extra fields to the record
        for key, value in extra_fields.items():
            setattr(record, key, value)

        # Use the formatter directly to format the message
        formatter = JSONFormatter()
        formatted_message = formatter.format(record)

        # Log with the formatted JSON message
        if level == logging.DEBUG:
            self.logger.debug(formatted_message)
        elif level == logging.INFO:
            self.logger.info(formatted_message)
        elif level == logging.WARNING:
            self.logger.warning(formatted_message)
        elif level == logging.ERROR:
            self.logger.error(formatted_message)
        elif level == logging.CRITICAL:
            self.logger.critical(formatted_message)

    def debug(self, message, **kwargs):
        """Log debug message."""
        self._log_with_context(logging.DEBUG, message, **kwargs)

    def info(self, message, **kwargs):
        """Log info message."""
        self._log_with_context(logging.INFO, message, **kwargs)

    def warning(self, message, **kwargs):
        """Log warning message."""
        self._log_with_context(logging.WARNING, message, **kwargs)

    def error(self, message, **kwargs):
        """Log error message."""
        self._log_with_context(logging.ERROR, message, **kwargs)

    def critical(self, message, **kwargs):
        """Log critical message."""
        self._log_with_context(logging.CRITICAL, message, **kwargs)

# Create structured logger instance
structured_logger = StructuredLogger("app")

# Utility functions for common logging patterns
def log_request_start(method: str, endpoint: str, request_id: str | None = None) -> None:
    """Log the start of a request."""
    if request_id:
        set_request_id(request_id)
    structured_logger.info("Request started", method=method, endpoint=endpoint, request_type="start")

def log_request_end(method: str, endpoint: str, status_code: int, duration: float, request_id: str | None = None) -> None:
    """Log's end of a request."""
    structured_logger.info(
        "Request completed",
        method=method,
        endpoint=endpoint,
        status_code=status_code,
        duration=duration,
        request_type="end",
        duration_ms=round(duration * 1000, 2)
    )

def log_error(error: Exception, message: str = "An error occurred", **kwargs) -> None:
    """Log an error with structured information."""
    structured_logger.error(
        message,
        error_type=type(error).__name__,
        error_message=str(error),
        **kwargs
    )

def log_debug(message: str, **kwargs) -> None:
    """Log a debug message with structured information."""
    structured_logger.debug(message, **kwargs)

def log_info(message: str, **kwargs) -> None:
    """Log an info message with structured information."""
    structured_logger.info(message, **kwargs)

def log_warning(message: str, **kwargs) -> None:
    """Log a warning message with structured information."""
    structured_logger.warning(message, **kwargs)

def log_critical(message: str, **kwargs) -> None:
    """Log a critical message with structured information."""
    structured_logger.critical(message, **kwargs)

# Simple context manager for temporary context
class LoggingContext:
    """Simple context manager for adding contextual information to logs."""

    def __init__(self, **kwargs):
        self.old_correlation_id = None
        self.old_request_id = None
        self.context = kwargs

    def __enter__(self):
        # Store old values
        self.old_correlation_id = _current_correlation_id
        self.old_request_id = _current_request_id

        # Set new values from context
        if 'correlation_id' in self.context:
            set_correlation_id(self.context['correlation_id'])
        if 'request_id' in self.context:
            set_request_id(self.context['request_id'])

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore old values
        if self.old_correlation_id is not None:
            set_correlation_id(self.old_correlation_id)
        else:
            _current_correlation_id = None

        if self.old_request_id is not None:
            set_request_id(self.old_request_id)
        else:
            _current_request_id = None




