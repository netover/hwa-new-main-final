import pytest

def test_smoke_import_main_modules():
    """
    Test that the main application modules can be imported without errors.
    """
    try:
        from resync import app_factory
        from resync import main
        from resync.api import routes
        from resync.core import security
        from resync.api import agents
    except ImportError as e:
        pytest.fail(f"Failed to import a main module: {e}")
