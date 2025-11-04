"""Lightweight CQRS query objects used by the API and tests.

These dataclasses mirror the legacy project surface area while keeping the
implementation intentionally minimal.  They provide value semantics,
human-readable ``repr`` output, and no behavioural side effects so they can be
freely instantiated inside unit tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True, slots=True)
class GetSystemStatusQuery:
    """Retrieve overall TWS system status."""


@dataclass(frozen=True, slots=True)
class GetWorkstationsStatusQuery:
    """Retrieve status information for all TWS workstations."""


@dataclass(frozen=True, slots=True)
class GetJobsStatusQuery:
    """Retrieve status information for jobs."""


@dataclass(frozen=True, slots=True)
class GetCriticalPathStatusQuery:
    """Retrieve the status of the critical job path."""


@dataclass(frozen=True, slots=True)
class GetJobStatusQuery:
    """Retrieve status information for a single job."""

    job_id: str


@dataclass(frozen=True, slots=True)
class GetSystemHealthQuery:
    """Retrieve aggregated health metrics for the platform."""


@dataclass(frozen=True, slots=True)
class SearchJobsQuery:
    """Search jobs by name or metadata."""

    search_term: str
    limit: int = 10


@dataclass(frozen=True, slots=True)
class GetPerformanceMetricsQuery:
    """Retrieve performance metrics."""


@dataclass(frozen=True, slots=True)
class CheckTWSConnectionQuery:
    """Verify the TWS connection health."""


@dataclass(frozen=True, slots=True)
class GetJobStatusBatchQuery:
    """Retrieve status information for a collection of jobs."""

    job_ids: List[str]


@dataclass(frozen=True, slots=True)
class GetJobDetailsQuery:
    """Retrieve detailed information about a single job."""

    job_id: str


@dataclass(frozen=True, slots=True)
class GetJobHistoryQuery:
    """Retrieve execution history for a job name."""

    job_name: str


@dataclass(frozen=True, slots=True)
class GetJobLogQuery:
    """Retrieve log output for a particular job execution."""

    job_id: str


@dataclass(frozen=True, slots=True)
class GetJobDependenciesQuery:
    """Retrieve upstream/downstream dependencies for a job."""

    job_id: str


@dataclass(frozen=True, slots=True)
class GetPlanDetailsQuery:
    """Retrieve details about the active TWS plan."""


@dataclass(frozen=True, slots=True)
class GetResourceUsageQuery:
    """Retrieve aggregated resource usage across TWS."""


@dataclass(frozen=True, slots=True)
class GetEventLogQuery:
    """Retrieve recent events from the TWS log."""

    last_hours: int = 24


__all__ = [
    "CheckTWSConnectionQuery",
    "GetCriticalPathStatusQuery",
    "GetJobsStatusQuery",
    "GetJobDetailsQuery",
    "GetJobStatusBatchQuery",
    "GetJobStatusQuery",
    "GetJobHistoryQuery",
    "GetJobLogQuery",
    "GetPerformanceMetricsQuery",
    "GetPlanDetailsQuery",
    "GetSystemHealthQuery",
    "GetSystemStatusQuery",
    "GetWorkstationsStatusQuery",
    "GetJobDependenciesQuery",
    "GetResourceUsageQuery",
    "GetEventLogQuery",
    "SearchJobsQuery",
]
