"""
Qdrant collection snapshot management for versioning and rollback.

Provides create, list, and delete operations for Qdrant snapshots to enable safe migrations and rollbacks.
"""

from __future__ import annotations

import asyncio
import functools
import logging
from typing import Optional

from .config import CFG

logger = logging.getLogger(__name__)

# Optional import
try:
    from qdrant_client import QdrantClient
except ImportError:
    raise RuntimeError("qdrant-client is required for snapshots")


def _to_thread(fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return loop.run_in_executor(None, functools.partial(fn, *args, **kwargs))


class QdrantPersistence:
    """
    Handles Qdrant snapshot creation and management for versioning and rollback.
    """

    def __init__(self, url: Optional[str] = None, api_key: Optional[str] = None):
        self._client = QdrantClient(
            url or CFG.qdrant_url, api_key=api_key or CFG.qdrant_api_key
        )

    async def create_collection_snapshot(self, collection: Optional[str] = None) -> str:
        """
        Create a snapshot of the specified collection.
        """
        col = collection or CFG.collection_write
        snap = await _to_thread(self._client.create_snapshot, collection_name=col)
        logger.info("Snapshot created for %s: %s", col, snap)
        return str(snap)

    async def list_collection_snapshots(self, collection: Optional[str] = None):
        """
        List all snapshots for the specified collection.
        """
        col = collection or CFG.collection_write
        return await _to_thread(self._client.list_snapshots, collection_name=col)

    async def delete_collection_snapshot(
        self, snapshot_name: str, collection: Optional[str] = None
    ) -> None:
        """
        Delete a specific snapshot from the collection.
        """
        col = collection or CFG.collection_write
        await _to_thread(
            self._client.delete_snapshot,
            collection_name=col,
            snapshot_name=snapshot_name,
        )