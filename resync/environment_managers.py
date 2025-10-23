"""Environment-specific managers for different deployment configurations.

This module provides specialized managers for handling environment-specific
logic and configurations for development, production, and test environments.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Type, Dict, Any, Optional, override

from .settings import Settings
from .settings_validator import Environment as ValidatedEnvironment
from .settings_factory import SettingsFactory
from .settings_observer import settings_monitor


class EnvironmentManager(ABC):
    """Abstract base class for environment managers."""

    def __init__(self, settings: Settings):  # type: ignore[reportMissingSuperCall]
        self.settings = settings
        self.logger = logging.getLogger(
            f"{self.__class__.__name__}.{settings.environment.value}"
        )

    @abstractmethod
    def setup_logging(self) -> None:
        """Setup environment-specific logging configuration."""

    @abstractmethod
    def get_cache_config(self) -> Dict[str, Any]:
        """Get environment-specific cache configuration."""

    @abstractmethod
    def get_connection_pool_config(self) -> Dict[str, Any]:
        """Get environment-specific connection pool configuration."""

    @abstractmethod
    def validate_environment_specific_settings(self) -> None:
        """Validate settings specific to this environment."""

    def get_environment_info(self) -> Dict[str, Any]:
        """Get environment-specific information."""
        return {
            "environment": self.settings.environment.value,
            "is_production": self.settings.is_production,
            "is_development": self.settings.is_development,
            "log_level": self.settings.log_level,
            "debug_mode": self.settings.environment == ValidatedEnvironment.DEVELOPMENT,
        }


class DevelopmentManager(EnvironmentManager):
    """Manager for development environment."""

    def __init__(self, settings: Settings):
        super().__init__(settings)

    @override
    def setup_logging(self) -> None:
        """Setup development logging with debug level and console output."""
        logging.basicConfig(
            level=getattr(logging, self.settings.log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            force=True,  # Override any existing configuration
        )

        # Add console handler for development
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(formatter)

        # Add to root logger
        root_logger = logging.getLogger()
        if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
            root_logger.addHandler(console_handler)

        self.logger.info("Development logging configured")

    @override
    def get_cache_config(self) -> Dict[str, Any]:
        """Get development-optimized cache configuration."""
        return {
            "hierarchy_l1_max_size": 1000,
            "hierarchy_l2_ttl": 300,  # 5 minutes
            "hierarchy_l2_cleanup_interval": 60,
            "hierarchy_num_shards": 4,
            "hierarchy_max_workers": 2,
            "enable_memory_monitoring": False,
            "enable_detailed_metrics": True,
        }

    @override
    def get_connection_pool_config(self) -> Dict[str, Any]:
        """Get development connection pool configuration."""
        return {
            "db_pool_min_size": 2,
            "db_pool_max_size": 10,
            "redis_pool_min_size": 2,
            "redis_pool_max_size": 8,
            "http_pool_min_size": 2,
            "http_pool_max_size": 10,
            "enable_pool_metrics": True,
        }

    @override
    def validate_environment_specific_settings(self) -> None:
        """Validate development-specific settings."""
        if not self.settings.tws_mock_mode:  # In development, we can be more lenient but still validate basics
            self.logger.warning(
                "TWS mock mode is disabled in development. Ensure TWS credentials are properly configured."
            )

        # Check for development-friendly settings
        if self.settings.cors_allowed_origins == ["*"]:
            self.logger.info("CORS configured for development (allows all origins)")

        if self.settings.admin_password in ["dev_password_123", "change_me_please"]:
            self.logger.warning(
                "Using default/weak admin password in development. Consider changing for security."
            )


class ProductionManager(EnvironmentManager):
    """Manager for production environment."""

    def __init__(self, settings: Settings):
        super().__init__(settings)

    @override
    def setup_logging(self) -> None:
        """Setup production logging with structured output."""
        # Configure JSON logging for production
        logging.basicConfig(
            level=getattr(logging, self.settings.log_level),
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
            force=True,
        )

        # Add file handler for production logs
        log_file = self.settings.base_dir / "logs" / "app.log"
        log_file.parent.mkdir(exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, self.settings.log_level))

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)

        # Add to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)

        # Prevent duplicate logs in production
        root_logger.setLevel(getattr(logging, self.settings.log_level))

        self.logger.info("Production logging configured")

    @override
    def get_cache_config(self) -> Dict[str, Any]:
        """Get production-optimized cache configuration."""
        return {
            "hierarchy_l1_max_size": min(
                self.settings.cache_hierarchy_l1_max_size, 20000
            ),
            "hierarchy_l2_ttl": self.settings.cache_hierarchy_l2_ttl,
            "hierarchy_l2_cleanup_interval": self.settings.cache_hierarchy_l2_cleanup_interval,
            "hierarchy_num_shards": max(self.settings.cache_hierarchy_num_shards, 8),
            "hierarchy_max_workers": max(self.settings.cache_hierarchy_max_workers, 4),
            "enable_memory_monitoring": True,
            "enable_detailed_metrics": False,  # Reduce overhead in production
        }

    @override
    def get_connection_pool_config(self) -> Dict[str, Any]:
        """Get production connection pool configuration."""
        return {
            "db_pool_min_size": self.settings.db_pool_min_size,
            "db_pool_max_size": self.settings.db_pool_max_size,
            "redis_pool_min_size": self.settings.redis_pool_min_size,
            "redis_pool_max_size": self.settings.redis_pool_max_size,
            "http_pool_min_size": self.settings.http_pool_min_size,
            "http_pool_max_size": self.settings.http_pool_max_size,
            "enable_pool_metrics": False,  # Reduce overhead in production
        }

    def _validate_cors_settings(self) -> None:
        """Validate CORS settings for production."""
        if self.settings.cors_allowed_origins == ["*"]:
            raise ValueError("Wildcard CORS origins not allowed in production")

    def _validate_admin_credentials(self) -> None:
        """Validate admin credentials for production."""
        if not self.settings.admin_password or self.settings.admin_password in [
            "change_me_please",
            "admin",
            "password",
        ]:
            raise ValueError("Secure admin password required for production")

    def _validate_llm_api_key(self) -> None:
        """Validate LLM API key for production."""
        if (
            not self.settings.llm_api_key
            or self.settings.llm_api_key == "dummy_key_for_development"
        ):
            raise ValueError("Valid LLM API key required for production")

    def _validate_tws_settings(self) -> None:
        """Validate TWS settings for production."""
        if self.settings.tws_mock_mode:
            self.logger.warning(
                "TWS is running in mock mode in production. Ensure this is intentional."
            )

    def _validate_connection_settings(self) -> None:
        """Validate database connection settings for production."""
        if (
            not self.settings.redis_url
            or self.settings.redis_url == "redis://localhost:6379/0"
        ):
            raise ValueError("Production Redis URL must be properly configured")

        if (
            not self.settings.neo4j_uri
            or self.settings.neo4j_uri == "bolt://localhost:7687"
        ):
            raise ValueError("Production Neo4j URI must be properly configured")

    @override
    def validate_environment_specific_settings(self) -> None:
        """Validate production-specific settings."""
        # Call specialized validation methods
        self._validate_cors_settings()
        self._validate_admin_credentials()
        self._validate_llm_api_key()
        self._validate_tws_settings()
        self._validate_connection_settings()


class TestManager(EnvironmentManager):
    """Manager for test environment."""

    def __init__(self, settings: Settings):
        super().__init__(settings)

    @override
    def setup_logging(self) -> None:
        """Setup test logging with minimal output."""
        logging.basicConfig(
            level=logging.WARNING,  # Only warnings and errors in tests
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            force=True,
        )

        # Capture warnings to avoid cluttering test output
        logging.captureWarnings(True)

        self.logger.info("Test logging configured")

    @override
    def get_cache_config(self) -> Dict[str, Any]:
        """Get test-optimized cache configuration."""
        return {
            "hierarchy_l1_max_size": 100,
            "hierarchy_l2_ttl": 30,  # 30 seconds for fast tests
            "hierarchy_l2_cleanup_interval": 10,
            "hierarchy_num_shards": 2,
            "hierarchy_max_workers": 1,
            "enable_memory_monitoring": False,
            "enable_detailed_metrics": False,
        }

    @override
    def get_connection_pool_config(self) -> Dict[str, Any]:
        """Get test connection pool configuration."""
        return {
            "db_pool_min_size": 1,
            "db_pool_max_size": 3,
            "redis_pool_min_size": 1,
            "redis_pool_max_size": 3,
            "http_pool_min_size": 1,
            "http_pool_max_size": 3,
            "enable_pool_metrics": False,
        }

    @override
    def validate_environment_specific_settings(self) -> None:
        """Validate test-specific settings."""
        # Tests should use mock mode by default
        if not self.settings.tws_mock_mode:
            self.logger.info("TWS mock mode disabled in tests - ensure test isolation")

        # Tests should use test-specific ports/URLs
        if "localhost:6379" in self.settings.redis_url:
            test_db_number = self.settings.redis_url.split("/")[-1]
            if test_db_number == "0":
                self.logger.warning(
                    "Tests should use dedicated Redis database (not 0) to avoid conflicts"
                )

        if "localhost:7687" in self.settings.neo4j_uri:
            self.logger.info("Using default Neo4j URI in tests - ensure test database")


class EnvironmentManagerFactory:
    """Factory for creating environment managers."""

    _managers: dict[ValidatedEnvironment, Type[EnvironmentManager]] = {
        ValidatedEnvironment.DEVELOPMENT: DevelopmentManager,
        ValidatedEnvironment.PRODUCTION: ProductionManager,
        ValidatedEnvironment.TEST: TestManager,
    }

    @classmethod
    def create_manager(cls, settings: Settings) -> EnvironmentManager:
        """Create appropriate manager for the given settings."""
        # Convert settings environment to validated environment
        validated_env = ValidatedEnvironment(settings.environment.value)
        if validated_env not in cls._managers:
            raise ValueError(f"Unsupported environment: {validated_env.value}")

        manager_class = cls._managers[validated_env]
        return manager_class(settings)

    @classmethod
    def create_development_manager(
        cls, settings: Optional[Settings] = None
    ) -> DevelopmentManager:
        """Create development manager with optional settings."""
        if settings is None:
            settings = SettingsFactory.create_development()
        return DevelopmentManager(settings)

    @classmethod
    def create_production_manager(
        cls, settings: Optional[Settings] = None
    ) -> ProductionManager:
        """Create production manager with optional settings."""
        if settings is None:
            settings = SettingsFactory.create_production()
        return ProductionManager(settings)

    @classmethod
    def create_test_manager(cls, settings: Optional[Settings] = None) -> TestManager:
        """Create test manager with optional settings."""
        if settings is None:
            settings = SettingsFactory.create_test()
        return TestManager(settings)


class EnvironmentService:
    """Service for managing environment-specific operations."""

    def __init__(self, settings: Optional[Settings] = None):  # type: ignore[reportMissingSuperCall]
        self.settings = settings or Settings()
        self.manager = EnvironmentManagerFactory.create_manager(self.settings)
        env_name = self.settings.environment.value
        self.logger = logging.getLogger(f"{self.__class__.__name__}.{env_name}")

        # Register with settings monitor
        settings_monitor.set_settings(self.settings)

    def initialize_environment(self) -> None:
        """Initialize environment-specific configurations."""
        self.logger.info(f"Initializing {self.settings.environment.value} environment")

        # Setup logging
        self.manager.setup_logging()

        # Validate environment-specific settings
        self.manager.validate_environment_specific_settings()

        # Log environment info
        env_info = self.manager.get_environment_info()
        self.logger.info(f"Environment info: {env_info}")

    def get_cache_config(self) -> Dict[str, Any]:
        """Get cache configuration for current environment."""
        return self.manager.get_cache_config()

    def get_connection_pool_config(self) -> Dict[str, Any]:
        """Get connection pool configuration for current environment."""
        return self.manager.get_connection_pool_config()

    def is_production(self) -> bool:
        """Check if running in production."""
        return self.settings.is_production

    def is_development(self) -> bool:
        """Check if running in development."""
        return self.settings.is_development

    def is_test(self) -> bool:
        """Check if running in test."""
        return self.settings.environment == ValidatedEnvironment.TEST

    def reload_settings(self, new_settings: Settings) -> None:
        """Reload settings and reinitialize environment."""
        old_environment = self.settings.environment
        self.settings = new_settings
        self.manager = EnvironmentManagerFactory.create_manager(self.settings)

        # Update settings monitor
        settings_monitor.set_settings(new_settings)

        # Reinitialize if environment changed
        if old_environment != new_settings.environment:
            self.initialize_environment()
        else:
            self.logger.info("Settings reloaded for same environment")


# Global environment service instance
environment_service = EnvironmentService()
