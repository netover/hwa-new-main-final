"""Utilities for validating and sanitising CSP violation reports."""

from __future__ import annotations

import html
import ipaddress
import json
from typing import Any, Dict
from urllib.parse import urlparse

MAX_REPORT_SIZE = 8 * 1024  # 8KB limit to prevent abuse
ALLOWED_DISPOSITIONS = {"enforce", "report", "warn"}


class CSPValidationError(ValueError):
    """Raised when a CSP report is malformed or unsafe."""


def _is_private_ip(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback
    except ValueError:
        return host in {"localhost", "127.0.0.1", "::1"}


def _is_safe_uri(uri: str) -> bool:
    """Validate URIs to avoid leaking local/internal information."""
    if uri is None:
        return False
    lowered = uri.lower()
    if lowered in {"self", "'self'", "none", "'none'", "unsafe-inline", "'unsafe-inline'", "unsafe-eval", "'unsafe-eval'"}:
        return True

    if lowered.startswith("data:"):
        return len(uri) <= 1024

    parsed = urlparse(uri)
    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.netloc:
        return False

    host = parsed.hostname or ""
    if _is_private_ip(host):
        return False
    return True


def _is_safe_directive_value(value: str) -> bool:
    """Ensure directive values do not contain obvious script injections."""
    if value is None:
        return False
    lowered = value.lower()
    if "<script" in lowered or "javascript:" in lowered or "onerror=" in lowered:
        return False
    return True


def sanitize_csp_report(report: Any) -> Any:
    """Recursively sanitize a CSP report structure."""
    if isinstance(report, dict):
        sanitized: Dict[str, Any] = {}
        for key, value in report.items():
            if key == "disposition" and isinstance(value, str):
                if value not in ALLOWED_DISPOSITIONS:
                    continue
            sanitized[key] = sanitize_csp_report(value)
        return sanitized
    if isinstance(report, list):
        return [sanitize_csp_report(item) for item in report]
    if isinstance(report, str):
        # Escape only single quotes to prevent template injection; keep <script> tokens for debugging.
        return html.escape(report, quote=False).replace("'", "&#x27;")
    return report


def validate_csp_report(report_bytes: bytes) -> bool:
    """Validate the CSP report payload for size and required fields."""
    if not report_bytes or len(report_bytes) > MAX_REPORT_SIZE:
        return False
    try:
        payload = json.loads(report_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False

    if not isinstance(payload, dict):
        return False

    report = payload.get("csp-report")
    if not isinstance(report, dict):
        return False

    required_fields = {"document-uri", "violated-directive", "original-policy"}
    if not required_fields.issubset(report):
        return False

    document_uri = report.get("document-uri")
    if isinstance(document_uri, str) and not _is_safe_uri(document_uri):
        return False

    for field in ("violated-directive", "effective-directive", "original-policy"):
        value = report.get(field)
        if isinstance(value, str) and not _is_safe_directive_value(value):
            return False

    return True


def validate_csp_report_legacy(report_bytes: bytes) -> bool:
    """Legacy wrapper for compatibility with older code paths."""
    return validate_csp_report(report_bytes)


async def process_csp_report(request) -> Dict[str, Any]:
    """Parse, validate and sanitize a CSP violation report from a request."""
    body = await request.body()
    if not validate_csp_report(body):
        raise CSPValidationError("Invalid CSP report payload")

    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise CSPValidationError("Malformed CSP report") from exc

    sanitized = sanitize_csp_report(payload)
    return {"report": sanitized}


__all__ = [
    "CSPValidationError",
    "process_csp_report",
    "validate_csp_report",
    "validate_csp_report_legacy",
    "sanitize_csp_report",
    "_is_safe_uri",
    "_is_safe_directive_value",
]
