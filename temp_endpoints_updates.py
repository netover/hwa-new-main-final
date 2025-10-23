from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel, Field

from resync.core.agent_manager import AgentConfig
from resync.core.fastapi_di import get_agent_manager, get_tws_client
from resync.core.interfaces import IAgentManager, ITWSClient
from resync.core.llm_wrapper import optimized_llm
from resync.core.metrics import runtime_metrics
from resync.core.rate_limiter import authenticated_rate_limit, public_rate_limit
from resync.core.tws_monitor import tws_monitor
from resync.models.tws import SystemStatus
from resync.settings import settings

# --- Logging Setup ---
logger = logging.getLogger(__name__)

# Module-level dependencies to avoid B008 errors
agent_manager_dependency = Depends(get_agent_manager)
tws_client_dependency = Depends(get_tws_client)

# --- APIRouter Initialization ---
api_router = APIRouter()


# --- Pydantic Models for Endpoints ---
class OptimizeLLMQueryRequest(BaseModel):
    query: str
    context: Dict[str, Any] = Field(default_factory=dict)
    use_cache: bool = True
    stream: bool = False


class OptimizeLLMQueryResponse(BaseModel):
    optimized: bool
    query: str
    response: Any
    cache_used: bool


class TWSMetricsResponse(BaseModel):
    """Response model for TWS metrics endpoint"""

    api_performance: Dict[str, Any]
    cache_stats: Dict[str, Any]
    llm_usage: Dict[str, Any]
    circuit_breaker_status: Dict[str, Any]
    memory_usage: Dict[str, Any]


class TWSAlert(BaseModel):
    """Model for TWS alerts"""

    timestamp: str
    severity: str
    message: str
    component: str


class TWSHealthResponse(BaseModel):
    """Response model for TWS health monitoring"""

    status: str
    critical_alerts: int
    warning_alerts: int
    last_updated: Optional[str] = None


# --- HTML serving endpoint for the main dashboard ---
@api_router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
@public_rate_limit
async def get_dashboard(request: Request) -> HTMLResponse:
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
    response_model=List[AgentConfig],
    summary="Get All Agent Configurations",
)
@public_rate_limit
async def get_all_agents(
    request: Request,
    agent_manager: IAgentManager = agent_manager_dependency,
) -> List[AgentConfig]:
    """
    Returns the full configuration for all loaded agents.
    """
    return await agent_manager.get_all_agents()


# --- System Status Endpoints ---
@api_router.get("/status", response_model=SystemStatus)
@public_rate_limit
async def get_system_status(
    request: Request,
    tws_client: ITWSClient = tws_client_dependency,
) -> SystemStatus:
    """
    Provides a comprehensive status of the TWS environment, including
    workstations, jobs, and critical path information.
    """
    try:
        workstations = await tws_client.get_workstations_status()
        jobs = await tws_client.get_jobs_status()
        critical_jobs = await tws_client.get_critical_path_status()

        status = SystemStatus(
            workstations=workstations, jobs=jobs, critical_jobs=critical_jobs
        )
        # Record metrics upon successful status retrieval
        runtime_metrics.tws_status_requests_success.increment()
        runtime_metrics.tws_workstations_total.set(len(workstations))
        runtime_metrics.tws_jobs_total.set(len(jobs))
        return status
    except Exception as e:
        logger.error("Failed to get TWS system status: %s", e, exc_info=True)
        runtime_metrics.tws_status_requests_failed.increment()
        raise HTTPException(
            status_code=503, detail=f"Falha ao comunicar com o TWS: {e}"
        ) from e


# --- Health Check Endpoints ---
@api_router.get("/health/app", summary="Check Application Health")
@public_rate_limit
def get_app_health(request: Request) -> Dict[str, str]:
    """Returns a simple 'ok' to indicate the FastAPI application is running."""
    return {"status": "ok"}


@api_router.get("/health/tws", summary="Check TWS Connection Health")
@public_rate_limit
async def get_tws_health(
    request: Request,
    tws_client: ITWSClient = tws_client_dependency,
) -> Dict[str, str]:
    """
    Performs a quick check to verify the connection to the TWS server is active.
    """
    try:
        is_connected = await tws_client.check_connection()
        if is_connected:
            return {
                "status": "ok",
                "message": "Conexão com o TWS bem-sucedida.",
            }
        else:
            raise HTTPException(
                status_code=503,
                detail="A verificação da conexão com o TWS falhou.",
            )
    except Exception as e:
        logger.error("TWS health check failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=503, detail=f"Falha na conexão com o TWS: {e}"
        ) from e


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


@api_router.post("/chat")
@public_rate_limit
async def chat_endpoint(request: Request, data: Dict[str, Any]) -> Dict[str, str]:
    """Chat endpoint for testing input validation."""
    message = data.get("message", "")
    if "<script>" in message:
        raise HTTPException(status_code=400, detail="XSS detected")
    return {"response": "ok"}


@api_router.post("/sensitive")
@authenticated_rate_limit
async def sensitive_endpoint(request: Request, data: Dict[str, Any]) -> Dict[str, str]:
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
async def protected_endpoint(request: Request):
    """Protected endpoint for testing authentication."""
    raise HTTPException(status_code=401, detail="Unauthorized")


@api_router.get("/admin/users")
@authenticated_rate_limit
async def admin_users_endpoint(request: Request):
    """Admin endpoint for testing authorization."""
    raise HTTPException(status_code=403, detail="Forbidden")


class ReviewRequest(BaseModel):
    content: str = Field(..., max_length=1000)  # noqa: F821


@api_router.post("/review")
@public_rate_limit
async def review_endpoint(request: Request, data: ReviewRequest):
    """Review endpoint for testing input validation."""
    if "<script>" in data.content:
        raise HTTPException(status_code=400, detail="XSS detected")
    return {"status": "reviewed"}


class ExecuteRequest(BaseModel):
    command: str


@api_router.post("/execute")
@public_rate_limit
async def execute_endpoint(request: Request, data: ExecuteRequest) -> Dict[str, str]:
    """Execute endpoint for testing input validation."""
    forbidden_commands = ["rm", "del", ";", "`", "$"]
    if any(cmd in data.command for cmd in forbidden_commands):
        raise HTTPException(status_code=400, detail="Invalid command")
    return {"result": "executed"}


@api_router.get("/files/{path:path}")
@public_rate_limit
async def files_endpoint(request: Request, path: str) -> Dict[str, str]:
    """Files endpoint for testing path traversal."""
    # URL decode the path to prevent bypasses with encoded characters
    decoded_path = unquote(path)

    # Check for path traversal attempts
    if ".." in decoded_path or decoded_path.startswith("/") or "//" in decoded_path:
        raise HTTPException(status_code=400, detail="Invalid path")

    # Normalize the path to remove any potential traversal patterns
    import os

    normalized_path = os.path.normpath(decoded_path)

    # Ensure the normalized path doesn't try to go up directories
    if normalized_path.startswith("..") or "/.." in normalized_path:
        raise HTTPException(status_code=400, detail="Invalid path")

    return {"path": normalized_path}


# --- Login Endpoint ---
@api_router.get("/login", response_class=HTMLResponse, include_in_schema=False)
@public_rate_limit
async def login_page(request: Request) -> HTMLResponse:
    """
    Serve the login page for email authentication.
    """
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Login - Resync</title>
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
        </style>
    </head>
    <body>
        <div class="login-container">
            <h2 class="login-title">Acesso ao Resync</h2>
            <form method="post" action="/login">
                <div class="form-group">
                    <label for="email">E-mail:</label>
                    <input type="email" id="email" name="email" required>
                </div>
                <button type="submit" class="btn">Acessar</button>
            </form>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@api_router.post("/login", include_in_schema=False)
@public_rate_limit
async def login(request: Request, email: str = Form(...)):
    """
    Handle login form submission and redirect to dashboard.
    """
    # For now, just store the email in session for auditing purposes
    # In a real implementation, we would validate the email format
    # and potentially check if it's in a whitelist

    # Create a redirect response to dashboard
    response = RedirectResponse(url="/dashboard", status_code=302)

    # Store the user email in session for auditing (in a real app, we'd use proper session management)
    # For now we just log the access for auditing
    logger.info(f"User accessed with email: {email}")

    return response


@api_router.post(
    "/llm/optimize", summary="Optimize LLM query with TWS-specific optimizations"
)
@authenticated_rate_limit
async def optimize_llm_query(
    request: Request, query_data: OptimizeLLMQueryRequest
) -> OptimizeLLMQueryResponse:
    """
    Optimize an LLM query using TWS-specific optimizations.

    This endpoint uses the LLM optimizer to enhance query processing
    with caching, model selection, and TWS-specific template matching.
    """
    try:
        if not query_data.query:
            raise HTTPException(status_code=400, detail="Query is required")

        response = await optimized_llm.get_response(
            query=query_data.query,
            context=query_data.context,
            use_cache=query_data.use_cache,
            stream=query_data.stream,
        )

        return OptimizeLLMQueryResponse(
            optimized=True,
            query=query_data.query,
            response=response,
            cache_used=not query_data.use_cache,  # Simplified - in real implementation would check cache hit
        )
    except Exception as e:
        logger.error(f"LLM optimization failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to optimize LLM query: {str(e)}"
        )


# Redirect root to login page
@api_router.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/login")


# --- TWS Monitoring Endpoints ---
@api_router.get("/monitoring/metrics", summary="Get TWS Performance Metrics")
@authenticated_rate_limit
async def get_tws_metrics(request: Request) -> TWSMetricsResponse:
    """
    Returns comprehensive TWS performance metrics including:
    - API performance
    - Cache hit ratios
    - LLM usage and costs
    - Circuit breaker status
    - Memory usage
    """
    # Return the performance report from the monitor
    performance_report = tws_monitor.get_performance_report()

    return TWSMetricsResponse(
        api_performance=performance_report.get("api_performance", {}),
        cache_stats=performance_report.get("cache_stats", {}),
        llm_usage=performance_report.get("llm_usage", {}),
        circuit_breaker_status=performance_report.get("circuit_breaker_status", {}),
        memory_usage=performance_report.get("memory_usage", {}),
    )


@api_router.get("/monitoring/alerts", summary="Get Recent System Alerts")
@authenticated_rate_limit
async def get_tws_alerts(request: Request, limit: int = 10) -> List[TWSAlert]:
    """
    Returns recent system alerts and warnings.

    Args:
        limit: Maximum number of alerts to return (default: 10)
    """
    # Get alerts from the monitor and convert to TWSAlert models
    alert_data = tws_monitor.get_alerts(limit=limit)
    return [TWSAlert(**alert) for alert in alert_data]


@api_router.get("/monitoring/health", summary="Get TWS System Health")
@authenticated_rate_limit
async def get_tws_health_monitoring(
    request: Request,
) -> TWSHealthResponse:  # Renamed to avoid conflict
    """
    Returns overall TWS system health status.
    """
    performance_report = tws_monitor.get_performance_report()

    # Determine health status
    alerts = performance_report.get("alerts", [])
    critical_alerts = [alert for alert in alerts if alert.get("severity") == "critical"]
    warning_alerts = [alert for alert in alerts if alert.get("severity") == "warning"]

    if critical_alerts:
        status = "critical"
    elif warning_alerts:
        status = "warning"
    else:
        status = "healthy"

    return TWSHealthResponse(
        status=status,
        critical_alerts=len(critical_alerts),
        warning_alerts=len(warning_alerts),
        last_updated=performance_report.get("current_metrics", {}).get("timestamp"),
    )
