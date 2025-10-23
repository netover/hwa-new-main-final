"""
Integration tests for healthcheck endpoints.
"""

from fastapi.testclient import TestClient


class TestHealthcheckIntegration:
    """Integration tests for healthcheck endpoints."""

    def test_global_health_endpoint(self, client: TestClient):
        """Test global health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "correlation_id" in data
        assert "components" in data
        assert "subsystems" in data

        # Check subsystems
        subsystems = data["subsystems"]
        assert "core" in subsystems
        assert "infrastructure" in subsystems
        assert "services" in subsystems

    def test_core_health_endpoint(self, client: TestClient):
        """Test core health endpoint."""
        response = client.get("/health/core")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "correlation_id" in data
        assert "components" in data

    def test_infrastructure_health_endpoint(self, client: TestClient):
        """Test infrastructure health endpoint."""
        response = client.get("/health/infrastructure")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "correlation_id" in data
        assert "components" in data

    def test_services_health_endpoint(self, client: TestClient):
        """Test services health endpoint."""
        response = client.get("/health/services")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "correlation_id" in data
        assert "components" in data

    def test_di_health_endpoint(self, client: TestClient):
        """Test DI container health endpoint."""
        response = client.get("/health/di")
        assert response.status_code == 200

        data = response.json()
        assert "overall_status" in data
        assert "services" in data
        assert "timestamp" in data
        assert "correlation_id" in data

    def test_config_validation_endpoint(self, client: TestClient):
        """Test configuration validation endpoint."""
        response = client.get("/config/validate")
        assert response.status_code == 200

        data = response.json()

        # Should return some validation result
        assert isinstance(data, dict)
        assert data.get("overall_status") == "valid"
        assert "correlation_id" in data
        assert len(data.get("missing_variables", [])) == 0
        assert len(data.get("invalid_variables", [])) == 0
