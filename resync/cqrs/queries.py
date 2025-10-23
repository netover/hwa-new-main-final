"""
Query implementations for TWS operations in the CQRS pattern.
"""

from dataclasses import dataclass
from typing import List

from resync.cqrs.base import IQuery


@dataclass
class GetSystemStatusQuery(IQuery):
    """
    Query to retrieve the overall TWS system status.
    """


@dataclass
class GetWorkstationsStatusQuery(IQuery):
    """
    Query to retrieve the status of all TWS workstations.
    """


@dataclass
class GetJobsStatusQuery(IQuery):
    """
    Query to retrieve the status of all TWS jobs.
    """


@dataclass
class GetCriticalPathStatusQuery(IQuery):
    """
    Query to retrieve the status of TWS critical path jobs.
    """


@dataclass
class GetJobStatusQuery(IQuery):
    """
    Query to retrieve the status of a specific TWS job.
    """

    job_id: str


@dataclass
class GetJobStatusBatchQuery(IQuery):
    """
    Query to retrieve the status of multiple TWS jobs in a batch.
    """

    job_ids: List[str]


@dataclass
class GetSystemHealthQuery(IQuery):
    """
    Query to retrieve system health metrics.
    """


@dataclass
class SearchJobsQuery(IQuery):
    """
    Query to search for jobs based on specific criteria.
    """

    search_term: str
    limit: int = 10


@dataclass
class GetPerformanceMetricsQuery(IQuery):
    """
    Query to retrieve system performance metrics.
    """


@dataclass
class CheckTWSConnectionQuery(IQuery):
    """
    Query to check the TWS connection status.
    """


@dataclass
class GetJobDetailsQuery(IQuery):
    """
    Query to retrieve detailed information about a specific TWS job.
    """

    job_id: str


@dataclass
class GetJobHistoryQuery(IQuery):
    """
    Query to retrieve the execution history for a specific TWS job.
    """

    job_name: str


@dataclass
class GetJobLogQuery(IQuery):
    """
    Query to retrieve the log content for a specific TWS job execution.
    """

    job_id: str


@dataclass
class GetPlanDetailsQuery(IQuery):
    """
    Query to retrieve details about the current TWS plan.
    """


@dataclass
class GetJobDependenciesQuery(IQuery):
    """
    Query to retrieve the dependency tree for a specific TWS job.
    """

    job_id: str


@dataclass
class GetResourceUsageQuery(IQuery):
    """
    Query to retrieve resource usage information.
    """


@dataclass
class GetEventLogQuery(IQuery):
    """
    Query to retrieve TWS event log entries.
    """

    last_hours: int = 24


@dataclass
class GetPerformanceMetricsQuery(IQuery):
    """
    Query to retrieve TWS performance metrics.
    """
