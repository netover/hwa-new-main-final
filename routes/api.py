"""
API Routes for HWA Application

This module defines all API endpoints for the HWA application.
"""

from flask import Blueprint, jsonify, request
from flask_socketio import SocketIO

from resync.services.rag_client import rag_client
from resync.core.exceptions import (
    ValidationError,
    ResourceNotFoundError,
    IntegrationError,
    FileIngestionError,
    InternalError
)

api = Blueprint('api', __name__)

@api.route('/status')
def api_status():
    return jsonify({"workstations": [], "jobs": []})

@api.route('/v1/')
def list_agents():
    return jsonify([])

@api.route('/rag/upload', methods=['POST'])
async def upload_rag_file():
    """
    Upload a file for RAG processing.

    This endpoint is asynchronous and returns immediately with a job_id.
    Processing happens in the background via the RAG microservice.
    """
    file = request.files.get('file')
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    try:
        # Enqueue file for processing via RAG microservice
        job_id = await rag_client.enqueue_file(file)

        return jsonify({
            "job_id": job_id,
            "status": "queued",
            "message": "File queued for processing"
        }), 202  # Accepted

    except FileIngestionError:
        # Re-raise file ingestion errors as-is
        raise
    except IntegrationError:
        # Re-raise integration errors as-is
        raise
    except ValidationError:
        # Re-raise validation errors as-is
        raise
    except Exception as e:
        # Wrap unexpected errors in InternalError
        raise InternalError(
            message=f"Failed to queue file for processing: {str(e)}",
            details={"original_error": str(e)},
            original_exception=e
        ) from e

@api.route('/rag/jobs/<job_id>', methods=['GET'])
async def get_rag_job_status(job_id: str):
    """
    Get the status of a RAG processing job.

    Args:
        job_id: The job identifier

    Returns:
        JSON with job status information
    """
    try:
        # Get job status from RAG microservice
        job_status = await rag_client.get_job_status(job_id)

        return jsonify({
            "job_id": job_status.job_id,
            "status": job_status.status,
            "progress": job_status.progress,
            "message": job_status.message
        }), 200

    except ResourceNotFoundError:
        # Re-raise not found errors as-is
        raise
    except IntegrationError:
        # Re-raise integration errors as-is
        raise
    except ValidationError:
        # Re-raise validation errors as-is
        raise
    except Exception as e:
        # Wrap unexpected errors in InternalError
        raise InternalError(
            message=f"Failed to get job status: {str(e)}",
            details={"job_id": job_id, "original_error": str(e)},
            original_exception=e
        ) from e

@api.route('/audit/flags')
def audit_flags():
    return jsonify([])

@api.route('/audit/metrics')
def audit_metrics():
    return jsonify({"pending": 0, "approved": 0, "rejected": 0})

@api.route('/audit/review', methods=['POST'])
def audit_review():
    data = request.get_json()
    memory_id = data.get('memory_id')
    action = data.get('action')
    return jsonify({"memory_id": memory_id, "action": action, "status": "processed"})

socketio = SocketIO()

# Register blueprint in main.py