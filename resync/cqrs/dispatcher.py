"""Simplified CQRS dispatcher used by the FastAPI endpoints in tests."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Type

from . import queries as q


@dataclass(frozen=True, slots=True)
class QueryResult:
    success: bool
    data: Any
    error: str | None = None


class QueryDispatcher:
    """Dispatches query objects to lightweight handlers."""

    def __init__(self) -> None:
        self._handlers: Dict[Type[Any], Callable[[Any], Awaitable[Any] | Any]] = {
            q.GetWorkstationsStatusQuery: self._handle_workstations_status,
            q.GetJobsStatusQuery: self._handle_jobs_status,
            q.GetJobDetailsQuery: self._handle_job_details,
            q.GetJobHistoryQuery: self._handle_job_history,
            q.GetJobLogQuery: self._handle_job_log,
            q.GetPlanDetailsQuery: self._handle_plan_details,
            q.GetJobDependenciesQuery: self._handle_job_dependencies,
            q.GetResourceUsageQuery: self._handle_resource_usage,
            q.GetEventLogQuery: self._handle_event_log,
            q.GetPerformanceMetricsQuery: self._handle_performance_metrics,
            q.GetJobStatusBatchQuery: self._handle_job_status_batch,
            q.GetJobStatusQuery: self._handle_job_status_single,
            q.CheckTWSConnectionQuery: self._handle_connection_check,
        }

    async def execute_query(self, query: Any) -> QueryResult:
        handler = self._handlers.get(type(query))
        if handler is None:
            return QueryResult(
                success=True,
                data={"message": f"No handler registered for {type(query).__name__}"},
            )

        try:
            result = handler(query)
            if asyncio.iscoroutine(result):
                result = await result
            return QueryResult(success=True, data=result)
        except Exception as exc:  # pragma: no cover - defensive
            return QueryResult(success=False, data=None, error=str(exc))

    # ------------------------------------------------------------------
    @staticmethod
    def _handle_workstations_status(query: q.GetWorkstationsStatusQuery) -> list[dict[str, Any]]:
        return [
            {"name": "MASTER", "status": "online", "queue_depth": 3},
            {"name": "AGENT01", "status": "online", "queue_depth": 0},
        ]

    @staticmethod
    def _handle_jobs_status(query: q.GetJobsStatusQuery) -> list[dict[str, Any]]:
        return [
            {"job_id": "JOB001", "name": "Daily ETL", "status": "SUCC"},
            {"job_id": "JOB002", "name": "Data Cleanup", "status": "RUNNING"},
        ]

    @staticmethod
    def _handle_job_status_single(query: q.GetJobStatusQuery) -> dict[str, Any]:
        return {"job_id": query.job_id, "status": "SUCC", "workstation": "MASTER"}

    @staticmethod
    def _handle_job_status_batch(query: q.GetJobStatusBatchQuery) -> list[dict[str, Any]]:
        return [{"job_id": job_id, "status": "UNKNOWN"} for job_id in query.job_ids]

    @staticmethod
    def _handle_job_details(query: q.GetJobDetailsQuery) -> dict[str, Any]:
        return {
            "job_id": query.job_id,
            "description": "Synthetic job detail",
            "last_status": "SUCC",
            "last_run": "2024-01-01T00:00:00Z",
        }

    @staticmethod
    def _handle_job_history(query: q.GetJobHistoryQuery) -> list[dict[str, Any]]:
        return [
            {"run_id": f"{query.job_name}-001", "status": "SUCC"},
            {"run_id": f"{query.job_name}-002", "status": "SUCC"},
        ]

    @staticmethod
    def _handle_job_log(query: q.GetJobLogQuery) -> str:
        return f"Log output for job {query.job_id}"

    @staticmethod
    def _handle_plan_details(query: q.GetPlanDetailsQuery) -> dict[str, Any]:
        return {"plan_name": "DEFAULT", "version": "1.0.0", "status": "active"}

    @staticmethod
    def _handle_job_dependencies(query: q.GetJobDependenciesQuery) -> dict[str, Any]:
        return {
            "job_id": query.job_id,
            "upstream": [],
            "downstream": [],
        }

    @staticmethod
    def _handle_resource_usage(query: q.GetResourceUsageQuery) -> list[dict[str, Any]]:
        return [
            {"resource": "cpu", "usage": 42.5},
            {"resource": "memory", "usage": 68.2},
        ]

    @staticmethod
    def _handle_event_log(query: q.GetEventLogQuery) -> list[dict[str, Any]]:
        return [
            {
                "timestamp": "2024-01-01T00:00:00Z",
                "event": "JOB_STARTED",
                "details": {},
            }
        ]

    @staticmethod
    def _handle_performance_metrics(query: q.GetPerformanceMetricsQuery) -> dict[str, Any]:
        return {"throughput": 120, "latency_ms": 85}

    @staticmethod
    def _handle_connection_check(query: q.CheckTWSConnectionQuery) -> dict[str, Any]:
        return {"healthy": True}


dispatcher = QueryDispatcher()

__all__ = ["QueryDispatcher", "QueryResult", "dispatcher"]
