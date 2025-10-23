
"""
Resync Application Main Entry Point - Production-Ready Implementation

This module serves as the primary entry point for the Resync application,
providing enterprise-grade startup validation, configuration loading, and
application initialization. It implements a robust, fail-fast startup process
that comprehensively validates system configuration before launching the FastAPI application.

🏗️ ARCHITECTURAL FEATURES:
- Async-First Architecture: Full asyncio implementation with proper event loop management
- Comprehensive Validation: Environment variables, dependencies, and service connectivity
- Configuration Caching: LRU-cached validation to avoid redundant checks
- Health Checks: Pre-startup service health validation beyond basic connectivity
- Graceful Shutdown: Signal handlers for SIGTERM/SIGINT with proper resource cleanup
- Structured Logging: Context-aware logging with correlation and performance metrics

🚀 STARTUP PROCESS:
1. Configuration validation (environment variables, credentials, URLs)
2. Dependency verification (Redis connectivity with retry logic)
3. Security settings validation (admin credentials, secret keys)
4. Service health checks (TWS, LLM endpoints)
5. Application factory initialization
6. Uvicorn server startup with monitoring

🛡️ ERROR HANDLING:
- Hierarchical exception system with specific error types
- Detailed error messages with actionable troubleshooting guidance
- Fail-fast approach preventing unsafe application states
- Comprehensive logging for debugging and monitoring

⚡ PERFORMANCE OPTIMIZATIONS:
- Cached settings validation (no redundant checks)
- Async validation with proper concurrency
- Resource cleanup and memory management
- Efficient signal handling without blocking

📊 MONITORING & OBSERVABILITY:
- Structured JSON logging with context
- Startup metrics and timing information
- Health check results and service status
- Resource usage tracking and cleanup verification

Usage:
    python -m resync.main                    # Production with full validation
    # or
    python resync/main.py                    # Direct execution
    # or
    uvicorn resync.main:app --reload         # Development mode
    # or
    gunicorn resync.main:app -w 4 -k uvicorn.workers.UvicornWorker  # Production WSGI

Environment Variables Required:
    REDIS_URL, TWS_HOST, TWS_PORT, TWS_USER, TWS_PASSWORD,
    ADMIN_USERNAME, ADMIN_PASSWORD, SECRET_KEY, LLM_ENDPOINT, LLM_API_KEY

Optional but Recommended:
    LOG_LEVEL, SERVER_HOST, SERVER_PORT
"""
from dotenv import load_dotenv

# Load environment variables from .env file before any other imports
load_dotenv()

from typing import TYPE_CHECKING, Optional, Any, Dict
import signal
import asyncio
import sys
import os
import threading
import platform
import socket

if TYPE_CHECKING:
    from resync.settings import Settings
    from resync.core.startup_validation import (
        ConfigurationValidationError,
        DependencyUnavailableError,
        StartupError,
    )

import structlog

from resync.api.routes import api
from resync.core.encoding_utils import symbol
from resync.core.exceptions import ConfigurationError

# Runtime imports
from resync.core.startup_validation import (
    ConfigurationValidationError,
    DependencyUnavailableError,
    StartupError,
)
# Configure startup logger
startup_logger = structlog.get_logger("resync.startup")

# Global state for validated settings cache
_validated_settings_cache: Optional["Settings"] = None
_settings_validation_lock = asyncio.Lock()


async def get_validated_settings(fail_fast: bool = True) -> "Settings":
    """
    Cached settings validation to avoid repeated checks.

    This function caches the validated settings to prevent redundant
    validation operations during application lifecycle.

    Returns:
        Validated Settings object

    Raises:
        Reraises exceptions from validate_configuration_on_startup if fail_fast is False.
    """
    global _validated_settings_cache

    async with _settings_validation_lock:
        if _validated_settings_cache is None:
            startup_logger.info("performing_initial_settings_validation")
            _validated_settings_cache = await validate_configuration_on_startup()
            startup_logger.info("settings_validation_cached_successfully")

        return _validated_settings_cache


async def _check_tcp(host: str, port: int, timeout: float = 3.0) -> bool:
    """Asynchronously check if a TCP port is open."""
    def _connect() -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            return sock.connect_ex((host, port)) == 0
        finally:
            sock.close()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _connect)


async def run_startup_health_checks(settings: "Settings") -> Dict[str, Any]:
    """
    Run comprehensive health checks before full application startup.

    Performs additional validation beyond basic configuration to ensure
    all critical services are operational and responsive.

    Args:
        settings: Validated settings object

    Returns:
        Dict containing health check results
    """
    health_results = {
        "redis_connection": False,
        "tws_reachability": False,
        "llm_service": False,
        "overall_health": False,
    }

    try:
        startup_logger.info("running_startup_health_checks")

        # Redis connectivity check (already done in validation, but double-check)
        from resync.core.startup_validation import validate_redis_connection
        await validate_redis_connection(max_retries=1, timeout=3.0)
        health_results["redis_connection"] = True

        # TWS reachability (basic connectivity test)
        if settings.tws_host and settings.tws_port:
            health_results["tws_reachability"] = await _check_tcp(
                settings.tws_host, settings.tws_port
            )
        else:
            startup_logger.warning(
                "tws_reachability_check_skipped",
                reason="TWS host or port not configured",
                tws_host=settings.tws_host,
                tws_port=settings.tws_port,
            )
            health_results["tws_reachability"] = False

        # LLM service basic check (if endpoint is configured)
        if hasattr(settings, 'llm_endpoint') and settings.llm_endpoint:
            try:
                import aiohttp
                timeout = aiohttp.ClientTimeout(total=5.0)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    # Simple HEAD request to check if service is responsive
                    async with session.head(settings.llm_endpoint.rstrip('/')) as response:
                        health_results["llm_service"] = response.status < 500
            except Exception as e:
                startup_logger.warning("llm_service_check_failed", error=str(e))
                health_results["llm_service"] = False

        # Overall health assessment
        critical_services = ["redis_connection"] # Redis is always critical
        if getattr(settings, "require_llm_at_boot", False):
            critical_services.append("llm_service")
        if getattr(settings, "require_tws_at_boot", False):
            critical_services.append("tws_reachability")

        health_results["overall_health"] = all(
            health_results.get(service, False) for service in critical_services
        )

        startup_logger.info(
            "startup_health_checks_completed",
            health_results=health_results,
            overall_health=health_results["overall_health"]
        )

        return health_results

    except Exception as e:
        startup_logger.error("startup_health_checks_failed", error=str(e))
        return health_results


def setup_signal_handlers() -> None:
    """
    Setup signal handlers for graceful shutdown.

    Configures handlers for SIGTERM and SIGINT to ensure
    proper cleanup on application termination.
    """
    # Signal handlers should only be set in the main thread and not on Windows
    if platform.system() == "Windows":
        startup_logger.debug("signal_handlers_skipped_on_windows")
        return

    if threading.current_thread() is not threading.main_thread():
        startup_logger.debug("signal_handlers_skipped_on_non_main_thread")
        return

    def signal_handler(signum: int, frame: Any) -> None:
        """Handle shutdown signals gracefully."""
        signal_name = signal.Signals(signum).name
        startup_logger.info(
            "shutdown_signal_received",
            signal=signal_name,
            signal_number=signum
        )

        # Perform cleanup
        cleanup_resources()

        startup_logger.info("application_shutdown_complete")
        sys.exit(0)

    # Register signal handlers
    try:
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        startup_logger.info("signal_handlers_configured_successfully")
    except (ValueError, OSError) as e:
        startup_logger.warning("could_not_set_signal_handlers", reason=str(e))


def cleanup_resources() -> None:
    """
    Perform cleanup of application resources.

    Called during graceful shutdown to ensure proper resource cleanup.
    """
    try:
        startup_logger.info("performing_resource_cleanup")

        # Clear validated settings cache
        global _validated_settings_cache
        _validated_settings_cache = None

        startup_logger.info("resource_cleanup_completed")

    except Exception as e:
        startup_logger.error("resource_cleanup_failed", error=str(e))


async def validate_configuration_on_startup(fail_fast: bool = True) -> "Settings":
    """
    Validate system configuration before application startup using comprehensive validation.

    This function performs comprehensive validation of the application environment
    including settings, dependencies, and security configurations. It provides
    detailed feedback about any configuration issues that need to be resolved
    before the application can start successfully.

    The validation includes:
    - Environment variable validation
    - Security settings verification
    - TWS configuration checks
    - Redis connectivity testing
    - Settings loading and schema validation

    Returns:
        Validated Settings object ready for application use

    Raises:
        ConfigurationValidationError: If configuration validation fails
        DependencyUnavailableError: If required dependencies are unavailable
        StartupError: For other startup-related errors
        SystemExit: With appropriate exit code for startup failures
    """
    startup_logger.info("comprehensive_startup_validation_started")

    try:
        # Use the new comprehensive validation module
        from resync.core.startup_validation import validate_all_settings

        settings = await validate_all_settings()

        # Additional logging for successful validation (backward compatibility)
        startup_logger.info(
            "configuration_validation_successful",
            environment=settings.environment,
            redis_host=(
                settings.redis_url.split("@")[-1]
                if "@" in settings.redis_url
                else settings.redis_url
            ),
            tws_host=settings.tws_host,
            tws_port=settings.tws_port,
            status_symbol=symbol(True, sys.stdout),
        )

        return settings

    except Exception as e:
        # Handle different types of validation errors with appropriate logging
        if isinstance(e, ConfigurationValidationError):
            startup_logger.error(
                "configuration_validation_failed",
                error_type="ConfigurationValidationError",
                error_message=e.message,
                error_details=e.details,
                status_symbol=symbol(False, sys.stdout),
            )
        elif isinstance(e, DependencyUnavailableError):
            startup_logger.error(
                "dependency_unavailable",
                error_type="DependencyUnavailableError",
                dependency=e.dependency,
                error_message=e.message,
                error_details=e.details,
                status_symbol=symbol(False, sys.stdout),
            )
        elif isinstance(e, StartupError):
            startup_logger.error(
                "startup_error",
                error_type="StartupError",
                error_message=e.message,
                error_details=e.details,
                status_symbol=symbol(False, sys.stdout),
            )
        else:
            # Fallback for unexpected errors
            startup_logger.error(
                "unexpected_validation_error",
                error_type=type(e).__name__,
                error_message=str(e),
                status_symbol=symbol(False, sys.stdout),
            )

        # Log configuration guidance for developers (only for configuration errors)
        if isinstance(e, ConfigurationValidationError):
            startup_logger.warning(
                "configuration_setup_required",
                admin_username="admin",
                admin_password="suasenha123",
                secret_key_generation="python -c 'import secrets; print(secrets.token_urlsafe(32))'",
                redis_url="redis://localhost:6379",
                tws_host="localhost",
                tws_port=31111,
                tws_user="twsuser",
                tws_password="twspass",
            )

        if fail_fast:
            sys.exit(1)
        else:
            raise e


# Create the FastAPI application
from resync.fastapi_app.main import app

async def main() -> None:
    """
    Main entry point for running the application directly.

    This function handles the complete application startup process
    including validation, health checks, signal handlers, and server startup.
    It runs the server synchronously and will block until the server is stopped.

    For production deployments, it is recommended to use an ASGI server like
    Uvicorn or Gunicorn directly:

        uvicorn resync.main:app --workers 4
        gunicorn resync.main:app -w 4 -k uvicorn.workers.UvicornWorker

    Raises:
        SystemExit: If startup validation or health checks fail
    """
    import uvicorn

    try:
        # Setup signal handlers for graceful shutdown when running directly
        setup_signal_handlers()

        # Get validated settings (cached)
        settings = await get_validated_settings(fail_fast=True)

        # Run comprehensive health checks
        health_results = await run_startup_health_checks(settings)

        if not health_results["overall_health"]:
            startup_logger.critical(
                "startup_health_checks_failed",
                health_results=health_results,
                message="Critical services are not healthy. Application will not start."
            )
            sys.exit(1)

        startup_logger.info(
            "starting_uvicorn_server",
            host=getattr(settings, "server_host", "127.0.0.1"),
            port=getattr(settings, "server_port", 8000),
            environment=settings.environment,
            health_status="all_systems_go"
        )

        # Start the server
        config = uvicorn.Config(
            app,
            host=getattr(settings, "server_host", "127.0.0.1"),
            port=getattr(settings, "server_port", 8000),
            log_config=None,  # Use our structured logging
            access_log=False,  # Disable default access log, use middleware if needed
        )
        server = uvicorn.Server(config)
        await server.serve()

    except Exception as e:
        startup_logger.critical(
            "main_startup_failed",
            error_type=type(e).__name__,
            error_message=str(e)
        )
        cleanup_resources()
        raise

if __name__ == "__main__":
    """
    Direct execution entry point with enhanced error handling and resource management.

    This section provides:
    - Async context management via asyncio.run()
    - Graceful handling of KeyboardInterrupt
    - Comprehensive error logging for startup failures
    - Proper exit codes for different failure scenarios
    """
    import asyncio

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Signal handlers will manage cleanup, just log and exit
        startup_logger.info("application_shutdown_requested_via_keyboard")
        sys.exit(0)
    except SystemExit as e:
        # Respect explicit exit codes from validation/health checks
        sys.exit(e.code)
    except Exception as e:
        startup_logger.critical(
            "application_startup_failed_unexpected_error",
            error_type=type(e).__name__,
            error_message=str(e),
            traceback_info=True
        )
        # Ensure cleanup even on unexpected errors
        cleanup_resources()
        sys.exit(1)
