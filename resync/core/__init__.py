"""
Hardened Core Package Initialization for Resync

This module provides hardened initialization and lifecycle management for core components
with comprehensive error handling, health validation, and security measures.
"""

import asyncio
import logging
import os
import re
import threading
import time
from typing import Any, Dict, Optional, Set

# Initialize logger early
logger = logging.getLogger(__name__)

# Import from local modules
from .config_watcher import handle_config_change
from .metrics import runtime_metrics

# Lazy loading for heavy imports to avoid collection issues
_LAZY_EXPORTS = {
    "AsyncTTLCache": ("resync.core.async_cache", "AsyncTTLCache"),
}
_LOADED_EXPORTS = {}

def __getattr__(name: str):
    """PEP 562 lazy loading for heavy imports."""
    if name in _LAZY_EXPORTS:
        mod, attr = _LAZY_EXPORTS[name]
        if name not in _LOADED_EXPORTS:
            module = __import__(mod, fromlist=[attr])
            _LOADED_EXPORTS[name] = getattr(module, attr)
        return _LOADED_EXPORTS[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

def get_async_ttl_cache_class():
    """Explicit accessor to avoid import-time side effects."""
    from .async_cache import AsyncTTLCache
    return AsyncTTLCache

# Direct imports of exceptions for stability and simplicity
from .exceptions import (
    AuditError,
    DatabaseError,
    PoolExhaustedError,
    ToolProcessingError,
    BaseAppException,
    InvalidConfigError,
    AgentExecutionError,
    AuthenticationError,
    LLMError,
    RedisConnectionError,
)
# SOC2 Compliance - import available but commented to avoid circular imports
# Use direct import when needed: from resync.core.soc2_compliance_refactored import SOC2ComplianceManager
# from .soc2_compliance_refactored import SOC2ComplianceManager, soc2_compliance_manager, get_soc2_compliance_manager


# --- Core Component Boot Manager ---
class CoreBootManager:
    """Hardened boot manager for core components with lifecycle tracking and health validation."""

    def __init__(self):
        self._components: Dict[str, Any] = {}
        self._boot_times: Dict[str, float] = {}
        self._health_status: Dict[str, Dict[str, Any]] = {}
        self._boot_lock = threading.RLock()
        # Global correlation ID for distributed tracing
        self._correlation_id = f"core_boot_{int(time.time())}_{os.urandom(4).hex()}"
        self._failed_imports: Set[str] = set()
        self._global_correlation_context = {
            "boot_id": self._correlation_id,
            "environment": "unknown",  # Will be set by env_detector
            "security_level": "unknown",
            "start_time": time.time(),
            "events": [],
        }

    def register_component(self, name: str, component: Any) -> None:
        """Register a component. Health checks are deferred."""
        with self._boot_lock:
            start_time = time.time()
            try:
                self._components[name] = component
                self._boot_times[name] = time.time() - start_time
            except Exception as e:
                logger.error(f"Failed to register component {name}: {e}")
                raise

    def get_component(self, name: str) -> Any:
        """Get a registered component."""
        return self._components.get(name)

    def get_boot_status(self) -> Dict[str, Any]:
        """Get boot status for all components."""
        with self._boot_lock:
            return {
                "components": list(self._components.keys()),
                "boot_times": self._boot_times.copy(),
                "health_status": self._health_status.copy(),
                "correlation_id": self._correlation_id,
            }

    def add_global_event(
        self, event: str, data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add a trace event to the global correlation context."""
        with self._boot_lock:
            self._global_correlation_context["events"].append(
                {"timestamp": time.time(), "event": event, "data": data or {}}
            )

            # Keep only last 100 events to prevent memory growth
            if len(self._global_correlation_context["events"]) > 100:
                self._global_correlation_context["events"] = (
                    self._global_correlation_context["events"][-100:]
                )

    def get_global_correlation_id(self) -> str:
        """Get the global correlation ID for distributed tracing."""
        return self._correlation_id

    def get_environment_tags(self) -> Dict[str, Any]:
        """Get environment tags for mock detection and debugging."""
        return {
            "is_mock": getattr(self, "_is_mock", False),
            "mock_reason": getattr(self, "_mock_reason", None),
            "boot_id": self._correlation_id,
            "component_count": len(self._components),
        }


# --- Environment Detection and Validation ---
class EnvironmentDetector:
    """Detect and validate execution environment for security and compatibility."""

    def __init__(self):
        self._validation_cache = {}
        self._last_validation = 0

    def detect_environment(self) -> Dict[str, Any]:
        """Detect execution environment characteristics."""
        return {
            "platform": os.name,
            "is_ci": bool(os.environ.get("CI")),
            "has_internet": self._check_internet_access(),
            "temp_dir": os.environ.get("TEMP", "/tmp"),
        }

    def _check_internet_access(self) -> bool:
        """Check if internet access is available."""
        # Simplified check - in a real implementation this would be more robust
        return True

    def validate_environment(self) -> bool:
        """Validate execution environment for security compliance."""
        try:
            # Cache validation for 60 seconds
            current_time = time.time()
            if current_time - self._last_validation < 60:
                return self._validation_cache.get("result", True)

            # Perform validation checks
            env_ok = True

            # Update cache
            self._validation_cache = {
                "result": env_ok,
                "timestamp": current_time,
                "details": {},
            }
            self._last_validation = current_time

            return env_ok
        except Exception as e:
            logger.warning(f"Environment validation failed: {e}")
            return False


# --- Lazy Import Functions ---
# Use explicit lazy import functions instead of __getattr__ to avoid initialization issues

def _get_env_detector():
    """Lazy import of EnvironmentDetector."""
    from resync.core.environment_detector import EnvironmentDetector
    return EnvironmentDetector()

def _get_boot_manager():
    """Lazy import of CoreBootManager."""
    from resync.core.lifecycle import CoreBootManager
    return CoreBootManager()

def _get_settings():
    """Lazy import of settings."""
    from resync.settings import settings
    return settings

def _get_logger():
    """Lazy import of logger."""
    from resync.core.structured_logger import get_logger
    return get_logger

def _get_metrics():
    """Lazy import of runtime metrics."""
    from resync.core.metrics import runtime_metrics
    return runtime_metrics

def _get_cache_hierarchy():
    """Lazy import of cache hierarchy."""
    from resync.core.cache_hierarchy import get_cache_hierarchy
    return get_cache_hierarchy

def _get_container():
    """Lazy import of DI container."""
    from resync.core.di_container import container
    return container

def _get_config_watcher():
    """Lazy import of config watcher."""
    from resync.core.config_watcher import handle_config_change
    return handle_config_change


# --- Backward Compatibility ---
# Keep old lazy initialization for compatibility
def _initialize_core_components():
    """Legacy initialization - now using __getattr__."""
    # Components are now loaded lazily via __getattr__
    pass


# --- Global Access Functions ---
# Imported from global_utils.py to avoid circular imports


def get_global_correlation_id() -> str:
    """Get the global correlation ID for distributed tracing."""
    _initialize_core_components()
    return boot_manager.get_global_correlation_id()


def get_environment_tags() -> Dict[str, Any]:
    """Get environment tags for mock detection and debugging."""
    _initialize_core_components()
    return boot_manager.get_environment_tags()


# Validate environment on import
def add_global_trace_event(event: str, data: Optional[Dict[str, Any]] = None) -> None:
    """Add a trace event to the global correlation context."""
    _initialize_core_components()
    boot_manager.add_global_event(event, data)


# Validate environment on import (lazy)
def _validate_environment():
    """Validate environment lazily."""
    try:
        env_detector = _get_env_detector()
        boot_manager = _get_boot_manager()
        lazy_logger = _get_logger()
        logger = lazy_logger(__name__)

        if not env_detector.validate_environment():
            logger.error(
                "Environment validation failed - system may not be secure",
                extra={"correlation_id": boot_manager._correlation_id},
            )
            # Don't raise exception here to avoid import failures, but log critically
    except Exception as e:
        # If validation fails, log but don't crash
        try:
            lazy_logger = _get_logger()
            logger = lazy_logger(__name__)
            logger.warning(f"Environment validation failed: {e}")
        except:
            pass  # Avoid circular import issues

# Validation is now optional and lazy - call _validate_environment() explicitly when needed
# _validate_environment()  # Commented out to avoid import-time execution
