from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from resync.core.rate_limiter import authenticated_rate_limit

logger = logging.getLogger(__name__)

# Module-level dependency to avoid B008 error for Query
origins_query_dependency = Query(..., description="List of origins to validate")

cors_monitor_router = APIRouter()


class CORSStats(BaseModel):
    """CORS middleware statistics."""

    total_requests: int
    preflight_requests: int
    violations: int
    violation_rate: float
    last_updated: datetime


class CORSViolation(BaseModel):
    """CORS violation details."""

    timestamp: datetime
    origin: str
    method: str
    path: str
    preflight: bool
    remote_ip: str
    user_agent: str
    referrer: str


class CORSConfigResponse(BaseModel):
    """CORS configuration response."""

    environment: str
    enabled: bool
    allow_all_origins: bool
    allowed_origins: List[str]
    allowed_methods: List[str]
    allowed_headers: List[str]
    allow_credentials: bool
    max_age: int
    log_violations: bool


class CORSPolicyTestRequest(BaseModel):
    """Request model for CORS policy testing"""

    origin: str
    method: str = "GET"
    path: str = "/api/test"


class CORSPolicyTestResponse(BaseModel):
    """Response model for CORS policy testing"""

    origin: str
    method: str
    path: str
    environment: str
    origin_allowed: bool
    method_allowed: bool
    overall_allowed: bool
    policy_details: Dict[str, Any]


@cors_monitor_router.get("/cors/stats", response_model=CORSStats)
@authenticated_rate_limit
async def get_cors_stats(request: Request) -> CORSStats:
    """
    Get CORS middleware statistics for monitoring.

    Returns:
        CORS statistics including request counts and violation rates
    """
    # Get the CORS middleware from the app (this would need to be accessible)
    # For now, return mock data - in a real implementation, we'd access the middleware stats
    return CORSStats(
        total_requests=0,
        preflight_requests=0,
        violations=0,
        violation_rate=0.0,
        last_updated=datetime.now(),
    )


@cors_monitor_router.get("/cors/violations")
@authenticated_rate_limit
async def get_cors_violations(
    request: Request,
    limit: int = Query(
        default=50, ge=1, le=500, description="Maximum number of violations to return"
    ),
    hours: int = Query(
        default=24, ge=1, le=168, description="Number of hours to look back"
    ),
) -> List[CORSViolation]:
    """
    Get recent CORS violations for security analysis.

    Args:
        limit: Maximum number of violations to return
        hours: Number of hours to look back for violations

    Returns:
        List of CORS violations with details
    """
    # This would need to be implemented with actual violation logging
    # For now, return empty list
    return []


@cors_monitor_router.get("/cors/config", response_model=CORSConfigResponse)
@authenticated_rate_limit
async def get_cors_config(request: Request) -> CORSConfigResponse:
    """
    Get current CORS configuration for verification.

    Returns:
        Current CORS configuration settings
    """
    from resync.api.middleware.cors_config import cors_config
    from resync.settings import settings

    # Get current environment
    environment = getattr(settings, "CORS_ENVIRONMENT", "development")
    policy = cors_config.get_policy(environment)

    return CORSConfigResponse(
        environment=environment,
        enabled=getattr(settings, "CORS_ENABLED", True),
        allow_all_origins=policy.allow_all_origins,
        allowed_origins=policy.allowed_origins,
        allowed_methods=policy.allowed_methods,
        allowed_headers=policy.allowed_headers,
        allow_credentials=policy.allow_credentials,
        max_age=policy.max_age,
        log_violations=policy.log_violations,
    )


@cors_monitor_router.post("/cors/test")
@authenticated_rate_limit
async def test_cors_policy(
    request: Request, test_request: CORSPolicyTestRequest
) -> CORSPolicyTestResponse:
    """
    Test CORS policy for a specific origin and method.

    Args:
        test_request: Request with origin, method, and path to test

    Returns:
        Test results including whether the origin would be allowed
    """
    from resync.api.middleware.cors_config import cors_config
    from resync.settings import settings

    # Get current environment and policy
    environment = getattr(settings, "CORS_ENVIRONMENT", "development")
    policy = cors_config.get_policy(environment)

    # Test if origin would be allowed
    is_allowed = policy.is_origin_allowed(test_request.origin)

    # Check if method is allowed
    is_method_allowed = test_request.method.upper() in [
        m.upper() for m in policy.allowed_methods
    ]

    return CORSPolicyTestResponse(
        origin=test_request.origin,
        method=test_request.method,
        path=test_request.path,
        environment=environment,
        origin_allowed=is_allowed,
        method_allowed=is_method_allowed,
        overall_allowed=is_allowed and is_method_allowed,
        policy_details={
            "allow_all_origins": policy.allow_all_origins,
            "allowed_origins_count": len(policy.allowed_origins),
            "allowed_methods": policy.allowed_methods,
            "allow_credentials": policy.allow_credentials,
            "log_violations": policy.log_violations,
        },
    )


@cors_monitor_router.post("/cors/validate-origins")
@authenticated_rate_limit
async def validate_origins(
    request: Request,
    origins: List[str] = Query(..., description="List of origins to validate"),
) -> Dict[str, Any]:
    """
    Validate a list of origins against the current CORS policy.

    Args:
        origins: List of origins to validate

    Returns:
        Validation results for each origin
    """
    from resync.api.middleware.cors_config import cors_config
    from resync.settings import settings

    # Get current environment and policy
    environment = getattr(settings, "CORS_ENVIRONMENT", "development")
    policy = cors_config.get_policy(environment)

    results = {}
    for origin in origins:
        is_allowed = policy.is_origin_allowed(origin)
        validation_errors = []

        # Perform additional validation
        if environment == "production" and "*" in origin:
            validation_errors.append("Wildcard origins not allowed in production")

        results[origin] = {
            "allowed": is_allowed,
            "validation_errors": validation_errors,
            "policy_match": origin in policy.allowed_origins
            or policy.allow_all_origins,
        }

    return {
        "environment": environment,
        "total_origins": len(origins),
        "allowed_count": sum(1 for r in results.values() if r["allowed"]),
        "results": results,
    }
