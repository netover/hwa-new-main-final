
"""
Response models for FastAPI endpoints
"""
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

class WorkstationInfo(BaseModel):
    id: str
    name: str
    status: str
    last_seen: Optional[datetime] = None

class JobInfo(BaseModel):
    id: str
    name: str
    status: str
    workstation_id: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

class SystemStatusResponse(BaseModel):
    workstations: List[WorkstationInfo]
    jobs: List[JobInfo]
    timestamp: datetime

class AgentInfo(BaseModel):
    id: str
    name: str
    status: str
    description: Optional[str] = None

class AgentListResponse(BaseModel):
    agents: List[AgentInfo]
    total: int

class FileUploadResponse(BaseModel):
    filename: str
    status: str
    file_id: Optional[str] = None
    upload_time: datetime

class AuditFlagInfo(BaseModel):
    memory_id: str
    status: str
    user_query: str
    agent_response: str
    ia_audit_reason: Optional[str] = None
    ia_audit_confidence: Optional[float] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None

class AuditMetricsResponse(BaseModel):
    pending: int
    approved: int
    rejected: int
    total: int

class AuditReviewResponse(BaseModel):
    memory_id: str
    action: str
    status: str
    reviewed_at: datetime

class ChatMessageResponse(BaseModel):
    message: str
    timestamp: datetime
    agent_id: Optional[str] = None
    is_final: bool = False

class HealthResponse(BaseModel):
    status: str
    uptime: str
    version: str

class LoginResponse(BaseModel):
    message: str

class StatusResponse(BaseModel):
    workstations: List[Any]
    jobs: List[Any]

class AuditFlagsResponse(BaseModel):
    flags: List[Dict[str, Any]]

class RAGUploadResponse(BaseModel):
    filename: str
    status: str
