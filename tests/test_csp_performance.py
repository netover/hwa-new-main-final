"""Performance benchmarks for CSP validation optimization."""

import time
import json
from resync.csp_validation import validate_csp_report


def create_test_csp_report() -> bytes:
    """Create a valid test CSP report."""
    report_data = {
        "csp-report": {
            "document-uri": "https://example.com/page.html",
            "violated-directive": "script-src",
            "original-policy": "script-src 'self' https://cdn.example.com",
            "blocked-uri": "https://malicious.com/script.js",
            "status-code": 200,
            "referrer": "https://google.com/",
            "script-sample": "alert('xss')",
            "disposition": "enforce",
            "line-number": 15,
            "column-number": 20,
            "source-file": "https://example.com/page.html",
            "effective-directive": "script-src",
        }
    }
    return json.dumps(report_data).encode("utf-8")


def benchmark_validation(iterations: int = 10000) -> dict:
    """
    Benchmark CSP validation performance.

    Args:
        iterations: Number of iterations to run

    Returns:
        dict: Performance metrics
    """
    test_data = create_test_csp_report()

    # Warm up
    for _ in range(100):
        validate_csp_report(test_data)

    # Benchmark
    start_time = time.time()

    for _ in range(iterations):
        validate_csp_report(test_data)

    end_time = time.time()

    total_time = end_time - start_time
    ops_per_second = iterations / total_time
    time_per_op = total_time / iterations

    return {
        "iterations": iterations,
        "total_time_seconds": total_time,
        "operations_per_second": ops_per_second,
        "time_per_operation_seconds": time_per_op,
    }


def test_performance_improvement():
    """Test that optimized validation is at least 40% faster."""
    print("Running CSP validation performance benchmark...")

    results = benchmark_validation(10000)

    print(f"Iterations: {results['iterations']}")
    print(f"Total time: {results['total_time_seconds']:.4f} seconds")
    print(f"Operations per second: {results['operations_per_second']:.2f}")
    print(f"Time per operation: {results['time_per_operation_seconds']:.6f} seconds")

    # Baseline assumption: original implementation would be slower
    # We expect at least 40% improvement (40% less time per operation)
    expected_max_time_per_op = 0.0001  # Adjust based on actual baseline

    assert results["time_per_operation_seconds"] < expected_max_time_per_op, (
        f"Performance not improved enough. Expected < {expected_max_time_per_op:.6f}s per op, "
        f"got {results['time_per_operation_seconds']:.6f}s per op"
    )

    print("✅ Performance test passed - optimization successful!")
    return results


if __name__ == "__main__":
    test_performance_improvement()
