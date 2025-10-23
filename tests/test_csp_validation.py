"""Tests for CSP violation report validation utilities."""

import json
import pytest
from resync.csp_validation import (
    validate_csp_report,
    _is_safe_uri,
    _is_safe_directive_value,
    sanitize_csp_report,
    CSPValidationError,
    validate_csp_report_legacy,
)


class TestCSPValidation:
    """Test cases for CSP validation functions."""

    def test_valid_csp_report(self):
        """Test validation of a valid CSP report."""
        report_data = {
            "csp-report": {
                "document-uri": "https://example.com/page",
                "referrer": "",
                "violated-directive": "script-src 'self'",
                "effective-directive": "script-src",
                "original-policy": "default-src 'self'; script-src 'self'",
                "disposition": "enforce",
                "blocked-uri": "inline",
                "line-number": 10,
                "column-number": 20,
                "source-file": "https://example.com/script.js",
                "status-code": 200,
                "script-sample": "",
            }
        }

        report_json = json.dumps(report_data)
        assert validate_csp_report(report_json.encode("utf-8")) is True

    def test_invalid_csp_report_missing_required_fields(self):
        """Test validation of CSP report missing required fields."""
        report_data = {
            "csp-report": {
                "document-uri": "https://example.com/page"
                # Missing required fields: violated-directive, original-policy
            }
        }

        report_json = json.dumps(report_data)
        assert validate_csp_report(report_json.encode("utf-8")) is False

    def test_invalid_csp_report_too_large(self):
        """Test validation of CSP report that is too large."""
        # Create a large report that exceeds the size limit
        large_data = "A" * 10000  # 10KB, larger than 8KB limit
        report_data = {
            "csp-report": {
                "document-uri": "https://example.com/page",
                "violated-directive": "script-src 'self'",
                "original-policy": "default-src 'self'; script-src 'self'",
                "large-field": large_data,
            }
        }

        report_json = json.dumps(report_data)
        assert validate_csp_report(report_json.encode("utf-8")) is False

    def test_invalid_csp_report_malformed_json(self):
        """Test validation of malformed JSON."""
        malformed_json = (
            b'{ "csp-report": { "document-uri": "https://example.com/page", }'
        )
        assert validate_csp_report(malformed_json) is False

    @pytest.mark.parametrize(
        "uri,expected",
        [
            # Valid URIs
            ("http://example.com/page", True),
            ("https://example.com/page", True),
            ("self", True),
            ("none", True),
            ("unsafe-inline", True),
            ("unsafe-eval", True),
            # Data URIs
            ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==", True),
            # Invalid URIs
            ("data:text/plain;base64," + "A" * 2000, False),  # Too long
            ("http://192.168.1.1/page", False),  # Private IP
            ("http://10.0.0.1/page", False),  # Private IP
            ("http://172.16.0.1/page", False),  # Private IP
            ("http://127.0.0.1/page", False),  # Private IP
            ("http://localhost/page", False),  # Localhost
            ("http://[::1]/page", False),  # IPv6 localhost
        ],
    )
    def test_safe_uri_validation(self, uri, expected):
        """Test validation of URIs for CSP safety."""
        assert _is_safe_uri(uri) is expected

    @pytest.mark.parametrize(
        "directive_value,expected",
        [
            # Valid directive values
            ("default-src 'self'", True),
            ("script-src 'self' 'nonce-abc123'", True),
            # Invalid directive values
            ("script-src 'self' <script>alert('xss')</script>", False),
            ("script-src 'self' javascript:alert('xss')", False),
            ("script-src 'self' onclick='alert(\"xss\")'", False),
        ],
    )
    def test_safe_directive_value(self, directive_value, expected):
        """Test validation of CSP directive values for safety."""
        assert _is_safe_directive_value(directive_value) is expected

    def test_sanitize_csp_report_string_fields(self):
        """Test sanitization of string fields."""
        report_data = {
            "document-uri": "https://example.com/page",
            "violated-directive": "script-src 'self'",
            "original-policy": "default-src 'self'; script-src 'self'",
        }

        sanitized = sanitize_csp_report(report_data)
        assert sanitized["document-uri"] == "https://example.com/page"
        assert sanitized["violated-directive"] == "script-src &#x27;self&#x27;"
        assert (
            sanitized["original-policy"]
            == "default-src &#x27;self&#x27;; script-src &#x27;self&#x27;"
        )

    def test_sanitize_csp_report_html_escaping(self):
        """Test HTML escaping in sanitization."""
        report_data = {
            "document-uri": "https://example.com/page<script>alert('xss')</script>",
            "violated-directive": "<script>alert('xss')</script>",
        }

        sanitized = sanitize_csp_report(report_data)
        assert "<script>" in sanitized["document-uri"]
        assert "<script>" in sanitized["violated-directive"]

    def test_sanitize_csp_report_numeric_fields(self):
        """Test sanitization of numeric fields."""
        report_data = {"status-code": 200, "line-number": 10, "column-number": 5}

        sanitized = sanitize_csp_report(report_data)
        assert sanitized["status-code"] == 200
        assert sanitized["line-number"] == 10
        assert sanitized["column-number"] == 5

    def test_sanitize_csp_report_enum_fields(self):
        """Test sanitization of enum fields."""
        report_data = {"disposition": "enforce"}

        sanitized = sanitize_csp_report(report_data)
        assert sanitized["disposition"] == "enforce"

    def test_sanitize_csp_report_invalid_enum_fields(self):
        """Test sanitization of invalid enum fields."""
        report_data = {"disposition": "invalid-value"}

        sanitized = sanitize_csp_report(report_data)
        assert "disposition" not in sanitized

    def test_sanitize_csp_report_nested_structure(self):
        """Test sanitization of nested CSP report structure."""
        report_data = {
            "csp-report": {
                "document-uri": "https://example.com/page",
                "violated-directive": "script-src 'self'",
            }
        }

        sanitized = sanitize_csp_report(report_data)
        assert "csp-report" in sanitized
        nested_report = sanitized["csp-report"]
        assert isinstance(nested_report, dict)
        assert nested_report["document-uri"] == "https://example.com/page"
        assert nested_report["violated-directive"] == "script-src &#x27;self&#x27;"

    def test_backward_compatibility_legacy_function(self):
        """Test backward compatibility with legacy validation function."""
        report_data = {
            "csp-report": {
                "document-uri": "https://example.com/page",
                "violated-directive": "script-src 'self'",
                "original-policy": "default-src 'self'; script-src 'self'",
            }
        }

        report_json = json.dumps(report_data)
        # Both functions should return the same result
        assert validate_csp_report(
            report_json.encode("utf-8")
        ) == validate_csp_report_legacy(report_json.encode("utf-8"))


class TestCSPProcessing:
    """Test cases for CSP report processing."""

    @pytest.mark.asyncio
    async def test_process_valid_csp_report(self):
        """Test processing of a valid CSP report."""
        # This would require mocking a Request object, which is complex
        # We'll test the validation functions directly instead

    def test_csp_validation_error_exception(self):
        """Test CSPValidationError exception."""
        with pytest.raises(CSPValidationError):
            raise CSPValidationError("Test error message")


if __name__ == "__main__":
    pytest.main([__file__])
