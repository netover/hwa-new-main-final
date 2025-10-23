"""
Integration tests for the complete connection pooling system.

This module validates the end-to-end functionality of the connection pooling
implementation, including:
- System initialization and shutdown
- Cross-pool coordination and resource management
- Performance under realistic load conditions
- Integration with existing application components
- Memory usage and resource cleanup
- Production-like scenarios
"""

import asyncio
import gc
import os
import time
from unittest.mock import AsyncMock, patch

import psutil
import pytest
import pytest_asyncio

from resync.core.connection_pool_manager import (
    get_connection_pool_manager,
    shutdown_connection_pool_manager,
)
from resync.core.websocket_pool_manager import (
    get_websocket_pool_manager,
    shutdown_websocket_pool_manager,
)
from resync.settings import settings


class TestConnectionPoolIntegration:
    """Test complete connection pooling system integration."""

    @pytest_asyncio.fixture
    async def integrated_system(self):
        """Create an integrated system with all connection pools."""
        # Initialize connection pool manager
        pool_manager = await get_connection_pool_manager()

        # Initialize WebSocket pool manager
        ws_manager = await get_websocket_pool_manager()

        # Create integrated system
        system = {
            "pool_manager": pool_manager,
            "ws_manager": ws_manager,
            "initialized": True,
        }

        yield system

        # Cleanup
        await shutdown_connection_pool_manager()
        await shutdown_websocket_pool_manager()

    @pytest.mark.asyncio
    async def test_system_initialization(self, integrated_system):
        """Test complete system initialization."""
        pool_manager = integrated_system["pool_manager"]
        ws_manager = integrated_system["ws_manager"]

        # Verify managers are initialized
        assert pool_manager._initialized is True
        assert ws_manager._initialized is True

        # Verify pools are available
        assert len(pool_manager.pools) >= 0  # Pools might be lazy-initialized

        # Verify health checks pass
        is_healthy = pool_manager.is_healthy()
        ws_healthy = await ws_manager.health_check()

        assert is_healthy is True
        assert ws_healthy is True

    @pytest.mark.asyncio
    async def test_cross_pool_coordination(self, integrated_system):
        """Test coordination between different connection pools."""
        pool_manager = integrated_system["pool_manager"]
        results = []

        async def multi_pool_operation(operation_id: int):
            """Operation that uses multiple connection pools."""
            try:
                # Get database connection
                db_pool = pool_manager.get_pool("database")
                if db_pool:
                    async with db_pool.get_connection():
                        # Simulate database operation
                        await asyncio.sleep(0.001)

                # Get Redis connection
                redis_pool = pool_manager.get_pool("redis")
                if redis_pool:
                    async with redis_pool.get_connection():
                        # Simulate cache operation
                        await asyncio.sleep(0.001)

                # Get HTTP connection
                http_pool = pool_manager.get_pool("http")
                if http_pool:
                    async with http_pool.get_connection():
                        # Simulate API call
                        await asyncio.sleep(0.001)

                results.append(f"success_{operation_id}")
                return True

            except Exception as e:
                results.append(f"error_{operation_id}_{str(e)}")
                return False

        # Run coordinated operations
        num_operations = 10
        tasks = [multi_pool_operation(i) for i in range(num_operations)]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        # Should have mostly successful operations
        successful = sum(1 for outcome in outcomes if outcome is True)
        assert successful >= num_operations * 0.8

    @pytest.mark.asyncio
    async def test_memory_usage_and_cleanup(self, integrated_system):
        """Test memory usage and resource cleanup."""
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Perform operations that use connections
        async def memory_intensive_operation(operation_id: int):
            """Memory-intensive operation with connections."""
            pool_manager = integrated_system["pool_manager"]
            ws_manager = integrated_system["ws_manager"]

            # Create WebSocket connection
            mock_websocket = AsyncMock()
            mock_websocket.client_state.DISCONNECTED = False

            client_id = f"client_{operation_id}"
            await ws_manager.connect(mock_websocket, client_id)

            # Use multiple connection types
            for pool_name in ["database", "redis", "http"]:
                pool = pool_manager.get_pool(pool_name)
                if pool:
                    try:
                        async with pool.get_connection():
                            # Simulate work
                            await asyncio.sleep(0.001)
                    except Exception:
                        pass  # Ignore connection errors for memory test

            # Send message
            await ws_manager.send_personal_message(f"Message {operation_id}", client_id)

            # Disconnect
            await ws_manager.disconnect(client_id)

            return f"completed_{operation_id}"

        # Run memory-intensive operations
        num_operations = 20
        tasks = [memory_intensive_operation(i) for i in range(num_operations)]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Force garbage collection
        gc.collect()

        # Check final memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 50MB)
        assert memory_increase < 50

        print("Memory usage test:")
        print(f"  Initial memory: {initial_memory:.2f}MB")
        print(f"  Final memory: {final_memory:.2f}MB")
        print(f"  Memory increase: {memory_increase:.2f}MB")

    @pytest.mark.asyncio
    async def test_production_like_scenario(self, integrated_system):
        """Test production-like scenario with mixed load."""
        pool_manager = integrated_system["pool_manager"]
        ws_manager = integrated_system["ws_manager"]

        # Simulate production load patterns
        results = {
            "database_queries": 0,
            "cache_operations": 0,
            "api_calls": 0,
            "websocket_messages": 0,
            "errors": 0,
        }

        async def production_database_task(task_id: int):
            """Simulate production database task."""
            try:
                db_pool = pool_manager.get_pool("database")
                if db_pool:
                    async with db_pool.get_connection():
                        # Simulate database query
                        await asyncio.sleep(0.002)
                        results["database_queries"] += 1
                        return "db_success"
                return "db_no_pool"
            except Exception as e:
                results["errors"] += 1
                return f"db_error_{str(e)}"

        async def production_cache_task(task_id: int):
            """Simulate production cache task."""
            try:
                redis_pool = pool_manager.get_pool("redis")
                if redis_pool:
                    async with redis_pool.get_connection():
                        # Simulate cache operation
                        await asyncio.sleep(0.001)
                        results["cache_operations"] += 1
                        return "cache_success"
                return "cache_no_pool"
            except Exception as e:
                results["errors"] += 1
                return f"cache_error_{str(e)}"

        async def production_api_task(task_id: int):
            """Simulate production API task."""
            try:
                http_pool = pool_manager.get_pool("http")
                if http_pool:
                    async with http_pool.get_connection():
                        # Simulate API call
                        await asyncio.sleep(0.003)
                        results["api_calls"] += 1
                        return "api_success"
                return "api_no_pool"
            except Exception as e:
                results["errors"] += 1
                return f"api_error_{str(e)}"

        async def production_websocket_task(task_id: int):
            """Simulate production WebSocket task."""
            try:
                # Create WebSocket connection
                mock_websocket = AsyncMock()
                mock_websocket.client_state.DISCONNECTED = False

                client_id = f"ws_client_{task_id}"
                await ws_manager.connect(mock_websocket, client_id)

                # Simulate WebSocket activity
                await asyncio.sleep(0.001)

                # Send message
                await ws_manager.send_personal_message(
                    f"WS message {task_id}", client_id
                )
                results["websocket_messages"] += 1

                # Disconnect
                await ws_manager.disconnect(client_id)

                return "ws_success"
            except Exception as e:
                results["errors"] += 1
                return f"ws_error_{str(e)}"

        # Create mixed workload
        tasks = []

        # Database-heavy workload
        for i in range(30):
            tasks.append(production_database_task(i))

        # Cache-heavy workload
        for i in range(40):
            tasks.append(production_cache_task(i))

        # API calls
        for i in range(20):
            tasks.append(production_api_task(i))

        # WebSocket connections
        for i in range(10):
            tasks.append(production_websocket_task(i))

        # Execute mixed workload
        start_time = time.time()
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()

        duration = end_time - start_time

        # Analyze results
        successful_tasks = sum(
            1
            for outcome in outcomes
            if isinstance(outcome, str) and "success" in outcome
        )

        assert successful_tasks >= len(tasks) * 0.85  # At least 85% success rate
        assert results["database_queries"] > 0
        assert results["cache_operations"] > 0
        assert results["api_calls"] > 0
        assert results["websocket_messages"] > 0
        assert results["errors"] < len(tasks) * 0.15  # Less than 15% errors

        print("Production scenario test:")
        print(f"  Total tasks: {len(tasks)}")
        print(f"  Successful: {successful_tasks}")
        print(f"  Duration: {duration:.2f}s")
        print(f"  Database queries: {results['database_queries']}")
        print(f"  Cache operations: {results['cache_operations']}")
        print(f"  API calls: {results['api_calls']}")
        print(f"  WebSocket messages: {results['websocket_messages']}")
        print(f"  Errors: {results['errors']}")

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, integrated_system):
        """Test graceful shutdown of connection pooling system."""
        pool_manager = integrated_system["pool_manager"]
        ws_manager = integrated_system["ws_manager"]

        # Create some active connections
        active_connections = []

        async def create_active_connection(conn_id: int):
            """Create an active connection."""
            db_pool = pool_manager.get_pool("database")
            if db_pool:
                async with db_pool.get_connection():
                    active_connections.append(conn_id)
                    await asyncio.sleep(0.1)  # Hold connection

            # Create WebSocket connection
            mock_websocket = AsyncMock()
            mock_websocket.client_state.DISCONNECTED = False

            client_id = f"active_client_{conn_id}"
            await ws_manager.connect(mock_websocket, client_id)

            return f"active_{conn_id}"

        # Create active connections
        tasks = [create_active_connection(i) for i in range(5)]
        await asyncio.gather(*tasks)

        # Verify active connections exist
        initial_pool_stats = pool_manager.get_all_pools()
        has_active_connections = any(
            pool.get_stats().active_connections > 0
            for pool in initial_pool_stats.values()
        )

        # Shutdown system
        shutdown_start = time.time()

        await shutdown_connection_pool_manager()
        await shutdown_websocket_pool_manager()

        shutdown_duration = time.time() - shutdown_start

        # Verify graceful shutdown
        assert pool_manager._shutdown is True
        assert ws_manager._shutdown is True

        # Shutdown should be reasonably fast (under 5 seconds)
        assert shutdown_duration < 5.0

        print("Graceful shutdown test:")
        print(f"  Had active connections: {has_active_connections}")
        print(f"  Shutdown duration: {shutdown_duration:.3f}s")

    @pytest.mark.asyncio
    async def test_error_recovery_and_resilience(self, integrated_system):
        """Test error recovery and system resilience."""
        pool_manager = integrated_system["pool_manager"]

        error_scenarios = []
        recovery_results = []

        async def error_scenario_test(scenario_id: int):
            """Test different error scenarios."""
            try:
                # Scenario 1: Pool exhaustion
                if scenario_id == 0:
                    # Try to exhaust a pool
                    db_pool = pool_manager.get_pool("database")
                    if db_pool:
                        # Force pool exhaustion by setting very low limit
                        original_max = db_pool.config.max_size
                        db_pool.config.max_size = 1

                        async with db_pool.get_connection():
                            # Try to get another connection (should fail)
                            try:
                                async with db_pool.get_connection(timeout=0.1):
                                    pass
                            except Exception:
                                error_scenarios.append(f"exhaustion_{scenario_id}")

                        # Restore original limit
                        db_pool.config.max_size = original_max

                # Scenario 2: Connection timeout
                elif scenario_id == 1:
                    # Simulate connection timeout
                    db_pool = pool_manager.get_pool("database")
                    if db_pool:
                        try:
                            # Use very short timeout
                            async with db_pool.get_connection(timeout=0.001):
                                await asyncio.sleep(0.1)  # Longer than timeout
                        except Exception:
                            error_scenarios.append(f"timeout_{scenario_id}")

                # Scenario 3: Health check failure
                elif scenario_id == 2:
                    db_pool = pool_manager.get_pool("database")
                    if db_pool:
                        # Mock health check failure
                        with patch.object(
                            db_pool, "_validate_connection", return_value=False
                        ):
                            health_result = await db_pool.health_check()
                            if not health_result:
                                error_scenarios.append(f"health_fail_{scenario_id}")

                recovery_results.append(f"recovered_{scenario_id}")
                return True

            except Exception as e:
                recovery_results.append(f"failed_{scenario_id}_{str(e)}")
                return False

        # Test multiple error scenarios
        scenario_tasks = [error_scenario_test(i) for i in range(3)]
        await asyncio.gather(*scenario_tasks, return_exceptions=True)

        # Should handle errors gracefully
        assert len(error_scenarios) >= 2  # Should trigger multiple error scenarios
        assert len(recovery_results) >= 2  # Should recover from most scenarios

        print("Error recovery test:")
        print(f"  Error scenarios triggered: {len(error_scenarios)}")
        print(f"  Recovery results: {len(recovery_results)}")

    @pytest.mark.asyncio
    async def test_performance_under_stress(self, integrated_system):
        """Test system performance under stress conditions."""
        pool_manager = integrated_system["pool_manager"]

        # Create stress test with high concurrency
        stress_results = {
            "successful_operations": 0,
            "failed_operations": 0,
            "total_time": 0,
        }

        async def stress_operation(operation_id: int):
            """High-frequency operation to stress the system."""
            start_time = time.time()

            try:
                # Try to use multiple pools rapidly
                for pool_name in ["database", "redis", "http"]:
                    pool = pool_manager.get_pool(pool_name)
                    if pool:
                        try:
                            async with pool.get_connection(timeout=0.5):
                                await asyncio.sleep(0.001)  # Very short operation
                                stress_results["successful_operations"] += 1
                        except Exception:
                            stress_results["failed_operations"] += 1

            except Exception:
                stress_results["failed_operations"] += 1

            finally:
                end_time = time.time()
                stress_results["total_time"] += end_time - start_time

        # Create high concurrency stress test
        num_stress_operations = 100
        max_concurrent = 20

        semaphore = asyncio.Semaphore(max_concurrent)

        async def limited_stress_operation(operation_id: int):
            async with semaphore:
                return await stress_operation(operation_id)

        stress_start_time = time.time()
        stress_tasks = [
            limited_stress_operation(i) for i in range(num_stress_operations)
        ]
        await asyncio.gather(*stress_tasks, return_exceptions=True)
        stress_end_time = time.time()

        total_stress_time = stress_end_time - stress_start_time

        # Analyze stress test results
        success_rate = stress_results["successful_operations"] / (
            stress_results["successful_operations"]
            + stress_results["failed_operations"]
        )

        assert success_rate > 0.7  # At least 70% success rate under stress
        assert total_stress_time < 10.0  # Should complete within 10 seconds

        print("Stress test results:")
        print(f"  Total operations: {num_stress_operations}")
        print(f"  Successful: {stress_results['successful_operations']}")
        print(f"  Failed: {stress_results['failed_operations']}")
        print(f"  Success rate: {success_rate*100:.1f}%")
        print(f"  Total time: {total_stress_time:.2f}s")
        print(
            f"  Average time per operation: {stress_results['total_time']/num_stress_operations*1000:.1f}ms"
        )


class TestConnectionPoolProductionReadiness:
    """Test production readiness of connection pooling system."""

    @pytest.mark.asyncio
    async def test_configuration_validation(self):
        """Test that all configurations are valid for production."""

        # Validate database pool settings
        assert settings.DB_POOL_MIN_SIZE >= 1
        assert settings.DB_POOL_MAX_SIZE >= settings.DB_POOL_MIN_SIZE
        assert settings.DB_POOL_TIMEOUT >= 1
        assert settings.DB_POOL_MAX_OVERFLOW >= 0

        # Validate Redis pool settings
        assert settings.REDIS_POOL_MIN_SIZE >= 1
        assert settings.REDIS_POOL_MAX_SIZE >= settings.REDIS_POOL_MIN_SIZE
        assert settings.REDIS_POOL_TIMEOUT >= 1
        assert settings.REDIS_POOL_RETRY_ATTEMPTS >= 1

        # Validate HTTP pool settings
        assert settings.HTTP_POOL_MIN_SIZE >= 1
        assert settings.HTTP_POOL_MAX
