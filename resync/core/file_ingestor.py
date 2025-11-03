"""File Ingestor Module.

This module provides file ingestion functionality for the application.
"""

from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod


class IFileIngestor(ABC):
    """Interface for file ingestors."""
    
    @abstractmethod
    async def ingest_file(self, file_path: str) -> Dict[str, Any]:
        """Ingest a file and return metadata."""
        pass
    
    @abstractmethod
    async def batch_ingest(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """Ingest multiple files and return metadata."""
        pass


class SimpleFileIngestor(IFileIngestor):
    """Simple implementation of file ingestor."""
    
    def __init__(self, knowledge_graph=None):
        """Initialize with optional knowledge graph."""
        self.knowledge_graph = knowledge_graph
    
    async def ingest_file(self, file_path: str) -> Dict[str, Any]:
        """Ingest a file and return metadata."""
        return {
            "file_path": file_path,
            "status": "ingested",
            "timestamp": "2023-01-01T00:00:00Z"
        }
    
    async def batch_ingest(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """Ingest multiple files and return metadata."""
        return [
            {
                "file_path": path,
                "status": "ingested",
                "timestamp": "2023-01-01T00:00:00Z"
            }
            for path in file_paths
        ]


def create_file_ingestor(knowledge_graph=None) -> IFileIngestor:
    """Create a file ingestor instance."""
    return SimpleFileIngestor(knowledge_graph)
