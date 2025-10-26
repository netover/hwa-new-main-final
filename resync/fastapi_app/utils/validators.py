
"""
Validation utilities for FastAPI application
"""
import re
from typing import Optional
from pathlib import Path
from ..core.config import settings

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_username(username: str) -> bool:
    """Validate username format"""
    # Alphanumeric, underscore, dash, 3-30 characters
    pattern = r'^[a-zA-Z0-9_-]{3,30}$'
    return bool(re.match(pattern, username))

def validate_password(password: str) -> tuple[bool, Optional[str]]:
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"

    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"

    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one digit"

    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"

    return True, None

def validate_file_extension(filename: str) -> bool:
    """Validate file extension against allowed types"""
    file_ext = Path(filename).suffix.lower()
    return file_ext in settings.allowed_extensions

def validate_file_size(size: int) -> bool:
    """Validate file size against maximum allowed"""
    return size <= settings.max_file_size

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent security issues"""
    # Remove potentially dangerous characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Limit length
    filename = filename[:255]
    return filename

def validate_agent_id(agent_id: str) -> bool:
    """Validate agent ID format"""
    # UUID format or alphanumeric with dash/underscore
    pattern = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$|^[a-zA-Z0-9_-]+$'
    return bool(re.match(pattern, agent_id))

def validate_memory_id(memory_id: str) -> bool:
    """Validate memory ID format (UUID)"""
    pattern = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
    return bool(re.match(pattern, memory_id))

def validate_audit_action(action: str) -> bool:
    """Validate audit review action"""
    return action in ["approve", "reject"]

def validate_search_query(query: str) -> str:
    """Validate and sanitize search query"""
    # Remove potentially dangerous SQL injection patterns
    query = re.sub(r'[<>"\';]', '', query)
    # Limit length
    return query[:100] if len(query) > 100 else query

def validate_pagination_params(limit: int, offset: int) -> tuple[int, int]:
    """Validate pagination parameters"""
    # Ensure reasonable limits
    limit = min(max(1, limit), 100)  # 1-100 items per page
    offset = max(0, offset)  # Non-negative offset

    return limit, offset

def validate_rate_limit(request_count: int, window_seconds: int) -> bool:
    """Check if request count is within rate limits"""
    max_requests = settings.rate_limit_requests
    return request_count <= max_requests
