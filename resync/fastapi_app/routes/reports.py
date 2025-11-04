"""Reporting endpoints derived from TWS data and in-memory metrics."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from .tws import get_tws_client

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/operations")
async def operations_report(request: Request, from_date: str | None = None, to_date: str | None = None) -> dict[str, Any]:
    client = await get_tws_client(request.app)
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
        for job in jobs:
            if job.status == "ABEND":
                flow_failures[job.job_stream] += 1
        top_failed = [
            {"job_stream": stream, "failures": count}
            for stream, count in flow_failures.most_common(10)
        ]
        backlog: dict[str, int] = {}
        for job in jobs:
            if job.status not in {"SUCC", "ABEND"}:
                backlog[job.workstation] = backlog.get(job.workstation, 0) + 1
        return {
            "total_jobs": len(jobs),
            "executed": executed,
            "pending": pending,
            "failed": failed,
            "top_failed_flows": top_failed,
            "backlog": backlog,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/reliability")
async def reliability_report(request: Request, window: str = "7d") -> dict[str, Any]:
    client = await get_tws_client(request.app)
    if client is None:
        return {"mtta_minutes": 0.0, "mttr_minutes": 0.0, "flaky_jobs": []}
    try:
        jobs = await client.get_jobs_status()
        total_counts: Counter[str] = Counter()
        fail_counts: Counter[str] = Counter()
        mtta_durations: list[float] = []
        mttr_durations: list[float] = []
        for job in jobs:
            total_counts[job.name] += 1
            if job.status.upper() == "ABEND":
                fail_counts[job.name] += 1
            try:
                details = await client.get_job_details(job.name)
                for execution in details.execution_history:
                    if execution.start_time and execution.end_time:
                        duration = (execution.end_time - execution.start_time).total_seconds() / 60.0
                        mtta_durations.append(duration)
                        if execution.status and execution.status.upper() == "ABEND":
                            mttr_durations.append(duration)
            except Exception:
                continue
        mtta = (sum(mtta_durations) / len(mtta_durations)) if mtta_durations else float(len(jobs)) * 2.5
        mttr = (sum(mttr_durations) / len(mttr_durations)) if mttr_durations else float(len(jobs)) * 5.0
        flaky: list[dict[str, float]] = []
        for name, total in total_counts.items():
            if total:
                rate = fail_counts[name] / total
                if rate > 0.3:
                    flaky.append({"job": name, "failure_rate": rate})
        return {"mtta_minutes": mtta, "mttr_minutes": mttr, "flaky_jobs": flaky}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/sla")
async def sla_report(request: Request, period: str = "week") -> dict[str, Any]:
    client = await get_tws_client(request.app)
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
        met = sum(1 for job in jobs if job.status and job.status.upper() == "SUCC")
        durations: list[float] = []
        risk_map: dict[str, int] = {}
        for job in jobs:
            try:
                details = await client.get_job_details(job.name)
                for execution in details.execution_history:
                    if execution.start_time and execution.end_time:
                        duration = (execution.end_time - execution.start_time).total_seconds() / 60.0
                        durations.append(duration)
                        if execution.status and execution.status.upper() == "ABEND":
                            hour_key = str(execution.start_time.hour)
                            risk_map[hour_key] = risk_map.get(hour_key, 0) + 1
            except Exception:
                continue
        if durations:
            sorted_durations = sorted(durations)
            mean_drift = sum(durations) / len(durations)
            idx_95 = min(int(0.95 * len(sorted_durations)), len(sorted_durations) - 1)
            p95_drift = sorted_durations[idx_95]
        else:
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
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/perf")
async def performance_report(request: Request, window: str = "24h") -> dict[str, Any]:
    client = await get_tws_client(request.app)
    metrics = getattr(request.app.state, "metrics", {})
    http_count = metrics.get("http_request_count", 0) or 1
    http_errors = metrics.get("http_request_errors", 0)
    avg_latency = metrics.get("http_request_latency_sum_ms", 0.0) / http_count
    if client is None:
        return {
            "api_avg_latency_ms": avg_latency,
            "api_error_count": http_errors,
            "resource_utilisation": {},
        }
    try:
        resources = await client.get_resource_usage()
        utilisation = {
            resource.resource_name: {
                "used": resource.used_capacity,
                "total": resource.total_capacity,
                "utilization_percentage": resource.utilization_percentage,
            }
            for resource in resources
        }
        return {
            "api_avg_latency_ms": avg_latency,
            "api_error_count": http_errors,
            "resource_utilisation": utilisation,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _compute_sla_risk(jobs: list[dict], workstations: list[dict]) -> dict[str, float]:
    abend_counts: dict[str, int] = defaultdict(int)
    late_counts: dict[str, int] = defaultdict(int)
    running_counts: dict[str, int] = defaultdict(int)
    for job in jobs:
        stream = job.get("stream") or job.get("job_stream") or "unknown"
        status = str(job.get("status", "")).upper()
        if status == "ABEND":
            abend_counts[stream] += 1
        elif status not in {"SUCC", "SUCCESS"}:
            late_counts[stream] += 1
        if status in {"RUNNING", "HOLD"}:
            running_counts[stream] += 1
    total_depth = 0.0
    for ws in workstations:
        try:
            total_depth += float(ws.get("queue_depth", 0) or 0)
        except Exception:
            continue
    avg_depth = total_depth / max(len(workstations), 1)
    scores: dict[str, float] = {}
    all_streams = set().union(abend_counts.keys(), late_counts.keys(), running_counts.keys())
    for stream in all_streams:
        base_score = (
            abend_counts.get(stream, 0) * 50
            + late_counts.get(stream, 0) * 20
            + running_counts.get(stream, 0) * 5
        )
        depth_score = min(avg_depth * 2, 20)
        score = base_score + depth_score
        max_possible = 50 * 5 + 20 * 10 + 5 * 20 + 20
        normalised = (score / max_possible) * 100.0
        scores[stream] = round(min(normalised, 100.0), 2)
    return scores


@router.get("/sla_watch")
async def sla_watch(request: Request) -> dict[str, float]:
    client = await get_tws_client(request.app)
    if client is None:
        request.app.state.sla_risk_scores = {}  # type: ignore[attr-defined]
        return {}
    try:
        jobs_models = await client.get_jobs_status()
        jobs = [job.dict() for job in jobs_models]
        ws_models = await client.get_workstations_status()
        workstations = [ws.dict() for ws in ws_models]
        scores = _compute_sla_risk(jobs, workstations)
        request.app.state.sla_risk_scores = scores  # type: ignore[attr-defined]
        return scores
    except Exception as exc:
        request.app.state.sla_risk_scores = {}  # type: ignore[attr-defined]
        raise HTTPException(status_code=500, detail=str(exc)) from exc
