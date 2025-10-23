"""
Audit Logging System for Resync

This module implements comprehensive audit logging to persist audit events to a database,
in addition to the existing Redis-based audit queue functionality.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from resync.settings import settings

logger = logging.getLogger(__name__)

# SQLAlchemy setup
Base = declarative_base()


class AuditLogEntry(Base):  
    """
    SQLAlchemy model for audit log entries.
    """

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String(255), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    details = Column(Text)  # JSON string
    correlation_id = Column(String(255), nullable=True, index=True)  # For tracing
    source_component = Column(String(255), nullable=True, default="audit")
    severity = Column(
        String(50), nullable=True, default="INFO"
    )  # INFO, WARNING, ERROR, CRITICAL

    def __repr__(self) -> str:
        return f"<AuditLogEntry(id={self.id}, action='{self.action}', user_id='{self.user_id}', timestamp='{self.timestamp}')>"


class AuditLogResponse(BaseModel):
    """
    Pydantic model for audit log responses.
    """

    id: int
    action: str
    user_id: str
    timestamp: datetime
    details: str
    correlation_id: Optional[str]
    source_component: Optional[str]
    severity: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class AuditLogManager:
    """
    Manages audit logging to database with proper session handling.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the audit log manager.

        Args:
            db_path: Path to the SQLite database. If None, uses default settings.
        """
        self.db_path = db_path or str(settings.BASE_DIR / "audit_log.db")
        self.engine = self._create_engine()
        self.SessionLocal = sessionmaker(bind=self.engine)
        self._create_tables()

    def _create_engine(self) -> Any:
        """
        Create SQLAlchemy engine with optimized settings for audit logs.
        """
        return create_engine(
            f"sqlite:///{self.db_path}",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False, "timeout": 30.0},
            echo=False,  # Set to True for debugging
        )

    def _create_tables(self) -> None:
        """
        Create audit log tables if they don't exist.
        """
        Base.metadata.create_all(bind=self.engine)
        logger.info(f"Audit logs database initialized at: {self.db_path}")

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Context manager for getting a database session.

        Yields:
            Database session for audit logging operations.
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {str(e)}", exc_info=True)
            raise
        finally:
            session.close()

    def log_audit_event(
        self,
        action: str,
        user_id: str,
        details: Dict[str, Any],
        correlation_id: Optional[str] = None,
        source_component: str = "audit",
        severity: str = "INFO",
    ) -> Optional[int]:
        """
        Log an audit event to the database.

        Args:
            action: The audited action
            user_id: The ID of the user performing the action
            details: Additional details about the action
            correlation_id: Optional correlation ID for tracing
            source_component: Component name logging the event
            severity: Severity level (INFO, WARNING, ERROR, CRITICAL)

        Returns:
            The ID of the created audit log entry, or None if failed
        """
        try:
            # Serialize details to JSON string
            import json

            details_json = json.dumps(
                details, default=str
            )  # Convert non-serializable objects to strings

            # Create audit log entry
            audit_entry = AuditLogEntry(
                action=action,
                user_id=user_id,
                details=details_json,
                correlation_id=correlation_id,
                source_component=source_component,
                severity=severity,
            )

            # Save to database
            with self.get_session() as session:
                session.add(audit_entry)
                session.flush()  # Get the ID without committing
                audit_id = int(audit_entry.id) if audit_entry.id is not None else None
                session.commit()

            logger.debug(
                f"Audit event logged: action={action}, user_id={user_id}, audit_id={audit_id}"
            )
            return audit_id

        except Exception as e:
            logger.error(f"Failed to log audit event: {str(e)}", exc_info=True)
            return None

    def query_audit_logs(
        self,
        action: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        severity: Optional[str] = None,
        correlation_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditLogResponse]:
        """
        Query audit logs with optional filters.

        Args:
            action: Filter by specific action
            user_id: Filter by specific user ID
            start_date: Filter by minimum timestamp
            end_date: Filter by maximum timestamp
            severity: Filter by severity level
            correlation_id: Filter by correlation ID
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of matching audit log entries as dictionaries to avoid ORM session issues
        """
        try:
            with self.get_session() as session:
                query = session.query(AuditLogEntry)

                if action:
                    query = query.filter(AuditLogEntry.action == action)
                if user_id:
                    query = query.filter(AuditLogEntry.user_id == user_id)
                if start_date:
                    query = query.filter(AuditLogEntry.timestamp >= start_date)
                if end_date:
                    query = query.filter(AuditLogEntry.timestamp <= end_date)
                if severity:
                    query = query.filter(AuditLogEntry.severity == severity)
                if correlation_id:
                    query = query.filter(AuditLogEntry.correlation_id == correlation_id)

                # Add ordering and limits
                query = query.order_by(AuditLogEntry.timestamp.desc())
                query = query.offset(offset).limit(limit)

                # Convert to dictionaries to avoid session detachment issues
                results = [AuditLogResponse.from_orm(entry) for entry in query.all()]

                logger.debug(f"Queried {len(results)} audit logs")
                return results

        except Exception as e:
            logger.error(f"Failed to query audit logs: {str(e)}", exc_info=True)
            return []

    def get_audit_metrics(self) -> Dict[str, Any]:
        """
        Get audit log metrics for monitoring.

        Returns:
            Dictionary with audit log metrics
        """
        try:
            with self.get_session() as session:
                total_logs = session.query(AuditLogEntry).count()

                # Count by severity
                from sqlalchemy import func

                severity_counts = (
                    session.query(AuditLogEntry.severity, func.count(AuditLogEntry.id))
                    .group_by(AuditLogEntry.severity)
                    .all()
                )

                # Count by action type
                action_counts = (
                    session.query(AuditLogEntry.action, func.count(AuditLogEntry.id))
                    .group_by(AuditLogEntry.action)
                    .all()
                )

                metrics = {
                    "total_logs": total_logs,
                    "by_severity": {
                        k: int(v) for k, v in severity_counts if k is not None
                    },
                    "by_action": {k: int(v) for k, v in action_counts if k is not None},
                }

                return metrics

        except Exception as e:
            logger.error(f"Failed to get audit metrics: {str(e)}", exc_info=True)
            return {"total_logs": 0, "by_severity": {}, "by_action": {}}


# Global audit log manager instance
_audit_log_manager: Optional[AuditLogManager] = None


def get_audit_log_manager() -> AuditLogManager:
    """
    Get the global audit log manager instance.

    Returns:
        AuditLogManager instance
    """
    global _audit_log_manager
    if _audit_log_manager is None:
        _audit_log_manager = AuditLogManager()
    return _audit_log_manager
