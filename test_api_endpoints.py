"""
API Endpoint Test for Phase 2 Performance Optimization.

This script tests the performance monitoring API endpoints.
"""

import requests
import json

BASE_URL = "http://localhost:8000"


def test_endpoint(endpoint: str, description: str) -> bool:
    """Test a single API endpoint."""
    url = f"{BASE_URL}{endpoint}"
    print(f"\nTesting: {description}")
    print(f"URL: {url}")

    try:
        response = requests.get(url, timeout=5)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)[:200]}...")
            print("[OK] Endpoint working")
            return True
        else:
            print(f"[FAIL] Unexpected status code: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
    except requests.exceptions.ConnectionError:
        print(
            "[SKIP] Server not running (this is expected if you haven't started the app)"
        )
        return None
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def main():
    """Test all performance API endpoints."""
    print("=" * 60)
    print("PHASE 2 PERFORMANCE API - ENDPOINT TESTS")
    print("=" * 60)
    print("\nNote: These tests require the application to be running.")
    print("Start the app with: uvicorn resync.main:app --reload")
    print("=" * 60)

    endpoints = [
        ("/api/performance/health", "Performance Health Status"),
        ("/api/performance/report", "Full Performance Report"),
        ("/api/performance/cache/metrics", "Cache Metrics"),
        ("/api/performance/cache/recommendations", "Cache Recommendations"),
        ("/api/performance/pools/metrics", "Connection Pool Metrics"),
        ("/api/performance/pools/recommendations", "Pool Recommendations"),
        ("/api/performance/resources/stats", "Resource Statistics"),
        ("/api/performance/resources/leaks", "Resource Leak Detection"),
    ]

    results = []
    for endpoint, description in endpoints:
        result = test_endpoint(endpoint, description)
        results.append((description, result))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result is True)
    skipped = sum(1 for _, result in results if result is None)
    failed = sum(1 for _, result in results if result is False)
    total = len(results)

    for description, result in results:
        if result is True:
            status = "[PASS]"
        elif result is None:
            status = "[SKIP]"
        else:
            status = "[FAIL]"
        print(f"{status} {description}")

    print(
        f"\nTotal: {passed} passed, {skipped} skipped, {failed} failed out of {total}"
    )

    if skipped == total:
        print("\n[INFO] All tests skipped - server not running.")
        print("To test the API endpoints:")
        print("1. Start the server: uvicorn resync.main:app --reload")
        print("2. Run this script again: python test_api_endpoints.py")
        return 0
    elif failed == 0:
        print("\n[SUCCESS] All API endpoints working correctly!")
        return 0
    else:
        print(f"\n[WARNING] {failed} endpoint(s) failed.")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
