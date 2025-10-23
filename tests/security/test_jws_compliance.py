#!/usr/bin/env python3
"""
JWS Token Compliance Test Suite for authlib 1.6.4+
Tests RFC 7515 "must-understand" critical header compliance

This script validates that our token issuer sends only compliant critical headers
and that the system rejects invalid ones as required by authlib 1.6.4+.
"""

import json
import unittest

from authlib.jose.errors import (
    InvalidCritHeaderParameterNameError,
    InvalidHeaderParameterNameError,
    JoseError,
)
from authlib.jose.rfc7515 import JsonWebSignature


class TestJWSCompliance(unittest.TestCase):
    """Test suite for JWS token compliance with RFC 7515"""

    def setUp(self):
        """Setup test environment"""
        # Use HS256 for testing - same as production
        self.secret = b"0123456789abcdef0123456789abcdef"  # 32-byte key
        self.jws = JsonWebSignature()

    def test_token_with_unknown_critical_header(self):
        """Test: Token with unknown critical header (bork) - must be rejected"""
        # This is the CVE-2025-59420 attack vector
        protected_header = {
            "alg": "HS256",
            "crit": ["bork"],  # Unknown header - must be rejected
            "bork": "malicious-value",
        }

        payload = {"sub": "123", "role": "user", "exp": 9999999999}

        # Sign token - must fail with InvalidCritHeaderParameterNameError
        with self.assertRaises(InvalidCritHeaderParameterNameError) as context:
            self.jws.serialize_compact(
                protected_header,
                json.dumps(payload).encode("utf-8"),
                self.secret,
            )

        # Verify it fails for the right reason
        self.assertIn("Invalid Header Parameter Name", str(context.exception))

    def test_token_without_crit_header(self):
        """Test: Token without crit header - should be accepted (standard case)"""
        protected_header = {"alg": "HS256"}

        payload = {"sub": "123", "role": "user", "exp": 9999999999}

        token = self.jws.serialize_compact(
            protected_header, json.dumps(payload).encode("utf-8"), self.secret
        )

        # Verify - must succeed
        try:
            data = self.jws.deserialize_compact(token, self.secret)
            # Parse the payload which comes back as bytes
            payload = json.loads(data["payload"].decode("utf-8"))
            self.assertEqual(payload["sub"], "123")
        except JoseError as e:
            self.fail(f"Standard token rejected: {e}")

    def test_token_with_empty_crit_list(self):
        """Test: Token with empty crit list - should be accepted"""
        protected_header = {
            "alg": "HS256",
            "crit": [],
        }  # Empty list - valid per RFC

        payload = {"sub": "123", "role": "user", "exp": 9999999999}

        token = self.jws.serialize_compact(
            protected_header, json.dumps(payload).encode("utf-8"), self.secret
        )

        # Verify - must succeed
        try:
            data = self.jws.deserialize_compact(token, self.secret)
            # Parse the payload which comes back as bytes
            payload = json.loads(data["payload"].decode("utf-8"))
            self.assertEqual(payload["sub"], "123")
        except JoseError as e:
            self.fail(f"Token with empty crit rejected: {e}")

    def test_token_with_non_array_crit(self):
        """Test: Token with non-array crit - must be rejected"""
        protected_header = {
            "alg": "HS256",
            "crit": "cnf",
        }  # Invalid: must be array

        payload = {"sub": "123", "role": "user", "exp": 9999999999}

        # Sign token - must fail with InvalidHeaderParameterNameError
        with self.assertRaises(InvalidHeaderParameterNameError) as context:
            self.jws.serialize_compact(
                protected_header,
                json.dumps(payload).encode("utf-8"),
                self.secret,
            )

        self.assertIn("crit", str(context.exception))


if __name__ == "__main__":
    # Run tests
    unittest.main()
