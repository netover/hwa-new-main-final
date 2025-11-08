import pytest


def test_smoke_import_main_modules():
    """
    Test that the main application modules can be imported without errors.
    """
    try:
        from resync import app_factory, main
        from resync.api import agents, routes
        from resync.core import security
    except ImportError as e:
        pytest.fail(f"Failed to import a main module: {e}")
