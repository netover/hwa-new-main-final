"""Static assets and template configuration helpers."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterable

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)


def _deduplicate_paths(paths: Iterable[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


def _resolve_resource_directory(env_var: str, *relative_parts: str) -> Path | None:
    candidates: list[Path] = []

    env_value = os.getenv(env_var)
    if env_value:
        candidates.append(Path(env_value).expanduser())

    module_path = Path(__file__).resolve()
    base_dir = module_path.parents[2]
    project_root = base_dir.parent
    candidates.extend(
        [
            module_path.parent / Path(*relative_parts),
            base_dir / Path(*relative_parts),
            project_root / Path(*relative_parts),
        ]
    )

    for candidate in _deduplicate_paths(candidates):
        if candidate.exists():
            return candidate
    logger.warning(
        "Unable to resolve resource directory for %s; tried: %s",
        env_var,
        ", ".join(str(path) for path in _deduplicate_paths(candidates)),
    )
    return None


def setup_static_files(app: FastAPI) -> Jinja2Templates | None:
    """Mount static assets and prepare template rendering."""
    static_dir = _resolve_resource_directory("RESYNC_STATIC_DIR", "static")
    if static_dir:
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    else:
        logger.warning("Static directory could not be resolved; static files disabled.")

    templates_dir = _resolve_resource_directory("RESYNC_TEMPLATES_DIR", "templates")
    if templates_dir:
        templates = Jinja2Templates(directory=str(templates_dir))
        app.state.templates = templates  # type: ignore[attr-defined]
        return templates

    logger.warning("Templates directory could not be resolved; template rendering disabled.")
    return None
