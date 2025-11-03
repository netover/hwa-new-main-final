#!/usr/bin/env python3
"""
Test script for Redis Streams audit migration.
This script tests the new Redis Streams implementation with SQLite fallback.
"""

import os
import sys
from pathlib import Path

# Set environment variable before importing modules
os.environ["USE_REDIS_AUDIT_STREAMS"] = os.environ.get("USE_REDIS_AUDIT_STREAMS", "false")

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from resync.core.audit_db import (
    USE_REDIS_STREAMS,
    add_audit_record,
    get_pending_audits,
    is_memory_approved,
    update_audit_status,
)


def test_audit_operations():
    """Test basic audit operations with both Redis and SQLite backends."""

    print(f"Testing audit operations with Redis Streams enabled: {USE_REDIS_STREAMS}")

    # Test data
    test_memory = {
        "id": "test_memory_123",
        "user_query": "What is the capital of France?",
        "agent_response": "The capital of France is Paris.",
        "ia_audit_reason": "Response contains factual information",
        "ia_audit_confidence": 0.95
    }

    print("\n1. Testing add_audit_record...")
    record_id = add_audit_record(test_memory)
    print(f"   Record added with ID: {record_id}")

    print("\n2. Testing get_pending_audits...")
    pending_audits = get_pending_audits()
    print(f"   Found {len(pending_audits)} pending audits")

    # Find our test record
    test_record = None
    for audit in pending_audits:
        if audit.get("memory_id") == test_memory["id"]:
            test_record = audit
            break

    if test_record:
        print("   Test record found in pending audits [OK]")
        print(f"   Status: {test_record.get('status')}")
        print(f"   User query: {test_record.get('user_query')}")
    else:
        print("   Test record NOT found in pending audits [ERROR]")

    print("\n3. Testing update_audit_status...")
    success = update_audit_status(test_memory["id"], "approved")
    print(f"   Status update successful: {success}")

    print("\n4. Testing is_memory_approved...")
    approved = is_memory_approved(test_memory["id"])
    print(f"   Memory approved: {approved}")

    if approved:
        print("   [SUCCESS] Redis Streams audit migration working correctly!")
    else:
        print("   [ERROR] Redis Streams audit migration has issues")

    print("\n5. Final status check:")
    final_audits = get_pending_audits()
    print(f"   Remaining pending audits: {len(final_audits)}")


if __name__ == "__main__":
    print("Redis Audit Migration Test")
    print("=" * 40)

    # Test with SQLite (default)
    print("\nTesting with SQLite backend...")
    test_audit_operations()

    # Test with Redis Streams if enabled
    if USE_REDIS_STREAMS:
        print("\n" + "=" * 40)
        print("Testing with Redis Streams backend...")
        test_audit_operations()
    else:
        print("\nTo test Redis Streams, set USE_REDIS_AUDIT_STREAMS=true in environment variables")

    print("\n" + "=" * 40)
    print("Test completed!")




