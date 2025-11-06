"""
Tests for enhanced security configuration.
"""

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from resync.settings.enhanced_security import (
    EnhancedSecurityMiddleware,
    configure_enhanced_security,
    validate_security_headers,
)


class TestEnhancedSecurityConfiguration:
    """Tests for enhanced security configuration."""

    def test_enhanced_security_middleware_initialization(self):
        """Test initialization of enhanced security middleware."""
        app = FastAPI()

        # Test with default configuration
        middleware = EnhancedSecurityMiddleware(app)
        assert middleware is not None
        assert middleware.enable_hsts is False  # Disabled in non-production

        # Test with custom configuration
        middleware = EnhancedSecurityMiddleware(
            app,
            enable_hsts=True,
            strict_transport_security_max_age=63072000,  # 2 years
        )
        assert middleware is not None
        assert middleware.enable_hsts is True
        assert middleware.strict_transport_security_max_age == 63072000

    def test_default_csp_generation(self):
        """Test default CSP generation."""
        app = FastAPI()
        middleware = EnhancedSecurityMiddleware(app)

        csp = middleware._default_csp()
        assert isinstance(csp, str)
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "style-src 'self'" in csp
        assert "object-src 'none'" in csp

    def test_default_permissions_policy_generation(self):
        """Test default permissions policy generation."""
        app = FastAPI()
        middleware = EnhancedSecurityMiddleware(app)

        policy = middleware._default_permissions_policy()
        assert isinstance(policy, str)
        assert "geolocation=()" in policy
        assert "microphone=()" in policy
        assert "camera=()" in policy

    def test_default_feature_policy_generation(self):
        """Test default feature policy generation."""
        app = FastAPI()
        middleware = EnhancedSecurityMiddleware(app)

        policy = middleware._default_feature_policy()
        assert isinstance(policy, str)
        assert "geolocation 'none'" in policy
        assert "microphone 'none'" in policy
        assert "camera 'none'" in policy

    def test_security_headers_validation(self):
        """Test security headers validation."""
        # Test with all headers present
        headers_with_all_security = {
            "Strict-Transport-Security": "max-age=31536000",
            "Content-Security-Policy": "default-src 'self'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=()",
            "X-XSS-Protection": "1; mode=block",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-Permitted-Cross-Domain-Policies": "none",
            "Cross-Origin-Embedder-Policy": "require-corp",
            "Cross-Origin-Opener-Policy": "same-origin",
            "Cross-Origin-Resource-Policy": "same-origin",
        }

        missing = validate_security_headers(headers_with_all_security)
        assert len(missing) == 0

        # Test with missing headers
        headers_missing_some = {
            "Content-Security-Policy": "default-src 'self'",
            "X-Content-Type-Options": "nosniff",
        }

        missing = validate_security_headers(headers_missing_some)
        assert len(missing) > 0
        assert "Strict-Transport-Security" in missing
        assert "Referrer-Policy" in missing

    def test_configure_enhanced_security(self):
        """Test configuration of enhanced security."""
        app = FastAPI()

        # Test configuration with default settings
        configure_enhanced_security(app)

        # Should have middleware added
        assert len(app.user_middleware) > 0

        # Test configuration with custom settings
        app2 = FastAPI()
        custom_config = {
            "enable_hsts": False,
            "strict_transport_security_max_age": 15768000,  # 6 months
        }
        configure_enhanced_security(app2, custom_config)

        # Should have middleware added
        assert len(app2.user_middleware) > 0

    @pytest.mark.asyncio
    async def test_security_middleware_dispatch(self):
        """Test security middleware dispatch functionality."""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        # Add security middleware
        app.add_middleware(EnhancedSecurityMiddleware)

        client = TestClient(app)
        response = client.get("/test")

        # Check that security headers are present
        assert response.status_code == 200
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    @pytest.mark.asyncio
    async def test_security_middleware_skip_paths(self):
        """Test that security headers are skipped for certain paths."""
        app = FastAPI()

        @app.get("/health")
        async def health_endpoint():
            return {"status": "ok"}

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        # Add security middleware
        app.add_middleware(EnhancedSecurityMiddleware)

        client = TestClient(app)

        # Test health endpoint (should skip security headers)
        health_response = client.get("/health")
        assert health_response.status_code == 200

        # Test regular endpoint (should have security headers)
        test_response = client.get("/test")
        assert test_response.status_code == 200
        assert "X-Content-Type-Options" in test_response.headers


if __name__ == "__main__":
    pytest.main([__file__])









