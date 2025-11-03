"""Contract tests to ensure Resync uses only valid TWS API routes.

These tests load the official TWS API specification from the
knowledge_base directory and validate that the HTTP method/path pairs
used by the application are defined.  If a route is missing from the
specification, these tests will fail, signalling that the client and
specification are out of sync.

Running these tests will not perform any network calls; they purely
validate static definitions.  If the specification file is not
available, the test will be skipped.
"""

import os
import pytest

try:
    from resync.services.tws_routes import load_tws_api_spec, validate_routes
    from resync.services.tws_service import OptimizedTWSClient  # noqa: F401 - used for reference
except ImportError:
    pytest.skip("resync services modules not available", allow_module_level=True)


def test_tws_routes_exist():
    """Validate that all used TWS API routes exist in the specification."""
    # Load API spec
    spec = load_tws_api_spec()
    if not spec or "paths" not in spec:
        pytest.skip("TWS API specification not found; skipping contract test")
    # Define the method/path pairs used by the OptimizedTWSClient.  Query
    # parameters are omitted because the spec defines paths without
    # parameters; validation focuses on the base path and HTTP method.
    routes_to_check = [
        ("GET", "/model/workstation"),
        ("GET", "/model/jobdefinition"),
        ("GET", "/model/jobdefinition/{job_id}"),
        ("GET", "/model/jobdefinition/{job_id}/dependencies"),
        ("GET", "/plan/current"),
        ("GET", "/plan/current/criticalpath"),
        ("GET", "/model/resource"),
    ]
    # Validate routes; will raise ValueError if missing
    validate_routes(routes_to_check, spec=spec)