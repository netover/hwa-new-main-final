# resync/api/audit.py
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
from pydantic import field_validator, BaseModel

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from resync.core.fastapi_di import get_audit_queue, get_knowledge_graph
from resync.core.interfaces import IAuditQueue, IKnowledgeGraph
from resync.core.logger import log_audit_event

# Module-level dependencies to avoid B008 errors
audit_queue_dependency = Depends(get_audit_queue)
knowledge_graph_dependency = Depends(get_knowledge_graph)

router = APIRouter(prefix="/api/audit", tags=["audit"])


class AuditRecordResponse(BaseModel):
    """Pydantic model for audit record responses"""

    id: str
    user_query: str
    agent_response: str
    status: str
    timestamp: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


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


@router.get("/flags", response_model=List[AuditRecordResponse])
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
) -> List[AuditRecordResponse]:
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

        # Convert dictionaries to AuditRecordResponse models
        return [AuditRecordResponse(**memory) for memory in memories]
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

            await knowledge_graph.client.add_observations(
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

            await knowledge_graph.client.delete(review.memory_id)

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
