"""
ChuckNorris Connection Pool Optimizer

Advanced connection pool optimization with adaptive sizing, health monitoring,
and intelligent resource management for maximum performance.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections import deque, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import weakref
import statistics

logger = logging.getLogger(__name__)


class PoolState(Enum):
    """Connection pool states."""
    HEALTHY = "healthy"
    DEGRADING = "degrading"
    STRESSED = "stressed"
    RECOVERING = "recovering"
    FAILED = "failed"


class ConnectionHealth(Enum):
    """Health status of individual connections."""
    HEALTHY = "healthy"
    SLOW = "slow"
    ERROR_PRONE = "error_prone"
    DEAD = "dead"


@dataclass
class ConnectionMetrics:
    """Metrics for individual connections."""
    connection_id: str
    created_at: float
    last_used: float
    usage_count: int = 0
    error_count: int = 0
    total_response_time: float = 0.0
    last_error_time: float = 0.0
    health_status: ConnectionHealth = ConnectionHealth.HEALTHY
    is_active: bool = True
    
    @property
    def avg_response_time(self) -> float:
        """Calculate average response time."""
        return self.total_response_time / max(1, self.usage_count)
    
    @property
    def error_rate(self) -> float:
        """Calculate error rate."""
        return self.error_count / max(1, self.usage_count)
    
    @property
    def age_seconds(self) -> float:
        """Get connection age in seconds."""
        return time.time() - self.created_at
    
    @property
    def idle_time(self) -> float:
        """Get idle time in seconds."""
        return time.time() - self.last_used


@dataclass
class PoolMetrics:
    """Comprehensive metrics for connection pool."""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    failed_connections: int = 0
    
    # Performance metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    
    # Resource metrics
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    
    # Health metrics
    health_score: float = 1.0
    pool_state: PoolState = PoolState.HEALTHY
    
    # Response time history for percentile calculations
    response_times: deque = field(default_factory=lambda: deque(maxlen=1000))


@dataclass
class ChuckNorrisPoolConfig:
    """Configuration for ChuckNorris pool optimizer."""
    # Pool sizing
    min_size: int = 2
    max_size: int = 20
    initial_size: int = 5
    
    # Adaptive sizing
    adaptive_sizing_enabled: bool = True
    sizing_adjustment_interval: int = 60  # seconds
    scale_up_threshold: float = 0.8  # 80% utilization
    scale_down_threshold: float = 0.3  # 30% utilization
    scale_factor: float = 1.5
    
    # Health monitoring
    health_check_interval: int = 30  # seconds
    health_check_timeout: float = 5.0
    max_error_rate: float = 0.1  # 10% error rate
    max_response_time: float = 2.0  # 2 seconds
    
    # Connection lifecycle
    max_connection_age: int = 3600  # 1 hour
    max_idle_time: int = 300  # 5 minutes
    connection_timeout: float = 10.0
    
    # Performance optimization
    prefer_existing_connections: bool = True
    connection_warmup_enabled: bool = True
    batch_operations_enabled: bool = True
    batch_size: int = 10
    
    # Failure handling
    circuit_breaker_enabled: bool = True
    failure_threshold: int = 5
    recovery_timeout: int = 60
    half_open_max_calls: int = 3


class ChuckNorrisPoolOptimizer:
    """
    Advanced connection pool optimizer with ChuckNorris-level intelligence:
    
    1. Adaptive Pool Sizing based on real-time metrics
    2. Connection Health Monitoring and proactive replacement
    3. Performance-based Connection Selection
    4. Circuit Breaker Pattern Integration
    5. Resource Usage Optimization
    6. Predictive Scaling
    """
    
    def __init__(self, pool_name: str, config: ChuckNorrisPoolConfig | None = None):
        self.pool_name = pool_name
        self.config = config or ChuckNorrisPoolConfig()
        
        # Connection tracking
        self.connections: Dict[str, Tuple[Any, ConnectionMetrics]] = {}
        self.connection_lock = asyncio.Lock()
        
        # Performance tracking
        self.pool_metrics = PoolMetrics()
        self.metrics_history: deque[PoolMetrics] = deque(maxlen=100)
        
        # Circuit breaker state
        self.circuit_state = "closed"
        self.circuit_failure_count = 0
        self.circuit_last_failure_time = 0.0
        self.circuit_half_open_calls = 0
        
        # Background tasks
        self.health_check_task: Optional[asyncio.Task] = None
        self.sizing_task: Optional[asyncio.Task] = None
        self.running = False
        
        # Performance optimization
        self.fast_connections: List[str] = []  # Connections with good response times
        self.slow_connections: List[str] = []   # Connections to avoid
        self.connection_rankings: Dict[str, float] = {}
        
        # Predictive metrics
        self.request_history: deque[Tuple[float, float]] = deque(maxlen=100)
        self.prediction_window = 300  # 5 minutes
        
        logger.info(f"ChuckNorris pool optimizer initialized for {pool_name}")
    
    async def start(self) -> None:
        """Start pool optimizer background tasks."""
        if self.running:
            return
            
        self.running = True
        
        # Start background tasks
        self.health_check_task = asyncio.create_task(self._health_check_loop())
        self.sizing_task = asyncio.create_task(self._adaptive_sizing_loop())
        
        logger.info(f"ChuckNorris pool optimizer started for {self.pool_name}")
    
    async def stop(self) -> None:
        """Stop pool optimizer background tasks."""
        if not self.running:
            return
            
        self.running = False
        
        # Cancel background tasks
        if self.health_check_task:
            self.health_check_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.health_check_task
                
        if self.sizing_task:
            self.sizing_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.sizing_task
                
        logger.info(f"ChuckNorris pool optimizer stopped for {self.pool_name}")
    
    async def add_connection(self, connection: Any, connection_id: str | None = None) -> str:
        """Add a new connection to the pool."""
        if connection_id is None:
            connection_id = f"{self.pool_name}_{int(time.time() * 1000)}"
        
        async with self.connection_lock:
            if connection_id in self.connections:
                raise ValueError(f"Connection {connection_id} already exists")
            
            metrics = ConnectionMetrics(
                connection_id=connection_id,
                created_at=time.time(),
                last_used=time.time()
            )
            
            self.connections[connection_id] = (connection, metrics)
            
            # Warm up connection if enabled
            if self.config.connection_warmup_enabled:
                await self._warmup_connection(connection, connection_id)
            
            # Update connection rankings
            await self._update_connection_rankings()
            
            logger.debug(f"Added connection {connection_id} to pool {self.pool_name}")
            return connection_id
    
    async def get_connection(self, prefer_fast: bool = True) -> Tuple[Any, str]:
        """Get the best available connection from the pool."""
        async with self.connection_lock:
            # Check circuit breaker
            if self.config.circuit_breaker_enabled and not await self._can_make_request():
                raise ConnectionError("Circuit breaker is open")
            
            # Find best connection
            connection_id = await self._select_best_connection(prefer_fast)
            
            if connection_id is None:
                # No available connections, try to create one
                return await self._create_on_demand_connection()
            
            connection, metrics = self.connections[connection_id]
            metrics.last_used = time.time()
            metrics.usage_count += 1
            
            return connection, connection_id
    
    async def release_connection(self, connection_id: str, success: bool = True, 
                              response_time: float = 0.0) -> None:
        """Release a connection back to the pool."""
        async with self.connection_lock:
            if connection_id not in self.connections:
                logger.warning(f"Unknown connection {connection_id} released")
                return
            
            connection, metrics = self.connections[connection_id]
            
            # Update metrics
            metrics.total_response_time += response_time
            self.pool_metrics.total_requests += 1
            
            if success:
                metrics.last_used = time.time()
                self.pool_metrics.successful_requests += 1
            else:
                metrics.error_count += 1
                metrics.last_error_time = time.time()
                self.pool_metrics.failed_requests += 1
                
                # Update circuit breaker
                if self.config.circuit_breaker_enabled:
                    await self._record_failure()
            
            # Update response time history
            self.pool_metrics.response_times.append(response_time)
            
            # Update health status
            await self._update_connection_health(connection_id)
            
            # Update rankings
            await self._update_connection_rankings()
            
            # Record request for prediction
            self.request_history.append((time.time(), response_time))
    
    async def remove_connection(self, connection_id: str) -> None:
        """Remove a connection from the pool."""
        async with self.connection_lock:
            if connection_id not in self.connections:
                return
            
            connection, metrics = self.connections[connection_id]
            
            # Close connection if it has a close method
            if hasattr(connection, 'close'):
                try:
                    if asyncio.iscoroutinefunction(connection.close):
                        await connection.close()
                    else:
                        connection.close()
                except Exception as e:
                    logger.warning(f"Error closing connection {connection_id}: {e}")
            
            del self.connections[connection_id]
            
            # Update rankings
            await self._update_connection_rankings()
            
            logger.debug(f"Removed connection {connection_id} from pool {self.pool_name}")
    
    async def get_pool_metrics(self) -> PoolMetrics:
        """Get current pool metrics."""
        async with self.connection_lock:
            # Update basic counts
            self.pool_metrics.total_connections = len(self.connections)
            self.pool_metrics.active_connections = sum(
                1 for _, metrics in self.connections.values()
                if metrics.is_active
            )
            self.pool_metrics.idle_connections = (
                self.pool_metrics.total_connections - self.pool_metrics.active_connections
            )
            
            # Calculate performance metrics
            if self.pool_metrics.response_times:
                response_times = list(self.pool_metrics.response_times)
                self.pool_metrics.avg_response_time = statistics.mean(response_times)
                self.pool_metrics.p95_response_time = statistics.quantiles(
                    response_times, n=20
                )[18] if len(response_times) >= 20 else max(response_times)
                self.pool_metrics.p99_response_time = statistics.quantiles(
                    response_times, n=100
                )[98] if len(response_times) >= 100 else max(response_times)
            
            # Calculate health score
            await self._calculate_health_score()
            
            # Store in history
            self.metrics_history.append(self.pool_metrics)
            
            return self.pool_metrics
    
    async def _select_best_connection(self, prefer_fast: bool = True) -> Optional[str]:
        """Select the best available connection."""
        if not self.connections:
            return None
        
        # Filter active connections
        active_connections = [
            (conn_id, metrics) for conn_id, (_, metrics) in self.connections.items()
            if metrics.is_active and metrics.health_status != ConnectionHealth.DEAD
        ]
        
        if not active_connections:
            return None
        
        if prefer_fast and self.connection_rankings:
            # Select highest ranked connection
            best_id = max(
                active_connections,
                key=lambda x: self.connection_rankings.get(x[0], 0.0)
            )[0]
            return best_id
        else:
            # Select least recently used connection
            return min(active_connections, key=lambda x: x[1].last_used)[0]
    
    async def _create_on_demand_connection(self) -> Tuple[Any, str]:
        """Create a new connection on demand."""
        # This would be implemented by the specific pool type
        # For now, raise an error
        raise ConnectionError("No available connections and on-demand creation not implemented")
    
    async def _warmup_connection(self, connection: Any, connection_id: str) -> None:
        """Warm up a new connection."""
        try:
            # This would be implemented by the specific pool type
            # For example, a simple ping or test query
            if hasattr(connection, 'ping'):
                if asyncio.iscoroutinefunction(connection.ping):
                    await connection.ping()
                else:
                    connection.ping()
            
            logger.debug(f"Warmed up connection {connection_id}")
        except Exception as e:
            logger.warning(f"Failed to warm up connection {connection_id}: {e}")
    
    async def _update_connection_health(self, connection_id: str) -> None:
        """Update health status of a connection."""
        if connection_id not in self.connections:
            return
        
        _, metrics = self.connections[connection_id]
        
        # Determine health based on error rate and response time
        if metrics.error_rate > self.config.max_error_rate:
            metrics.health_status = ConnectionHealth.ERROR_PRONE
        elif metrics.avg_response_time > self.config.max_response_time:
            metrics.health_status = ConnectionHealth.SLOW
        elif metrics.age_seconds > self.config.max_connection_age:
            metrics.health_status = ConnectionHealth.DEAD
            metrics.is_active = False
        else:
            metrics.health_status = ConnectionHealth.HEALTHY
    
    async def _update_connection_rankings(self) -> None:
        """Update connection performance rankings."""
        self.connection_rankings.clear()
        self.fast_connections.clear()
        self.slow_connections.clear()
        
        for connection_id, (_, metrics) in self.connections.items():
            if not metrics.is_active:
                continue
            
            # Calculate ranking score (higher is better)
            if metrics.usage_count == 0:
                score = 1.0  # New connection gets neutral score
            else:
                # Score based on response time and error rate
                response_score = 1.0 / (1.0 + metrics.avg_response_time)
                error_score = 1.0 - metrics.error_rate
                usage_score = min(1.0, metrics.usage_count / 100.0)  # Favor used connections
                
                score = (response_score * 0.5 + error_score * 0.3 + usage_score * 0.2)
            
            self.connection_rankings[connection_id] = score
            
            # Categorize connections
            if metrics.health_status == ConnectionHealth.HEALTHY and score > 0.7:
                self.fast_connections.append(connection_id)
            elif metrics.health_status in [ConnectionHealth.SLOW, ConnectionHealth.ERROR_PRONE]:
                self.slow_connections.append(connection_id)
    
    async def _health_check_loop(self) -> None:
        """Background task to perform health checks."""
        while self.running:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._perform_health_checks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
    
    async def _perform_health_checks(self) -> None:
        """Perform health checks on all connections."""
        async with self.connection_lock:
            current_time = time.time()
            connections_to_remove = []
            
            for connection_id, (connection, metrics) in self.connections.items():
                # Check if connection is too old
                if metrics.age_seconds > self.config.max_connection_age:
                    connections_to_remove.append(connection_id)
                    continue
                
                # Check if connection has been idle too long
                if metrics.idle_time > self.config.max_idle_time:
                    connections_to_remove.append(connection_id)
                    continue
                
                # Perform health check
                try:
                    # This would be implemented by the specific pool type
                    if hasattr(connection, 'ping'):
                        if asyncio.iscoroutinefunction(connection.ping):
                            await asyncio.wait_for(
                                connection.ping(), 
                                timeout=self.config.health_check_timeout
                            )
                        else:
                            connection.ping()
                except Exception as e:
                    logger.warning(f"Health check failed for connection {connection_id}: {e}")
                    metrics.error_count += 1
                    metrics.last_error_time = current_time
                    
                    # Mark as dead if too many errors
                    if metrics.error_count > 5:
                        metrics.health_status = ConnectionHealth.DEAD
                        metrics.is_active = False
                        connections_to_remove.append(connection_id)
            
            # Remove dead connections
            for connection_id in connections_to_remove:
                await self.remove_connection(connection_id)
    
    async def _adaptive_sizing_loop(self) -> None:
        """Background task to handle adaptive pool sizing."""
        while self.running:
            try:
                await asyncio.sleep(self.config.sizing_adjustment_interval)
                await self._adjust_pool_size()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in adaptive sizing loop: {e}")
    
    async def _adjust_pool_size(self) -> None:
        """Adjust pool size based on current load."""
        if not self.config.adaptive_sizing_enabled:
            return
        
        await self.get_pool_metrics()  # Update metrics
        
        current_size = self.pool_metrics.total_connections
        utilization = (
            self.pool_metrics.active_connections / max(1, current_size)
        )
        
        # Scale up if under high load
        if utilization > self.config.scale_up_threshold:
            target_size = min(
                int(current_size * self.config.scale_factor),
                self.config.max_size
            )
            await self._scale_up(target_size - current_size)
        
        # Scale down if under low load
        elif utilization < self.config.scale_down_threshold:
            target_size = max(
                int(current_size / self.config.scale_factor),
                self.config.min_size
            )
            await self._scale_down(current_size - target_size)
    
    async def _scale_up(self, additional_connections: int) -> None:
        """Scale up pool by adding connections."""
        # This would be implemented by the specific pool type
        logger.info(f"Scaling up pool {self.pool_name} by {additional_connections} connections")
    
    async def _scale_down(self, connections_to_remove: int) -> None:
        """Scale down pool by removing connections."""
        async with self.connection_lock:
            # Remove least recently used idle connections
            idle_connections = sorted(
                [
                    (conn_id, metrics)
                    for conn_id, (_, metrics) in self.connections.items()
                    if metrics.is_active and metrics.idle_time > 60  # At least 1 minute idle
                ],
                key=lambda x: x[1].last_used
            )
            
            for i in range(min(connections_to_remove, len(idle_connections))):
                connection_id = idle_connections[i][0]
                await self.remove_connection(connection_id)
        
        logger.info(f"Scaled down pool {self.pool_name} by {connections_to_remove} connections")
    
    async def _can_make_request(self) -> bool:
        """Check if requests can be made (circuit breaker logic)."""
        current_time = time.time()
        
        if self.circuit_state == "closed":
            return True
        elif self.circuit_state == "open":
            if current_time - self.circuit_last_failure_time > self.config.recovery_timeout:
                self.circuit_state = "half_open"
                self.circuit_half_open_calls = 0
                return False
            return False
        elif self.circuit_state == "half_open":
            if self.circuit_half_open_calls >= self.config.half_open_max_calls:
                return False
            return True
        
        return False
    
    async def _record_failure(self) -> None:
        """Record a failure for circuit breaker."""
        current_time = time.time()
        
        if self.circuit_state == "closed":
            self.circuit_failure_count += 1
            if self.circuit_failure_count >= self.config.failure_threshold:
                self.circuit_state = "open"
                self.circuit_last_failure_time = current_time
                logger.warning(f"Circuit breaker opened for pool {self.pool_name}")
        
        elif self.circuit_state == "half_open":
            self.circuit_state = "open"
            self.circuit_last_failure_time = current_time
            logger.warning(f"Circuit breaker re-opened for pool {self.pool_name}")
    
    async def _calculate_health_score(self) -> None:
        """Calculate overall pool health score."""
        if self.pool_metrics.total_requests == 0:
            self.pool_metrics.health_score = 1.0
            self.pool_metrics.pool_state = PoolState.HEALTHY
            return
        
        # Calculate success rate
        success_rate = (
            self.pool_metrics.successful_requests / self.pool_metrics.total_requests
        )
        
        # Calculate response time score
        response_score = 1.0
        if self.pool_metrics.avg_response_time > 0:
            response_score = max(0.0, 1.0 - (self.pool_metrics.avg_response_time / self.config.max_response_time))
        
        # Calculate connection utilization score
        utilization_score = min(1.0, self.pool_metrics.active_connections / max(1, self.pool_metrics.total_connections))
        
        # Combine scores
        self.pool_metrics.health_score = (
            success_rate * 0.5 + response_score * 0.3 + utilization_score * 0.2
        )
        
        # Determine pool state
        if self.pool_metrics.health_score > 0.8:
            self.pool_metrics.pool_state = PoolState.HEALTHY
        elif self.pool_metrics.health_score > 0.6:
            self.pool_metrics.pool_state = PoolState.DEGRADING
        elif self.pool_metrics.health_score > 0.3:
            self.pool_metrics.pool_state = PoolState.STRESSED
        elif self.circuit_state == "open":
            self.pool_metrics.pool_state = PoolState.FAILED
        else:
            self.pool_metrics.pool_state = PoolState.RECOVERING
    
    async def get_optimization_report(self) -> Dict[str, Any]:
        """Get comprehensive optimization report."""
        await self.get_pool_metrics()
        
        return {
            'pool_name': self.pool_name,
            'pool_metrics': {
                'total_connections': self.pool_metrics.total_connections,
                'active_connections': self.pool_metrics.active_connections,
                'idle_connections': self.pool_metrics.idle_connections,
                'success_rate': (
                    self.pool_metrics.successful_requests / max(1, self.pool_metrics.total_requests)
                ),
                'avg_response_time': self.pool_metrics.avg_response_time,
                'p95_response_time': self.pool_metrics.p95_response_time,
                'p99_response_time': self.pool_metrics.p99_response_time,
                'health_score': self.pool_metrics.health_score,
                'pool_state': self.pool_metrics.pool_state.value,
            },
            'connection_health': {
                'healthy_connections': sum(
                    1 for _, (_, metrics) in self.connections.items()
                    if metrics.health_status == ConnectionHealth.HEALTHY
                ),
                'slow_connections': sum(
                    1 for _, (_, metrics) in self.connections.items()
                    if metrics.health_status == ConnectionHealth.SLOW
                ),
                'error_prone_connections': sum(
                    1 for _, (_, metrics) in self.connections.items()
                    if metrics.health_status == ConnectionHealth.ERROR_PRONE
                ),
                'dead_connections': sum(
                    1 for _, (_, metrics) in self.connections.items()
                    if metrics.health_status == ConnectionHealth.DEAD
                ),
            },
            'circuit_breaker': {
                'state': self.circuit_state,
                'failure_count': self.circuit_failure_count,
                'last_failure_time': self.circuit_last_failure_time,
            },
            'optimization_stats': {
                'fast_connections_count': len(self.fast_connections),
                'slow_connections_count': len(self.slow_connections),
                'connection_rankings_count': len(self.connection_rankings),
                'request_history_size': len(self.request_history),
            }
        }




