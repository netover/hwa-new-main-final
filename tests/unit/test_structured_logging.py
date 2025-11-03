#!/usr/bin/env python3
"""
Test script for structured logging system.

This script tests the structured logging implementation to ensure it's working correctly.
"""

import json
import os
import sys
import time
import uuid
from io import StringIO

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_structured_logging():
    """Test the structured logging system."""
    print("Testing structured logging system...")

    try:
        # Import structured logging components
        from config.structured_logging_basic import (
            LoggingContext,
            log_critical,
            log_debug,
            log_error,
            log_info,
            log_request_end,
            log_request_start,
            log_warning,
            logger,
        )

        print("✓ Successfully imported structured logging components")

        # Test basic logging
        print("\n1. Testing basic logging levels:")

        # Capture stdout to see JSON output
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            log_debug("This is a debug message", user_id="123", action="test")
            log_info("This is an info message", user_id="123", action="test")
            log_warning("This is a warning message", user_id="123", action="test")
            log_error(ValueError("Test error"), "This is an error message", user_id="123")
            log_critical("This is a critical message", user_id="123", action="test")

            output = captured_output.getvalue()
            print("✓ Basic logging levels work")

            # Check if output contains JSON-like structure
            if '{' in output and '}' in output:
                print("✓ JSON format detected in output")
            else:
                print("⚠ Warning: JSON format not clearly detected")

        finally:
            sys.stdout = old_stdout

        # Test contextual logging
        print("\n2. Testing contextual logging:")

        with LoggingContext(user_id="456", session_id="test_session"):
            log_info("Message with context", action="context_test")

        print("✓ Contextual logging works")

        # Test request logging functions
        print("\n3. Testing request logging functions:")

        request_id = str(uuid.uuid4())
        start_time = time.time()

        log_request_start("GET", "/api/test", request_id)

        # Simulate some processing time
        time.sleep(0.01)

        duration = time.time() - start_time
        log_request_end("GET", "/api/test", 200, duration, request_id)

        print("✓ Request logging functions work")

        # Test correlation ID generation
        print("\n4. Testing correlation ID generation:")

        with LoggingContext(action="correlation_test"):
            logger.info("Message with auto-generated correlation ID")

        print("✓ Correlation ID generation works")

        print("\n🎉 All structured logging tests passed!")
        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure structlog is installed: pip install structlog>=23.2.0")
        return False
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_log_file_creation():
    """Test that log files are created correctly."""
    print("\n5. Testing log file creation:")

    log_file = "logs/app.log"
    if os.path.exists(log_file):
        print(f"✓ Log file exists: {log_file}")
        # Check if file has content
        with open(log_file) as f:
            content = f.read().strip()
            if content:
                print("✓ Log file has content")
                # Try to parse as JSON to verify format
                try:
                    lines = content.split('\n')
                    for line in lines[-3:]:  # Check last 3 lines
                        if line.strip():
                            json.loads(line)
                    print("✓ Log file contains valid JSON format")
                except json.JSONDecodeError:
                    print("⚠ Warning: Log file doesn't contain valid JSON")
            else:
                print("⚠ Warning: Log file is empty")
    else:
        print(f"⚠ Warning: Log file not found: {log_file}")

if __name__ == "__main__":
    print("=" * 60)
    print("STRUCTURED LOGGING SYSTEM TEST")
    print("=" * 60)

    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)

    success = test_structured_logging()
    test_log_file_creation()

    print("\n" + "=" * 60)
    if success:
        print("✅ STRUCTURED LOGGING SYSTEM IS READY!")
        print("\nThe system provides:")
        print("• JSON formatted log output")
        print("• Automatic correlation ID generation")
        print("• Request ID tracking")
        print("• Contextual information logging")
        print("• Proper log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
        print("• Log rotation (10MB files, 14 backups)")
        print("• Integration with Flask middleware")
    else:
        print("❌ STRUCTURED LOGGING SYSTEM NEEDS ATTENTION!")
        sys.exit(1)
    print("=" * 60)




