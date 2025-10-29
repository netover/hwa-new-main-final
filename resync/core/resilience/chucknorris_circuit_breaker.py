"""
ChuckNorris Circuit Breaker

Advanced circuit breaker implementation with dynamic thresholds,
machine learning-based predictions, and intelligent failure handling.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections import deque, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import statistics
import math

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states with enhanced granularity."""
    CLOSED = "closed"           # Normal operation
    OPEN = "open"               # Failing, reject calls
    HALF_OPEN = "half_open"      # Testing if recovered
    DEGRADED = "degraded"        # Slow but working
    ISOLATED = "isolated"        # Manually isolated


class FailureType(Enum):
    """Types of failures for intelligent handling."""
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    NETWORK_ERROR = "network_error"
    AUTHENTICATION_ERROR = "authentication_error"
    UNKNOWN = "unknown"


@dataclass
class FailureEvent:
    """Represents a single failure event."""
    timestamp: float
    failure_type: FailureType
    error_message: str
    response_time: float = 0.0
    retry_count: int = 0
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CircuitMetrics:
    """Comprehensive metrics for circuit breaker."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    
    # Failure type breakdown
    failure_counts: Dict[FailureType, int] = field(default_factory=lambda: defaultdict(int))
    
    # Response time metrics
    response_times: deque = field(default_factory=lambda: deque(maxlen=1000))
    avg_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    
    # State transitions
    state_changes: List[Tuple[float, CircuitState]] = field(default_factory=list)
    last_state_change: float = 0.0
    
    # Recovery metrics
    recovery_attempts: int = 0
    successful_recoveries: int = 0
    avg_recovery_time: float = 0.0


@dataclass
class ChuckNorrisCircuitConfig:
    """Configuration for ChuckNorris circuit breaker."""
    
    # Basic thresholds
    failure_threshold: int = 5
    success_threshold: int = 3
    timeout: float = 60.0
    half_open_max_calls: int = 5
    
    # Dynamic threshold adjustment
    adaptive_thresholds_enabled: bool = True
    threshold_adjustment_interval: int = 300  # 5 minutes
    min_failure_threshold: int = 2
    max_failure_threshold: int = 20
    threshold_sensitivity: float = 0.1  # 10% adjustment
    
    # Response time monitoring
    response_time_threshold: float = 2.0
    response_time_window: int = 100
    slow_call_ratio_threshold: float = 0.5  # 50% slow calls
    
    # Failure pattern analysis
    failure_pattern_window: int = 50
    failure_pattern_threshold: float = 0.7  # 70% similarity
    
    # Predictive features
    prediction_enabled: bool = True
    prediction_window: int = 200
    prediction_confidence_threshold: float = 0.8
    
    # Advanced features
    degradation_detection: bool = True
    isolation_mode_enabled: bool = True
    auto_recovery_enabled: bool = True
    recovery_strategy: str = "gradual"  # gradual, immediate, conservative


class ChuckNorrisCircuitBreaker:
    """
    Advanced circuit breaker with ChuckNorris-level intelligence:
    
    1. Dynamic Threshold Adjustment based on historical patterns
    2. Machine Learning-based Failure Prediction
    3. Response Time Monitoring and Degradation Detection
    4. Intelligent State Transition Logic
    5. Failure Pattern Analysis
    6. Adaptive Recovery Strategies
    """
    
    def __init__(self, name: str, config: ChuckNorrisCircuitConfig | None = None):
        self.name = name
        self.config = config or ChuckNorrisCircuitConfig()
        
        # State management
        self.state = CircuitState.CLOSED
        self.metrics = CircuitMetrics()
        self.metrics.last_state_change = time.time()
        
        # Failure tracking
        self.recent_failures: deque[FailureEvent] = deque(maxlen=self.config.failure_pattern_window)
        self.failure_lock = asyncio.Lock()
        
        # Dynamic thresholds
        self.current_failure_threshold = self.config.failure_threshold
        self.current_success_threshold = self.config.success_threshold
        self.current_timeout = self.config.timeout
        
        # Prediction model
        self.request_history: deque[Tuple[float, bool, float]] = deque(maxlen=self.config.prediction_window)
        self.prediction_accuracy = deque(maxlen=100)
        
        # Background tasks
        self.adaptation_task: Optional[asyncio.Task] = None
        self.running = False
        
        # Callbacks
        self.state_change_callbacks: List[Callable[[CircuitState, CircuitState], None]] = []
        self.failure_callbacks: List[Callable[[FailureEvent], None]] = []
        
        logger.info(f"ChuckNorris circuit breaker initialized for {name}")
    
    async def start(self) -> None:
        """Start circuit breaker background tasks."""
        if self.running:
            return
            
        self.running = True
        
        # Start adaptive threshold adjustment
        if self.config.adaptive_thresholds_enabled:
            self.adaptation_task = asyncio.create_task(self._adaptive_threshold_loop())
        
        logger.info(f"ChuckNorris circuit breaker started for {self.name}")
    
    async def stop(self) -> None:
        """Stop circuit breaker background tasks."""
        if not self.running:
            return
            
        self.running = False
        
        # Cancel background tasks
        if self.adaptation_task:
            self.adaptation_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.adaptation_task
        
        logger.info(f"ChuckNorris circuit breaker stopped for {self.name}")
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function through the circuit breaker."""
        start_time = time.time()
        
        # Check if call should be allowed
        if not await self._should_allow_request():
            raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is {self.state.value}")
        
        try:
            # Execute the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Record success
            response_time = time.time() - start_time
            await self._record_success(response_time)
            
            return result
            
        except Exception as e:
            # Record failure
            response_time = time.time() - start_time
            failure_type = self._classify_failure(e)
            await self._record_failure(response_time, failure_type, str(e))
            
            # Re-raise the exception
            raise
    
    async def force_open(self, reason: str = "Manual isolation") -> None:
        """Force the circuit breaker open."""
        await self._change_state(CircuitState.OPEN, reason)
        logger.warning(f"Circuit breaker {self.name} forced open: {reason}")
    
    async def force_close(self, reason: str = "Manual reset") -> None:
        """Force the circuit breaker closed."""
        await self._change_state(CircuitState.CLOSED, reason)
        logger.info(f"Circuit breaker {self.name} forced closed: {reason}")
    
    async def isolate(self, reason: str = "Manual isolation") -> None:
        """Isolate the circuit breaker."""
        if self.config.isolation_mode_enabled:
            await self._change_state(CircuitState.ISOLATED, reason)
            logger.warning(f"Circuit breaker {self.name} isolated: {reason}")
    
    def add_state_change_callback(self, callback: Callable[[CircuitState, CircuitState], None]) -> None:
        """Add a callback for state changes."""
        self.state_change_callbacks.append(callback)
    
    def add_failure_callback(self, callback: Callable[[FailureEvent], None]) -> None:
        """Add a callback for failure events."""
        self.failure_callbacks.append(callback)
    
    async def get_metrics(self) -> CircuitMetrics:
        """Get current circuit breaker metrics."""
        # Update response time metrics
        if self.metrics.response_times:
            response_times = list(self.metrics.response_times)
            self.metrics.avg_response_time = statistics.mean(response_times)
            
            if len(response_times) >= 20:
                self.metrics.p95_response_time = statistics.quantiles(response_times, n=20)[18]
            else:
                self.metrics.p95_response_time = max(response_times) if response_times else 0.0
            
            if len(response_times) >= 100:
                self.metrics.p99_response_time = statistics.quantiles(response_times, n=100)[98]
            else:
                self.metrics.p99_response_time = max(response_times) if response_times else 0.0
        
        return self.metrics
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status."""
        await self.get_metrics()
        
        # Calculate success rate
        success_rate = (
            self.metrics.successful_requests / max(1, self.metrics.total_requests)
        )
        
        # Calculate failure distribution
        total_failures = sum(self.metrics.failure_counts.values())
        failure_distribution = {
            failure_type.value: count / max(1, total_failures)
            for failure_type, count in self.metrics.failure_counts.items()
        }
        
        # Check for degradation
        is_degraded = await self._detect_degradation()
        
        # Predict next failure probability
        failure_probability = await self._predict_failure_probability()
        
        return {
            'name': self.name,
            'state': self.state.value,
            'success_rate': success_rate,
            'failure_rate': 1.0 - success_rate,
            'avg_response_time': self.metrics.avg_response_time,
            'p95_response_time': self.metrics.p95_response_time,
            'p99_response_time': self.metrics.p99_response_time,
            'failure_distribution': failure_distribution,
            'is_degraded': is_degraded,
            'failure_probability': failure_probability,
            'current_thresholds': {
                'failure_threshold': self.current_failure_threshold,
                'success_threshold': self.current_success_threshold,
                'timeout': self.current_timeout,
            },
            'metrics': {
                'total_requests': self.metrics.total_requests,
                'successful_requests': self.metrics.successful_requests,
                'failed_requests': self.metrics.failed_requests,
                'recovery_attempts': self.metrics.recovery_attempts,
                'successful_recoveries': self.metrics.successful_recoveries,
            }
        }
    
    async def _should_allow_request(self) -> bool:
        """Determine if a request should be allowed."""
        current_time = time.time()
        
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            # Check if timeout has passed
            if current_time - self.metrics.last_state_change > self.current_timeout:
                await self._change_state(CircuitState.HALF_OPEN, "Timeout elapsed")
                return True
            return False
        elif self.state == CircuitState.HALF_OPEN:
            # Allow limited number of requests
            return self.metrics.total_requests < self.metrics.recovery_attempts + self.config.half_open_max_calls
        elif self.state == CircuitState.DEGRADED:
            # Allow requests but warn
            logger.warning(f"Circuit breaker {self.name} is degraded")
            return True
        elif self.state == CircuitState.ISOLATED:
            return False
        
        return False
    
    async def _record_success(self, response_time: float) -> None:
        """Record a successful request."""
        async with self.failure_lock:
            self.metrics.total_requests += 1
            self.metrics.successful_requests += 1
            self.metrics.response_times.append(response_time)
            self.request_history.append((time.time(), True, response_time))
        
        # Handle state transitions
        if self.state == CircuitState.HALF_OPEN:
            if self.metrics.total_requests >= self.metrics.recovery_attempts + self.current_success_threshold:
                await self._change_state(CircuitState.CLOSED, "Recovery successful")
                self.metrics.successful_recoveries += 1
                self.metrics.recovery_attempts = 0
    
    async def _record_failure(self, response_time: float, failure_type: FailureType, error_message: str) -> None:
        """Record a failed request."""
        async with self.failure_lock:
            failure_event = FailureEvent(
                timestamp=time.time(),
                failure_type=failure_type,
                error_message=error_message,
                response_time=response_time
            )
            
            self.recent_failures.append(failure_event)
            self.metrics.total_requests += 1
            self.metrics.failed_requests += 1
            self.metrics.failure_counts[failure_type] += 1
            self.metrics.response_times.append(response_time)
            self.request_history.append((time.time(), False, response_time))
        
        # Call failure callbacks
        for callback in self.failure_callbacks:
            try:
                callback(failure_event)
            except Exception as e:
                logger.error(f"Error in failure callback: {e}")
        
        # Handle state transitions
        await self._handle_failure_state_transition()
    
    async def _handle_failure_state_transition(self) -> None:
        """Handle state transitions based on failures."""
        current_time = time.time()
        
        if self.state == CircuitState.CLOSED:
            # Check if failure threshold exceeded
            if self.metrics.failed_requests >= self.current_failure_threshold:
                await self._change_state(CircuitState.OPEN, "Failure threshold exceeded")
        
        elif self.state == CircuitState.HALF_OPEN:
            # Any failure in half-open state goes back to open
            await self._change_state(CircuitState.OPEN, "Failure in half-open state")
            self.metrics.recovery_attempts += 1
        
        elif self.state == CircuitState.DEGRADED:
            # Check if should open
            if await self._detect_severe_degradation():
                await self._change_state(CircuitState.OPEN, "Severe degradation detected")
    
    async def _change_state(self, new_state: CircuitState, reason: str) -> None:
        """Change circuit breaker state."""
        if new_state == self.state:
            return
        
        old_state = self.state
        self.state = new_state
        self.metrics.last_state_change = time.time()
        self.metrics.state_changes.append((time.time(), new_state))
        
        # Call state change callbacks
        for callback in self.state_change_callbacks:
            try:
                callback(old_state, new_state)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")
        
        logger.info(f"Circuit breaker {self.name} state changed: {old_state.value} -> {new_state.value} ({reason})")
    
    def _classify_failure(self, exception: Exception) -> FailureType:
        """Classify exception type for intelligent handling."""
        exception_name = type(exception).__name__.lower()
        error_message = str(exception).lower()
        
        if "timeout" in exception_name or "timeout" in error_message:
            return FailureType.TIMEOUT
        elif "connection" in exception_name or "connection" in error_message:
            return FailureType.CONNECTION_ERROR
        elif "rate" in error_message and "limit" in error_message:
            return FailureType.RATE_LIMIT
        elif any(code in error_message for code in ["500", "502", "503", "504"]):
            return FailureType.SERVER_ERROR
        elif "network" in error_message or "dns" in error_message:
            return FailureType.NETWORK_ERROR
        elif "auth" in error_message or "unauthorized" in error_message:
            return FailureType.AUTHENTICATION_ERROR
        else:
            return FailureType.UNKNOWN
    
    async def _detect_degradation(self) -> bool:
        """Detect if the service is degraded."""
        if not self.config.degradation_detection or len(self.metrics.response_times) < 10:
            return False
        
        # Check response times
        recent_times = list(self.metrics.response_times)[-self.config.response_time_window:]
        
        # Calculate percentage of slow calls
        slow_calls = sum(1 for t in recent_times if t > self.config.response_time_threshold)
        slow_call_ratio = slow_calls / len(recent_times)
        
        return slow_call_ratio > self.config.slow_call_ratio_threshold
    
    async def _detect_severe_degradation(self) -> bool:
        """Detect severe degradation that should open the circuit."""
        # More aggressive thresholds for severe degradation
        recent_times = list(self.metrics.response_times)[-50:]  # Last 50 calls
        
        if len(recent_times) < 20:
            return False
        
        # High error rate
        error_rate = self.metrics.failed_requests / max(1, self.metrics.total_requests)
        if error_rate > 0.5:  # 50% error rate
            return True
        
        # Very slow responses
        avg_response_time = statistics.mean(recent_times)
        if avg_response_time > self.config.response_time_threshold * 3:  # 3x threshold
            return True
        
        return False
    
    async def _predict_failure_probability(self) -> float:
        """Predict probability of next failure using historical patterns."""
        if not self.config.prediction_enabled or len(self.request_history) < 50:
            return 0.0
        
        # Simple ML approach: analyze recent patterns
        recent_history = list(self.request_history)[-100:]  # Last 100 requests
        
        # Calculate failure rate in sliding windows
        failure_rates = []
        window_size = 20
        
        for i in range(len(recent_history) - window_size + 1):
            window = recent_history[i:i + window_size]
            failures = sum(1 for _, failed, _ in window if failed)
            failure_rates.append(failures / window_size)
        
        if not failure_rates:
            return 0.0
        
        # Use trend analysis
        if len(failure_rates) >= 3:
            recent_trend = failure_rates[-3:]
            if len(recent_trend) > 1:
                # Simple linear trend
                trend_slope = (recent_trend[-1] - recent_trend[0]) / (len(recent_trend) - 1)
                
                # Predict next failure rate
                predicted_rate = failure_rates[-1] + trend_slope
                return max(0.0, min(1.0, predicted_rate))
        
        # Fallback to current failure rate
        return failure_rates[-1]
    
    async def _adaptive_threshold_loop(self) -> None:
        """Background task to adjust thresholds adaptively."""
        while self.running:
            try:
                await asyncio.sleep(self.config.threshold_adjustment_interval)
                await self._adjust_thresholds()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in adaptive threshold loop: {e}")
    
    async def _adjust_thresholds(self) -> None:
        """Adjust thresholds based on performance patterns."""
        if not self.config.adaptive_thresholds_enabled:
            return
        
        # Calculate recent performance metrics
        recent_requests = list(self.request_history)[-100:]  # Last 100 requests
        
        if len(recent_requests) < 50:
            return  # Not enough data
        
        # Calculate success rate and response time
        successes = sum(1 for _, success, _ in recent_requests if success)
        success_rate = successes / len(recent_requests)
        
        response_times = [rt for _, _, rt in recent_requests]
        avg_response_time = statistics.mean(response_times)
        
        # Adjust failure threshold
        if success_rate > 0.9:  # Very reliable
            # Allow more failures before opening
            new_threshold = min(
                self.current_failure_threshold * (1 + self.config.threshold_sensitivity),
                self.config.max_failure_threshold
            )
        elif success_rate < 0.7:  # Unreliable
            # Be more strict
            new_threshold = max(
                self.current_failure_threshold * (1 - self.config.threshold_sensitivity),
                self.config.min_failure_threshold
            )
        else:
            return  # No adjustment needed
        
        # Apply changes if significant
        if abs(new_threshold - self.current_failure_threshold) >= 1:
            old_threshold = self.current_failure_threshold
            self.current_failure_threshold = int(new_threshold)
            
            logger.info(
                f"Adjusted failure threshold for {self.name}: "
                f"{old_threshold} -> {self.current_failure_threshold} "
                f"(success_rate: {success_rate:.2f}, avg_response_time: {avg_response_time:.3f}s)"
            )


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""
    pass
