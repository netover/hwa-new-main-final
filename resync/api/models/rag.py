"""RAG (Retrieval-Augmented Generation) models."""

from typing import Optional

from pydantic import BaseModel

from .base import BaseModelWithTime


class RAGFileMetaData(BaseModel):
    """Metadata for RAG file uploads."""

    filename: str
    content_type: str
    uploaded_by: Optional[str] = None
    description: Optional[str] = None


class RAGFileCreate(BaseModelWithTime):
    """RAG file creation request model."""

    filename: str
    content_type: str
    metadata: Optional[RAGFileMetaData] = None


class RAGFileDetail(RAGFileCreate):
    """Detailed RAG file information."""

    id: str
    file_size: int
    ingestion_status: str
