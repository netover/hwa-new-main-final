"""
OAuth2 Security Module

This module provides OAuth2/JWT token verification functionality.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from jose import JWTError, jwt


class User:
    """
    User object representing an authenticated user.
    """

    def __init__(self, user_id: str, username: str, roles: list[str] = None):
        self.user_id = user_id
        self.username = username
        self.roles = roles or []


async def verify_oauth2_token(token: str) -> User:
    """
    Verify an OAuth2/JWT token and return user information.

    In development mode, this accepts a simple token format.
    In production, this should verify against your OAuth2 provider.

    Args:
        token: JWT token string

    Returns:
        User object with user information

    Raises:
        JWTError: If token is invalid
    """
    # For development/testing purposes, accept a simple format
    # In production, this should decode and verify a proper JWT
    if token.startswith("dev-token-"):
        # Extract user info from dev token
        parts = token.split("-")
        if len(parts) >= 3:
            user_id = parts[2]
            username = f"user_{user_id}"
            return User(user_id=user_id, username=username, roles=["user"])

    # For production, decode JWT
    try:
        # This is a placeholder - you should configure your actual JWT secret/key
        secret_key = "your-jwt-secret-key"  # Should come from config
        algorithm = "HS256"

        payload = jwt.decode(token, secret_key, algorithms=[algorithm])

        user_id = payload.get("sub")
        username = payload.get("username", user_id)
        roles = payload.get("roles", [])

        if not user_id:
            raise JWTError("Missing user ID in token")

        return User(user_id=str(user_id), username=username, roles=roles)

    except JWTError:
        raise JWTError("Invalid token")


def create_oauth2_token(user: User, expires_in: int = 3600) -> str:
    """
    Create an OAuth2/JWT token for a user.

    Args:
        user: User object
        expires_in: Token expiration time in seconds

    Returns:
        JWT token string
    """
    # For development purposes
    if user.username.startswith("user_"):
        return f"dev-token-{user.user_id}"

    # For production, create proper JWT
    from datetime import datetime, timedelta

    secret_key = "your-jwt-secret-key"  # Should come from config
    algorithm = "HS256"

    payload = {
        "sub": user.user_id,
        "username": user.username,
        "roles": user.roles,
        "exp": datetime.utcnow() + timedelta(seconds=expires_in),
        "iat": datetime.utcnow(),
    }

    token = jwt.encode(payload, secret_key, algorithm=algorithm)
    return token
