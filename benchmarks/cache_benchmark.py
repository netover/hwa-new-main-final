from __future__ import annotations

import asyncio
import secrets
import statistics
import time
from typing import Any

from resync.core._deprecated.async_cache_refactored import AsyncTTLCache
# TWS_OptimizedAsyncCache não existe - usar AsyncTTLCache como alternativa
from resync.core._deprecated.async_cache_refactored import AsyncTTLCache as TWS_OptimizedAsyncCache


class CacheBenchmark:
    """
    Benchmark tool for comparing cache implementations.

    This class provides methods to run various performance tests on cache
    implementations and compare their results.
    """

    def __init__(self) -> None:
        """Initialize the benchmark tool."""
        self.results: dict[str, dict[str, Any]] = {}

    async def setup_caches(self, num_shards: int = 16) -> tuple[Any, Any]:
        """
        Set up cache instances for benchmarking.

        Args:
            num_shards: Number of shards to use for both caches

        Returns:
            Tuple of (original_cache, enhanced_cache)
        """
        original_cache = AsyncTTLCache(
            ttl_seconds=60, cleanup_interval=30, num_shards=num_shards
        )

        enhanced_cache = TWS_OptimizedAsyncCache(
            ttl_seconds=60, cleanup_interval=30, num_shards=num_shards
        )

        return original_cache, enhanced_cache

    async def run_single_operation_benchmark(
        self,
        cache_name: str,
        cache: Any,
        operation: str,
        num_operations: int = 10000,
    ) -> dict[str, Any]:
        """
        Run benchmark for a single operation type.

        Args:
            cache_name: Name of the cache implementation
            cache: Cache instance
            operation: Operation type ('get', 'set', 'mixed')
            num_operations: Number of operations to perform

        Returns:
            Dictionary with benchmark results
        """
        keys = [f"benchmark_key_{i}" for i in range(num_operations)]
        values = [f"benchmark_value_{i}" for i in range(num_operations)]

        # Pre-populate cache for get operations
        if operation in ("get", "mixed"):
            for i in range(num_operations):
                await cache.set(keys[i], values[i])

        # Measure operation time
        start_time = time.time()

        if operation == "get":
            for i in range(num_operations):
                await cache.get(keys[i])
        elif operation == "set":
            for i in range(num_operations):
                await cache.set(keys[i], values[i])
        elif operation == "mixed":
            for i in range(num_operations):
                if secrets.randbelow(10) < 7:  # 70% reads, 30% writes
                    await cache.get(keys[i])
                else:
                    await cache.set(keys[i], values[i])

        end_time = time.time()
        duration = end_time - start_time
        ops_per_second = num_operations / duration

        return {
            "duration_seconds": duration,
            "operations_per_second": ops_per_second,
            "operation": operation,
            "cache": cache_name,
        }

    async def run_concurrent_benchmark(
        self,
        cache_name: str,
        cache: Any,
        num_workers: int = 10,
        operations_per_worker: int = 1000,
        read_ratio: float = 0.7,
    ) -> dict[str, Any]:
        """
        Run benchmark with concurrent workers.

        Args:
            cache_name: Name of the cache implementation
            cache: Cache instance
            num_workers: Number of concurrent workers
            operations_per_worker: Operations per worker
            read_ratio: Ratio of read operations (0.0-1.0)

        Returns:
            Dictionary with benchmark results
        """
        # Pre-populate cache with some data
        for i in range(operations_per_worker):
            await cache.set(f"concurrent_key_{i}", f"concurrent_value_{i}")

        # Define worker function
        async def worker(worker_id: int) -> list[float]:
            latencies = []
            for i in range(operations_per_worker):
                key = f"concurrent_key_{secrets.randbelow(operations_per_worker)}"

                start_time = time.time()
                if secrets.randbelow(10) < 7:
                    # Read operation
                    await cache.get(key)
                else:
                    # Write operation
                    await cache.set(key, f"new_value_{worker_id}_{i}")
                latency = (time.time() - start_time) * 1000  # ms
                latencies.append(latency)

            return latencies

        # Run workers concurrently
        start_time = time.time()
        all_latencies = await asyncio.gather(*[worker(i) for i in range(num_workers)])
        end_time = time.time()

        # Flatten latencies list
        latencies = [
            lat for worker_latencies in all_latencies for lat in worker_latencies
        ]

        # Calculate statistics
        total_operations = num_workers * operations_per_worker
        duration = end_time - start_time
        ops_per_second = total_operations / duration

        return {
            "duration_seconds": duration,
            "operations_per_second": ops_per_second,
            "avg_latency_ms": statistics.mean(latencies),
            "p95_latency_ms": statistics.quantiles(latencies, n=20)[
                18
            ],  # 95th percentile
            "p99_latency_ms": statistics.quantiles(latencies, n=100)[
                98
            ],  # 99th percentile
            "max_latency_ms": max(latencies),
            "min_latency_ms": min(latencies),
            "cache": cache_name,
            "concurrent_workers": num_workers,
        }

    async def run_cleanup_benchmark(
        self,
        cache_name: str,
        cache: Any,
        num_entries: int = 100000,
        expired_ratio: float = 0.5,
    ) -> dict[str, Any]:
        """
        Benchmark cache cleanup performance.

        Args:
            cache_name: Name of the cache implementation
            cache: Cache instance
            num_entries: Number of entries to add
            expired_ratio: Ratio of entries that should be expired

        Returns:
            Dictionary with benchmark results
        """
        # Add entries with mixed TTLs
        for i in range(num_entries):
            if secrets.randbelow(10) < 5:
                # Expired entry (TTL of 0 seconds)
                await cache.set(f"expired_key_{i}", f"expired_value_{i}", ttl_seconds=0)
            else:
                # Non-expired entry
                await cache.set(f"valid_key_{i}", f"valid_value_{i}", ttl_seconds=60)

        # Force cleanup and measure time
        start_time = time.time()

        if hasattr(cache, "_remove_expired_entries_parallel"):
            await cache._remove_expired_entries_parallel()
        else:
            await cache._remove_expired_entries()

        end_time = time.time()
        duration = end_time - start_time

        return {
            "duration_seconds": duration,
            "entries_per_second": num_entries * expired_ratio / duration,
            "total_entries": num_entries,
            "expired_entries": int(num_entries * expired_ratio),
            "cache": cache_name,
        }

    async def run_all_benchmarks(self) -> dict[str, dict[str, Any]]:
        """
        Run all benchmarks and return results.

        Returns:
            Dictionary with all benchmark results
        """
        original_cache, enhanced_cache = await self.setup_caches()

        try:
            # Single operation benchmarks
            for operation in ["get", "set", "mixed"]:
                self.results[f"original_{operation}"] = (
                    await self.run_single_operation_benchmark(
                        "AsyncTTLCache", original_cache, operation
                    )
                )
                self.results[f"tws_optimized_{operation}"] = (
                    await self.run_single_operation_benchmark(
                        "TWS_OptimizedAsyncCache", enhanced_cache, operation
                    )
                )

            # Concurrent benchmarks
            for workers in [10, 50, 100]:
                self.results[f"original_concurrent_{workers}"] = (
                    await self.run_concurrent_benchmark(
                        "AsyncTTLCache", original_cache, num_workers=workers
                    )
                )
                self.results[f"tws_optimized_concurrent_{workers}"] = (
                    await self.run_concurrent_benchmark(
                        "TWS_OptimizedAsyncCache", enhanced_cache, num_workers=workers
                    )
                )

            # Cleanup benchmarks
            self.results["original_cleanup"] = await self.run_cleanup_benchmark(
                "AsyncTTLCache", original_cache
            )
            self.results["tws_optimized_cleanup"] = await self.run_cleanup_benchmark(
                "TWS_OptimizedAsyncCache", enhanced_cache
            )

        finally:
            # Clean up
            await original_cache.stop()
            await enhanced_cache.stop()

        return self.results

    def print_results(self) -> None:
        """Print benchmark results in a formatted table."""
        if not self.results:
            print("No benchmark results available.")
            return

        print("\n=== Cache Benchmark Results ===\n")

        # Single operation results
        print("Single Operation Performance (ops/sec):")
        print("-" * 60)
        print(
            f"{'Operation':<10} | {'AsyncTTLCache':<20} | {'TWS_OptimizedAsyncCache':<20} | {'Improvement':<10}"
        )
        print("-" * 60)

        for op in ["get", "set", "mixed"]:
            orig = self.results.get(f"original_{op}", {}).get(
                "operations_per_second", 0
            )
            enhanced = self.results.get(f"tws_optimized_{op}", {}).get(
                "operations_per_second", 0
            )
            improvement = ((enhanced / orig) - 1) * 100 if orig > 0 else 0

            print(
                f"{op:<10} | {orig:<20.2f} | {enhanced:<20.2f} | {improvement:>9.2f}%"
            )

        # Concurrent benchmark results
        print("\nConcurrent Performance (ops/sec):")
        print("-" * 70)
        print(
            f"{'Workers':<10} | {'AsyncTTLCache':<20} | {'TWS_OptimizedAsyncCache':<20} | {'Improvement':<10}"
        )
        print("-" * 70)

        for workers in [10, 50, 100]:
            orig = self.results.get(f"original_concurrent_{workers}", {}).get(
                "operations_per_second", 0
            )
            enhanced = self.results.get(f"tws_optimized_concurrent_{workers}", {}).get(
                "operations_per_second", 0
            )
            improvement = ((enhanced / orig) - 1) * 100 if orig > 0 else 0

            print(
                f"{workers:<10} | {orig:<20.2f} | {enhanced:<20.2f} | {improvement:>9.2f}%"
            )

        # Latency results for concurrent tests
        print("\nLatency Results (ms) for 100 Workers:")
        print("-" * 70)
        print(
            f"{'Metric':<10} | {'AsyncTTLCache':<20} | {'TWS_OptimizedAsyncCache':<20} | {'Improvement':<10}"
        )
        print("-" * 70)

        orig_results = self.results.get("original_concurrent_100", {})
        enhanced_results = self.results.get("tws_optimized_concurrent_100", {})

        for metric in [
            "avg_latency_ms",
            "p95_latency_ms",
            "p99_latency_ms",
            "max_latency_ms",
        ]:
            orig = orig_results.get(metric, 0)
            enhanced = enhanced_results.get(metric, 0)
            improvement = (
                ((orig / enhanced) - 1) * 100 if enhanced > 0 else 0
            )  # Lower is better for latency

            metric_name = metric.replace("_latency_ms", "")
            print(
                f"{metric_name:<10} | {orig:<20.2f} | {enhanced:<20.2f} | {improvement:>9.2f}%"
            )

        # Cleanup benchmark
        print("\nCleanup Performance:")
        print("-" * 70)
        print(
            f"{'Metric':<15} | {'AsyncTTLCache':<20} | {'TWS_OptimizedAsyncCache':<20} | {'Improvement':<10}"
        )
        print("-" * 70)

        orig_cleanup = self.results.get("original_cleanup", {})
        enhanced_cleanup = self.results.get("tws_optimized_cleanup", {})

        orig_duration = orig_cleanup.get("duration_seconds", 0)
        enhanced_duration = enhanced_cleanup.get("duration_seconds", 0)
        duration_improvement = (
            ((orig_duration / enhanced_duration) - 1) * 100
            if enhanced_duration > 0
            else 0
        )

        orig_throughput = orig_cleanup.get("entries_per_second", 0)
        enhanced_throughput = enhanced_cleanup.get("entries_per_second", 0)
        throughput_improvement = (
            ((enhanced_throughput / orig_throughput) - 1) * 100
            if orig_throughput > 0
            else 0
        )

        print(
            f"{'Duration (s)':<15} | {orig_duration:<20.3f} | {enhanced_duration:<20.3f} | {duration_improvement:>9.2f}%"
        )
        print(
            f"{'Entries/sec':<15} | {orig_throughput:<20.2f} | {enhanced_throughput:<20.2f} | {throughput_improvement:>9.2f}%"
        )


async def main() -> None:
    """Run the benchmark suite."""
    print("Starting cache benchmark...")
    benchmark = CacheBenchmark()
    await benchmark.run_all_benchmarks()
    benchmark.print_results()


if __name__ == "__main__":
    asyncio.run(main())




