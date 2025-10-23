
"""
Request models for FastAPI endpoints
"""
from pydantic import BaseModel
from typing import Optional, List

class AuditReviewRequest(BaseModel):
    memory_id: str
    action: str

class ChatMessageRequest(BaseModel):
    message: str
    agent_id: Optional[str] = None

class FileUploadRequest(BaseModel):
    filename: str
    content_type: str
    size: int

class SystemStatusFilter(BaseModel):
    workstation_filter: Optional[str] = None
    job_status_filter: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class RAGUploadRequest(BaseModel):
    filename: str
    content: str

class AuditFlagsQuery(BaseModel):
    status_filter: Optional[str] = None
    query: Optional[str] = None
    limit: int = 50
    offset: int = 0

class ChatHistoryQuery(BaseModel):
    agent_id: Optional[str] = None
    limit: int = 50

class RAGFileQuery(BaseModel):
    file_id: str

class FileUploadValidation(BaseModel):
    """Validation model for file uploads"""
    filename: str
    content_type: str
    size: int

    def validate_file(self) -> None:
        """Validate file properties"""
        from pathlib import Path

        # Check file extension
        file_ext = Path(self.filename).suffix.lower()
        allowed_extensions = {".txt", ".pdf", ".docx", ".md", ".json"}
        if file_ext not in allowed_extensions:
            raise ValueError(f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}")

        # Check file size (10MB limit)
        max_size = 10 * 1024 * 1024
        if self.size > max_size:
            raise ValueError(f"File too large. Maximum size: {max_size / (1024*1024)}MB")
