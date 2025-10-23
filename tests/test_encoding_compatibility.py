import io
import logging
import sys
from unittest.mock import patch
import pytest
from resync.core.encoding_utils import can_encode, symbol
from resync.core.structured_logger import SafeEncodingFormatter


@pytest.mark.parametrize("encoding,expected_ok,expected_err", [
    ("utf-8", "✅", "❌"),
    ("cp1252", "[OK]", "[ERR]"),
    (None, "✅", "❌"),  # None defaults to utf-8 fallback
])
def test_symbol_fallback(encoding, expected_ok, expected_err):
    # Simulate stream with encoding
    stream = io.TextIOWrapper(io.BytesIO(), encoding=encoding) if encoding else None

    assert symbol(True, stream=stream, encoding=encoding) == expected_ok
    assert symbol(False, stream=stream, encoding=encoding) == expected_err


def test_can_encode():
    assert can_encode("hello", encoding="utf-8")
    assert not can_encode("✅", encoding="cp1252")


def test_safe_formatter(caplog):
    formatter = SafeEncodingFormatter()

    # Mock record with emoji
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="Status: ✅", args=(), exc_info=None
    )

    # Simulate cp1252 encoding
    with patch('sys.stdout') as mock_stdout:
        mock_stdout.encoding = 'cp1252'
        formatted = formatter.format(record)
        assert "[OK]" in formatted  # Fallback applied
        assert "✅" not in formatted


def test_safe_formatter_utf8(caplog):
    formatter = SafeEncodingFormatter()

    # Mock record with emoji
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="Status: ✅", args=(), exc_info=None
    )

    # Simulate UTF-8 encoding
    with patch('sys.stdout') as mock_stdout:
        mock_stdout.encoding = 'utf-8'
        formatted = formatter.format(record)
        assert "✅" in formatted  # Emoji preserved
        assert "[OK]" not in formatted


def test_safe_formatter_unknown_encoding():
    formatter = SafeEncodingFormatter()

    # Mock record with emoji
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="Status: ✅", args=(), exc_info=None
    )

    # Simulate unknown encoding
    with patch('sys.stdout') as mock_stdout:
        mock_stdout.encoding = 'unknown-encoding'
        formatted = formatter.format(record)
        # Should fall back to ASCII or error handling
        assert "[ENCODING ERROR]" in formatted or "[OK]" in formatted


def test_no_unicode_encode_error():
    """Ensure no UnicodeEncodeError is raised in any scenario."""
    # Test various encoding scenarios
    test_cases = [
        ("utf-8", "✅ Test message"),
        ("cp1252", "❌ Error occurred"),
        (None, "🚀 Starting service"),
    ]

    for encoding, message in test_cases:
        with patch('sys.stdout') as mock_stdout:
            mock_stdout.encoding = encoding

            # Should not raise UnicodeEncodeError
            result = symbol(True, encoding=encoding)
            assert isinstance(result, str)

            # Safe formatter should also work
            formatter = SafeEncodingFormatter()
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg=message, args=(), exc_info=None
            )

            formatted = formatter.format(record)
            assert isinstance(formatted, str)
            # Ensure no UnicodeEncodeError was raised during formatting
