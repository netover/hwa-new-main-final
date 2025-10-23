"""
Tests for InputSanitizer class and related functionality.
"""

from pathlib import Path

import pytest

from resync.core import env_detector
from resync.core.security import InputSanitizer


@pytest.fixture
def set_test_env(monkeypatch):
    """Fixture to set the environment to 'testing' for the duration of a test."""
    monkeypatch.setenv("APP_ENV", "testing")
    # We need to re-initialize the detector since it's created on module import
    env_detector.__init__()


@pytest.mark.usefixtures("set_test_env")
class TestInputSanitizer:
    """Test cases for InputSanitizer functionality."""

    def test_sanitize_path_valid(self):
        """Test path sanitization with valid paths."""
        # Test with string path, now allowed in test mode
        result = InputSanitizer.sanitize_path("/tmp/test.txt")
        assert isinstance(result, Path)
        assert str(result).endswith("test.txt")

        # Test with relative path
        path_obj = Path("test.txt")
        result = InputSanitizer.sanitize_path(path_obj)
        assert isinstance(result, Path)

    def test_sanitize_path_invalid(self):
        """Test path sanitization with invalid paths."""
        # Test with path traversal attempt which resolves to an absolute path
        with pytest.raises(
            ValueError,
            match="Absolute paths outside allowed directories are not permitted",
        ):
            InputSanitizer.sanitize_path("../../etc/passwd")

        # Test with null bytes - this raises a ValueError from the OS/pathlib level first
        with pytest.raises(ValueError, match="embedded null character in path"):
            InputSanitizer.sanitize_path("test\x00file.txt")

        # Test with empty path - Pydantic's min_length validation is hit first.
        with pytest.raises(ValueError, match="String should have at least 1 character"):
            InputSanitizer.sanitize_path("")

    def test_sanitize_host_port_valid(self):
        """Test host:port sanitization with valid inputs."""
        host, port = InputSanitizer.sanitize_host_port("192.168.1.1:8080")
        assert host == "192.168.1.1"
        assert port == 8080

        host, port = InputSanitizer.sanitize_host_port("localhost:3000")
        assert host == "localhost"
        assert port == 3000

    def test_sanitize_host_port_invalid(self):
        """Test host:port sanitization with invalid inputs."""
        with pytest.raises(ValueError, match="Host:port format required"):
            InputSanitizer.sanitize_host_port("localhost")

        with pytest.raises(ValueError, match="Invalid hostname format"):
            InputSanitizer.sanitize_host_port("invalid..host:8080")

        with pytest.raises(ValueError):
            InputSanitizer.sanitize_host_port("localhost:70000")

    def test_sanitize_environment_value(self):
        """Test environment variable sanitization."""
        result = InputSanitizer.sanitize_environment_value("TEST_VAR", "hello", str)
        assert result == "hello"

        result = InputSanitizer.sanitize_environment_value("TEST_BOOL", "true", bool)
        assert result is True

        result = InputSanitizer.sanitize_environment_value("TEST_BOOL", "0", bool)
        assert result is False

        result = InputSanitizer.sanitize_environment_value("TEST_INT", "42", int)
        assert result == 42

        result = InputSanitizer.sanitize_environment_value("TEST_FLOAT", "3.14", float)
        assert result == 3.14

    def test_validate_path_exists(self):
        """Test path existence validation."""
        import tempfile

        with tempfile.NamedTemporaryFile() as tmp:
            tmp_path = Path(tmp.name)
            result = InputSanitizer.validate_path_exists(tmp_path, must_exist=True)
            assert result == tmp_path.resolve()

            nonexistent = Path("definitely_does_not_exist_12345.txt")
            with pytest.raises(FileNotFoundError):
                InputSanitizer.validate_path_exists(nonexistent, must_exist=True)

            result = InputSanitizer.validate_path_exists(nonexistent, must_exist=False)
            assert result == nonexistent.resolve()
