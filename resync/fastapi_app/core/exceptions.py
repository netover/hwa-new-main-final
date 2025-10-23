
"""
Custom exceptions for FastAPI application
"""
from fastapi import HTTPException, status
from typing import Optional, Dict, Any

class AppException(Exception):
    """Base application exception"""

    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class AuthenticationError(AppException):
    """Authentication related errors"""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED)

class AuthorizationError(AppException):
    """Authorization related errors"""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, status.HTTP_403_FORBIDDEN)

class ValidationError(AppException):
    """Data validation errors"""

    def __init__(self, message: str = "Validation failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.details = details

class ResourceNotFoundError(AppException):
    """Resource not found errors"""

    def __init__(self, resource: str, resource_id: Optional[str] = None):
        message = f"{resource} not found"
        if resource_id:
            message += f": {resource_id}"
        super().__init__(message, status.HTTP_404_NOT_FOUND)

class ResourceConflictError(AppException):
    """Resource conflict errors"""

    def __init__(self, message: str = "Resource conflict"):
        super().__init__(message, status.HTTP_409_CONFLICT)

class ExternalServiceError(AppException):
    """External service communication errors"""

    def __init__(self, service: str, message: str = "Service unavailable"):
        super().__init__(f"{service}: {message}", status.HTTP_503_SERVICE_UNAVAILABLE)
        self.service = service

class RateLimitExceededError(AppException):
    """Rate limit exceeded errors"""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, status.HTTP_429_TOO_MANY_REQUESTS)

class FileUploadError(AppException):
    """File upload related errors"""

    def __init__(self, message: str = "File upload failed"):
        super().__init__(message, status.HTTP_400_BAD_REQUEST)

# Exception handlers for FastAPI
def create_http_exception(exc: AppException) -> HTTPException:
    """Convert AppException to FastAPI HTTPException"""
    return HTTPException(
        status_code=exc.status_code,
        detail=exc.message
    )

# Custom exception handlers
async def app_exception_handler(request, exc: AppException):
    """Handle custom application exceptions"""
    return {
        "detail": exc.message,
        "type": exc.__class__.__name__,
        "status_code": exc.status_code
    }

async def validation_exception_handler(request, exc):
    """Handle Pydantic validation exceptions"""
    return {
        "detail": "Validation error",
        "errors": exc.errors(),
        "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY
    }
