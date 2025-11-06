"""
Security Module

This module provides security-related functionality including OAuth2 authentication.
"""

from .oauth2 import User, create_oauth2_token, verify_oauth2_token

__all__ = ["User", "create_oauth2_token", "verify_oauth2_token"]
