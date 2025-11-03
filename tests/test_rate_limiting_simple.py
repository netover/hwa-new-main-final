"""
Simple unit tests for rate limiting functionality without full app imports.

Tests cover basic rate limiting functionality without importing the full resync module.
"""

import os
import sys
from unittest.mock import Mock

import pytest

# Set test environment variables before any imports
os.environ["APP_ENV"] = "test"
os.environ["ADMIN_USERNAME"] = "test_admin"
os.environ["ADMIN_PASSWORD"] = "test_password"

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Now we can import just the rate limiter module
from resync.core.rate_limiter import (
    authenticated_rate_limit,
    create_rate_limit_exceeded_response,
    critical_rate_limit,
    get_authenticated_user_identifier,
    get_user_identifier,
    public_rate_limit,
)


@pytest.fixture
def mock_request():
    """Create a mock request for testing."""
    request = Mock()
    request.client.host = "127.0.0.1"
    request.url.path = "/test"
    request.state = Mock()
    request.state.user = None
    return request


@pytest.fixture
def mock_authenticated_request():
    """Create a mock authenticated request for testing."""
    request = Mock()
    request.client.host = "127.0.0.1"
    request.url.path = "/test"
    request.state = Mock()
    request.state.user = "test_user"
    return request


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
        from slowapi.errors import RateLimitExceeded

        exc = Mock(spec=RateLimitExceeded)
        exc.limit = 100
        exc.window = 60
        exc.retry_after = 30

        response = create_rate_limit_exceeded_response(mock_request, exc)

        assert response.status_code == 429
        assert response.content["error"] == "Rate limit exceeded"
        assert response.content["retry_after"] == 30

    def test_rate_limit_headers(self, mock_request):
        """Test that rate limit headers are added to response."""
        from slowapi.errors import RateLimitExceeded

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

    def test_public_rate_limit_decorator(self):
        """Test public rate limit decorator."""

        @public_rate_limit
        def test_endpoint():
            return {"status": "ok"}

        # The decorator should be applied
        assert hasattr(test_endpoint, "_rate_limit")

    def test_authenticated_rate_limit_decorator(self):
        """Test authenticated rate limit decorator."""

        @authenticated_rate_limit
        def test_endpoint():
            return {"status": "ok"}

        # The decorator should be applied
        assert hasattr(test_endpoint, "_rate_limit")

    def test_critical_rate_limit_decorator(self):
        """Test critical rate limit decorator."""

        @critical_rate_limit
        def test_endpoint():
            return {"status": "ok"}

        # The decorator should be applied
        assert hasattr(test_endpoint, "_rate_limit")


class TestErrorHandling:
    """Test error handling in rate limiting."""

    def test_rate_limit_exceeded_with_missing_retry_after(self, mock_request):
        """Test rate limit exceeded response with missing retry_after."""
        from slowapi.errors import RateLimitExceeded

        exc = Mock(spec=RateLimitExceeded)
        exc.limit = 100
        exc.window = 60
        exc.retry_after = None  # No retry_after provided

        response = create_rate_limit_exceeded_response(mock_request, exc)

        assert response.status_code == 429
        assert response.content["retry_after"] == 60  # Should use default


if __name__ == "__main__":
    pytest.main([__file__, "-v"])




