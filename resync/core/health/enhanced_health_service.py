"""
Enhanced Health Service

This module provides the enhanced health service functionality.
It aliases HealthServiceFacade as EnhancedHealthService for API compatibility.
"""

from __future__ import annotations

from .health_service_facade import HealthServiceFacade

# Alias for API compatibility
EnhancedHealthService = HealthServiceFacade
