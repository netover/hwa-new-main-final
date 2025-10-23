"""
Health Check Integration Tests.

This module contains integration tests for the health check API endpoints.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from resync.api.health import health_router
from resync.core.health_models import (
    ComponentHealth,
    ComponentType,
    HealthCheckResult,
    HealthStatus,
)


@pytest.fixture
def client():
    """
    Create a TestClient instance using a minimal FastAPI app that only includes
    the health check router.
    """
    app = FastAPI()
    app.include_router(health_router)
    with TestClient(app) as c:
        yield c


class TestHealthCheckIntegration:
    """Test health check API endpoint integrations."""

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_health_check_endpoint_basic(self, mock_get_health_service, client):
        """Test basic health check endpoint."""
        # Arrange
        mock_health_service = MagicMock()
        mock_health_service.perform_comprehensive_health_check = AsyncMock(
            return_value=HealthCheckResult(
                overall_status=HealthStatus.HEALTHY,
                timestamp=datetime.now(),
                components={
                    "test": ComponentHealth(
                        "test", ComponentType.DATABASE, HealthStatus.HEALTHY
                    )
                },
                performance_metrics={"total_check_time_ms": 100},
                alerts=[],
                summary={},
            )
        )
        mock_get_health_service.return_value = mock_health_service

        # Act
        response = client.get("/health/")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "core_components" not in data  # This is not the core endpoint

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_health_check_endpoint_unhealthy(self, mock_get_health_service, client):
        """Test health check endpoint with unhealthy status."""
        # Arrange
        mock_health_service = MagicMock()
        mock_health_service.perform_comprehensive_health_check = AsyncMock(
            return_value=HealthCheckResult(
                overall_status=HealthStatus.UNHEALTHY,
                timestamp=datetime.now(),
                components={
                    "test": ComponentHealth(
                        "test", ComponentType.DATABASE, HealthStatus.UNHEALTHY
                    )
                },
                performance_metrics={"total_check_time_ms": 100},
                alerts=[],
                summary={},
            )
        )
        mock_get_health_service.return_value = mock_health_service

        # Act
        response = client.get("/health/")

        # Assert
        assert response.status_code == 200  # Endpoint should still be reachable
        data = response.json()
        assert data["status"] == "unhealthy"

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_health_check_no_service(self, mock_get_health_service, client):
        """Test health check when service is not available."""
        # Arrange
        mock_get_health_service.side_effect = Exception(
            "Health check service not available"
        )

        # Act
        response = client.get("/health/")

        # Assert
        assert response.status_code == 503
        data = response.json()
        assert "Health check service not available" in data["detail"]

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_health_check_service_exception(self, mock_get_health_service, client):
        """Test health check when service raises exception."""
        # Arrange
        mock_health_service = MagicMock()
        mock_health_service.perform_comprehensive_health_check = AsyncMock(
            side_effect=Exception("Service error")
        )
        mock_get_health_service.return_value = mock_health_service

        # Act
        response = client.get("/health/")

        # Assert
        assert response.status_code == 503
        data = response.json()
        assert "Service error" in data["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])