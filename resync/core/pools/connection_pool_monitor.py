"""
Connection Pool Monitoring and Alerting System
Enhanced monitoring for optimized connection pools in 20-user environment
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from resync.core.simple_logger import get_logger

from resync.core.pools.pool_manager import get_connection_pool_manager

logger = get_logger(__name__)


@dataclass
class PoolAlert:
    """Alert configuration for connection pool monitoring."""

    pool_name: str
    alert_type: str  # 'utilization', 'wait_time', 'errors', 'exhaustion'
    severity: str  # 'warning', 'critical', 'info'
    threshold: float
    current_value: float
    message: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PoolMetrics:
    """Real-time metrics for connection pool monitoring."""

    pool_name: str
    active_connections: int = 0
    idle_connections: int = 0
    total_connections: int = 0
    waiting_requests: int = 0
    utilization_percent: float = 0.0
    avg_wait_time_ms: float = 0.0
    error_count: int = 0
    exhaustion_count: int = 0
    last_health_check: datetime | None = None
    health_status: str = "unknown"

    def calculate_utilization(self) -> float:
        """Calculate pool utilization percentage."""
        if self.total_connections > 0:
            self.utilization_percent = (
                self.active_connections / self.total_connections
            ) * 100
        return self.utilization_percent


class ConnectionPoolMonitor:
    """
    Advanced connection pool monitoring system optimized for 20-user environment.

    Provides real-time monitoring, alerting, and performance insights for:
    - Database connection pools (Neo4j)
    - Redis connection pools
    - HTTP connection pools (TWS)
    """

    def __init__(self):
        self.pool_manager = None
        self.metrics: dict[str, PoolMetrics] = {}
        self.alerts: list[PoolAlert] = []
        self.monitoring_active = False
        self.monitor_task: asyncio.Task | None = None

        # Optimized thresholds for 20-user environment
        self.thresholds = {
            "utilization_warning": 80.0,  # 80% utilization
            "utilization_critical": 90.0,  # 90% utilization
            "wait_time_warning_ms": 100,  # 100ms wait time
            "wait_time_critical_ms": 500,  # 500ms wait time
            "error_rate_warning": 5.0,  # 5% error rate
            "error_rate_critical": 10.0,  # 10% error rate
        }

        # Monitoring intervals (optimized for 20-user load)
        self.monitor_interval = 30  # 30 seconds
        self.health_check_interval = 60  # 1 minute
        self.alert_cleanup_interval = 300  # 5 minutes

    async def initialize(self) -> None:
        """Initialize the connection pool monitor."""
        try:
            self.pool_manager = await get_connection_pool_manager()
            logger.info(
                "connection_pool_monitor_initialized",
                pool_count=len(self.pool_manager.pools),
            )
        except Exception as e:
            logger.error(
                "connection_pool_monitor_initialization_failed", error=str(e)
            )
            raise

    async def start_monitoring(self) -> None:
        """Start background monitoring."""
        if self.monitoring_active:
            return

        self.monitoring_active = True
        self.monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("connection_pool_monitoring_started")

    async def stop_monitoring(self) -> None:
        """Stop background monitoring."""
        if not self.monitoring_active:
            return

        self.monitoring_active = False
        if self.monitor_task:
            self.monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.monitor_task

        logger.info("connection_pool_monitoring_stopped")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop optimized for 20-user environment."""
        last_health_check = 0
        last_alert_cleanup = 0

        while self.monitoring_active:
            try:
                current_time = time.time()

                # Update metrics every 30 seconds
                await self._update_metrics()

                # Health checks every 60 seconds
                if (
                    current_time - last_health_check
                    >= self.health_check_interval
                ):
                    await self._perform_health_checks()
                    last_health_check = current_time

                # Check for alerts
                await self._check_alerts()

                # Cleanup old alerts every 5 minutes
                if (
                    current_time - last_alert_cleanup
                    >= self.alert_cleanup_interval
                ):
                    self._cleanup_old_alerts()
                    last_alert_cleanup = current_time

                await asyncio.sleep(self.monitor_interval)

            except Exception as e:
                logger.error("connection_pool_monitoring_error", error=str(e))
                await asyncio.sleep(self.monitor_interval)

    async def _update_metrics(self) -> None:
        """Update real-time metrics for all pools."""
        if not self.pool_manager:
            return

        for pool_name, pool in self.pool_manager.pools.items():
            try:
                stats = pool.get_stats_copy()

                metrics = PoolMetrics(
                    pool_name=pool_name,
                    active_connections=stats.get("active_connections", 0),
                    idle_connections=stats.get("idle_connections", 0),
                    total_connections=stats.get("total_connections", 0),
                    waiting_requests=stats.get("waiting_connections", 0),
                    avg_wait_time_ms=stats.get("average_wait_time", 0.0)
                    * 1000,  # Convert to ms
                    error_count=stats.get("connection_errors", 0),
                    exhaustion_count=stats.get("pool_exhaustions", 0),
                    last_health_check=stats.get("last_health_check"),
                )

                metrics.calculate_utilization()
                self.metrics[pool_name] = metrics

            except Exception as e:
                logger.warning(
                    "pool_metrics_update_failed",
                    pool_name=pool_name,
                    error=str(e),
                )

    async def _perform_health_checks(self) -> None:
        """Perform health checks on all pools."""
        if not self.pool_manager:
            return

        health_results = await self.pool_manager.health_check_all()

        for pool_name, is_healthy in health_results.items():
            if pool_name in self.metrics:
                self.metrics[pool_name].health_status = (
                    "healthy" if is_healthy else "unhealthy"
                )
                self.metrics[pool_name].last_health_check = datetime.now()

                if not is_healthy:
                    logger.warning(
                        "pool_health_check_failed", pool_name=pool_name
                    )

    async def _check_alerts(self) -> None:
        """Check for alert conditions optimized for 20-user environment."""
        for pool_name, metrics in self.metrics.items():
            # Utilization alerts
            if (
                metrics.utilization_percent
                >= self.thresholds["utilization_critical"]
            ):
                self._create_alert(
                    pool_name,
                    "utilization",
                    "critical",
                    metrics.utilization_percent,
                    ".1f",
                )
            elif (
                metrics.utilization_percent
                >= self.thresholds["utilization_warning"]
            ):
                self._create_alert(
                    pool_name,
                    "utilization",
                    "warning",
                    metrics.utilization_percent,
                    ".1f",
                )

            # Wait time alerts
            if (
                metrics.avg_wait_time_ms
                >= self.thresholds["wait_time_critical_ms"]
            ):
                self._create_alert(
                    pool_name,
                    "wait_time",
                    "critical",
                    metrics.avg_wait_time_ms,
                    ".0f",
                )
            elif (
                metrics.avg_wait_time_ms
                >= self.thresholds["wait_time_warning_ms"]
            ):
                self._create_alert(
                    pool_name,
                    "wait_time",
                    "warning",
                    metrics.avg_wait_time_ms,
                    ".0f",
                )

            # Error rate alerts (calculate from recent errors)
            if metrics.error_count > 0:
                # Simplified error rate check - could be enhanced with time windows
                error_rate = (
                    metrics.error_count / max(metrics.total_connections, 1)
                ) * 100
                if error_rate >= self.thresholds["error_rate_critical"]:
                    self._create_alert(
                        pool_name, "errors", "critical", error_rate, ".1f"
                    )
                elif error_rate >= self.thresholds["error_rate_warning"]:
                    self._create_alert(
                        pool_name, "errors", "warning", error_rate, ".1f"
                    )

            # Pool exhaustion alerts
            if metrics.exhaustion_count > 0:
                self._create_alert(
                    pool_name,
                    "exhaustion",
                    "critical",
                    metrics.exhaustion_count,
                    "d",
                )

    def _create_alert(
        self,
        pool_name: str,
        alert_type: str,
        severity: str,
        value: float,
        format_spec: str,
    ) -> None:
        """Create a new alert if one doesn't already exist for this condition."""

        # Check if similar alert already exists (avoid spam)
        existing_alert = None
        for alert in self.alerts:
            if (
                alert.pool_name == pool_name
                and alert.alert_type == alert_type
                and alert.severity == severity
            ):
                existing_alert = alert
                break

        if existing_alert:
            # Update existing alert with new value
            existing_alert.current_value = value
            existing_alert.timestamp = datetime.now()
            return

        # Create new alert
        message = self._format_alert_message(
            pool_name, alert_type, severity, value, format_spec
        )

        alert = PoolAlert(
            pool_name=pool_name,
            alert_type=alert_type,
            severity=severity,
            threshold=getattr(self.thresholds, f"{alert_type}_{severity}", 0),
            current_value=value,
            message=message,
        )

        self.alerts.append(alert)
        logger.warning(
            "connection_pool_alert",
            pool_name=pool_name,
            alert_type=alert_type,
            severity=severity,
            value=value,
            message=message,
        )

    def _format_alert_message(
        self,
        pool_name: str,
        alert_type: str,
        severity: str,
        value: float,
        format_spec: str,
    ) -> str:
        """Format alert message for the specific alert type."""

        formatted_value = f"{value:{format_spec}}"

        if alert_type == "utilization":
            return f"{pool_name} pool utilization at {formatted_value}% (threshold: {self.thresholds[f'utilization_{severity}']}%)"
        if alert_type == "wait_time":
            return f"{pool_name} pool average wait time: {formatted_value}ms (threshold: {self.thresholds[f'wait_time_{severity}_ms']}ms)"
        if alert_type == "errors":
            return f"{pool_name} pool error rate: {formatted_value}% (threshold: {self.thresholds[f'error_rate_{severity}']}%)"
        if alert_type == "exhaustion":
            return f"{pool_name} pool exhausted {formatted_value} times"
        return f"{pool_name} pool {alert_type}: {formatted_value}"

    def _cleanup_old_alerts(self) -> None:
        """Clean up old alerts to prevent memory buildup."""
        cutoff_time = datetime.now() - timedelta(
            minutes=30
        )  # Keep alerts for 30 minutes

        old_count = len(self.alerts)
        self.alerts = [
            alert for alert in self.alerts if alert.timestamp > cutoff_time
        ]

        if old_count > len(self.alerts):
            logger.info(
                "connection_pool_alerts_cleaned",
                removed=old_count - len(self.alerts),
                remaining=len(self.alerts),
            )

    def get_pool_metrics(self, pool_name: str | None = None) -> dict[str, Any]:
        """Get current pool metrics."""
        if pool_name:
            metrics = self.metrics.get(pool_name)
            return metrics.__dict__ if metrics else {}
        return {
            name: metrics.__dict__ for name, metrics in self.metrics.items()
        }

    def get_active_alerts(self) -> list[dict[str, Any]]:
        """Get all active alerts."""
        return [alert.__dict__ for alert in self.alerts]

    def get_monitoring_status(self) -> dict[str, Any]:
        """Get overall monitoring status."""
        return {
            "monitoring_active": self.monitoring_active,
            "pools_monitored": len(self.metrics),
            "active_alerts": len(self.alerts),
            "last_update": datetime.now().isoformat(),
            "thresholds": self.thresholds,
        }


# Global monitor instance
_monitor_instance: ConnectionPoolMonitor | None = None


async def get_connection_pool_monitor() -> ConnectionPoolMonitor:
    """Get the global connection pool monitor instance."""
    global _monitor_instance

    if _monitor_instance is None:
        _monitor_instance = ConnectionPoolMonitor()
        await _monitor_instance.initialize()

    return _monitor_instance


async def start_connection_pool_monitoring() -> None:
    """Start the connection pool monitoring system."""
    monitor = await get_connection_pool_monitor()
    await monitor.start_monitoring()


async def stop_connection_pool_monitoring() -> None:
    """Stop the connection pool monitoring system."""
    global _monitor_instance

    if _monitor_instance:
        await _monitor_instance.stop_monitoring()
        _monitor_instance = None




