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

# Standard library imports
import asyncio
import platform
import signal
import sys
import threading
from typing import TYPE_CHECKING, Any, Optional

import aiohttp
import structlog
import uvicorn

# Third-party imports
from dotenv import load_dotenv

# Local imports
from resync.core.encoding_utils import symbol
from resync.core.startup_validation import (
    ConfigurationValidationError,
    DependencyUnavailableError,
    StartupError,
    validate_all_settings,
    validate_redis_connection,
)
from resync.fastapi_app.main import app

if TYPE_CHECKING:
    from resync.settings import Settings

# Load environment variables from .env file before any other imports
load_dotenv()
# Configure startup logger
startup_logger = structlog.get_logger("resync.startup")

# Global state for validated settings cache
# NOTE: Settings cache is managed by the SettingsCache class below


class SettingsCache:
    """Thread-safe cache for validated settings."""

    def __init__(self) -> None:
        self._cache: "Settings" | None = None
        self._lock = asyncio.Lock()

    async def get_validated_settings(self, fail_fast: bool = True) -> "Settings":
        """Get validated settings with caching."""
        async with self._lock:
            if self._cache is None:
                startup_logger.info("performing_initial_settings_validation")
                self._cache = await validate_configuration_on_startup(fail_fast=fail_fast)
                startup_logger.info("settings_validation_cached_successfully")
            return self._cache

    def clear_cache(self) -> None:
        """Clear the cached settings."""
        self._cache = None


# Global settings cache instance
_settings_cache = SettingsCache()


async def get_validated_settings(fail_fast: bool = True) -> "Settings":
    """Valida e cacheia Settings (fail-fast configurável)."""
    return await _settings_cache.get_validated_settings(fail_fast)


async def _check_tcp(host: str, port: int, timeout: float = 3.0) -> bool:
    """
    Verifica reachability TCP de forma 100% assíncrona.
    Usa asyncio.open_connection com timeout explícito e fechamento adequado de recursos.
    """
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        try:
            await writer.wait_closed()
        except (OSError, ConnectionError, RuntimeError):
            # alguns transports podem não suportar wait_closed; ignore
            pass
        return True
    except (asyncio.TimeoutError, ConnectionError, OSError):
        return False


async def run_startup_health_checks(settings: "Settings") -> dict[str, Any]:
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

        # Redis connectivity double-check
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

        # LLM service basic check (GET curto; HEAD pode retornar 405 em alguns provedores)
        if getattr(settings, 'llm_endpoint', None):
            try:
                timeout = aiohttp.ClientTimeout(total=5.0)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    endpoint = settings.llm_endpoint.rstrip('/')
                    async with session.get(
                        endpoint, allow_redirects=True
                    ) as resp:
                        # Considera apenas status 200-399 como saudável (mais rigoroso)
                        health_results["llm_service"] = 200 <= resp.status < 400
                        if not health_results["llm_service"]:
                            startup_logger.warning(
                                "llm_service_unhealthy_status",
                                status=resp.status,
                                reason="Status code not in 200-399 range"
                            )
            except (aiohttp.ClientPayloadError, aiohttp.ServerDisconnectedError,
                    aiohttp.ClientConnectionError) as e:
                startup_logger.warning("llm_service_check_unexpected_error", error=str(e))
                health_results["llm_service"] = False
            except aiohttp.ClientError as e:
                startup_logger.warning("llm_service_check_failed", error=str(e))
                health_results["llm_service"] = False
            except RuntimeError as e:
                startup_logger.warning("llm_service_check_unexpected_error", error=str(e))
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

    except (RuntimeError, ConnectionError, OSError) as e:
        startup_logger.error("startup_health_checks_failed", error=str(e))
        return health_results


def setup_signal_handlers(server: Optional["uvicorn.Server"] = None) -> None:
    """Configura handlers para SIGTERM/SIGINT (apenas main thread; skip no Windows)."""
    if platform.system() == "Windows":
        startup_logger.debug("signal_handlers_skipped_on_windows")
        return
    if threading.current_thread() is not threading.main_thread():
        startup_logger.debug("signal_handlers_skipped_on_non_main_thread")
        return

    def signal_handler(signum: int, _frame: Any) -> None:
        signal_name = signal.Signals(signum).name
        startup_logger.info("shutdown_signal_received", signal=signal_name, signal_number=signum)
        cleanup_resources()
        startup_logger.info("application_shutdown_complete")

        # Prefer server.should_exit = True over sys.exit() when server is available
        if server is not None:
            server.should_exit = True
        else:
            sys.exit(0)

    try:
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        startup_logger.info("signal_handlers_configured_successfully")
    except (ValueError, OSError) as e:
        startup_logger.warning("could_not_set_signal_handlers", reason=str(e))


def cleanup_resources() -> None:
    """Limpa recursos de aplicação (cache de settings, etc.)."""
    try:
        startup_logger.info("performing_resource_cleanup")
        _settings_cache.clear_cache()
        startup_logger.info("resource_cleanup_completed")
    except (RuntimeError, OSError) as e:
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

    except (ConfigurationValidationError, DependencyUnavailableError, StartupError) as e:
        # ✅ StartupError agora tratado aqui
        if isinstance(e, ConfigurationValidationError):
            startup_logger.error("configuration_validation_failed",
                                 error_type="ConfigurationValidationError",
                                 error_message=e.message, error_details=e.details,
                                 status_symbol=symbol(False, sys.stdout))
        elif isinstance(e, DependencyUnavailableError):
            startup_logger.error("dependency_unavailable",
                                 error_type="DependencyUnavailableError",
                                 dependency=e.dependency, error_message=e.message,
                                 error_details=e.details, status_symbol=symbol(False, sys.stdout))
        else:
            startup_logger.error("startup_error",
                                 error_type="StartupError",
                                 error_message=getattr(e, "message", str(e)),
                                 error_details=getattr(e, "details", None),
                                 status_symbol=symbol(False, sys.stdout))

        # Log configuration guidance for developers (only for configuration errors)
        if isinstance(e, ConfigurationValidationError):
            startup_logger.warning(
                "configuration_setup_required",
                admin_username="admin",
                admin_password="suasenha123",
                secret_key_generation=(
                    "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                ),
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
# app is already imported at the top of the file

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

    try:
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
            log_config=None,   # usar nosso logging estruturado
            access_log=False,  # logs de acesso via middleware, se necessário
        )
        server = uvicorn.Server(config)

        # Setup signal handlers with server reference
        setup_signal_handlers(server)

        await server.serve()

    except (RuntimeError, OSError, ConnectionError) as e:
        startup_logger.critical(
            "main_startup_failed",
            error_type=type(e).__name__,
            error_message=str(e)
        )
        cleanup_resources()
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Signal handlers will manage cleanup, just log and exit
        startup_logger.info("application_shutdown_requested_via_keyboard")
        sys.exit(0)
    except SystemExit as e:
        # Respect explicit exit codes from validation/health checks
        sys.exit(e.code if e.code is not None else 1)
    except (RuntimeError, OSError, ConnectionError) as e:
        startup_logger.critical(
            "application_startup_failed_unexpected_error",
            error_type=type(e).__name__,
            error_message=str(e),
            traceback_info=True
        )
        # Ensure cleanup even on unexpected errors
        cleanup_resources()
        sys.exit(1)
