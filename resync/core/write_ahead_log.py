"""Write Ahead Log Module.

This module provides write-ahead logging functionality for the application.
"""

import logging
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass


class WalOperationType(Enum):
    """Types of WAL operations."""
    WRITE = "write"
    DELETE = "delete"
    CLEAR = "clear"


@dataclass
class WalEntry:
    """Entry in the write-ahead log."""

    operation: WalOperationType
    key: str
    sequence_number: int = 0
    value: Optional[Any] = None
    timestamp: float = 0.0  # Valor padrão para timestamp


class IWriteAheadLog(ABC):
    """Interface for write-ahead log."""
    
    @abstractmethod
    async def write_log(self, message: str, level: str = "INFO") -> bool:
        """Write a message to the log."""
        pass
    
    @abstractmethod
    async def flush_logs(self) -> bool:
        """Flush all pending logs."""
        pass


class SimpleWriteAheadLog(IWriteAheadLog):
    """Simple implementation of write-ahead log."""
    
    def __init__(self):
        """Initialize the write-ahead log."""
        self.logger = logging.getLogger(__name__)
        self.pending_logs = []
    
    async def write_log(self, message: str, level: str = "INFO") -> bool:
        """Write a message to the log."""
        try:
            self.pending_logs.append((message, level))
            return True
        except Exception as e:
            self.logger.error(f"Error writing to log: {e}")
            return False
    
    async def flush_logs(self) -> bool:
        """Flush all pending logs."""
        try:
            for message, level in self.pending_logs:
                if level == "INFO":
                    self.logger.info(message)
                elif level == "WARNING":
                    self.logger.warning(message)
                elif level == "ERROR":
                    self.logger.error(message)
                elif level == "DEBUG":
                    self.logger.debug(message)
            
            self.pending_logs.clear()
            return True
        except Exception as e:
            self.logger.error(f"Error flushing logs: {e}")
            return False


# Global instance
_write_ahead_log: Optional[SimpleWriteAheadLog] = None


def get_write_ahead_log() -> SimpleWriteAheadLog:
    """Get the global write-ahead log instance."""
    global _write_ahead_log
    if _write_ahead_log is None:
        _write_ahead_log = SimpleWriteAheadLog()
    return _write_ahead_log
