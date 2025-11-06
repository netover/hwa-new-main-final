"""Lightweight audit logging manager backed by SQLite."""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional


LOGGER = logging.getLogger("resync.audit")


@dataclass
class AuditLogEntry:
    id: int
    action: str
    user_id: Optional[str]
    details: str
    correlation_id: Optional[str]
    severity: str
    source_component: Optional[str]
    created_at: datetime


class AuditLogManager:
    """SQLite-backed audit log manager used in tests and runtime."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = str(db_path or ":memory:")
        self.engine = sqlite3.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            check_same_thread=False,
        )
        self.engine.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.engine.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                user_id TEXT,
                details TEXT,
                correlation_id TEXT,
                severity TEXT,
                source_component TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.engine.commit()

    @contextmanager
    def get_session(self) -> Iterator[sqlite3.Connection]:
        yield self.engine

    def close(self) -> None:
        try:
            self.engine.close()
        except Exception:  # pragma: no cover - defensive
            LOGGER.debug("Failed to close audit log engine", exc_info=True)

    def log_audit_event(
        self,
        action: str,
        user_id: str | None = None,
        details: dict[str, Any] | None = None,
        *,
        correlation_id: str | None = None,
        severity: str | None = None,
        source_component: str | None = None,
    ) -> Optional[int]:
        payload = json.dumps(details or {})
        try:
            with self.get_session() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO audit_logs (
                        action, user_id, details, correlation_id,
                        severity, source_component
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        action,
                        user_id,
                        payload,
                        correlation_id,
                        severity or "INFO",
                        source_component,
                    ),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.error("Failed to persist audit event: %s", exc, exc_info=True)
            return None

    def query_audit_logs(
        self,
        *,
        action: str | None = None,
        user_id: str | None = None,
        severity: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[AuditLogEntry]:
        query = "SELECT * FROM audit_logs WHERE 1=1"
        params: list[Any] = []
        if action:
            query += " AND action = ?"
            params.append(action)
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        if start_date:
            query += " AND datetime(created_at) >= datetime(?)"
            params.append(start_date.isoformat())
        if end_date:
            query += " AND datetime(created_at) <= datetime(?)"
            params.append(end_date.isoformat())
        query += " ORDER BY datetime(created_at) DESC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        if offset is not None:
            query += " OFFSET ?"
            params.append(offset)

        with self.get_session() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
        return [self._row_to_entry(row) for row in rows]

    def get_audit_metrics(self) -> dict[str, Any]:
        data: dict[str, Any] = {"total_logs": 0, "by_severity": {}, "by_action": {}}
        with self.get_session() as conn:
            total = conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
            data["total_logs"] = total
            for row in conn.execute(
                "SELECT severity, COUNT(*) AS count FROM audit_logs GROUP BY severity"
            ):
                data["by_severity"][row["severity"]] = row["count"]
            for row in conn.execute(
                "SELECT action, COUNT(*) AS count FROM audit_logs GROUP BY action"
            ):
                data["by_action"][row["action"]] = row["count"]
        return data

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> AuditLogEntry:
        created_at = datetime.fromisoformat(row["created_at"])
        return AuditLogEntry(
            id=row["id"],
            action=row["action"],
            user_id=row["user_id"],
            details=row["details"],
            correlation_id=row["correlation_id"],
            severity=row["severity"],
            source_component=row["source_component"],
            created_at=created_at,
        )


_audit_log_manager: AuditLogManager | None = None


def get_audit_log_manager() -> AuditLogManager:
    global _audit_log_manager
    if _audit_log_manager is None:
        _audit_log_manager = AuditLogManager()
    return _audit_log_manager


def set_audit_log_manager(manager: AuditLogManager | None) -> None:
    global _audit_log_manager
    _audit_log_manager = manager


__all__ = ["AuditLogManager", "AuditLogEntry", "get_audit_log_manager", "set_audit_log_manager"]
