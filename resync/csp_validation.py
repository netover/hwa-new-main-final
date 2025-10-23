"""CSP violation report validation utilities."""

import json
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

from typing_extensions import Literal

if TYPE_CHECKING:
    from fastapi import Request

# Maximum allowed size for CSP reports (8KB)
MAX_REPORT_SIZE = 8192

# Maximum URI length
MAX_URI_LENGTH = 2048

# Maximum directive value length
MAX_DIRECTIVE_LENGTH = 1000

# Maximum data URI length
MAX_DATA_URI_LENGTH = 1000

# Required fields in a valid CSP report
REQUIRED_FIELDS = {"document-uri", "violated-directive", "original-policy"}

# Optional known fields
OPTIONAL_FIELDS = {
    "blocked-uri",
    "status-code",
    "referrer",
    "script-sample",
    "disposition",
    "line-number",
    "column-number",
    "source-file",
    "effective-directive",
}

# Special values for blocked-uri that are valid
BLOCKED_URI_SPECIAL_VALUES = {"inline", "eval", "self", "none", "about:blank"}

# Dangerous patterns to block
DANGEROUS_PATTERNS = [
    r"<script",
    r"javascript:",
    r"data:",
    r"vbscript:",
    r"on\w+\s*=",
    r"\b(alert|prompt|confirm)\s*\(",
]

# Pre-compiled regex patterns for performance
HTTP_HTTPS_PATTERN = re.compile(r"^https?://")
PRIVATE_IP_PATTERN = re.compile(
    r"^(127\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)"
)
SANITIZE_KEY_PATTERN = re.compile(r"[^\w\-\.]")

# Pre-compile dangerous patterns
DANGEROUS_PATTERNS_COMPILED = [
    re.compile(pattern, re.IGNORECASE) for pattern in DANGEROUS_PATTERNS
]


@dataclass
class CSPReport:
    """Dataclass for structured CSP report validation."""

    document_uri: str
    violated_directive: str
    original_policy: str
    blocked_uri: Optional[str] = None
    status_code: Optional[int] = None
    referrer: Optional[str] = None
    script_sample: Optional[str] = None
    disposition: Optional[Literal["enforce", "report"]] = None
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    source_file: Optional[str] = None
    effective_directive: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional["CSPReport"]:
        """Create CSPReport instance from dictionary data."""
        try:
            # Extract nested csp-report if present
            report_data = data
            if "csp-report" in data:
                report_data = data["csp-report"]

            if not isinstance(report_data, dict):
                return None

            return cls(
                document_uri=report_data.get("document-uri", ""),
                violated_directive=report_data.get("violated-directive", ""),
                original_policy=report_data.get("original-policy", ""),
                blocked_uri=report_data.get("blocked-uri"),
                status_code=report_data.get("status-code"),
                referrer=report_data.get("referrer"),
                script_sample=report_data.get("script-sample"),
                disposition=report_data.get("disposition"),
                line_number=report_data.get("line-number"),
                column_number=report_data.get("column-number"),
                source_file=report_data.get("source-file"),
                effective_directive=report_data.get("effective-directive"),
            )
        except (TypeError, ValueError):
            return None

    def validate(self) -> bool:
        """Validate the CSP report structure and content."""
        # Check required fields
        if not all([self.document_uri, self.violated_directive, self.original_policy]):
            return False

        # Validate URIs
        uri_fields = [
            ("document-uri", self.document_uri, False),
            ("blocked-uri", self.blocked_uri, True),
            ("referrer", self.referrer, False),
            ("source-file", self.source_file, False),
        ]

        for field_name, uri_value, is_blocked_uri in uri_fields:
            if uri_value and not _is_safe_uri(uri_value, is_blocked_uri):
                return False

        # Validate directive values
        directive_fields = [
            self.violated_directive,
            self.effective_directive,
            self.original_policy,
        ]

        for directive_value in directive_fields:
            if directive_value and not _is_safe_directive_value(directive_value):
                return False

        # Validate numeric fields
        numeric_fields = [
            ("status-code", self.status_code),
            ("line-number", self.line_number),
            ("column-number", self.column_number),
        ]

        for field_name, numeric_value in numeric_fields:
            if numeric_value is not None and not isinstance(
                numeric_value, (int, float)
            ):
                return False

        # Validate disposition
        if self.disposition and self.disposition not in ["enforce", "report"]:
            return False

        return True


class CSPValidationError(Exception):
    """Custom exception for CSP validation errors."""


def validate_csp_report(body: bytes) -> bool:
    """
    Validate CSP violation report format and content with enhanced security.

    Args:
        body: Raw bytes of the CSP report

    Returns:
        bool: True if valid, False otherwise
    """
    try:
        # Size limit
        if len(body) > MAX_REPORT_SIZE:
            return False

        report_data = json.loads(body.decode("utf-8"))

        # Use CSPReport dataclass for structured validation
        csp_report = CSPReport.from_dict(report_data)
        if csp_report is None:
            return False

        # Validate using dataclass validation
        return csp_report.validate()
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError):
        return False


def _is_safe_uri(uri: str, is_blocked_uri: bool = False) -> bool:
    """
    Validate that a URI is safe and conforms to expected formats.

    Args:
        uri: URI string to validate
        is_blocked_uri: Whether this is a blocked-uri field (has special valid values)

    Returns:
        bool: True if URI is safe, False otherwise
    """
    if not isinstance(uri, str):
        return False

    # Length limit
    if len(uri) > MAX_URI_LENGTH:
        return False

    # For blocked-uri, allow special values
    if is_blocked_uri and uri in BLOCKED_URI_SPECIAL_VALUES:
        return True

    # Must be HTTP/HTTPS only
    if not HTTP_HTTPS_PATTERN.match(uri):
        # Allow relative URLs and special values
        if uri in ["", "self", "none", "unsafe-inline", "unsafe-eval", "about:blank"]:
            return True
        # Allow data URIs for specific cases
        if uri.startswith("data:"):
            return len(uri) <= MAX_DATA_URI_LENGTH
        return False

    # Validate hostname
    hostname_match = re.search(r"^https?://([^/]+)", uri)
    if not hostname_match:
        return False

    hostname = hostname_match.group(1)

    # Block private IP addresses
    if PRIVATE_IP_PATTERN.match(hostname):
        return False

    # Block localhost variations
    if hostname.lower() in ["localhost", "[::1]"]:
        return False

    return True


def _is_safe_directive_value(value: str) -> bool:
    """
    Validate that a CSP directive value is safe.

    Args:
        value: Directive value to validate

    Returns:
        bool: True if value is safe, False otherwise
    """
    if not isinstance(value, str):
        return False

    # Length limit
    if len(value) > MAX_DIRECTIVE_LENGTH:
        return False

    # Block dangerous patterns
    for pattern in DANGEROUS_PATTERNS_COMPILED:
        if pattern.search(value):
            return False

    return True


def sanitize_csp_report(
    report_data: Dict[str, Any],
) -> Dict[str, Union[str, int, float, None]]:
    """
    Sanitize CSP report data to prevent XSS and other injection attacks.

    Args:
        report_data: Raw CSP report data

    Returns:
        Dict[str, Any]: Sanitized report data
    """
    sanitized: Dict[str, Union[str, int, float, None]] = {}

    # Fields that should remain as strings
    string_fields = [
        "document-uri",
        "violated-directive",
        "original-policy",
        "blocked-uri",
        "referrer",
        "script-sample",
        "source-file",
        "effective-directive",
    ]

    # Fields that should remain as integers
    int_fields = ["status-code", "line-number", "column-number"]

    # Fields with specific allowed values
    enum_fields = {"disposition": ["enforce", "report"]}

    for key, value in report_data.items():
        # Sanitize key name
        safe_key = SANITIZE_KEY_PATTERN.sub("", str(key))[:100]

        if safe_key in string_fields and isinstance(value, str):
            # Truncate and escape HTML special characters
            safe_value = value[:1000]
            # Basic HTML escaping
            safe_value = (
                safe_value.replace("&", "&")
                .replace("<", "<")
                .replace(">", ">")
                .replace('"', '"')
                .replace("'", "&#x27;")
            )
            sanitized[safe_key] = safe_value
        elif safe_key in int_fields and isinstance(value, (int, float)):
            sanitized[safe_key] = value
        elif safe_key in enum_fields and value in enum_fields[safe_key]:
            sanitized[safe_key] = value
        elif safe_key == "csp-report":
            # Handle nested csp-report structure
            if isinstance(value, dict):
                sanitized[safe_key] = sanitize_csp_report(value)

    return sanitized


@asynccontextmanager
async def csp_report_context(request: "Request") -> "Request":
    """
    Async context manager for handling CSP report processing.

    Args:
        request: The incoming request containing CSP report data

    Yields:
        Request: The request object for processing
    """
    try:
        # Pre-processing
        yield request
    finally:
        # Post-processing cleanup if needed
        pass


async def process_csp_report(request: "Request") -> Dict[str, Any]:
    """
    Process a CSP violation report with enhanced validation and security.

    Args:
        request: The incoming request containing CSP report data

    Returns:
        Dict[str, Any]: Processing result

    Raises:
        CSPValidationError: If the report is invalid
    """
    try:
        body = await request.body()

        # Enhanced CSP report validation
        if not validate_csp_report(body):
            raise CSPValidationError("Invalid CSP report format")

        # Parse and sanitize the report
        report_data = json.loads(body.decode("utf-8"))
        sanitized_data = sanitize_csp_report(report_data)

        return {"status": "processed", "report": sanitized_data}

    except json.JSONDecodeError as e:
        raise CSPValidationError(f"Invalid JSON in CSP report: {str(e)}")
    except Exception as e:
        raise CSPValidationError(f"Error processing CSP report: {str(e)}")


# Backward compatibility function
def validate_csp_report_legacy(body: bytes) -> bool:
    """
    Legacy function for backward compatibility.

    Args:
        body: Raw bytes of the CSP report

    Returns:
        bool: True if valid, False otherwise
    """
    return validate_csp_report(body)
