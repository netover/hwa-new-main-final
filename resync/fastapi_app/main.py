"""
FastAPI Application Main Entry Point
"""
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from .api.v1.routes.auth import router as auth_router
from .api.v1.routes.chat import router as chat_router
from .api.v1.routes.audit import router as audit_router
from .api.v1.routes.agents import router as agents_router
from .api.v1.routes.rag import router as rag_router
from .api.v1.routes.status import router as status_router
from .api.v1.routes.admin_config import router as admin_config_router
from .api.websocket.handlers import websocket_handler

app = FastAPI(
    title="HWA API",
    version="1.0",
    description="High-Performance Web Application API"
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates - use absolute path from project root
import pathlib
project_root = pathlib.Path(__file__).parent.parent.parent
templates = Jinja2Templates(directory=str(project_root / "templates"))

# Include routers
app.include_router(auth_router, prefix="/api/v1", tags=["Authentication"])
app.include_router(chat_router, prefix="/api/v1", tags=["Chat"])
app.include_router(audit_router, prefix="/api/v1", tags=["Audit"])
app.include_router(agents_router, prefix="/api/v1", tags=["Agents"])
app.include_router(rag_router, prefix="/api/v1", tags=["RAG"])
app.include_router(status_router, prefix="/api/v1", tags=["Status"])

# Include admin configuration routes under a dedicated namespace
app.include_router(admin_config_router, prefix="/api/v1/admin", tags=["Admin"])

# WebSocket endpoint
@app.websocket("/api/v1/ws/{agent_id}")
async def websocket_endpoint(websocket: WebSocket, agent_id: str):
    """WebSocket endpoint for real-time chat with agents"""
    await websocket_handler(websocket, agent_id)

@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    """Main dashboard page with all system functionalities"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health", response_class=HTMLResponse)
async def health_page(request: Request):
    """Health check page with system status"""
    return templates.TemplateResponse("health.html", {"request": request})

@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """Web page for chat interface"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/revisao", response_class=HTMLResponse)
async def revisao_page(request: Request):
    """Web page for review interface"""
    return templates.TemplateResponse("revisao.html", {"request": request})

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Web page for admin interface"""
    return templates.TemplateResponse("admin.html", {"request": request})

# API routes are now handled by routers included above
# Direct app routes removed to avoid conflicts
