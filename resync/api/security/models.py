from __future__ import annotations

from datetime import datetime

from passlib.context import CryptContext
from pydantic import field_validator, BaseModel, EmailStr, Field

# --- Password Validation Context ---
password_hasher = CryptContext(schemes=["bcrypt"], deprecated="auto")


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=8)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        return v


class UserCreate(BaseModel):
    username: str = Field(
        ..., min_length=3, max_length=32, json_schema_extra={"example": "johndoe"}
    )
    email: EmailStr = Field(...)
    password: str = Field(
        ..., min_length=8, json_schema_extra={"example": "securepassword123!"}
    )


class UserResponse(BaseModel):
    id: str
    username: str
    email: EmailStr
    created_at: datetime


class TokenRequest(BaseModel):
    refresh_token: str = Field(...)


class OAuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str
    expires_in: int
