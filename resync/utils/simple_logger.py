"""Simplified logging system using Python's standard logging module.

This module provides a simple, efficient logging system for the application,
replacing the complex structured logging system with a more lightweight approach
suitable for a 20-user deployment.

Features:
- Standard Python logging with rotating file handler
- Simple log formatting without JSON serialization overhead
- Basic correlation ID support without complex context management
- Configurable log levels and file rotation
- Minimal memory footprint and CPU overhead
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from contextvars import ContextVar


# Lazy import of settings to avoid circular dependencies
def _get_settings():
    """Lazy import of settings to avoid circular dependencies."""
    from resync.settings.settings import settings

    return settings


# ============================================================================
# CONTEXT VARIABLES
# ============================================================================

# Store current correlation ID for simple context tracking
_current_correlation_id: ContextVar[str | None] = ContextVar(
    "current_correlation_id", default=None
)

# ============================================================================
# SIMPLE LOGGER IMPLEMENTATION
# ============================================================================


class SimpleLogger:
    """Simplified logger wrapper around Python's standard logging."""

    def __init__(self, name: str):
        """Initialize the simple logger.

        Args:
            name: Logger name (usually __name__ of the module)
        """
        self.name = name
        self._logger = logging.getLogger(name)

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, exc_info: bool = False, **kwargs) -> None:
        """Log error message."""
        self._log(logging.ERROR, message, exc_info=exc_info, **kwargs)

    def critical(self, message: str, exc_info: bool = False, **kwargs) -> None:
        """Log critical message."""
        self._log(logging.CRITICAL, message, exc_info=exc_info, **kwargs)

    def _log(self, level: int, message: str, **kwargs) -> None:
        """Internal log method with optional correlation ID."""
        # Get correlation ID if available
        correlation_id = _current_correlation_id.get() or kwargs.get(
            "correlation_id"
        )

        # Format message with correlation ID if available
        if correlation_id:
            message = f"[{correlation_id}] {message}"

        # Log with standard Python logging
        self._logger.log(
            level, message, exc_info=kwargs.get("exc_info", False)
        )


# ============================================================================
# LOGGER FACTORY
# ============================================================================

_loggers: dict[str, SimpleLogger] = {}


def get_logger(name: str | None = None) -> SimpleLogger:
    """Get a simple logger instance.

    Args:
        name: Logger name (usually __name__ of the module)

    Returns:
        SimpleLogger instance
    """
    logger_name = name or "resync"

    if logger_name not in _loggers:
        _loggers[logger_name] = SimpleLogger(logger_name)

    return _loggers[logger_name]


# ============================================================================
# CONFIGURATION
# ============================================================================


def configure_simple_logging(
    log_level: str = "INFO",
    log_file: str | None = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 3,
    console_output: bool = True,
) -> None:
    """Configure simple logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional, defaults to resync.log)
        max_bytes: Maximum bytes before rotation (default: 10MB)
        backup_count: Number of backup files to keep (default: 3)
        console_output: Whether to also output to console (default: True)
    """
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Add file handler with rotation
    if log_file is None:
        log_file = "resync.log"

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Add console handler if requested
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)


# ============================================================================
# CONTEXT MANAGEMENT
# ============================================================================


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for current context.

    Args:
        correlation_id: Correlation ID to set
    """
    _current_correlation_id.set(correlation_id)


def get_correlation_id() -> str | None:
    """Get correlation ID from current context.

    Returns:
        Current correlation ID or None
    """
    return _current_correlation_id.get()


# ============================================================================
# COMPATIBILITY FUNCTIONS
# ============================================================================

# These functions provide compatibility with the old structured_logger interface
# to minimize changes in other parts of the codebase


def get_logger_adapter(name: str | None = None) -> SimpleLogger:
    """Get a logger adapter (compatibility function).

    Args:
        name: Logger name

    Returns:
        SimpleLogger instance
    """
    return get_logger(name)


def get_performance_logger(name: str | None = None) -> SimpleLogger:
    """Get a performance logger (compatibility function).

    Args:
        name: Logger name

    Returns:
        SimpleLogger instance
    """
    return get_logger(name)


class LoggerAdapter:
    """Compatibility adapter for the old LoggerAdapter class."""

    def __init__(self, logger: SimpleLogger):
        """Initialize the adapter.

        Args:
            logger: SimpleLogger instance
        """
        self.logger = logger

    def debug(self, event: str, **kwargs) -> None:
        """Log debug event."""
        self.logger.debug(event, **kwargs)

    def info(self, event: str, **kwargs) -> None:
        """Log info event."""
        self.logger.info(event, **kwargs)

    def warning(self, event: str, **kwargs) -> None:
        """Log warning event."""
        self.logger.warning(event, **kwargs)

    def error(self, event: str, exc_info: bool = False, **kwargs) -> None:
        """Log error event."""
        self.logger.error(event, exc_info=exc_info, **kwargs)

    def critical(self, event: str, exc_info: bool = False, **kwargs) -> None:
        """Log critical event."""
        self.logger.critical(event, exc_info=exc_info, **kwargs)

    def bind(self, **kwargs) -> LoggerAdapter:
        """Create new logger with context (simplified).

        Args:
            **kwargs: Context to be added

        Returns:
            New LoggerAdapter with context
        """
        # For simplicity, we just return the same adapter
        # In a more complex implementation, we would store the context
        return self


class PerformanceLogger:
    """Compatibility class for the old PerformanceLogger."""

    def __init__(self, logger: SimpleLogger):
        """Initialize the performance logger.

        Args:
            logger: SimpleLogger instance
        """
        self.logger = logger

    def log_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        request_size: int | None = None,
        response_size: int | None = None,
        user_agent: str | None = None,
        client_ip: str | None = None,
        **kwargs,
    ) -> None:
        """Log HTTP request (simplified)."""
        message = f"{method} {path} - {status_code} - {duration_ms:.2f}ms"
        if client_ip:
            message += f" - {client_ip}"

        if 200 <= status_code < 300:
            self.logger.info(message)
        elif 400 <= status_code < 500:
            self.logger.warning(f"Client error: {message}")
        else:
            self.logger.error(f"Server error: {message}")

    def log_database_query(
        self,
        query_type: str,
        duration_ms: float,
        rows_affected: int | None = None,
        query: str | None = None,
        **kwargs,
    ) -> None:
        """Log database query (simplified)."""
        message = f"DB {query_type} - {duration_ms:.2f}ms"
        if rows_affected is not None:
            message += f" - {rows_affected} rows"

        if duration_ms > 1000:
            self.logger.warning(f"Slow query: {message}")
        else:
            self.logger.debug(message)

    def log_external_call(
        self,
        service_name: str,
        operation: str,
        duration_ms: float,
        success: bool,
        request_size: int | None = None,
        response_size: int | None = None,
        **kwargs,
    ) -> None:
        """Log external service call (simplified)."""
        message = f"External {service_name}.{operation} - {duration_ms:.2f}ms"

        if not success:
            self.logger.error(f"Failed: {message}")
        elif duration_ms > 5000:
            self.logger.warning(f"Slow: {message}")
        else:
            self.logger.debug(message)

    def log_cache_operation(
        self,
        operation: str,
        key: str,
        hit: bool,
        duration_ms: float | None = None,
        **kwargs,
    ) -> None:
        """Log cache operation (simplified)."""
        message = f"Cache {operation} {key} - {'HIT' if hit else 'MISS'}"
        if duration_ms is not None:
            message += f" - {duration_ms:.2f}ms"

        self.logger.debug(message)

    def log_security_event(
        self,
        event_type: str,
        severity: str,
        source_ip: str | None = None,
        user_id: str | None = None,
        details: str | None = None,
        **kwargs,
    ) -> None:
        """Log security event (simplified)."""
        message = f"Security: {event_type} - {severity}"
        if source_ip:
            message += f" - {source_ip}"
        if user_id:
            message += f" - {user_id}"
        if details:
            message += f" - {details}"

        if severity == "critical":
            self.logger.critical(message)
        elif severity == "high":
            self.logger.error(message)
        elif severity == "medium":
            self.logger.warning(message)
        else:
            self.logger.info(message)


class StructuredErrorLogger:
    """Compatibility class for the old StructuredErrorLogger."""

    @staticmethod
    def log_error(
        error: Exception, context: dict, level: str = "error"
    ) -> None:
        """Log error with context (simplified).

        Args:
            error: The exception to log
            context: Additional context information
            level: Log level
        """
        logger = get_logger(__name__)
        message = f"{type(error).__name__}: {str(error)}"

        if context:
            message += f" - Context: {context}"

        if level.lower() == "critical":
            logger.critical(message)
        elif level.lower() == "error":
            logger.error(message)
        elif level.lower() == "warning":
            logger.warning(message)
        else:
            logger.info(message)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Core functions
    "get_logger",
    "configure_simple_logging",
    "set_correlation_id",
    "get_correlation_id",
    # Compatibility functions
    "get_logger_adapter",
    "get_performance_logger",
    # Compatibility classes
    "SimpleLogger",
    "LoggerAdapter",
    "PerformanceLogger",
    "StructuredErrorLogger",
]








