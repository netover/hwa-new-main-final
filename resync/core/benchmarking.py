"""Minimal benchmarking helpers used by API endpoints."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, List, Sequence


async def _awaitable_call(func: Callable[[], Awaitable[Any] | Any]) -> Any:
    result = func()
    if asyncio.iscoroutine(result):
        return await result
    return result


@dataclass(slots=True)
class BenchmarkResult:
    name: str
    operation: str
    iterations: int
    warmup_rounds: int
    mean_duration_ms: float
    success_rate: float
    timestamp: float


class InMemoryBenchmark:
    """Captures lightweight benchmark results in memory."""

    def __init__(self) -> None:
        self.results: List[BenchmarkResult] = []

    async def run_benchmark(
        self,
        *,
        name: str,
        operation: str,
        func: Callable[[], Awaitable[Any] | Any],
        iterations: int,
        warmup_rounds: int,
    ) -> BenchmarkResult:
        for _ in range(max(0, warmup_rounds)):
            await _awaitable_call(func)

        total_duration = 0.0
        successes = 0
        iterations = max(1, iterations)

        for _ in range(iterations):
            start = time.perf_counter()
            try:
                await _awaitable_call(func)
                successes += 1
            finally:
                total_duration += (time.perf_counter() - start) * 1000.0

        mean_duration = total_duration / iterations
        success_rate = successes / iterations
        result = BenchmarkResult(
            name=name,
            operation=operation,
            iterations=iterations,
            warmup_rounds=warmup_rounds,
            mean_duration_ms=mean_duration,
            success_rate=success_rate,
            timestamp=time.time(),
        )
        self.results.append(result)
        return result

    def get_historical_performance(self, operation: str) -> Sequence[BenchmarkResult]:
        return [result for result in self.results if result.operation == operation]


class BenchmarkRunner:
    """Facade combining benchmarking operations with agent/TWS dependencies."""

    def __init__(self, agent_manager: Any, tws_client: Any) -> None:
        self.agent_manager = agent_manager
        self.tws_client = tws_client
        self.benchmark = InMemoryBenchmark()

    async def run_comprehensive_benchmark(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        status_result = await self.benchmark.run_benchmark(
            name="TWS Status Check",
            operation="tws_status",
            func=self._benchmark_tws_status,
            iterations=5,
            warmup_rounds=1,
        )
        results["tws_status"] = status_result.__dict__

        agent_result = await self.benchmark.run_benchmark(
            name="Agent Creation",
            operation="create_agent",
            func=self._benchmark_agent_creation,
            iterations=5,
            warmup_rounds=1,
        )
        results["agent_creation"] = agent_result.__dict__

        return results

    async def _benchmark_tws_status(self) -> dict[str, Any]:
        # In the real system this would call the TWS client; here we just return a placeholder.
        return {"status": "ok"}

    async def _benchmark_agent_creation(self) -> dict[str, Any]:
        # Placeholder agent creation benchmark.
        return {"created": True}


async def create_benchmark_runner(agent_manager: Any, tws_client: Any) -> BenchmarkRunner:
    """Factory returning a ready-to-use benchmark runner."""
    return BenchmarkRunner(agent_manager, tws_client)


__all__ = ["BenchmarkRunner", "BenchmarkResult", "InMemoryBenchmark", "create_benchmark_runner"]
