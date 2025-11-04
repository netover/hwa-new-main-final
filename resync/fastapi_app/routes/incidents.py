"""Incident management endpoints backed by Redis or in-memory storage."""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi import FastAPI

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])

try:
    from resync.core.redis_init import get_redis_client, is_redis_available  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    get_redis_client = None  # type: ignore

    def is_redis_available() -> bool:  # type: ignore
        return False


async def _load_incidents(app: FastAPI) -> list[dict[str, Any]]:
    """Load incidents from Redis when available."""
    try:
        if callable(is_redis_available) and is_redis_available():
            if os.getenv("RESYNC_DISABLE_REDIS") != "1" and get_redis_client is not None:
                client = get_redis_client()
                data = await client.get("resync:incidents")  # type: ignore[attr-defined]
                if data:
                    return json.loads(data)
    except Exception:
        pass
    return list(getattr(app.state, "incidents", []))


async def _save_incidents(app: FastAPI, incidents: list[dict[str, Any]]) -> None:
    """Persist incidents to Redis and update in-memory cache."""
    try:
        if callable(is_redis_available) and is_redis_available():
            if os.getenv("RESYNC_DISABLE_REDIS") != "1" and get_redis_client is not None:
                client = get_redis_client()
                await client.set("resync:incidents", json.dumps(incidents))  # type: ignore[attr-defined]
                app.state.incidents = incidents  # type: ignore[attr-defined]
                return
    except Exception:
        pass
    app.state.incidents = incidents  # type: ignore[attr-defined]


def _calculate_incident_priority(impact: float, urgency: float) -> float:
    return impact * urgency


@router.post("")
async def create_incident(incident: dict[str, Any], request: Request) -> dict[str, Any]:
    job_id = incident.get("job_id")
    status = incident.get("status")
    timestamp = incident.get("timestamp")
    severity_map = {"ABEND": 3.0, "ERROR": 2.0, "WARNING": 1.0}
    severity = severity_map.get((status or "").upper(), 1.0)
    impact = float(len(job_id)) if job_id else 1.0
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
    record = {
        "id": str(uuid.uuid4()),
        "job_id": job_id,
        "workstation": incident.get("workstation"),
        "status": status,
        "root_cause": incident.get("root_cause"),
        "timestamp": timestamp,
        "severity": severity,
        "impact": impact,
        "urgency": urgency,
        "priority": priority,
        "owner": None,
        "state": "Novo",
        "notes": [],
    }
    incidents = await _load_incidents(request.app)
    incidents.append(record)
    await _save_incidents(request.app, incidents)
    return {"id": record["id"], "priority": priority}


@router.get("")
async def list_incidents(
    request: Request,
    status: str | None = None,
    sort: str | None = None,
) -> list[dict[str, Any]]:
    incidents = await _load_incidents(request.app)
    filtered: list[dict[str, Any]] = []
    for inc in incidents:
        state = str(inc.get("state", "Novo")).lower()
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


@router.post("/{incident_id}/assign")
async def assign_incident(
    incident_id: str,
    request: Request,
    assignee: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    incidents = await _load_incidents(request.app)
    owner = assignee.get("owner")
    for inc in incidents:
        if inc["id"] == incident_id:
            inc["owner"] = owner
            inc["state"] = "Em andamento"
            await _save_incidents(request.app, incidents)
            return {
                "id": incident_id,
                "owner": owner,
                "state": inc.get("state"),
                "priority": inc.get("priority"),
            }
    raise HTTPException(status_code=404, detail="Incident not found")


@router.post("/{incident_id}/snooze")
async def snooze_incident(
    incident_id: str,
    request: Request,
    minutes: int = Body(...),
) -> dict[str, Any]:
    incidents = await _load_incidents(request.app)
    for inc in incidents:
        if inc["id"] == incident_id:
            inc["state"] = "Silenciado"
            inc["urgency"] = max(0.1, inc.get("urgency", 1.0) * 0.1)
            inc["priority"] = _calculate_incident_priority(
                inc.get("impact", 1.0),
                inc["urgency"],
            )
            await _save_incidents(request.app, incidents)
            return {
                "id": incident_id,
                "state": inc.get("state"),
                "priority": inc.get("priority"),
            }
    raise HTTPException(status_code=404, detail="Incident not found")


@router.post("/{incident_id}/note")
async def add_incident_note(
    incident_id: str,
    request: Request,
    note_body: dict[str, Any] = Body(...),
) -> dict[str, str]:
    note = note_body.get("note")
    incidents = await _load_incidents(request.app)
    for inc in incidents:
        if inc["id"] == incident_id:
            inc.setdefault("notes", []).append(note)
            await _save_incidents(request.app, incidents)
            return {"id": incident_id}
    raise HTTPException(status_code=404, detail="Incident not found")


@router.post("/{incident_id}/open-runbook")
async def open_runbook(incident_id: str, request: Request) -> dict[str, str]:
    incidents = await _load_incidents(request.app)
    for inc in incidents:
        if inc["id"] == incident_id:
            job_id = inc.get("job_id") or "unknown"
            return {"id": incident_id, "url": f"/runbook/{job_id}"}
    raise HTTPException(status_code=404, detail="Incident not found")
