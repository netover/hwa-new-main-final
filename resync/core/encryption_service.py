"""
Encryption service for Resync core.
"""

import base64
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class EncryptionService:
    """Simple encryption service for sensitive data handling."""

    def __init__(self, key: Optional[bytes] = None):
        # In production, the key should be stored securely
        if key:
            self.key = key
        else:
            env_key = os.getenv("ENCRYPTION_KEY")
            if env_key:
                self.key = env_key.encode()
            else:
                # This is still not ideal in production - key should be provided
                self.key = Fernet.generate_key()
        self.cipher_suite = Fernet(self.key)

    @staticmethod
    def generate_key() -> bytes:
        """Generate a new encryption key."""
        return Fernet.generate_key()

    def encrypt(self, data: str) -> str:
        """Encrypt sensitive data."""
        if not isinstance(data, str):
            data = str(data)
        encrypted_data = self.cipher_suite.encrypt(data.encode())
        return base64.b64encode(encrypted_data).decode()

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt data."""
        try:
            encrypted_bytes = base64.b64decode(encrypted_data.encode())
            decrypted_data = self.cipher_suite.decrypt(encrypted_bytes)
            return decrypted_data.decode()
        except Exception as e:
            # If decryption fails, raise an exception instead of returning original data
            logger.error(
                "decryption_failed",
                encrypted_data_preview=encrypted_data[:50],
                error=str(e),
            )
            raise ValueError(f"Decryption failed: {str(e)}") from e


# Global instance
encryption_service = EncryptionService()


# Logger masking
logger = logging.getLogger(__name__)


def mask_sensitive_data_in_logs(record) -> None:
    """Mask sensitive data in log records."""
    if hasattr(record, "msg"):
        msg_str = str(record.msg)
        # Replace entire lines containing password with masked version
        lines = msg_str.split("\n")
        masked_lines = []

        for line in lines:
            if "password" in line.lower():
                # Mask the entire line containing password
                masked_lines.append("*** PASSWORD LOG ENTRY MASKED ***")
            else:
                masked_lines.append(line)

        record.msg = "\n".join(masked_lines)
    return True


logging.getLogger().addFilter(mask_sensitive_data_in_logs)
