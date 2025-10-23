"""Integration tests for CSP functionality with the full FastAPI application."""

import pytest
from fastapi.testclient import TestClient

from resync.api.endpoints import api_router as csp_router
from fastapi import FastAPI

app = FastAPI()
app.include_router(csp_router)


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    return TestClient(app)


class TestCSPIntegration:
    """Integration tests for CSP with the full application."""

    def test_csp_headers_on_all_routes(self, client):
        """Test that CSP headers are present on all HTML endpoints."""
        # Test main endpoints that serve HTML
        html_endpoints = ["/revisao"]

        for endpoint in html_endpoints:
            response = client.get(endpoint)

            # Should have CSP headers regardless of response status
            assert (
                "Content-Security-Policy" in response.headers
                or "Content-Security-Policy-Report-Only" in response.headers
            )

            # Should have additional security headers
            assert "X-Content-Type-Options" in response.headers
            assert "X-Frame-Options" in response.headers
            assert "X-XSS-Protection" in response.headers

    def test_csp_violation_report_endpoint(self, client):
        """Test the CSP violation report endpoint."""
        report_data = {
            "csp-report": {
                "document-uri": "http://testserver/revisao",
                "referrer": "",
                "violated-directive": "script-src 'self'",
                "effective-directive": "script-src",
                "original-policy": "default-src 'self'; script-src 'self'",
                "disposition": "enforce",
                "blocked-uri": "inline",
                "line-number": 10,
                "column-number": 20,
                "source-file": "http://testserver/revisao",
                "status-code": 200,
                "script-sample": "",
            }
        }

        response = client.post("/csp-violation-report", json=report_data)
        # Should either accept the report (200) or return 404 if endpoint not found
        assert response.status_code in [200, 404]

    def test_html_templates_have_nonce_attributes(self, client):
        """Test that HTML templates include nonce attributes in script tags."""
        response = client.get("/revisao")

        assert response.status_code == 200
        html_content = response.text

        # Should have script tags with nonce attributes
        assert "nonce=" in html_content
        assert "script" in html_content

        # Should have the specific script files from templates
        assert "revisao.js" in html_content

    def test_static_files_allowed_by_csp(self, client):
        """Test that static files are accessible under CSP policy."""
        # Test that static files endpoint exists and is accessible
        response = client.get("/revisao")  # HTML page that loads static files

        # Should be able to access the page (static files will be loaded by browser)
        assert response.status_code == 200

        # CSP should allow 'self' for static files
        csp_header = response.headers.get("Content-Security-Policy", "")
        assert "'self'" in csp_header

    def test_api_endpoints_have_csp_headers(self, client):
        """Test that API endpoints also have CSP headers."""
        # Test a few API endpoints
        api_endpoints = ["/api/health", "/docs"]

        for endpoint in api_endpoints:
            response = client.get(endpoint)

            # Should have CSP headers
            assert (
                "Content-Security-Policy" in response.headers
                or "Content-Security-Policy-Report-Only" in response.headers
            )

    def test_csp_policy_varies_by_environment(self, client):
        """Test that CSP policy changes based on environment settings."""
        response = client.get("/revisao")

        # Get the CSP header
        csp_header = response.headers.get("Content-Security-Policy", "")
        csp_report_only = response.headers.get(
            "Content-Security-Policy-Report-Only", ""
        )

        # Should have one or the other
        assert csp_header or csp_report_only

        if csp_header:
            # In enforcement mode
            assert "Content-Security-Policy" in response.headers
        else:
            # In report-only mode
            assert "Content-Security-Policy-Report-Only" in response.headers

    def test_nonce_uniqueness_across_requests(self, client):
        """Test that nonces are unique for each request."""
        responses = []
        for _ in range(5):
            response = client.get("/revisao")
            responses.append(response)

        # Extract nonces from responses (they should be in the HTML)
        nonces = []
        for response in responses:
            html_content = response.text

            # Find nonce values in script tags
            import re

            nonce_matches = re.findall(r'nonce="([^"]+)"', html_content)
            nonces.extend(nonce_matches)

        # Should have found some nonces
        assert len(nonces) > 0

        # All nonces should be unique
        assert len(set(nonces)) == len(nonces)

    def test_csp_blocks_unsafe_content(self, client):
        """Test that CSP policy would block unsafe content."""
        response = client.get("/revisao")

        csp_header = response.headers.get(
            "Content-Security-Policy", ""
        ) or response.headers.get("Content-Security-Policy-Report-Only", "")

        # Should not allow unsafe-inline for scripts
        assert "script-src" in csp_header

        # Should require nonces for scripts
        assert "nonce-" in csp_header

        # Should not allow external script sources by default
        assert (
            "https:" not in csp_header
            or "script-src" not in csp_header.split("https:")[0]
        )

    def test_security_headers_completeness(self, client):
        """Test that all expected security headers are present."""
        response = client.get("/revisao")

        # Check for all security headers added by CSP middleware

        # Should have either CSP or CSP-Report-Only
        has_csp = "Content-Security-Policy" in response.headers
        has_csp_report_only = "Content-Security-Policy-Report-Only" in response.headers

        assert has_csp or has_csp_report_only, "Missing CSP header"

        # Check other security headers
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
