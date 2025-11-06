"""
RAG Service Client for API Gateway

This module provides a client to communicate with the standalone RAG microservice.
"""

from typing import Any

import httpx
from pydantic import BaseModel

from resync.core.resilience import CircuitBreakerManager, retry_with_backoff_async
from resync.core.structured_logger import get_logger
from resync.settings import settings

logger = get_logger(__name__)


class RAGJobStatus(BaseModel):
    """Model for RAG job status response"""

    job_id: str
    status: str  # queued, processing, completed, failed
    progress: int | None = None
    message: str | None = None


class RAGUploadResponse(BaseModel):
    """Model for RAG upload response"""

    job_id: str
    filename: str
    status: str


class RAGServiceClient:
    """
    Client to communicate with the RAG microservice.

    Implements:
    - HTTP client with retry logic
    - Circuit breaker for protection
    - Timeout configuration
    - Error handling
    """

    def __init__(self):
        """Initialize the RAG service client"""
        self.rag_service_url = settings.RAG_SERVICE_URL
        self.max_retries = 3
        self.retry_backoff = 1.0  # seconds

        # Initialize HTTP client
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout=30.0, connect=10.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

        # Centralized circuit breaker manager
        self.cbm = CircuitBreakerManager()
        self.cbm.register(
            "rag_service", fail_max=5, reset_timeout=60, exclude=(ValueError,)
        )

        logger.info("RAGServiceClient initialized")

    async def enqueue_file(self, file: Any) -> str:
        """
        Enqueue a file for RAG processing.

        Args:
            file: UploadFile object from FastAPI

        Returns:
            str: Generated job_id

        Raises:
            Exception: If upload fails after retries
        """
        if not self.rag_service_url:
            raise Exception("RAG_SERVICE_URL not configured")

        async def _once():
            return await self.http_client.post(
                f"{self.rag_service_url}/api/v1/upload",
                files={"file": (file.filename, file.file, file.content_type)},
            )

        async def _call():
            resp = await self.cbm.call("rag_service", _once)
            resp.raise_for_status()
            return resp

        resp = await retry_with_backoff_async(
            _call,
            retries=self.max_retries,
            base_delay=self.retry_backoff,
            cap=5.0,
            jitter=True,
            retry_on=(httpx.RequestError, httpx.TimeoutException),
        )
        data = resp.json()
        return data["job_id"]

    async def get_job_status(self, job_id: str) -> RAGJobStatus:
        """
        Get the status of a RAG processing job.

        Args:
            job_id: The job identifier

        Returns:
            RAGJobStatus: Job status information

        Raises:
            Exception: If job status cannot be retrieved
        """
        if not self.rag_service_url:
            raise Exception("RAG_SERVICE_URL not configured")

        async def _once():
            return await self.http_client.get(
                f"{self.rag_service_url}/api/v1/jobs/{job_id}"
            )

        async def _call():
            resp = await self.cbm.call("rag_service", _once)
            if resp.status_code == 404:
                return RAGJobStatus(
                    job_id=job_id,
                    status="not_found",
                    progress=0,
                    message="Job ID not found",
                )
            resp.raise_for_status()
            return RAGJobStatus(**resp.json())

        return await retry_with_backoff_async(
            _call,
            retries=self.max_retries,
            base_delay=self.retry_backoff,
            cap=5.0,
            jitter=True,
            retry_on=(httpx.RequestError, httpx.TimeoutException),
        )


# Global instance
rag_client = RAGServiceClient()
"""Global RAG service client instance"""
