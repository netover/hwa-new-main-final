"""Idempotency package.

This package provides utilities for implementing idempotent APIs.  The
original implementation has been removed as part of a codebase cleanup to
reduce complexity.  To maintain backwards compatibility and allow the
existing imports throughout the codebase to resolve without raising
``ModuleNotFoundError``, we provide a minimal, no-op implementation of
``IdempotencyManager`` here.

The provided ``IdempotencyManager`` class exposes the same interface as
the original implementation but does not perform any idempotency
persistence.  It can be extended in the future if idempotency is
required.
"""

from .manager import IdempotencyManager

__all__ = ["IdempotencyManager"]



