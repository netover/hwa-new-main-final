from __future__ import annotations

import asyncio
import secrets
import time
from typing import Any

from resync.core.enhanced_async_cache import EnhancedAsyncTTLCache  # type: ignore[attr-defined]


async def simulate_high_concurrency(
    cache: Any,
    num_tasks: int = 100,
    operations_per_task: int = 1000,
    read_ratio: float = 0.8,
) -> None:
    """
    Simulate high concurrency access to the cache.

    Args:
        cache: The cache instance
        num_tasks: Number of concurrent tasks
        operations_per_task: Operations per task
        read_ratio: Ratio of read operations (0.0-1.0)
    """
    # Pre-populate cache with some data
    keys = [f"key_{i}" for i in range(1000)]
    for key in keys:
        await cache.set(key, f"value_for_{key}")

    print(f"Cache pre-populated with {len(keys)} keys")

    # Define task function
    async def worker_task(task_id: int) -> None:
        for i in range(operations_per_task):
            # Select random key
            key = secrets.choice(keys)

            # Perform operation based on read ratio
            if secrets.random() < read_ratio:
                # Read operation
                await cache.get(key)
            else:
                # Write operation
                await cache.set(key, f"new_value_from_task_{task_id}_{i}")

            # Small delay to simulate real-world processing
            await asyncio.sleep(0.001)

    # Create and run tasks
    print(f"Starting {num_tasks} concurrent tasks...")
    start_time = time.time()

    tasks = [worker_task(i) for i in range(num_tasks)]
    await asyncio.gather(*tasks)

    duration = time.time() - start_time
    total_operations = num_tasks * operations_per_task
    ops_per_second = total_operations / duration

    print(f"Completed {total_operations} operations in {duration:.2f} seconds")
    print(f"Performance: {ops_per_second:.2f} operations/second")

    # Show cache metrics
    metrics = cache.get_metrics()
    print("\nCache Metrics:")
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")


async def demonstrate_key_level_locking(cache: EnhancedAsyncTTLCache) -> None:  # type: ignore[no-any-unimported]
    """
    Demonstrate the benefits of key-level locking.

    Args:
        cache: The cache instance
    """
    # Set up test data
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")

    # Define tasks that operate on different keys
    async def task1() -> list[float]:
        times = []
        for i in range(10):
            start = time.time()
            await cache.set("key1", f"new_value1_{i}")
            await asyncio.sleep(0.05)  # Simulate work while holding the lock
            await cache.get("key1")
            times.append(time.time() - start)
        return times

    async def task2() -> list[float]:
        times = []
        for i in range(10):
            start = time.time()
            await cache.set("key2", f"new_value2_{i}")
            await asyncio.sleep(0.05)  # Simulate work while holding the lock
            await cache.get("key2")
            times.append(time.time() - start)
        return times

    print("\nDemonstrating key-level locking...")
    print("Running two tasks that operate on different keys concurrently")

    start_time = time.time()
    times1, times2 = await asyncio.gather(task1(), task2())
    total_time = time.time() - start_time

    print(f"Total time with key-level locking: {total_time:.2f} seconds")
    print(f"Average operation time for task1: {sum(times1)/len(times1):.3f} seconds")
    print(f"Average operation time for task2: {sum(times2)/len(times2):.3f} seconds")

    # With shard-level locking, the operations would be sequential
    print(
        f"Estimated time with shard-level locking: {sum(times1) + sum(times2):.2f} seconds"
    )
    print(
        f"Speedup from key-level locking: {(sum(times1) + sum(times2))/total_time:.2f}x"
    )


async def demonstrate_parallel_cleanup(cache: EnhancedAsyncTTLCache) -> None:  # type: ignore[no-any-unimported]
    """
    Demonstrate the benefits of parallel cleanup.

    Args:
        cache: The cache instance
    """
    print("\nDemonstrating parallel cleanup...")

    # Add many entries with short TTL
    num_entries = 10000
    print(f"Adding {num_entries} entries with short TTL...")

    for i in range(num_entries):
        await cache.set(f"expired_key_{i}", f"value_{i}", ttl_seconds=0)

    # Force cleanup and measure time
    print("Running cleanup...")
    start_time = time.time()

    await cache._remove_expired_entries_parallel()

    duration = time.time() - start_time
    print(
        f"Parallel cleanup of {num_entries} entries completed in {duration:.3f} seconds"
    )
    print(f"Cleanup rate: {num_entries/duration:.2f} entries/second")


async def main() -> None:
    """Main demonstration function."""
    print("Enhanced AsyncTTLCache Demonstration")
    print("===================================")

    # Create cache instance
    cache = EnhancedAsyncTTLCache(
        ttl_seconds=60, cleanup_interval=30, num_shards=16, max_workers=4
    )

    try:
        # Run demonstrations
        await simulate_high_concurrency(cache)
        await demonstrate_key_level_locking(cache)
        await demonstrate_parallel_cleanup(cache)

    finally:
        # Clean up
        await cache.stop()
        print("\nCache stopped")


if __name__ == "__main__":
    asyncio.run(main())
