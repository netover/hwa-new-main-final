"""
WebSocket Implementation for Real-Time RAG Job Status Updates

This module implements WebSocket endpoints for real-time status updates
from the RAG microservice to clients.
"""

from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import request
import asyncio
from typing import Dict
import logging

from resync.services.rag_client import rag_client
from resync.core.exceptions import (
    ValidationError,
    ResourceNotFoundError,
    IntegrationError,
    WebSocketError,
    InternalError
)

# Initialize SocketIO
socketio = SocketIO()

# Store active connections
active_connections: Dict[str, str] = {}  # job_id -> session_id

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    logging.info("WebSocket client connected")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    logging.info("WebSocket client disconnected")
    # Clean up connections
    for job_id, session_id in list(active_connections.items()):
        if session_id == request.sid:
            del active_connections[job_id]

@socketio.on('join_rag_job')
def join_rag_job(data):
    """Client joins a specific RAG job room for updates"""
    job_id = data.get('job_id')
    if not job_id:
        emit('error', {'message': 'Job ID required'})
        return

    # Join room for this job
    join_room(job_id)
    active_connections[job_id] = request.sid

    logging.info(f"Client {request.sid} joined job {job_id}")

    # Send current status immediately
    try:
        job_status = asyncio.run_coroutine_threadsafe(
            rag_client.get_job_status(job_id),
            asyncio.get_event_loop()
        ).result()

        emit('rag_job_status', {
            'job_id': job_status.job_id,
            'status': job_status.status,
            'progress': job_status.progress,
            'message': job_status.message
        })

    except ResourceNotFoundError:
        # Re-raise not found errors as-is
        raise
    except IntegrationError:
        # Re-raise integration errors as-is
        raise
    except ValidationError:
        # Re-raise validation errors as-is
        raise
    except WebSocketError:
        # Re-raise WebSocket errors as-is
        raise
    except Exception as e:
        # Wrap unexpected errors in InternalError
        raise InternalError(
            message=f"Failed to get job status for {job_id}: {str(e)}",
            details={"job_id": job_id, "original_error": str(e)},
            original_exception=e
        ) from e

@socketio.on('leave_rag_job')
def leave_rag_job(data):
    """Client leaves a specific RAG job room"""
    job_id = data.get('job_id')
    if job_id and job_id in active_connections and active_connections[job_id] == request.sid:
        leave_room(job_id)
        del active_connections[job_id]
        logging.info(f"Client {request.sid} left job {job_id}")

async def emit_rag_job_status_update(job_id: str, status: str, progress: int = None, message: str = None):
    """
    Emit a RAG job status update to all clients subscribed to this job.

    This function should be called by the RAG microservice when job status changes.
    """
    if job_id in active_connections:
        socketio.emit('rag_job_status', {
            'job_id': job_id,
            'status': status,
            'progress': progress,
            'message': message
        }, room=job_id)
        logging.info(f"Emitted status update for job {job_id}: {status}")

# Export the socketio instance for use in other modules
__all__ = ['socketio', 'emit_rag_job_status_update']