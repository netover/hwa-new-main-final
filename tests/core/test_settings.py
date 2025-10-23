import pytest
import os
from unittest.mock import patch

from resync.settings import Settings, Environment


def test_settings_validation_success():
    """
    Tests that validation passes when all required settings are present.
    """
    # This should not raise any exception
    settings = Settings()
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
    ):
        with pytest.raises(ValueError) as excinfo:
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
    ):
        with pytest.raises(ValueError) as excinfo:
            Settings()

    # Check that TWS-related fields are mentioned
    error_str = str(excinfo.value).lower()
    assert "tws" in error_str


def test_settings_validation_fails_in_production_with_insecure_values():
    """
    Tests that validation fails in production with insecure default values.
    """
    # Test with insecure admin password
    with patch.dict(
        os.environ,
        {
            "APP_ENVIRONMENT": "production",
            "APP_ADMIN_PASSWORD": "change_me_please",  # Insecure default
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
    assert settings.BASE_DIR == settings.base_dir
    assert settings.PROJECT_NAME == settings.project_name
    assert settings.PROJECT_VERSION == settings.project_version
    assert settings.DESCRIPTION == settings.description
    assert settings.LOG_LEVEL == settings.log_level
    assert settings.ENVIRONMENT == settings.environment.value
    assert settings.DEBUG == (settings.environment == Environment.DEVELOPMENT)

    # Test database properties
    assert settings.NEO4J_URI == settings.neo4j_uri
    assert settings.NEO4J_USER == settings.neo4j_user
    assert settings.NEO4J_PASSWORD == settings.neo4j_password

    # Test Redis properties
    assert settings.REDIS_URL == settings.redis_url

    # Test LLM properties
    assert settings.LLM_ENDPOINT == settings.llm_endpoint
    assert settings.LLM_API_KEY == settings.llm_api_key

    # Test admin properties
    assert settings.ADMIN_USERNAME == settings.admin_username
    assert settings.ADMIN_PASSWORD == settings.admin_password

    # Test TWS properties
    assert settings.TWS_MOCK_MODE == settings.tws_mock_mode
    assert settings.TWS_HOST == settings.tws_host
    assert settings.TWS_PORT == settings.tws_port
    assert settings.TWS_USER == settings.tws_user
    assert settings.TWS_PASSWORD == settings.tws_password

    # Test server properties
    assert settings.SERVER_HOST == settings.server_host
    assert settings.SERVER_PORT == settings.server_port

    # Test CORS properties
    assert settings.CORS_ALLOWED_ORIGINS == settings.cors_allowed_origins
    assert settings.CORS_ALLOW_CREDENTIALS == settings.cors_allow_credentials
    assert settings.CORS_ALLOW_METHODS == settings.cors_allow_methods
    assert settings.CORS_ALLOW_HEADERS == settings.cors_allow_headers

    # Test static files properties
    assert settings.STATIC_CACHE_MAX_AGE == settings.static_cache_max_age

    # Test model name properties
    assert settings.AUDITOR_MODEL_NAME == settings.auditor_model_name
    assert settings.AGENT_MODEL_NAME == settings.agent_model_name

    # Test connection pool properties
    assert settings.DB_POOL_MIN_SIZE == settings.db_pool_min_size
    assert settings.DB_POOL_MAX_SIZE == settings.db_pool_max_size
    assert settings.DB_POOL_IDLE_TIMEOUT == settings.db_pool_idle_timeout
    assert settings.DB_POOL_CONNECT_TIMEOUT == settings.db_pool_connect_timeout
    assert (
        settings.DB_POOL_HEALTH_CHECK_INTERVAL == settings.db_pool_health_check_interval
    )
    assert settings.DB_POOL_MAX_LIFETIME == settings.db_pool_max_lifetime

    assert settings.REDIS_POOL_MIN_SIZE == settings.redis_pool_min_size
    assert settings.REDIS_POOL_MAX_SIZE == settings.redis_pool_max_size
    assert settings.REDIS_POOL_IDLE_TIMEOUT == settings.redis_pool_idle_timeout
    assert settings.REDIS_POOL_CONNECT_TIMEOUT == settings.redis_pool_connect_timeout
    assert (
        settings.REDIS_POOL_HEALTH_CHECK_INTERVAL
        == settings.redis_pool_health_check_interval
    )
    assert settings.REDIS_POOL_MAX_LIFETIME == settings.redis_pool_max_lifetime

    assert settings.HTTP_POOL_MIN_SIZE == settings.http_pool_min_size
    assert settings.HTTP_POOL_MAX_SIZE == settings.http_pool_max_size
    assert settings.HTTP_POOL_IDLE_TIMEOUT == settings.http_pool_idle_timeout
    assert settings.HTTP_POOL_CONNECT_TIMEOUT == settings.http_pool_connect_timeout
    assert (
        settings.HTTP_POOL_HEALTH_CHECK_INTERVAL
        == settings.http_pool_health_check_interval
    )
    assert settings.HTTP_POOL_MAX_LIFETIME == settings.http_pool_max_lifetime

    # Test additional properties
    assert settings.JINJA2_TEMPLATE_CACHE_SIZE == (
        400 if settings.environment == Environment.PRODUCTION else 0
    )
    assert settings.AGENT_CONFIG_PATH == settings.base_dir / "config" / "agents.json"
    assert settings.MAX_CONCURRENT_AGENT_CREATIONS == 5
    assert settings.TWS_ENGINE_NAME == "TWS"
    assert settings.TWS_ENGINE_OWNER == "twsuser"
