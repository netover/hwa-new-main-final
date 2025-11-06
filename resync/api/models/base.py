"""Base models and common classes."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class BaseModelWithTime(BaseModel):
    """Base model with automatic timestamp fields."""

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PaginationRequest(BaseModel):
    """Standard pagination request parameters."""

    page: int = 1
    page_size: int = 10


class PaginationResponse(BaseModel):
    """Standard pagination response metadata."""

    total_items: int
    total_pages: int
    current_page: int
    page_size: int
