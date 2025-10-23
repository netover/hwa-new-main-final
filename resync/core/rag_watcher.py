# resync/core/rag_watcher.py
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from watchfiles import awatch

from resync.core.interfaces import IFileIngestor
from resync.settings import settings

logger = logging.getLogger(__name__)

RAG_DIRECTORY = settings.BASE_DIR / "rag"


async def watch_rag_directory(file_ingestor: IFileIngestor) -> None:
    """Watches the rag/ directory for new files and triggers ingestion."""
    # Ensure the directory exists
    RAG_DIRECTORY.mkdir(exist_ok=True)

    logger.info(f"Starting RAG watcher on directory: {RAG_DIRECTORY}")
    try:
        async for changes in awatch(RAG_DIRECTORY):
            for change_type, path_str in changes:
                # We only care about new files being added.
                if change_type.name == "added":
                    file_path = Path(path_str)
                    logger.info(f"New file detected in RAG directory: {file_path.name}")
                    # Schedule ingestion as a background task to avoid blocking the watcher
                    asyncio.create_task(file_ingestor.ingest_file(file_path))

    except Exception as e:
        logger.error(f"Error in RAG directory watcher: {e}", exc_info=True)
