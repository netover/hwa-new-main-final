"""
CQRS Command and Query Infrastructure for Resync

This module provides the foundational classes for implementing the
Command Query Responsibility Segregation (CQRS) pattern in Resync.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, TypeVar, Union

from pydantic import BaseModel

# Generic type variables
TCommand = TypeVar("TCommand", bound="ICommand")
TQuery = TypeVar("TQuery", bound="IQuery")
TResult = TypeVar("TResult")


@dataclass
class ICommand(ABC):
    """
    Base interface for command objects in the CQRS pattern.
    Commands represent operations that change the system state.
    """


@dataclass
class IQuery(ABC):
    """
    Base interface for query objects in the CQRS pattern.
    Queries represent operations that read data without changing the system state.
    """


@dataclass
class ICommandHandler(ABC, Generic[TCommand, TResult]):
    """
    Base interface for command handlers.
    """

    @abstractmethod
    async def execute(self, command: TCommand) -> TResult:
        """
        Execute the command and return the result.

        Args:
            command: The command to execute

        Returns:
            The result of the command execution
        """


@dataclass
class IQueryHandler(ABC, Generic[TQuery, TResult]):
    """
    Base interface for query handlers.
    """

    @abstractmethod
    async def execute(self, query: TQuery) -> TResult:
        """
        Execute the query and return the result.

        Args:
            query: The query to execute

        Returns:
            The result of the query execution
        """


class CommandResult(BaseModel):
    """
    Base class for command execution results.
    """

    success: bool
    message: str = ""
    data: Any = None
    error: Union[str, None] = None


class QueryResult(BaseModel):
    """
    Base class for query execution results.
    """

    success: bool
    data: Any = None
    error: Union[str, None] = None
