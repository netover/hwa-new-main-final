
"""
System status routes for FastAPI
"""
from fastapi import APIRouter, Depends
from ..models.response_models import SystemStatusResponse
from ..dependencies import get_logger

router = APIRouter()

@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(
    # Temporarily disabled authentication for testing
    # current_user: dict = Depends(get_current_user),
    logger_instance = Depends(get_logger)
):
    """Get system status including workstations and jobs"""
    try:
        # TODO: Implement actual status retrieval from database/Redis
        # This is a placeholder implementation
        workstations = []
        jobs = []

        logger_instance.info(
            "system_status_retrieved",
            # Temporarily using placeholder for user_id since auth is disabled
            user_id="test_user",
            workstation_count=len(workstations),
            job_count=len(jobs)
        )

        return SystemStatusResponse(
            workstations=workstations,
            jobs=jobs,
            timestamp="2025-01-01T00:00:00Z"  # TODO: Use proper datetime
        )

    except Exception as e:
        logger_instance.error("system_status_retrieval_error", error=str(e))
        # Return empty status on error
        return SystemStatusResponse(
            workstations=[],
            jobs=[],
            timestamp="2025-01-01T00:00:00Z"
        )

# Note: Agent listing moved to agents router
