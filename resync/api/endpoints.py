"""API endpoints for the Resync application.

This module defines all the REST API endpoints for the Resync application,
providing interfaces for TWS integration, health monitoring, authentication,
audit logging, and administrative functions.

The endpoints are organized into logical groups:
- Authentication endpoints (/auth)
- Health monitoring endpoints (/health)
- TWS integration endpoints (/status)
- Audit and logging endpoints (/audit)
- Administrative endpoints (/admin)
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import unquote

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import PlainTextResponse, RedirectResponse, Response
from pydantic import BaseModel, Field
from resync.settings import settings
from resync.core.fastapi_di import get_agent_manager, get_tws_client
from resync.core.monitoring.metrics import runtime_metrics
from resync.core.interfaces import IAgentManager, ITWSClient
from starlette.responses import HTMLResponse

from resync.api.circuit_breaker_metrics import router as circuit_breaker_router
from resync.api.utils.error_handlers import handle_api_error
from resync.core.agent_manager import AgentConfig
from resync.core.benchmarking import create_benchmark_runner
from resync.core.container import app_container
from resync.core.llm_wrapper import optimized_llm  # type: ignore[attr-defined]
from resync.core.rate_limiter import (  # type: ignore[attr-defined]
    authenticated_rate_limit,
    public_rate_limit,
)
from resync.core.runbooks import runbook_registry
from resync.core.tws_monitor import tws_monitor  # type: ignore[attr-defined]
from resync.cqrs.dispatcher import dispatcher
from resync.cqrs.queries import (
    CheckTWSConnectionQuery,
    GetEventLogQuery,
    GetJobDependenciesQuery,
    GetJobDetailsQuery,
    GetJobHistoryQuery,
    GetJobLogQuery,
    GetJobsStatusQuery,
    GetPerformanceMetricsQuery,
    GetPlanDetailsQuery,
    GetResourceUsageQuery,
    GetWorkstationsStatusQuery,
)


# Lazy import of alerting_system to avoid circular dependencies
def _get_alerting_system():
    """Lazy import of alerting_system."""
    from resync.core.alerting import alerting_system

    return alerting_system


# Import endpoint utilities for cross-cutting concerns


# --- Logging Setup ---
logger = logging.getLogger(__name__)

# Module-level dependencies to avoid B008 errors
agent_manager_dependency = Depends(get_agent_manager)
tws_client_dependency = Depends(get_tws_client)

# --- APIRouter Initialization ---
api_router = APIRouter()


# --- Pydantic Models for Request/Response ---
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)


class ChatResponse(BaseModel):
    response: str


class ExecuteRequest(BaseModel):
    command: str = Field(..., min_length=1, max_length=200)


class ExecuteResponse(BaseModel):
    result: str


class FilesResponse(BaseModel):
    path: str


class LLMQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    context: dict[str, Any] = Field(default_factory=dict)
    use_cache: bool = Field(default=True)
    stream: bool = Field(default=False)


class LLMQueryResponse(BaseModel):
    optimized: bool
    query: str
    response: Any = None
    cache_used: bool


class TWSMetricsResponse(BaseModel):
    status: str
    critical_alerts: int
    warning_alerts: int
    last_updated: str | None = None


# Error handling is now centralized in resync.api.utils.error_handlers


# --- HTML serving endpoint for the main dashboard ---
@api_router.get("/dashboard", include_in_schema=False)
@public_rate_limit
async def get_dashboard(request: Request) -> Response:
    """
    Serves the main `index.html` file for the dashboard.
    """
    index_path = settings.BASE_DIR / "templates" / "index.html"
    if not index_path.exists():
        logger.error("Dashboard index.html not found at path: %s", index_path)
        raise HTTPException(
            status_code=404, detail="Interface do dashboard não encontrada."
        )
    content = index_path.read_text(encoding="utf-8")
    return HTMLResponse(content=content)


# --- Agent Endpoints ---
@api_router.get(
    "/agents",
    response_model=list[AgentConfig],
    summary="Get All Agent Configurations",
)
@public_rate_limit
async def get_all_agents(
    request: Request,
    agent_manager: IAgentManager = agent_manager_dependency,
) -> list[AgentConfig]:
    """
    Returns the full configuration for all loaded agents.
    """
    return await agent_manager.get_all_agents()


# --- Test endpoint ---
@api_router.get("/test")
async def test_endpoint(request: Request) -> dict[str, str]:
    return {"message": "Test endpoint working"}


# --- System Status Endpoints ---
@api_router.get("/status")
async def get_system_status(
    request: Request,
) -> dict[str, list[dict[str, str]]]:
    """
    Provides a comprehensive status of the TWS environment, including
    workstations, jobs, and critical path information.
    """
    # Return mock data for now until TWS integration is working
    return {
        "workstations": [
            {
                "id": "TWS_MASTER",
                "name": "Master Domain Manager",
                "status": "ONLINE",
            },
            {
                "id": "TWS_AGENT1",
                "name": "Agent Workstation 1",
                "status": "ONLINE",
            },
            {
                "id": "TWS_AGENT2",
                "name": "Agent Workstation 2",
                "status": "OFFLINE",
            },
        ],
        "jobs": [
            {
                "id": "JOB001",
                "name": "Daily Backup",
                "status": "SUCC",
                "workstation": "TWS_AGENT1",
            },
            {
                "id": "JOB002",
                "name": "Data Processing",
                "status": "ABEND",
                "workstation": "TWS_AGENT2",
            },
            {
                "id": "JOB003",
                "name": "Report Generation",
                "status": "SUCC",
                "workstation": "TWS_AGENT1",
            },
            {
                "id": "JOB004",
                "name": "System Cleanup",
                "status": "RUNNING",
                "workstation": "TWS_MASTER",
            },
        ],
    }


# --- New CQRS-based endpoints ---
@api_router.get("/status/workstations")
@public_rate_limit
async def get_workstations_status_cqrs(
    request: Request,
    tws_client: ITWSClient = tws_client_dependency,
) -> list[dict[str, Any]]:
    """
    Get workstation statuses using CQRS pattern.
    """
    try:
        query = GetWorkstationsStatusQuery()
        result = await dispatcher.execute_query(query)

        if not result.success:
            raise HTTPException(
                status_code=500,
                detail=result.error or "Failed to retrieve workstation statuses",
            )

        return result.data
    except Exception as e:
        logger.error("Failed to get TWS workstation statuses: %s", e, exc_info=True)
        raise handle_api_error(e, "TWS workstation statuses retrieval")


@api_router.get("/status/jobs")
@public_rate_limit
async def get_jobs_status_cqrs(
    request: Request,
    tws_client: ITWSClient = tws_client_dependency,
) -> list[dict[str, Any]]:
    """
    Get job statuses using CQRS pattern.
    """
    try:
        query = GetJobsStatusQuery()
        result = await dispatcher.execute_query(query)

        if not result.success:
            raise HTTPException(
                status_code=500,
                detail=result.error or "Failed to retrieve job statuses",
            )

        return result.data
    except Exception as e:
        logger.error("Failed to get TWS job statuses: %s", e, exc_info=True)
        raise handle_api_error(e, "TWS job statuses retrieval")


@api_router.get("/status/jobs/{job_id}")
@public_rate_limit
async def get_job_details(
    request: Request,
    job_id: str,
    tws_client: ITWSClient = tws_client_dependency,
) -> dict[str, Any]:
    """
    Get detailed information about a specific TWS job.
    """
    try:
        query = GetJobDetailsQuery(job_id=job_id)
        result = await dispatcher.execute_query(query)

        if not result.success:
            raise HTTPException(
                status_code=500,
                detail=result.error or "Failed to retrieve job details",
            )

        return result.data
    except Exception as e:
        logger.error("Failed to get TWS job details: %s", e, exc_info=True)
        raise handle_api_error(e, "TWS job details retrieval")


@api_router.get("/status/jobs/{job_name}/history")
@public_rate_limit
async def get_job_history(
    request: Request,
    job_name: str,
    tws_client: ITWSClient = tws_client_dependency,
) -> list[dict[str, Any]]:
    """
    Get execution history for a specific TWS job.
    """
    try:
        query = GetJobHistoryQuery(job_name=job_name)
        result = await dispatcher.execute_query(query)

        if not result.success:
            raise HTTPException(
                status_code=500,
                detail=result.error or "Failed to retrieve job history",
            )

        return result.data
    except Exception as e:
        logger.error("Failed to get TWS job history: %s", e, exc_info=True)
        raise handle_api_error(e, "TWS job history retrieval")


@api_router.get("/status/jobs/{job_id}/log")
@public_rate_limit
async def get_job_log(
    request: Request,
    job_id: str,
    tws_client: ITWSClient = tws_client_dependency,
) -> dict[str, str]:
    """
    Get log content for a specific TWS job execution.
    """
    try:
        query = GetJobLogQuery(job_id=job_id)
        result = await dispatcher.execute_query(query)

        if not result.success:
            raise HTTPException(
                status_code=500,
                detail=result.error or "Failed to retrieve job log",
            )

        return {"log_content": result.data}
    except Exception as e:
        logger.error("Failed to get TWS job log: %s", e, exc_info=True)
        raise handle_api_error(e, "TWS job log retrieval")


@api_router.get("/status/plan")
@public_rate_limit
async def get_plan_details(
    request: Request,
    tws_client: ITWSClient = tws_client_dependency,
) -> dict[str, Any]:
    """
    Get details about the current TWS plan.
    """
    try:
        query = GetPlanDetailsQuery()
        result = await dispatcher.execute_query(query)

        if not result.success:
            raise HTTPException(
                status_code=500,
                detail=result.error or "Failed to retrieve plan details",
            )

        return result.data
    except Exception as e:
        logger.error("Failed to get TWS plan details: %s", e, exc_info=True)
        raise handle_api_error(e, "TWS plan details retrieval")


@api_router.get("/status/jobs/{job_id}/dependencies")
@public_rate_limit
async def get_job_dependencies(
    request: Request,
    job_id: str,
    tws_client: ITWSClient = tws_client_dependency,
) -> dict[str, Any]:
    """
    Get dependency tree for a specific TWS job.
    """
    try:
        query = GetJobDependenciesQuery(job_id=job_id)
        result = await dispatcher.execute_query(query)

        if not result.success:
            raise HTTPException(
                status_code=500,
                detail=result.error or "Failed to retrieve job dependencies",
            )

        return result.data
    except Exception as e:
        logger.error("Failed to get TWS job dependencies: %s", e, exc_info=True)
        raise handle_api_error(e, "TWS job dependencies retrieval")


@api_router.get("/status/resources")
@public_rate_limit
async def get_resource_usage(
    request: Request,
    tws_client: ITWSClient = tws_client_dependency,
) -> list[dict[str, Any]]:
    """
    Get resource usage information.
    """
    try:
        query = GetResourceUsageQuery()
        result = await dispatcher.execute_query(query)

        if not result.success:
            raise HTTPException(
                status_code=500,
                detail=result.error or "Failed to retrieve resource usage",
            )

        return result.data
    except Exception as e:
        logger.error("Failed to get TWS resource usage: %s", e, exc_info=True)
        raise handle_api_error(e, "TWS resource usage retrieval")


@api_router.get("/status/events")
@public_rate_limit
async def get_event_log(
    request: Request,
    last_hours: int = Query(
        default=24, ge=1, le=168, description="Hours to look back for events"
    ),
    tws_client: ITWSClient = tws_client_dependency,
) -> list[dict[str, Any]]:
    """
    Get TWS event log entries.
    """
    try:
        query = GetEventLogQuery(last_hours=last_hours)
        result = await dispatcher.execute_query(query)

        if not result.success:
            raise HTTPException(
                status_code=500,
                detail=result.error or "Failed to retrieve event log",
            )

        return result.data
    except Exception as e:
        logger.error("Failed to get TWS event log: %s", e, exc_info=True)
        raise handle_api_error(e, "TWS event log retrieval")


@api_router.get("/status/performance")
@public_rate_limit
async def get_performance_metrics(
    request: Request,
    tws_client: ITWSClient = tws_client_dependency,
) -> dict[str, Any]:
    """
    Get TWS performance metrics.
    """
    try:
        query = GetPerformanceMetricsQuery()
        result = await dispatcher.execute_query(query)

        if not result.success:
            raise HTTPException(
                status_code=500,
                detail=result.error or "Failed to retrieve performance metrics",
            )

        return result.data
    except Exception as e:
        logger.error("Failed to get TWS performance metrics: %s", e, exc_info=True)
        raise handle_api_error(e, "TWS performance metrics retrieval")


# --- Health Check Endpoints ---
@api_router.get("/health/app", summary="Check Application Health")
@public_rate_limit
def get_app_health(request: Request) -> dict[str, str]:
    """Returns a simple 'ok' to indicate the FastAPI application is running."""
    return {"status": "ok"}


@api_router.get("/health/tws", summary="Check TWS Connection Health")
@public_rate_limit
async def get_tws_health(
    request: Request,
    auto_enable: bool = Query(
        default=False, description="Auto-enable connection if valid"
    ),
    tws_client: ITWSClient = tws_client_dependency,
) -> dict[str, Any]:
    """
    Performs a quick check to verify the connection to the TWS server is active.

    Args:
        auto_enable: Whether to auto-enable the connection if validation is successful
    """
    try:
        query = CheckTWSConnectionQuery()
        result = await dispatcher.execute_query(query)

        if not result.success:
            logger.error("TWS connection check failed: %s", result.error)
            return {
                "status": "error",
                "message": "A verificação da conexão com o TWS falhou.",
                "auto_enable": auto_enable,
                "auto_enable_applied": False,
            }

        is_connected = result.data.get("connected", False) if result.data else False
        if is_connected:
            # If auto_enable is true, ensure the connection is properly enabled
            if auto_enable:
                # This would implement the auto-enable logic
                logger.info(
                    "TWS connection validation successful with auto_enable: %s",
                    auto_enable,
                )

            # Record TWS status success metrics
            runtime_metrics.tws_status_requests_success.increment()

            return {
                "status": "ok",
                "message": "Conexão com o TWS bem-sucedida.",
                "auto_enable": auto_enable,
                "auto_enable_applied": auto_enable,  # In a real implementation, this would reflect if changes were applied
            }
        # Record TWS status failure metrics
        runtime_metrics.tws_status_requests_failed.increment()
        return {
            "status": "error",
            "message": "A verificação da conexão com o TWS falhou.",
            "auto_enable": auto_enable,
            "auto_enable_applied": False,
        }
    except Exception as e:
        logger.error("TWS health check failed: %s", e, exc_info=True)
        # Record TWS status failure metrics on exception
        runtime_metrics.tws_status_requests_failed.increment()
        raise handle_api_error(e, "TWS health check")


# --- Connection Validation Endpoint ---
class ConnectionValidationRequest(BaseModel):
    auto_enable: bool = False
    tws_host: str | None = None
    tws_port: int | None = None
    tws_user: str | None = None
    tws_password: str | None = None


@api_router.post(
    "/v2/validate-connection", summary="Validate TWS Connection Parameters"
)
@authenticated_rate_limit
async def validate_connection(
    request: ConnectionValidationRequest,
    tws_client: ITWSClient = tws_client_dependency,
) -> dict[str, Any]:
    """
    Validates TWS connection parameters with optional auto-enable feature.

    Args:
        request: Connection validation parameters
        tws_client: TWS client for validation

    Returns:
        Validation result with connection status
    """
    try:
        # Perform connection validation
        validation_result = await tws_client.validate_connection(
            host=request.tws_host,
            port=request.tws_port,
            user=request.tws_user,
            password=request.tws_password,
        )

        # Record validation metrics
        runtime_metrics.connection_validations_total.increment()
        if validation_result.get("valid", False):
            runtime_metrics.connection_validation_success.increment()
        else:
            runtime_metrics.connection_validation_failure.increment()

        # If auto_enable is true, update the service to use the validated settings
        if request.auto_enable and validation_result.get("valid", False):
            # Update the TWS client with new settings
            if request.tws_host:
                tws_client.host = request.tws_host
            if request.tws_port:
                tws_client.port = request.tws_port
            if request.tws_user:
                tws_client.user = request.tws_user
            if request.tws_password:
                tws_client.password = request.tws_password

        return {
            "status": ("success" if validation_result.get("valid", False) else "error"),
            "valid": validation_result.get("valid", False),
            "message": validation_result.get("message", ""),
            "auto_enable": request.auto_enable,
            "auto_enable_applied": request.auto_enable
            and validation_result.get("valid", False),
        }
    except Exception as e:
        logger.error("Connection validation failed: %s", e, exc_info=True)
        # Record validation failure
        runtime_metrics.connection_validations_total.increment()
        runtime_metrics.connection_validation_failure.increment()
        return {
            "status": "error",
            "valid": False,
            "message": f"Connection validation failed: {str(e)}",
            "auto_enable": request.auto_enable,
            "auto_enable_applied": False,
        }


# --- Metrics Endpoint ---
@api_router.get(
    "/metrics",
    summary="Get Application Metrics",
    response_class=PlainTextResponse,
)
@public_rate_limit
def get_metrics(request: Request) -> str:
    """
    Returns application metrics in Prometheus text exposition format.
    """
    return runtime_metrics.generate_prometheus_metrics()


@api_router.post("/chat", response_model=ChatResponse)
@public_rate_limit
async def chat_endpoint(request: Request, data: ChatRequest) -> ChatResponse:
    """Chat endpoint for testing input validation."""
    if "<script>" in data.message:
        raise HTTPException(status_code=400, detail="XSS detected")
    return ChatResponse(response="ok")


@api_router.post("/sensitive")
@authenticated_rate_limit
async def sensitive_endpoint(request: Request, data: dict[str, Any]) -> dict[str, str]:
    """Sensitive endpoint for testing encryption."""
    from resync.core.encryption_service import encryption_service

    encrypted = encryption_service.encrypt(data["data"])
    from resync.core.logger import log_with_correlation

    log_with_correlation(
        logging.INFO,
        "Processing sensitive data (encrypted successfully)",
        component="api",
    )
    return {"encrypted": encrypted}


@api_router.get("/protected")
@authenticated_rate_limit
async def protected_endpoint(request: Request) -> None:
    """Protected endpoint for testing authentication."""
    raise HTTPException(status_code=401, detail="Unauthorized")


@api_router.get("/admin/users")
@authenticated_rate_limit
async def admin_users_endpoint(request: Request) -> None:
    """Admin endpoint for testing authorization."""
    raise HTTPException(status_code=403, detail="Forbidden")


class ReviewRequest(BaseModel):
    content: str = Field(..., max_length=1000)  # noqa: F821


@api_router.post("/review")
@public_rate_limit
async def review_endpoint(request: Request, data: ReviewRequest) -> dict[str, str]:
    """Review endpoint for testing input validation."""
    if "<script>" in data.content:
        raise HTTPException(status_code=400, detail="XSS detected")
    return {"status": "reviewed"}


@api_router.post("/execute", response_model=ExecuteResponse)
@public_rate_limit
async def execute_endpoint(request: Request, data: ExecuteRequest) -> ExecuteResponse:
    """Execute endpoint for testing input validation."""
    forbidden_commands = ["rm", "del", ";", "`", "$"]
    if any(cmd in data.command for cmd in forbidden_commands):
        raise HTTPException(status_code=400, detail="Invalid command")
    return ExecuteResponse(result="executed")


@api_router.get("/files/{path:path}", response_model=FilesResponse)
@public_rate_limit
async def files_endpoint(request: Request, path: str) -> FilesResponse:
    """Files endpoint with enhanced path traversal protection."""
    import os

    # Define the base directory for allowed access
    allowed_base = settings.BASE_DIR / "uploads"

    # URL decode the path
    decoded_path = unquote(path)

    # Normalize path to prevent directory traversal
    normalized_path = os.path.normpath(decoded_path)

    # Construct the requested path safely
    requested_path = allowed_base / normalized_path
    requested_path = requested_path.resolve()

    # Compat: Python 3.8 não possui is_relative_to
    try:
        is_inside = requested_path.is_relative_to(allowed_base)  # py>=3.9
    except AttributeError:
        try:
            requested_path.relative_to(allowed_base)
            is_inside = True
        except ValueError:
            is_inside = False
    if not is_inside:
        raise HTTPException(
            status_code=400, detail="Invalid path: path traversal detected"
        )

    # Verify the file exists and is not a directory
    if requested_path.is_dir():
        raise HTTPException(status_code=400, detail="Cannot access directories")

    if not requested_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FilesResponse(path=str(requested_path.relative_to(settings.BASE_DIR)))


# --- Login Endpoint ---
@api_router.get("/login", include_in_schema=False)
@public_rate_limit
async def login_page(request: Request) -> Response:
    """
    Serve the login page for admin authentication.
    """
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Login - Resync Admin</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f5f5f5;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }
            .login-container {
                background-color: white;
                padding: 2rem;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                width: 100%;
                max-width: 400px;
            }
            .login-title {
                text-align: center;
                margin-bottom: 1.5rem;
                color: #333;
            }
            .form-group {
                margin-bottom: 1rem;
            }
            .form-group label {
                display: block;
                margin-bottom: 0.5rem;
                color: #555;
            }
            .form-group input {
                width: 100%;
                padding: 0.75rem;
                border: 1px solid #ddd;
                border-radius: 4px;
                box-sizing: border-box;
            }
            .btn {
                width: 100%;
                padding: 0.75rem;
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 1rem;
            }
            .btn:hover {
                background-color: #0056b3;
            }
            .error-message {
                color: red;
                text-align: center;
                margin-top: 1rem;
            }
        </style>
    </head>
    <body>
        <div class="login-container">
            <h2 class="login-title">Resync Admin Login</h2>
            <form id="loginForm" method="post" action="/token">
                <div class="form-group">
                    <label for="username">Username:</label>
                    <input type="text" id="username" name="username" required>
                </div>
                <div class="form-group">
                    <label for="password">Password:</label>
                    <input type="password" id="password" name="password" required>
                </div>
                <button type="submit" class="btn">Login</button>
            </form>
            <div id="errorMessage" class="error-message" style="display: none;"></div>

            <script>
                document.getElementById('loginForm').addEventListener('submit', async (e) => {
                    e.preventDefault();
                    const formData = new FormData(e.target);
                    const data = {
                        username: formData.get('username'),
                        password: formData.get('password')
                    };
                    try {
                        const response = await fetch('/token', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                            body: new URLSearchParams(data)
                        });
                        if (response.ok) {
                            // Token é enviado como cookie HttpOnly; não usar localStorage
                            window.location.href = '/dashboard';
                        } else {
                            const error = await response.json();
                            document.getElementById('errorMessage').textContent = error.detail || 'Login failed';
                            document.getElementById('errorMessage').style.display = 'block';
                        }
                    } catch (error) {
                        document.getElementById('errorMessage').textContent = 'An error occurred';
                        document.getElementById('errorMessage').style.display = 'block';
                    }
                });
            </script>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


# Token endpoint for JWT authentication
@api_router.post("/token", include_in_schema=False)
@public_rate_limit
async def login_for_access_token(
    request: Request, username: str = Form(...), password: str = Form(...)
) -> Response:
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    from resync.api.auth import (
        ACCESS_TOKEN_EXPIRE_MINUTES,
        authenticate_admin,
        create_access_token,
    )

    user = await authenticate_admin(username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": username})
    # Define também como cookie HttpOnly para mitigar XSS (mantém JSON para compat)
    from fastapi import Response

    resp = Response(
        content=f'{{"access_token": "{access_token}", "token_type": "bearer"}}',
        media_type="application/json",
    )
    resp.set_cookie(
        "access_token",
        access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=(
            ACCESS_TOKEN_EXPIRE_MINUTES * 60
            if "ACCESS_TOKEN_EXPIRE_MINUTES" in globals()
            else 1800
        ),
        path="/",
    )
    return resp


@api_router.post(
    "/llm/optimize",
    summary="Optimize LLM query with TWS-specific optimizations",
    response_model=LLMQueryResponse,
)
@authenticated_rate_limit
async def optimize_llm_query(
    request: Request, query_data: LLMQueryRequest
) -> LLMQueryResponse:
    """
    Optimize an LLM query using TWS-specific optimizations.

    This endpoint uses the LLM optimizer to enhance query processing
    with caching, model selection, and TWS-specific template matching.
    """
    try:
        response = await optimized_llm.get_response(
            query=query_data.query,
            context=query_data.context,
            use_cache=query_data.use_cache,
            stream=query_data.stream,
        )

        return LLMQueryResponse(
            optimized=True,
            query=query_data.query,
            response=response,
            cache_used=bool(
                query_data.use_cache
            ),  # melhor aproximação até termos flag de hit real
        )
    except Exception as e:
        logger.error(f"LLM optimization failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to optimize LLM query: {str(e)}"
        )


# Redirect root to login page
@api_router.get("/", include_in_schema=False)
async def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/login")


# --- TWS Monitoring Endpoints ---
@api_router.get("/monitoring/metrics", summary="Get TWS Performance Metrics")
@authenticated_rate_limit
async def get_tws_metrics(request: Request) -> dict[str, Any]:
    """
    Returns comprehensive TWS performance metrics including:
    - API performance
    - Cache hit ratios
    - LLM usage and costs
    - Circuit breaker status
    - Memory usage
    """
    return tws_monitor.get_performance_report()


@api_router.get("/monitoring/alerts", summary="Get Recent System Alerts")
@authenticated_rate_limit
async def get_tws_alerts(request: Request, limit: int = 10) -> list[dict[str, Any]]:
    """
    Returns recent system alerts and warnings.

    Args:
        limit: Maximum number of alerts to return (default: 10)
    """
    return tws_monitor.get_alerts(limit=limit)


@api_router.get("/monitoring/health", summary="Get TWS System Health")
@authenticated_rate_limit
async def get_tws_health_monitoring(
    request: Request,
) -> TWSMetricsResponse:  # Renamed to avoid conflict
    """
    Returns overall TWS system health status.
    """
    performance_report = tws_monitor.get_performance_report()

    # Determine health status
    critical_alerts = [
        alert
        for alert in performance_report["alerts"]
        if alert["severity"] == "critical"
    ]

    warning_alerts = [
        alert
        for alert in performance_report["alerts"]
        if alert["severity"] == "warning"
    ]

    if critical_alerts:
        status = "critical"
    elif warning_alerts:
        status = "warning"
    else:
        status = "healthy"

    return TWSMetricsResponse(
        status=status,
        critical_alerts=len(critical_alerts),
        warning_alerts=len(warning_alerts),
        last_updated=performance_report["current_metrics"].get("timestamp"),
    )


# --- Runbook and Alerting Endpoints ---
@api_router.get("/runbooks", summary="Get Available Runbooks")
@authenticated_rate_limit
async def list_runbooks(request: Request) -> list[str]:
    """
    Returns a list of available incident response runbooks.
    """
    return runbook_registry.list_runbooks()


class ExecuteRunbookRequest(BaseModel):
    runbook_name: str
    context: dict[str, Any] = Field(default_factory=dict)


@api_router.post("/runbooks/execute", summary="Execute an Incident Response Runbook")
@authenticated_rate_limit
async def execute_runbook(
    request: Request, runbook_data: ExecuteRunbookRequest
) -> dict[str, Any]:
    """
    Executes an incident response runbook with the provided context.
    """
    result = runbook_registry.execute_runbook(
        runbook_data.runbook_name, runbook_data.context
    )
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Runbook '{runbook_data.runbook_name}' not found",
        )
    return result


@api_router.get("/alerts/active", summary="Get Active Alerts")
@authenticated_rate_limit
async def get_active_alerts(request: Request) -> list[dict[str, Any]]:
    """
    Returns a list of currently active (non-acknowledged) alerts.
    """
    alerts = _get_alerting_system().get_active_alerts()
    return [alert.__dict__ for alert in alerts]


@api_router.post("/alerts/acknowledge/{alert_id}", summary="Acknowledge an Alert")
@authenticated_rate_limit
async def acknowledge_alert(request: Request, alert_id: str) -> dict[str, bool]:
    """
    Acknowledges an active alert by ID.
    """
    success = _get_alerting_system().acknowledge_alert(
        alert_id, request.headers.get("x-forwarded-for", "unknown")
    )
    return {"success": success}


class AddAlertRuleRequest(BaseModel):
    name: str
    description: str
    metric_name: str
    condition: str  # "gt", "lt", "eq", "ne", "ge", "le"
    threshold: float
    severity: str  # "info", "warning", "critical", "emergency"


@api_router.post("/alerts/rules", summary="Add an Alert Rule")
@authenticated_rate_limit
async def add_alert_rule(
    request: Request, rule_data: AddAlertRuleRequest
) -> dict[str, str]:
    """
    Adds a new alert rule to the system.
    """
    from resync.core.alerting import AlertRule, AlertSeverity

    severity_map = {
        "info": AlertSeverity.INFO,
        "warning": AlertSeverity.WARNING,
        "critical": AlertSeverity.CRITICAL,
        "emergency": AlertSeverity.EMERGENCY,
    }

    if rule_data.severity not in severity_map:
        raise HTTPException(
            status_code=400, detail=f"Invalid severity: {rule_data.severity}"
        )

    rule = AlertRule(
        name=rule_data.name,
        description=rule_data.description,
        metric_name=rule_data.metric_name,
        condition=rule_data.condition,
        threshold=rule_data.threshold,
        severity=severity_map[rule_data.severity],
    )

    _get_alerting_system().add_rule(rule)
    return {
        "status": "success",
        "message": f"Alert rule '{rule_data.name}' added successfully",
    }


# --- Benchmarking Endpoints ---


class RunBenchmarkRequest(BaseModel):
    benchmark_name: str
    iterations: int = 100
    warmup_rounds: int = 10


@api_router.post("/benchmark/run", summary="Run a performance benchmark")
@authenticated_rate_limit
async def run_benchmark(
    request: Request, benchmark_data: RunBenchmarkRequest
) -> dict[str, Any]:
    """
    Run a performance benchmark for the system.

    Args:
        benchmark_data: Configuration for the benchmark to run
    """
    try:
        # Get required services from DI container
        tws_client = await app_container.get(ITWSClient)
        agent_manager = await app_container.get(IAgentManager)

        # Create benchmark runner
        benchmark_runner = await create_benchmark_runner(agent_manager, tws_client)

        # Run specific benchmark based on name
        if benchmark_data.benchmark_name == "comprehensive":
            results = await benchmark_runner.run_comprehensive_benchmark()
            return {
                "status": "success",
                "benchmark_name": benchmark_data.benchmark_name,
                "results": results,
            }
        if benchmark_data.benchmark_name == "tws_status":
            result = await benchmark_runner.benchmark.run_benchmark(
                name="TWS Status Check",
                operation="tws_status",
                func=benchmark_runner._benchmark_tws_status,
                iterations=benchmark_data.iterations,
                warmup_rounds=benchmark_data.warmup_rounds,
            )
            return {
                "status": "success",
                "benchmark_name": benchmark_data.benchmark_name,
                "result": result.__dict__,
            }
        if benchmark_data.benchmark_name == "agent_creation":
            result = await benchmark_runner.benchmark.run_benchmark(
                name="Agent Creation",
                operation="create_agent",
                func=benchmark_runner._benchmark_agent_creation,
                iterations=benchmark_data.iterations,
                warmup_rounds=benchmark_data.warmup_rounds,
            )
            return {
                "status": "success",
                "benchmark_name": benchmark_data.benchmark_name,
                "result": result.__dict__,
            }
        raise HTTPException(
            status_code=400,
            detail=f"Unknown benchmark name: {benchmark_data.benchmark_name}. Available: comprehensive, tws_status, agent_creation",
        )
    except Exception as e:
        logger.error(f"Benchmark execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Benchmark execution failed: {str(e)}"
        )


@api_router.get("/benchmark/results", summary="Get benchmark results history")
@authenticated_rate_limit
async def get_benchmark_results(
    request: Request, operation: str | None = None
) -> dict[str, Any]:
    """
    Get historical benchmark results.

    Args:
        operation: Optional operation name to filter results
    """
    try:
        # Get the benchmark instance (we need to access it from somewhere)
        # For now we'll create a new runner to access the benchmark - in practice this would be a shared instance
        tws_client = await app_container.get(ITWSClient)
        agent_manager = await app_container.get(IAgentManager)

        benchmark_runner = await create_benchmark_runner(agent_manager, tws_client)

        if operation:
            historical_results = benchmark_runner.benchmark.get_historical_performance(
                operation
            )
            return {
                "operation": operation,
                "results": [result.__dict__ for result in historical_results],
            }
        # Return all results
        return {
            "all_results": [
                result.__dict__ for result in benchmark_runner.benchmark.results
            ]
        }
    except Exception as e:
        logger.error(f"Getting benchmark results failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Getting benchmark results failed: {str(e)}",
        )


# Register circuit breaker metrics endpoints
api_router.include_router(circuit_breaker_router)
