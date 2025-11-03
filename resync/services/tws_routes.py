"""TWS API route definitions and contract validation.

This module provides utilities to load the official TWS API specification
from a JSON file (``WA_API3_v2.json``) and to validate that the
endpoints used by the application exist in the specification.  It also
exposes convenience functions to build common endpoint URLs.

The specification file is expected to reside under
``knowledge_base/BASE/WA_API3_v2.json`` relative to the project root.  If
the specification cannot be loaded or is invalid JSON, the loader
returns an empty dictionary.  Comments beginning with ``//`` in the JSON
file are stripped prior to parsing.

Example usage::

    from resync.services.tws_routes import load_tws_api_spec, validate_routes

    spec = load_tws_api_spec()
    validate_routes([
        ("GET", "/model/workstation"),
        ("GET", "/plan/current"),
    ])

Author: Resync Project Maintainers
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Iterable, Tuple

__all__ = [
    "load_tws_api_spec",
    "validate_routes",
    "TWS_ROUTES",
]


def _strip_json_comments(text: str) -> str:
    """Remove simple ``//`` comments from a JSON-like string.

    This helper is intentionally minimal: it removes any occurrence of
    ``//`` and the remainder of the line.  It does not support block
    comments or strings containing ``//``.  It is used to parse the
    WA_API3_v2.json file, which may include single-line comments.
    """
    lines: list[str] = []
    for line in text.splitlines():
        if "//" in line:
            line = line.split("//", 1)[0]
        lines.append(line)
    return "\n".join(lines)


def load_tws_api_spec(path: str | None = None) -> Dict[str, Dict[str, any]]:
    """Load the TWS API specification from a JSON file.

    Parameters
    ----------
    path: str | None
        Optional path to the JSON specification file.  If not provided,
        defaults to ``knowledge_base/BASE/WA_API3_v2.json`` relative to
        the project root.

    Returns
    -------
    dict
        A dictionary representing the parsed API specification.  If the
        file cannot be read or parsed, an empty dictionary is returned.
    """
    # Determine default path relative to this file (two levels up)
    if path is None:
        base_dir = Path(__file__).resolve().parents[2]
        default_path = base_dir / "knowledge_base" / "BASE" / "WA_API3_v2.json"
        path = str(default_path)
    spec: Dict[str, Dict[str, any]] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
            cleaned = _strip_json_comments(raw)
            # Parse JSON
            spec = json.loads(cleaned)
    except Exception:
        # Return empty spec on any error
        return {}
    return spec  # type: ignore[return-value]


def validate_routes(routes: Iterable[Tuple[str, str]], spec: Dict[str, any] | None = None) -> None:
    """Validate that the given method/path pairs exist in the API spec.

    Raises a ``ValueError`` if any route is missing.  If the spec is
    not provided, it will be loaded from the default location.
    """
    if spec is None:
        spec = load_tws_api_spec()
    paths = set()
    # Flatten the spec to a set of (method, path) tuples
    for path, path_item in spec.get("paths", {}).items():
        if isinstance(path_item, dict):
            for method, _ in path_item.items():
                paths.add((method.upper(), path))
    missing: list[str] = []
    for method, route in routes:
        if (method.upper(), route) not in paths:
            missing.append(f"{method.upper()} {route}")
    if missing:
        raise ValueError(f"The following routes are not defined in the TWS API spec: {', '.join(missing)}")


class TWS_ROUTES:
    """Helper container for building common TWS API URLs.

    These methods return path strings relative to the TWS base URL.  They do
    not perform validation against the API specification.
    """

    @staticmethod
    def workstations(engine_name: str, engine_owner: str) -> str:
        return f"/model/workstation?engineName={engine_name}&engineOwner={engine_owner}"

    @staticmethod
    def jobs_status(engine_name: str, engine_owner: str) -> str:
        return f"/model/jobdefinition?engineName={engine_name}&engineOwner={engine_owner}"

    @staticmethod
    def job_details(job_id: str, engine_name: str, engine_owner: str) -> str:
        return f"/model/jobdefinition/{job_id}?engineName={engine_name}&engineOwner={engine_owner}"

    @staticmethod
    def job_dependencies(job_id: str, engine_name: str, engine_owner: str) -> str:
        return f"/model/jobdefinition/{job_id}/dependencies?engineName={engine_name}&engineOwner={engine_owner}"

    @staticmethod
    def plan_current(engine_name: str, engine_owner: str) -> str:
        return f"/plan/current?engineName={engine_name}&engineOwner={engine_owner}"

    @staticmethod
    def critical_path(engine_name: str, engine_owner: str) -> str:
        return f"/plan/current/criticalpath?engineName={engine_name}&engineOwner={engine_owner}"