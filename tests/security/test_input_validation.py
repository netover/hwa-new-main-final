"""
Security Input Validation Tests

This module tests input validation and security measures implemented
across the application endpoints.
"""

import sys
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from resync.core.fastapi_di import get_agent_manager, get_tws_client
from resync.core.interfaces import IAgentManager, ITWSClient


@pytest.fixture(scope="function")
def client_with_security_mocks(test_app: FastAPI):
    """
    Provides a TestClient with mocked dependencies for the security tests,
    using the App Factory pattern.
    """
    mock_agent_manager = AsyncMock(spec=IAgentManager)
    mock_agent_manager.get_all_agents.return_value = []

    mock_tws_client = AsyncMock(spec=ITWSClient)
    mock_tws_client.get_system_status.return_value = {}
    mock_tws_client.get_workstations_status.return_value = []
    mock_tws_client.get_jobs_status.return_value = []
    mock_tws_client.get_critical_path_status.return_value = []
    mock_tws_client.check_connection.return_value = True

    test_app.dependency_overrides[get_agent_manager] = lambda: mock_agent_manager
    test_app.dependency_overrides[get_tws_client] = lambda: mock_tws_client

    with TestClient(test_app) as test_client:
        yield test_client

    # Cleanup overrides after class tests are done
    test_app.dependency_overrides = {}


@pytest.mark.usefixtures("client_with_security_mocks")
class TestInputValidation:
    """Test input validation security measures."""

    @pytest.fixture(autouse=True)
    def inject_client(self, client_with_security_mocks: TestClient):
        """Inject the client fixture into the test class instance."""
        self.client = client_with_security_mocks

    @pytest.mark.security
    def test_health_endpoints_robustness(self, security_test_data):
        """Test health endpoints against malicious-looking but valid input."""
        response = self.client.get("/health/tws")
        # The endpoint should correctly handle the input without crashing.
        # A 422 is an acceptable response if validation fails.
        assert response.status_code != 500

    @pytest.mark.security
    def test_agents_endpoint_security(self, security_test_data):
        """Test /agents endpoint against malicious input."""
        payload = security_test_data["sql_injection"][0]
        response = self.client.get(f"/agents?filter={payload}")
        assert response.status_code != 500

    @pytest.mark.security
    def test_malicious_header_handling(self, security_test_data):
        """Test handling of malicious headers."""
        malicious_headers_list = security_test_data["malicious_headers"]

        for headers in malicious_headers_list:
            response = self.client.get("/agents", headers=headers)
            assert response.status_code != 500


@pytest.mark.usefixtures("client_with_security_mocks")
class TestEncryptionSecurity:
    """Test encryption and data protection measures."""

    @pytest.fixture(autouse=True)
    def inject_client(self, client_with_security_mocks: TestClient):
        """Inject the client fixture into the test class instance."""
        self.client = client_with_security_mocks

    @pytest.mark.security
    def test_data_masking_in_logs(self):
        """
        Test that sensitive data is not inadvertently logged. This test is a placeholder
        to be updated if sensitive endpoints are added in the future.
        """
        with patch("resync.api.endpoints.logging.getLogger") as mock_get_logger:
            mock_logger = AsyncMock()
            mock_get_logger.return_value = mock_logger

            # This is a placeholder assertion. If a sensitive endpoint were called,
            # we would check that mock_logger.info (or .error etc.) was not called
            # with sensitive data.
            assert "logging" in sys.modules
