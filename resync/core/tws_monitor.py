"""TWS monitoring and alerting system.

This module provides real-time monitoring of the TWS environment,
performance metrics collection, and alert generation for anomalies.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog

from resync.core.exceptions import PerformanceError
from resync.core.interfaces import ITWSClient
from resync.core.teams_integration import get_teams_integration

from .shared_utils import TeamsNotification, create_job_status_notification

logger = structlog.get_logger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for TWS operations."""

    # API Performance
    api_response_times: List[float] = field(default_factory=list)
    api_error_rates: List[float] = field(default_factory=list)

    # Cache Performance
    cache_hit_ratios: List[float] = field(default_factory=list)
    cache_miss_rates: List[float] = field(default_factory=list)

    # LLM Usage
    llm_calls: int = 0
    llm_tokens_used: int = 0
    llm_cost_estimate: float = 0.0

    # Circuit Breaker Status
    circuit_breaker_trips: int = 0
    circuit_breaker_status: str = "closed"

    # Memory Usage
    memory_usage_mb: float = 0.0
    memory_peak_mb: float = 0.0

    # Timestamps
    timestamp: datetime = field(default_factory=datetime.now)
    uptime_seconds: float = 0.0


@dataclass
class Alert:
    """Alert for system anomalies or issues."""

    alert_id: str
    severity: str  # critical, high, medium, low
    category: str  # api, cache, llm, circuit_breaker, memory, job
    message: str
    timestamp: datetime
    resolved: bool = False
    resolution_time: Optional[datetime] = None
    details: Dict[str, Any] = field(default_factory=dict)


class TWSMonitor:
    """TWS monitoring and alerting system."""

    def __init__(self, tws_client: ITWSClient):
        """Initialize TWS monitor.

        Args:
            tws_client: TWS client for data collection
        """
        self.tws_client = tws_client
        self.metrics_history: List[PerformanceMetrics] = []
        self.alerts: List[Alert] = []
        self.alert_check_interval = 30  # seconds
        self._is_monitoring = False
        self._monitoring_task: Optional[asyncio.Task] = None

        # Alert thresholds
        self.alert_thresholds = {
            "api_error_rate": 0.05,  # 5% error rate
            "cache_hit_ratio": 0.80,  # 80% hit ratio
            "llm_cost_daily": 10.0,  # $10 daily budget
            "memory_usage_mb": 500.0,  # 500MB memory limit
            "circuit_breaker_trips": 3,  # 3 trips per hour
        }

        logger.info("tws_monitor_initialized")

    async def start_monitoring(self) -> None:
        """Start continuous monitoring."""
        if self._is_monitoring:
            logger.warning("Monitoring already started")
            return

        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("tws_monitoring_started")

    async def stop_monitoring(self) -> None:
        """Stop continuous monitoring."""
        self._is_monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
        logger.info("tws_monitoring_stopped")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._is_monitoring:
            try:
                await self._collect_metrics()
                await self._check_alerts()
                await asyncio.sleep(self.alert_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "error_in_tws_monitoring_loop", error=str(e), exc_info=True
                )
                await asyncio.sleep(10)  # Brief pause on error

    async def _collect_metrics(self) -> None:
        """Collect performance metrics."""
        try:
            start_time = time.time()

            # Collect API metrics
            api_response_time = await self._measure_api_response_time()
            api_error_rate = await self._calculate_api_error_rate()

            # Collect cache metrics
            cache_hit_ratio = await self._measure_cache_performance()

            # Collect LLM metrics
            llm_metrics = await self._measure_llm_usage()

            # Collect memory metrics
            memory_usage = await self._measure_memory_usage()

            # Create metrics record
            metrics = PerformanceMetrics(
                api_response_times=[api_response_time],
                api_error_rates=[api_error_rate],
                cache_hit_ratios=[cache_hit_ratio],
                llm_calls=llm_metrics.get("calls", 0),
                llm_tokens_used=llm_metrics.get("tokens", 0),
                llm_cost_estimate=llm_metrics.get("cost", 0.0),
                memory_usage_mb=memory_usage,
                uptime_seconds=time.time() - start_time,
            )

            self.metrics_history.append(metrics)

            # Keep only last 24 hours of metrics
            cutoff_time = datetime.now() - timedelta(hours=24)
            self.metrics_history = [
                m for m in self.metrics_history if m.timestamp > cutoff_time
            ]

        except Exception as e:
            logger.error("error_collecting_metrics", error=str(e), exc_info=True)

    async def _measure_api_response_time(self) -> float:
        """Measure API response time."""
        try:
            start_time = time.time()
            await self.tws_client.check_connection()
            return time.time() - start_time
        except Exception:
            return 999.0  # High value indicates error

    async def _calculate_api_error_rate(self) -> float:
        """Calculate API error rate."""
        # This would typically track actual API calls and errors
        # For now, we'll use a simple heuristic
        return 0.0

    async def _measure_cache_performance(self) -> float:
        """Measure cache performance."""
        # This would typically access cache metrics
        # For now, we'll return a simulated value
        return 0.85  # 85% hit ratio

    async def _measure_llm_usage(self) -> Dict[str, Any]:
        """Measure LLM usage."""
        # This would typically access LLM metrics
        # For now, we'll return simulated values
        return {"calls": 10, "tokens": 1000, "cost": 0.02}

    async def _measure_memory_usage(self) -> float:
        """Measure memory usage."""
        import psutil

        process = psutil.Process()
        return process.memory_info().rss / (1024 * 1024)  # MB

    async def _check_alerts(self) -> None:
        """Check for alert conditions."""
        alerts_to_add = []

        if not self.metrics_history:
            return

        latest_metrics = self.metrics_history[-1]

        # Check API error rate
        if latest_metrics.api_error_rates:
            avg_error_rate = sum(latest_metrics.api_error_rates) / len(
                latest_metrics.api_error_rates
            )
            if avg_error_rate > self.alert_thresholds["api_error_rate"]:
                alerts_to_add.append(
                    Alert(
                        alert_id=f"api_error_{int(time.time())}",
                        severity="high",
                        category="api",
                        message=f"API error rate exceeded threshold: {avg_error_rate:.2%}",
                        timestamp=datetime.now(),
                        details={"error_rate": avg_error_rate},
                    )
                )

        # Check cache hit ratio
        if latest_metrics.cache_hit_ratios:
            avg_hit_ratio = sum(latest_metrics.cache_hit_ratios) / len(
                latest_metrics.cache_hit_ratios
            )
            if avg_hit_ratio < self.alert_thresholds["cache_hit_ratio"]:
                alerts_to_add.append(
                    Alert(
                        alert_id=f"cache_hit_{int(time.time())}",
                        severity="medium",
                        category="cache",
                        message=f"Cache hit ratio below threshold: {avg_hit_ratio:.2%}",
                        timestamp=datetime.now(),
                        details={"hit_ratio": avg_hit_ratio},
                    )
                )

        # Check LLM cost (daily)
        daily_cost = latest_metrics.llm_cost_estimate * 24  # Assuming hourly rate
        if daily_cost > self.alert_thresholds["llm_cost_daily"]:
            alerts_to_add.append(
                Alert(
                    alert_id=f"llm_cost_{int(time.time())}",
                    severity="medium",
                    category="llm",
                    message=f"LLM cost approaching daily budget: ${daily_cost:.2f}",
                    timestamp=datetime.now(),
                    details={
                        "daily_cost": daily_cost,
                        "budget": self.alert_thresholds["llm_cost_daily"],
                    },
                )
            )

        # Check memory usage
        if latest_metrics.memory_usage_mb > self.alert_thresholds["memory_usage_mb"]:
            alerts_to_add.append(
                Alert(
                    alert_id=f"memory_usage_{int(time.time())}",
                    severity="high",
                    category="memory",
                    message=f"Memory usage exceeded threshold: {latest_metrics.memory_usage_mb:.1f}MB",
                    timestamp=datetime.now(),
                    details={"memory_usage_mb": latest_metrics.memory_usage_mb},
                )
            )

        # Add new alerts
        for alert in alerts_to_add:
            self.alerts.append(alert)
            logger.warning("new_alert_generated", message=alert.message)

            # Send Teams notification for critical alerts
            if alert.severity in ["critical", "high"]:
                await self._send_teams_notification(alert)

    async def _send_teams_notification(self, alert: Alert) -> None:
        """Send alert notification to Microsoft Teams.

        Args:
            alert: Alert to send notification for
        """
        try:
            # Get Teams integration
            teams_integration = get_teams_integration()

            # Create Teams notification
            notification = TeamsNotification(
                title=f"TWS Alert: {alert.category.title()}",
                message=alert.message,
                severity=alert.severity,
                additional_data=alert.details,
            )

            # Send notification
            await teams_integration.send_notification(notification)

        except Exception as e:
            logger.error(
                "failed_to_send_teams_notification_for_alert",
                error=str(e),
                exc_info=True,
            )

    async def monitor_job_status_change(
        self, job_data: Dict[str, Any], instance_name: str
    ) -> None:
        """Monitor job status changes and send notifications for configured statuses.

        Args:
            job_data: Job status data from TWS
            instance_name: Name of the TWS instance
        """
        try:
            # Get Teams integration
            teams_integration = await get_teams_integration()

            # Check if job notifications are enabled
            if (
                not teams_integration.config.enabled
                or not teams_integration.config.enable_job_notifications
            ):
                return

            # Check if this instance is being monitored
            if (
                teams_integration.config.monitored_tws_instances
                and instance_name
                not in teams_integration.config.monitored_tws_instances
            ):
                return

            # Check if job status matches filters
            job_status = job_data.get("status", "").upper()
            if job_status in [
                status.upper() for status in teams_integration.config.job_status_filters
            ]:
                # Send notification
                notification = create_job_status_notification(
                    job_data, instance_name, teams_integration.config.job_status_filters
                )

                if notification is None:
                    return

                await teams_integration.send_notification(notification)

        except Exception as e:
            logger.error(
                "failed_to_process_job_status_change_for_teams_notification",
                error=str(e),
                exc_info=True,
            )

    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report.

        Returns:
            Dictionary with performance metrics and alerts
        """
        try:
            # Calculate averages
            if self.metrics_history:
                latest_metrics = self.metrics_history[-1]
                avg_api_response_time = (
                    (
                        sum(sum(m.api_response_times) for m in self.metrics_history)
                        / sum(len(m.api_response_times) for m in self.metrics_history)
                    )
                    if any(m.api_response_times for m in self.metrics_history)
                    else 0.0
                )

                avg_cache_hit_ratio = (
                    (
                        sum(sum(m.cache_hit_ratios) for m in self.metrics_history)
                        / sum(len(m.cache_hit_ratios) for m in self.metrics_history)
                    )
                    if any(m.cache_hit_ratios for m in self.metrics_history)
                    else 0.0
                )
            else:
                latest_metrics = PerformanceMetrics()
                avg_api_response_time = 0.0
                avg_cache_hit_ratio = 0.0

            # Get recent alerts
            recent_alerts = [
                alert
                for alert in self.alerts
                if not alert.resolved
                and (datetime.now() - alert.timestamp).seconds < 3600  # Last hour
            ]

            return {
                "current_metrics": {
                    "api_response_time_ms": avg_api_response_time * 1000,
                    "cache_hit_ratio": avg_cache_hit_ratio,
                    "llm_calls_today": latest_metrics.llm_calls,
                    "llm_cost_today": latest_metrics.llm_cost_estimate,
                    "memory_usage_mb": latest_metrics.memory_usage_mb,
                    "uptime_seconds": latest_metrics.uptime_seconds,
                    "timestamp": datetime.now().isoformat(),
                },
                "alerts": [
                    {
                        "id": alert.alert_id,
                        "severity": alert.severity,
                        "category": alert.category,
                        "message": alert.message,
                        "timestamp": alert.timestamp.isoformat(),
                        "resolved": alert.resolved,
                        "details": alert.details,
                    }
                    for alert in recent_alerts
                ],
                "summary": {
                    "total_alerts": len([a for a in self.alerts if not a.resolved]),
                    "critical_alerts": len(
                        [
                            a
                            for a in self.alerts
                            if not a.resolved and a.severity == "critical"
                        ]
                    ),
                    "high_alerts": len(
                        [
                            a
                            for a in self.alerts
                            if not a.resolved and a.severity == "high"
                        ]
                    ),
                },
            }

        except Exception as e:
            logger.error("Error generating performance report", error=str(e))
            raise PerformanceError(f"Failed to generate performance report: {e}") from e

    def get_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent alerts.

        Args:
            limit: Maximum number of alerts to return

        Returns:
            List of recent alerts
        """
        recent_alerts = sorted(
            [alert for alert in self.alerts if not alert.resolved],
            key=lambda x: x.timestamp,
            reverse=True,
        )[:limit]

        return [
            {
                "id": alert.alert_id,
                "severity": alert.severity,
                "category": alert.category,
                "message": alert.message,
                "timestamp": alert.timestamp.isoformat(),
                "resolved": alert.resolved,
                "details": alert.details,
            }
            for alert in recent_alerts
        ]


# Global TWS monitor instance
_tws_monitor: Optional[TWSMonitor] = None


async def get_tws_monitor(tws_client: ITWSClient) -> TWSMonitor:
    """Get global TWS monitor instance.

    Args:
        tws_client: TWS client instance

    Returns:
        TWSMonitor instance
    """
    global _tws_monitor
    if _tws_monitor is None:
        _tws_monitor = TWSMonitor(tws_client)
        await _tws_monitor.start_monitoring()
    return _tws_monitor


async def shutdown_tws_monitor() -> None:
    """Shutdown global TWS monitor instance."""
    global _tws_monitor
    if _tws_monitor is not None:
        await _tws_monitor.stop_monitoring()
        _tws_monitor = None


class TWSMonitorInterface:
    """Interface to provide synchronous access to the TWS monitor."""

    def get_performance_report(self) -> Dict[str, Any]:
        """Get performance report. Requires async initialization."""
        if _tws_monitor is None:
            # Return a default/empty report if monitor is not initialized
            return {
                "current_metrics": {
                    "api_response_time_ms": 0.0,
                    "cache_hit_ratio": 0.0,
                    "llm_calls_today": 0,
                    "llm_cost_today": 0.0,
                    "memory_usage_mb": 0.0,
                    "uptime_seconds": 0.0,
                    "timestamp": datetime.now().isoformat(),
                },
                "alerts": [],
                "summary": {"total_alerts": 0, "critical_alerts": 0, "high_alerts": 0},
            }
        return _tws_monitor.get_performance_report()

    def get_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent alerts. Requires async initialization."""
        if _tws_monitor is None:
            return []
        return _tws_monitor.get_alerts(limit)


# Global tws_monitor variable that provides synchronous access
tws_monitor = TWSMonitorInterface()
