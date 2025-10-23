from __future__ import annotations

import json
from resync.csp_validation import (
    validate_csp_report,
    _is_safe_uri,
    _is_safe_directive_value,
)

# Test data
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
result = validate_csp_report(report_json.encode("utf-8"))
print(f"Validation result: {result}")

# Let's also test each part of the validation
csp_report = report_data["csp-report"]
print(f"CSP report: {csp_report}")

# Check required fields
REQUIRED_FIELDS = {"document-uri", "violated-directive", "original-policy"}

has_required = True
for field in REQUIRED_FIELDS:
    if field not in csp_report:
        print(f"Missing required field: {field}")
        has_required = False
    else:
        print(f"Found required field: {field} = {csp_report[field]}")

print(f"Has all required fields: {has_required}")

# Test URI validation
uri_fields = ["document-uri", "blocked-uri", "referrer", "source-file"]
for field in uri_fields:
    if field in csp_report:
        # Pass the correct flag for blocked-uri
        is_blocked_uri = field == "blocked-uri"
        result = _is_safe_uri(str(csp_report[field]), is_blocked_uri)
        print(f"URI validation for {field} ({csp_report[field]}): {result}")

# Test directive validation
directive_fields = ["violated-directive", "effective-directive", "original-policy"]
for field in directive_fields:
    if field in csp_report:
        result = _is_safe_directive_value(str(csp_report[field]))
        print(f"Directive validation for {field} ({csp_report[field]}): {result}")

# Test numeric fields
numeric_fields = ["status-code", "line-number", "column-number"]
for field in numeric_fields:
    if field in csp_report:
        is_numeric = isinstance(csp_report[field], (int, float))
        print(f"Numeric validation for {field} ({csp_report[field]}): {is_numeric}")

# Test disposition
if "disposition" in csp_report:
    is_valid = csp_report["disposition"] in ["enforce", "report"]
    print(
        f"Disposition validation for disposition ({csp_report['disposition']}): {is_valid}"
    )
