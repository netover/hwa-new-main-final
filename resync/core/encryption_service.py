"""
Encryption Service Module

This module provides encryption/decryption functionality for sensitive data.
For development/testing purposes, this implements a simple reversible encoding
rather than actual encryption.
"""

from __future__ import annotations

import base64
import hashlib
from typing import Any, Union


class EncryptionService:
    """
    Service for encrypting and decrypting sensitive data.

    In production, this should use proper encryption algorithms like AES.
    For development/testing, this uses a simple reversible encoding.
    """

    def __init__(self, key: str = "default_dev_key"):
        """
        Initialize the encryption service.

        Args:
            key: Encryption key (not used in dev mode)
        """
        self.key = key

    def encrypt(self, data: Union[str, bytes, dict, list]) -> str:
        """
        Encrypt data.

        In development mode, this creates a reversible encoding.
        In production, this should use proper encryption.

        Args:
            data: Data to encrypt

        Returns:
            Encrypted data as string
        """
        # Convert data to string if needed
        if isinstance(data, (dict, list)):
            data_str = str(data)
        elif isinstance(data, bytes):
            data_str = data.decode('utf-8')
        else:
            data_str = str(data)

        # Simple reversible encoding for development
        # In production, this should use proper encryption
        encoded = base64.b64encode(data_str.encode('utf-8')).decode('utf-8')

        # Add a hash for integrity checking
        data_hash = hashlib.sha256(data_str.encode('utf-8')).hexdigest()[:8]
        return f"ENC:{data_hash}:{encoded}"

    def decrypt(self, encrypted_data: str) -> Any:
        """
        Decrypt data.

        Args:
            encrypted_data: Encrypted data string

        Returns:
            Decrypted data

        Raises:
            ValueError: If data cannot be decrypted or integrity check fails
        """
        if not encrypted_data.startswith("ENC:"):
            raise ValueError("Invalid encrypted data format")

        try:
            parts = encrypted_data.split(":", 2)
            if len(parts) != 3:
                raise ValueError("Invalid encrypted data format")

            expected_hash = parts[1]
            encoded_data = parts[2]

            # Decode the data
            decoded_bytes = base64.b64decode(encoded_data)
            decoded_str = decoded_bytes.decode('utf-8')

            # Verify integrity
            actual_hash = hashlib.sha256(decoded_str.encode('utf-8')).hexdigest()[:8]
            if actual_hash != expected_hash:
                raise ValueError("Data integrity check failed")

            # Try to parse back to original type if it was a dict/list
            if decoded_str.startswith("{") and decoded_str.endswith("}"):
                # This was a dict representation
                return decoded_str  # Return as string for now
            elif decoded_str.startswith("[") and decoded_str.endswith("]"):
                # This was a list representation
                return decoded_str  # Return as string for now
            else:
                return decoded_str

        except Exception as e:
            raise ValueError(f"Failed to decrypt data: {e}")

    async def encrypt_async(self, data: Any) -> str:
        """
        Async version of encrypt.

        Args:
            data: Data to encrypt

        Returns:
            Encrypted data as string
        """
        return self.encrypt(data)

    async def decrypt_async(self, encrypted_data: str) -> Any:
        """
        Async version of decrypt.

        Args:
            encrypted_data: Encrypted data string

        Returns:
            Decrypted data
        """
        return self.decrypt(encrypted_data)


# Global encryption service instance
encryption_service = EncryptionService()
