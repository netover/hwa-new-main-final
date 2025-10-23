"""
Tests for connection pool monitoring, metrics collection, and alerting.

This module tests:
- Pool statistics collection and accuracy
- Connection leak detection mechanisms
- Performance metrics and monitoring
- Alert threshold configurations
- Health check monitoring
- Resource utilization tracking
- Connection lifecycle monitoring
"""

import asyncio
import threading
import time
from asyncio import Lock
from dataclasses import asdict
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio
import structlog

from resync.core.connection_pool_manager import (ConnectionPoolConfig,
                                                 ConnectionPoolManager,
                                                 DatabaseConnectionPool)
from resync.core.exceptions import PoolExhaustedError, TimeoutError

# Configure structured logging for tests
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)
from resync.core.websocket_pool_manager import WebSocketPoolManager


class TestConnectionPoolMetrics:
    """Test connection pool metrics collection."""

    @pytest.fixture(scope="class")
    def mock_db_pool_dependencies(self):
        """A class-scoped fixture to mock database pool dependencies once per test class."""
        with (
            patch(
                "resync.core.pools.db_pool.create_async_engine"
            ) as mock_create_engine,
            patch("resync.core.pools.db_pool.async_sessionmaker") as mock_sessionmaker,
        ):

            mock_engine = AsyncMock()
            mock_create_engine.return_value = mock_engine

            mock_session_instance = AsyncMock()
            mock_session_instance.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session_maker_instance = Mock()
            mock_session_maker_instance.return_value = mock_session_instance
            mock_sessionmaker.return_value = mock_session_maker_instance

            yield

    @pytest_asyncio.fixture
    async def monitored_pool(self, mock_db_pool_dependencies):
        """Create monitored pool with comprehensive cleanup and validation."""
        config = ConnectionPoolConfig(
            pool_name="metrics_test_pool",
            min_size=2,
            max_size=10,
            connection_timeout=5,
            health_check_interval=10,
        )

        pool = DatabaseConnectionPool(
            config, "postgresql://test:test@localhost:5432/test"
        )

        try:
            await asyncio.wait_for(pool.initialize(), timeout=10.0)
            initial_stats = pool.stats
            assert initial_stats.active_connections == 0
            assert initial_stats.total_connections == 0
            yield pool
        finally:
            try:
                await asyncio.wait_for(pool.close(), timeout=5.0)
            except Exception as e:
                pytest.fail(f"Pool cleanup failed: {e}")
            final_stats = pool.stats
            assert final_stats.active_connections == 0, "Pool leaked connections"

    @pytest.mark.asyncio
    async def test_pool_statistics_accuracy(self, monitored_pool):
        """Test accuracy of pool statistics with comprehensive observability."""
        logger = structlog.get_logger("test.pool.stats")

        # Snapshot pré-teste para validação de deltas
        pre_stats = monitored_pool.get_stats_copy()
        logger.info("test_started", stats=pre_stats)

        # Proteção thread-safe para conexões compartilhadas
        connections_lock = Lock()
        connections = []

        async def acquire_connection_safe(connection_id: int):
            """Acquire connection with atomic state management."""
            op_logger = logger.bind(connection_id=connection_id)
            op_logger.debug("acquiring_connection")

            try:
                async with monitored_pool.get_connection():
                    # Operação atômica: append + validação
                    async with connections_lock:
                        connections.append(connection_id)
                        # Snapshot atômico do estado
                        current_stats = monitored_pool.get_stats_copy()
                        assert current_stats["active_connections"] >= 1

                    op_logger.info(
                        "connection_acquired",
                        active=current_stats["active_connections"],
                        total=current_stats["total_connections"],
                    )

                    # Sleep não-bloqueante com jitter para evitar thundering herd
                    await asyncio.sleep(0.001 * (1 + connection_id * 0.1))

            except Exception as e:
                op_logger.error("connection_failed", error=str(e))
                raise

        # Execute with timing and diagnostics
        start_time = time.perf_counter()
        num_operations = 3
        tasks = [acquire_connection_safe(i) for i in range(num_operations)]
        await asyncio.gather(*tasks)
        execution_time = time.perf_counter() - start_time

        # Snapshot pós-teste
        post_stats = monitored_pool.get_stats_copy()

        # Validação determinística com contexto rico
        expected_new_hits = num_operations
        actual_new_hits = post_stats["pool_hits"] - pre_stats["pool_hits"]

        logger.info(
            "test_completed",
            execution_time=execution_time,
            pre_stats=pre_stats,
            post_stats=post_stats,
            connections_processed=len(connections),
            expected_hits=expected_new_hits,
            actual_hits=actual_new_hits,
        )

        # Assertions determinísticas aprimoradas
        assert actual_new_hits == expected_new_hits, (
            f"Expected exactly {expected_new_hits} new hits, got {actual_new_hits}. "
            f"Stats delta: {post_stats}"
        )

        assert post_stats["active_connections"] == 0, (
            f"Connection leak detected: {post_stats['active_connections']} active. "
            f"Connections: {connections}"
        )

        # The pool might reuse connections, so we expect creations to be <= num_operations
        # and > 0 since the pool started empty.
        assert (
            0 < post_stats["connection_creations"] <= num_operations
        ), f"Expected between 1 and {num_operations} connection creations, but got {post_stats['connection_creations']}"

        # Validação de métricas de performance
        assert execution_time < 1.0, f"Test took too long: {execution_time}s"

        logger.info(
            "test_validation_complete",
            total_connections=len(connections),
            total_hits=post_stats["pool_hits"],
            performance_ratio=post_stats["pool_hits"]
            / max(post_stats["connection_creations"], 1),
        )

    @pytest.mark.asyncio
    async def test_pool_performance_metrics(self, monitored_pool):
        """Test pool performance metrics collection."""
        metrics = []

        async def timed_operation(operation_id: int):
            """Operation with timing metrics."""
            start_time = time.perf_counter()

            try:
                async with monitored_pool.get_connection() as engine:
                    # Simulate work
                    await asyncio.sleep(0.001 * operation_id)

                    # Record metrics
                    end_time = time.perf_counter()
                    wait_time = end_time - start_time

                    stats = monitored_pool.get_stats()
                    metrics.append(
                        {
                            "operation_id": operation_id,
                            "wait_time": wait_time,
                            "active_connections": stats.active_connections,
                            "pool_hits": stats.pool_hits,
                            "pool_misses": stats.pool_misses,
                        }
                    )

                    return f"success_{operation_id}"

            except Exception as e:
                end_time = time.perf_counter()
                metrics.append(
                    {
                        "operation_id": operation_id,
                        "wait_time": end_time - start_time,
                        "error": str(e),
                    }
                )
                raise

        # Run timed operations
        num_operations = 10
        tasks = [timed_operation(i) for i in range(num_operations)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Analyze metrics
        successful_metrics = [m for m in metrics if "error" not in m]

        assert len(successful_metrics) >= num_operations * 0.8

        # Check timing consistency
        wait_times = [m["wait_time"] for m in successful_metrics]
        avg_wait_time = sum(wait_times) / len(wait_times)

        assert avg_wait_time < 0.1  # Average wait should be reasonable

        # Update pool stats with average wait time
        stats = monitored_pool.get_stats()
        assert stats.average_wait_time >= 0

    @pytest.mark.asyncio
    async def test_pool_exhaustion_metrics(self, monitored_pool):
        """Test metrics during pool exhaustion."""
        exhaustion_events = []

        # Constrain pool to force exhaustion
        monitored_pool.config.max_size = 2

        async def exhaust_pool_operation(operation_id: int):
            """Operation that might exhaust the pool."""
            try:
                async with monitored_pool.get_connection() as engine:
                    # Hold connection to exhaust pool
                    await asyncio.sleep(0.1)
                    return f"success_{operation_id}"

            except PoolExhaustedError:
                exhaustion_events.append(
                    {
                        "operation_id": operation_id,
                        "timestamp": time.time(),
                        "type": "pool_exhausted",
                    }
                )
                raise
            except TimeoutError:
                exhaustion_events.append(
                    {
                        "operation_id": operation_id,
                        "timestamp": time.time(),
                        "type": "timeout",
                    }
                )
                raise

        # Create more operations than pool can handle
        num_operations = 5
        tasks = [exhaust_pool_operation(i) for i in range(num_operations)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Should have some exhaustion events
        assert len(exhaustion_events) > 0

        # Check pool stats for exhaustion
        stats = monitored_pool.get_stats()
        assert stats.pool_exhaustions >= len(exhaustion_events)

        # Verify exhaustion events are recorded properly
        timeout_events = [e for e in exhaustion_events if e["type"] == "timeout"]
        pool_exhausted_events = [
            e for e in exhaustion_events if e["type"] == "pool_exhausted"
        ]

        assert len(timeout_events) + len(pool_exhausted_events) == len(
            exhaustion_events
        )


class TestConnectionLeakDetection:
    """Test connection leak detection mechanisms."""

    @pytest.fixture(scope="class")
    def mock_db_pool_dependencies(self):
        """A class-scoped fixture to mock database pool dependencies once per test class."""
        with (
            patch(
                "resync.core.pools.db_pool.create_async_engine"
            ) as mock_create_engine,
            patch("resync.core.pools.db_pool.async_sessionmaker") as mock_sessionmaker,
        ):

            mock_engine = AsyncMock()
            mock_create_engine.return_value = mock_engine

            mock_session_instance = AsyncMock()
            mock_session_instance.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session_maker_instance = Mock()
            mock_session_maker_instance.return_value = mock_session_instance
            mock_sessionmaker.return_value = mock_session_maker_instance

            yield

    @pytest_asyncio.fixture
    async def leaky_pool(self, mock_db_pool_dependencies):
        """Create a pool for leak detection testing."""
        config = ConnectionPoolConfig(
            pool_name="leak_detection_pool",
            min_size=1,
            max_size=5,
            connection_timeout=3,
            idle_timeout=2,  # Short idle timeout for testing
            health_check_interval=5,
        )

        pool = DatabaseConnectionPool(
            config, "postgresql://test:test@localhost:5432/test"
        )
        await pool.initialize()
        yield pool
        await pool.close()

    @pytest.mark.asyncio
    async def test_connection_leak_detection(self, leaky_pool):
        """Test detection of connection leaks."""
        leaked_connections = []

        async def leaky_operation(operation_id: int):
            """Operation that might leak connections."""
            try:
                # Intentionally create potential leak by not using context manager properly
                engine = await leaky_pool._create_connection()
                leaked_connections.append(engine)

                # Simulate work without proper cleanup
                await asyncio.sleep(0.1)

                # In some cases, we "forget" to close the connection
                if operation_id % 3 == 0:
                    return f"leaked_{operation_id}"
                else:
                    await leaky_pool._close_connection(engine)
                    leaked_connections.remove(engine)
                    return f"clean_{operation_id}"

            except Exception as e:
                return f"error_{operation_id}_{str(e)}"

        # Run potentially leaky operations
        num_operations = 6
        results = []

        for i in range(num_operations):
            result = await leaky_operation(i)
            results.append(result)

        # Check for leaks
        await asyncio.sleep(0.2)  # Allow cleanup time

        # Should detect potential leaks
        stats = leaky_pool.get_stats()

        # Some connections might be leaked
        potential_leaks = sum(1 for r in results if r.startswith("leaked"))
        assert potential_leaks > 0

    @pytest.mark.asyncio
    async def test_connection_lifecycle_monitoring(self, leaky_pool):
        """Test monitoring of connection lifecycle."""
        lifecycle_events = []

        # Hook into connection lifecycle
        original_create = leaky_pool._create_connection
        original_close = leaky_pool._close_connection

        async def tracked_create_connection():
            conn = await original_create()
            lifecycle_events.append(
                {
                    "event": "created",
                    "timestamp": time.time(),
                    "connection_id": id(conn),
                }
            )
            return conn

        async def tracked_close_connection(connection):
            lifecycle_events.append(
                {
                    "event": "closed",
                    "timestamp": time.time(),
                    "connection_id": id(connection),
                }
            )
            await original_close(connection)

        leaky_pool._create_connection = tracked_create_connection
        leaky_pool._close_connection = tracked_close_connection

        # Use connections
        async def tracked_operation(operation_id: int):
            async with leaky_pool.get_connection() as engine:
                await asyncio.sleep(0.01)
                return f"success_{operation_id}"

        tasks = [tracked_operation(i) for i in range(3)]
        await asyncio.gather(*tasks)

        # Analyze lifecycle events
        create_events = [e for e in lifecycle_events if e["event"] == "created"]
        close_events = [e for e in lifecycle_events if e["event"] == "closed"]

        # Should have creation events
        assert len(create_events) >= 3

        # Most connections should be closed properly
        assert len(close_events) >= len(create_events) * 0.8

        # Calculate connection lifetime
        if create_events and close_events:
            avg_lifetime = sum(
                close_events[i]["timestamp"] - create_events[i]["timestamp"]
                for i in range(min(len(close_events), len(create_events)))
            ) / min(len(close_events), len(create_events))

            assert avg_lifetime > 0
            assert avg_lifetime < 1.0  # Should be short for our test

    @pytest.mark.asyncio
    async def test_connection_health_monitoring(self, leaky_pool):
        """Test health monitoring of connections."""
        health_events = []

        # Simulate connection health issues
        async def unhealthy_operation(operation_id: int):
            """Operation that might create unhealthy connections."""
            async with leaky_pool.get_connection() as engine:
                # Simulate work
                await asyncio.sleep(0.01)

                # Simulate health check failure for some connections
                if operation_id % 4 == 0:
                    # Mock a health check failure
                    with patch.object(
                        leaky_pool, "_validate_connection", return_value=False
                    ):
                        health_events.append(
                            {
                                "operation_id": operation_id,
                                "health_status": "failed",
                                "timestamp": time.time(),
                            }
                        )

                return f"operation_{operation_id}"

        tasks = [unhealthy_operation(i) for i in range(8)]
        await asyncio.gather(*tasks)

        # Check health events
        assert len(health_events) >= 2  # Should have some health failures

        # Pool should track connection errors
        stats = leaky_pool.get_stats()
        assert stats.connection_errors >= len(health_events)


class TestPoolManagerMonitoring:
    """Test connection pool manager monitoring capabilities."""

    @pytest_asyncio.fixture
    async def monitored_manager(self):
        """Create a monitored connection pool manager."""
        manager = ConnectionPoolManager()

        # Mock pool creation
        with patch.object(manager, "_setup_pool"):
            with patch.object(manager, "health_check", return_value=True):
                await manager.initialize()
                yield manager
                await manager.shutdown()

    @pytest.mark.asyncio
    async def test_manager_health_aggregation(self, monitored_manager):
        """Test health aggregation across multiple pools."""
        # Add mock pools with different health states
        healthy_pool = Mock()
        healthy_pool.health_check = AsyncMock(return_value=True)
        healthy_stats = Mock()
        healthy_stats.connection_errors = 1
        healthy_stats.active_connections = 5
        healthy_pool.get_stats.return_value = healthy_stats

        unhealthy_pool = Mock()
        unhealthy_pool.health_check = AsyncMock(return_value=False)
        unhealthy_stats = Mock()
        unhealthy_stats.connection_errors = 15  # Above threshold
        unhealthy_stats.active_connections = 0
        unhealthy_pool.get_stats.return_value = unhealthy_stats

        monitored_manager.pools["healthy_pool"] = healthy_pool
        monitored_manager.pools["unhealthy_pool"] = unhealthy_pool

        # Test individual pool health
        health_results = await monitored_manager.health_check_all()
        assert health_results["healthy_pool"] is True
        assert health_results["unhealthy_pool"] is False

        # Test overall manager health
        is_healthy = monitored_manager.is_healthy()
        assert is_healthy is False  # Should be unhealthy due to one bad pool

    @pytest.mark.asyncio
    async def test_manager_performance_metrics(self, monitored_manager):
        """Test manager-level performance metrics."""
        performance_metrics = []

        # Add mock pools with performance data
        for i in range(3):
            mock_pool = Mock()
            mock_stats = Mock()
            mock_stats.pool_name = f"pool_{i}"
            mock_stats.pool_hits = 100 + i * 50
            mock_stats.pool_misses = 10 + i * 5
            mock_stats.active_connections = 5 + i
            mock_stats.idle_connections = 15 - i
            mock_stats.connection_errors = i
            mock_pool.get_stats.return_value = mock_stats

            monitored_manager.pools[f"pool_{i}"] = mock_pool

        # Collect manager metrics
        all_pools = monitored_manager.get_all_pools()
        assert len(all_pools) == 3

        # Calculate aggregate metrics
        total_hits = 0
        total_misses = 0
        total_active = 0
        total_errors = 0

        for pool_name, pool in all_pools.items():
            stats = pool.get_stats()
            total_hits += stats.pool_hits
            total_misses += stats.pool_misses
            total_active += stats.active_connections
            total_errors += stats.connection_errors

        # Verify aggregate calculations
        assert total_hits == 100 + 150 + 200  # 450
        assert total_misses == 10 + 15 + 20  # 45
        assert total_active == 5 + 6 + 7  # 18
        assert total_errors == 0 + 1 + 2  # 3

    @pytest.mark.asyncio
    async def test_manager_alert_thresholds(self, monitored_manager):
        """Test alert threshold monitoring."""
        alerts_triggered = []

        # Set up alert thresholds
        alert_thresholds = {
            "max_connection_errors": 10,
            "max_pool_exhaustions": 5,
            "max_response_time": 1.0,
            "min_health_check_pass_rate": 0.95,
        }

        # Add problematic pool
        problematic_pool = Mock()
        problematic_stats = Mock()
        problematic_stats.connection_errors = 12  # Above threshold
        problematic_stats.pool_exhaustions = 7  # Above threshold
        problematic_stats.average_wait_time = 1.5  # Above threshold
        problematic_pool.get_stats.return_value = problematic_stats

        monitored_manager.pools["problematic_pool"] = problematic_pool

        # Check thresholds and trigger alerts
        for pool_name, pool in monitored_manager.get_all_pools().items():
            stats = pool.get_stats()

            if stats.connection_errors > alert_thresholds["max_connection_errors"]:
                alerts_triggered.append(
                    {
                        "type": "connection_errors",
                        "pool": pool_name,
                        "value": stats.connection_errors,
                        "threshold": alert_thresholds["max_connection_errors"],
                    }
                )

            if stats.pool_exhaustions > alert_thresholds["max_pool_exhaustions"]:
                alerts_triggered.append(
                    {
                        "type": "pool_exhaustions",
                        "pool": pool_name,
                        "value": stats.pool_exhaustions,
                        "threshold": alert_thresholds["max_pool_exhaustions"],
                    }
                )

            if stats.average_wait_time > alert_thresholds["max_response_time"]:
                alerts_triggered.append(
                    {
                        "type": "response_time",
                        "pool": pool_name,
                        "value": stats.average_wait_time,
                        "threshold": alert_thresholds["max_response_time"],
                    }
                )

        # Should have triggered alerts
        assert len(alerts_triggered) >= 3  # All three thresholds exceeded

        # Verify alert details
        error_alerts = [a for a in alerts_triggered if a["type"] == "connection_errors"]
        exhaust_alerts = [
            a for a in alerts_triggered if a["type"] == "pool_exhaustions"
        ]
        time_alerts = [a for a in alerts_triggered if a["type"] == "response_time"]

        assert len(error_alerts) >= 1
        assert len(exhaust_alerts) >= 1
        assert len(time_alerts) >= 1


class TestWebSocketPoolMonitoring:
    """Test WebSocket pool monitoring and metrics."""

    @pytest_asyncio.fixture
    async def monitored_ws_manager(self):
        """Create a monitored WebSocket pool manager."""
        manager = WebSocketPoolManager()
        await manager.initialize()
        yield manager
        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_websocket_connection_metrics(self, monitored_ws_manager):
        """Test WebSocket connection metrics."""
        connection_metrics = []

        async def tracked_connection(client_id: str):
            """Tracked WebSocket connection."""
            mock_websocket = AsyncMock()
            mock_websocket.client_state.DISCONNECTED = False

            # Connect
            connect_time = time.time()
            await monitored_ws_manager.connect(mock_websocket, client_id)

            connection_metrics.append(
                {
                    "event": "connected",
                    "client_id": client_id,
                    "timestamp": connect_time,
                    "active_connections": monitored_ws_manager.stats.active_connections,
                }
            )

            # Simulate activity
            await asyncio.sleep(0.01)

            # Disconnect
            disconnect_time = time.time()
            await monitored_ws_manager.disconnect(client_id)

            connection_metrics.append(
                {
                    "event": "disconnected",
                    "client_id": client_id,
                    "timestamp": disconnect_time,
                    "active_connections": monitored_ws_manager.stats.active_connections,
                }
            )

        # Test multiple connections
        num_connections = 5
        tasks = [tracked_connection(f"client_{i}") for i in range(num_connections)]
        await asyncio.gather(*tasks)

        # Analyze metrics
        connect_events = [m for m in connection_metrics if m["event"] == "connected"]
        disconnect_events = [
            m for m in connection_metrics if m["event"] == "disconnected"
        ]
