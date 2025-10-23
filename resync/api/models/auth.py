"""Authentication and user management models."""

from typing import Optional

from pydantic import BaseModel


class LoginRequest(BaseModel):
    """User login request model."""

    username: str
    password: str
    # Security fields
    captcha_token: Optional[str] = None
    client_fingerprint: Optional[str] = None
    session_token: Optional[str] = None


class UserRegistrationRequest(BaseModel):
    """User registration request model."""

    username: str
    email: str
    password: str
    # Security fields
    captcha_token: Optional[str] = None
    terms_accepted: bool = False
    client_fingerprint: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    """Password change request model."""

    current_password: str
    new_password: str
    confirm_password: str
    # Security fields
    session_token: Optional[str] = None
    client_fingerprint: Optional[str] = None


class Token(BaseModel):
    """OAuth2 token response model."""

    access_token: str
    token_type: str


class TokenData(BaseModel):
    """JWT token payload data."""

    username: Optional[str] = None






















