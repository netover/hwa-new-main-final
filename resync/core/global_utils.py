"""
Global utilities for the Resync core package.

This module provides global access to core system components and utilities
that need to be accessible across the entire application. It serves as a
centralized hub for system-wide resources and correlation tracking.

The module implements a global boot manager pattern that allows different
parts of the application to access shared state and correlation information
without creating circular import dependencies.

Key features:
- Global correlation ID tracking for distributed tracing
- Environment tag detection for debugging and monitoring
- Boot manager access for component lifecycle management
- Type-safe global state management

Warning:
    This module uses global state. Changes to global references should be
    made with caution and only during application initialization.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from . import CoreBootManager

# Global reference to boot manager
_boot_manager: Optional["CoreBootManager"] = None


def set_boot_manager(boot_manager: "CoreBootManager") -> None:
    """
    Set the global boot manager reference.

    This function establishes the global reference to the core boot manager,
    which is used throughout the application for component lifecycle management,
    correlation tracking, and global state access.

    Args:
        boot_manager: The CoreBootManager instance to set as global reference.

    Note:
        This function should only be called once during application initialization.
        Calling it multiple times will overwrite the previous reference.
    """
    global _boot_manager
    _boot_manager = boot_manager


def get_global_correlation_id() -> str:
    """
    Get the global correlation ID for distributed tracing.

    This function provides access to the application's global correlation ID,
    which is used for distributed tracing, request correlation, and debugging
    across all components.

    Returns:
        str: The global correlation ID string.

    Note:
        If the boot manager is not yet initialized, a fallback correlation ID
        will be generated. This ensures tracing works even during early
        initialization phases.
    """
    if _boot_manager is None:
        # Fallback if boot manager not set yet
        import os
        import time

        return f"fallback_{int(time.time())}_{os.urandom(4).hex()}"
    return _boot_manager.get_global_correlation_id()


def get_environment_tags() -> Dict[str, Any]:
    """
    Get environment tags for mock detection and debugging.

    This function returns environment information and tags that help with
    debugging, monitoring, and mock detection. The tags include information
    about the boot process, component count, and mock status.

    Returns:
        Dict[str, Any]: Dictionary containing environment tags with keys:
            - is_mock: Boolean indicating if running in mock mode
            - mock_reason: Reason for mock mode (if applicable)
            - boot_id: Global boot correlation ID
            - component_count: Number of registered components

    Note:
        If the boot manager is not yet initialized, returns a minimal
        fallback dictionary indicating the boot manager is not ready.
    """
    if _boot_manager is None:
        # Fallback if boot manager not set yet
        return {"boot_manager": "not_initialized"}
    return _boot_manager.get_environment_tags()
