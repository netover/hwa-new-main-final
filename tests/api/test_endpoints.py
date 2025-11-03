"""
API Endpoints Tests for Health Checks.

This module tests the /health API endpoints for functionality, ensuring they
respond correctly and reflect the state of their dependencies.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from resync.api.health import health_router, shutdown_health_service
from resync.core.health_models import (
    ComponentHealth,
    ComponentType,
    HealthCheckResult,
    HealthStatus,
    HealthStatusHistory,
)


@pytest.fixture
def client():
    """
    Create a TestClient instance using a minimal FastAPI app that only includes
    the health check router.
    """
    test_app = FastAPI()
    test_app.include_router(health_router)

    with TestClient(test_app) as c:
        yield c


class TestHealthEndpoint:
    """Test /health endpoint functionality."""

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_health_core_healthy(self, mock_get_health_service, client):
        """Test the /health/core endpoint with all components healthy."""
        # Arrange
        mock_health_service = MagicMock()
        mock_health_service.perform_comprehensive_health_check = AsyncMock()
        mock_get_health_service.return_value = mock_health_service

        mock_result = HealthCheckResult(
            overall_status=HealthStatus.HEALTHY,
            timestamp=datetime.now(),
            components={
                "database": ComponentHealth(
                    name="database",
                    component_type=ComponentType.DATABASE,
                    status=HealthStatus.HEALTHY,
                    last_check=datetime.now(),
                ),
                "redis": ComponentHealth(
                    name="redis",
                    component_type=ComponentType.REDIS,
                    status=HealthStatus.HEALTHY,
                    last_check=datetime.now(),
                ),
                "file_system": ComponentHealth(
                    name="file_system",
                    component_type=ComponentType.FILE_SYSTEM,
                    status=HealthStatus.HEALTHY,
                    last_check=datetime.now(),
                ),
                "other_service": ComponentHealth(  # This one should be filtered out
                    name="other_service",
                    component_type=ComponentType.EXTERNAL_API,
                    status=HealthStatus.HEALTHY,
                    last_check=datetime.now(),
                ),
            },
        )
        mock_health_service.perform_comprehensive_health_check.return_value = (
            mock_result
        )

        # Act
        response = client.get("/health/core")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "database" in data["core_components"]
        assert "redis" in data["core_components"]
        assert "file_system" in data["core_components"]
        assert "other_service" not in data["core_components"]
        mock_get_health_service.assert_awaited_once()
        mock_health_service.perform_comprehensive_health_check.assert_awaited_once()

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_health_summary_degraded(self, mock_get_health_service, client):
        """Test the /health summary endpoint with a degraded component."""
        # Arrange
        mock_health_service = MagicMock()
        mock_health_service.perform_comprehensive_health_check = AsyncMock()
        mock_get_health_service.return_value = mock_health_service

        alert_dict = {"message": "Redis connection is slow"}
        mock_result = HealthCheckResult(
            overall_status=HealthStatus.DEGRADED,
            timestamp=datetime.now(),
            summary={"details": "One component is degraded"},
            alerts=[alert_dict],
            performance_metrics={"db_query_time": 50},
        )
        mock_health_service.perform_comprehensive_health_check.return_value = (
            mock_result
        )

        # Act
        response = client.get("/health/")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["summary"]["details"] == "One component is degraded"
        assert str(alert_dict) in data["alerts"]

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_health_detailed_unhealthy(self, mock_get_health_service, client):
        """Test the /health/detailed endpoint with an unhealthy component."""
        # Arrange
        mock_health_service = MagicMock()
        mock_health_service.perform_comprehensive_health_check = AsyncMock()
        mock_get_health_service.return_value = mock_health_service

        mock_result = HealthCheckResult(
            overall_status=HealthStatus.UNHEALTHY,
            timestamp=datetime.now(),
            components={
                "database": ComponentHealth(
                    name="database",
                    component_type=ComponentType.DATABASE,
                    status=HealthStatus.UNHEALTHY,
                    message="Connection failed",
                    last_check=datetime.now(),
                ),
            },
        )
        mock_health_service.perform_comprehensive_health_check.return_value = (
            mock_result
        )

        # Act
        response = client.get("/health/detailed")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["overall_status"] == "unhealthy"
        assert data["components"]["database"]["status"] == "unhealthy"
        assert data["components"]["database"]["message"] == "Connection failed"

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_health_check_service_unavailable(self, mock_get_health_service, client):
        """Test health check when the health service itself raises an exception."""
        # Arrange
        mock_get_health_service.side_effect = Exception("Service not available")

        # Act
        response = client.get("/health/")

        # Assert
        assert response.status_code == 503
        data = response.json()
        assert "Health check system error: Service not available" in data["detail"]

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_readiness_probe_ready(self, mock_get_health_service, client):
        """Test the /health/ready endpoint when the system is ready."""
        # Arrange
        mock_health_service = MagicMock()
        mock_health_service.perform_comprehensive_health_check = AsyncMock()
        mock_get_health_service.return_value = mock_health_service

        mock_result = HealthCheckResult(
            overall_status=HealthStatus.HEALTHY,
            timestamp=datetime.now(),
            components={
                "database": ComponentHealth(
                    status=HealthStatus.HEALTHY,
                    name="database",
                    component_type=ComponentType.DATABASE,
                )
            },
        )
        mock_health_service.perform_comprehensive_health_check.return_value = (
            mock_result
        )

        # Act
        response = client.get("/health/ready")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_readiness_probe_not_ready(self, mock_get_health_service, client):
        """Test the /health/ready endpoint when a core component is unhealthy."""
        # Arrange
        mock_health_service = MagicMock()
        mock_health_service.perform_comprehensive_health_check = AsyncMock()
        mock_get_health_service.return_value = mock_health_service

        mock_result = HealthCheckResult(
            overall_status=HealthStatus.UNHEALTHY,
            timestamp=datetime.now(),
            components={
                "database": ComponentHealth(
                    status=HealthStatus.UNHEALTHY,
                    name="database",
                    component_type=ComponentType.DATABASE,
                )
            },
        )
        mock_health_service.perform_comprehensive_health_check.return_value = (
            mock_result
        )

        # Act
        response = client.get("/health/ready")

        # Assert
        assert response.status_code == 503
        data = response.json()
        assert data["detail"]["status"] == "not_ready"

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_liveness_probe_alive(self, mock_get_health_service, client):
        """Test the /health/live endpoint when the system is alive."""
        # Arrange
        mock_health_service = MagicMock()
        mock_health_service.last_health_check = datetime.now() - timedelta(minutes=1)
        mock_get_health_service.return_value = mock_health_service

        # Act
        response = client.get("/health/live")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_liveness_probe_stuck(self, mock_get_health_service, client):
        """Test the /health/live endpoint when the health check is stuck."""
        # Arrange
        mock_health_service = MagicMock()
        mock_health_service.last_health_check = datetime.now() - timedelta(minutes=10)
        mock_get_health_service.return_value = mock_health_service

        # Act
        response = client.get("/health/live")

        # Assert
        assert response.status_code == 503
        data = response.json()
        assert data["detail"]["status"] == "dead"

    def test_list_components(self, client):
        """Test the /health/components endpoint."""
        # Act
        response = client.get("/health/components")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "components" in data
        assert len(data["components"]) > 0
        assert data["components"][0]["name"] == "database"

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_redis_health_healthy(self, mock_get_health_service, client):
        """Test the /health/redis endpoint when Redis is healthy."""
        # Arrange
        mock_health_service = MagicMock()
        mock_health_service.perform_comprehensive_health_check = AsyncMock()
        mock_get_health_service.return_value = mock_health_service

        mock_result = HealthCheckResult(
            overall_status=HealthStatus.HEALTHY,
            timestamp=datetime.now(),
            components={
                "redis": ComponentHealth(
                    name="redis",
                    component_type=ComponentType.REDIS,
                    status=HealthStatus.HEALTHY,
                    response_time_ms=10.0,
                    metadata={"version": "6.2"},
                )
            },
        )
        mock_health_service.perform_comprehensive_health_check.return_value = (
            mock_result
        )

        # Act
        response = client.get("/health/redis")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["idempotency_safe"] is True
        assert data["redis"]["response_time_ms"] == 10.0
        assert data["redis"]["details"]["version"] == "6.2"

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_redis_health_unhealthy(self, mock_get_health_service, client):
        """Test the /health/redis endpoint when Redis is unhealthy."""
        # Arrange
        mock_health_service = MagicMock()
        mock_health_service.perform_comprehensive_health_check = AsyncMock()
        mock_get_health_service.return_value = mock_health_service

        mock_result = HealthCheckResult(
            overall_status=HealthStatus.UNHEALTHY,
            timestamp=datetime.now(),
            components={
                "redis": ComponentHealth(
                    name="redis",
                    component_type=ComponentType.REDIS,
                    status=HealthStatus.UNHEALTHY,
                )
            },
        )
        mock_health_service.perform_comprehensive_health_check.return_value = (
            mock_result
        )

        # Act
        response = client.get("/health/redis")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "critical"
        assert data["idempotency_safe"] is False

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_recover_component_success(self, mock_get_health_service, client):
        """Test component recovery when it succeeds."""
        # Arrange
        mock_health_service = MagicMock()
        mock_health_service.attempt_recovery = AsyncMock(return_value=True)
        mock_health_service.get_component_health = AsyncMock(
            return_value=ComponentHealth(
                name="database",
                component_type=ComponentType.DATABASE,
                status=HealthStatus.HEALTHY,
            )
        )
        mock_get_health_service.return_value = mock_health_service

        # Act
        response = client.post("/health/component/database/recover")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["recovery_successful"] is True
        assert data["current_status"] == "healthy"

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_recover_component_failure(self, mock_get_health_service, client):
        """Test component recovery when it fails."""
        # Arrange
        mock_health_service = MagicMock()
        mock_health_service.attempt_recovery = AsyncMock(return_value=False)
        mock_health_service.get_component_health = AsyncMock(
            return_value=ComponentHealth(
                name="database",
                component_type=ComponentType.DATABASE,
                status=HealthStatus.UNHEALTHY,
            )
        )
        mock_get_health_service.return_value = mock_health_service

        # Act
        response = client.post("/health/component/database/recover")

        # Assert
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["recovery_successful"] is False
        assert data["detail"]["current_status"] == "unhealthy"

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_health_detailed_with_history(self, mock_get_health_service, client):
        """Test the /health/detailed endpoint with history included."""
        # Arrange
        mock_health_service = MagicMock()
        mock_health_service.perform_comprehensive_health_check = AsyncMock()
        mock_health_service.get_health_history = MagicMock()
        mock_get_health_service.return_value = mock_health_service

        mock_result = HealthCheckResult(
            overall_status=HealthStatus.HEALTHY,
            timestamp=datetime.now(),
            components={},
        )
        history_entry = HealthStatusHistory(
            timestamp=datetime.now() - timedelta(hours=1),
            overall_status=HealthStatus.DEGRADED,
        )
        mock_health_service.perform_comprehensive_health_check.return_value = (
            mock_result
        )
        mock_health_service.get_health_history.return_value = [history_entry]

        # Act
        response = client.get("/health/detailed?include_history=true")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["overall_status"] == "healthy"
        assert len(data["history"]) == 1
        assert data["history"][0]["overall_status"] == "degraded"
        mock_health_service.get_health_history.assert_called_once_with(24)

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_health_core_unhealthy(self, mock_get_health_service, client):
        """Test the /health/core endpoint with an unhealthy core component."""
        # Arrange
        mock_health_service = MagicMock()
        mock_health_service.perform_comprehensive_health_check = AsyncMock()
        mock_get_health_service.return_value = mock_health_service

        mock_result = HealthCheckResult(
            overall_status=HealthStatus.UNHEALTHY,
            timestamp=datetime.now(),
            components={
                "database": ComponentHealth(
                    name="database",
                    component_type=ComponentType.DATABASE,
                    status=HealthStatus.UNHEALTHY,
                    last_check=datetime.now(),
                )
            },
        )
        mock_health_service.perform_comprehensive_health_check.return_value = (
            mock_result
        )

        # Act
        response = client.get("/health/core")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["core_components"]["database"]["status"] == "unhealthy"

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_readiness_probe_failure(self, mock_get_health_service, client):
        """Test the readiness probe when the service call fails."""
        mock_get_health_service.side_effect = Exception("boom")
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert "not_ready" in response.text
        assert "boom" in response.text

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_liveness_probe_failure(self, mock_get_health_service, client):
        """Test the liveness probe when the service call fails."""
        mock_get_health_service.side_effect = Exception("boom")
        response = client.get("/health/live")
        assert response.status_code == 503
        assert "dead" in response.text
        assert "boom" in response.text

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_recover_component_exception(self, mock_get_health_service, client):
        """Test component recovery when an exception occurs."""
        mock_health_service = MagicMock()
        mock_health_service.attempt_recovery = AsyncMock(
            side_effect=Exception("boom")
        )
        mock_get_health_service.return_value = mock_health_service
        response = client.post("/health/component/database/recover")
        assert response.status_code == 500
        assert "boom" in response.text

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_get_redis_health_exception(self, mock_get_health_service, client):
        """Test redis health check when an exception occurs."""
        mock_get_health_service.side_effect = Exception("boom")
        response = client.get("/health/redis")
        # this endpoint catches the exception and returns a 200
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "critical"
        assert data["idempotency_safe"] is False
        assert "boom" in data["error"]

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_get_core_health_exception(self, mock_get_health_service, client):
        """Test core health check when an exception occurs."""
        mock_get_health_service.side_effect = Exception("boom")
        response = client.get("/health/core")
        assert response.status_code == 503
        assert "boom" in response.text

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_get_detailed_health_exception(self, mock_get_health_service, client):
        """Test detailed health check when an exception occurs."""
        mock_get_health_service.side_effect = Exception("boom")
        response = client.get("/health/detailed")
        assert response.status_code == 503
        assert "boom" in response.text

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    @patch("resync.api.health.runtime_metrics")
    def test_health_summary_with_auto_enable(
        self, mock_metrics, mock_get_health_service, client
    ):
        """Test /health endpoint with auto_enable flag."""
        # Arrange
        mock_health_service = MagicMock()
        mock_health_service.perform_comprehensive_health_check = AsyncMock()
        mock_get_health_service.return_value = mock_health_service
        mock_result = HealthCheckResult(
            overall_status=HealthStatus.HEALTHY,
            timestamp=datetime.now(),
            summary={},
            alerts=[],
            performance_metrics={},
        )
        mock_health_service.perform_comprehensive_health_check.return_value = (
            mock_result
        )

        # Act
        response = client.get("/health/?auto_enable=true")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["auto_enable"] is True
        assert data["summary"]["auto_enable_applied"] is True
        mock_metrics.health_check_with_auto_enable.increment.assert_called_once()

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_health_core_degraded(self, mock_get_health_service, client):
        """Test /health/core with a degraded component."""
        # Arrange
        mock_health_service = MagicMock()
        mock_health_service.perform_comprehensive_health_check = AsyncMock()
        mock_get_health_service.return_value = mock_health_service
        mock_result = HealthCheckResult(
            overall_status=HealthStatus.DEGRADED,
            timestamp=datetime.now(),
            components={
                "database": ComponentHealth(
                    name="database",
                    component_type=ComponentType.DATABASE,
                    status=HealthStatus.DEGRADED,
                    last_check=datetime.now(),
                )
            },
        )
        mock_health_service.perform_comprehensive_health_check.return_value = (
            mock_result
        )

        # Act
        response = client.get("/health/core")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_redis_health_component_missing(self, mock_get_health_service, client):
        """Test /health/redis when the redis component is not in the health check."""
        # Arrange
        mock_health_service = MagicMock()
        mock_health_service.perform_comprehensive_health_check = AsyncMock()
        mock_get_health_service.return_value = mock_health_service
        mock_result = HealthCheckResult(
            overall_status=HealthStatus.HEALTHY,
            timestamp=datetime.now(),
            components={},  # No redis component
        )
        mock_health_service.perform_comprehensive_health_check.return_value = (
            mock_result
        )

        # Act
        response = client.get("/health/redis")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "critical"
        assert "Redis component not found" in data["message"]

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    def test_recover_component_http_exception(self, mock_get_health_service, client):
        """Test component recovery when an HTTPException is raised."""
        # Arrange
        mock_health_service = MagicMock()
        mock_health_service.attempt_recovery = AsyncMock(
            side_effect=HTTPException(status_code=404, detail="Not Found")
        )
        mock_get_health_service.return_value = mock_health_service

        # Act
        response = client.post("/health/component/database/recover")

        # Assert
        assert response.status_code == 404
        assert "Not Found" in response.text

    @patch("resync.api.health.shutdown_health_check_service", new_callable=AsyncMock)
    async def test_shutdown_health_service_exception(self, mock_shutdown):
        """Test that shutdown_health_service handles exceptions."""
        mock_shutdown.side_effect = Exception("boom")
        await shutdown_health_service()
        # No assert needed, we just want to make sure it doesn't raise

    @patch("resync.api.health.get_health_check_service", new_callable=AsyncMock)
    @patch("resync.api.health.runtime_metrics")
    def test_health_check_metrics_failure(
        self, mock_metrics, mock_get_health_service, client
    ):
        """Test that the health check handles metrics failures gracefully."""
        # Arrange
        mock_get_health_service.side_effect = Exception("Service not available")
        mock_metrics.health_check_with_auto_enable.increment.side_effect = Exception(
            "Metrics failure"
        )

        # Act
        response = client.get("/health/")

        # Assert
        assert response.status_code == 503
        assert "Service not available" in response.text
        # Check logs for the metrics failure warning
        # (This would require a more advanced logging capture mechanism)




