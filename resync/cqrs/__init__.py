"""Compatibility package exposing CQRS query objects.

The original project split CQRS queries into a dedicated module imported by
FastAPI routes as well as several unit tests.  Only a subset of lightweight
query objects is required for the current refactor, so we re-export them here
to keep the public API stable for both application code and tests.
"""

from .queries import (
    CheckTWSConnectionQuery,
    GetCriticalPathStatusQuery,
    GetJobsStatusQuery,
    GetJobStatusBatchQuery,
    GetJobStatusQuery,
    GetPerformanceMetricsQuery,
    GetSystemHealthQuery,
    GetSystemStatusQuery,
    GetWorkstationsStatusQuery,
    SearchJobsQuery,
)

__all__ = [
    "CheckTWSConnectionQuery",
    "GetCriticalPathStatusQuery",
    "GetJobsStatusQuery",
    "GetJobStatusBatchQuery",
    "GetJobStatusQuery",
    "GetPerformanceMetricsQuery",
    "GetSystemHealthQuery",
    "GetSystemStatusQuery",
    "GetWorkstationsStatusQuery",
    "SearchJobsQuery",
]
