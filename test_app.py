#!/usr/bin/env python3
"""
Simple FastAPI application for testing Resync TWS Integration
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(
    title="Resync TWS Integration API",
    description="Sistema de integração IA-TWS via linguagem natural",
    version="1.0.0",
)


@app.get("/")
async def root():
    return JSONResponse(
        {
            "message": "Resync TWS Integration API",
            "status": "running",
            "version": "1.0.0",
            "description": "Sistema de integração IA-TWS via linguagem natural",
        }
    )


@app.get("/health")
async def health():
    return JSONResponse(
        {
            "status": "healthy",
            "service": "resync-tws-integration",
            "timestamp": "2025-01-07T10:00:00Z",
        }
    )


@app.get("/api/v1/status")
async def api_status():
    return JSONResponse(
        {
            "tws_connected": False,
            "mock_mode": True,
            "agents_loaded": 0,
            "knowledge_graph": "available",
        }
    )


if __name__ == "__main__":
    import uvicorn

    print("Starting Resync TWS Integration API...")
    print("Server will run on http://localhost:8000")
    print("Health check: http://localhost:8000/health")
    print("API status: http://localhost:8000/api/v1/status")
    uvicorn.run(app, host="0.0.0.0", port=8000)
