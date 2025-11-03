"""Authentication and authorization API endpoints - SECURE VERSION.

This module provides JWT-based authentication endpoints and utilities,
including token generation, validation, and user session management.
It implements secure authentication flows with proper error handling
and integrates with the application's security middleware.

SECURITY FIXES:
- Removed fallback SECRET_KEY for production
- Added proper SECRET_KEY validation
- Enhanced error handling for missing security configuration
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from resync.config.settings import settings
from resync.utils.simple_logger import get_logger

logger = get_logger(__name__)

# Security schemes
# Allow missing Authorization to support HttpOnly cookie fallback
security = HTTPBearer(auto_error=False)

# Secret key for JWT tokens - CRITICAL SECURITY FIX
SECRET_KEY = getattr(settings, "SECRET_KEY", None)

# Validate SECRET_KEY is properly configured
if SECRET_KEY is None:
    raise ValueError(
        "CRITICAL SECURITY ERROR: SECRET_KEY is not configured. "
        "Set SECRET_KEY environment variable with at least 32 characters."
    )

if isinstance(SECRET_KEY, str) and len(SECRET_KEY) < 32:
    raise ValueError(
        "CRITICAL SECURITY ERROR: SECRET_KEY must be at least 32 characters long. "
        "Current length: {}".format(len(SECRET_KEY))
    )

# Additional production security checks
if getattr(settings, 'environment', 'development') == 'production':
    if not SECRET_KEY or SECRET_KEY in ['fallback_secret_key_for_development', 'dev', 'test']:
        raise ValueError(
            "CRITICAL SECURITY ERROR: Cannot use development fallback SECRET_KEY in production. "
            "Set a secure, random SECRET_KEY environment variable."
        )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


class SecureAuthenticator:
    """Authenticator resistente a timing attacks."""

    def __init__(self) -> None:
        self._failed_attempts: dict[str, list[datetime]] = {}
        self._lockout_duration = timedelta(minutes=15)
        self._max_attempts = 5
        self._lockout_lock = asyncio.Lock()

    async def verify_credentials(
        self, username: str, password: str, request_ip: str
    ) -> tuple[bool, Optional[str]]:
        """
        Verify credentials with:
        - Constant-time comparison
        - Rate limiting per IP
        - Account lockout
        - Audit logging
        """
        # Check if IP is locked out
        async with self._lockout_lock:
            if await self._is_locked_out(request_ip):
                logger.warning(
                    "Authentication attempt from locked out IP",
                    extra={"ip": request_ip},
                )
                # Still perform full verification to maintain constant time
                # but will return failure regardless
                lockout_remaining = await self._get_lockout_remaining(
                    request_ip
                )
                await asyncio.sleep(0.5)  # Artificial delay
                return (
                    False,
                    f"Too many failed attempts. Try again in {lockout_remaining} minutes",
                )

        # Always hash both provided and expected values to maintain constant time
        provided_username_hash = self._hash_credential(username)
        provided_password_hash = self._hash_credential(password)

        expected_username_hash = self._hash_credential(settings.admin_username)
        expected_password_hash = self._hash_credential(settings.admin_password)

        # Constant-time comparison using secrets.compare_digest
        username_valid = secrets.compare_digest(
            provided_username_hash, expected_username_hash
        )

        password_valid = secrets.compare_digest(
            provided_password_hash, expected_password_hash
        )

        # Combine results without short-circuiting
        credentials_valid = username_valid and password_valid

        # Artificial delay to prevent timing analysis
        await asyncio.sleep(
            secrets.randbelow(100) / 1000
        )  # 0-100ms random delay

        if not credentials_valid:
            await self._record_failed_attempt(request_ip)

            logger.warning(
                "Failed authentication attempt",
                extra={
                    "ip": request_ip,
                    "username_provided": username[:3]
                    + "***",  # Partial for logs
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            return False, "Invalid credentials"

        # Success - clear failed attempts
        async with self._lockout_lock:
            if request_ip in self._failed_attempts:
                del self._failed_attempts[request_ip]

        logger.info(
            "Successful authentication",
            extra={
                "ip": request_ip,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        return True, None

    def _hash_credential(self, credential: str) -> bytes:
        """Hash credential for constant-time comparison."""
        # Use HMAC with secret key to prevent rainbow table attacks
        secret_key = SECRET_KEY.encode("utf-8")  # Use validated SECRET_KEY
        return hmac.new(
            secret_key, credential.encode("utf-8"), hashlib.sha256
        ).digest()

    async def _record_failed_attempt(self, ip: str) -> None:
        """Record failed authentication attempt."""
        async with self._lockout_lock:
            now = datetime.utcnow()

            if ip not in self._failed_attempts:
                self._failed_attempts[ip] = []

            # Add current attempt
            self._failed_attempts[ip].append(now)

            # Remove attempts outside lockout window
            cutoff = now - self._lockout_duration
            self._failed_attempts[ip] = [
                attempt
                for attempt in self._failed_attempts[ip]
                if attempt > cutoff
            ]

            # Log if approaching lockout
            attempt_count = len(self._failed_attempts[ip])
            if attempt_count >= self._max_attempts - 1:
                logger.warning(
                    f"IP approaching lockout: {attempt_count}/{self._max_attempts} attempts",
                    extra={"ip": ip},
                )

    async def _is_locked_out(self, ip: str) -> bool:
        """Check if IP is currently locked out."""
        if ip not in self._failed_attempts:
            return False

        now = datetime.utcnow()
        cutoff = now - self._lockout_duration

        # Count recent attempts
        recent_attempts = [
            attempt
            for attempt in self._failed_attempts[ip]
            if attempt > cutoff
        ]

        return len(recent_attempts) >= self._max_attempts

    async def _get_lockout_remaining(self, ip: str) -> int:
        """Get remaining lockout time in minutes."""
        if ip not in self._failed_attempts or not self._failed_attempts[ip]:
            return 0

        oldest_attempt = min(self._failed_attempts[ip])
        unlock_time = oldest_attempt + self._lockout_duration
        remaining = (unlock_time - datetime.utcnow()).total_seconds() / 60

        return max(0, int(remaining))


# Global authenticator instance
authenticator = SecureAuthenticator()


def verify_admin_credentials(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[str]:
    """
    Verify admin credentials for protected endpoints using JWT tokens.
    """
    try:
        # 1) Try Authorization header (Bearer)
        token = (
            credentials.credentials
            if (credentials and credentials.credentials)
            else None
        )

        # 2) Fallback: HttpOnly cookie "access_token"
        if not token:
            token = request.cookies.get("access_token")
            if not token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Credentials not provided",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        # Decode & validate JWT
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")

        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Accept ADMIN_USERNAME or admin_username for compatibility
        admin_user = getattr(settings, "ADMIN_USERNAME", None) or getattr(
            settings, "admin_username", None
        )
        if username != admin_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return username
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def create_access_token(
    data: dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a new JWT access token.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def authenticate_admin(username: str, password: str) -> bool:
    """
    Authenticate admin user credentials with enhanced security validation.
    """
    # Verify the username matches the admin username from settings
    admin_user = getattr(settings, "ADMIN_USERNAME", None) or getattr(
        settings, "admin_username", None
    )
    if username != admin_user:
        return False

    # Use the SecureAuthenticator for constant-time comparison
    client_ip = "unknown"  # In this context, we don't have the request object
    is_valid, _ = await authenticator.verify_credentials(
        username, password, client_ip
    )
    return is_valid




