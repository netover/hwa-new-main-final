"""
API routes for admin configuration management.

This module provides simple endpoints to persist and retrieve configuration
settings for the administration UI.  Currently it supports only the
Microsoft Teams integration settings, but it can be extended to cover
additional configuration domains (e.g., TWS instances, system settings)
without changing the core logic.

Configurations are persisted to a JSON file under the ``config`` folder
within the project.  If the file does not exist, a default configuration
is returned.  Modifying environment variables or system settings at
runtime is outside the scope of this demonstration implementation.

Endpoints:

* ``GET /admin/teams-config`` – Return current Teams integration settings.
* ``POST /admin/teams-config`` – Update Teams integration settings.

These endpoints are mounted under the ``/api/v1/admin`` prefix via the
main application (see ``main.py``).
"""

from pathlib import Path
from typing import Any, Dict

import json
import shutil
import datetime
from fastapi import APIRouter, HTTPException, status


router = APIRouter()

# Determine the path to the configuration file.  We place the file
# alongside other configuration resources (e.g., settings.toml) inside
# the top-level ``config`` directory.  ``__file__`` is
# ``.../resync/fastapi_app/api/v1/routes/admin_config.py``.
CONFIG_PATH = Path(__file__).resolve().parent.parent.parent.parent.parent / "config" / "admin_config.json"

# Default configuration values used when the config file does not exist.
DEFAULT_CONFIG: Dict[str, Any] = {
    "teams_config": {
        "enabled": False,
        "webhook_url": "",
        "channel_name": "",
        "bot_name": "Resync Bot",
        "avatar_url": ""
    },
    # Configuration for TWS instances.  ``primary_instance`` is
    # required; ``monitored_instances`` is a list of instance names.
    "tws_config": {
        "primary_instance": "TWS_NAZ",
        "monitored_instances": ["TWS_NAZ", "TWS_SAZ"],
    },
    # System-wide settings controlling environment and security features.
    "system_settings": {
        "environment": "Production",
        "debug_mode": False,
        "ssl_enabled": True,
        "csp_enabled": True,
        "cors_enabled": True,
    },
    # Notification configuration (job status filters and alert toggles).
    "notifications": {
        "job_status_filters": ["ABEND", "ERROR", "FAILED"],
        "notify_job_status": True,
        "notify_alerts": True,
        "notify_performance": False,
    },
}

# -----------------------------------------------------------------------------
# Health monitoring helpers
#
# The admin UI may request a high-level health report for key services such as
# the primary database, cache and external integrations.  For demonstration
# purposes we avoid deep dependency checks and instead return simple boolean
# flags.  Integrators can replace these stubs with real connectivity tests.
def _get_health_report() -> Dict[str, Any]:
    """Assemble a basic health report.

    Returns
    -------
    dict
        A dictionary with boolean flags indicating the status of key services.
    """
    report = {
        "database": True,
        "cache": True,
        "teams": False,
        "llm": True,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }
    # If Teams integration is enabled in the config, mark as active
    cfg = _load_config()
    teams_cfg = cfg.get("teams_config", DEFAULT_CONFIG["teams_config"])
    report["teams"] = bool(teams_cfg.get("enabled"))
    return report



def _load_config() -> Dict[str, Any]:
    """Read the configuration from disk or return defaults.

    Returns
    -------
    dict
        The configuration dictionary containing all configurable sections.
    """
    if CONFIG_PATH.exists():
        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
                # Merge missing top-level keys from defaults without
                # overriding existing values.
                merged = DEFAULT_CONFIG.copy()
                merged.update(data)
                return merged
        except Exception:
            # If the file is corrupted, fall back to defaults but do not
            # overwrite the file immediately.  The next save will update it.
            return DEFAULT_CONFIG.copy()
    else:
        return DEFAULT_CONFIG.copy()


def _save_config(config: Dict[str, Any]) -> None:
    """Persist the entire configuration to disk as JSON.

    Parameters
    ----------
    config : dict
        The configuration to persist.
    """
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save configuration: {exc}"
        )


@router.get("/teams-config", tags=["Admin"])
async def get_teams_config() -> Dict[str, Any]:
    """Retrieve current Teams integration settings.

    Returns
    -------
    dict
        A dictionary containing Teams integration configuration such as
        ``enabled``, ``webhook_url``, ``channel_name``, ``bot_name`` and
        ``avatar_url``.
    """
    config = _load_config()
    return config.get("teams_config", DEFAULT_CONFIG["teams_config"]).copy()


@router.post("/teams-config", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin"])
async def update_teams_config(settings: Dict[str, Any]) -> None:
    """Persist Teams integration settings provided by the admin UI.

    Parameters
    ----------
    settings : dict
        A dictionary containing Teams integration configuration fields.  Any
        unspecified fields will be left unchanged from the current config.

    Raises
    ------
    HTTPException
        If saving the configuration fails.
    """
    config = _load_config()
    teams_config = config.get("teams_config", DEFAULT_CONFIG["teams_config"]).copy()
    # Update only known keys; ignore unknown keys for forward compatibility.
    for key in ["enabled", "webhook_url", "channel_name", "bot_name", "avatar_url"]:
        if key in settings:
            teams_config[key] = settings[key]
    config["teams_config"] = teams_config
    _save_config(config)
    # Returning None with status 204 implies success with no content


# ----- TWS Configuration Endpoints -----

@router.get("/tws-config", tags=["Admin"])
async def get_tws_config() -> Dict[str, Any]:
    """Return current TWS connection configuration."""
    config = _load_config()
    return config.get("tws_config", DEFAULT_CONFIG["tws_config"]).copy()


@router.post("/tws-config", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin"])
async def update_tws_config(settings: Dict[str, Any]) -> None:
    """Update TWS connection configuration.

    Accepts ``primary_instance`` (str) and ``monitored_instances`` (list of str).
    """
    config = _load_config()
    tws_config = config.get("tws_config", DEFAULT_CONFIG["tws_config"]).copy()
    if "primary_instance" in settings:
        tws_config["primary_instance"] = settings["primary_instance"]
    if "monitored_instances" in settings and isinstance(settings["monitored_instances"], list):
        tws_config["monitored_instances"] = settings["monitored_instances"]
    config["tws_config"] = tws_config
    _save_config(config)


# ----- System Settings Endpoints -----

@router.get("/system-settings", tags=["Admin"])
async def get_system_settings() -> Dict[str, Any]:
    """Return current system settings."""
    config = _load_config()
    return config.get("system_settings", DEFAULT_CONFIG["system_settings"]).copy()


@router.post("/system-settings", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin"])
async def update_system_settings(settings: Dict[str, Any]) -> None:
    """Update system settings configuration.

    Accepts any subset of keys defined in the ``system_settings`` section.
    """
    config = _load_config()
    sys_cfg = config.get("system_settings", DEFAULT_CONFIG["system_settings"]).copy()
    for key in ["environment", "debug_mode", "ssl_enabled", "csp_enabled", "cors_enabled"]:
        if key in settings:
            sys_cfg[key] = settings[key]
    config["system_settings"] = sys_cfg
    _save_config(config)


# ----- Notifications Endpoints -----

@router.get("/notifications", tags=["Admin"])
async def get_notifications() -> Dict[str, Any]:
    """Return current notification configuration."""
    config = _load_config()
    return config.get("notifications", DEFAULT_CONFIG["notifications"]).copy()


@router.post("/notifications", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin"])
async def update_notifications(settings: Dict[str, Any]) -> None:
    """Update notification configuration.

    Accepts ``job_status_filters`` (list of str) and boolean toggles for
    ``notify_job_status``, ``notify_alerts``, and ``notify_performance``.
    """
    config = _load_config()
    notifications = config.get("notifications", DEFAULT_CONFIG["notifications"]).copy()
    if "job_status_filters" in settings and isinstance(settings["job_status_filters"], list):
        notifications["job_status_filters"] = settings["job_status_filters"]
    for key in ["notify_job_status", "notify_alerts", "notify_performance"]:
        if key in settings:
            notifications[key] = bool(settings[key])
    config["notifications"] = notifications
    _save_config(config)


# ----- Logs Endpoint -----

@router.get("/logs", tags=["Admin"])
async def get_logs(file: str = "app.log", lines: int = 100) -> Dict[str, Any]:
    """Return the last ``lines`` lines of the specified log file.

    Parameters
    ----------
    file : str, optional
        Name of the log file (must be located in the project's ``logs`` directory).
    lines : int, optional
        Number of lines to return from the end of the file.

    Returns
    -------
    dict
        A dictionary containing the filename and the text content of the log.
    """
    logs_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "logs"
    log_path = logs_dir / file
    if not log_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log file not found")
    try:
        # Read the last ``lines`` lines efficiently
        with log_path.open("r", encoding="utf-8", errors="ignore") as f:
            # Use deque to store the last ``lines`` lines
            from collections import deque
            dq = deque(f, maxlen=lines)
            content = "".join(dq)
        return {"file": file, "content": content}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to read log file: {exc}")


# ----- Backup and Restore Endpoints -----

@router.post("/backup", tags=["Admin"])
async def create_backup() -> Dict[str, str]:
    """Create a timestamped backup of critical databases.

    Copies ``audit_log.db`` and ``audit_queue.db`` (if present) into a
    ``backup`` directory within the project, appending a timestamp to the
    filenames.  Returns the names of the created backup files.
    """
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    backup_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    created = []
    for db_name in ["audit_log.db", "audit_queue.db"]:
        src = Path(__file__).resolve().parent.parent.parent.parent.parent / db_name
        if src.is_file():
            dest = backup_dir / f"{src.stem}_{timestamp}{src.suffix}"
            try:
                shutil.copy2(src, dest)
                created.append(dest.name)
            except Exception as exc:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                    detail=f"Failed to backup {db_name}: {exc}")
    return {"created": created}


@router.post("/restore", tags=["Admin"])
async def restore_from_latest() -> Dict[str, str]:
    """Restore the most recent backup of the audit databases.

    Finds the latest files in the ``backup`` directory matching
    ``audit_log_*`` and ``audit_queue_*`` and copies them back into the
    project root.  Returns the names of the files restored.
    """
    backup_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "backup"
    if not backup_dir.is_dir():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No backup directory found")
    restored = []
    for pattern in ["audit_log_*.db", "audit_queue_*.db"]:
        backups = sorted(backup_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        if backups:
            latest = backups[0]
            target = Path(__file__).resolve().parent.parent.parent.parent.parent / latest.name.split("_")[0] + ".db"
            try:
                shutil.copy2(latest, target)
                restored.append(latest.name)
            except Exception as exc:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                    detail=f"Failed to restore {latest.name}: {exc}")
    return {"restored": restored}


# ----- Audit Logs Endpoint -----

@router.get("/audit", tags=["Admin"])
async def get_audit_logs(limit: int = 50) -> Dict[str, Any]:
    """Return the latest entries from the audit log database.

    Parameters
    ----------
    limit : int, optional
        Maximum number of audit records to return.

    Returns
    -------
    dict
        A dictionary containing a list of audit records.  If the database
        cannot be read, returns an empty list.
    """
    db_path = Path(__file__).resolve().parent.parent.parent.parent.parent / "audit_log.db"
    if not db_path.is_file():
        return {"records": []}


# ----- Health Monitoring Endpoint -----

@router.get("/health", tags=["Admin"])
async def get_health() -> Dict[str, Any]:
    """Return a simple health report for key services.

    The report includes boolean flags for the database, cache, Teams integration
    (if enabled in the configuration) and the LLM service.  In a production
    deployment, these values should be determined via connectivity checks or
    service probes.

    Returns
    -------
    dict
        A dictionary containing health flags and a timestamp.
    """
    return _get_health_report()
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # Attempt to read a table named 'audit_log' or 'log'; adapt as needed.
        # Fallback if table does not exist.
        table = None
        for candidate in ["audit_log", "log", "logs", "events"]:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (candidate,)
            )
            if cursor.fetchone():
                table = candidate
                break
        if not table:
            return {"records": []}
        cursor.execute(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        records = [dict(r) for r in rows]
        conn.close()
        return {"records": records}
    except Exception as exc:
        # If reading fails, return empty list to avoid exposing internals
        return {"records": []}
