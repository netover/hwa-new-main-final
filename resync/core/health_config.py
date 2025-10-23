"""
Health check configuration with security settings.

This module provides configuration options for secure error handling
in health checks across different environments.
"""

from enum import Enum

from pydantic import BaseModel


class ErrorDetailLevel(str, Enum):
    """Security levels for error message detail."""

    DEVELOPMENT = "development"
    PRODUCTION = "production"
    SECURE = "secure"


class HealthCheckSecurityConfig(BaseModel):
    """Security configuration for health checks."""

    error_detail_level: ErrorDetailLevel = ErrorDetailLevel.SECURE
    """Level of detail to include in error messages."""

    include_stack_traces: bool = False
    """Whether to include stack traces in error responses."""

    log_full_errors: bool = True
    """Whether to log full error details for debugging."""

    sanitize_file_paths: bool = True
    """Whether to sanitize file paths in error messages."""

    sanitize_connection_strings: bool = True
    """Whether to sanitize database connection strings."""

    sanitize_sql_queries: bool = True
    """Whether to sanitize SQL queries in error messages."""

    error_id_length: int = 8
    """Length of error IDs for correlation."""

    @classmethod
    def from_environment(cls) -> "HealthCheckSecurityConfig":
        """Create configuration from environment variables."""
        import os

        detail_level = os.getenv("HEALTH_ERROR_DETAIL_LEVEL", "secure").lower()

        mapping = {
            "dev": ErrorDetailLevel.DEVELOPMENT,
            "development": ErrorDetailLevel.DEVELOPMENT,
            "prod": ErrorDetailLevel.PRODUCTION,
            "production": ErrorDetailLevel.PRODUCTION,
            "secure": ErrorDetailLevel.SECURE,
        }

        return cls(
            error_detail_level=mapping.get(detail_level, ErrorDetailLevel.SECURE),
            include_stack_traces=os.getenv(
                "HEALTH_INCLUDE_STACK_TRACES", "false"
            ).lower()
            == "true",
            log_full_errors=os.getenv("HEALTH_LOG_FULL_ERRORS", "true").lower()
            == "true",
            sanitize_file_paths=os.getenv("HEALTH_SANITIZE_PATHS", "true").lower()
            == "true",
            sanitize_connection_strings=os.getenv(
                "HEALTH_SANITIZE_CONNECTIONS", "true"
            ).lower()
            == "true",
            sanitize_sql_queries=os.getenv("HEALTH_SANITIZE_SQL", "true").lower()
            == "true",
            error_id_length=int(os.getenv("HEALTH_ERROR_ID_LENGTH", "8")),
        )
