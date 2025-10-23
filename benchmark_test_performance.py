#!/usr/bin/env python3
"""
Benchmark script to measure test performance improvements.
This script runs the tests multiple times and measures execution time and memory usage.
"""

import asyncio
import gc
import os
import psutil
import statistics
import sys
import time
from typing import List, Tuple

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def get_memory_usage() -> float:
    """Get current memory usage in MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024


def run_single_test() -> Tuple[float, float]:
    """Run a single test iteration and return (execution_time, peak_memory)."""
    # Import here to avoid loading at module level
    import subprocess
    import sys

    gc.collect()  # Clean up before test
    start_memory = get_memory_usage()
    start_time = time.time()

    # Run the test as a subprocess to avoid event loop issues
    result = subprocess.run(
        [sys.executable, "test_env.py"], capture_output=True, text=True, cwd=os.getcwd()
    )

    end_time = time.time()
    end_memory = get_memory_usage()

    execution_time = end_time - start_time
    memory_used = end_memory - start_memory

    if result.returncode != 0:
        print(f"Warning: Test failed with exit code {result.returncode}")

    return execution_time, memory_used


async def run_benchmark(iterations: int = 5) -> None:
    """Run benchmark with multiple iterations."""
    print(f"Running benchmark with {iterations} iterations...")
    print("=" * 60)

    times = []
    memories = []

    for i in range(iterations):
        print(f"Iteration {i + 1}/{iterations}")

        exec_time, mem_used = run_single_test()
        times.append(exec_time)
        memories.append(mem_used)

        print(f"  Execution time: {exec_time:.3f}s")
        print(f"  Memory used: {mem_used:.1f}MB")
        print()

        # Small delay between iterations
        await asyncio.sleep(0.1)

    # Calculate statistics
    avg_time = statistics.mean(times)
    min_time = min(times)
    max_time = max(times)
    std_time = statistics.stdev(times) if len(times) > 1 else 0

    avg_memory = statistics.mean(memories)
    min_memory = min(memories)
    max_memory = max(memories)
    std_memory = statistics.stdev(memories) if len(memories) > 1 else 0

    print("=" * 60)
    print("BENCHMARK RESULTS:")
    print("=" * 60)
    print(f"Execution Time (seconds):")
    print(f"  Average: {avg_time:.3f}s")
    print(f"  Min:     {min_time:.3f}s")
    print(f"  Max:     {max_time:.3f}s")
    print(f"  StdDev:  {std_time:.3f}s")
    print()
    print(f"Memory Usage (MB):")
    print(f"  Average: {avg_memory:.1f}MB")
    print(f"  Min:     {min_memory:.1f}MB")
    print(f"  Max:     {max_memory:.1f}MB")
    print(f"  StdDev:  {std_memory:.1f}MB")
    print()

    # Memory efficiency check
    if max_memory < 100:  # Less than 100MB peak
        print("EXCELLENT: Excellent memory efficiency!")
    elif max_memory < 200:  # Less than 200MB peak
        print("GOOD: Good memory efficiency")
    else:
        print("WARNING: High memory usage detected")

    if avg_time < 2.0:  # Less than 2 seconds average
        print("EXCELLENT: Excellent execution speed!")
    elif avg_time < 5.0:  # Less than 5 seconds average
        print("GOOD: Good execution speed")
    else:
        print("WARNING: Slow execution detected")


async def main() -> None:
    """Main benchmark function."""
    # Set environment for testing
    os.environ["ADMIN_USERNAME"] = "test_admin"
    os.environ["ADMIN_PASSWORD"] = "test_password"
    os.environ["ENVIRONMENT"] = "test"
    os.environ["PYTHONASYNCIODEBUG"] = "0"

    iterations = 5

    if len(sys.argv) > 1:
        try:
            iterations = int(sys.argv[1])
        except ValueError:
            print("Invalid number of iterations. Using default (5).")

    await run_benchmark(iterations)


if __name__ == "__main__":
    asyncio.run(main())
