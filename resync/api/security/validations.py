from __future__ import annotations

from re import match

from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field, validator

# --- Enhanced Validation Rules ---
password_hasher = CryptContext(schemes=["bcrypt"], deprecated="auto")


class SensitiveFieldValidator:
    @staticmethod
    def validate_password(password: str) -> str:
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isdigit() for c in password):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isupper() for c in password):
            raise ValueError("Password must contain at least one uppercase letter")
        if match(r"^\d+", password):
            raise ValueError("Password must not start with a digit")
        return password

    @staticmethod
    def validate_email(email: str) -> str:
        if not EmailStr.validate(email):
            raise ValueError("Invalid email format")
        if "@" not in email:
            raise ValueError("Email must contain '@'")
        local, domain = email.split("@")
        if len(local) < 1 or len(local) > 64:
            raise ValueError("Local part must be 1-64 characters")
        if len(domain) < 1 or len(domain) > 255:
            raise ValueError("Domain part must be 1-255 characters")
        return email


class EnhancedLoginRequest(BaseModel):
    username: str = Field(
        ..., min_length=3, max_length=32, json_schema_extra={"example": "johndoe"}
    )
    password: str = Field(
        ..., min_length=8, json_schema_extra={"example": "SecureP@ss123!"}
    )

    @validator("password")
    def validate_password(cls, v):
        return SensitiveFieldValidator.validate_password(v)


class UserCreateWithValidation(BaseModel):
    username: str = Field(
        ..., min_length=3, max_length=32, json_schema_extra={"example": "johndoe"}
    )
    email: EmailStr = Field(..., json_schema_extra={"example": "user@example.com"})
    password: str = Field(
        ..., min_length=8, json_schema_extra={"example": "SecureP@ss123!"}
    )

    @validator("email")
    def validate_email(cls, v):
        return SensitiveFieldValidator.validate_email(v)


class TokenRequestWithValidation(BaseModel):
    refresh_token: str = Field(
        min_length=512,
        max_length=2048,
        example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    )

    @validator("refresh_token")
    def validate_refresh_token(cls, v):
        if len(v) < 512:
            raise ValueError("Refresh token must be at least 512 characters")
        if not v.startswith("eyJ"):
            raise ValueError("Token must start with 'eyJ' (JWT header)")
        return v
