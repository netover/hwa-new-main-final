"""Administrative endpoints for managing TWS connectivity and reports."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import FastAPI
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from httpx import AsyncClient
from pydantic import SecretStr

from resync.api.dependencies import get_http_client

from .reports import (
    compute_operations_report,
    compute_performance_report,
    compute_reliability_report,
    compute_sla_report,
)
from .tws import app_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
security = HTTPBasic()


async def require_admin(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "admin")
    provided_password = credentials.password or ""
    if credentials.username != username or provided_password != password:
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    return credentials.username


async def verify_csrf(request: Request) -> None:
    token = os.getenv("CSRF_TOKEN")
    if not token:
        return
    if request.headers.get("X-CSRF-Token") != token:
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")


@router.get("/tws-connection", dependencies=[Depends(require_admin), Depends(verify_csrf)])
async def get_tws_connection_config(request: Request) -> dict[str, Any]:
    try:
        if app_settings is None:
            cfg = getattr(request.app.state, "_tws_config", {})
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
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/tws-connection", dependencies=[Depends(require_admin), Depends(verify_csrf)])
async def update_tws_connection_config(config: dict[str, Any], request: Request) -> dict[str, str]:
    host = config.get("host")
    port = config.get("port")
    user = config.get("user")
    password = config.get("password")
    verify_tls = config.get("verify_tls", False)
    if not host or not user or not password or not port:
        raise HTTPException(status_code=400, detail="Missing required connection parameters")
    try:
        if app_settings is None:
            cfg = getattr(request.app.state, "_tws_config", {})
            cfg.update(
                {
                    "host": host,
                    "port": int(port),
                    "user": user,
                    "password": password,
                    "verify_tls": verify_tls,
                    "mock_mode": False,
                }
            )
        else:
            if hasattr(app_settings, "tws_mock_mode"):
                setattr(app_settings, "tws_mock_mode", False)
            setattr(app_settings, "tws_host", host)
            setattr(app_settings, "tws_port", int(port))
            setattr(app_settings, "tws_user", user)
            setattr(app_settings, "tws_password", SecretStr(password))
            setattr(app_settings, "tws_verify", verify_tls)
        if hasattr(request.app.state, "_tws_client"):
            request.app.state._tws_client = None  # type: ignore[attr-defined]
        return {"message": "TWS connection parameters updated successfully"}
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/tws-connection/test", dependencies=[Depends(require_admin), Depends(verify_csrf)])
async def test_tws_connection_parameters(
    config: dict[str, Any],
    http_client: AsyncClient = Depends(get_http_client),
) -> dict[str, Any]:
    host = config.get("host")
    port = config.get("port")
    user = config.get("user")
    password = config.get("password")
    verify_tls = config.get("verify_tls", False)
    if not host or not user or not password or not port:
        raise HTTPException(status_code=400, detail="Missing required connection parameters")
    base_url = f"http://{host}:{port}/twsd"
    try:
        timeout = httpx.Timeout(5.0, read=5.0, write=5.0, connect=5.0, pool=5.0)
        if verify_tls:
            response = await http_client.head(base_url, auth=(user, password), timeout=timeout)
        else:
            async with httpx.AsyncClient(verify=False, timeout=timeout) as insecure_client:
                response = await insecure_client.head(base_url, auth=(user, password))
        response.raise_for_status()
        return {"valid": True, "message": f"Successfully validated connection to {host}:{port}"}
    except httpx.TimeoutException as exc:  # pragma: no cover - defensive
        return {"valid": False, "message": f"TWS connection validation timed out: {exc}"}
    except Exception as exc:  # pragma: no cover - defensive
        return {"valid": False, "message": f"TWS connection validation failed: {exc}"}


async def _compute_reports_summary(app) -> str:
    try:
        ops, rel, sla, perf = await asyncio.gather(
            compute_operations_report(app),
            compute_reliability_report(app),
            compute_sla_report(app),
            compute_performance_report(app),
        )
    except Exception:
        ops = rel = sla = perf = {}
    lines: list[str] = ["**Resumo de Relatórios Resync**"]
    if ops:
        lines.append(
            "Total de jobs: {total} (Executados: {exec}, Pendentes: {pending}, Falhos: {fail})".format(
                total=ops.get("total_jobs", 0),
                exec=ops.get("executed", 0),
                pending=ops.get("pending", 0),
                fail=ops.get("failed", 0),
            )
        )
        top_failed = ops.get("top_failed_flows", [])
        if top_failed:
            flows_summary = ", ".join(f"{flow['job_stream']} ({flow['failures']})" for flow in top_failed)
            lines.append(f"Top fluxos com falhas: {flows_summary}")
    if rel:
        lines.append(
            "MTTA (min): {mtta:.1f}, MTTR (min): {mttr:.1f}".format(
                mtta=rel.get("mtta_minutes", 0.0),
                mttr=rel.get("mttr_minutes", 0.0),
            )
        )
        flaky = rel.get("flaky_jobs", [])
        if flaky:
            flaky_summary = ", ".join(f"{item['job']} ({item['failure_rate']*100:.1f}% falhas)" for item in flaky)
            lines.append(f"Jobs instáveis: {flaky_summary}")
    if sla:
        lines.append(
            "SLAs definidos: {defined}, atendidos: {met}".format(
                defined=sla.get("slas_defined", 0),
                met=sla.get("slas_met", 0),
            )
        )
        lines.append(
            "Drift médio (min): {mean:.1f}, p95 (min): {p95:.1f}".format(
                mean=sla.get("drift_mean_minutes", 0.0),
                p95=sla.get("drift_p95_minutes", 0.0),
            )
        )
    if perf:
        lines.append(
            "Latência média API (ms): {lat:.2f}, erros API: {errors}".format(
                lat=perf.get("api_avg_latency_ms", 0.0),
                errors=perf.get("api_error_count", 0),
            )
        )
    return "\n".join(lines)


async def _send_report_to_teams(summary: str, client: Optional[AsyncClient] = None) -> None:
    webhook = os.getenv("TEAMS_WEBHOOK_URL")
    if not webhook:
        return
    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "summary": "Relatorio Resync",
        "text": summary,
    }
    if client is None:
        async with httpx.AsyncClient(timeout=10.0) as transient_client:
            response = await transient_client.post(webhook, json=payload)
            response.raise_for_status()
    else:
        response = await client.post(webhook, json=payload, timeout=10.0)
        response.raise_for_status()


async def _schedule_reports(app: FastAPI) -> None:
    interval_minutes = int(os.getenv("REPORT_INTERVAL_MINUTES", "1440"))
    delay_seconds = max(interval_minutes, 1) * 60
    try:
        while True:
            try:
                summary = await _compute_reports_summary(app)
                if os.getenv("TEAMS_WEBHOOK_URL"):
                    shared_client: Optional[AsyncClient] = getattr(app.state, "http", None)
                    await _send_report_to_teams(summary, shared_client)
                else:
                    logger.info("Scheduled report summary:\n%s", summary)
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Failed to generate or send scheduled report: %s", exc)
            try:
                await asyncio.sleep(delay_seconds)
            except asyncio.CancelledError:
                logger.info("Scheduled report task cancelled.")
                raise
    finally:
        logger.info("Scheduled report task exiting.")


@router.post("/run-report", dependencies=[Depends(require_admin), Depends(verify_csrf)])
async def run_report_now(
    request: Request,
    http_client: AsyncClient = Depends(get_http_client),
) -> dict[str, Any]:
    summary = await _compute_reports_summary(request.app)
    if os.getenv("TEAMS_WEBHOOK_URL"):
        await _send_report_to_teams(summary, http_client)
        return {"message": "Report enviado via Teams"}
    return {"message": "Report gerado", "summary": summary}


_setup_flag = "_admin_routes_setup"


def setup(app: FastAPI) -> None:
    if getattr(app.state, _setup_flag, False):
        return
    setattr(app.state, _setup_flag, True)
    if os.getenv("TEAMS_WEBHOOK_URL"):
        try:
            app.state.register_background_task(_schedule_reports(app), name="scheduled-reports")  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to start scheduled report task: %s", exc)
