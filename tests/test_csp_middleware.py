"""Unit tests for CSP middleware functionality."""

from unittest.mock import Mock, patch
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from resync.api.middleware.csp_middleware import CSPMiddleware, create_csp_middleware
from resync.csp_validation import CSPValidationError


@pytest.fixture
def app_with_csp():
    """Create a FastAPI app with CSP middleware for testing."""
    app = FastAPI()

    # Add CSP middleware
    app.add_middleware(CSPMiddleware)

    @app.get("/test")
    async def test_endpoint(request: Request):
        """Test endpoint that returns CSP nonce."""
        nonce = getattr(request.state, "csp_nonce", None)
        return {"nonce": nonce}

    @app.get("/html")
    async def html_endpoint(request: Request):
        """Test endpoint that returns HTML with nonce."""
        nonce = getattr(request.state, "csp_nonce", "")
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Test</title></head>
        <body>
            <script nonce="{nonce}">console.log('test');</script>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)

    @app.post("/csp-violation-report")
    async def csp_violation_report(request: Request):
        """Handle CSP violation reports with enhanced validation and security."""
        try:
            from resync.csp_validation import process_csp_report, CSPValidationError

            # Process the CSP report with enhanced validation
            result = await process_csp_report(request)

            # Log specific violation details from sanitized data
            report = result.get("report", {})
            csp_report = (
                report.get("csp-report", {})
                if isinstance(report, dict) and "csp-report" in report
                else report
            )

            # Return 200 for all cases to avoid giving attackers information
            return {"status": "received"}

        except CSPValidationError:
            # Return 200 even for invalid reports to avoid giving attackers information
            return {"status": "received"}
        except Exception:
            # Return 200 even for processing errors to avoid giving attackers information
            return {"status": "received"}

    return app


@pytest.fixture
def app_with_csp_report_only():
    """Create a FastAPI app with CSP middleware in report-only mode."""
    app = FastAPI()

    # Add CSP middleware in report-only mode
    app.add_middleware(CSPMiddleware, report_only=True)

    @app.get("/test")
    async def test_endpoint(request: Request):
        """Test endpoint."""
        return {"status": "ok"}

    @app.post("/csp-violation-report")
    async def csp_violation_report(request: Request):
        """Handle CSP violation reports with enhanced validation and security."""
        try:
            from resync.csp_validation import process_csp_report, CSPValidationError

            # Process the CSP report with enhanced validation
            result = await process_csp_report(request)

            # Log specific violation details from sanitized data
            report = result.get("report", {})
            csp_report = (
                report.get("csp-report", {})
                if isinstance(report, dict) and "csp-report" in report
                else report
            )

            # Return 200 for all cases to avoid giving attackers information
            return {"status": "received"}

        except CSPValidationError:
            # Return 200 even for invalid reports to avoid giving attackers information
            return {"status": "received"}
        except Exception:
            # Return 200 even for processing errors to avoid giving attackers information
            return {"status": "received"}

    return app


@pytest.fixture
def app_without_csp():
    """Create a FastAPI app without CSP middleware."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint(request: Request):
        """Test endpoint."""
        return {"status": "ok"}

    @app.post("/csp-violation-report")
    async def csp_violation_report(request: Request):
        """Handle CSP violation reports with enhanced validation and security."""
        return {"status": "received"}

    return app


class TestCSPMiddleware:
    """Test cases for CSP middleware."""

    def test_csp_headers_present(self, app_with_csp):
        """Test that CSP headers are present in responses."""
        client = TestClient(app_with_csp)
        response = client.get("/test")

        assert response.status_code == 200
        assert "Content-Security-Policy" in response.headers
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers
        assert "X-XSS-Protection" in response.headers
        assert "Referrer-Policy" in response.headers

    def test_csp_policy_structure(self, app_with_csp):
        """Test that CSP policy has correct structure."""
        client = TestClient(app_with_csp)
        response = client.get("/test")

        csp_header = response.headers["Content-Security-Policy"]

        # Check for required directives
        assert "default-src 'self'" in csp_header
        assert "script-src 'self'" in csp_header
        assert "style-src 'self'" in csp_header
        assert "img-src 'self' data: blob: https:" in csp_header
        assert "font-src 'self' https: data:" in csp_header
        assert "connect-src 'self'" in csp_header
        assert "frame-ancestors 'none'" in csp_header
        assert "base-uri 'self'" in csp_header
        assert "form-action 'self'" in csp_header
        assert "object-src 'none'" in csp_header
        assert "child-src 'self'" in csp_header

    def test_nonce_generation(self, app_with_csp):
        """Test that nonce is generated for each request."""
        client = TestClient(app_with_csp)

        # Make multiple requests
        response1 = client.get("/test")
        response2 = client.get("/test")

        data1 = response1.json()
        data2 = response2.json()

        # Nonces should be different for each request
        assert data1["nonce"] != data2["nonce"]

        # Nonces should be 24 characters (16 bytes in base64)
        assert len(data1["nonce"]) == 24
        assert len(data2["nonce"]) == 24

    def test_nonce_in_csp_header(self, app_with_csp):
        """Test that nonce is included in CSP header."""
        client = TestClient(app_with_csp)
        response = client.get("/test")

        csp_header = response.headers["Content-Security-Policy"]
        data = response.json()

        # CSP header should contain the nonce
        assert f"'nonce-{data['nonce']}'" in csp_header

    def test_csp_report_only_mode(self, app_with_csp_report_only):
        """Test CSP middleware in report-only mode."""
        client = TestClient(app_with_csp_report_only)
        response = client.get("/test")

        # Should have Content-Security-Policy-Report-Only header instead
        assert "Content-Security-Policy-Report-Only" in response.headers
        assert "Content-Security-Policy" not in response.headers

    def test_csp_violation_report_endpoint_valid(self, app_with_csp):
        """Test CSP violation report endpoint with valid report."""
        client = TestClient(app_with_csp)

        # Send a valid CSP violation report
        report_data = {
            "csp-report": {
                "document-uri": "https://example.com/test",
                "referrer": "",
                "violated-directive": "script-src 'self'",
                "effective-directive": "script-src",
                "original-policy": "default-src 'self'; script-src 'self'",
                "disposition": "enforce",
                "blocked-uri": "inline",
                "line-number": 10,
                "column-number": 20,
                "source-file": "https://example.com/test",
                "status-code": 200,
                "script-sample": "",
            }
        }

        response = client.post("/csp-violation-report", json=report_data)
        assert response.status_code == 200
        assert response.json() == {"status": "received"}

    def test_csp_violation_report_endpoint_invalid(self, app_with_csp):
        """Test CSP violation report endpoint with invalid report."""
        client = TestClient(app_with_csp)

        # Send an invalid CSP violation report (missing required fields)
        report_data = {
            "csp-report": {
                "document-uri": "https://example.com/test"
                # Missing required fields
            }
        }

        response = client.post("/csp-violation-report", json=report_data)
        # Should still return 200 to avoid giving attackers information
        assert response.status_code == 200
        assert response.json() == {"status": "received"}

    def test_html_template_with_nonce(self, app_with_csp):
        """Test HTML template that uses CSP nonce."""
        client = TestClient(app_with_csp)
        response = client.get("/html")

        assert response.status_code == 200
        assert "Content-Security-Policy" in response.headers

        # Parse the HTML response
        html_content = response.text

        # Should contain a script tag with nonce attribute
        assert "nonce=" in html_content
        assert "console.log" in html_content

    def test_csp_disabled_via_settings(self, monkeypatch):
        """Test that CSP can be disabled via settings."""
        # Mock settings to disable CSP
        mock_settings = Mock()
        mock_settings.CSP_ENABLED = False
        mock_settings.CSP_REPORT_ONLY = False

        app = FastAPI()

        # Patch the settings import in the middleware
        with patch("resync.settings.settings", mock_settings):
            # Create middleware with CSP disabled
            middleware = create_csp_middleware(app)

        # Should return a no-op middleware when CSP is disabled
        from starlette.middleware.base import BaseHTTPMiddleware

        assert isinstance(middleware, BaseHTTPMiddleware)


class TestCSPConfiguration:
    """Test CSP configuration options."""

    def test_csp_report_uri_configuration(self, monkeypatch):
        """Test CSP report URI configuration."""
        # Mock settings with report URI
        mock_settings = Mock()
        mock_settings.CSP_REPORT_URI = "/custom-report-uri"

        app = FastAPI()

        # Patch the settings import in the middleware
        with patch("resync.settings.settings", mock_settings):
            app.add_middleware(CSPMiddleware)

        @app.get("/test")
        async def test_endpoint(request: Request):
            return {"status": "ok"}

        @app.post("/csp-violation-report")
        async def csp_violation_report(request: Request):
            return {"status": "received"}

        client = TestClient(app)
        response = client.get("/test")

        csp_header = response.headers["Content-Security-Policy"]
        assert "report-uri /custom-report-uri" in csp_header

    def test_csp_directives_customization(self):
        """Test that CSP directives can be customized."""
        app = FastAPI()

        # Create custom CSP middleware with modified directives
        class CustomCSPMiddleware(CSPMiddleware):
            def _generate_csp_policy(self, nonce: str) -> str:
                """Override to test custom directives."""
                return "default-src 'none'; script-src 'none'"

        app.add_middleware(CustomCSPMiddleware)

        @app.get("/test")
        async def test_endpoint(request: Request):
            return {"status": "ok"}

        @app.post("/csp-violation-report")
        async def csp_violation_report(request: Request):
            return {"status": "received"}

        client = TestClient(app)
        response = client.get("/test")

        csp_header = response.headers["Content-Security-Policy"]
        assert csp_header == "default-src 'none'; script-src 'none'"


class TestCSPValidationErrorHandling:
    """Test error handling in CSP validation."""

    @patch("resync.csp_validation.process_csp_report")
    def test_csp_violation_report_processing_error(
        self, mock_process_csp_report, app_with_csp
    ):
        """Test CSP violation report endpoint when processing fails."""
        # Mock the process_csp_report function to raise an exception
        mock_process_csp_report.side_effect = Exception("Processing failed")

        client = TestClient(app_with_csp)

        # Send a CSP violation report
        report_data = {
            "csp-report": {
                "document-uri": "https://example.com/test",
                "violated-directive": "script-src 'self'",
                "original-policy": "default-src 'self'; script-src 'self'",
            }
        }

        response = client.post("/csp-violation-report", json=report_data)
        # Should still return 200 to avoid giving attackers information
        assert response.status_code == 200
        assert response.json() == {"status": "received"}

    @patch("resync.csp_validation.process_csp_report")
    def test_csp_violation_report_validation_error(
        self, mock_process_csp_report, app_with_csp
    ):
        """Test CSP violation report endpoint when validation fails."""
        # Mock the process_csp_report function to raise a validation error
        mock_process_csp_report.side_effect = CSPValidationError(
            "Invalid report format"
        )

        client = TestClient(app_with_csp)

        # Send a CSP violation report
        report_data = {
            "csp-report": {
                "document-uri": "https://example.com/test",
                "violated-directive": "script-src 'self'",
                "original-policy": "default-src 'self'; script-src 'self'",
            }
        }

        response = client.post("/csp-violation-report", json=report_data)
        # Should still return 200 to avoid giving attackers information
        assert response.status_code == 200
        assert response.json() == {"status": "received"}


if __name__ == "__main__":
    pytest.main([__file__])
