"""
Input validation utilities using Pydantic for robust data validation.

This module provides pre-built validation models and utilities for
common input validation scenarios in the application.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Type

from pydantic import field_validator, BaseModel, ConfigDict, Field, ValidationError


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OLLAMA = "ollama"
    LITELLM = "litellm"


class LLMRequest(BaseModel):
    """Validation model for LLM requests."""

    prompt: str = Field(
        ..., min_length=1, max_length=10000, description="The prompt to send to the LLM"
    )
    model: str = Field(
        ..., description="The LLM model identifier", pattern=r"^[a-zA-Z0-9\-_/.]+$"
    )
    max_tokens: int = Field(
        default=200, ge=1, le=4000, description="Maximum tokens in response"
    )
    temperature: float = Field(
        default=0.1, ge=0.0, le=2.0, description="Sampling temperature"
    )
    timeout: float = Field(
        default=30.0, ge=1.0, le=300.0, description="Request timeout in seconds"
    )
    provider: Optional[LLMProvider] = Field(default=None, description="LLM provider")

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, v: str):
        """Validate and clean prompt input."""
        if not v or not v.strip():
            raise ValueError("Prompt cannot be empty")
        return v.strip()

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str):
        """Validate model identifier."""
        if not v or not v.strip():
            raise ValueError("Model cannot be empty")
        return v.strip()


class PaginationRequest(BaseModel):
    """Validation model for pagination parameters."""

    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    page_size: int = Field(default=50, ge=1, le=1000, description="Items per page")
    sort_by: Optional[str] = Field(
        default=None, description="Sort field", pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$"
    )
    sort_order: str = Field(
        default="asc", description="Sort order", pattern=r"^(asc|desc)$"
    )

    @property
    def offset(self) -> int:
        """Calculate database offset."""
        return (self.page - 1) * self.page_size


class SearchRequest(BaseModel):
    """Validation model for search requests."""

    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    filters: Optional[Dict[str, Any]] = Field(
        default=None, description="Search filters"
    )
    limit: int = Field(default=100, ge=1, le=1000, description="Maximum results")

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str):
        """Validate and clean search query."""
        if not v or not v.strip():
            raise ValueError("Search query cannot be empty")
        return v.strip()


class FileUploadRequest(BaseModel):
    """Validation model for file uploads."""

    filename: str = Field(
        ..., min_length=1, max_length=255, description="Original filename"
    )
    content_type: str = Field(
        ..., description="MIME type", pattern=r"^[a-zA-Z0-9\-]+/[a-zA-Z0-9\-]+$"
    )
    size: int = Field(
        ..., ge=1, le=50 * 1024 * 1024, description="File size in bytes"
    )  # 50MB max

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str):
        """Validate filename for security."""
        import os

        if os.path.basename(v) != v:
            raise ValueError("Filename cannot contain path separators")
        if ".." in v:
            raise ValueError("Filename cannot contain '..'")
        return v


class APIKeyRequest(BaseModel):
    """Validation model for API key operations."""

    name: str = Field(..., min_length=1, max_length=100, description="API key name")
    description: Optional[str] = Field(
        default=None, max_length=500, description="API key description"
    )
    scopes: List[str] = Field(default_factory=list, description="API key permissions")
    expires_at: Optional[str] = Field(default=None, description="Expiration timestamp")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str):
        """Validate API key name."""
        if not v or not v.strip():
            raise ValueError("API key name cannot be empty")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "API key name can only contain letters, numbers, underscores, and hyphens"
            )
        return v.strip()


class ConfigurationUpdate(BaseModel):
    """Validation model for configuration updates."""

    key: str = Field(..., min_length=1, max_length=200, description="Configuration key")
    value: Any = Field(..., description="Configuration value")
    value_type: str = Field(
        ..., description="Value type", pattern=r"^(str|int|float|bool|list|dict)$"
    )

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str):
        """Validate configuration key."""
        if not v or not v.strip():
            raise ValueError("Configuration key cannot be empty")
        if not all(c.isalnum() or c in "._-" for c in v):
            raise ValueError(
                "Configuration key can only contain letters, numbers, dots, underscores, and hyphens"
            )
        return v.strip()


def validate_input(data: Dict[str, Any], model_class: Type[BaseModel]) -> BaseModel:
    """
    Validate input data against a Pydantic model.

    Args:
        data: Input data to validate
        model_class: Pydantic model class to validate against

    Returns:
        Validated model instance

    Raises:
        ValidationError: If validation fails
    """
    try:
        return model_class(**data)
    except ValidationError as e:
        # Enhance error messages for better user experience
        enhanced_errors = []
        for error in e.errors():
            field_path = ".".join(str(loc) for loc in error["loc"])
            enhanced_errors.append(
                {"field": field_path, "message": error["msg"], "type": error["type"]}
            )

        raise ValidationError(errors=enhanced_errors, model=model_class) from e


def create_validation_middleware():
    """
    Create FastAPI middleware for automatic input validation.

    Returns:
        FastAPI middleware function
    """
    from fastapi import Request
    from fastapi.responses import JSONResponse

    async def validation_middleware(request: Request, call_next: Any):
        """Middleware to validate requests and provide better error responses."""
        try:
            response = await call_next(request)
            return response
        except ValidationError as e:
            # Return structured validation errors
            return JSONResponse(
                status_code=422,
                content={
                    "error": "validation_error",
                    "details": [
                        {
                            "field": ".".join(str(loc) for loc in error["loc"]),
                            "message": error["msg"],
                            "type": error["type"],
                        }
                        for error in e.errors()
                    ],
                },
            )
        except Exception as e:
            # Re-raise other exceptions
            raise

    return validation_middleware
