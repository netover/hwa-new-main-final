"""Observability endpoints exposing in-memory metrics."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["observability"])


@router.get("/api/v1/observability/metrics")
async def get_observability_metrics(request: Request) -> dict[str, object]:
    """Return aggregated metrics captured by the middleware."""
    metrics = getattr(request.app.state, "metrics", {})
    count = metrics.get("http_request_count", 0) or 1
    avg_latency = metrics.get("http_request_latency_sum_ms", 0.0) / count
    sla_risks = getattr(request.app.state, "sla_risk_scores", {})
    return {
        **metrics,
        "http_request_avg_latency_ms": avg_latency,
        "sla_risk_scores": sla_risks,
    }


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics(request: Request) -> str:
    """Expose metrics in Prometheus text format."""
    metrics = getattr(request.app.state, "metrics", {})
    lines: list[str] = []
    lines.append("# HELP resync_http_requests_total Total number of HTTP requests processed")
    lines.append("# TYPE resync_http_requests_total counter")
    lines.append(f"resync_http_requests_total {metrics.get('http_request_count', 0)}")

    lines.append("# HELP resync_http_request_errors_total Total number of HTTP errors")
    lines.append("# TYPE resync_http_request_errors_total counter")
    lines.append(f"resync_http_request_errors_total {metrics.get('http_request_errors', 0)}")

    lines.append("# HELP resync_http_request_latency_sum_ms Sum of HTTP request latencies in milliseconds")
    lines.append("# TYPE resync_http_request_latency_sum_ms counter")
    lines.append(
        f"resync_http_request_latency_sum_ms {metrics.get('http_request_latency_sum_ms', 0.0)}"
    )

    lines.append("# HELP resync_ws_connections_total Total number of WebSocket connections opened")
    lines.append("# TYPE resync_ws_connections_total counter")
    lines.append(f"resync_ws_connections_total {metrics.get('ws_connection_count', 0)}")

    lines.append("# HELP resync_ws_messages_total Total number of WebSocket messages received")
    lines.append("# TYPE resync_ws_messages_total counter")
    lines.append(f"resync_ws_messages_total {metrics.get('ws_message_count', 0)}")

    sla_risks = getattr(request.app.state, "sla_risk_scores", {})
    if sla_risks:
        lines.append("# HELP resync_sla_risk_score Heuristic SLA risk score per stream")
        lines.append("# TYPE resync_sla_risk_score gauge")
        for stream, score in sla_risks.items():
            label = str(stream).replace('"', '\\"')
            lines.append(f'resync_sla_risk_score{{stream="{label}"}} {score}')
    return "\n".join(lines) + "\n"
