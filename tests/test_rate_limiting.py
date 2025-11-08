"""
Unit tests for rate limiting functionality.

Tests cover various rate limiting scenarios including:
- Public endpoint rate limiting
- Authenticated endpoint rate limiting
- Critical endpoint rate limiting
- Rate limit exceeded responses
- Rate limit headers
"""

import os
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI, Request
from slowapi.errors import RateLimitExceeded

# Set test environment variables before importing resync modules
os.environ["APP_ENV"] = "test"
os.environ["ADMIN_USERNAME"] = "test_admin"
os.environ["ADMIN_PASSWORD"] = "test_password"
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_USER"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = "password"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["LLM_ENDPOINT"] = "http://localhost:8001/v1"
os.environ["TWS_MOCK_MODE"] = "true"

from resync.core.rate_limiter import (
    RateLimitConfig,
    authenticated_rate_limit,
    create_rate_limit_exceeded_response,
    critical_rate_limit,
    get_authenticated_user_identifier,
    get_user_identifier,
    init_rate_limiter,
    public_rate_limit,
)


@pytest.fixture
def mock_request():
    """Create a mock request for testing."""
    request = Mock(spec=Request)
    request.client.host = "127.0.0.1"
    request.url.path = "/test"
    request.state = Mock()
    request.state.user = None
    return request


@pytest.fixture
def mock_authenticated_request():
    """Create a mock authenticated request for testing."""
    request = Mock(spec=Request)
    request.client.host = "127.0.0.1"
    request.url.path = "/test"
    request.state = Mock()
    request.state.user = "test_user"
    return request


@pytest.fixture
def test_app():
    """Create a test FastAPI application."""
    return FastAPI()


class TestRateLimitConfiguration:
    """Test rate limit configuration values."""

    def test_public_endpoint_rate_limit(self):
        """Test public endpoint rate limit configuration."""
        assert "100/minute" in RateLimitConfig.PUBLIC_ENDPOINTS

    def test_authenticated_endpoint_rate_limit(self):
        """Test authenticated endpoint rate limit configuration."""
        assert "1000/minute" in RateLimitConfig.AUTHENTICATED_ENDPOINTS

    def test_critical_endpoint_rate_limit(self):
        """Test critical endpoint rate limit configuration."""
        assert "50/minute" in RateLimitConfig.CRITICAL_ENDPOINTS

    def test_error_handler_rate_limit(self):
        """Test error handler rate limit configuration."""
        assert "15/minute" in RateLimitConfig.ERROR_HANDLER

    def test_websocket_rate_limit(self):
        """Test WebSocket rate limit configuration."""
        assert "30/minute" in RateLimitConfig.WEBSOCKET

    def test_dashboard_rate_limit(self):
        """Test dashboard rate limit configuration."""
        assert "10/minute" in RateLimitConfig.DASHBOARD


class TestUserIdentifierFunctions:
    """Test user identifier functions."""

    def test_get_user_identifier_with_ip(self, mock_request):
        """Test getting user identifier from IP address."""
        identifier = get_user_identifier(mock_request)
        assert identifier == "127.0.0.1"

    def test_get_user_identifier_with_authenticated_user(
        self, mock_authenticated_request
    ):
        """Test getting user identifier from authenticated user."""
        identifier = get_user_identifier(mock_authenticated_request)
        assert identifier == "user:test_user"

    def test_get_authenticated_user_identifier_with_user(
        self, mock_authenticated_request
    ):
        """Test getting authenticated user identifier with user."""
        identifier = get_authenticated_user_identifier(mock_authenticated_request)
        assert identifier == "auth_user:test_user"

    def test_get_authenticated_user_identifier_without_user(self, mock_request):
        """Test getting authenticated user identifier without user."""
        identifier = get_authenticated_user_identifier(mock_request)
        assert identifier == "ip:127.0.0.1"


class TestRateLimitExceededResponse:
    """Test rate limit exceeded response creation."""

    def test_create_rate_limit_exceeded_response(self, mock_request):
        """Test creating rate limit exceeded response."""
        exc = Mock(spec=RateLimitExceeded)
        exc.limit = 100
        exc.window = 60
        exc.retry_after = 30

        response = create_rate_limit_exceeded_response(mock_request, exc)

        assert response.status_code == 429
        # Parse JSON content from response
        import json

        content = json.loads(response.body.decode("utf-8"))
        assert "error" in content
        assert content["error"] == "Rate limit exceeded"
        assert "retry_after" in content
        assert content["retry_after"] == 30

    def test_rate_limit_headers(self, mock_request):
        """Test that rate limit headers are added to response."""
        exc = Mock(spec=RateLimitExceeded)
        exc.limit = 100
        exc.window = 60
        exc.retry_after = 30

        response = create_rate_limit_exceeded_response(mock_request, exc)

        assert "X-RateLimit-Limit" in response.headers
        assert response.headers["X-RateLimit-Limit"] == "100"
        assert "X-RateLimit-Remaining" in response.headers
        assert response.headers["X-RateLimit-Remaining"] == "0"
        assert "Retry-After" in response.headers
        assert response.headers["Retry-After"] == "30"


class TestRateLimitDecorators:
    """Test rate limit decorators."""

    @pytest.mark.asyncio
    async def test_public_rate_limit_decorator(self):
        """Test public rate limit decorator."""

        # Test that decorator can be applied without error
        @public_rate_limit
        async def test_endpoint(request):  # Add request parameter required by slowapi
            return {"status": "ok"}

        # Just verify the function exists and is callable
        assert callable(test_endpoint)

    @pytest.mark.asyncio
    async def test_authenticated_rate_limit_decorator(self):
        """Test authenticated rate limit decorator."""

        # Test that decorator can be applied without error
        @authenticated_rate_limit
        async def test_endpoint(request):  # Add request parameter required by slowapi
            return {"status": "ok"}

        # Just verify the function exists and is callable
        assert callable(test_endpoint)

    @pytest.mark.asyncio
    async def test_critical_rate_limit_decorator(self):
        """Test critical rate limit decorator."""

        # Test that decorator can be applied without error
        @critical_rate_limit
        async def test_endpoint(request):  # Add request parameter required by slowapi
            return {"status": "ok"}

        # Just verify the function exists and is callable
        assert callable(test_endpoint)


class TestRateLimiterInitialization:
    """Test rate limiter initialization."""

    def test_init_rate_limiter(self, test_app):
        """Test initializing rate limiter with FastAPI app."""
        with patch("resync.core.rate_limiter.logger") as mock_logger:
            init_rate_limiter(test_app)

            # Check that limiter is added to app state
            assert hasattr(test_app.state, "limiter")

            # Check that exception handler is added
            assert RateLimitExceeded in test_app.exception_handlers

            # Check that middleware is added
            # Note: We can't easily test middleware addition without more complex setup

            # Check that logger was called
            mock_logger.info.assert_called()


class TestIntegrationScenarios:
    """Test integration scenarios."""

    @pytest.mark.asyncio
    async def test_rate_limiting_with_mock_redis(self, test_app):
        """Test rate limiting initialization."""
        with patch("redis.asyncio.from_url") as mock_redis:
            # Mock Redis client
            mock_redis_client = Mock()
            mock_redis.return_value = mock_redis_client

            # Initialize rate limiter
            init_rate_limiter(test_app)

            # Test that limiter is properly initialized (Redis connection is lazy)
            assert hasattr(test_app.state, "limiter")

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, mock_request):
        """Test handling concurrent requests with rate limiting."""
        # This would require more complex setup with actual Redis
        # For now, we just test that the functions can be called
        identifier = get_user_identifier(mock_request)
        assert identifier is not None

    def test_sliding_window_configuration(self):
        """Test sliding window rate limiting configuration."""
        # Test that sliding window is enabled by default
        from resync.settings import settings

        assert settings.rate_limit_sliding_window is True


class TestErrorHandling:
    """Test error handling in rate limiting."""

    def test_rate_limit_exceeded_with_missing_retry_after(self, mock_request):
        """Test rate limit exceeded response with missing retry_after."""
        exc = Mock(spec=RateLimitExceeded)
        exc.limit = 100
        exc.window = 60
        exc.retry_after = None  # No retry_after provided

        response = create_rate_limit_exceeded_response(mock_request, exc)

        assert response.status_code == 429
        # Parse JSON content from response
        import json

        content = json.loads(response.body.decode("utf-8"))
        assert content["retry_after"] == 60  # Should use default

    def test_invalid_request_object(self):
        """Test handling invalid request object."""
        invalid_request = Mock()
        # Missing required attributes

        # Should not crash, but handle gracefully
        try:
            get_user_identifier(invalid_request)
            # Should return some default value or handle gracefully
        except Exception as e:
            # If it crashes, it should be a controlled error
            assert isinstance(e, AttributeError | TypeError)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
