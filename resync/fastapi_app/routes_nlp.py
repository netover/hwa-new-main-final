"""FastAPI router for NLP utilities.

This router exposes an endpoint for extracting structured fields from
TWS/HWA log lines using the Promptify based ``LogFieldExtractor``.
Clients can optionally request strict validation of the response
schema by enabling the ``strict`` flag in the request body.  When
strict mode is enabled the output will be validated using a
Pydantic model and any unknown or malformed fields will result in
a 422 response.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError

from resync.nlp.promptify_pipeline import LogFieldExtractor


router = APIRouter(prefix="/api/v1/nlp", tags=["nlp"])


class LogExtractRequest(BaseModel):
    """Request model for log field extraction."""

    text: str
    strict: bool = False


class LogExtractResponse(BaseModel):
    """Response model for log field extraction."""

    job_id: str | None = Field(None, description="ID do job (se encontrado)")
    workstation: str | None = Field(None, description="Workstation associada")
    status: str | None = Field(
        None,
        description="Status do job (SUCC, ABEND, RUNNING, HOLD)",
        pattern="^(SUCC|ABEND|RUNNING|HOLD)$",
    )
    timestamp: str | None = Field(None, description="Timestamp extraído")
    root_cause: str | None = Field(None, description="Causa raiz do erro")


@router.post("/extract-log-fields", response_model=LogExtractResponse)
async def extract_log_fields(req: LogExtractRequest) -> LogExtractResponse:
    """Extract structured fields from an unstructured log line.

    The ``strict`` flag determines whether the output should be
    validated.  In strict mode the response is validated by the
    ``LogExtractResponse`` model and a validation error results in
    a 422 response.  When strict is false the fields are returned
    without additional validation.
    """
    try:
        extractor = LogFieldExtractor()
    except Exception as exc:
        # Likely misconfiguration (missing API key or Promptify not installed)
        raise HTTPException(status_code=500, detail=str(exc))

    try:
        data = await extractor.extract(req.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Build the response.  If strict mode is enabled, validate using
    # the response model.  Validation errors will propagate to FastAPI.
    if req.strict:
        try:
            return LogExtractResponse(**data)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors())
    else:
        # In non strict mode we coerce missing keys to None and ignore
        # invalid values in the status field by discarding them.
        safe_data = {
            "job_id": data.get("job_id"),
            "workstation": data.get("workstation"),
            "status": data.get("status"),
            "timestamp": data.get("timestamp"),
            "root_cause": data.get("root_cause"),
        }
        try:
            return LogExtractResponse(**safe_data)
        except ValidationError:
            # Discard invalid status if not conforming to pattern
            safe_data["status"] = None
            return LogExtractResponse(**safe_data)