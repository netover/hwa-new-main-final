"""
Health Service Components

This package contains modular health service components extracted from the monolithic
health service implementation. These components provide focused, reusable functionality
for health monitoring, alerting, and system diagnostics.

Exported Components:
    - HealthServiceOrchestrator: Main coordination logic for health checks
    - ProactiveHealthMonitor: Proactive monitoring and predictive analysis
    - PerformanceMetricsCollector: System and connection pool performance metrics
    - CircuitBreaker: Circuit breaker implementation for health checks
    - CircuitBreakerManager: Advanced circuit breaker management
    - ComponentCacheManager: Component health result caching
    - HealthHistoryManager: Health check history management
    - MemoryManager: Memory usage tracking and optimization
    - MemoryUsageTracker: Detailed memory usage monitoring
    - RecoveryManager: Component recovery mechanisms
    - HealthAlerting: Alert generation and management
    - HealthCheckConfigurationManager: Configuration management for health checks
    - HealthMonitoringCoordinator: Continuous monitoring coordination
    - HealthCheckRetry: Retry mechanisms with exponential backoff
    - GlobalHealthServiceManager: Singleton management for global health service
"""

from .circuit_breaker import CircuitBreaker
from .circuit_breaker_manager import CircuitBreakerManager
from .component_cache_manager import ComponentCacheManager
from .global_health_service_manager import (
    GlobalHealthServiceManager,
    get_global_health_service,
    shutdown_global_health_service,
    get_current_global_health_service,
    is_global_health_service_initialized,
)
from .health_alerting import HealthAlerting
from .health_check_retry import HealthCheckRetry
from .health_check_service import HealthCheckService
from .health_check_utils import HealthCheckUtils
from .health_config_manager import HealthCheckConfigurationManager
from .health_history_manager import HealthHistoryManager
from .health_monitoring_coordinator import HealthMonitoringCoordinator
from .health_service_manager import HealthServiceManager
from .health_service_orchestrator import HealthServiceOrchestrator
from .memory_manager import MemoryManager
from .memory_usage_tracker import MemoryUsageTracker
from .monitoring_aggregator import HealthMonitoringAggregator
from .performance_metrics_collector import PerformanceMetricsCollector
from .proactive_monitor import ProactiveHealthMonitor
from .recovery_manager import HealthRecoveryManager

__all__ = [
    # Core orchestration
    "HealthServiceOrchestrator",
    "HealthServiceManager",
    # Monitoring components
    "ProactiveHealthMonitor",
    "PerformanceMetricsCollector",
    "HealthMonitoringCoordinator",
    "MonitoringAggregator",
    # Circuit breaker functionality
    "CircuitBreaker",
    "CircuitBreakerManager",
    # Caching and history
    "ComponentCacheManager",
    "HealthHistoryManager",
    # Memory management
    "MemoryManager",
    "MemoryUsageTracker",
    # Recovery and alerting
    "RecoveryManager",
    "HealthAlerting",
    # Configuration
    "HealthConfigManager",
    # Utilities
    "HealthCheckUtils",
    "HealthCheckRetry",
    # Global service management
    "GlobalHealthServiceManager",
    "get_global_health_service",
    "shutdown_global_health_service",
    "get_current_global_health_service",
    "is_global_health_service_initialized",
    # Legacy support
    "HealthCheckService",
]
