"""
Additional security headers and configuration for Resync application.
"""

import logging

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .enhanced_security import configure_enhanced_security

logger = logging.getLogger(__name__)


class AdditionalSecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Additional security headers middleware.
    This middleware adds extra security headers to responses.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Add additional security headers
        # Strict-Transport-Security: Force HTTPS (only if app is deployed with HTTPS)
        # Note: Only enable if using HTTPS in production
        # response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

        # Permissions-Policy header
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )

        # Feature-Policy header (deprecated but still supported by some browsers)
        response.headers.setdefault(
            "Feature-Policy", "geolocation 'none'; microphone 'none'; camera 'none'"
        )

        return response


def add_additional_security_headers(app: FastAPI) -> None:
    """
    Add additional security headers middleware to the application.

    Args:
        app: FastAPI application instance
    """
    # Configure enhanced security features
    configure_enhanced_security(app)

    # Add additional security headers middleware
    app.add_middleware(AdditionalSecurityHeadersMiddleware)
    logger.info("Additional security headers middleware added")
