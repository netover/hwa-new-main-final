"""Circuit breakers for external dependencies with correct aiobreaker interface."""

from datetime import timedelta
from functools import wraps
from typing import Any, Callable, TypeVar, Union
import asyncio

from aiobreaker import CircuitBreaker, CircuitBreakerListener

from resync.core.structured_logger import get_logger
from resync.core.exceptions import AuthenticationError, LLMError, RedisConnectionError

logger = get_logger(__name__)

# Lazy import of runtime_metrics to avoid circular dependencies
def _get_runtime_metrics():
    """Lazy import of runtime_metrics."""
    from resync.core.metrics import runtime_metrics
    return runtime_metrics

# Type variable for generic decorator typing
F = TypeVar('F', bound=Callable[..., Any])

# ============================================================================ 
# CORRECT LISTENER IMPLEMENTATIONS
# ============================================================================

class RedisBreakerListener(CircuitBreakerListener):
    """Listener for Redis circuit breaker state changes."""
    
    def state_change(self, breaker, old, new):
        """Handle circuit breaker state changes."""
        old_state = old.name if hasattr(old, 'name') else str(old)
        new_state = new.name if hasattr(new, 'name') else str(new)
        
        logger.info(
            "redis_circuit_breaker_state_change",
            breaker_name=breaker.name,
            old_state=old_state,
            new_state=new_state,
            fail_counter=breaker.fail_counter
        )
        
        if new_state == "OPEN":
            _get_runtime_metrics().record_health_check(
                "redis_circuit_breaker",
                "opened",
                {
                    "failure_count": breaker.fail_counter,
                    "last_failure": str(breaker.last_failure) if breaker.last_failure else None,
                    "state": new_state
                }
            )

class TWSBreakerListener(CircuitBreakerListener):
    """Listener for TWS circuit breaker state changes."""
    
    def state_change(self, breaker, old, new):
        """Handle circuit breaker state changes."""
        old_state = old.name if hasattr(old, 'name') else str(old)
        new_state = new.name if hasattr(new, 'name') else str(new)
        
        logger.info(
            "tws_circuit_breaker_state_change",
            breaker_name=breaker.name,
            old_state=old_state,
            new_state=new_state,
            fail_counter=breaker.fail_counter
        )
        
        if new_state == "OPEN":
            _get_runtime_metrics().record_health_check(
                "tws_circuit_breaker",
                "opened",
                {
                    "failure_count": breaker.fail_counter,
                    "last_failure": str(breaker.last_failure) if breaker.last_failure else None,
                    "state": new_state
                }
            )

class LLMBreakerListener(CircuitBreakerListener):
    """Listener for LLM circuit breaker state changes."""
    
    def state_change(self, breaker, old, new):
        """Handle circuit breaker state changes."""
        old_state = old.name if hasattr(old, 'name') else str(old)
        new_state = new.name if hasattr(new, 'name') else str(new)
        
        logger.info(
            "llm_circuit_breaker_state_change",
            breaker_name=breaker.name,
            old_state=old_state,
            new_state=new_state,
            fail_counter=breaker.fail_counter
        )
        
        if new_state == "OPEN":
            _get_runtime_metrics().record_health_check(
                "llm_circuit_breaker",
                "opened",
                {
                    "failure_count": breaker.fail_counter,
                    "last_failure": str(breaker.last_failure) if breaker.last_failure else None,
                    "state": new_state
                }
            )

# ============================================================================
# CIRCUIT BREAKER INSTANCES
# ============================================================================

# Redis Circuit Breaker
redis_breaker: CircuitBreaker = CircuitBreaker(
    fail_max=3,
    timeout_duration=timedelta(seconds=30),
    exclude=[ValueError, TypeError],
    name="redis_operations"
)
# Add compatibility attributes
redis_breaker.exclude = [ValueError, TypeError]
redis_breaker.add_listener(RedisBreakerListener())

# TWS Circuit Breaker
tws_breaker: CircuitBreaker = CircuitBreaker(
    fail_max=5,
    timeout_duration=timedelta(seconds=60),
    exclude=[AuthenticationError],
    name="tws_operations"
)
# Add compatibility attributes
tws_breaker.exclude = [AuthenticationError]
tws_breaker.add_listener(TWSBreakerListener())

# LLM Circuit Breaker
llm_breaker: CircuitBreaker = CircuitBreaker(
    fail_max=2,
    timeout_duration=timedelta(seconds=45),
    exclude=[LLMError],
    name="llm_operations"
)
llm_breaker.add_listener(LLMBreakerListener())

# ============================================================================
# DECORATOR APPLICATION FUNCTIONS
# ============================================================================

def with_redis_circuit_breaker(func: F) -> F:
    """Apply Redis circuit breaker to function."""
    return redis_breaker(func)

def with_tws_circuit_breaker(func: F) -> F:
    """Apply TWS circuit breaker to function."""
    return tws_breaker(func)

def with_llm_circuit_breaker(func: F) -> F:
    """Apply LLM circuit breaker to function."""
    return llm_breaker(func)

# ============================================================================
# CONVENIENCE DECORATORS
# ============================================================================

def redis_protected(func: F) -> F:
    """
    Decorator to protect Redis operations with circuit breaker.
    
    Usage:
        @redis_protected
        async def redis_operation():
            # Redis code here
    """
    @wraps(func)
    @redis_breaker
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
    return wrapper

def tws_protected(func: F) -> F:
    """
    Decorator to protect TWS operations with circuit breaker.
    
    Usage:
        @tws_protected  
        async def tws_operation():
            # TWS code here
    """
    @wraps(func)
    @tws_breaker
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
    return wrapper

def llm_protected(func: F) -> F:
    """
    Decorator to protect LLM operations with circuit breaker.
    
    Usage:
        @llm_protected
        async def llm_operation():
            # LLM code here  
    """
    @wraps(func)
    @llm_breaker
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
    return wrapper

# ============================================================================
# MANUAL CALL METHODS (Alternative to decorators)
# ============================================================================

async def call_with_redis_breaker(func: Callable, *args, **kwargs) -> Any:
    """Manually call function with Redis circuit breaker protection."""
    return await redis_breaker.call_async(func, *args, **kwargs)

async def call_with_tws_breaker(func: Callable, *args, **kwargs) -> Any:
    """Manually call function with TWS circuit breaker protection."""
    return await tws_breaker.call_async(func, *args, **kwargs)

async def call_with_llm_breaker(func: Callable, *args, **kwargs) -> Any:
    """Manually call function with LLM circuit breaker protection."""
    return await llm_breaker.call_async(func, *args, **kwargs)

# ============================================================================
# CIRCUIT BREAKER STATUS AND MANAGEMENT
# ============================================================================

def get_circuit_breaker_status() -> dict:
    """Get status of all circuit breakers."""
    return {
        "redis": {
            "name": redis_breaker.name,
            "state": redis_breaker.current_state.__class__.__name__,
            "fail_counter": redis_breaker.fail_counter,
            "last_failure": str(redis_breaker.last_failure) if redis_breaker.last_failure else None,
            "timeout_duration": str(redis_breaker.timeout_duration),
        },
        "tws": {
            "name": tws_breaker.name,
            "state": tws_breaker.current_state.__class__.__name__,
            "fail_counter": tws_breaker.fail_counter,
            "last_failure": str(tws_breaker.last_failure) if tws_breaker.last_failure else None,
            "timeout_duration": str(tws_breaker.timeout_duration),
        },
        "llm": {
            "name": llm_breaker.name,
            "state": llm_breaker.current_state.__class__.__name__,
            "fail_counter": llm_breaker.fail_counter,
            "last_failure": str(llm_breaker.last_failure) if llm_breaker.last_failure else None,
            "timeout_duration": str(llm_breaker.timeout_duration),
        }
    }

def reset_all_circuit_breakers() -> None:
    """Reset all circuit breakers to closed state."""
    redis_breaker.reset()
    tws_breaker.reset()
    llm_breaker.reset()
    
    logger.info("all_circuit_breakers_reset")

# ============================================================================
# EXPORT PUBLIC API
# ============================================================================

__all__ = [
    "redis_breaker",
    "tws_breaker",
    "llm_breaker",
    "redis_protected",
    "tws_protected",
    "llm_protected",
    "call_with_redis_breaker",
    "call_with_tws_breaker",
    "call_with_llm_breaker",
    "get_circuit_breaker_status",
    "reset_all_circuit_breakers",
]
