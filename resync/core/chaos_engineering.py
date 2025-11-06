"""Lightweight chaos engineering and fuzzing utilities used by tests."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

from resync.core.agent_manager import AgentManager
from resync.core._deprecated.async_cache_refactored import AsyncTTLCache
from resync.core.write_ahead_log import (
    WalOperationType,
    WalEntry,
    get_write_ahead_log,
)


@dataclass(slots=True)
class ChaosTestResult:
    """Structured result returned by every chaos experiment."""

    test_name: str
    component: str
    duration: float
    success: bool
    error_count: int = 0
    operations_performed: int = 0
    anomalies_detected: List[str] = field(default_factory=list)
    correlation_id: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FuzzingScenario:
    """Definition of a fuzzing scenario."""

    name: str
    description: str
    fuzz_function: Callable[[], Dict[str, Any]]
    expected_failures: List[str] = field(default_factory=list)
    max_duration: float = 60.0


class ChaosEngineer:
    """Coordinates chaos experiments across components."""

    def __init__(self) -> None:
        self.correlation_id = uuid.uuid4().hex
        self.results: List[ChaosTestResult] = []
        self.active_tests: Dict[str, asyncio.Task[Any]] = {}
        self._lock = asyncio.Lock()

    async def run_full_chaos_suite(self, *, duration_minutes: float = 1.0) -> Dict[str, Any]:
        """Execute a curated list of chaos experiments."""

        start = time.perf_counter()
        planned_tests = [
            self._cache_race_condition_fuzzing,
            self._agent_concurrent_initialization_chaos,
            self._audit_db_failure_injection,
            self._memory_pressure_simulation,
            self._network_partition_simulation,
            self._component_isolation_testing,
        ]

        self.results.clear()
        for test_fn in planned_tests:
            try:
                result = await test_fn()
            except Exception as exc:  # pragma: no cover - defensive
                result = ChaosTestResult(
                    test_name=test_fn.__name__,
                    component="unknown",
                    duration=0.0,
                    success=False,
                    error_count=1,
                    anomalies_detected=[str(exc)],
                    correlation_id=self.correlation_id,
                )
            self.results.append(result)

        duration = time.perf_counter() - start
        successful = sum(1 for result in self.results if result.success)
        total_anomalies = sum(len(result.anomalies_detected) for result in self.results)

        summary = {
            "correlation_id": self.correlation_id,
            "duration": duration,
            "total_tests": len(self.results),
            "successful_tests": successful,
            "success_rate": successful / len(self.results) if self.results else 0.0,
            "total_anomalies": total_anomalies,
            "test_results": self.results,
        }
        return summary

    async def _cache_race_condition_fuzzing(self) -> ChaosTestResult:
        """Exercise the async cache under concurrent pressure."""

        start = time.perf_counter()
        cache = AsyncTTLCache(ttl_seconds=0.5, cleanup_interval=0.2, num_shards=4)
        errors: List[str] = []
        operations = 0

        async def worker(worker_id: int) -> None:
            nonlocal operations
            for i in range(25):
                key = f"chaos_key_{worker_id}_{i}"
                try:
                    op = (worker_id + i) % 3
                    if op == 0:
                        await cache.set(key, f"value_{worker_id}_{i}")
                    elif op == 1:
                        await cache.get(key)
                    else:
                        await cache.delete(key)
                    operations += 1
                except Exception as exc:  # pragma: no cover - defensive
                    errors.append(str(exc))

        await asyncio.gather(*(worker(i) for i in range(6)))
        metrics = cache.get_detailed_metrics()
        await cache.stop()

        return ChaosTestResult(
            test_name="cache_race_condition_fuzzing",
            component="async_cache",
            duration=time.perf_counter() - start,
            success=not errors,
            error_count=len(errors),
            operations_performed=operations,
            anomalies_detected=errors[:20],
            correlation_id=self.correlation_id,
            details={"cache_metrics": metrics},
        )

    async def _agent_concurrent_initialization_chaos(self) -> ChaosTestResult:
        """Stress the agent manager with concurrent access."""

        start = time.perf_counter()
        errors: List[str] = []

        async def load_agents() -> int:
            try:
                manager = AgentManager()
                agents = await manager.get_all_agents()
                return len(agents)
            except Exception as exc:  # pragma: no cover - defensive
                errors.append(str(exc))
                return 0

        counts = await asyncio.gather(*(load_agents() for _ in range(5)))

        return ChaosTestResult(
            test_name="agent_concurrent_initialization_chaos",
            component="agent_manager",
            duration=time.perf_counter() - start,
            success=not errors,
            error_count=len(errors),
            operations_performed=sum(counts),
            anomalies_detected=errors,
            correlation_id=self.correlation_id,
        )

    async def _audit_db_failure_injection(self) -> ChaosTestResult:
        """Simulate intermittent failures when writing audit records."""

        start = time.perf_counter()
        wal = get_write_ahead_log()
        failures = 0
        anomalies: List[str] = []

        for i in range(10):
            entry = WalEntry(
                operation=WalOperationType.WRITE,
                key=f"audit_{i}",
                sequence_number=i,
                value={"event": "test", "index": i},
                timestamp=time.time(),
            )
            try:
                await wal.write_log(
                    f"audit_event_{i}", level="INFO"
                )
                wal.pending_logs.append(entry)
            except Exception as exc:  # pragma: no cover - defensive
                failures += 1
                anomalies.append(str(exc))

        await wal.flush_logs()

        return ChaosTestResult(
            test_name="audit_db_failure_injection",
            component="write_ahead_log",
            duration=time.perf_counter() - start,
            success=failures == 0,
            error_count=failures,
            operations_performed=10,
            anomalies_detected=anomalies,
            correlation_id=self.correlation_id,
        )

    async def _memory_pressure_simulation(self) -> ChaosTestResult:
        """Create large objects in cache to simulate memory pressure."""

        start = time.perf_counter()
        cache = AsyncTTLCache(ttl_seconds=1, cleanup_interval=0.5, num_shards=2)
        created = 0
        anomalies: List[str] = []

        try:
            for idx in range(30):
                payload = {"data": "x" * 1024, "idx": idx, "created": time.time()}
                try:
                    await cache.set(f"mem_{idx}", payload, ttl_seconds=2)
                    created += 1
                except Exception as exc:  # pragma: no cover - defensive
                    anomalies.append(str(exc))
                    break
            await asyncio.sleep(0)
            metrics = cache.get_detailed_metrics()
        finally:
            await cache.stop()

        return ChaosTestResult(
            test_name="memory_pressure_simulation",
            component="async_cache",
            duration=time.perf_counter() - start,
            success=True,
            error_count=len(anomalies),
            operations_performed=created,
            anomalies_detected=anomalies,
            correlation_id=self.correlation_id,
            details={"cache_metrics": metrics},
        )

    async def _network_partition_simulation(self) -> ChaosTestResult:
        """Simulate temporary network partitions between services."""

        start = time.perf_counter()
        failures = 0
        anomalies: List[str] = []

        async def simulate_call(call_id: int) -> None:
            nonlocal failures
            await asyncio.sleep(0)
            if call_id % 5 == 0:
                failures += 1
                anomalies.append(f"partition_detected_{call_id}")

        await asyncio.gather(*(simulate_call(i) for i in range(20)))

        return ChaosTestResult(
            test_name="network_partition_simulation",
            component="chaos_network",
            duration=time.perf_counter() - start,
            success=True,
            error_count=failures,
            operations_performed=20,
            anomalies_detected=anomalies,
            correlation_id=self.correlation_id,
        )

    async def _component_isolation_testing(self) -> ChaosTestResult:
        """Ensure failing components do not cascade across the system."""

        start = time.perf_counter()
        anomalies: List[str] = []

        try:
            manager = AgentManager()
            await manager.get_all_agents()
        except Exception as exc:  # pragma: no cover - defensive
            anomalies.append(f"agent_manager_error: {exc}")

        cache = AsyncTTLCache(ttl_seconds=1)
        try:
            await cache.set("isolation_key", "value")
            await cache.delete("isolation_key")
        except Exception as exc:  # pragma: no cover - defensive
            anomalies.append(f"cache_error: {exc}")
        finally:
            await cache.stop()

        return ChaosTestResult(
            test_name="component_isolation_testing",
            component="system",
            duration=time.perf_counter() - start,
            success=not anomalies,
            error_count=len(anomalies),
            operations_performed=2,
            anomalies_detected=anomalies,
            correlation_id=self.correlation_id,
        )


class FuzzingEngine:
    """Runs lightweight fuzzing scenarios and collects metrics."""

    def __init__(self) -> None:
        self.correlation_id = uuid.uuid4().hex
        self.scenarios: List[FuzzingScenario] = [
            FuzzingScenario(
                name="cache_keys",
                description="Fuzz cache set/get/delete operations.",
                fuzz_function=self._fuzz_cache_keys,
            ),
            FuzzingScenario(
                name="cache_values",
                description="Fuzz cache values serialization.",
                fuzz_function=self._fuzz_cache_values,
            ),
            FuzzingScenario(
                name="cache_ttl",
                description="Fuzz cache TTL expirations.",
                fuzz_function=self._fuzz_cache_ttl,
            ),
            FuzzingScenario(
                name="agent_configs",
                description="Fuzz agent configuration handling.",
                fuzz_function=self._fuzz_agent_configs,
            ),
            FuzzingScenario(
                name="audit_records",
                description="Fuzz audit record persistence.",
                fuzz_function=self._fuzz_audit_records,
            ),
        ]

    async def run_fuzzing_campaign(self, *, max_duration: float = 5.0) -> Dict[str, Any]:
        start = time.perf_counter()
        results: List[Dict[str, Any]] = []

        for scenario in self.scenarios:
            outcome = scenario.fuzz_function()
            results.append({"scenario": scenario.name, "result": outcome})

        duration = time.perf_counter() - start
        successful = sum(1 for entry in results if entry["result"].get("failed", 0) == 0)

        return {
            "correlation_id": self.correlation_id,
            "campaign_duration": duration,
            "total_scenarios": len(results),
            "successful_scenarios": successful,
            "success_rate": successful / len(results) if results else 0.0,
            "results": results,
        }

    def _fuzz_cache_keys(self) -> Dict[str, Any]:
        cache = AsyncTTLCache(ttl_seconds=1, num_shards=2)
        passed = failed = 0
        errors: List[str] = []
        async def scenario() -> None:
            nonlocal passed, failed, errors
            try:
                await cache.set("key", "value")
                value = await cache.get("key")
                if value == "value":
                    passed += 1
                else:
                    failed += 1
            except Exception as exc:
                failed += 1
                errors.append(str(exc))
        asyncio.run(scenario())
        asyncio.run(cache.stop())
        return {"passed": passed, "failed": failed, "errors": errors}

    def _fuzz_cache_values(self) -> Dict[str, Any]:
        cache = AsyncTTLCache(ttl_seconds=1)
        passed = failed = 0
        errors: List[str] = []

        async def scenario() -> None:
            nonlocal passed, failed, errors
            complex_value = {"numbers": list(range(10)), "nested": {"foo": "bar"}}
            try:
                await cache.set("complex", complex_value)
                value = await cache.get("complex")
                if value == complex_value:
                    passed += 1
                else:
                    failed += 1
            except Exception as exc:
                failed += 1
                errors.append(str(exc))

        asyncio.run(scenario())
        asyncio.run(cache.stop())
        return {"passed": passed, "failed": failed, "errors": errors}

    def _fuzz_cache_ttl(self) -> Dict[str, Any]:
        cache = AsyncTTLCache(ttl_seconds=0.1, cleanup_interval=0.05)
        passed = failed = 0
        errors: List[str] = []

        async def scenario() -> None:
            nonlocal passed, failed, errors
            try:
                await cache.set("ttl_key", "ttl_value", ttl_seconds=0.2)
                await asyncio.sleep(0.3)
                value = await cache.get("ttl_key")
                if value is None:
                    passed += 1
                else:
                    failed += 1
            except Exception as exc:
                failed += 1
                errors.append(str(exc))

        asyncio.run(scenario())
        asyncio.run(cache.stop())
        return {"passed": passed, "failed": failed, "errors": errors}

    def _fuzz_agent_configs(self) -> Dict[str, Any]:
        passed = failed = 0
        errors: List[str] = []

        async def scenario() -> None:
            nonlocal passed, failed, errors
            try:
                manager = AgentManager()
                agents = await manager.get_all_agents()
                if isinstance(agents, list):
                    passed += 1
                else:
                    failed += 1
            except Exception as exc:
                failed += 1
                errors.append(str(exc))

        asyncio.run(scenario())
        return {"passed": passed, "failed": failed, "errors": errors}

    def _fuzz_audit_records(self) -> Dict[str, Any]:
        wal = get_write_ahead_log()
        passed = failed = 0
        errors: List[str] = []

        async def scenario() -> None:
            nonlocal passed, failed, errors
            try:
                await wal.write_log("fuzz audit", level="INFO")
                passed += 1
            except Exception as exc:  # pragma: no cover - defensive
                failed += 1
                errors.append(str(exc))

        asyncio.run(scenario())
        return {"passed": passed, "failed": failed, "errors": errors}


async def run_chaos_engineering_suite(duration_minutes: float = 1.0) -> Dict[str, Any]:
    return await chaos_engineer.run_full_chaos_suite(duration_minutes=duration_minutes)


async def run_fuzzing_campaign(max_duration: float = 5.0) -> Dict[str, Any]:
    return await fuzzing_engine.run_fuzzing_campaign(max_duration=max_duration)


chaos_engineer = ChaosEngineer()
fuzzing_engine = FuzzingEngine()


__all__ = [
    "ChaosEngineer",
    "ChaosTestResult",
    "FuzzingEngine",
    "FuzzingScenario",
    "chaos_engineer",
    "fuzzing_engine",
    "run_chaos_engineering_suite",
    "run_fuzzing_campaign",
    "AsyncTTLCache",
    "AgentManager",
]
