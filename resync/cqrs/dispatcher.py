"""
CQRS dispatcher for routing commands and queries to their respective handlers.
"""

from typing import Dict, Type

from resync.cqrs.base import (
    CommandResult,
    ICommand,
    ICommandHandler,
    IQuery,
    IQueryHandler,
    QueryResult,
)
from resync.cqrs.command_handlers import (
    ExecuteJobCommandHandler,
    GetCriticalPathStatusCommandHandler,
    GetJobsStatusCommandHandler,
    GetJobStatusBatchCommandHandler,
    GetSystemHealthCommandHandler,
    GetSystemStatusCommandHandler,
    GetWorkstationsStatusCommandHandler,
    UpdateJobStatusCommandHandler,
)
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
from resync.cqrs.queries import (
    CheckTWSConnectionQuery,
    GetCriticalPathStatusQuery,
    GetEventLogQuery,
    GetJobDependenciesQuery,
    GetJobDetailsQuery,
    GetJobHistoryQuery,
    GetJobLogQuery,
    GetJobsStatusQuery,
    GetJobStatusBatchQuery,
    GetJobStatusQuery,
    GetPerformanceMetricsQuery,
    GetPlanDetailsQuery,
    GetResourceUsageQuery,
    GetSystemHealthQuery,
    GetSystemStatusQuery,
    GetWorkstationsStatusQuery,
    SearchJobsQuery,
)
from resync.cqrs.query_handlers import (
    CheckTWSConnectionQueryHandler,
    GetCriticalPathStatusQueryHandler,
    GetEventLogQueryHandler,
    GetJobDependenciesQueryHandler,
    GetJobDetailsQueryHandler,
    GetJobHistoryQueryHandler,
    GetJobLogQueryHandler,
    GetJobsStatusQueryHandler,
    GetJobStatusBatchQueryHandler,
    GetJobStatusQueryHandler,
    GetPerformanceMetricsQueryHandler,
    GetPlanDetailsQueryHandler,
    GetResourceUsageQueryHandler,
    GetSystemHealthQueryHandler,
    GetSystemStatusQueryHandler,
    GetWorkstationsStatusQueryHandler,
    SearchJobsQueryHandler,
)


class CQRSDispatcher:
    """
    Central dispatcher for CQRS commands and queries.
    Routes commands/queries to their appropriate handlers.
    """

    def __init__(self):
        self.command_handlers: Dict[Type[ICommand], ICommandHandler] = {}
        self.query_handlers: Dict[Type[IQuery], IQueryHandler] = {}

    def register_command_handler(
        self, command_type: Type[ICommand], handler: ICommandHandler
    ):
        """Register a command handler for a specific command type."""
        self.command_handlers[command_type] = handler

    def register_query_handler(self, query_type: Type[IQuery], handler: IQueryHandler):
        """Register a query handler for a specific query type."""
        self.query_handlers[query_type] = handler

    async def execute_command(self, command: ICommand) -> CommandResult:
        """Execute a command by routing it to the appropriate handler."""
        command_type = type(command)
        if command_type not in self.command_handlers:
            raise ValueError(f"No handler registered for command type: {command_type}")

        handler = self.command_handlers[command_type]
        return await handler.execute(command)

    async def execute_query(self, query: IQuery) -> QueryResult:
        """Execute a query by routing it to the appropriate handler."""
        query_type = type(query)
        if query_type not in self.query_handlers:
            raise ValueError(f"No handler registered for query type: {query_type}")

        handler = self.query_handlers[query_type]
        return await handler.execute(query)


# Global dispatcher instance
dispatcher = CQRSDispatcher()


def initialize_dispatcher(tws_client, tws_monitor):
    """
    Initialize the CQRS dispatcher with all necessary handlers.

    Args:
        tws_client: The TWS client instance
        tws_monitor: The TWS monitor instance
    """
    # Register command handlers
    dispatcher.register_command_handler(
        GetSystemStatusCommand, GetSystemStatusCommandHandler(tws_client)
    )
    dispatcher.register_command_handler(
        GetWorkstationsStatusCommand, GetWorkstationsStatusCommandHandler(tws_client)
    )
    dispatcher.register_command_handler(
        GetJobsStatusCommand, GetJobsStatusCommandHandler(tws_client)
    )
    dispatcher.register_command_handler(
        GetCriticalPathStatusCommand, GetCriticalPathStatusCommandHandler(tws_client)
    )
    dispatcher.register_command_handler(
        GetJobStatusBatchCommand, GetJobStatusBatchCommandHandler(tws_client)
    )
    dispatcher.register_command_handler(
        UpdateJobStatusCommand, UpdateJobStatusCommandHandler(tws_client)
    )
    dispatcher.register_command_handler(
        ExecuteJobCommand, ExecuteJobCommandHandler(tws_client)
    )
    dispatcher.register_command_handler(
        GetSystemHealthCommand, GetSystemHealthCommandHandler(tws_client, tws_monitor)
    )

    # Register query handlers
    dispatcher.register_query_handler(
        GetSystemStatusQuery, GetSystemStatusQueryHandler(tws_client)
    )
    dispatcher.register_query_handler(
        GetWorkstationsStatusQuery, GetWorkstationsStatusQueryHandler(tws_client)
    )
    dispatcher.register_query_handler(
        GetJobsStatusQuery, GetJobsStatusQueryHandler(tws_client)
    )
    dispatcher.register_query_handler(
        GetCriticalPathStatusQuery, GetCriticalPathStatusQueryHandler(tws_client)
    )
    dispatcher.register_query_handler(
        GetJobStatusQuery, GetJobStatusQueryHandler(tws_client)
    )
    dispatcher.register_query_handler(
        GetJobStatusBatchQuery, GetJobStatusBatchQueryHandler(tws_client)
    )
    dispatcher.register_query_handler(
        GetSystemHealthQuery, GetSystemHealthQueryHandler(tws_monitor)
    )
    dispatcher.register_query_handler(
        SearchJobsQuery, SearchJobsQueryHandler(tws_client)
    )
    dispatcher.register_query_handler(
        GetPerformanceMetricsQuery, GetPerformanceMetricsQueryHandler(tws_monitor)
    )
    dispatcher.register_query_handler(
        CheckTWSConnectionQuery, CheckTWSConnectionQueryHandler(tws_client)
    )

    # Register new query handlers
    dispatcher.register_query_handler(
        GetJobDetailsQuery, GetJobDetailsQueryHandler(tws_client)
    )
    dispatcher.register_query_handler(
        GetJobHistoryQuery, GetJobHistoryQueryHandler(tws_client)
    )
    dispatcher.register_query_handler(GetJobLogQuery, GetJobLogQueryHandler(tws_client))
    dispatcher.register_query_handler(
        GetPlanDetailsQuery, GetPlanDetailsQueryHandler(tws_client)
    )
    dispatcher.register_query_handler(
        GetJobDependenciesQuery, GetJobDependenciesQueryHandler(tws_client)
    )
    dispatcher.register_query_handler(
        GetResourceUsageQuery, GetResourceUsageQueryHandler(tws_client)
    )
    dispatcher.register_query_handler(
        GetEventLogQuery, GetEventLogQueryHandler(tws_client)
    )
