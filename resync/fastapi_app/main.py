"""
FastAPI application main entry point.

This module creates and configures the FastAPI application with all routers
included under the /api/v1 prefix for versioned API endpoints.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.websockets import WebSocket

# Import routers (simplified to avoid import issues for now)
# from resync.api.endpoints import api_router
# from resync.api.agents import agents_router
# from resync.api.chat import chat_router
# from resync.api.audit import router as audit_router
# from resync.api.rag_upload import router as rag_router
# from resync.api.exception_handlers import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager."""
    # Startup
    yield
    # Shutdown


# Create FastAPI application
app = FastAPI(
    title="Resync API",
    description="Unified API for Resync TWS Integration",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register exception handlers
# register_exception_handlers(app)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")

# --- Basic API Endpoints (temporary implementation) ---

@app.get("/api/v1/status")
async def get_status():
    """Get system status."""
    return {
        "tws_connected": False,
        "mock_mode": True,
        "agents_loaded": 0,
        "knowledge_graph": "available",
    }

@app.get("/api/v1/chat")
async def get_chat():
    """Basic chat endpoint."""
    return {"message": "Chat endpoint working", "status": "active"}

@app.get("/api/v1/agents/")
async def list_agents():
    """List all agents."""
    return [
        {
            "id": "test-agent-1",
            "name": "Test Agent 1",
            "role": "Tester",
            "goal": "To be tested",
            "model": "test-model",
        }
    ]

@app.get("/api/v1/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get agent details."""
    return {
        "id": agent_id,
        "name": f"Agent {agent_id}",
        "role": "Assistant",
        "goal": "To assist users",
        "model": "test-model",
    }

@app.post("/api/v1/rag/upload")
async def upload_rag():
    """Upload RAG file."""
    return {"filename": "test.txt", "status": "uploaded"}

@app.get("/api/v1/audit/metrics")
async def get_audit_metrics():
    """Get audit metrics."""
    return {"pending": 0, "approved": 0, "rejected": 0}

@app.post("/api/v1/audit/review")
async def audit_review():
    """Review audit item."""
    return {"memory_id": "test", "action": "approved", "status": "success"}

@app.websocket("/api/v1/ws/{agent_id}")
async def websocket_endpoint(websocket: WebSocket, agent_id: str):
    """WebSocket endpoint for real-time communication."""
    await websocket.accept()
    await websocket.send_text(f"Connected to agent {agent_id}")
    await websocket.close()

# Include API routers with /api/v1 prefix
# TODO: Uncomment when import issues are resolved
# app.include_router(api_router, prefix="/api/v1", tags=["API"])
# app.include_router(agents_router, prefix="/api/v1/agents", tags=["Agents"])
# app.include_router(chat_router, prefix="/api/v1", tags=["Chat"])
# app.include_router(audit_router, prefix="/api/v1", tags=["Audit"])
# app.include_router(rag_router, prefix="/api/v1", tags=["RAG"])

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "resync-api"}
