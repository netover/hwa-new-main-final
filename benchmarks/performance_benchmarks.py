"""
Performance Benchmarking module for Resync application optimizations.

This module includes benchmarks for:
1. Async cache operations with parallel cleanup
2. TWS batch operations with parallel API calls
3. Agent initialization with parallel creation
4. WebSocket connection handling
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from resync.core._deprecated.async_cache_refactored import AsyncTTLCache


class PerformanceBenchmarkSuite:
    """
    A comprehensive performance benchmarking suite for the Resync application.
    """

    def __init__(self) -> None:
        self.results: dict[str, Any] = {}

    async def benchmark_async_cache_cleanup(self) -> None:
        """
        Benchmark the async cache cleanup operation with parallel vs sequential implementation.
        """
        print("Benchmarking async cache cleanup...")

        # Initialize cache with many entries
        cache = AsyncTTLCache(ttl_seconds=1, cleanup_interval=3600, num_shards=16)

        # Add many entries that will expire quickly
        for i in range(1000):
            await cache.set(
                f"key_{i}", f"value_{i}", ttl_seconds=0.01
            )  # Expire quickly

        # Wait for entries to expire
        await asyncio.sleep(0.1)

        # Benchmark cleanup performance
        start_time = time.time()
        await cache._remove_expired_entries()
        end_time = time.time()

        cleanup_time = end_time - start_time
        self.results["cache_cleanup_time"] = cleanup_time
        print(
            f"Cache cleanup time: {cleanup_time:.4f} seconds for {cache.size()} entries"
        )

        await cache.stop()

    async def benchmark_tws_batch_operations(self) -> None:
        """
        Benchmark TWS batch operations with parallel vs sequential implementation.
        """
        print("Benchmarking TWS batch operations...")

        # This is a simulation since we don't have actual TWS running
        # In a real scenario, we would test with actual TWS API calls

        # Create mock job IDs
        job_ids = [f"job_{i}" for i in range(50)]

        # Simulate parallel vs sequential processing
        async def simulate_sequential_processing() -> float:
            results = {}
            start_time = time.time()
            for job_id in job_ids:
                # Simulate API call taking 0.1 seconds
                await asyncio.sleep(0.1)
                results[job_id] = f"status_{job_id}"
            end_time = time.time()
            return end_time - start_time

        async def simulate_parallel_processing() -> float:
            start_time = time.time()

            async def fetch_job_status(job_id: str) -> tuple[str, str]:
                # Simulate API call taking 0.1 seconds
                await asyncio.sleep(0.1)
                return job_id, f"status_{job_id}"

            tasks = [fetch_job_status(job_id) for job_id in job_ids]
            results = {}
            for job_id, status in await asyncio.gather(*tasks):
                results[job_id] = status

            end_time = time.time()
            return end_time - start_time

        sequential_time = await simulate_sequential_processing()
        parallel_time = await simulate_parallel_processing()

        self.results["tws_sequential_time"] = sequential_time
        self.results["tws_parallel_time"] = parallel_time
        self.results["tws_improvement_factor"] = (
            sequential_time / parallel_time if parallel_time > 0 else 0
        )

        print(f"TWS sequential time: {sequential_time:.4f}s")
        print(f"TWS parallel time: {parallel_time:.4f}s")
        print(f"Improvement factor: {self.results['tws_improvement_factor']:.2f}x")

    async def benchmark_agent_initialization(self) -> None:
        """
        Benchmark agent initialization with parallel vs sequential implementation.
        """
        print("Benchmarking agent initialization...")

        # This would benchmark the agent creation process
        from resync.core.agent_manager import AgentConfig

        # Create mock agent configurations
        agent_configs = []
        for i in range(20):
            config = AgentConfig(
                id=f"agent_{i}",
                name=f"Agent {i}",
                role="Test agent",
                goal="To be used for testing",
                backstory="I am a test agent",
                tools=(
                    ["tws_status_tool"] if i % 2 == 0 else ["tws_troubleshooting_tool"]
                ),
                model_name="llama3:latest",
                memory=True,
                verbose=False,
            )
            agent_configs.append(config)

        # Benchmark the agent creation process (this is a simplified simulation)
        start_time = time.time()

        # Simulate parallel agent creation
        async def create_mock_agent(config: Any) -> str:
            # Simulate agent initialization with some async work
            await asyncio.sleep(0.05)  # Simulate initialization time
            return str(config.get("id", "mock_agent"))

        tasks = [create_mock_agent(config) for config in agent_configs]
        await asyncio.gather(*tasks)

        end_time = time.time()
        parallel_time = end_time - start_time

        # Simulate sequential agent creation for comparison
        start_time = time.time()
        for config in agent_configs:
            await asyncio.sleep(0.05)  # Simulate initialization time
        end_time = time.time()
        sequential_time = end_time - start_time

        self.results["agent_sequential_time"] = sequential_time
        self.results["agent_parallel_time"] = parallel_time
        self.results["agent_improvement_factor"] = (
            sequential_time / parallel_time if parallel_time > 0 else 0
        )

        print(f"Agent sequential time: {sequential_time:.4f}s")
        print(f"Agent parallel time: {parallel_time:.4f}s")
        print(f"Improvement factor: {self.results['agent_improvement_factor']:.2f}x")

    async def benchmark_websocket_concurrent_connections(self) -> None:
        """
        Benchmark WebSocket concurrent connection handling.
        """
        print("Benchmarking WebSocket concurrent connections...")

        # This would simulate multiple concurrent WebSocket connections
        # For now, simulating the connection handling process

        async def simulate_websocket_interaction(connection_id: int) -> int:
            # Simulate connection processing time
            await asyncio.sleep(0.01)
            # Simulate message processing
            for _ in range(5):
                await asyncio.sleep(0.001)
            return connection_id

        # Test with 100 concurrent connections
        num_connections = 100
        start_time = time.time()

        tasks = [simulate_websocket_interaction(i) for i in range(num_connections)]
        await asyncio.gather(*tasks)

        end_time = time.time()
        total_time = end_time - start_time

        self.results["websocket_concurrent_connections"] = num_connections
        self.results["websocket_total_time"] = total_time
        self.results["websocket_connections_per_second"] = (
            num_connections / total_time if total_time > 0 else 0
        )

        print(
            f"Processed {num_connections} concurrent WebSocket connections in {total_time:.4f}s"
        )
        print(
            f"Connections per second: {self.results['websocket_connections_per_second']:.2f}"
        )

    async def run_all_benchmarks(self) -> dict[str, Any]:
        """
        Run all performance benchmarks and return the results.
        """
        print("Starting performance benchmarking suite...")

        await self.benchmark_async_cache_cleanup()
        await self.benchmark_tws_batch_operations()
        await self.benchmark_agent_initialization()
        await self.benchmark_websocket_concurrent_connections()

        print("\nPerformance Benchmark Results Summary:")
        print("=" * 50)
        for key, value in self.results.items():
            if isinstance(value, float):
                print(f"{key}: {value:.4f}")
            else:
                print(f"{key}: {value}")

        return self.results


# Run benchmarks when executed as a script
async def run_benchmarks() -> dict[str, Any]:
    benchmark_suite = PerformanceBenchmarkSuite()
    return await benchmark_suite.run_all_benchmarks()


if __name__ == "__main__":
    asyncio.run(run_benchmarks())




