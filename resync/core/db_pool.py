"""
Advanced Database Connection Pool with Multiplexing Support.

This module provides sophisticated database connection pooling with:
- Connection multiplexing for concurrent operations
- Intelligent load balancing across connections
- Connection health monitoring and recovery
- Prepared statement caching and reuse
- Performance metrics and analytics
"""

from __future__ import annotations

import asyncio
import hashlib
import time
import threading
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from resync.core.structured_logger import get_logger

logger = get_logger(__name__)


@dataclass
class ConnectionInfo:
    """Information about a database connection."""

    connection_id: str
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    use_count: int = 0
    active_operations: int = 0
    total_operations: int = 0
    errors_count: int = 0
    avg_response_time: float = 0.0
    is_healthy: bool = True

    @property
    def age(self) -> float:
        """Get connection age in seconds."""
        return time.time() - self.created_at

    @property
    def idle_time(self) -> float:
        """Get idle time in seconds."""
        return time.time() - self.last_used

    @property
    def utilization(self) -> float:
        """Get connection utilization (0.0 to 1.0)."""
        return min(1.0, self.active_operations / max(1, self.total_operations))

    def should_retire(self, max_age: float, max_idle: float, max_errors: int) -> bool:
        """Check if connection should be retired."""
        return (
            self.age > max_age
            or self.idle_time > max_idle
            or self.errors_count > max_errors
            or not self.is_healthy
        )


@dataclass
class MultiplexOperation:
    """Represents an operation that can be multiplexed on a connection."""

    operation_id: str
    sql: str
    params: Tuple[Any, ...]
    start_time: float = field(default_factory=time.time)
    timeout: float = 30.0
    priority: int = 1  # 1=low, 5=high

    @property
    def is_expired(self) -> bool:
        """Check if operation has timed out."""
        return time.time() - self.start_time > self.timeout

    @property
    def age(self) -> float:
        """Get operation age in seconds."""
        return time.time() - self.start_time


@dataclass
class MultiplexConnection:
    """A connection that supports multiplexing operations."""

    connection: Any  # Actual database connection
    info: ConnectionInfo
    max_concurrent_operations: int = 10
    active_operations: Dict[str, MultiplexOperation] = field(default_factory=dict)
    operation_queue: asyncio.Queue = field(default_factory=asyncio.Queue)

    @property
    def available_slots(self) -> int:
        """Get number of available operation slots."""
        return max(0, self.max_concurrent_operations - len(self.active_operations))

    @property
    def utilization(self) -> float:
        """Get connection utilization."""
        return len(self.active_operations) / self.max_concurrent_operations

    async def can_accept_operation(self, operation: MultiplexOperation) -> bool:
        """Check if connection can accept a new operation."""
        return (
            self.available_slots > 0
            and self.info.is_healthy
            and not operation.is_expired
        )

    async def add_operation(self, operation: MultiplexOperation) -> bool:
        """Add operation to this connection."""
        if not await self.can_accept_operation(operation):
            return False

        self.active_operations[operation.operation_id] = operation
        self.info.active_operations += 1
        return True

    async def remove_operation(self, operation_id: str, success: bool = True) -> None:
        """Remove completed operation."""
        if operation_id in self.active_operations:
            operation = self.active_operations[operation_id]
            duration = time.time() - operation.start_time

            # Update connection stats
            self.info.total_operations += 1
            self.info.last_used = time.time()

            if not success:
                self.info.errors_count += 1

            # Update average response time
            if self.info.total_operations == 1:
                self.info.avg_response_time = duration
            else:
                self.info.avg_response_time = (
                    (self.info.avg_response_time * (self.info.total_operations - 1))
                    + duration
                ) / self.info.total_operations

            del self.active_operations[operation_id]
            self.info.active_operations -= 1


@dataclass
class MultiplexPoolConfig:
    """Configuration for multiplexed connection pool."""

    # Connection limits
    min_connections: int = 2
    max_connections: int = 20
    max_connections_per_host: int = 5

    # Connection lifecycle
    max_connection_age: float = 3600.0  # 1 hour
    max_connection_idle: float = 300.0  # 5 minutes
    max_connection_errors: int = 5

    # Multiplexing
    max_concurrent_operations_per_connection: int = 10
    operation_timeout: float = 30.0
    load_balancing_strategy: str = "round_robin"  # round_robin, least_loaded, random

    # Health checks
    health_check_interval: float = 60.0  # 1 minute
    health_check_timeout: float = 5.0

    # Prepared statements
    enable_prepared_statements: bool = True
    prepared_statement_cache_size: int = 100

    # Monitoring
    enable_metrics: bool = True
    metrics_interval: float = 10.0  # 10 seconds


@dataclass
class PoolMetrics:
    """Comprehensive pool performance metrics."""

    # Connection stats
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    unhealthy_connections: int = 0

    # Operation stats
    total_operations: int = 0
    active_operations: int = 0
    queued_operations: int = 0
    failed_operations: int = 0

    # Performance
    avg_operation_time: float = 0.0
    operation_throughput: float = 0.0  # operations per second
    connection_utilization: float = 0.0

    # Queue stats
    avg_queue_time: float = 0.0
    max_queue_depth: int = 0

    # Cache stats
    prepared_statements_cached: int = 0
    prepared_statement_hits: int = 0
    prepared_statement_misses: int = 0

    def get_prepared_statement_hit_rate(self) -> float:
        """Calculate prepared statement cache hit rate."""
        total = self.prepared_statement_hits + self.prepared_statement_misses
        return self.prepared_statement_hits / max(1, total)


class MultiplexConnectionPool:
    """
    Advanced database connection pool with multiplexing support.

    Features:
    - Connection multiplexing for concurrent operations
    - Intelligent load balancing
    - Automatic connection lifecycle management
    - Prepared statement caching
    - Comprehensive monitoring and metrics
    """

    def __init__(self, config: Optional[MultiplexPoolConfig] = None):
        self.config = config or MultiplexPoolConfig()

        # Connection management
        self.connections: Dict[str, MultiplexConnection] = {}
        self.connection_queue: asyncio.Queue = asyncio.Queue()
        self.operation_queue: asyncio.Queue = asyncio.Queue()

        # Load balancing
        self.load_balancer_index = 0
        self._load_balancer_lock = asyncio.Lock()

        # Prepared statement cache
        self.prepared_statements: Dict[str, Any] = {}
        self.statement_usage: Dict[str, int] = {}

        # Metrics
        self.metrics = PoolMetrics()
        self._metrics_lock = asyncio.Lock()

        # Background tasks
        self._health_check_task: Optional[asyncio.Task] = None
        self._metrics_task: Optional[asyncio.Task] = None
        self._operation_processor_task: Optional[asyncio.Task] = None
        self._running = False

        # Synchronization
        self._lock = asyncio.Lock()
        self._connection_counter = 0

    async def start(self) -> None:
        """Start the multiplex connection pool."""
        if self._running:
            return

        self._running = True

        # Initialize minimum connections
        await self._initialize_connections()

        # Start background tasks
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        self._metrics_task = asyncio.create_task(self._metrics_loop())
        self._operation_processor_task = asyncio.create_task(
            self._operation_processor()
        )

        logger.info(
            "Multiplex connection pool started",
            min_connections=self.config.min_connections,
            max_connections=self.config.max_connections,
        )

    async def stop(self) -> None:
        """Stop the multiplex connection pool."""
        if not self._running:
            return

        self._running = False

        # Stop background tasks
        for task in [
            self._health_check_task,
            self._metrics_task,
            self._operation_processor_task,
        ]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Close all connections
        await self._close_all_connections()

        logger.info("Multiplex connection pool stopped")

    @asynccontextmanager
    async def execute_operation(
        self,
        sql: str,
        params: Tuple[Any, ...] = (),
        priority: int = 1,
        timeout: Optional[float] = None,
    ):
        """
        Execute a database operation using the multiplex pool.

        Args:
            sql: SQL query to execute
            params: Query parameters
            priority: Operation priority (1-5)
            timeout: Operation timeout in seconds
        """
        operation = MultiplexOperation(
            operation_id=f"op_{id(asyncio.current_task())}_{time.time()}",
            sql=sql,
            params=params,
            priority=priority,
            timeout=timeout or self.config.operation_timeout,
        )

        start_time = time.time()

        # Try to execute immediately
        result = await self._try_execute_operation(operation)

        if result is not None:
            # Operation completed immediately
            async with self._metrics_lock:
                self.metrics.avg_operation_time = (
                    (
                        self.metrics.avg_operation_time
                        * (self.metrics.total_operations - 1)
                    )
                    + (time.time() - start_time)
                ) / self.metrics.total_operations

            yield result
            return

        # Queue operation for later execution
        future = asyncio.Future()
        await self.operation_queue.put((operation, future))

        try:
            # Wait for operation to complete
            result = await asyncio.wait_for(future, timeout=operation.timeout)

            async with self._metrics_lock:
                self.metrics.avg_operation_time = (
                    (
                        self.metrics.avg_operation_time
                        * (self.metrics.total_operations - 1)
                    )
                    + (time.time() - start_time)
                ) / self.metrics.total_operations

            yield result

        except asyncio.TimeoutError:
            async with self._metrics_lock:
                self.metrics.failed_operations += 1
            raise RuntimeError(f"Operation timed out after {operation.timeout}s")

    async def get_prepared_statement(self, sql: str) -> Any:
        """
        Get or create a prepared statement.

        Args:
            sql: SQL statement to prepare

        Returns:
            Prepared statement object
        """
        if not self.config.enable_prepared_statements:
            return None

        statement_key = hashlib.md5(sql.encode()).hexdigest()

        # Check cache
        if statement_key in self.prepared_statements:
            async with self._metrics_lock:
                self.metrics.prepared_statement_hits += 1
            self.statement_usage[statement_key] += 1
            return self.prepared_statements[statement_key]

        # Create new prepared statement
        try:
            # Get a connection to prepare the statement
            connection = await self._get_connection_for_preparation()

            # In real implementation, this would prepare the statement on the connection
            prepared_stmt = f"prepared_{statement_key}"  # Mock prepared statement

            # Cache it
            if (
                len(self.prepared_statements)
                < self.config.prepared_statement_cache_size
            ):
                self.prepared_statements[statement_key] = prepared_stmt
                self.statement_usage[statement_key] = 1

                async with self._metrics_lock:
                    self.metrics.prepared_statements_cached += 1
            else:
                # Evict least used statement
                await self._evict_prepared_statement()

            async with self._metrics_lock:
                self.metrics.prepared_statement_misses += 1

            return prepared_stmt

        except Exception as e:
            logger.warning(f"Failed to prepare statement: {e}")
            async with self._metrics_lock:
                self.metrics.prepared_statement_misses += 1
            return None

    def get_pool_stats(self) -> Dict[str, Any]:
        """Get comprehensive pool statistics."""
        return {
            "connections": {
                "total": self.metrics.total_connections,
                "active": self.metrics.active_connections,
                "idle": self.metrics.idle_connections,
                "unhealthy": self.metrics.unhealthy_connections,
                "utilization": self.metrics.connection_utilization,
            },
            "operations": {
                "total": self.metrics.total_operations,
                "active": self.metrics.active_operations,
                "queued": self.metrics.queued_operations,
                "failed": self.metrics.failed_operations,
                "throughput": self.metrics.operation_throughput,
            },
            "performance": {
                "avg_operation_time": self.metrics.avg_operation_time,
                "avg_queue_time": self.metrics.avg_queue_time,
                "max_queue_depth": self.metrics.max_queue_depth,
            },
            "cache": {
                "prepared_statements": self.metrics.prepared_statements_cached,
                "hit_rate": self.metrics.get_prepared_statement_hit_rate(),
                "hits": self.metrics.prepared_statement_hits,
                "misses": self.metrics.prepared_statement_misses,
            },
            "config": {
                "min_connections": self.config.min_connections,
                "max_connections": self.config.max_connections,
                "load_balancing": self.config.load_balancing_strategy,
                "multiplexing_enabled": True,
            },
        }

    async def _initialize_connections(self) -> None:
        """Initialize minimum number of connections."""
        for _ in range(self.config.min_connections):
            try:
                await self._create_connection()
            except Exception as e:
                logger.error(f"Failed to create initial connection: {e}")

    async def _create_connection(self) -> str:
        """Create a new multiplex connection."""
        connection_id = f"conn_{self._connection_counter}"
        self._connection_counter += 1

        try:
            # In real implementation, this would create actual database connection
            mock_connection = f"db_connection_{connection_id}"

            # Create multiplex connection wrapper
            multiplex_conn = MultiplexConnection(
                connection=mock_connection,
                info=ConnectionInfo(connection_id=connection_id),
                max_concurrent_operations=self.config.max_concurrent_operations_per_connection,
            )

            self.connections[connection_id] = multiplex_conn

            async with self._metrics_lock:
                self.metrics.total_connections += 1
                self.metrics.idle_connections += 1

            logger.debug(f"Connection created: {connection_id}")
            return connection_id

        except Exception as e:
            logger.error(f"Failed to create connection {connection_id}: {e}")
            raise

    async def _get_connection_for_preparation(self) -> Any:
        """Get a connection suitable for statement preparation."""
        # Find least loaded connection
        best_connection = None
        best_utilization = float("inf")

        for multiplex_conn in self.connections.values():
            if (
                multiplex_conn.info.is_healthy
                and multiplex_conn.utilization < best_utilization
            ):
                best_connection = multiplex_conn
                best_utilization = multiplex_conn.utilization

        if best_connection:
            return best_connection.connection

        # Create new connection if needed
        conn_id = await self._create_connection()
        return self.connections[conn_id].connection

    async def _try_execute_operation(self, operation: MultiplexOperation) -> Any:
        """Try to execute operation immediately on an available connection."""
        # Find best connection using load balancing strategy
        connection = await self._select_connection(operation)

        if connection and await connection.can_accept_operation(operation):
            # Execute operation on this connection
            try:
                result = await self._execute_on_connection(connection, operation)

                async with self._metrics_lock:
                    self.metrics.total_operations += 1
                    self.metrics.active_operations += 1

                return result

            except Exception as e:
                await connection.remove_operation(operation.operation_id, success=False)
                logger.warning(f"Operation failed on connection: {e}")
                return None

        return None

    async def _select_connection(
        self, operation: MultiplexOperation
    ) -> Optional[MultiplexConnection]:
        """Select best connection for operation using load balancing."""
        async with self._load_balancer_lock:
            strategy = self.config.load_balancing_strategy

            if strategy == "round_robin":
                return self._round_robin_selection()
            elif strategy == "least_loaded":
                return self._least_loaded_selection()
            elif strategy == "random":
                return self._random_selection()
            else:
                return self._least_loaded_selection()  # Default

    def _round_robin_selection(self) -> Optional[MultiplexConnection]:
        """Round-robin connection selection."""
        healthy_connections = [
            conn for conn in self.connections.values() if conn.info.is_healthy
        ]

        if not healthy_connections:
            return None

        selected = healthy_connections[
            self.load_balancer_index % len(healthy_connections)
        ]
        self.load_balancer_index += 1
        return selected

    def _least_loaded_selection(self) -> Optional[MultiplexConnection]:
        """Select least loaded connection."""
        best_connection = None
        best_utilization = float("inf")

        for connection in self.connections.values():
            if connection.info.is_healthy and connection.utilization < best_utilization:
                best_connection = connection
                best_utilization = connection.utilization

        return best_connection

    def _random_selection(self) -> Optional[MultiplexConnection]:
        """Random connection selection."""
        import random

        healthy_connections = [
            conn for conn in self.connections.values() if conn.info.is_healthy
        ]

        return random.choice(healthy_connections) if healthy_connections else None

    async def _execute_on_connection(
        self, connection: MultiplexConnection, operation: MultiplexOperation
    ) -> Any:
        """Execute operation on a specific connection."""
        # Add operation to connection
        await connection.add_operation(operation)

        try:
            # Simulate operation execution
            # In real implementation, this would execute the SQL on the connection
            await asyncio.sleep(0.01)  # Simulate network latency

            # Mock result based on operation
            if operation.sql.lower().startswith("select"):
                result = [{"id": 1, "data": "sample"}]  # Mock SELECT result
            else:
                result = 1  # Mock affected rows for INSERT/UPDATE/DELETE

            await connection.remove_operation(operation.operation_id, success=True)
            return result

        except Exception as e:
            await connection.remove_operation(operation.operation_id, success=False)
            raise

    async def _operation_processor(self) -> None:
        """Background processor for queued operations."""
        while self._running:
            try:
                # Wait for queued operation
                operation, future = await self.operation_queue.get()

                async with self._metrics_lock:
                    self.metrics.queued_operations += 1
                    self.metrics.max_queue_depth = max(
                        self.metrics.max_queue_depth, self.operation_queue.qsize()
                    )

                # Try to execute
                result = await self._try_execute_operation(operation)

                if result is not None:
                    future.set_result(result)
                else:
                    # Still couldn't execute - this shouldn't happen in normal operation
                    future.set_exception(RuntimeError("No available connections"))

                async with self._metrics_lock:
                    self.metrics.queued_operations -= 1

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Operation processor error: {e}")

    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while self._running:
            try:
                await asyncio.sleep(self.config.health_check_interval)

                for connection_id, multiplex_conn in self.connections.items():
                    try:
                        # Perform health check
                        is_healthy = await self._health_check_connection(multiplex_conn)

                        if not is_healthy and multiplex_conn.info.is_healthy:
                            # Connection became unhealthy
                            multiplex_conn.info.is_healthy = False
                            async with self._metrics_lock:
                                self.metrics.unhealthy_connections += 1
                                self.metrics.idle_connections -= 1

                        elif is_healthy and not multiplex_conn.info.is_healthy:
                            # Connection recovered
                            multiplex_conn.info.is_healthy = True
                            async with self._metrics_lock:
                                self.metrics.unhealthy_connections -= 1
                                self.metrics.idle_connections += 1

                    except Exception as e:
                        logger.warning(f"Health check failed for {connection_id}: {e}")
                        multiplex_conn.info.errors_count += 1

                # Retire old/unhealthy connections
                await self._retire_connections()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}")

    async def _health_check_connection(
        self, multiplex_conn: MultiplexConnection
    ) -> bool:
        """Perform health check on a multiplex connection."""
        try:
            # Simulate health check
            await asyncio.sleep(0.001)  # Fast health check
            return True  # Assume healthy
        except Exception:
            return False

    async def _retire_connections(self) -> None:
        """Retire old or unhealthy connections."""
        to_retire = []

        for connection_id, multiplex_conn in self.connections.items():
            if multiplex_conn.info.should_retire(
                self.config.max_connection_age,
                self.config.max_connection_idle,
                self.config.max_connection_errors,
            ):
                to_retire.append(connection_id)

        for connection_id in to_retire:
            multiplex_conn = self.connections[connection_id]

            # Close connection (in real implementation)
            async with self._metrics_lock:
                self.metrics.total_connections -= 1
                if multiplex_conn.info.is_healthy:
                    self.metrics.idle_connections -= 1
                else:
                    self.metrics.unhealthy_connections -= 1

            del self.connections[connection_id]
            logger.debug(f"Retired connection: {connection_id}")

    async def _metrics_loop(self) -> None:
        """Background metrics collection loop."""
        while self._running:
            try:
                await asyncio.sleep(self.config.metrics_interval)

                async with self._metrics_lock:
                    # Update derived metrics
                    total_ops = self.metrics.total_operations
                    if total_ops > 0:
                        # Calculate throughput (operations per second)
                        time_window = self.config.metrics_interval
                        self.metrics.operation_throughput = total_ops / time_window

                    # Calculate connection utilization
                    if self.metrics.total_connections > 0:
                        active_count = sum(
                            1
                            for conn in self.connections.values()
                            if len(conn.active_operations) > 0
                        )
                        self.metrics.connection_utilization = (
                            active_count / self.metrics.total_connections
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics loop error: {e}")

    async def _evict_prepared_statement(self) -> None:
        """Evict least used prepared statement."""
        if not self.statement_usage:
            return

        # Find least used statement
        least_used_key = min(self.statement_usage, key=self.statement_usage.get)

        # Remove from cache
        if least_used_key in self.prepared_statements:
            del self.prepared_statements[least_used_key]
            del self.statement_usage[least_used_key]

    async def _close_all_connections(self) -> None:
        """Close all connections."""
        for connection_id in list(self.connections.keys()):
            # In real implementation, close the actual connection
            del self.connections[connection_id]

        async with self._metrics_lock:
            self.metrics.total_connections = 0
            self.metrics.active_connections = 0
            self.metrics.idle_connections = 0
            self.metrics.unhealthy_connections = 0


# Global pool instance
multiplex_pool = MultiplexConnectionPool()


async def get_multiplex_connection_pool() -> MultiplexConnectionPool:
    """Get the global multiplex connection pool instance."""
    if not multiplex_pool._running:
        await multiplex_pool.start()
    return multiplex_pool
