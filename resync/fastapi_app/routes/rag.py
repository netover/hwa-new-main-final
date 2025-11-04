"""Routes related to RAG microservice orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from anyio import to_thread
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])

try:
    from resync.services.rag_client import rag_client, RAGJobStatus  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    rag_client = None  # type: ignore
    RAGJobStatus = None  # type: ignore

try:
    from resync.core.file_ingestor import create_file_ingestor  # type: ignore
    from resync.core.knowledge_graph import AsyncKnowledgeGraph  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    create_file_ingestor = None  # type: ignore
    AsyncKnowledgeGraph = None  # type: ignore


@router.post("/upload")
async def upload_rag() -> dict[str, str]:
    """Upload a document to the RAG service and return a job identifier."""
    if rag_client is None:
        raise HTTPException(status_code=501, detail="RAG service not available")
    raise HTTPException(
        status_code=503,
        detail="Multipart file upload not supported in this deployment",
    )


@router.get("/jobs/{job_id}")
async def get_rag_job_status(job_id: str) -> dict[str, Any]:
    """Return the status of a RAG processing job."""
    if rag_client is None or RAGJobStatus is None:
        raise HTTPException(status_code=501, detail="RAG service not available")
    try:
        status = await rag_client.get_job_status(job_id)
        return status.dict()
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/packages")
async def list_rag_packages(request: Request) -> list[str]:
    """List available knowledge packages on the server."""
    base_path = Path(__file__).resolve().parents[2] / "knowledge_base"

    def _collect_packages() -> list[str]:
        if not base_path.exists() or not base_path.is_dir():
            return []
        return [entry.name for entry in base_path.iterdir() if entry.is_dir()]

    try:
        return await to_thread.run_sync(_collect_packages)
    except OSError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/packages/{package_name}/ingest")
async def ingest_rag_package(package_name: str) -> dict[str, Any]:
    """Ingest all files from a server-side knowledge package."""
    if create_file_ingestor is None or AsyncKnowledgeGraph is None:
        raise HTTPException(status_code=501, detail="Knowledge graph not available")
    base_path = Path(__file__).resolve().parents[2] / "knowledge_base"
    pkg_path = base_path / package_name
    if not pkg_path.exists() or not pkg_path.is_dir():
        raise HTTPException(status_code=404, detail="Knowledge package not found")

    def _collect_file_paths() -> list[str]:
        import os

        paths: list[str] = []
        for root, _, files in os.walk(pkg_path):
            for name in files:
                paths.append(str(Path(root) / name))
        return paths

    file_paths = await to_thread.run_sync(_collect_file_paths)
    if not file_paths:
        return {"indexed": 0, "message": "No files to ingest"}
    try:
        kg = AsyncKnowledgeGraph()
        ingestor = create_file_ingestor(kg)
        results = await ingestor.batch_ingest(file_paths)  # type: ignore[attr-defined]
        return {"indexed": len(results), "message": f"Ingested {len(results)} files"}
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc
