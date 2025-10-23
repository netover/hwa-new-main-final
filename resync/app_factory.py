"""
Application factory for creating and configuring the FastAPI application.

This module is imported by resync/main.py and provides the actual application
initialization logic following the factory pattern.
"""

import hashlib
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader, select_autoescape
from starlette.responses import HTMLResponse
from starlette.staticfiles import StaticFiles as StarletteStaticFiles

from resync.core.structured_logger import get_logger
from resync.settings import settings

# Configure app factory logger
app_logger = get_logger("resync.app_factory")

logger = get_logger(__name__)


class CachedStaticFiles(StarletteStaticFiles):
    """Static files handler with optimized caching."""

    async def get_response(self, path: str, scope):
        """Get response with cache headers."""
        response = await super().get_response(path, scope)

        if response.status_code == 200:
            # Set cache headers
            cache_max_age = getattr(
                settings, "static_cache_max_age", 86400
            )  # Default 1 day
            response.headers["Cache-Control"] = f"public, max-age={cache_max_age}"

            # Generate ETag for cache validation
            try:
                full_path = Path(self.directory) / path
                if full_path.exists():
                    stat_result = os.stat(full_path)
                    file_metadata = f"{stat_result.st_size}-{int(stat_result.st_mtime)}"
                    etag_value = (
                        f'"{hashlib.sha256(file_metadata.encode()).hexdigest()[:16]}"'
                    )
                    response.headers["ETag"] = etag_value
            except Exception as e:
                logger.warning("failed_to_generate_etag", error=str(e))
                response.headers["ETag"] = f'"{hash(path)}"'

        return response


class ApplicationFactory:
    """
    Factory for creating and configuring FastAPI applications.

    This class encapsulates all application initialization logic,
    providing a clean separation of concerns and modular architecture.
    """

    def __init__(self):
        """Initialize the application factory."""
        self.app: Optional[FastAPI] = None
        self.templates: Optional[Jinja2Templates] = None
        self.template_env: Optional[Environment] = None

    @asynccontextmanager
    async def lifespan(self, app: FastAPI) -> AsyncIterator[None]:
        """
            Manage application lifecycle with proper startup and shutdown.

        Args:
                app: FastAPI application instance

            Yields:
                None during application runtime
        """
        # Startup
        logger.info("application_startup_initiated")

        try:
            # Import here to avoid circular dependencies
            from resync.api_gateway.container import setup_dependencies
            from resync.core.container import app_container
            from resync.core.exceptions import (
                ConfigurationError,
                RedisAuthError,
                RedisConnectionError,
                RedisInitializationError,
                RedisTimeoutError,
            )
            from resync.core.interfaces import (
                IAgentManager,
                IKnowledgeGraph,
                ITWSClient,
            )
            from resync.core.tws_monitor import get_tws_monitor, shutdown_tws_monitor
            from resync.cqrs.dispatcher import initialize_dispatcher
            from resync.lifespan import initialize_redis_with_retry

            # Store container reference
            app.state.container = app_container

            # Container is already initialized during creation

            # Get required services
            tws_client = await app_container.get(ITWSClient)
            agent_manager = await app_container.get(IAgentManager)
            knowledge_graph = await app_container.get(IKnowledgeGraph)

            # Initialize TWS monitor
            tws_monitor = await get_tws_monitor(tws_client)

            # Setup dependencies
            setup_dependencies(tws_client, agent_manager, knowledge_graph)

            # Initialize CQRS dispatcher
            initialize_dispatcher(tws_client, tws_monitor)

            # Initialize Redis with retry
            # This function now handles idempotency manager initialization internally
            await initialize_redis_with_retry(
                max_retries=settings.redis_max_startup_retries,
                base_backoff=settings.redis_startup_backoff_base,
                max_backoff=settings.redis_startup_backoff_max,
            )

            app_logger.info(
                "application_startup_initiated", component="resync_hwa_dashboard"
            )

            # Initialize Redis
            app_logger.info("redis_connection_attempt")
            await initialize_redis_with_retry()
            app_logger.info("redis_connection_successful")

            # Outras inicializações...

            logger.info("application_startup_completed")

            yield  # Application runs here

        except ConfigurationError as e:
            app_logger.error(
                "configuration_error",
                error_message=str(e),
                error_details=e.details,
                hint=e.details.get("hint"),
            )
            sys.exit(2)

        except RedisAuthError as e:
            app_logger.error(
                "redis_authentication_error",
                error_message=str(e),
                error_details=e.details,
                hint=e.details.get("hint"),
                example_redis_url="redis://:suasenha@localhost:6379",
            )
            sys.exit(3)

        except RedisConnectionError as e:
            app_logger.error(
                "redis_connection_error",
                error_message=str(e),
                error_details=e.details,
                hint=e.details.get("hint"),
                installation_guide={
                    "macos": "brew install redis",
                    "linux": "apt install redis",
                    "start_command": "redis-server",
                    "test_command": "redis-cli ping (should return 'PONG')",
                },
            )
            sys.exit(4)

        except RedisTimeoutError as e:
            app_logger.error(
                "redis_timeout_error",
                error_message=str(e),
                error_details=e.details,
                hint=e.details.get("hint"),
            )
            sys.exit(5)

        except RedisInitializationError as e:
            app_logger.error(
                "redis_initialization_error",
                error_message=str(e),
                error_details=e.details,
                hint=e.details.get("hint"),
            )
            sys.exit(6)

        except Exception as e:
            logger.critical("application_startup_failed", error=str(e), exc_info=True)
            raise
        finally:
            # Shutdown
            app_logger.info("application_shutdown_initiated")

            try:
                await shutdown_tws_monitor()
                logger.info("application_shutdown_completed")
                app_logger.info("application_shutdown_successful")
            except Exception as e:
                logger.error("application_shutdown_error", error=str(e), exc_info=True)

    def create_application(self) -> FastAPI:
        """
        Create and configure the FastAPI application.

        Returns:
            Fully configured FastAPI application instance
        """
        # Validate settings first
        self._validate_critical_settings()

        # Create FastAPI app with lifespan
        self.app = FastAPI(
            title=settings.project_name,
            version=settings.project_version,
            description=settings.description,
            lifespan=self.lifespan,
            docs_url="/api/docs" if not settings.is_production else None,
            redoc_url="/api/redoc" if not settings.is_production else None,
            openapi_url="/api/openapi.json" if not settings.is_production else None,
        )

        # Configure all components in order
        self._setup_templates()
        self._configure_middleware()
        self._configure_exception_handlers()
        self._setup_dependency_injection()
        self._register_routers()
        self._mount_static_files()
        self._register_special_endpoints()

        logger.info(
            "application_created",
            environment=settings.environment.value,
            debug_mode=settings.is_development,
        )

        return self.app

    def _validate_critical_settings(self) -> None:
        """Validate critical settings before application startup."""
        errors = []

        # Redis configuration
        if settings.redis_pool_min_size > settings.redis_pool_max_size:
            errors.append(
                f"redis_pool_min_size ({settings.redis_pool_min_size}) > "
                f"redis_pool_max_size ({settings.redis_pool_max_size})"
            )

        # Production-specific validations
        if settings.is_production:
            if settings.admin_password in ["change_me_please", "admin", "password"]:
                errors.append("Insecure admin password in production")

            if "*" in settings.cors_allowed_origins:
                errors.append("Wildcard CORS origins not allowed in production")

            if settings.llm_api_key == "dummy_key_for_development":
                errors.append("Invalid LLM API key in production")

        # Raise if any critical errors
        if errors:
            for error in errors:
                logger.error("configuration_error", error=error)
            raise ValueError(f"Configuration errors: {'; '.join(errors)}")

        logger.info("settings_validation_passed")

    def _setup_templates(self) -> None:
        """Configure Jinja2 template engine."""
        templates_dir = settings.base_dir / "templates"

        if not templates_dir.exists():
            logger.warning("templates_directory_not_found", path=str(templates_dir))
            return

        # Create Jinja2 environment with security settings
        self.template_env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(
                enabled_extensions=("html", "xml"),
                default_for_string=True,
                default=True,
            ),
            auto_reload=settings.is_development,
            cache_size=400 if settings.is_production else 0,
            enable_async=True,
            # extensions=['resync.core.csp_jinja_extension.CSPNonceExtension']
        )

        self.templates = Jinja2Templates(directory=str(templates_dir))
        self.templates.env = self.template_env

        # Store in app state for access in routes
        self.app.state.template_env = self.template_env
        self.app.state.templates = self.templates

        logger.info("templates_configured", directory=str(templates_dir))

    def _configure_middleware(self) -> None:
        """Configure all middleware in the correct order."""
        from resync.api.middleware.correlation_id import CorrelationIdMiddleware
        from resync.api.middleware.cors_config import CORSConfig
        from resync.api.middleware.csp_middleware import CSPMiddleware
        from resync.api.middleware.error_handler import GlobalExceptionHandlerMiddleware

        # 1. Correlation ID (must be first)
        self.app.add_middleware(CorrelationIdMiddleware)

        # 2. Global Exception Handler
        self.app.add_middleware(GlobalExceptionHandlerMiddleware)

        # 3. CORS Configuration
        cors_config = CORSConfig()
        cors_policy = cors_config.get_policy(settings.environment.value)

        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_policy.allowed_origins,
            allow_credentials=cors_policy.allow_credentials,
            allow_methods=cors_policy.allowed_methods,
            allow_headers=cors_policy.allowed_headers,
            max_age=cors_policy.max_age,
        )

        # 4. CSP Middleware
        self.app.add_middleware(CSPMiddleware, report_only=not settings.is_production)

        # 5. Additional security headers
        from resync.config.security import add_additional_security_headers

        add_additional_security_headers(self.app)

        logger.info("middleware_configured")

    def _configure_exception_handlers(self) -> None:
        """Register global exception handlers."""
        from resync.api.exception_handlers import register_exception_handlers

        register_exception_handlers(self.app)
        logger.info("exception_handlers_registered")

    def _setup_dependency_injection(self) -> None:
        """Configure dependency injection."""
        from resync.core.fastapi_di import inject_container

        inject_container(self.app)
        logger.info("dependency_injection_configured")

    def _register_routers(self) -> None:
        """Register all API routers."""
        # Import routers
        from resync.api.admin import admin_router
        from resync.api.agents import agents_router
        from resync.api.audit import router as audit_router
        from resync.api.cache import cache_router
        from resync.api.chat import chat_router
        from resync.api.cors_monitoring import cors_monitor_router
        from resync.api.health import router as health_router
        from resync.api.performance import performance_router

        # Additional routers from main_improved
        try:
            from resync.api.endpoints import api_router
            from resync.api.health import config_router
            from resync.api.rag_upload import router as rag_upload_router

            # Register additional routers
            self.app.include_router(api_router, prefix="/api")
            self.app.include_router(config_router, prefix="/api/v1")
            self.app.include_router(rag_upload_router, prefix="/api/v1")
        except ImportError as e:
            logger.warning("optional_routers_not_available", error=str(e))

        # Register core routers
        routers = [
            (health_router, "/api/v1", ["Health"]),
            (agents_router, "/api/v1/agents", ["Agents"]),
            (chat_router, "/api/v1", ["Chat"]),
            (cache_router, "/api/v1", ["Cache"]),
            (audit_router, "/api/v1", ["Audit"]),
            (cors_monitor_router, "/api/v1", ["CORS"]),
            (performance_router, "/api", ["Performance"]),
            (admin_router, "/api/v1", ["Admin"]),
            # Also register admin router at root level for /admin access
            (admin_router, "", ["Admin"]),
        ]

        for router, prefix, tags in routers:
            self.app.include_router(router, prefix=prefix, tags=tags)

        logger.info("routers_registered", count=len(routers))

    def _mount_static_files(self) -> None:
        """Mount static file directories with caching."""
        static_dir = settings.base_dir / "static"

        if not static_dir.exists():
            logger.warning("static_directory_not_found", path=str(static_dir))
            return

        # Mount main static directory with caching
        self.app.mount(
            "/static", CachedStaticFiles(directory=str(static_dir)), name="static"
        )

        # Mount subdirectories if they exist
        subdirs = ["assets", "css", "js", "img", "fonts"]
        mounted = 1

        for subdir in subdirs:
            subdir_path = static_dir / subdir
            if subdir_path.exists():
                self.app.mount(
                    f"/{subdir}",
                    CachedStaticFiles(directory=str(subdir_path)),
                    name=subdir,
                )
                mounted += 1

        logger.info("static_files_mounted", count=mounted, directory=str(static_dir))

    def _register_special_endpoints(self) -> None:
        """Register special endpoints (frontend, CSP, etc.)."""

        # Root redirect
        @self.app.get("/", include_in_schema=False)
        async def root():
            """Redirect root to admin panel."""
            return RedirectResponse(url="/admin", status_code=302)

        # Admin panel is now handled by the admin router

        # Revision page
        @self.app.get("/revisao", include_in_schema=False, response_class=HTMLResponse)
        async def revisao_page(request: Request):
            """Serve the revision page."""
            # Apply rate limiting if available
            try:
                from resync.core.rate_limiter import dashboard_rate_limit

                return await dashboard_rate_limit(
                    self._render_template("revisao.html", request)
                )
            except ImportError:
                return self._render_template("revisao.html", request)

        # CSP violation report endpoint
        @self.app.post("/csp-violation-report", include_in_schema=False)
        async def csp_violation_report(request: Request):
            """Handle CSP violation reports."""
            return await self._handle_csp_report(request)

        logger.info("special_endpoints_registered")

    def _render_template(self, template_name: str, request: Request) -> HTMLResponse:
        """
        Render a template with CSP nonce support.

        Args:
            template_name: Name of the template file
            request: FastAPI request object

        Returns:
            Rendered HTML response
        """
        if not self.templates:
            raise HTTPException(
                status_code=500, detail="Template engine not configured"
            )

        try:
            from resync.core.csp_template_response import CSPTemplateResponse

            nonce = getattr(request.state, "csp_nonce", "")
            return CSPTemplateResponse(
                template_name,
                {
                    "request": request,
                    "nonce": nonce,
                    "settings": {
                        "project_name": settings.project_name,
                        "version": settings.project_version,
                        "environment": settings.environment.value,
                    },
                },
                self.templates,
            )
        except FileNotFoundError:
            logger.error("template_not_found", template=template_name)
            raise HTTPException(
                status_code=404, detail=f"Template {template_name} not found"
            )
        except Exception as e:
            logger.error("template_render_error", template=template_name, error=str(e))
            raise HTTPException(status_code=500, detail="Internal server error")

    async def _handle_csp_report(self, request: Request) -> JSONResponse:
        """
        Handle CSP violation reports with validation.

        Args:
            request: FastAPI request containing CSP report

        Returns:
            JSON response acknowledging receipt
        """
        try:
            from resync.csp_validation import process_csp_report

            result = await process_csp_report(request)

            # Log violation details
            report = result.get("report", {})
            csp_report = (
                report.get("csp-report", report) if isinstance(report, dict) else report
            )

            logger.warning(
                "csp_violation_reported",
                client_host=request.client.host if request.client else "unknown",
                blocked_uri=csp_report.get("blocked-uri", "unknown"),
                violated_directive=csp_report.get("violated-directive", "unknown"),
                effective_directive=csp_report.get("effective-directive", "unknown"),
            )

            return JSONResponse(content={"status": "received"}, status_code=200)

        except Exception as e:
            logger.error(
                "csp_report_error",
                error_type=type(e).__name__,
                client_host=request.client.host if request.client else "unknown",
            )
            # Always return 200 to prevent information leakage
            return JSONResponse(content={"status": "received"}, status_code=200)


# Module-level factory instance
_factory = ApplicationFactory()


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    This is the main entry point for application creation,
    providing a fully configured FastAPI instance.

    Returns:
        Configured FastAPI application
    """
    return _factory.create_application()
