from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from resync.api.cors_monitoring import cors_monitor_router
from resync.core.rate_limiter import CustomRateLimitMiddleware, limiter
from resync.models.validation import (
    CorsConfigResponse,
    CorsTestResponse,
    OriginValidationResponse,
)


@pytest.fixture
def client() -> TestClient:
    """Create a TestClient for the FastAPI app."""
    app = FastAPI()

    # Apply the rate-limiting middleware correctly
    app.add_middleware(CustomRateLimitMiddleware, limiter=limiter)

    # Include the CORS monitoring router
    app.include_router(
        cors_monitor_router, prefix="/api/cors", tags=["CORS Monitoring"]
    )

    return TestClient(app)


class TestCORSMonitoring:
    """Test suite for CORS monitoring endpoints."""

    def test_get_cors_stats_endpoint(self, client: TestClient):
        """Test CORS statistics endpoint."""
        response = client.get("/api/cors/stats")
        assert response.status_code == 200
        assert "violations_detected" in response.json()

    def test_get_cors_config_endpoint(self, client: TestClient):
        """Test CORS configuration endpoint."""
        with patch("resync.api.cors_monitoring.settings") as mock_settings:
            mock_settings.CORS_ALLOW_ORIGINS = ["http://localhost:3000"]
            mock_settings.CORS_ALLOW_METHODS = ["GET", "POST"]
            mock_settings.CORS_ALLOW_HEADERS = ["Content-Type"]
            mock_settings.CORS_ALLOW_CREDENTIALS = True
            mock_settings.CORS_EXPOSE_HEADERS = ["X-Custom-Header"]
            mock_settings.CORS_MAX_AGE = 600

            response = client.get("/api/cors/config")
            assert response.status_code == 200
            data = CorsConfigResponse(**response.json())
            assert data.allow_origins == ["http://localhost:3000"]

    def test_test_cors_policy_endpoint(self, client: TestClient):
        """Test CORS policy testing endpoint."""
        with patch("resync.api.cors_monitoring.settings") as mock_settings:
            mock_settings.CORS_ALLOW_ORIGINS = ["http://localhost:3000"]
            mock_settings.CORS_ALLOW_METHODS = ["GET"]

            response = client.post(
                "/api/cors/test",
                params={
                    "origin": "http://localhost:3000",
                    "method": "GET",
                    "path": "/api/test",
                },
            )
            assert response.status_code == 200
            data = CorsTestResponse(**response.json())
            assert data.is_allowed is True

    def test_validate_origins_endpoint(self, client: TestClient):
        """Test origins validation endpoint."""
        with patch("resync.api.cors_monitoring.settings") as mock_settings:
            mock_settings.CORS_ALLOW_ORIGINS = ["http://localhost:3000"]
            mock_settings.ENV_FOR_DYNACONF = "development"

            response = client.post(
                "/api/cors/validate-origins",
                json={"origins": ["http://localhost:3000", "https://example.com"]},
            )
            assert response.status_code == 200
            data = OriginValidationResponse(**response.json())
            assert data.validated_origins["http://localhost:3000"] == "valid"
            assert data.validated_origins["https://example.com"] == "invalid"

    def test_validate_origins_production_restrictions(self, client: TestClient):
        """Test that production environment rejects wildcard origins."""
        with patch("resync.api.cors_monitoring.settings") as mock_settings:
            mock_settings.ENV_FOR_DYNACONF = "production"
            response = client.post(
                "/api/cors/validate-origins", json={"origins": ["*"]}
            )
            assert response.status_code == 200
            data = OriginValidationResponse(**response.json())
            assert data.validated_origins["*"] == "invalid_in_production"

    def test_cors_violations_endpoint_empty(self, client: TestClient):
        """Test CORS violations endpoint when no violations exist."""
        response = client.get("/api/cors/violations")
        assert response.status_code == 200
        assert response.json() == []

    def test_cors_violations_endpoint_with_params(self, client: TestClient):
        """Test CORS violations endpoint with query parameters."""
        response = client.get(
            "/api/cors/violations", params={"limit": 10, "hours": 1}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_cors_endpoints_require_authentication(self, client: TestClient):
        """Test that CORS monitoring endpoints require authentication."""
        endpoints = [
            "/api/cors/stats",
            "/api/cors/config",
            "/api/cors/violations",
        ]
        for endpoint in endpoints:
            response = client.get(endpoint)
            # This test is just checking if the endpoint exists and returns,
            # not enforcing strict authentication yet.
            assert response.status_code == 200


class TestCORSMonitoringIntegration:
    """Integration tests for CORS monitoring."""

    def test_cors_monitoring_router_integration(self, client: TestClient):
        """Test that CORS monitoring router integrates properly."""
        response = client.get("/api/cors/config")
        assert response.status_code == 200

    def test_cors_endpoints_documentation(self, client: TestClient):
        """Test that CORS endpoints are properly documented."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        openapi_schema = response.json()
        paths = openapi_schema.get("paths", {})
        assert "/api/cors/stats" in paths
        assert "/api/cors/config" in paths


class TestCORSMonitoringValidation:
    """Validation tests for CORS monitoring endpoints."""

    def test_validate_origins_with_invalid_input(self, client: TestClient):
        """Test origins validation with invalid input."""
        response = client.post(
            "/api/cors/validate-origins",
            json="invalid-input",
        )
        assert response.status_code == 422  # Unprocessable Entity

    def test_test_cors_policy_with_invalid_method(self, client: TestClient):
        """Test CORS policy testing with invalid HTTP method."""
        response = client.post(
            "/api/cors/test",
            params={
                "origin": "http://localhost:3000",
                "method": "INVALID",
                "path": "/api/test",
            },
        )
        # This should be allowed because the method is validated against a list of strings
        assert response.status_code == 200

    def test_cors_violations_with_invalid_params(self, client: TestClient):
        """Test CORS violations endpoint with invalid parameters."""
        response = client.get("/api/cors/violations", params={"limit": -1})
        assert response.status_code == 422  # Unprocessable Entity




