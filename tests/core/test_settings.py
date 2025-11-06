import os
import warnings
from unittest.mock import patch

import pytest

from resync.settings import Environment, Settings


def test_settings_validation_success():
    """
    Tests that validation passes when all required settings are present.
    """
    # This should not raise any exception
    Settings()
    # Validation happens automatically in Pydantic v2


def test_settings_validation_fails_on_missing_required_fields():
    """
    Tests that validation fails with a ValueError if required fields are missing.
    """
    # Temporarily unset required environment variables
    with patch.dict(
        os.environ,
        {
            "APP_NEO4J_URI": "",
            "APP_REDIS_URL": "",
            "APP_NEO4J_USER": "",
            "APP_NEO4J_PASSWORD": "",
        },
        clear=True,
    ), pytest.raises(ValueError) as excinfo:
        Settings()

    # Should mention the missing fields
    error_str = str(excinfo.value).lower()
    assert (
        "neo4j_uri" in error_str
        or "redis_url" in error_str
        or "neo4j_user" in error_str
        or "neo4j_password" in error_str
    )


def test_settings_validation_requires_tws_keys_when_not_mocked():
    """
    Tests that TWS-specific keys are required when TWS_MOCK_MODE is False.
    """
    with patch.dict(
        os.environ,
        {
            "APP_TWS_MOCK_MODE": "False",
            "APP_TWS_HOST": "",
            "APP_TWS_PORT": "",
            "APP_TWS_USER": "",
            "APP_TWS_PASSWORD": "",
        },
        clear=True,
    ), pytest.raises(ValueError) as excinfo:
        Settings()

    # Check that TWS-related fields are mentioned
    error_str = str(excinfo.value).lower()
    assert "tws" in error_str


def test_settings_validation_fails_in_production_with_insecure_values():
    """
    Tests that validation fails in production with insecure default values.
    """
    # Test with insecure admin password - uses ADMIN_PASSWORD without APP_ prefix for security
    with patch.dict(
        os.environ,
        {
            "APP_ENVIRONMENT": "production",
            "ADMIN_PASSWORD": "change_me_please",  # Insecure default
        },
        clear=True,
    ):
        with pytest.raises(ValueError) as excinfo:
            Settings()

    # Should mention insecure password
    error_str = str(excinfo.value).lower()
    assert "insecure" in error_str and "password" in error_str

    # Test with insecure LLM API key
    with patch.dict(
        os.environ,
        {
            "APP_ENVIRONMENT": "production",
            "APP_LLM_API_KEY": "dummy_key_for_development",  # Insecure default
        },
        clear=True,
    ):
        with pytest.raises(ValueError) as excinfo:
            Settings()

    # Should mention LLM API key
    error_str = str(excinfo.value).lower()
    assert "llm_api_key" in error_str or "llm" in error_str


def test_settings_backward_compatibility_properties():
    """
    Tests that backward compatibility properties work correctly.
    """
    settings = Settings()

    # Test that uppercase properties work
    assert settings.base_dir == settings.BASE_DIR
    assert settings.project_name == settings.PROJECT_NAME
    assert settings.project_version == settings.PROJECT_VERSION
    assert settings.description == settings.DESCRIPTION
    assert settings.log_level == settings.LOG_LEVEL
    assert settings.environment.value == settings.ENVIRONMENT
    assert (settings.environment == Environment.DEVELOPMENT) == settings.DEBUG

    # Test database properties
    assert settings.neo4j_uri == settings.NEO4J_URI
    assert settings.neo4j_user == settings.NEO4J_USER
    assert settings.neo4j_password == settings.NEO4J_PASSWORD

    # Test Redis properties
    assert settings.redis_url == settings.REDIS_URL

    # Test LLM properties
    assert settings.llm_endpoint == settings.LLM_ENDPOINT
    assert settings.llm_api_key == settings.LLM_API_KEY

    # Test admin properties
    assert settings.admin_username == settings.ADMIN_USERNAME
    assert settings.admin_password == settings.ADMIN_PASSWORD

    # Test TWS properties
    assert settings.tws_mock_mode == settings.TWS_MOCK_MODE
    assert settings.tws_host == settings.TWS_HOST
    assert settings.tws_port == settings.TWS_PORT
    assert settings.tws_user == settings.TWS_USER
    assert settings.tws_password == settings.TWS_PASSWORD

    # Test server properties
    assert settings.server_host == settings.SERVER_HOST
    assert settings.server_port == settings.SERVER_PORT

    # Test CORS properties
    assert settings.cors_allowed_origins == settings.CORS_ALLOWED_ORIGINS
    assert settings.cors_allow_credentials == settings.CORS_ALLOW_CREDENTIALS
    assert settings.cors_allow_methods == settings.CORS_ALLOW_METHODS
    assert settings.cors_allow_headers == settings.CORS_ALLOW_HEADERS

    # Test static files properties
    assert settings.static_cache_max_age == settings.STATIC_CACHE_MAX_AGE

    # Test model name properties
    assert settings.auditor_model_name == settings.AUDITOR_MODEL_NAME
    assert settings.agent_model_name == settings.AGENT_MODEL_NAME

    # Test connection pool properties
    assert settings.db_pool_min_size == settings.DB_POOL_MIN_SIZE
    assert settings.db_pool_max_size == settings.DB_POOL_MAX_SIZE
    assert settings.db_pool_idle_timeout == settings.DB_POOL_IDLE_TIMEOUT
    assert settings.db_pool_connect_timeout == settings.DB_POOL_CONNECT_TIMEOUT
    assert (
        settings.db_pool_health_check_interval == settings.DB_POOL_HEALTH_CHECK_INTERVAL
    )
    assert settings.db_pool_max_lifetime == settings.DB_POOL_MAX_LIFETIME

    assert settings.redis_pool_min_size == settings.REDIS_POOL_MIN_SIZE
    assert settings.redis_pool_max_size == settings.REDIS_POOL_MAX_SIZE
    assert settings.redis_pool_idle_timeout == settings.REDIS_POOL_IDLE_TIMEOUT
    assert settings.redis_pool_connect_timeout == settings.REDIS_POOL_CONNECT_TIMEOUT
    assert (
        settings.redis_pool_health_check_interval
        == settings.REDIS_POOL_HEALTH_CHECK_INTERVAL
    )
    assert settings.redis_pool_max_lifetime == settings.REDIS_POOL_MAX_LIFETIME

    assert settings.http_pool_min_size == settings.HTTP_POOL_MIN_SIZE
    assert settings.http_pool_max_size == settings.HTTP_POOL_MAX_SIZE
    assert settings.http_pool_idle_timeout == settings.HTTP_POOL_IDLE_TIMEOUT
    assert settings.http_pool_connect_timeout == settings.HTTP_POOL_CONNECT_TIMEOUT
    assert (
        settings.http_pool_health_check_interval
        == settings.HTTP_POOL_HEALTH_CHECK_INTERVAL
    )
    assert settings.http_pool_max_lifetime == settings.HTTP_POOL_MAX_LIFETIME

    # Test additional properties
    assert (
        400 if settings.environment == Environment.PRODUCTION else 0
    ) == settings.JINJA2_TEMPLATE_CACHE_SIZE
    assert settings.base_dir / "ops_config" / "agents.json" == settings.AGENT_CONFIG_PATH
    assert settings.MAX_CONCURRENT_AGENT_CREATIONS == 5
    assert settings.TWS_ENGINE_NAME == "TWS"
    assert settings.TWS_ENGINE_OWNER == "twsuser"


def test_tws_verify_warning_in_production():
    """Test that TWS verification emits warning in production when disabled."""
    with patch.dict(
        os.environ,
        {
            "APP_ENVIRONMENT": "production",
            "APP_TWS_VERIFY": "False",
        },
        clear=True,
    ), warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        Settings()
        # Check that a warning was issued
        assert len(w) >= 1
        warning_found = any("TWS verification is disabled" in str(warning.message) for warning in w)
        assert warning_found, "Expected warning about TWS verification being disabled in production"


def test_neo4j_uri_warning_in_production():
    """Test that Neo4j URI emits warning in production when using unencrypted connection."""
    with patch.dict(
        os.environ,
        {
            "APP_ENVIRONMENT": "production",
            "APP_NEO4J_URI": "neo4j://localhost:7687",
        },
        clear=True,
    ), warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        Settings()
        # Check that a warning was issued
        assert len(w) >= 1
        warning_found = any("unencrypted connection" in str(warning.message) for warning in w)
        assert warning_found, "Expected warning about unencrypted Neo4j connection in production"


def test_redis_url_accepts_both_schemes():
    """Test that Redis URL accepts both redis:// and rediss:// schemes."""
    # Test redis://
    with patch.dict(
        os.environ,
        {
            "APP_REDIS_URL": "redis://localhost:6379",
        },
        clear=True,
    ):
        settings = Settings()
        assert settings.redis_url == "redis://localhost:6379"

    # Test rediss://
    with patch.dict(
        os.environ,
        {
            "APP_REDIS_URL": "rediss://localhost:6379",
        },
        clear=True,
    ):
        settings = Settings()
        assert settings.redis_url == "rediss://localhost:6379"


def test_secret_fields_exclusion():
    """Test that secret fields are properly excluded from repr."""
    settings = Settings()
    repr_str = repr(settings)
    # Ensure secret fields don't appear in repr
    assert "password" not in repr_str.lower()
    assert "api_key" not in repr_str


def test_cors_credentials_with_wildcard_warning():
    """Test that CORS with credentials and wildcard origins emits warning."""
    with patch.dict(
        os.environ,
        {
            "APP_CORS_ALLOWED_ORIGINS": '["*"]',
            "APP_CORS_ALLOW_CREDENTIALS": "True",
        },
        clear=True,
    ), warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        Settings()
        # Check that a warning was issued
        assert len(w) >= 1
        warning_found = any("insecure" in str(warning.message).lower() for warning in w)
        assert warning_found, "Expected warning about insecure CORS configuration"


def test_redis_pool_fallback_deprecation_warning():
    """Test that deprecated Redis connection settings trigger deprecation warning."""
    with patch.dict(
        os.environ,
        {
            "APP_REDIS_MIN_CONNECTIONS": "5",
            "APP_REDIS_MAX_CONNECTIONS": "25",
            "APP_REDIS_POOL_MIN_SIZE": "5",  # Default value to trigger fallback
            "APP_REDIS_POOL_MAX_SIZE": "20", # Default value to trigger fallback
        },
        clear=True,
    ):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Settings()
            # Check that a deprecation warning was issued
            assert len(w) >= 1
            warning_found = any("deprecated" in str(warning.message).lower() for warning in w)
            assert warning_found, "Expected deprecation warning for old Redis connection settings"


def test_redis_pool_size_validation():
    """Test that Redis pool min size <= max size validation works."""
    with patch.dict(
        os.environ,
        {
            "APP_REDIS_POOL_MIN_SIZE": "25",
            "APP_REDIS_POOL_MAX_SIZE": "10",  # Less than min, should fail
        },
        clear=True,
    ):
        with pytest.raises(ValueError) as excinfo:
            Settings()
        error_str = str(excinfo.value).lower()
        assert "max_size" in error_str and "min_size" in error_str


def test_rate_limit_storage_uri_default():
    """Test that rate limit storage URI defaults to separate Redis DB."""
    settings = Settings()
    assert settings.rate_limit_storage_uri == "redis://localhost:6379/1"


def test_semver_regex_accepts_pre_release_and_build():
    """Test that SemVer regex accepts pre-release and build metadata."""
    with patch.dict(
        os.environ,
        {
            "APP_PROJECT_VERSION": "1.2.3-alpha+build.5",
        },
        clear=True,
    ):
        settings = Settings()
        assert settings.project_version == "1.2.3-alpha+build.5"


def test_base_dir_validation():
    """Test that base_dir is properly resolved and validated."""
    settings = Settings()
    # Check that base_dir is a valid directory path
    assert settings.base_dir.exists()
    assert settings.base_dir.is_dir()
    # Check that it's properly resolved
    assert settings.base_dir.is_absolute()


def test_cache_settings_exposed():
    """Test that new cache settings are exposed."""
    settings = Settings()
    assert hasattr(settings, 'enable_cache_swr')
    assert hasattr(settings, 'cache_ttl_jitter_ratio')
    assert hasattr(settings, 'enable_cache_mutex')
    assert settings.enable_cache_swr is True
    assert settings.cache_ttl_jitter_ratio == 0.1
    assert settings.enable_cache_mutex is True


def test_logging_settings_redaction():
    """Test that logging redaction setting is available."""
    settings = Settings()
    assert hasattr(settings, 'log_sensitive_data_redaction')
    assert settings.log_sensitive_data_redaction is True




