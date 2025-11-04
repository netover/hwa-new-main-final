"""Endpoints exposing data from the TWS integration layer."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi import FastAPI

router = APIRouter(prefix="/api/v1/tws", tags=["tws"])

try:
    from resync.services.tws_service import OptimizedTWSClient  # type: ignore
    from resync.config.settings import settings as app_settings  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    OptimizedTWSClient = None  # type: ignore
    app_settings = None  # type: ignore


async def get_tws_client(app: FastAPI) -> object | None:
    """Initialise (or reuse) the shared TWS client."""
    if OptimizedTWSClient is None:
        return None
    cached = getattr(app.state, "_tws_client", None)
    if cached:
        return cached
    if app_settings is None:
        cfg = getattr(app.state, "_tws_config", {})
        if cfg.get("mock_mode", True):
            return None
        host = cfg.get("host")
        port = cfg.get("port")
        user = cfg.get("user")
        password = cfg.get("password")
        if not all([host, port, user, password]):
            return None
        client = OptimizedTWSClient(
            hostname=host,
            port=port,
            username=user,
            password=password,
            engine_name="tws-engine",
            engine_owner="tws-owner",
        )
        app.state._tws_client = client  # type: ignore[attr-defined]
        return client
    if getattr(app_settings, "tws_mock_mode", True):
        return None
    host = getattr(app_settings, "tws_host", None)
    port = getattr(app_settings, "tws_port", None)
    user = getattr(app_settings, "tws_user", None)
    password_obj = getattr(app_settings, "tws_password", None)
    password = password_obj.get_secret_value() if password_obj else None  # type: ignore[union-attr]
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
    app.state._tws_client = client  # type: ignore[attr-defined]
    return client


@router.get("/workstations")
async def list_workstations(request: Request) -> list[dict]:
    client = await get_tws_client(request.app)
    if client is None:
        return []
    try:
        workstations = await client.get_workstations_status()
        return [ws.dict() for ws in workstations]
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/jobs")
async def list_jobs(request: Request) -> list[dict]:
    client = await get_tws_client(request.app)
    if client is None:
        return []
    try:
        jobs = await client.get_jobs_status()
        return [job.dict() for job in jobs]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/system_status")
async def get_system_status(request: Request) -> dict:
    client = await get_tws_client(request.app)
    if client is None:
        return {
            "tws_connected": False,
            "workstations": [],
            "jobs": [],
            "critical_jobs": [],
        }
    try:
        status = await client.get_system_status()
        return status.dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/details")
async def job_details(job_id: str, request: Request) -> dict:
    client = await get_tws_client(request.app)
    if client is None:
        return {}
    try:
        details = await client.get_job_details(job_id)
        return details.dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/log")
async def job_log(job_id: str, request: Request) -> str:
    client = await get_tws_client(request.app)
    if client is None:
        return ""
    try:
        return await client.get_job_log(job_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/replay")
async def replay_job(job_id: str) -> dict[str, object]:
    return {
        "job_id": job_id,
        "dry_run": True,
        "diff": "No changes - mock implementation",
    }


@router.get("/jobs/{job_id}/dependencies")
async def job_dependencies(job_id: str, request: Request, depth: int = 1) -> dict:
    client = await get_tws_client(request.app)
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
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/graph/criticalpath")
async def critical_path(request: Request) -> list[dict]:
    client = await get_tws_client(request.app)
    if client is None:
        return []
    try:
        critical_jobs = await client.get_critical_path_status()
        return [cj.dict() for cj in critical_jobs]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
