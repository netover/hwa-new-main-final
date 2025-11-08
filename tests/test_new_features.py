"""
Tests for the new features implemented as part of the optimization and refactoring plan.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from resync.api.audit import (
    AuditAction,
    AuditLogger,
    AuditRecordResponse,
    generate_audit_log,
)
from resync.api.cache import (
    ConnectionPoolValidator,
    RedisCacheManager,
    get_redis_connection,
)
from resync.api.middleware.cors_monitoring import CORSMonitor, CORSOperation
from resync.settings import Environment
from resync.settings import Settings as ApplicationSettings


class TestTypeAnnotationsAndDataValidation:
    """Tests for type annotations and data validation features."""

    def test_application_settings_validation(self):
        """Test that the ApplicationSettings model validates correctly."""
        # Test valid settings
        settings = ApplicationSettings(
            neo4j_uri="bolt://localhost:7687",
            neo4j_user="admin",
            neo4j_password="password",
            redis_url="redis://localhost:6379",
            llm_endpoint="http://localhost:8000",
            llm_api_key="test-key",
            admin_username="admin",
            admin_password="password",
            tws_mock_mode=True,
            base_dir=Path("."),
        )
        assert settings.neo4j_uri == "bolt://localhost:7687"

        # Test invalid TWS port validation
        with pytest.raises(ValidationError):
            ApplicationSettings(
                neo4j_uri="bolt://localhost:7687",
                neo4j_user="admin",
                neo4j_password="password",
                redis_url="redis://localhost:6379",
                llm_endpoint="http://localhost:8000",
                llm_api_key="test-key",
                admin_username="admin",
                admin_password="password",
                tws_mock_mode=False,
                tws_host="localhost",
                tws_port=99999,  # Invalid port
                tws_user="user",
                tws_password="pass",
                base_dir=Path("."),
            )

    def test_redis_connection_counts_validation(self):
        """Test validation of Redis connection counts."""
        # Test valid counts
        settings = ApplicationSettings(
            neo4j_uri="bolt://localhost:7687",
            neo4j_user="admin",
            neo4j_password="password",
            redis_url="redis://localhost:6379",
            llm_endpoint="http://localhost:8000",
            llm_api_key="test-key",
            admin_username="admin",
            admin_password="password",
            redis_min_connections=2,
            redis_max_connections=20,
            base_dir=Path("."),
        )
        assert settings.redis_min_connections == 2
        assert settings.redis_max_connections == 20

        # Test invalid connection count
        with pytest.raises(ValidationError):
            ApplicationSettings(
                neo4j_uri="bolt://localhost:7687",
                neo4j_user="admin",
                neo4j_password="password",
                redis_url="redis://localhost:6379",
                llm_endpoint="http://localhost:8000",
                llm_api_key="test-key",
                admin_username="admin",
                admin_password="password",
                redis_min_connections=-1,  # Invalid
                base_dir=Path("."),
            )


class TestRedisCaching:
    """Tests for Redis caching features."""

    def test_connection_pool_validator(self):
        """Test the ConnectionPoolValidator functionality."""
        # Valid configuration
        result = ConnectionPoolValidator.validate_connection_pool(1, 10, 30.0)
        assert result is True

        # Invalid min connections
        result = ConnectionPoolValidator.validate_connection_pool(-1, 10, 30.0)
        assert result is False

        # Invalid max connections
        result = ConnectionPoolValidator.validate_connection_pool(1, 0, 30.0)
        assert result is False

        # Min > max
        result = ConnectionPoolValidator.validate_connection_pool(10, 5, 30.0)
        assert result is False

        # Invalid timeout
        result = ConnectionPoolValidator.validate_connection_pool(1, 10, -5.0)
        assert result is False

    @patch("resync.api.cache.Redis")
    def test_get_redis_connection(self, mock_redis):
        """Test the get_redis_connection function."""
        # Mock successful connection
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_redis.from_url.return_value = mock_redis_client

        result = get_redis_connection()
        assert result is not None

        # Mock failed connection
        mock_redis_client.ping.side_effect = Exception("Connection failed")
        result = get_redis_connection()
        assert result is None

    @patch("resync.api.cache.Redis")
    def test_redis_cache_manager(self, mock_redis):
        """Test the RedisCacheManager functionality."""
        mock_redis_client = Mock()
        mock_redis.from_url.return_value = mock_redis_client

        cache_manager = RedisCacheManager(mock_redis_client)

        # Test get
        cache_manager.get("test_key")
        mock_redis_client.get.assert_called_with("test_key")

        # Test set
        cache_manager.set("test_key", "test_value", 3600)
        mock_redis_client.setex.assert_called_with("test_key", 3600, "test_value")

        # Test delete
        cache_manager.delete("test_key")
        mock_redis_client.delete.assert_called_with("test_key")


class TestCORSMonitoring:
    """Tests for CORS monitoring features."""

    def test_cors_monitor_basic_functionality(self):
        """Test basic CORS monitor functionality."""
        monitor = CORSMonitor()

        # Create a mock request
        mock_request = type(
            "MockRequest",
            (),
            {
                "headers": {
                    "origin": "https://example.com",
                    "user-agent": "test-agent",
                },
                "url": type("URL", (), {"path": "/test"})(),
                "method": "GET",
            },
        )()

        # Test monitoring a request
        result = monitor.monitor_request(mock_request, CORSOperation.REQUEST)
        assert result["origin"] == "https://example.com"
        assert result["path"] == "/test"
        assert result["operation"] == "request"

        # Test logging a violation
        monitor.log_violation("https://bad-origin.com", "/forbidden", "Test violation")
        assert len(monitor.violations) == 1
        assert monitor.violations[0]["origin"] == "https://bad-origin.com"

        # Test statistics
        stats = monitor.get_statistics()
        assert "total_requests" in stats
        assert "total_violations" in stats
        assert "violation_rate" in stats


class TestAuditLogging:
    """Tests for audit logging features."""

    def test_audit_logger_functionality(self):
        """Test the AuditLogger functionality."""
        logger = AuditLogger()

        result = logger.generate_audit_log(
            user_id="test_user",
            action=AuditAction.API_ACCESS,
            details={"resource": "/api/test", "method": "GET"},
        )

        assert isinstance(result, AuditRecordResponse)
        assert result.user_id == "test_user"
        assert result.action == AuditAction.API_ACCESS
        assert "resource" in result.details

        # Test the standalone generate_audit_log function
        result2 = generate_audit_log(
            user_id="test_user_2",
            action=AuditAction.DATA_ACCESS,
            details={"resource": "/api/data", "method": "POST"},
            ip_address="127.0.0.1",
            user_agent="test-agent",
        )

        assert result2.user_id == "test_user_2"
        assert result2.ip_address == "127.0.0.1"

    def test_audit_action_enum(self):
        """Test the AuditAction enum."""
        assert AuditAction.LOGIN.value == "login"
        assert AuditAction.API_ACCESS.value == "api_access"
        assert AuditAction.CACHE_INVALIDATION.value == "cache_invalidation"


class TestConfigurationEnhancement:
    """Tests for configuration enhancement features."""

    def test_environment_validation(self):
        """Test environment validation."""
        # Valid environments
        settings = ApplicationSettings(
            neo4j_uri="bolt://localhost:7687",
            neo4j_user="admin",
            neo4j_password="password",
            redis_url="redis://localhost:6379",
            llm_endpoint="http://localhost:8000",
            llm_api_key="test-key",
            admin_username="admin",
            admin_password="password",
            environment=Environment.DEVELOPMENT,
            base_dir=Path("."),
        )
        assert settings.environment == "development"

        settings = ApplicationSettings(
            neo4j_uri="bolt://localhost:7687",
            neo4j_user="admin",
            neo4j_password="password",
            redis_url="redis://localhost:6379",
            llm_endpoint="http://localhost:8000",
            llm_api_key="test-key",
            admin_username="admin",
            admin_password="password",
            environment=Environment.PRODUCTION,
            base_dir=Path("."),
        )
        assert settings.environment == "production"

        # Invalid environment
        with pytest.raises(ValidationError):
            ApplicationSettings(
                neo4j_uri="bolt://localhost:7687",
                neo4j_user="admin",
                neo4j_password="password",
                redis_url="redis://localhost:6379",
                llm_endpoint="http://localhost:8000",
                llm_api_key="test-key",
                admin_username="admin",
                admin_password="password",
                environment="invalid_env",
                base_dir=Path("."),
            )


class TestErrorHandling:
    """Tests for improved error handling."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a TestClient for the FastAPI app."""
        from fastapi import FastAPI

        from resync.api.endpoints import api_router

        app = FastAPI()
        app.include_router(api_router)
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_handle_error_function(self):
        """Test the improved handle_error function."""
        from resync.api.endpoints import handle_error

        # Test timeout error
        timeout_error = Exception("Connection timeout")
        result = handle_error(timeout_error, "test operation")
        assert result.status_code == 504

        # Test auth error
        auth_error = Exception("Unauthorized access")
        result = handle_error(auth_error, "test operation")
        assert result.status_code == 401

        # Test not found error
        not_found_error = Exception("Resource not found")
        result = handle_error(not_found_error, "test operation")
        assert result.status_code == 404

        # Test validation error
        validation_error = Exception("Invalid input")
        result = handle_error(validation_error, "test operation")
        assert result.status_code == 422

        # Test conflict error
        conflict_error = Exception("Resource already exists")
        result = handle_error(conflict_error, "test operation")
        assert result.status_code == 409

        # Test general error
        general_error = Exception("General error")
        result = handle_error(general_error, "test operation")
        assert result.status_code == 500


