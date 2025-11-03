"""
FastAPI application main entry point.

This module creates and configures the FastAPI application with all routers
included under the /api/v1 prefix for versioned API endpoints.
"""

import asyncio  # used for simulating streaming responses
import json  # added for WebSocket message handling
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Awaitable, Iterable

from fastapi import Body
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.websockets import WebSocket, WebSocketDisconnect
import httpx  # used for validating external connections
import uuid  # used for generating correlation IDs for WebSockets

# Attempt to import an improved lifespan implementation.  When present
# this lifespan will set up shared resources such as Redis and handle
# graceful shutdown of external clients.  If the import fails the
# application will fall back to the legacy lifespan defined below.
try:
    from .lifespan import lifespan as app_lifespan  # type: ignore
except Exception:
    app_lifespan = None  # type: ignore

# Import do módulo que registra handlers
try:
    from resync.api.exception_handlers import register_exception_handlers
except Exception:
    register_exception_handlers = None


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager."""
    # Startup
    yield
    # Shutdown
    # Fechar conexões HTTPX se estiverem em uso
    try:
        from resync.services.tws_service import shutdown_httpx
        await shutdown_httpx()
    except Exception:
        logger.exception("Error shutting down HTTPX client")


def _deduplicate_paths(paths: Iterable[Path]) -> list[Path]:
    """Return a list of unique paths preserving order."""
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def _resolve_resource_directory(env_var: str, *relative_parts: str) -> Path | None:
    """Resolve a resource directory using overrides and fallback locations."""
    candidates: list[Path] = []

    override = os.getenv(env_var)
    if override:
        candidates.append(Path(override).expanduser())

    module_path = Path(__file__).resolve()
    candidates.extend(
        [
            module_path.parent / Path(*relative_parts),
            module_path.parents[1] / Path(*relative_parts),
            module_path.parents[2] / Path(*relative_parts),
        ]
    )

    for candidate in _deduplicate_paths(candidates):
        if candidate.exists():
            return candidate

    logger.warning(
        "Unable to resolve resource directory for %s; tried: %s",
        env_var,
        ", ".join(str(path) for path in _deduplicate_paths(candidates)),
    )
    return None


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Resync API",
        description="Unified API for Resync TWS Integration",
        version="1.0.0",
        # Prefer the improved lifespan when available
        lifespan=app_lifespan or lifespan,
    )

    # Initialise in-memory TWS connection configuration.  When optional
    # pydantic settings are unavailable, the application will fall back
    # to storing TWS connection parameters here.  The mock_mode flag
    # indicates whether TWS calls should return empty results.
    app.state._tws_config = {
        "host": None,
        "port": None,
        "user": None,
        "password": None,
        "verify_tls": False,
        "mock_mode": True,
    }

    # -------------------------------------------------------------------------
    # Middleware to add a correlation ID, measure response time and collect
    # simple metrics.  A global metrics dictionary is defined here to
    # accumulate counts and latencies of HTTP requests and WebSocket
    # interactions.  In a production system these metrics would be exported
    # to a monitoring backend rather than stored in memory.

    # Metrics storage (captured by closure in middleware and WebSocket handler)
    metrics = {
        "http_request_count": 0,
        "http_request_errors": 0,
        "http_request_latency_sum_ms": 0.0,
        "ws_connection_count": 0,
        "ws_message_count": 0,
    }

    import uuid  # import inside function scope to avoid leaking to module level
    import time
    from starlette.middleware.base import BaseHTTPMiddleware

    class CorrelationIdMiddleware(BaseHTTPMiddleware):  # type: ignore[misc]
        async def dispatch(self, request, call_next):  # type: ignore[override]
            # Use provided correlation ID or generate a new one
            correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
            start_time = time.monotonic()
            # Store correlation ID on request.state for downstream handlers
            request.state.correlation_id = correlation_id
            try:
                response = await call_next(request)
            except Exception:
                # Count uncaught exceptions as errors
                metrics["http_request_errors"] += 1
                raise
            finally:
                # Always record latency and count
                elapsed_ms = (time.monotonic() - start_time) * 1000.0
                metrics["http_request_count"] += 1
                metrics["http_request_latency_sum_ms"] += elapsed_ms
            # Add headers to the response
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Process-Time-ms"] = f"{elapsed_ms:.2f}"
            return response

    app.add_middleware(CorrelationIdMiddleware)

    # Add CORS middleware.  Allowed origins are read from the environment
    # variable ``CORS_ALLOWED_ORIGINS`` as a comma-separated list.  When not
    # specified the wildcard is allowed to enable local development.  To
    # restrict CORS in production, set the variable to a comma-separated
    # list of trusted origins (e.g. ``https://example.com,https://foo.bar``).
    import os  # import here to avoid polluting module namespace
    cors_origins_env = os.getenv("CORS_ALLOWED_ORIGINS")
    if cors_origins_env:
        allowed_origins = [orig.strip() for orig in cors_origins_env.split(",") if orig.strip()]
    else:
        # Default to wildcard in absence of configuration.  A wildcard
        # simplifies development but should be overridden in production.
        allowed_origins = ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Registrar exception handlers (se disponível)
    if register_exception_handlers:
        register_exception_handlers(app)

    # Determine directories for static assets and templates using flexible fallbacks
    static_dir = _resolve_resource_directory("RESYNC_STATIC_DIR", "static")
    if static_dir:
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    else:
        logger.warning(
            "Static assets directory not found; static file serving disabled. "
            "Set RESYNC_STATIC_DIR or ensure a 'static' directory is present."
        )

    templates_dir = _resolve_resource_directory("RESYNC_TEMPLATES_DIR", "templates")
    if templates_dir is None:
        logger.error(
            "Templates directory not found. Set RESYNC_TEMPLATES_DIR or ensure a 'templates' directory exists."
        )
        templates: Jinja2Templates | None = None
    else:
        templates = Jinja2Templates(directory=str(templates_dir))

    def render_template(template_name: str, context: dict[str, Any]) -> HTMLResponse:
        if templates is None:
            raise HTTPException(
                status_code=503,
                detail="Template rendering is unavailable because the templates directory is missing.",
            )
        return templates.TemplateResponse(template_name, context)

    # Background task registry to manage lifecycle and graceful shutdown
    app.state.background_tasks: set[asyncio.Task[Any]] = set()  # type: ignore[type-arg]

    def register_background_task(coro: Awaitable[Any], *, name: str) -> asyncio.Task[Any]:
        task = asyncio.create_task(coro, name=name)
        app.state.background_tasks.add(task)

        def _cleanup(completed: asyncio.Task[Any]) -> None:
            app.state.background_tasks.discard(completed)
            if completed.cancelled():
                return
            try:
                exception = completed.exception()
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("Unable to retrieve exception for task %s: %s", name, exc)
                return
            if exception:
                logger.exception("Background task %s failed", name, exc_info=exception)

        task.add_done_callback(_cleanup)
        return task

    app.state.register_background_task = register_background_task  # type: ignore[attr-defined]

    async def _cancel_background_tasks() -> None:
        tasks = list(app.state.background_tasks)
        if not tasks:
            return
        for task in tasks:
            if not task.done():
                task.cancel()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for task, result in zip(tasks, results):
            if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                logger.warning(
                    "Background task %s raised during shutdown: %s",
                    task.get_name(),
                    result,
                )

    app.add_event_handler("shutdown", _cancel_background_tasks)

    # ---------------------------------------------------------------------
    # Admin authentication and CSRF protection
    #
    # The admin section of the API exposes configuration endpoints that
    # modify sensitive settings.  To protect these routes, a simple
    # authentication and CSRF mechanism is implemented.  A basic
    # username/password pair must be provided via HTTP Basic auth, and a
    # CSRF token must accompany each request.  Credentials and the
    # required CSRF token are sourced from environment variables
    # (ADMIN_USERNAME, ADMIN_PASSWORD, CSRF_TOKEN) for configurability.

    from fastapi.security import HTTPBasic, HTTPBasicCredentials

    security = HTTPBasic()

    def require_admin(credentials: HTTPBasicCredentials = Depends(security)) -> str:
        """Validate admin credentials via HTTP Basic authentication.

        Raises HTTP 401 if the provided username or password do not match
        the configured admin credentials.  Credentials are read from
        environment variables to avoid hardcoding secrets in code.  In
        absence of configuration, defaults are 'admin' / 'admin'.
        """
        import os
        correct_username = os.getenv("ADMIN_USERNAME", "admin")
        correct_password = os.getenv("ADMIN_PASSWORD", "admin")
        provided_username = credentials.username
        provided_password = credentials.password or ""
        if provided_username != correct_username or provided_password != correct_password:
            raise HTTPException(status_code=401, detail="Invalid admin credentials")
        return provided_username

    def verify_csrf(request: Request) -> None:
        """Check for a valid CSRF token in the request headers.

        This function inspects the ``X-CSRF-Token`` header and compares
        it against the ``CSRF_TOKEN`` environment variable.  A 403
        Forbidden response is raised if the token is missing or does
        not match.  When CSRF_TOKEN is not configured, CSRF checks
        are disabled.
        """
        import os
        expected_token = os.getenv("CSRF_TOKEN")
        if not expected_token:
            # CSRF protection disabled; no-op
            return None
        token = request.headers.get("X-CSRF-Token")
        if token != expected_token:
            raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    # Incluir routers principais (incluir os mais simples primeiro)
    try:
        from resync.api.cache import cache_router
        app.include_router(cache_router, prefix="/api/v1/cache")
    except Exception as exc:
        logger.warning("Cache router not included: %s", exc)

    try:
        # health simplified (menor superfície)
        from resync.api.health_simplified import health_router
        app.include_router(health_router, prefix="/health")
    except Exception as exc:
        logger.warning("Health router not included: %s", exc)

    # Register NLP router for log field extraction using Promptify.  The
    # router will only be included if both the module and its
    # dependencies can be imported.  If Promptify is not installed,
    # this silently fails and the NLP endpoints will be unavailable.
    try:
        from resync.fastapi_app.routes_nlp import router as nlp_router  # type: ignore
        app.include_router(nlp_router)
    except Exception:
        pass

    # outros routers (audit, chat) serão incluídos em fases B/C

    # Serve the main dashboard page at the root.  This route renders the
    # ``index.html`` template so users can access the frontend.  Without
    # this route, the root path returns 404 and the dashboard cannot be
    # loaded via a browser.
    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):  # type: ignore[valid-type]
        return render_template("index.html", {"request": request})

    # Basic API Endpoints (temporary implementation)
    @app.get("/api/v1/status")
    async def get_status():
        """Get system status."""
        # NOTE: This status endpoint returns a minimal structure used by the
        # frontend dashboard.  It exposes lists for ``workstations`` and
        # ``jobs`` even when running in mock mode so that the client
        # JavaScript can calculate counts without encountering undefined
        # values.  In a production deployment this route should be
        # implemented to retrieve real data from the TWS service.
        return {
            "tws_connected": False,
            "mock_mode": True,
            "agents_loaded": 0,
            "knowledge_graph": "available",
            "workstations": [],
            "jobs": [],
        }

    @app.get("/api/v1/chat")
    async def get_chat():
        """Basic chat endpoint."""
        return {"message": "Chat endpoint working", "status": "active"}

    @app.get("/api/v1/agents/")
    async def list_agents():
        """List all agents."""
        return [
            {
                "id": "test-agent-1",
                "name": "Test Agent 1",
                "role": "Tester",
                "goal": "To be tested",
                "model": "test-model",
            }
        ]

    @app.get("/api/v1/agents/{agent_id}")
    async def get_agent(agent_id: str):
        """Get agent details."""
        return {
            "id": agent_id,
            "name": f"Agent {agent_id}",
            "role": "Assistant",
            "goal": "To assist users",
            "model": "test-model",
        }

    # --- RAG Endpoints ---
    try:
        # Import the RAG client only if available.
        from resync.services.rag_client import rag_client, RAGUploadResponse, RAGJobStatus  # type: ignore
    except Exception:
        rag_client = None  # type: ignore
    # Import create_file_ingestor regardless of rag_client availability.  This
    # ensures the ingestion endpoints can still function even if the RAG
    # microservice is not present.
    try:
        from resync.core.file_ingestor import create_file_ingestor  # type: ignore
    except Exception:
        create_file_ingestor = None  # type: ignore

    @app.post("/api/v1/rag/upload")
    async def upload_rag():
        """Upload a document to the RAG service and return a job identifier.

        This simplified implementation does not process multipart form-data
        because the optional dependency ``python-multipart`` is not installed
        in the execution environment.  Instead, it returns a 501 error when
        the RAG client is unavailable and a 503 error indicating that
        multipart file uploads are unsupported.
        """
        # Reject if RAG service is disabled
        if rag_client is None:
            raise HTTPException(status_code=501, detail="RAG service not available")
        # Without python-multipart installed, FastAPI cannot parse UploadFile objects.
        # Inform the caller that file upload support is unavailable.
        raise HTTPException(status_code=503, detail="Multipart file upload not supported in this deployment")

    @app.get("/api/v1/rag/jobs/{job_id}")
    async def get_rag_job_status(job_id: str):
        """Get the status of a RAG processing job."""
        if rag_client is None:
            raise HTTPException(status_code=501, detail="RAG service not available")
        try:
            status = await rag_client.get_job_status(job_id)
            # Convert Pydantic model to dict for JSON serialisation
            return status.dict()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    # ---------------------------------------------------------------------
    # RAG package ingestion endpoints
    #
    # In the absence of multipart/form-data support (no python-multipart), we
    # provide an alternative mechanism for ingesting knowledge packages that
    # reside on the server.  The ``knowledge_base`` directory contains
    # subdirectories with static documentation (e.g. manuals, APIs).  These
    # endpoints allow the frontend to discover available packages and trigger
    # ingestion via the SimpleFileIngestor.  The ingested content can then be
    # searched or used by the chat system.

    from resync.core.knowledge_graph import AsyncKnowledgeGraph

    # Define base path for knowledge packages relative to the application
    _kb_base = Path(__file__).resolve().parents[2] / "knowledge_base"

    @app.get("/api/v1/rag/packages")
    async def list_rag_packages() -> list[str]:  # pragma: no cover - simple I/O
        """List available knowledge packages on the server.

        Returns a list of directory names under the ``knowledge_base`` folder.
        An empty list is returned if the directory does not exist or has
        no subdirectories.
        """
        try:
            if not _kb_base.exists() or not _kb_base.is_dir():
                return []
            packages = []
            for entry in _kb_base.iterdir():
                if entry.is_dir():
                    packages.append(entry.name)
            return packages
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.post("/api/v1/rag/packages/{package_name}/ingest")
    async def ingest_rag_package(package_name: str):  # pragma: no cover - simple I/O
        """Ingest all files from a server-side knowledge package.

        This endpoint walks the specified package directory under
        ``knowledge_base`` and ingests every file via the file ingestor.  The
        ingestion result includes the number of files processed.  If the
        package is not found, a 404 response is returned.
        """
        pkg_path = _kb_base / package_name
        if not pkg_path.exists() or not pkg_path.is_dir():
            raise HTTPException(status_code=404, detail="Knowledge package not found")
        # Collect all file paths recursively
        file_paths: list[str] = []
        import os  # import locally to avoid pollution if unused
        for root, _, files in os.walk(pkg_path):
            for name in files:
                file_paths.append(str(Path(root) / name))
        if not file_paths:
            return {"indexed": 0, "message": "No files to ingest"}
        try:
            # Create a new knowledge graph and file ingestor
            kg = AsyncKnowledgeGraph()
            fi = create_file_ingestor(kg)
            # Ingest files concurrently
            results = await fi.batch_ingest(file_paths)  # type: ignore[call-arg]
            return {"indexed": len(results), "message": f"Ingested {len(results)} files"}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/v1/audit/metrics")
    async def get_audit_metrics():
        """Get audit metrics."""
        return {"pending": 0, "approved": 0, "rejected": 0}

    @app.post("/api/v1/audit/review")
    async def audit_review():
        """Review audit item."""
        return {"memory_id": "test", "action": "approved", "status": "success"}

    # ---------------------------------------------------------------------
    # Observability endpoints
    #
    # Expose collected metrics for HTTP and WebSocket traffic.  The metrics
    # dictionary is closed over from the middleware defined earlier in
    # create_app().  Average latency is computed on-the-fly to avoid
    # division by zero.
    @app.get("/api/v1/observability/metrics")
    async def get_observability_metrics():  # pragma: no cover - simple I/O
        count = metrics["http_request_count"] or 1
        avg_latency = metrics["http_request_latency_sum_ms"] / count
        # Include any domain-specific gauges such as SLA risk scores stored on app.state
        sla_risks: dict[str, float] = getattr(app.state, "sla_risk_scores", {})
        return {
            **metrics,
            "http_request_avg_latency_ms": avg_latency,
            "sla_risk_scores": sla_risks,
        }

    @app.get("/metrics", response_class=PlainTextResponse)
    async def get_prometheus_metrics():  # pragma: no cover - simple I/O
        """Expose metrics in Prometheus text format.

        The metrics exported here are a minimal subset suitable for a
        demonstration environment.  In a production system you would
        likely use the ``prometheus_client`` library to collect and
        export a richer set of metrics.
        """
        # Build metrics lines
        lines = []
        # HTTP request count
        lines.append("# HELP resync_http_requests_total Total number of HTTP requests")
        lines.append("# TYPE resync_http_requests_total counter")
        lines.append(f"resync_http_requests_total {metrics['http_request_count']}")
        # HTTP error count
        lines.append("# HELP resync_http_errors_total Total number of HTTP request errors")
        lines.append("# TYPE resync_http_errors_total counter")
        lines.append(f"resync_http_errors_total {metrics['http_request_errors']}")
        # HTTP latency
        lines.append("# HELP resync_http_request_latency_seconds_sum Sum of request latencies in seconds")
        lines.append("# TYPE resync_http_request_latency_seconds_sum counter")
        latency_seconds = metrics["http_request_latency_sum_ms"] / 1000.0
        lines.append(f"resync_http_request_latency_seconds_sum {latency_seconds}")
        lines.append("# HELP resync_http_request_latency_seconds_count Total number of latency measurements")
        lines.append("# TYPE resync_http_request_latency_seconds_count counter")
        lines.append(f"resync_http_request_latency_seconds_count {metrics['http_request_count']}")
        # WebSocket connections
        lines.append("# HELP resync_ws_connections_total Total number of WebSocket connections")
        lines.append("# TYPE resync_ws_connections_total counter")
        lines.append(f"resync_ws_connections_total {metrics['ws_connection_count']}")
        # WebSocket messages
        lines.append("# HELP resync_ws_messages_total Total number of WebSocket messages received")
        lines.append("# TYPE resync_ws_messages_total counter")
        lines.append(f"resync_ws_messages_total {metrics['ws_message_count']}")

        # SLA risk scores (gauge per stream)
        sla_risks = getattr(app.state, "sla_risk_scores", {})
        if sla_risks:
            lines.append("# HELP resync_sla_risk_score Heuristic SLA risk score per stream")
            lines.append("# TYPE resync_sla_risk_score gauge")
            for stream, score in sla_risks.items():
                # stream label may contain special characters; escape as needed
                label = stream.replace('"', '\"')
                lines.append(f'resync_sla_risk_score{{stream="{label}"}} {score}')
        return "\n".join(lines) + "\n"

    # --- TWS Endpoints ---
    try:
        from resync.services.tws_service import OptimizedTWSClient
        from resync.config.settings import settings as app_settings  # rename to avoid shadowing outer settings
    except Exception:
        OptimizedTWSClient = None  # type: ignore
        app_settings = None  # type: ignore

    async def _get_tws_client() -> object | None:
        """Lazy initialise a TWS client based on application settings.

        Returns None if the client cannot be created (e.g. missing settings or in mock mode).
        """
        # If the TWS client class is unavailable, or if neither the
        # application settings nor in-memory configuration are defined,
        # return None to indicate mock mode.
        if OptimizedTWSClient is None:
            return None
        # Check for cached client
        client = getattr(app.state, "_tws_client", None)
        if client:
            return client  # type: ignore[return-value]
        # Determine whether we should operate in mock mode and read
        # configuration values.  If the pydantic settings module is
        # unavailable (app_settings is None), fall back to the values
        # stored in app.state._tws_config.
        if app_settings is None:
            cfg = app.state._tws_config
            if cfg.get("mock_mode", True):
                return None
            host = cfg.get("host")
            port = cfg.get("port")
            user = cfg.get("user")
            password = cfg.get("password")
            verify = cfg.get("verify_tls", False)
            if not all([host, port, user, password]):
                return None
            client = OptimizedTWSClient(
                hostname=host,
                port=port,
                username=user,
                password=password,
                engine_name=getattr(app_settings, "engine_name", "tws-engine") if app_settings else "tws-engine",
                engine_owner=getattr(app_settings, "engine_owner", "tws-owner") if app_settings else "tws-owner",
            )
            # Optionally set TLS verification on client if supported
            # (OptimizedTWSClient constructor may not accept verify argument)
            app.state._tws_client = client  # cache
            return client  # type: ignore[return-value]
        # If app_settings is available, follow existing configuration
        if getattr(app_settings, "tws_mock_mode", True):
            return None
        host = getattr(app_settings, "tws_host", None)
        port = getattr(app_settings, "tws_port", None)
        user = getattr(app_settings, "tws_user", None)
        password_obj = getattr(app_settings, "tws_password", None)
        password = (password_obj.get_secret_value() if password_obj else None)
        if not all([host, port, user, password]):
            return None
        client = OptimizedTWSClient(
            hostname=host,
            port=port,
            username=user,
            password=password,
            engine_name=getattr(app_settings, "engine_name", "tws-engine"),
            engine_owner=getattr(app_settings, "engine_owner", "tws-owner"),
        )
        app.state._tws_client = client  # cache
        return client  # type: ignore[return-value]

    @app.get("/api/v1/tws/workstations")
    async def get_tws_workstations():
        """Return the status of workstations from TWS.

        In mock mode, returns an empty list.  In production, fetches from the TWS client.
        """
        client = await _get_tws_client()
        if client is None:
            # Return empty list in mock mode or if client cannot be created
            return []
        try:
            workstations = await client.get_workstations_status()
            # Convert Pydantic models to dicts
            return [ws.dict() for ws in workstations]
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/v1/tws/jobs")
    async def get_tws_jobs():
        """Return the status of jobs from TWS."""
        client = await _get_tws_client()
        if client is None:
            return []
        try:
            jobs = await client.get_jobs_status()
            return [job.dict() for job in jobs]
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/v1/tws/system_status")
    async def get_tws_system_status():
        """Return the overall system status from TWS."""
        client = await _get_tws_client()
        if client is None:
            # Basic mock status
            return {
                "tws_connected": False,
                "workstations": [],
                "jobs": [],
                "critical_jobs": [],
            }
        try:
            system_status = await client.get_system_status()
            return system_status.dict()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    # ---------------------------------------------------------------------
    # Admin TWS connection configuration endpoints
    #
    # These endpoints allow administrators to read and update the
    # connection parameters (host, port, user, password, TLS verify) used to
    # communicate with the HCL TWS instance.  The settings are stored
    # within the application settings object (app_settings) but passwords are
    # not returned to the client for security reasons.

    from pydantic import SecretStr
    import httpx  # type: ignore

    @app.get(
        "/api/v1/admin/tws-connection",
        dependencies=[Depends(require_admin), Depends(verify_csrf)],
    )
    async def get_tws_connection_config():
        """Return the current TWS connection parameters.

        Password is not included in the response for security.  If the
        application is running in mock mode or configuration is incomplete,
        values may be null.
        """
        try:
            # If application settings are unavailable (e.g. optional
            # pydantic_settings not installed), fall back to the values stored
            # in app.state._tws_config.
            if app_settings is None:
                cfg = app.state._tws_config
                return {
                    "host": cfg.get("host"),
                    "port": cfg.get("port"),
                    "user": cfg.get("user"),
                    "verify_tls": cfg.get("verify_tls", False),
                }
            return {
                "host": getattr(app_settings, "tws_host", None),
                "port": getattr(app_settings, "tws_port", None),
                "user": getattr(app_settings, "tws_user", None),
                "verify_tls": getattr(app_settings, "tws_verify", False),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.post(
        "/api/v1/admin/tws-connection",
        dependencies=[Depends(require_admin), Depends(verify_csrf)],
    )
    async def update_tws_connection_config(config: dict):
        """Update the TWS connection parameters.

        Expects JSON body with keys: host, port, user, password, verify_tls.
        The password is stored in a SecretStr.  Returns a success message
        without echoing the password back.
        """
        host = config.get("host")
        port = config.get("port")
        user = config.get("user")
        password = config.get("password")
        verify_tls = config.get("verify_tls", False)
        if not host or not user or not password or not port:
            raise HTTPException(status_code=400, detail="Missing required connection parameters")
        try:
            # Persist configuration differently depending on whether
            # application settings are available.  When the optional
            # pydantic settings module is missing, store the values in
            # app.state._tws_config; otherwise update the settings object.
            if app_settings is None:
                cfg = app.state._tws_config
                cfg["host"] = host
                cfg["port"] = int(port)
                cfg["user"] = user
                cfg["password"] = password  # store raw password (not returned)
                cfg["verify_tls"] = verify_tls
                cfg["mock_mode"] = False
                # Invalidate cached TWS client if present
                if hasattr(app.state, "_tws_client"):
                    app.state._tws_client = None
                return {"message": "TWS connection parameters updated successfully"}
            # Otherwise update the pydantic settings
            if hasattr(app_settings, "tws_mock_mode"):
                setattr(app_settings, "tws_mock_mode", False)
            setattr(app_settings, "tws_host", host)
            setattr(app_settings, "tws_port", int(port))
            setattr(app_settings, "tws_user", user)
            setattr(app_settings, "tws_password", SecretStr(password))  # type: ignore[arg-type]
            setattr(app_settings, "tws_verify", verify_tls)
            if hasattr(app.state, "_tws_client"):
                app.state._tws_client = None
            return {"message": "TWS connection parameters updated successfully"}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.post(
        "/api/v1/admin/tws-connection/test",
        dependencies=[Depends(require_admin), Depends(verify_csrf)],
    )
    async def test_tws_connection_parameters(config: dict):
        """Validate TWS connection parameters without updating the settings.

        Attempts to perform a HEAD request to the TWS service using the
        provided parameters.  Returns a JSON object indicating whether
        connectivity was successful along with a message.
        """
        host = config.get("host")
        port = config.get("port")
        user = config.get("user")
        password = config.get("password")
        verify_tls = config.get("verify_tls", False)
        if not host or not user or not password or not port:
            raise HTTPException(status_code=400, detail="Missing required connection parameters")
        base_url = f"http://{host}:{port}/twsd"
        try:
            async with httpx.AsyncClient(
                base_url=base_url,
                auth=(user, password),
                verify=verify_tls,
                timeout=httpx.Timeout(5.0, read=5.0, write=5.0, connect=5.0, pool=5.0),
            ) as client:
                response = await client.head("")
                response.raise_for_status()
            return {
                "valid": True,
                "message": f"Successfully validated connection to {host}:{port}",
            }
        except httpx.TimeoutException as exc:
            return {
                "valid": False,
                "message": f"TWS connection validation timed out: {exc}",
            }
        except Exception as exc:
            return {
                "valid": False,
                "message": f"TWS connection validation failed: {exc}",
            }

    @app.websocket("/api/v1/ws/{agent_id}")
    async def websocket_endpoint(websocket: WebSocket, agent_id: str) -> None:
        """WebSocket endpoint for real-time chat communication.

        This handler keeps the connection open, receives JSON payloads from the client
        and emits structured responses.  The expected payload has the form::

            {"type": "chat_message", "content": "...", "agent_id": "..."}

        The server responds with events of type ``stream`` (partial) or ``message`` (final).
        Since no real LLM integration is implemented here, the handler echoes the
        user's message with a simple acknowledgement.
        """
        # Accept the WebSocket connection and assign a correlation ID
        await websocket.accept()
        # Generate a unique correlation ID for this WebSocket session and
        # record the new connection in the metrics.  Note that ``metrics``
        # is closed over from ``create_app``.
        ws_corr_id = str(uuid.uuid4())
        websocket.state.correlation_id = ws_corr_id
        metrics["ws_connection_count"] += 1
        try:
            # Notify client that the connection is ready and include the
            # correlation ID in the system message.  Clients can use this to
            # correlate log entries with the server side.
            await websocket.send_json({
                "type": "system",
                "sender": "system",
                "message": f"Connected to agent {agent_id}",
                "is_final": True,
                "correlation_id": ws_corr_id,
            })
            while True:
                try:
                    data = await websocket.receive_text()
                except WebSocketDisconnect:
                    break
                # Increment message count for each inbound message
                metrics["ws_message_count"] += 1
                # Parse incoming JSON payload
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "sender": "system",
                        "message": "Invalid JSON payload",
                        "is_final": True,
                        "correlation_id": ws_corr_id,
                    })
                    continue
                # Handle different message types
                msg_type = payload.get("type")
                if msg_type == "chat_message":
                    content = payload.get("content", "")
                    # Construct a simple echo response.  In the future this is
                    # where the LLM or TWS integration would be invoked.
                    full_response = f"Recebido: {content}"
                    # Stream the response in chunks for a better UX.  Split
                    # the message into 40-character chunks and emit interim
                    # "stream" events before the final message.  This simulates
                    # a streaming response from a language model.
                    chunk_size = 40
                    for start in range(0, len(full_response), chunk_size):
                        segment = full_response[start:start + chunk_size]
                        is_last = start + chunk_size >= len(full_response)
                        if not is_last:
                            await websocket.send_json({
                                "type": "stream",
                                "sender": "agent",
                                "message": segment,
                                "is_final": False,
                                "correlation_id": ws_corr_id,
                            })
                        else:
                            await websocket.send_json({
                                "type": "message",
                                "sender": "agent",
                                "message": segment,
                                "is_final": True,
                                "correlation_id": ws_corr_id,
                            })
                else:
                    # Unknown type
                    await websocket.send_json({
                        "type": "error",
                        "sender": "system",
                        "message": f"Unsupported message type: {msg_type}",
                        "is_final": True,
                        "correlation_id": ws_corr_id,
                    })
        finally:
            try:
                await websocket.close()
            except Exception:
                pass

    # -----------------------------------------------------------------
    # Incident Management and Reporting Endpoints
    #
    # The following routes and utilities implement an in-memory incident
    # management system and a set of reporting endpoints.  These are
    # inserted here before the health check and return statement so they
    # become part of the application.  Because incidents are stored in
    # memory they will be lost when the application restarts.

    # Attempt to import Redis helper functions.  If Redis is available
    # and enabled, incidents will be persisted to Redis instead of kept
    # purely in memory.  On failure (library missing or disabled via
    # environment), the application falls back to an in-memory list.
    try:
        from resync.core.redis_init import get_redis_client, is_redis_available  # type: ignore
    except Exception:
        get_redis_client = None  # type: ignore
        def is_redis_available() -> bool:  # type: ignore
            return False

    # Initialise the incident list on the application state.  When
    # Redis is unavailable, incidents are appended to this list.  When
    # Redis is present, incidents are stored in the Redis database and
    # this list is unused.
    app.state.incidents = []  # type: ignore[attr-defined]

    # Helper functions for incident persistence.  These functions load and
    # store the incident list to/from Redis when it is available.  When
    # Redis is unavailable or disabled, they operate on the in-memory
    # ``app.state.incidents`` list.  Redis persistence uses a single key
    # ``resync:incidents`` storing a JSON array.
    async def _load_incidents() -> list[dict]:  # pragma: no cover - trivial I/O
        """Load the list of incidents from Redis or memory.

        If Redis is available and enabled (``RESYNC_DISABLE_REDIS`` is not
        set), this function retrieves the JSON array stored under the
        ``resync:incidents`` key.  If the key is absent or decoding
        fails, it falls back to the in-memory list stored on
        ``app.state.incidents``.
        """
        try:
            if callable(is_redis_available) and is_redis_available():
                import os as _os
                if _os.getenv("RESYNC_DISABLE_REDIS") != "1" and get_redis_client is not None:
                    client = get_redis_client()
                    data = await client.get("resync:incidents")  # type: ignore[attr-defined]
                    if data:
                        import json as _json
                        return _json.loads(data)
        except Exception:
            # ignore Redis errors and fall back to memory
            pass
        return list(getattr(app.state, "incidents", []))  # type: ignore[attr-defined]

    async def _save_incidents(incidents: list[dict]) -> None:  # pragma: no cover - trivial I/O
        """Persist the list of incidents to Redis and memory.

        Attempts to write the JSON array of incidents to the Redis key
        ``resync:incidents`` when Redis is available and enabled.
        Regardless of Redis availability, updates the in-memory list on
        ``app.state.incidents``.
        """
        try:
            if callable(is_redis_available) and is_redis_available():
                import os as _os
                if _os.getenv("RESYNC_DISABLE_REDIS") != "1" and get_redis_client is not None:
                    client = get_redis_client()
                    import json as _json
                    await client.set("resync:incidents", _json.dumps(incidents))  # type: ignore[attr-defined]
                    app.state.incidents = incidents  # type: ignore[attr-defined]
                    return
        except Exception:
            # ignore Redis errors and proceed to update memory
            pass
        app.state.incidents = incidents  # type: ignore[attr-defined]

    def _calculate_incident_priority(impact: float, urgency: float) -> float:
        """Compute a priority score based on impact and urgency."""
        return impact * urgency

    @app.post("/api/v1/incidents")
    async def create_incident(incident: dict) -> dict:
        """Create a new incident and add it to the incident store.

        The payload may contain ``job_id``, ``workstation``, ``status``,
        ``root_cause`` and ``timestamp``.  Severity is derived from the
        status, impact from the job identifier length and urgency from
        recency.  Priority is computed as impact × urgency.  A unique
        identifier is assigned and the incident state is set to ``Novo``.
        """
        job_id = incident.get("job_id")
        workstation = incident.get("workstation")
        status = incident.get("status")
        root_cause = incident.get("root_cause")
        timestamp = incident.get("timestamp")
        # Map status to severity (simple heuristic)
        severity_map = {"ABEND": 3.0, "ERROR": 2.0, "WARNING": 1.0}
        sev = severity_map.get((status or "").upper(), 1.0)
        # Impact is approximated by length of job ID
        impact = float(len(job_id)) if job_id else 1.0
        # Compute urgency based on timestamp recency
        urgency = 1.0
        if timestamp:
            try:
                from datetime import datetime, timezone
                occurred = datetime.fromisoformat(timestamp)
                now = datetime.now(tz=occurred.tzinfo or timezone.utc)
                minutes_ago = (now - occurred).total_seconds() / 60.0
                urgency = max(1.0, 60.0 / (minutes_ago + 1.0))
            except Exception:
                urgency = 1.0
        priority = _calculate_incident_priority(impact, urgency)
        # Build and store the incident
        record = {
            "id": str(uuid.uuid4()),
            "job_id": job_id,
            "workstation": workstation,
            "status": status,
            "root_cause": root_cause,
            "timestamp": timestamp,
            "severity": sev,
            "impact": impact,
            "urgency": urgency,
            "priority": priority,
            "owner": None,
            "state": "Novo",
            "notes": [],
        }
        # Load current incidents, append the new record and persist
        incidents = await _load_incidents()
        incidents.append(record)
        await _save_incidents(incidents)
        return {"id": record["id"], "priority": priority}

    @app.get("/api/v1/incidents")
    async def list_incidents(status: str | None = None, sort: str | None = None) -> list[dict]:
        """Return incidents filtered by status and optionally sorted by priority."""
        incidents = await _load_incidents()
        filtered: list[dict] = []
        for inc in incidents:
            state = inc.get("state", "Novo").lower()
            if status == "open":
                if state in {"novo", "em andamento"}:
                    filtered.append(inc)
            elif status == "resolved":
                if state == "resolvido":
                    filtered.append(inc)
            elif status == "silenced":
                if state == "silenciado":
                    filtered.append(inc)
            else:
                filtered.append(inc)
        if sort == "priority":
            filtered.sort(key=lambda x: x.get("priority", 0.0), reverse=True)
        return filtered

    @app.post("/api/v1/incidents/{incident_id}/assign")
    async def assign_incident(incident_id: str, assignee: dict = Body(...)) -> dict:
        """Assign an incident to a specified owner and mark it as in progress."""
        owner = assignee.get("owner")
        incidents = await _load_incidents()
        for inc in incidents:
            if inc["id"] == incident_id:
                inc["owner"] = owner
                inc["state"] = "Em andamento"
                await _save_incidents(incidents)
                return {"id": incident_id, "owner": owner, "state": inc.get("state"), "priority": inc.get("priority")}
        raise HTTPException(status_code=404, detail="Incident not found")

    @app.post("/api/v1/incidents/{incident_id}/snooze")
    async def snooze_incident(incident_id: str, minutes: int = Body(...)) -> dict:
        """Silence an incident for a specified number of minutes and lower its priority."""
        incidents = await _load_incidents()
        for inc in incidents:
            if inc["id"] == incident_id:
                inc["state"] = "Silenciado"
                inc["urgency"] = max(0.1, inc.get("urgency", 1.0) * 0.1)
                inc["priority"] = _calculate_incident_priority(inc.get("impact", 1.0), inc["urgency"])
                await _save_incidents(incidents)
                return {"id": incident_id, "state": inc.get("state"), "priority": inc.get("priority")}
        raise HTTPException(status_code=404, detail="Incident not found")

    @app.post("/api/v1/incidents/{incident_id}/note")
    async def add_incident_note(incident_id: str, note_body: dict = Body(...)) -> dict[str, str]:
        """Append a note to an incident for audit and collaboration."""
        note = note_body.get("note")
        incidents = await _load_incidents()
        for inc in incidents:
            if inc["id"] == incident_id:
                inc.setdefault("notes", []).append(note)
                await _save_incidents(incidents)
                return {"id": incident_id}
        raise HTTPException(status_code=404, detail="Incident not found")

    @app.post("/api/v1/incidents/{incident_id}/open-runbook")
    async def open_runbook(incident_id: str) -> dict[str, str]:
        """Return a placeholder runbook URL based on the job identifier."""
        incidents = await _load_incidents()
        for inc in incidents:
            if inc["id"] == incident_id:
                job_id = inc.get("job_id") or "unknown"
                return {"id": incident_id, "url": f"/runbook/{job_id}"}
        raise HTTPException(status_code=404, detail="Incident not found")

    # -----------------------------------------------------------------
    # Reporting endpoints
    from datetime import datetime
    from collections import Counter

    @app.get("/api/v1/reports/operations")
    async def get_operations_report(from_date: str | None = None, to_date: str | None = None) -> dict:
        client = await _get_tws_client()
        # Date parsing reserved for future enhancements
        if client is None:
            return {
                "total_jobs": 0,
                "executed": 0,
                "pending": 0,
                "failed": 0,
                "top_failed_flows": [],
                "backlog": {},
            }
        try:
            jobs = await client.get_jobs_status()
            workstations = await client.get_workstations_status()
            executed = sum(1 for j in jobs if j.status == "SUCC")
            failed = sum(1 for j in jobs if j.status == "ABEND")
            pending = len(jobs) - executed - failed
            flow_failures: Counter[str] = Counter()
            for j in jobs:
                if j.status == "ABEND":
                    flow_failures[j.job_stream] += 1
            top_failed = [
                {"job_stream": fs, "failures": cnt}
                for fs, cnt in flow_failures.most_common(10)
            ]
            backlog: dict[str, int] = {}
            for j in jobs:
                if j.status not in {"SUCC", "ABEND"}:
                    backlog[j.workstation] = backlog.get(j.workstation, 0) + 1
            return {
                "total_jobs": len(jobs),
                "executed": executed,
                "pending": pending,
                "failed": failed,
                "top_failed_flows": top_failed,
                "backlog": backlog,
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/v1/reports/reliability")
    async def get_reliability_report(window: str = "7d") -> dict:
        """Return reliability metrics based on recent job execution history.

        The window parameter is currently ignored but is reserved for future
        filtering by time range.  When a TWS client is available, this
        endpoint computes the mean time to acknowledge (MTTA) and mean
        time to repair (MTTR) by analysing the execution history of jobs.
        Each execution's duration is derived from start and end timestamps
        reported by the TWS API.  Flaky jobs are identified when their
        failure rate exceeds 30 %.

        If the TWS client or detailed execution history is unavailable,
        approximate values are returned based on the number of jobs.
        """
        client = await _get_tws_client()
        # Default response for mock mode or missing client
        if client is None:
            return {
                "mtta_minutes": 0.0,
                "mttr_minutes": 0.0,
                "flaky_jobs": [],
            }
        try:
            # Retrieve the current status of all jobs
            jobs = await client.get_jobs_status()
            # Track failure counts for flaky job detection
            total_counts: Counter[str] = Counter()
            fail_counts: Counter[str] = Counter()
            # Collect execution durations (in minutes) for MTTA/MTTR
            mtta_durations: list[float] = []
            mttr_durations: list[float] = []
            # Loop through each job and gather its execution history
            for j in jobs:
                total_counts[j.name] += 1
                if j.status.upper() == "ABEND":
                    fail_counts[j.name] += 1
                # Fetch detailed history for the job to compute durations
                try:
                    details = await client.get_job_details(j.name)
                    for exec_ in details.execution_history:
                        # Compute duration from start and end times
                        # Only consider entries with both timestamps present
                        if exec_.start_time and exec_.end_time:
                            duration_minutes = (exec_.end_time - exec_.start_time).total_seconds() / 60.0
                            # All durations contribute to MTTA
                            mtta_durations.append(duration_minutes)
                            # Failed runs contribute to MTTR
                            if exec_.status and exec_.status.upper() == "ABEND":
                                mttr_durations.append(duration_minutes)
                except Exception:
                    # Ignore errors when fetching details; continue with others
                    continue
            # Compute averages (fallback to heuristics if no durations collected)
            mtta = (sum(mtta_durations) / len(mtta_durations)) if mtta_durations else float(len(jobs)) * 2.5
            mttr = (sum(mttr_durations) / len(mttr_durations)) if mttr_durations else float(len(jobs)) * 5.0
            # Identify flaky jobs where failure rate > 30 %
            flaky: list[dict[str, float]] = []
            for name, total in total_counts.items():
                if total > 0:
                    rate = fail_counts[name] / total
                    if rate > 0.3:
                        flaky.append({"job": name, "failure_rate": rate})
            return {
                "mtta_minutes": mtta,
                "mttr_minutes": mttr,
                "flaky_jobs": flaky,
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/v1/reports/sla")
    async def get_sla_report(period: str = "week") -> dict:
        """Return SLA metrics and risk map based on job execution history.

        The ``period`` query parameter is currently informational and
        reserved for future filtering by week, month, etc.  This endpoint
        computes how many jobs have SLAs defined (all jobs), how many
        completed successfully, and estimates drift statistics (mean and
        p95) from the durations of recent executions.  A risk map
        aggregates the number of failed executions per hour of day.
        """
        client = await _get_tws_client()
        if client is None:
            return {
                "slas_defined": 0,
                "slas_met": 0,
                "drift_mean_minutes": 0.0,
                "drift_p95_minutes": 0.0,
                "risk_map": {},
            }
        try:
            jobs = await client.get_jobs_status()
            total = len(jobs)
            # Count jobs with success status as meeting SLA
            met = sum(1 for j in jobs if j.status and j.status.upper() == "SUCC")
            # Collect execution durations (minutes) to derive drift statistics
            durations: list[float] = []
            risk_map: dict[str, int] = {}
            for job in jobs:
                try:
                    details = await client.get_job_details(job.name)
                    for exec_ in details.execution_history:
                        if exec_.start_time and exec_.end_time:
                            dur = (exec_.end_time - exec_.start_time).total_seconds() / 60.0
                            durations.append(dur)
                            # Record failed execution in risk map by hour
                            if exec_.status and exec_.status.upper() == "ABEND":
                                hour_key = str(exec_.start_time.hour)
                                risk_map[hour_key] = risk_map.get(hour_key, 0) + 1
                except Exception:
                    continue
            # Compute mean and p95 drift (use heuristics if no durations)
            if durations:
                durations_sorted = sorted(durations)
                mean_drift = sum(durations) / len(durations)
                # 95th percentile index
                idx95 = int(0.95 * len(durations_sorted))
                p95_drift = durations_sorted[idx95]
            else:
                # Fallback: use number of jobs to approximate
                mean_drift = float(max(total - met, 0)) * 1.5
                p95_drift = float(max(total - met, 0)) * 2.5
            return {
                "slas_defined": total,
                "slas_met": met,
                "drift_mean_minutes": mean_drift,
                "drift_p95_minutes": p95_drift,
                "risk_map": risk_map,
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/v1/reports/perf")
    async def get_performance_report(window: str = "24h") -> dict:
        client = await _get_tws_client()
        http_count = metrics.get("http_request_count", 0)
        http_errors = metrics.get("http_request_errors", 0)
        avg_latency = (
            metrics["http_request_latency_sum_ms"] / http_count
            if http_count
            else 0.0
        )
        if client is None:
            return {
                "api_avg_latency_ms": avg_latency,
                "api_error_count": http_errors,
                "resource_utilisation": {},
            }
        try:
            resources = await client.get_resource_usage()
            utilisation = {
                r.resource_name: {
                    "used": r.used_capacity,
                    "total": r.total_capacity,
                    "utilization_percentage": r.utilization_percentage,
                }
                for r in resources
            }
            return {
                "api_avg_latency_ms": avg_latency,
                "api_error_count": http_errors,
                "resource_utilisation": utilisation,
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    # -----------------------------------------------------------------
    # SLA Watch heuristic report
    #
    # This endpoint computes a heuristic risk score for each job stream based
    # on recent job and workstation metrics.  The intention is to provide
    # an early warning of SLA violations by combining several signals: the
    # number of abended or late jobs in the stream, the number of running
    # jobs, and the queue depth across workstations.  Each factor is
    # weighted to produce a score between 0 and 100, where higher values
    # indicate higher risk.  The resulting scores are also stored on
    # ``app.state.sla_risk_scores`` for inclusion in observability metrics.
    from collections import defaultdict

    def _compute_sla_risk(jobs: list[dict], workstations: list[dict]) -> dict[str, float]:
        """Compute an SLA risk score per job stream.

        Args:
            jobs: List of job dicts returned by get_jobs_status().  Each dict must
                contain at least ``stream`` and ``status`` keys.
            workstations: List of workstation dicts returned by get_workstations_status().
                Each dict must contain ``queue_depth``.

        Returns:
            Mapping from stream name to risk score (0–100).
        """
        abend_counts: dict[str, int] = defaultdict(int)
        late_counts: dict[str, int] = defaultdict(int)
        running_counts: dict[str, int] = defaultdict(int)
        for job in jobs:
            stream = job.get("stream") or job.get("job_stream") or "unknown"
            status = str(job.get("status", "")).upper()
            if status == "ABEND":
                abend_counts[stream] += 1
            elif status not in {"SUCC", "SUCCESS"}:
                # Treat any non-success as a potential late job
                late_counts[stream] += 1
            if status in {"RUNNING", "HOLD"}:
                running_counts[stream] += 1
        # Average queue depth across workstations
        total_depth = 0.0
        for ws in workstations:
            try:
                total_depth += float(ws.get("queue_depth", 0) or 0)
            except Exception:
                continue
        avg_depth = total_depth / max(len(workstations), 1)
        scores: dict[str, float] = {}
        # Combine all streams that appear in any count
        all_streams = set(list(abend_counts.keys()) + list(late_counts.keys()) + list(running_counts.keys()))
        for stream in all_streams:
            base_score = (
                abend_counts.get(stream, 0) * 50
                + late_counts.get(stream, 0) * 20
                + running_counts.get(stream, 0) * 5
            )
            # Depth contributes up to 20 points
            depth_score = min(avg_depth * 2, 20)
            score = base_score + depth_score
            # Normalise to 0–100 range relative to a plausible maximum
            max_possible = 50 * 5 + 20 * 10 + 5 * 20 + 20  # assume maximum counts
            normalised = (score / max_possible) * 100.0
            scores[stream] = round(min(normalised, 100.0), 2)
        return scores

    @app.get("/api/v1/reports/sla_watch")
    async def get_sla_watch_report() -> dict[str, float]:  # pragma: no cover - complex I/O
        """Compute a heuristic SLA risk score per job stream.

        Synthesises information from TWS job statuses and workstation queue
        depths to estimate how likely each stream is to violate its SLA in
        the near future.  Heuristic weights emphasise abended jobs, then
        late jobs, running jobs and queue depth.  The resulting scores
        are stored on ``app.state.sla_risk_scores`` for exposure via
        observability metrics.
        """
        client = await _get_tws_client()
        if client is None:
            # Clear and return empty if in mock mode
            app.state.sla_risk_scores = {}
            return {}
        try:
            jobs_models = await client.get_jobs_status()
            jobs = [job.dict() for job in jobs_models]
            ws_models = await client.get_workstations_status()
            workstations = [ws.dict() for ws in ws_models]
            scores = _compute_sla_risk(jobs, workstations)
            app.state.sla_risk_scores = scores
            return scores
        except Exception as exc:
            app.state.sla_risk_scores = {}
            raise HTTPException(status_code=500, detail=str(exc))

    # -----------------------------------------------------------------
    # Job details and dependency graph endpoints
    @app.get("/api/v1/tws/jobs/{job_id}/details")
    async def get_job_details_endpoint(job_id: str):
        client = await _get_tws_client()
        if client is None:
            return {}
        try:
            details = await client.get_job_details(job_id)
            return details.dict()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/v1/tws/jobs/{job_id}/log")
    async def get_job_log_endpoint(job_id: str, start: str | None = None, end: str | None = None):
        client = await _get_tws_client()
        if client is None:
            return ""
        try:
            log = await client.get_job_log(job_id)
            return log
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.post("/api/v1/tws/jobs/{job_id}/replay")
    async def replay_job_endpoint(job_id: str):
        return {
            "job_id": job_id,
            "dry_run": True,
            "diff": "No changes - mock implementation",
        }

    @app.get("/api/v1/tws/jobs/{job_id}/dependencies")
    async def get_job_dependencies_endpoint(job_id: str, depth: int = 1):
        client = await _get_tws_client()
        if client is None:
            return {
                "job_id": job_id,
                "dependencies": [],
                "dependents": [],
                "dependency_graph": {},
            }
        try:
            tree = await client.get_job_dependencies(job_id)
            return tree.dict()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/v1/tws/graph/criticalpath")
    async def get_critical_path_graph():
        client = await _get_tws_client()
        if client is None:
            return []
        try:
            critical_jobs = await client.get_critical_path_status()
            return [cj.dict() for cj in critical_jobs]
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    # -----------------------------------------------------------------
    # Scheduled reporting and Teams integration
    #
    # The Resync API can optionally generate periodic reports and deliver
    # them via Microsoft Teams.  When the environment variable
    # ``TEAMS_WEBHOOK_URL`` is set, a background task will run on a
    # configurable interval (``REPORT_INTERVAL_MINUTES``) to compute
    # operational, reliability, SLA and performance reports using the
    # existing endpoints and send a concise summary to the configured
    # Teams channel.  An admin-only endpoint is also provided to
    # trigger a one-off report on demand.  If the webhook URL is not
    # configured, the scheduler is disabled.

    async def _compute_reports_summary() -> str:
        """Compute current reports and return a text summary.

        This helper calls the existing report endpoints internally to
        gather data.  In a production deployment you may call
        dependency-internal functions directly for efficiency; here we
        reuse the API endpoints to ensure consistent behaviour.
        """
        try:
            # Call report functions directly rather than using TestClient.
            # These functions are defined in the current scope when the
            # endpoints are registered.  Direct invocation avoids the
            # overhead and potential lifecycle issues of creating a
            # TestClient during runtime.
            ops = await get_operations_report()  # type: ignore[arg-type]
            rel = await get_reliability_report()  # type: ignore[arg-type]
            sla = await get_sla_report()  # type: ignore[arg-type]
            perf = await get_performance_report()  # type: ignore[arg-type]
        except Exception:
            # Fallback: use empty metrics on error
            ops = rel = sla = perf = {}
        lines: list[str] = []
        lines.append("**Resumo de Relatórios Resync**")
        # Operations
        if ops:
            lines.append(f"Total de jobs: {ops.get('total_jobs', 0)} (Executados: {ops.get('executed', 0)}, Pendentes: {ops.get('pending', 0)}, Falhos: {ops.get('failed', 0)})")
            top_flows = ops.get('top_failed_flows', [])
            if top_flows:
                flows_summary = ", ".join([f"{f['job_stream']} ({f['failures']})" for f in top_flows])
                lines.append(f"Top fluxos com falhas: {flows_summary}")
        # Reliability
        if rel:
            lines.append(f"MTTA (min): {rel.get('mtta_minutes', 0.0):.1f}, MTTR (min): {rel.get('mttr_minutes', 0.0):.1f}")
            flaky = rel.get('flaky_jobs', [])
            if flaky:
                flaky_summary = ", ".join([f"{f['job']} ({f['failure_rate']*100:.1f}% falhas)" for f in flaky])
                lines.append(f"Jobs instáveis: {flaky_summary}")
        # SLA
        if sla:
            lines.append(f"SLAs definidos: {sla.get('slas_defined', 0)}, cumpridos: {sla.get('slas_met', 0)}, drift médio: {sla.get('drift_mean_minutes', 0.0):.1f} min, p95 drift: {sla.get('drift_p95_minutes', 0.0):.1f} min")
        # Performance
        if perf:
            lines.append(f"Latência média API: {perf.get('api_avg_latency_ms', 0.0):.2f} ms, erros: {perf.get('api_error_count', 0)}")
        return "\n".join(lines)

    async def _send_report_to_teams(summary: str) -> None:
        """Send a report summary to Microsoft Teams via webhook.

        The webhook URL must be set via the ``TEAMS_WEBHOOK_URL``
        environment variable.  Errors are silently ignored.
        """
        import os
        webhook_url = os.getenv("TEAMS_WEBHOOK_URL")
        if not webhook_url:
            return
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(webhook_url, json={"text": summary})
        except Exception:
            # Ignore exceptions when sending notifications
            pass

    async def _schedule_reports() -> None:
        """Periodically compute and send reports to Teams.

        This function runs indefinitely until cancelled.  It reads the
        interval in minutes from the ``REPORT_INTERVAL_MINUTES`` environment
        variable (default: 1440 minutes / 24 hours).  If the Teams
        webhook is not configured, it exits immediately.
        """
        webhook_url = os.getenv("TEAMS_WEBHOOK_URL")
        if not webhook_url:
            logger.info("Skipping scheduled reports; TEAMS_WEBHOOK_URL not configured.")
            return
        try:
            interval_minutes = int(os.getenv("REPORT_INTERVAL_MINUTES", "1440"))
            if interval_minutes <= 0:
                raise ValueError("interval must be positive")
        except Exception as exc:
            logger.warning("Invalid REPORT_INTERVAL_MINUTES value: %s; using default 1440.", exc)
            interval_minutes = 1440

        delay_seconds = interval_minutes * 60.0
        logger.info("Starting scheduled report task with interval %s minutes.", interval_minutes)

        try:
            while True:
                try:
                    summary = await _compute_reports_summary()
                    await _send_report_to_teams(summary)
                except Exception as exc:
                    logger.exception("Failed to generate or send scheduled report: %s", exc)
                try:
                    await asyncio.sleep(delay_seconds)
                except asyncio.CancelledError:
                    logger.info("Scheduled report task cancelled.")
                    raise
        finally:
            logger.info("Scheduled report task exiting.")

    # Launch scheduler task at startup if Teams webhook configured
    try:
        if os.getenv("TEAMS_WEBHOOK_URL"):
            register_background_task(_schedule_reports(), name="scheduled-reports")
    except Exception as exc:
        logger.warning("Failed to start scheduled report task: %s", exc)

    @app.post(
        "/api/v1/admin/run-report",
        dependencies=[Depends(require_admin), Depends(verify_csrf)],
    )
    async def run_report_now() -> dict[str, str]:
        """Generate a report immediately and send it via Teams.

        This admin-only endpoint triggers the report generation and
        dispatches it to the configured Teams webhook.  It returns a
        message indicating success or failure.  If no webhook is
        configured, the summary is returned directly instead of
        attempting to send a notification.
        """
        summary = await _compute_reports_summary()
        import os
        if os.getenv("TEAMS_WEBHOOK_URL"):
            await _send_report_to_teams(summary)
            return {"message": "Report enviado via Teams"}
        return {"message": "Report gerado", "summary": summary}


    # -----------------------------------------------------------------
    # Template routes for additional UI pages
    @app.get("/reports", response_class=HTMLResponse)
    async def reports_page(request: Request):  # type: ignore[valid-type]
        return render_template("reports.html", {"request": request})

    @app.get("/incidents", response_class=HTMLResponse)
    async def incidents_page(request: Request):  # type: ignore[valid-type]
        return render_template("incidents.html", {"request": request})

    @app.get("/jobs/{job_id}", response_class=HTMLResponse)
    async def job_details_page(job_id: str, request: Request):  # type: ignore[valid-type]
        return render_template("job.html", {"request": request, "job_id": job_id})

    @app.get("/graph/{job_id}", response_class=HTMLResponse)
    async def job_graph_page(job_id: str, request: Request):  # type: ignore[valid-type]
        return render_template("graph.html", {"request": request, "job_id": job_id})

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "service": "resync-api"}

    # -----------------------------------------------------------------
    # Validate TWS API contract against the specification on startup.
    #
    # During development and continuous integration, it is valuable to
    # detect divergence between the endpoints used by our TWS client and
    # the official API specification (WA_API3_v2.json).  If the
    # specification file is present, validate the basic method/path
    # pairs.  If validation fails, log the error; do not raise to
    # avoid breaking the application in production.  Contract tests
    # enforce stricter behaviour via pytest (see tests/test_tws_contract.py).
    try:
        from resync.services.tws_routes import validate_routes, load_tws_api_spec
        # Routes used by the OptimizedTWSClient (without query params)
        _routes_to_validate = [
            ("GET", "/model/workstation"),
            ("GET", "/model/jobdefinition"),
            ("GET", "/model/jobdefinition/{job_id}"),
            ("GET", "/model/jobdefinition/{job_id}/dependencies"),
            ("GET", "/plan/current"),
            ("GET", "/plan/current/criticalpath"),
            ("GET", "/model/resource"),
        ]
        _spec = load_tws_api_spec()
        if _spec:
            try:
                validate_routes(_routes_to_validate, spec=_spec)
            except Exception as _e:
                # Log the error but do not stop application startup
                logger.warning("TWS API spec validation warning: %s", _e)
    except Exception:
        # Missing specification or validation library; skip contract check
        pass

    return app


# Create FastAPI application instance
app = create_app()
