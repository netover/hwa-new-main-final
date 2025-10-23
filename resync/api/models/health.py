"""Health-related API models."""

from typing import Optional

from pydantic import BaseModel, Field

from .base import BaseModelWithTime
from resync.core.health_models import SystemHealthStatus


class SystemMetric(BaseModelWithTime):
    """System metric model for API responses."""

    metric_name: str
    value: float
    status: SystemHealthStatus
