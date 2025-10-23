"""Audit logging API endpoints.

This module provides REST API endpoints for audit logging functionality,
including retrieving audit logs, audit statistics, and audit queue management.
It handles audit data retrieval with proper pagination, filtering, and access control.
"""

# resync/api/audit.py
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator

from resync.api.dependencies import get_idempotency_manager, require_idempotency_key
from resync.core.fastapi_di import get_audit_queue, get_knowledge_graph
from resync.core.idempotency.manager import IdempotencyManager
from resync.core.interfaces import IAuditQueue, IKnowledgeGraph
from resync.core.logger import log_audit_event

# Module-level dependencies to avoid B008 errors
audit_queue_dependency = Depends(get_audit_queue)
knowledge_graph_dependency = Depends(get_knowledge_graph)

router = APIRouter(prefix="/api/audit", tags=["audit"])


class AuditAction(str, Enum):
    """Enum for different audit actions."""

    LOGIN = "login"
    LOGOUT = "logout"
    API_ACCESS = "api_access"
    CONFIG_CHANGE = "config_change"
    DATA_ACCESS = "data_access"
    CACHE_INVALIDATION = "cache_invalidation"
    LLM_QUERY = "llm_query"
    CORS_VIOLATION = "cors_violation"


class AuditRecordResponse(BaseModel):
    """Response model for audit records."""

    id: str = Field(..., description="Unique audit record ID")
    timestamp: str = Field(..., description="ISO format timestamp of the audit event")
    user_id: str = Field(..., description="ID of the user performing the action")
    action: AuditAction = Field(..., description="Type of action being audited")
    details: Dict[str, Any] = Field(
        ..., description="Additional details about the action"
    )
    correlation_id: Optional[str] = Field(
        None, description="Correlation ID for tracking requests"
    )
    ip_address: Optional[str] = Field(None, description="IP address of the requester")
    user_agent: Optional[str] = Field(
        None, description="User agent string of the requester"
    )


def generate_audit_log(
    user_id: str,
    action: AuditAction,
    details: Dict[str, Any],
    correlation_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditRecordResponse:
    """
    Generate an audit log entry with proper structure.

    Args:
        user_id: ID of the user performing the action
        action: Type of action being audited
        details: Additional details about the action
        correlation_id: Correlation ID for tracking requests
        ip_address: IP address of the requester
        user_agent: User agent string of the requester

    Returns:
        AuditRecordResponse with the audit information
    """
    timestamp = datetime.utcnow().isoformat()
    audit_id = f"audit_{timestamp}_{user_id[:8]}_{action}"

    # Create the audit record
    audit_record = AuditRecordResponse(
        id=audit_id,
        timestamp=timestamp,
        user_id=user_id,
        action=action,
        details=details,
        correlation_id=correlation_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    # Log the audit event using structlog
    log_audit_event(
        action=action,
        user_id=user_id,
        details=details,
        correlation_id=correlation_id,
        severity="INFO",
    )

    return audit_record


class ReviewAction(BaseModel):
    memory_id: str
    action: str  # "approve" or "reject"

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        """
        Validate the review action.

        Args:
            v: The action to validate

        Returns:
            The validated action
        """
        valid_actions = {"approve", "reject"}
        if v.lower() not in valid_actions:
            raise ValueError(f"Invalid action: {v}. Must be one of {valid_actions}")
        return v.lower()


@router.get("/flags", response_model=List[Dict[str, Any]])
def get_flagged_memories(
    request: Request,
    status: str = Query(
        "pending",
        description="Filter by audit status (pending, approved, rejected, all)",
    ),
    query: Optional[str] = Query(
        None,
        description="Search query in user_query or agent_response",
    ),
    audit_queue: IAuditQueue = audit_queue_dependency,
) -> List[Dict[str, Any]]:
    """
    Retrieves memories from the audit queue based on status and search query.
    """
    # Get the current user from request state
    user_id = (
        getattr(request.state, "user_id", "system")
        if hasattr(request.state, "user_id")
        else "system"
    )
    correlation_id = (
        getattr(request.state, "correlation_id", None)
        if hasattr(request.state, "correlation_id")
        else None
    )

    try:
        if status == "all":
            memories = audit_queue.get_all_audits_sync()
        else:
            memories = audit_queue.get_audits_by_status_sync(status)

        if query:
            # Filter in Python for now, can be pushed to DB later
            query_lower = query.lower()
            memories = [
                m
                for m in memories
                if query_lower in m.get("user_query", "").lower()
                or query_lower in m.get("agent_response", "").lower()
            ]

        # Log the audit event for successful retrieval
        log_audit_event(
            action="retrieve_flagged_memories",
            user_id=user_id,
            details={
                "status_filter": status,
                "query_present": query is not None,
                "result_count": len(memories),
            },
            correlation_id=correlation_id,
        )

        return memories
    except Exception as e:
        log_audit_event(
            action="retrieve_flagged_memories_error",
            user_id=user_id,
            details={"status_filter": status, "error": str(e)},
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=500, detail=f"Error retrieving flagged memories: {e}"
        ) from e


@router.post("/review")
async def review_memory(
    request: Request,
    review: ReviewAction,
    audit_queue: IAuditQueue = audit_queue_dependency,
    knowledge_graph: IKnowledgeGraph = knowledge_graph_dependency,
) -> Dict[str, str]:
    """
    Processes a human review action for a flagged memory, updating its status in the database.
    """
    # Get the current user from request state (this would need to come from auth)
    # For now, using a placeholder - in production, this should come from auth
    user_id = (
        getattr(request.state, "user_id", "system")
        if hasattr(request.state, "user_id")
        else "system"
    )
    correlation_id = (
        getattr(request.state, "correlation_id", None)
        if hasattr(request.state, "correlation_id")
        else None
    )

    if review.action == "approve":
        try:
            if not audit_queue.update_audit_status_sync(review.memory_id, "approved"):
                log_audit_event(
                    action="review_attempt_failed",
                    user_id=user_id,
                    details={
                        "memory_id": review.memory_id,
                        "attempted_action": "approve",
                        "reason": "not_found",
                    },
                    correlation_id=correlation_id,
                )
                raise HTTPException(status_code=404, detail="Audit record not found.")

            await knowledge_graph.add_observations(
                review.memory_id, ["MANUALLY_APPROVED_BY_ADMIN"]
            )

            # Log the successful audit event
            log_audit_event(
                action="memory_approved",
                user_id=user_id,
                details={"memory_id": review.memory_id},
                correlation_id=correlation_id,
            )

            return {"status": "approved", "memory_id": review.memory_id}
        except Exception as e:
            log_audit_event(
                action="approval_error",
                user_id=user_id,
                details={"memory_id": review.memory_id, "error": str(e)},
                correlation_id=correlation_id,
            )
            raise HTTPException(
                status_code=500, detail=f"Error approving memory: {e}"
            ) from e

    elif review.action == "reject":
        try:
            if not audit_queue.update_audit_status_sync(review.memory_id, "rejected"):
                log_audit_event(
                    action="review_attempt_failed",
                    user_id=user_id,
                    details={
                        "memory_id": review.memory_id,
                        "attempted_action": "reject",
                        "reason": "not_found",
                    },
                    correlation_id=correlation_id,
                )
                raise HTTPException(status_code=404, detail="Audit record not found.")

            await knowledge_graph.delete_memory(review.memory_id)

            # Log the successful audit event
            log_audit_event(
                action="memory_rejected",
                user_id=user_id,
                details={"memory_id": review.memory_id},
                correlation_id=correlation_id,
            )

            return {"status": "rejected", "memory_id": review.memory_id}
        except Exception as e:
            log_audit_event(
                action="rejection_error",
                user_id=user_id,
                details={"memory_id": review.memory_id, "error": str(e)},
                correlation_id=correlation_id,
            )
            raise HTTPException(
                status_code=500, detail=f"Error rejecting memory: {e}"
            ) from e

    raise HTTPException(status_code=400, detail="Invalid action")


@router.get("/metrics", response_model=Dict[str, int])  # New endpoint for metrics
def get_audit_metrics(
    request: Request,
    audit_queue: IAuditQueue = audit_queue_dependency,
) -> Dict[str, int]:
    """
    Returns metrics for the audit queue (total pending, approved, rejected).
    """
    # Get the current user from request state
    user_id = (
        getattr(request.state, "user_id", "system")
        if hasattr(request.state, "user_id")
        else "system"
    )
    correlation_id = (
        getattr(request.state, "correlation_id", None)
        if hasattr(request.state, "correlation_id")
        else None
    )

    try:
        metrics = audit_queue.get_audit_metrics_sync()

        # Log the audit event for successful metrics retrieval
        log_audit_event(
            action="retrieve_audit_metrics",
            user_id=user_id,
            details=metrics,
            correlation_id=correlation_id,
        )

        return metrics
    except Exception as e:
        log_audit_event(
            action="retrieve_audit_metrics_error",
            user_id=user_id,
            details={"error": str(e)},
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=500, detail=f"Error retrieving audit metrics: {e}"
        ) from e


# Additional audit endpoints for enhanced functionality
@router.get("/logs", response_model=List[AuditRecordResponse])
def get_audit_logs(
    request: Request,
    limit: int = Query(100, description="Maximum number of logs to return"),
    offset: int = Query(0, description="Offset for pagination"),
    action: Optional[AuditAction] = Query(None, description="Filter by action type"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
) -> List[AuditRecordResponse]:
    """
    Retrieves audit logs with optional filtering and pagination.
    """
    # Get the current user from request state
    current_user_id = (
        getattr(request.state, "user_id", "system")
        if hasattr(request.state, "user_id")
        else "system"
    )
    correlation_id = (
        getattr(request.state, "correlation_id", None)
        if hasattr(request.state, "correlation_id")
        else None
    )

    try:
        # For now, we'll just log that this endpoint was accessed
        # In a real implementation, this would fetch audit logs from the database
        details = {
            "limit": limit,
            "offset": offset,
            "action_filter": action,
            "user_id_filter": user_id,
        }
        log_audit_event(
            action="retrieve_audit_logs",
            user_id=current_user_id,
            details=details,
            correlation_id=correlation_id,
        )

        # This would normally return actual audit logs from the database
        # For now, return an empty list as a placeholder
        return []
    except Exception as e:
        log_audit_event(
            action="retrieve_audit_logs_error",
            user_id=current_user_id,
            details={"error": str(e)},
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=500, detail=f"Error retrieving audit logs: {e}"
        ) from e


@router.post("/log", response_model=AuditRecordResponse)
async def create_audit_log(
    request: Request,
    audit_data: AuditRecordResponse,
    idempotency_key: str = Depends(require_idempotency_key),
    manager: IdempotencyManager = Depends(get_idempotency_manager),
) -> AuditRecordResponse:
    """
    Create a new audit log entry with idempotency support.

    This endpoint requires an X-Idempotency-Key header to prevent duplicate
    audit log entries. The same key will return the same result.

    Args:
        request: FastAPI request object
        audit_data: Audit record data
        idempotency_key: Unique key for idempotent operation
        manager: Idempotency manager instance

    Returns:
        Created audit record

    Raises:
        ValidationError: If idempotency key is invalid
        ResourceConflictError: If operation is already in progress
    """
    # Get the current user from request state
    current_user_id = (
        getattr(request.state, "user_id", "system")
        if hasattr(request.state, "user_id")
        else "system"
    )
    correlation_id = (
        getattr(request.state, "correlation_id", None)
        if hasattr(request.state, "correlation_id")
        else None
    )

    async def _create_audit_log() -> AuditRecordResponse:
        """Internal function to create audit log."""
        try:
            # Log the audit event
            log_audit_event(
                action="create_audit_log",
                user_id=current_user_id,
                details={
                    "target_user_id": audit_data.user_id,
                    "target_action": audit_data.action,
                    "target_details": audit_data.details,
                    "idempotency_key": idempotency_key,
                },
                correlation_id=correlation_id,
            )

            # In a real implementation, we would store this in the audit database
            # For now, we'll just return the data that was provided
            return audit_data
        except Exception as e:
            log_audit_event(
                action="create_audit_log_error",
                user_id=current_user_id,
                details={"error": str(e), "idempotency_key": idempotency_key},
                correlation_id=correlation_id,
            )
            raise HTTPException(
                status_code=500, detail=f"Error creating audit log: {e}"
            ) from e

    # Execute with idempotency
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency key is required")

    return await manager.execute_idempotent(
        key=idempotency_key,
        func=_create_audit_log,
        ttl_seconds=3600,  # 1 hour TTL for audit logs
    )


class AuditLogger:
    """Basic audit logger implementation."""

    def __init__(self):
        self.records = []

    def log_action(self, action: AuditAction, details: dict = None):
        """Log an audit action."""
        record = {
            "action": action,
            "details": details or {},
            "timestamp": "now"
        }
        self.records.append(record)
        return record

    def generate_audit_log(self, user_id: str, action: AuditAction, details: dict = None):
        """Generate an audit log entry."""
        import uuid
        record = AuditRecordResponse(
            id=str(uuid.uuid4()),
            user_id=user_id,
            action=action,
            details=details or {},
            timestamp="now"
        )
        self.records.append(record)
        return record

    def get_records(self):
        """Get all audit records."""
        return self.records