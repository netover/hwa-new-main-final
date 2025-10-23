"""
Command handlers for TWS operations in the CQRS pattern.
"""

from resync.core.interfaces import ITWSClient
from resync.cqrs.base import CommandResult, ICommandHandler
from resync.cqrs.commands import (
    ExecuteJobCommand,
    GetCriticalPathStatusCommand,
    GetJobsStatusCommand,
    GetJobStatusBatchCommand,
    GetSystemHealthCommand,
    GetSystemStatusCommand,
    GetWorkstationsStatusCommand,
    UpdateJobStatusCommand,
)


class GetSystemStatusCommandHandler(
    ICommandHandler[GetSystemStatusCommand, CommandResult]
):
    """Handler for getting the overall system status."""

    def __init__(self, tws_client: ITWSClient):
        self.tws_client = tws_client

    async def execute(self, command: GetSystemStatusCommand) -> CommandResult:
        try:
            system_status = await self.tws_client.get_system_status()
            return CommandResult(
                success=True,
                data=system_status.dict(),
                message="System status retrieved successfully",
            )
        except Exception as e:
            return CommandResult(
                success=False, error=str(e), message="Failed to retrieve system status"
            )


class GetWorkstationsStatusCommandHandler(
    ICommandHandler[GetWorkstationsStatusCommand, CommandResult]
):
    """Handler for getting workstation statuses."""

    def __init__(self, tws_client: ITWSClient):
        self.tws_client = tws_client

    async def execute(self, command: GetWorkstationsStatusCommand) -> CommandResult:
        try:
            workstations = await self.tws_client.get_workstations_status()
            return CommandResult(
                success=True,
                data=[ws.dict() for ws in workstations],
                message="Workstation statuses retrieved successfully",
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=str(e),
                message="Failed to retrieve workstation statuses",
            )


class GetJobsStatusCommandHandler(ICommandHandler[GetJobsStatusCommand, CommandResult]):
    """Handler for getting job statuses."""

    def __init__(self, tws_client: ITWSClient):
        self.tws_client = tws_client

    async def execute(self, command: GetJobsStatusCommand) -> CommandResult:
        try:
            jobs = await self.tws_client.get_jobs_status()
            return CommandResult(
                success=True,
                data=[job.dict() for job in jobs],
                message="Job statuses retrieved successfully",
            )
        except Exception as e:
            return CommandResult(
                success=False, error=str(e), message="Failed to retrieve job statuses"
            )


class GetCriticalPathStatusCommandHandler(
    ICommandHandler[GetCriticalPathStatusCommand, CommandResult]
):
    """Handler for getting critical path statuses."""

    def __init__(self, tws_client: ITWSClient):
        self.tws_client = tws_client

    async def execute(self, command: GetCriticalPathStatusCommand) -> CommandResult:
        try:
            critical_jobs = await self.tws_client.get_critical_path_status()
            return CommandResult(
                success=True,
                data=[cj.dict() for cj in critical_jobs],
                message="Critical path statuses retrieved successfully",
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=str(e),
                message="Failed to retrieve critical path statuses",
            )


class GetJobStatusBatchCommandHandler(
    ICommandHandler[GetJobStatusBatchCommand, CommandResult]
):
    """Handler for getting batch job statuses."""

    def __init__(self, tws_client: ITWSClient):
        self.tws_client = tws_client

    async def execute(self, command: GetJobStatusBatchCommand) -> CommandResult:
        try:
            jobs_status = await self.tws_client.get_job_status_batch(command.job_ids)
            return CommandResult(
                success=True,
                data={k: v.dict() if v else None for k, v in jobs_status.items()},
                message="Batch job statuses retrieved successfully",
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=str(e),
                message="Failed to retrieve batch job statuses",
            )


class UpdateJobStatusCommandHandler(
    ICommandHandler[UpdateJobStatusCommand, CommandResult]
):
    """Handler for updating job status (placeholder implementation)."""

    def __init__(self, tws_client: ITWSClient):
        self.tws_client = tws_client

    async def execute(self, command: UpdateJobStatusCommand) -> CommandResult:
        # In a real implementation, this would update the job status in TWS
        # For now, we're just simulating the operation
        try:
            # Placeholder: In a real implementation, call TWS API to update job status
            return CommandResult(
                success=True,
                message=f"Status of job {command.job_id} updated to {command.new_status}",
                data={"job_id": command.job_id, "new_status": command.new_status},
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=str(e),
                message=f"Failed to update status for job {command.job_id}",
            )


class ExecuteJobCommandHandler(ICommandHandler[ExecuteJobCommand, CommandResult]):
    """Handler for executing a job."""

    def __init__(self, tws_client: ITWSClient):
        self.tws_client = tws_client

    async def execute(self, command: ExecuteJobCommand) -> CommandResult:
        # In a real implementation, this would execute the job in TWS
        try:
            # Placeholder: In a real implementation, call TWS API to execute job
            return CommandResult(
                success=True,
                message=f"Job {command.job_id} executed successfully",
                data={"job_id": command.job_id},
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=str(e),
                message=f"Failed to execute job {command.job_id}",
            )


class GetSystemHealthCommandHandler(
    ICommandHandler[GetSystemHealthCommand, CommandResult]
):
    """Handler for getting system health."""

    def __init__(self, tws_client: ITWSClient, tws_monitor: any):
        self.tws_client = tws_client
        self.tws_monitor = tws_monitor

    async def execute(self, command: GetSystemHealthCommand) -> CommandResult:
        try:
            health_report = self.tws_monitor.get_performance_report()
            return CommandResult(
                success=True,
                data=health_report,
                message="System health retrieved successfully",
            )
        except Exception as e:
            return CommandResult(
                success=False, error=str(e), message="Failed to retrieve system health"
            )
