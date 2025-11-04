"""Core routes for the Resync FastAPI application."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.websockets import WebSocket, WebSocketDisconnect

router = APIRouter()


def render_template(request: Request, template_name: str, context: dict[str, Any]) -> HTMLResponse:
    """Render a template stored on the application state."""
    templates = getattr(request.app.state, "templates", None)
    if templates is None:
        raise HTTPException(status_code=500, detail="Templates not configured.")
    return templates.TemplateResponse(template_name, context)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Serve the main dashboard page."""
    return render_template(request, "index.html", {"request": request})


@router.get("/api/v1/status")
async def get_status(request: Request) -> dict[str, Any]:
    """Return a minimal status payload for the frontend dashboard."""
    return {
        "tws_connected": False,
        "mock_mode": True,
        "agents_loaded": 0,
        "knowledge_graph": "available",
        "workstations": [],
        "jobs": [],
        "tws_config": getattr(request.app.state, "_tws_config", {}),
    }


@router.get("/api/v1/chat")
async def get_chat() -> dict[str, str]:
    """Basic chat endpoint placeholder."""
    return {"message": "Chat endpoint working", "status": "active"}


@router.get("/api/v1/agents/")
async def list_agents() -> list[dict[str, str]]:
    """List all registered agents."""
    return [
        {
            "id": "test-agent-1",
            "name": "Test Agent 1",
            "role": "Tester",
            "goal": "To be tested",
            "model": "test-model",
        }
    ]


@router.get("/api/v1/agents/{agent_id}")
async def get_agent(agent_id: str) -> dict[str, str]:
    """Return details for a specific agent."""
    return {
        "id": agent_id,
        "name": f"Agent {agent_id}",
        "role": "Assistant",
        "goal": "To assist users",
        "model": "test-model",
    }


@router.websocket("/api/v1/ws/{agent_id}")
async def websocket_endpoint(websocket: WebSocket, agent_id: str) -> None:
    """WebSocket endpoint for real-time chat communication."""
    await websocket.accept()
    metrics = getattr(websocket.app.state, "metrics", {})
    ws_corr_id = str(uuid.uuid4())
    websocket.state.correlation_id = ws_corr_id
    metrics["ws_connection_count"] = metrics.get("ws_connection_count", 0) + 1
    try:
        await websocket.send_json(
            {
                "type": "system",
                "sender": "system",
                "message": f"Connected to agent {agent_id}",
                "is_final": True,
                "correlation_id": ws_corr_id,
            }
        )
        while True:
            try:
                data = await websocket.receive_text()
            except WebSocketDisconnect:
                break
            metrics["ws_message_count"] = metrics.get("ws_message_count", 0) + 1
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json(
                    {
                        "type": "error",
                        "sender": "system",
                        "message": "Invalid JSON payload",
                        "is_final": True,
                        "correlation_id": ws_corr_id,
                    }
                )
                continue
            msg_type = payload.get("type")
            if msg_type == "chat_message":
                content = payload.get("content", "")
                full_response = f"Recebido: {content}"
                chunk_size = 40
                for start in range(0, len(full_response), chunk_size):
                    segment = full_response[start : start + chunk_size]
                    is_last = start + chunk_size >= len(full_response)
                    if not is_last:
                        await websocket.send_json(
                            {
                                "type": "stream",
                                "sender": "agent",
                                "message": segment,
                                "is_final": False,
                                "correlation_id": ws_corr_id,
                            }
                        )
                    else:
                        await websocket.send_json(
                            {
                                "type": "message",
                                "sender": "agent",
                                "message": segment,
                                "is_final": True,
                                "correlation_id": ws_corr_id,
                            }
                        )
            else:
                await websocket.send_json(
                    {
                        "type": "error",
                        "sender": "system",
                        "message": f"Unsupported message type: {msg_type}",
                        "is_final": True,
                        "correlation_id": ws_corr_id,
                    }
                )
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request) -> HTMLResponse:
    """Render the reports page."""
    return render_template(request, "reports.html", {"request": request})


@router.get("/incidents", response_class=HTMLResponse)
async def incidents_page(request: Request) -> HTMLResponse:
    """Render the incidents page."""
    return render_template(request, "incidents.html", {"request": request})


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_details_page(job_id: str, request: Request) -> HTMLResponse:
    """Render the job details page."""
    return render_template(
        request,
        "job.html",
        {"request": request, "job_id": job_id},
    )


@router.get("/graph/{job_id}", response_class=HTMLResponse)
async def job_graph_page(job_id: str, request: Request) -> HTMLResponse:
    """Render the job dependency graph page."""
    return render_template(
        request,
        "graph.html",
        {"request": request, "job_id": job_id},
    )


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "healthy", "service": "resync-api"}
