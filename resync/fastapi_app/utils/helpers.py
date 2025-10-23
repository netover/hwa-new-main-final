
"""
Helper utilities for FastAPI application
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import hashlib
import json
from pathlib import Path

def generate_uuid() -> str:
    """Generate a new UUID4 string"""
    return str(uuid.uuid4())

def get_current_timestamp() -> str:
    """Get current timestamp in ISO format"""
    return datetime.now(timezone.utc).isoformat()

def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of a file"""
    sha256 = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def safe_json_loads(data: str) -> Optional[Dict[str, Any]]:
    """Safely parse JSON string"""
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return None

def safe_json_dumps(data: Any) -> str:
    """Safely serialize to JSON string"""
    try:
        return json.dumps(data, default=str)
    except (TypeError, ValueError):
        return "{}"

def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return ".1f"
        size_bytes /= 1024.0
    return ".1f"

def extract_text_from_filename(filename: str) -> str:
    """Extract text content from filename (placeholder)"""
    # TODO: Implement actual text extraction based on file type
    # For now, return filename without extension
    return Path(filename).stem

def create_pagination_info(
    total_items: int,
    limit: int,
    offset: int,
    current_page: Optional[int] = None
) -> Dict[str, Any]:
    """Create pagination information"""
    total_pages = (total_items + limit - 1) // limit if limit > 0 else 1
    current_page = current_page or (offset // limit) + 1

    return {
        "total_items": total_items,
        "total_pages": total_pages,
        "current_page": current_page,
        "items_per_page": limit,
        "has_next": current_page < total_pages,
        "has_previous": current_page > 1
    }

def mask_sensitive_data(data: str, mask_char: str = "*") -> str:
    """Mask sensitive data in strings"""
    # Simple masking for demo - replace with more sophisticated logic
    if len(data) <= 4:
        return mask_char * len(data)
    return data[:2] + mask_char * (len(data) - 4) + data[-2:]

def validate_redis_connection(redis_client) -> bool:
    """Validate Redis connection"""
    try:
        redis_client.ping()
        return True
    except Exception:
        return False

def create_error_response(
    error_type: str,
    message: str,
    status_code: int,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create standardized error response"""
    response = {
        "error": {
            "type": error_type,
            "message": message,
            "status_code": status_code,
            "timestamp": get_current_timestamp()
        }
    }

    if details:
        response["error"]["details"] = details

    return response

def create_success_response(
    data: Any,
    message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create standardized success response"""
    response = {
        "success": True,
        "data": data,
        "timestamp": get_current_timestamp()
    }

    if message:
        response["message"] = message

    if metadata:
        response["metadata"] = metadata

    return response

def normalize_agent_name(name: str) -> str:
    """Normalize agent name for consistent storage/retrieval"""
    return name.lower().strip().replace(" ", "_")

def generate_correlation_id() -> str:
    """Generate correlation ID for request tracing"""
    return f"req_{uuid.uuid4().hex[:8]}"

def parse_user_agent(user_agent: str) -> Dict[str, str]:
    """Parse user agent string (simplified)"""
    # TODO: Implement proper user agent parsing
    return {
        "raw": user_agent,
        "browser": "unknown",
        "os": "unknown",
        "device": "unknown"
    }
