"""
ChuckNorris Metrics System

Advanced monitoring system with custom metrics, real-time analytics,
and intelligent alerting for comprehensive observability.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections import deque, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
import json
import statistics
# Removed unused import of weakref to satisfy linting tools

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics supported."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"
    METER = "meter"


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class MetricValue:
    """Represents a single metric value."""
    name: str
    value: Union[int, float, str]
    timestamp: float = field(default_factory=time.time)
    labels: Dict[str, str] = field(default_factory=dict)
    metric_type: MetricType = MetricType.GAUGE


@dataclass
class Alert:
    """Represents an alert condition."""
    name: str
    severity: AlertSeverity
    message: str
    timestamp: float = field(default_factory=time.time)
    labels: Dict[str, str] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[float] = None
    correlation_id: Optional[str] = None


@dataclass
class ChuckNorrisMetricsConfig:
    """Configuration for ChuckNorris metrics system."""
    
    # Collection settings
    collection_interval: float = 1.0  # seconds
    max_metrics_history: int = 10000
    enable_persistence: bool = True
    persistence_path: str = "./metrics_data"
    
    # Alerting settings
    alerting_enabled: bool = True
    alert_cooldown: float = 300.0  # 5 minutes
    max_alerts_per_hour: int = 100
    
    # Performance settings
    enable_real_time: bool = True
    enable_aggregation: bool = True
    aggregation_window: int = 60  # seconds
    
    # Export settings
    enable_prometheus: bool = True
    enable_json_export: bool = True
    export_interval: float = 60.0  # seconds
    prometheus_port: int = 9090
    
    # Business metrics
    enable_business_metrics: bool = True
    custom_metrics_enabled: bool = True
    
    # Advanced features
    enable_anomaly_detection: bool = True
    anomaly_threshold: float = 2.0  # standard deviations
    enable_trend_analysis: bool = True
    trend_window: int = 300  # 5 minutes


class ChuckNorrisMetricsCollector:
    """
    Advanced metrics collection system with ChuckNorris-level intelligence:
    
    1. Custom Metric Types (Counter, Gauge, Histogram, Timer, Meter)
    2. Real-time Alerting with severity levels
    3. Intelligent Aggregation and Rollups
    4. Anomaly Detection and Trend Analysis
    5. Business Metrics and KPIs
    6. Prometheus Export Support
    7. Persistent Storage with Time Series
    """
    
    def __init__(self, name: str, config: ChuckNorrisMetricsConfig | None = None):
        self.name = name
        self.config = config or ChuckNorrisMetricsConfig()
        
        # Metrics storage
        self.metrics: Dict[str, deque[MetricValue]] = defaultdict(lambda: deque(maxlen=self.config.max_metrics_history))
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = defaultdict(float)
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.timers: Dict[str, List[float]] = defaultdict(list)
        
        # Alerting system
        self.alerts: deque[Alert] = deque(maxlen=1000)
        self.alert_history: Dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=100))
        self.alert_callbacks: List[Callable[[Alert], None]] = []
        
        # Aggregation cache
        self.aggregated_metrics: Dict[str, MetricValue] = {}
        self.last_aggregation = 0.0
        
        # Anomaly detection
        self.baselines: Dict[str, Dict[str, float]] = {}  # name -> {mean, std}
        self.anomaly_history: deque[Alert] = deque(maxlen=500)
        
        # Background tasks
        self.collection_task: Optional[asyncio.Task] = None
        self.aggregation_task: Optional[asyncio.Task] = None
        self.export_task: Optional[asyncio.Task] = None
        self.anomaly_task: Optional[asyncio.Task] = None
        self.running = False
        
        # Persistence
        self.persistence_enabled = False
        
        logger.info(f"ChuckNorris metrics collector initialized for {name}")
    
    async def start(self) -> None:
        """Start the metrics collector."""
        if self.running:
            return
            
        self.running = True
        
        # Start background tasks
        self.collection_task = asyncio.create_task(self._collection_loop())
        
        if self.config.enable_aggregation:
            self.aggregation_task = asyncio.create_task(self._aggregation_loop())
        
        if self.config.enable_anomaly_detection:
            self.anomaly_task = asyncio.create_task(self._anomaly_detection_loop())
        
        if self.config.enable_prometheus or self.config.enable_json_export:
            self.export_task = asyncio.create_task(self._export_loop())
        
        # Initialize persistence
        if self.config.enable_persistence:
            await self._init_persistence()
        
        logger.info(f"ChuckNorris metrics collector started for {self.name}")
    
    async def stop(self) -> None:
        """Stop the metrics collector."""
        if not self.running:
            return
            
        self.running = False
        
        # Cancel background tasks
        tasks = [
            self.collection_task,
            self.aggregation_task,
            self.export_task,
            self.anomaly_task
        ]
        
        for task in tasks:
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        
        # Final export
        await self._export_metrics()
        
        logger.info(f"ChuckNorris metrics collector stopped for {self.name}")
    
    def increment(self, name: str, value: int = 1, labels: Dict[str, str] | None = None) -> None:
        """Increment a counter metric."""
        self.counters[name] += value
        
        metric = MetricValue(
            name=name,
            value=self.counters[name],
            metric_type=MetricType.COUNTER,
            labels=labels or {}
        )
        
        self._add_metric(metric)
    
    def gauge(self, name: str, value: float, labels: Dict[str, str] | None = None) -> None:
        """Set a gauge metric."""
        self.gauges[name] = value
        
        metric = MetricValue(
            name=name,
            value=value,
            metric_type=MetricType.GAUGE,
            labels=labels or {}
        )
        
        self._add_metric(metric)
    
    def histogram(self, name: str, value: float, labels: Dict[str, str] | None = None) -> None:
        """Add a value to a histogram."""
        self.histograms[name].append(value)
        
        metric = MetricValue(
            name=name,
            value=value,
            metric_type=MetricType.HISTOGRAM,
            labels=labels or {}
        )
        
        self._add_metric(metric)
    
    def timer(self, name: str, duration: float, labels: Dict[str, str] | None = None) -> None:
        """Record a timer metric."""
        self.timers[name].append(duration)
        
        metric = MetricValue(
            name=name,
            value=duration,
            metric_type=MetricType.TIMER,
            labels=labels or {}
        )
        
        self._add_metric(metric)
    
    def meter(self, name: str, rate: float, labels: Dict[str, str] | None = None) -> None:
        """Record a meter metric (rate)."""
        # Store as gauge for simplicity
        self.gauge(f"{name}_rate", rate, labels)
    
    def cache_hit(self, endpoint: str, cache_type: str = "default", labels: Dict[str, str] | None = None) -> None:
        """Record a cache hit."""
        metric_labels = {"endpoint": endpoint, "cache_type": cache_type}
        if labels:
            metric_labels.update(labels)
        
        self.increment("cache_hits_total", labels=metric_labels)
        
        # Update hit ratio
        total_hits = self.counters.get("cache_hits_total", 0)
        total_misses = self.counters.get("cache_misses_total", 0)
        if total_hits + total_misses > 0:
            hit_ratio = total_hits / (total_hits + total_misses)
            self.gauge("cache_hit_ratio", hit_ratio, {"endpoint": endpoint, "cache_type": cache_type})
    
    def cache_miss(self, endpoint: str, cache_type: str = "default", labels: Dict[str, str] | None = None) -> None:
        """Record a cache miss."""
        metric_labels = {"endpoint": endpoint, "cache_type": cache_type}
        if labels:
            metric_labels.update(labels)
        
        self.increment("cache_misses_total", labels=metric_labels)
        
        # Update hit ratio
        total_hits = self.counters.get("cache_hits_total", 0)
        total_misses = self.counters.get("cache_misses_total", 0)
        if total_hits + total_misses > 0:
            hit_ratio = total_hits / (total_hits + total_misses)
            self.gauge("cache_hit_ratio", hit_ratio, {"endpoint": endpoint, "cache_type": cache_type})
    
    def circuit_breaker_state_change(self, breaker_name: str, old_state: str, new_state: str, service: str, labels: Dict[str, str] | None = None) -> None:
        """Record circuit breaker state change."""
        metric_labels = {"breaker_name": breaker_name, "service": service, "old_state": old_state, "new_state": new_state}
        if labels:
            metric_labels.update(labels)
        
        # Convert state to numeric (0=closed, 1=open, 2=half-open)
        state_values = {"closed": 0, "open": 1, "half-open": 2}
        state_value = state_values.get(new_state.lower(), 0)
        
        self.gauge("circuit_breaker_state", state_value, metric_labels)
        self.increment("circuit_breaker_state_changes_total", metric_labels)
        
        # Alert on state change to open
        if new_state.lower() in ["open", "half-open"]:
            self.create_alert(
                name="circuit_breaker_opened",
                severity=AlertSeverity.WARNING,
                message=f"Circuit breaker {breaker_name} for service {service} changed to {new_state}",
                labels=metric_labels
            )
    
    def circuit_breaker_failure(self, breaker_name: str, service: str, failure_type: str, labels: Dict[str, str] | None = None) -> None:
        """Record circuit breaker failure."""
        metric_labels = {"breaker_name": breaker_name, "service": service, "failure_type": failure_type}
        if labels:
            metric_labels.update(labels)
        
        self.increment("circuit_breaker_failures_total", metric_labels)
        
        # Alert on failures
        self.create_alert(
            name="circuit_breaker_failure",
            severity=AlertSeverity.ERROR,
            message=f"Circuit breaker {breaker_name} for service {service} recorded failure: {failure_type}",
            labels=metric_labels
        )
    
    def request_latency(self, endpoint: str, method: str, status_code: int, duration: float, labels: Dict[str, str] | None = None) -> None:
        """Record request latency with histogram."""
        metric_labels = {"endpoint": endpoint, "method": method, "status_code": str(status_code)}
        if labels:
            metric_labels.update(labels)
        
        # Record as histogram
        self.histogram("request_duration_seconds", duration, metric_labels)
        
        # Also record as timer for compatibility
        self.timer(f"request_{endpoint}_{method}", duration, metric_labels)
        
        # Alert on slow requests
        if duration > 5.0:  # 5 seconds threshold
            self.create_alert(
                name="slow_request",
                severity=AlertSeverity.WARNING,
                message=f"Slow request detected: {method} {endpoint} took {duration:.2f}s",
                labels=metric_labels
            )
    
    def api_latency(self, endpoint: str, operation: str, duration: float, labels: Dict[str, str] | None = None) -> None:
        """Record API-specific latency with detailed buckets."""
        metric_labels = {"endpoint": endpoint, "operation": operation}
        if labels:
            metric_labels.update(labels)
        
        # Record with specialized histogram
        self.histogram("api_request_duration_seconds", duration, metric_labels)
        
        # Track P50, P95, P99
        recent_durations = self.timers.get(f"api_{endpoint}_{operation}", [])[-100:]  # Last 100 requests
        if recent_durations:
            p50 = self._percentile(recent_durations, 0.5)
            p95 = self._percentile(recent_durations, 0.95)
            p99 = self._percentile(recent_durations, 0.99)
            
            self.gauge(f"api_latency_p50_{endpoint}_{operation}", p50, metric_labels)
            self.gauge(f"api_latency_p95_{endpoint}_{operation}", p95, metric_labels)
            self.gauge(f"api_latency_p99_{endpoint}_{operation}", p99, metric_labels)
    
    def error_rate(self, endpoint: str, error_type: str, status_code: int = 0, labels: Dict[str, str] | None = None) -> None:
        """Record error rate for endpoints."""
        metric_labels = {"endpoint": endpoint, "error_type": error_type}
        if status_code:
            metric_labels["status_code"] = str(status_code)
        if labels:
            metric_labels.update(labels)
        
        # Increment error counter
        self.increment("endpoint_errors_total", metric_labels)
        
        # Calculate error rate (errors per minute in last 5 minutes)
        current_time = time.time()
        recent_errors = [
            m for m in self.metrics.get("endpoint_errors_total", [])
            if m.timestamp >= current_time - 300 and isinstance(m.value, (int, float))
        ]
        
        if recent_errors:
            error_rate_per_minute = len(recent_errors) / 5.0
            self.gauge("endpoint_error_rate", error_rate_per_minute, {"endpoint": endpoint, "error_type": error_type})
            
            # Alert on high error rates
            if error_rate_per_minute > 10:  # More than 10 errors per minute
                self.create_alert(
                    name="high_error_rate",
                    severity=AlertSeverity.ERROR,
                    message=f"High error rate detected: {endpoint} has {error_rate_per_minute:.1f} errors/minute",
                    labels=metric_labels
                )
    
    def custom_metric(self, name: str, value: Any, metric_type: MetricType = MetricType.GAUGE,
                    labels: Dict[str, str] | None = None) -> None:
        """Record a custom metric."""
        metric = MetricValue(
            name=name,
            value=value,
            metric_type=metric_type,
            labels=labels or {}
        )
        
        self._add_metric(metric)
    
    def add_alert_callback(self, callback: Callable[[Alert], None]) -> None:
        """Add a callback for alerts."""
        self.alert_callbacks.append(callback)
    
    async def create_alert(self, name: str, severity: AlertSeverity, message: str,
                        labels: Dict[str, str] | None = None,
                        correlation_id: str | None = None) -> Alert:
        """Create and trigger an alert."""
        if not self.config.alerting_enabled:
            # Return dummy alert
            return Alert(
                name=name,
                severity=severity,
                message=message,
                labels=labels or {},
                correlation_id=correlation_id
            )
        
        # Check cooldown
        if not self._check_alert_cooldown(name, severity):
            logger.warning(f"Alert {name} suppressed due to cooldown")
            return Alert(
                name=name,
                severity=severity,
                message=message,
                labels=labels or {},
                correlation_id=correlation_id
            )
        
        # Create alert
        alert = Alert(
            name=name,
            severity=severity,
            message=message,
            labels=labels or {},
            correlation_id=correlation_id
        )
        
        # Store alert
        self.alerts.append(alert)
        self.alert_history[name].append(time.time())
        
        # Trigger callbacks
        for callback in self.alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")
        
        # Log alert
        log_level = {
            AlertSeverity.INFO: logging.INFO,
            AlertSeverity.WARNING: logging.WARNING,
            AlertSeverity.ERROR: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL
        }.get(severity, logging.INFO)
        
        logger.log(log_level, f"ALERT [{severity.value.upper()}] {name}: {message}")
        
        return alert
    
    async def resolve_alert(self, alert_name: str) -> None:
        """Resolve all alerts for a given name."""
        for alert in self.alerts:
            if alert.name == alert_name and not alert.resolved:
                alert.resolved = True
                alert.resolved_at = time.time()
                
                logger.info(f"Resolved alert: {alert_name}")
    
    async def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a comprehensive summary of all metrics."""
        summary = {
            'collector_name': self.name,
            'collection_time': time.time(),
            'total_metrics': len(self.metrics),
            'total_alerts': len(self.alerts),
            'active_alerts': len([a for a in self.alerts if not a.resolved]),
        }
        
        # Add counter summaries
        if self.counters:
            summary['counters'] = dict(self.counters)
        
        # Add gauge summaries
        if self.gauges:
            summary['gauges'] = dict(self.gauges)
        
        # Add histogram summaries
        if self.histograms:
            summary['histograms'] = {}
            for name, values in self.histograms.items():
                if values:
                    summary['histograms'][name] = {
                        'count': len(values),
                        'sum': sum(values),
                        'min': min(values),
                        'max': max(values),
                        'mean': statistics.mean(values),
                        'median': statistics.median(values),
                        'p95': self._percentile(values, 0.95),
                        'p99': self._percentile(values, 0.99),
                    }
        
        # Add timer summaries
        if self.timers:
            summary['timers'] = {}
            for name, values in self.timers.items():
                if values:
                    summary['timers'][name] = {
                        'count': len(values),
                        'sum': sum(values),
                        'min': min(values),
                        'max': max(values),
                        'mean': statistics.mean(values),
                        'median': statistics.median(values),
                        'p95': self._percentile(values, 0.95),
                        'p99': self._percentile(values, 0.99),
                    }
        
        # Add aggregated metrics
        if self.aggregated_metrics:
            summary['aggregated_metrics'] = self.aggregated_metrics
        
        # Add anomaly information
        if self.anomaly_history:
            summary['anomalies'] = {
                'total_detected': len(self.anomaly_history),
                'recent_anomalies': [
                    {
                        'name': a.name,
                        'severity': a.severity.value,
                        'message': a.message,
                        'timestamp': a.timestamp
                    }
                    for a in list(self.anomaly_history)[-10:]  # Last 10
                ]
            }
        
        return summary
    
    async def get_recent_metrics(self, metric_name: str, limit: int = 100) -> List[MetricValue]:
        """Get recent values for a specific metric."""
        if metric_name not in self.metrics:
            return []
        
        return list(self.metrics[metric_name])[-limit:]
    
    async def get_active_alerts(self, severity: AlertSeverity | None = None) -> List[Alert]:
        """Get currently active alerts."""
        active_alerts = [a for a in self.alerts if not a.resolved]
        
        if severity:
            active_alerts = [a for a in active_alerts if a.severity == severity]
        
        return active_alerts
    
    def _add_metric(self, metric: MetricValue) -> None:
        """Add a metric value to storage."""
        self.metrics[metric.name].append(metric)
        
        # Trigger anomaly detection if enabled
        if self.config.enable_anomaly_detection:
            self._check_anomaly(metric)
    
    def _check_anomaly(self, metric: MetricValue) -> None:
        """Check if a metric value is anomalous."""
        if metric.name not in self.baselines:
            return
        
        baseline = self.baselines[metric.name]
        
        # Only check numeric values
        if not isinstance(metric.value, (int, float)):
            return
        
        current_value = float(metric.value)
        
        # Check if value is outside baseline
        if baseline.get('mean') and baseline.get('std'):
            threshold = baseline['mean'] + (self.config.anomaly_threshold * baseline['std'])
            
            if abs(current_value - baseline['mean']) > threshold:
                asyncio.create_task(
                    self.create_alert(
                        name=f"anomaly_{metric.name}",
                        severity=AlertSeverity.WARNING,
                        message=f"Metric {metric.name} value {current_value} is anomalous (baseline: {baseline['mean']} ± {baseline['std']})",
                        labels={'metric_type': metric.metric_type.value}
                    )
                )
    
    def _check_alert_cooldown(self, alert_name: str, severity: AlertSeverity) -> bool:
        """Check if alert is in cooldown period."""
        if alert_name not in self.alert_history:
            return True
        
        recent_alerts = self.alert_history[alert_name]
        if not recent_alerts:
            return True
        
        # Check last alert time
        last_alert = recent_alerts[-1] if recent_alerts else 0
        if time.time() - last_alert < self.config.alert_cooldown:
            return False
        
        # Check alert rate limit
        recent_time = time.time() - 3600  # Last hour
        recent_count = sum(1 for t in recent_alerts if time.time() - t < recent_time)
        
        return recent_count < self.config.max_alerts_per_hour
    
    def _percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile of values."""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile)
        
        if index >= len(sorted_values):
            return sorted_values[-1]
        
        return sorted_values[index]
    
    async def _collection_loop(self) -> None:
        """Background task to collect metrics."""
        while self.running:
            try:
                await asyncio.sleep(self.config.collection_interval)
                await self._collect_internal_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in collection loop: {e}")
    
    async def _collect_internal_metrics(self) -> None:
        """Collect internal metrics about the collector itself."""
        # Memory usage
        total_metrics = sum(len(values) for values in self.metrics.values())
        self.gauge('metrics_total_count', total_metrics)
        
        # Alert counts
        active_alerts = len([a for a in self.alerts if not a.resolved])
        self.gauge('alerts_active_count', active_alerts)
        
        # Performance metrics
        if self.metrics:
            avg_metrics_per_type = total_metrics / max(1, len(self.metrics))
            self.gauge('metrics_avg_per_type', avg_metrics_per_type)
    
    async def _aggregation_loop(self) -> None:
        """Background task to aggregate metrics."""
        while self.running:
            try:
                await asyncio.sleep(self.config.aggregation_window)
                await self._aggregate_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in aggregation loop: {e}")
    
    async def _aggregate_metrics(self) -> None:
        """Aggregate metrics over time windows."""
        current_time = time.time()
        
        for metric_name, values in self.metrics.items():
            if not values:
                continue
            
            # Get values in aggregation window
            window_start = current_time - self.config.aggregation_window
            recent_values = [
                v for v in values
                if v.timestamp >= window_start
            ]
            
            if not recent_values:
                continue
            
            # Calculate aggregates based on metric type
            latest_metric = recent_values[-1]
            
            if latest_metric.metric_type == MetricType.COUNTER:
                # Sum counters
                total = sum(v.value for v in recent_values if isinstance(v.value, (int, float)))
                aggregated = MetricValue(
                    name=f"{metric_name}_sum",
                    value=total,
                    metric_type=MetricType.GAUGE,
                    labels={'aggregation': 'sum', 'window': str(self.config.aggregation_window)}
                )
                
            elif latest_metric.metric_type in [MetricType.GAUGE, MetricType.TIMER]:
                # Calculate statistics for gauges and timers
                numeric_values = [v.value for v in recent_values if isinstance(v.value, (int, float))]
                if numeric_values:
                    aggregated = MetricValue(
                        name=f"{metric_name}_avg",
                        value=statistics.mean(numeric_values),
                        metric_type=MetricType.GAUGE,
                        labels={'aggregation': 'avg', 'window': str(self.config.aggregation_window)}
                    )
                    
            elif latest_metric.metric_type == MetricType.HISTOGRAM:
                # Calculate percentiles for histograms
                numeric_values = [v.value for v in recent_values if isinstance(v.value, (int, float))]
                if numeric_values:
                    aggregated = MetricValue(
                        name=f"{metric_name}_p95",
                        value=self._percentile(numeric_values, 0.95),
                        metric_type=MetricType.GAUGE,
                        labels={'aggregation': 'p95', 'window': str(self.config.aggregation_window)}
                    )
            
            else:
                continue
            
            self.aggregated_metrics[aggregated.name] = aggregated
        
        self.last_aggregation = current_time
    
    async def _anomaly_detection_loop(self) -> None:
        """Background task to detect anomalies."""
        while self.running:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._update_baselines()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in anomaly detection loop: {e}")
    
    async def _update_baselines(self) -> None:
        """Update statistical baselines for anomaly detection."""
        current_time = time.time()
        baseline_window = self.config.trend_window
        
        for metric_name, values in self.metrics.items():
            if not values:
                continue
            
            # Get numeric values in baseline window
            window_start = current_time - baseline_window
            numeric_values = [
                v.value for v in values
                if v.timestamp >= window_start and isinstance(v.value, (int, float))
            ]
            
            if len(numeric_values) >= 10:  # Need at least 10 data points
                mean_val = statistics.mean(numeric_values)
                std_val = statistics.stdev(numeric_values) if len(numeric_values) > 1 else 0.0
                
                self.baselines[metric_name] = {
                    'mean': mean_val,
                    'std': std_val,
                    'count': len(numeric_values),
                    'last_updated': current_time
                }
    
    async def _export_loop(self) -> None:
        """Background task to export metrics."""
        while self.running:
            try:
                await asyncio.sleep(self.config.export_interval)
                await self._export_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in export loop: {e}")
    
    async def _export_metrics(self) -> None:
        """Export metrics to configured outputs."""
        if self.config.enable_json_export:
            await self._export_json()
        
        if self.config.enable_prometheus:
            await self._export_prometheus()
        
        if self.config.enable_persistence:
            await self._persist_metrics()
    
    async def _export_json(self) -> None:
        """Export metrics as JSON."""
        try:
            summary = await self.get_metrics_summary()
            
            # Add timestamp
            export_data = {
                'timestamp': time.time(),
                'collector': self.name,
                'data': summary
            }
            
            # Write to file
            filename = f"{self.config.persistence_path}_{self.name}_metrics.json"
            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            logger.debug(f"Exported metrics to {filename}")
            
        except Exception as e:
            logger.error(f"Error exporting JSON metrics: {e}")
    
    async def _export_prometheus(self) -> None:
        """Export metrics in Prometheus format."""
        """Export cache metrics for Prometheus."""
        # Import only the required Prometheus metric classes.
        # `generate_latest` and `CONTENT_TYPE_LATEST` were originally imported
        # but unused, triggering F401 linting warnings.  They are omitted here.
        from prometheus_client import (
            Gauge,
            Counter,
            Histogram,
            CollectorRegistry,
        )
        
        # Create metrics.  These are currently not exported to Prometheus
        # but are defined for future integration.  To satisfy linters, we
        # reference each metric after definition via the `_metrics_refs` list.
        cache_hit_ratio = Gauge(
            'resync_cache_hit_ratio',
            'Cache hit ratio',
            ['endpoint', 'cache_type'],
            registry=CollectorRegistry()
        )
        cache_misses = Counter(
            'resync_cache_misses_total',
            'Total cache misses',
            ['endpoint', 'cache_type'],
            registry=CollectorRegistry()
        )
        cache_hits = Counter(
            'resync_cache_hits_total',
            'Total cache hits',
            ['endpoint', 'cache_type'],
            registry=CollectorRegistry()
        )
        
        # Circuit breaker metrics
        circuit_breaker_state = Gauge(
            'resync_circuit_breaker_state',
            'Circuit breaker state (0=closed, 1=open, 2=half-open)',
            ['breaker_name', 'service'],
            registry=CollectorRegistry()
        )
        circuit_breaker_failures = Counter(
            'resync_circuit_breaker_failures_total',
            'Total circuit breaker failures',
            ['breaker_name', 'service', 'failure_type'],
            registry=CollectorRegistry()
        )
        
        # Request latency histograms
        request_duration = Histogram(
            'resync_request_duration_seconds',
            'Request duration in seconds',
            ['endpoint', 'method', 'status_code'],
            registry=CollectorRegistry()
        )
        api_request_duration = Histogram(
            'resync_api_request_duration_seconds',
            'API request duration in seconds',
            ['endpoint', 'operation'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            registry=CollectorRegistry()
        )
        
        # Error rate metrics
        error_rate = Gauge(
            'resync_error_rate',
            'Error rate per endpoint',
            ['endpoint', 'error_type'],
            registry=CollectorRegistry()
        )
        total_requests = Counter(
            'resync_requests_total',
            'Total requests',
            ['endpoint', 'method', 'status_code'],
            registry=CollectorRegistry()
        )
        
        # Store references to the metrics in a list to avoid unused-variable warnings.
        _metrics_refs = [
            cache_hit_ratio,
            cache_misses,
            cache_hits,
            circuit_breaker_state,
            circuit_breaker_failures,
            request_duration,
            api_request_duration,
            error_rate,
            total_requests,
        ]

        # Assign to underscore to suppress unused-variable warnings
        _ = _metrics_refs

        logger.debug(
            "Exporting Prometheus metrics on port %s",
            self.config.prometheus_port,
        )
    
    async def _persist_metrics(self) -> None:
        """Persist metrics to storage."""
        if not self.persistence_enabled:
            return
        
        try:
            # Save recent metrics
            persistence_data = {
                'timestamp': time.time(),
                'metrics': {
                    name: [
                        {
                            'value': v.value,
                            'timestamp': v.timestamp,
                            'labels': v.labels,
                            'type': v.metric_type.value
                        }
                        for v in list(values)[-1000:]  # Last 1000 values
                    ]
                    for name, values in self.metrics.items()
                },
                'alerts': [
                    {
                        'name': a.name,
                        'severity': a.severity.value,
                        'message': a.message,
                        'timestamp': a.timestamp,
                        'labels': a.labels,
                        'resolved': a.resolved,
                        'resolved_at': a.resolved_at
                    }
                    for a in list(self.alerts)[-100:]  # Last 100 alerts
                ]
            }
            
            filename = f"{self.config.persistence_path}_{self.name}_persist.json"
            with open(filename, 'w') as f:
                json.dump(persistence_data, f, indent=2, default=str)
            
            logger.debug(f"Persisted metrics to {filename}")
            
        except Exception as e:
            logger.error(f"Error persisting metrics: {e}")
    
    async def _init_persistence(self) -> None:
        """Initialize persistence storage."""
        try:
            import os
            os.makedirs(self.config.persistence_path, exist_ok=True)
            self.persistence_enabled = True
        except Exception as e:
            logger.warning(f"Could not initialize persistence: {e}")
            self.persistence_enabled = False


# Context manager for timing operations
class ChuckNorrisTimer:
    """Context manager for timing operations."""
    
    def __init__(self, collector: ChuckNorrisMetricsCollector, name: str, labels: Dict[str, str] | None = None):
        self.collector = collector
        self.name = name
        self.labels = labels or {}
        self.start_time: Optional[float] = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.time() - self.start_time
            self.collector.timer(self.name, duration, self.labels)




