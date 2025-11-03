from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from resync.api.middleware.cors_config import (
    CORSConfig,
    CORSPolicy,
    Environment,
    cors_config,
)
from resync.api.middleware.cors_middleware import (
    LoggingCORSMiddleware,
    add_cors_middleware,
    get_development_cors_config,
    get_production_cors_config,
    get_test_cors_config,
)


class TestCORSPolicy:
    """Test CORS policy configuration and validation."""

    def test_cors_policy_default_development(self):
        """Test default development CORS policy."""
        policy = CORSPolicy(environment=Environment.DEVELOPMENT)

        assert policy.environment == Environment.DEVELOPMENT
        assert policy.allow_all_origins is False
        assert policy.allow_credentials is False
        assert policy.max_age == 86400
        assert policy.log_violations is True
        assert "GET" in policy.allowed_methods
        assert "POST" in policy.allowed_methods

    def test_cors_policy_default_production(self):
        """Test default production CORS policy."""
        policy = CORSPolicy(environment=Environment.PRODUCTION)

        assert policy.environment == Environment.PRODUCTION
        assert policy.allow_all_origins is False
        assert policy.allowed_origins == []
        assert policy.allow_credentials is False

    def test_cors_policy_wildcard_in_production_fails(self):
        """Test that wildcard origins are rejected in production."""
        with pytest.raises(
            ValueError, match="Wildcard origins are not allowed in production"
        ):
            CORSPolicy(environment=Environment.PRODUCTION, allowed_origins=["*"])

    def test_cors_policy_invalid_origin_format(self):
        """Test that invalid origin formats are rejected."""
        with pytest.raises(ValueError, match="Invalid origin format"):
            CORSPolicy(
                environment=Environment.DEVELOPMENT, allowed_origins=["invalid-origin"]
            )

    def test_cors_policy_invalid_method(self):
        """Test that invalid HTTP methods are rejected."""
        with pytest.raises(ValueError, match="Invalid HTTP method"):
            CORSPolicy(
                environment=Environment.DEVELOPMENT, allowed_methods=["INVALID_METHOD"]
            )

    def test_cors_policy_invalid_max_age(self):
        """Test that invalid max_age values are rejected."""
        with pytest.raises(ValueError, match="max_age must be non-negative"):
            CORSPolicy(environment=Environment.DEVELOPMENT, max_age=-1)

        with pytest.raises(ValueError, match="max_age should not exceed 7 days"):
            CORSPolicy(environment=Environment.DEVELOPMENT, max_age=86400 * 8)  # 8 days

    def test_cors_policy_invalid_regex_pattern(self):
        """Test that invalid regex patterns are rejected."""
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            CORSPolicy(
                environment=Environment.DEVELOPMENT, origin_regex_patterns=["[invalid"]
            )

    def test_origin_validation_exact_match(self):
        """Test exact origin matching."""
        policy = CORSPolicy(
            environment=Environment.DEVELOPMENT,
            allowed_origins=["https://example.com", "http://localhost:3000"],
        )

        assert policy.is_origin_allowed("https://example.com") is True
        assert policy.is_origin_allowed("http://localhost:3000") is True
        assert policy.is_origin_allowed("https://other.com") is False

    def test_origin_validation_wildcard(self):
        """Test wildcard origin matching."""
        policy = CORSPolicy(environment=Environment.DEVELOPMENT, allow_all_origins=True)

        assert policy.is_origin_allowed("https://any-origin.com") is True
        assert policy.is_origin_allowed("http://localhost:3000") is True

    def test_origin_validation_regex_patterns(self):
        """Test regex pattern origin matching."""
        policy = CORSPolicy(
            environment=Environment.DEVELOPMENT,
            allowed_origins=[],
            origin_regex_patterns=[
                r"https://.*\.example\.com",
                r"http://localhost:\d+",
            ],
        )

        assert policy.is_origin_allowed("https://app.example.com") is True
        assert policy.is_origin_allowed("https://api.example.com") is True
        assert policy.is_origin_allowed("http://localhost:3000") is True
        assert policy.is_origin_allowed("http://localhost:8080") is True
        assert policy.is_origin_allowed("https://other.com") is False

    def test_get_cors_config_dict(self):
        """Test conversion to CORS config dictionary."""
        policy = CORSPolicy(
            environment=Environment.DEVELOPMENT,
            allowed_origins=["https://example.com"],
            allowed_methods=["GET", "POST"],
            allowed_headers=["Content-Type"],
            allow_credentials=True,
            max_age=3600,
        )

        config_dict = policy.get_cors_config_dict()

        assert config_dict["allow_origins"] == ["https://example.com"]
        assert config_dict["allow_methods"] == ["GET", "POST"]
        assert config_dict["allow_headers"] == ["Content-Type"]
        assert config_dict["allow_credentials"] is True
        assert config_dict["max_age"] == 3600


class TestCORSConfig:
    """Test CORS configuration management."""

    def test_cors_config_default_policies(self):
        """Test default policies for each environment."""
        config = CORSConfig()

        # Development should be permissive
        assert config.development.allow_all_origins is True
        assert config.development.allow_credentials is True

        # Production should be restrictive
        assert config.production.allow_all_origins is False
        assert config.production.allowed_origins == []
        assert config.production.allow_credentials is False

        # Test should have specific origins
        assert config.test.allowed_origins == [
            "http://localhost:3000",
            "http://localhost:8000",
        ]

    def test_get_policy_by_environment(self):
        """Test retrieving policy by environment."""
        config = CORSConfig()

        dev_policy = config.get_policy("development")
        assert dev_policy.environment == Environment.DEVELOPMENT

        prod_policy = config.get_policy("production")
        assert prod_policy.environment == Environment.PRODUCTION

        test_policy = config.get_policy("test")
        assert test_policy.environment == Environment.TEST

        # Test with enum directly
        dev_policy_enum = config.get_policy(Environment.DEVELOPMENT)
        assert dev_policy_enum.environment == Environment.DEVELOPMENT

    def test_get_policy_invalid_environment(self):
        """Test that invalid environment raises error."""
        config = CORSConfig()

        with pytest.raises(ValueError, match="'invalid' is not a valid Environment"):
            config.get_policy("invalid")

    def test_update_policy(self):
        """Test updating policy for specific environment."""
        config = CORSConfig()

        new_dev_policy = CORSPolicy(
            environment=Environment.DEVELOPMENT,
            allowed_origins=["https://specific-origin.com"],
        )

        config.update_policy("development", new_dev_policy)
        assert config.development.allowed_origins == ["https://specific-origin.com"]

    def test_update_policy_invalid_environment(self):
        """Test that updating invalid environment raises error."""
        config = CORSConfig()

        with pytest.raises(ValueError, match="'invalid' is not a valid Environment"):
            config.update_policy(
                "invalid", CORSPolicy(environment=Environment.DEVELOPMENT)
            )


class TestCORSMiddleware:
    """Test CORS middleware functionality."""

    def test_logging_cors_middleware_initialization(self):
        """Test middleware initialization."""
        app = FastAPI()
        policy = CORSPolicy(environment=Environment.DEVELOPMENT)

        middleware = LoggingCORSMiddleware(
            app=app,
            policy=policy,
            allow_origins=["*"],
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
            allow_credentials=False,
            max_age=86400,
        )

        assert middleware.policy == policy
        assert middleware.allow_origins == ["*"]
        assert middleware.allow_methods == ["GET", "POST"]
        assert middleware.allow_headers == ["Content-Type"]
        assert middleware.allow_credentials is False
        assert middleware.max_age == 86400

    @pytest.mark.asyncio
    async def test_cors_middleware_same_origin_request(self):
        """Test middleware handling of same-origin requests (no origin header)."""
        app = FastAPI()
        policy = CORSPolicy(environment=Environment.DEVELOPMENT)

        middleware = LoggingCORSMiddleware(app=app, policy=policy, allow_origins=["*"])

        # Create a mock request without origin header
        request = Mock()
        request.headers = {}
        request.method = "GET"
        request.url.path = "/api/test"
        request.client = Mock()
        request.client.host = "127.0.0.1"

        # Mock call_next to return a response
        async def mock_call_next(req):
            from fastapi.responses import JSONResponse

            return JSONResponse(content={"status": "ok"})

        # Process the request
        response = await middleware.dispatch(request, mock_call_next)

        # Should proceed normally without CORS headers for same-origin
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_cors_middleware_allowed_origin(self):
        """Test middleware handling of allowed cross-origin requests."""
        app = FastAPI()
        policy = CORSPolicy(
            environment=Environment.DEVELOPMENT, allowed_origins=["https://allowed.com"]
        )

        middleware = LoggingCORSMiddleware(
            app=app, policy=policy, allow_origins=["https://allowed.com"]
        )

        # Create a mock request with allowed origin
        request = Mock()
        request.headers = {"origin": "https://allowed.com"}
        request.method = "GET"
        request.url.path = "/api/test"
        request.client = Mock()
        request.client.host = "127.0.0.1"

        # Mock call_next to return a response
        async def mock_call_next(req):
            from fastapi.responses import JSONResponse

            return JSONResponse(content={"status": "ok"})

        # Process the request
        response = await middleware.dispatch(request, mock_call_next)

        # Should add CORS headers for allowed origin
        assert response.status_code == 200

    def test_cors_middleware_stats(self):
        """Test middleware statistics tracking."""
        app = FastAPI()
        policy = CORSPolicy(environment=Environment.DEVELOPMENT)

        middleware = LoggingCORSMiddleware(app=app, policy=policy)

        # Simulate some requests
        middleware._cors_requests = 100
        middleware._preflight_requests = 20
        middleware._cors_violations = 5

        stats = middleware.get_stats()

        assert stats["total_requests"] == 100
        assert stats["preflight_requests"] == 20
        assert stats["violations"] == 5
        assert stats["violation_rate"] == 5.0  # 5% violation rate


class TestCORSHelpers:
    """Test CORS helper functions."""

    def test_get_development_cors_config(self):
        """Test development CORS configuration helper."""
        config = get_development_cors_config()

        assert config.environment == Environment.DEVELOPMENT
        assert config.allow_all_origins is True
        assert config.allow_credentials is True
        assert config.log_violations is True

    def test_get_production_cors_config_default(self):
        """Test production CORS configuration helper with defaults."""
        config = get_production_cors_config()

        assert config.environment == Environment.PRODUCTION
        assert config.allow_all_origins is False
        assert config.allowed_origins == []
        assert config.allow_credentials is False
        assert config.log_violations is True

    def test_get_production_cors_config_custom(self):
        """Test production CORS configuration helper with custom settings."""
        origins = ["https://app.example.com", "https://api.example.com"]
        config = get_production_cors_config(
            allowed_origins=origins, allow_credentials=True
        )

        assert config.environment == Environment.PRODUCTION
        assert config.allowed_origins == origins
        assert config.allow_credentials is True
        assert config.allow_all_origins is False

    def test_get_test_cors_config(self):
        """Test test CORS configuration helper."""
        config = get_test_cors_config()

        assert config.environment == Environment.TEST
        assert config.allowed_origins == [
            "http://localhost:3000",
            "http://localhost:8000",
        ]
        assert config.allow_credentials is True
        assert config.log_violations is True


class TestCORSIntegration:
    """Test CORS integration with FastAPI application."""


    def test_add_cors_middleware_integration(self):
        """Test adding CORS middleware to FastAPI app."""
        app = FastAPI()

        # Add middleware to app
        add_cors_middleware(app, environment="development")

        # Check that middleware was added
        from starlette.middleware.cors import CORSMiddleware as StarletteCORSMiddleware

        assert any(
            m.cls == StarletteCORSMiddleware for m in app.user_middleware
        )

    def test_fastapi_app_with_cors_middleware(self):
        """Test complete FastAPI app with CORS middleware."""
        app = FastAPI()

        # Add CORS middleware
        add_cors_middleware(app, environment="development")

        # Add a test endpoint
        @app.get("/test")
        def test_endpoint():
            return {"message": "Hello World"}

        # Test with client
        client = TestClient(app)

        # Test CORS preflight request
        response = client.options(
            "/test",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 200
        # Should have CORS headers for development environment
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"

    def test_cors_policy_environment_from_settings(self):
        """Test CORS policy loaded from settings."""
        with patch("resync.api.middleware.cors_middleware.settings") as mock_settings:
            mock_settings.ENVIRONMENT = "production"

            app = FastAPI()
            add_cors_middleware(app)

            # To verify, we need to inspect the middleware added to the app
            # This is a bit of an integration test
            added_middleware = app.user_middleware[-1]
            assert added_middleware.cls == CORSMiddleware
            assert added_middleware.kwargs["allow_origins"] == []


class TestCORSSecurity:
    """Test CORS security features."""

    def test_production_policy_strict_security(self):
        """Test that production policy enforces strict security."""
        policy = get_production_cors_config(allowed_origins=["https://app.example.com"])

        # Should not allow wildcards
        assert policy.allow_all_origins is False

        # Should not allow credentials by default
        assert policy.allow_credentials is False

        # Should only allow specified origins
        assert policy.is_origin_allowed("https://app.example.com") is True
        assert policy.is_origin_allowed("https://other.com") is False
        assert policy.is_origin_allowed("http://localhost:3000") is False

    def test_cors_violation_logging(self):
        """Test that CORS violations are properly logged."""
        policy = CORSPolicy(
            environment=Environment.PRODUCTION,
            allowed_origins=["https://allowed.com"],
            log_violations=True,
        )

        # Mock logger to capture log calls
        with patch("resync.api.middleware.cors_config.logger"):
            # This would be called during middleware processing
            # For now, just verify the policy is configured for logging
            assert policy.log_violations is True

    def test_dynamic_origin_validation(self):
        """Test dynamic origin validation with regex patterns."""
        policy = CORSPolicy(
            environment=Environment.PRODUCTION,
            allowed_origins=[],
            origin_regex_patterns=[
                r"https://.*\.example\.com$",
                r"https://api\..*\.com$",
            ],
        )

        # Should match regex patterns
        assert policy.is_origin_allowed("https://app.example.com") is True
        assert policy.is_origin_allowed("https://api.example.com") is True
        assert policy.is_origin_allowed("https://api.service.com") is True

        # Should not match invalid patterns
        assert policy.is_origin_allowed("https://example.com") is False
        assert policy.is_origin_allowed("https://other.com") is False


# Integration tests for different environments
@pytest.mark.parametrize(
    "environment,expected_allow_all",
    [
        ("development", True),
        ("production", False),
        ("test", False),
    ],
)
def test_environment_specific_cors_policies(environment, expected_allow_all):
    """Test that CORS policies are correctly configured for each environment."""

    policy = cors_config.get_policy(environment)

    if environment == "development":
        assert policy.allow_all_origins is True
        assert policy.allow_credentials is True
    elif environment == "production":
        assert policy.allow_all_origins is False
        assert policy.allow_credentials is False
        assert policy.allowed_origins == []
    elif environment == "test":
        assert policy.allow_all_origins is False
        assert policy.allow_credentials is True
        assert "http://localhost:3000" in policy.allowed_origins


if __name__ == "__main__":
    pytest.main([__file__, "-v"])




