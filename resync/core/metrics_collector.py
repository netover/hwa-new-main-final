"""
Metrics Collection System with Prometheus and Grafana Integration.

This module provides comprehensive metrics collection and visualization capabilities including:
- Prometheus-compatible metrics endpoint
- Automatic system metrics collection
- Custom business metrics registration
- Grafana dashboard generation
- Alerting rules configuration
- Performance metrics tracking
- Health status monitoring
- Security metrics integration
- Real-time metrics streaming
- Metrics aggregation and analysis
"""

from __future__ import annotations

import asyncio
import json
import psutil
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable

import aiohttp
from aiohttp import web

from resync.core.structured_logger import get_logger

logger = get_logger(__name__)


class MetricType(Enum):
    """Types of metrics supported."""

    COUNTER = "counter"  # Monotonically increasing value
    GAUGE = "gauge"  # Value that can go up and down
    HISTOGRAM = "histogram"  # Distribution of values
    SUMMARY = "summary"  # Quantiles and sum


class MetricCategory(Enum):
    """Metric categories for organization."""

    SYSTEM = "system"
    APPLICATION = "application"
    BUSINESS = "business"
    SECURITY = "security"
    PERFORMANCE = "performance"
    HEALTH = "health"


@dataclass
class MetricDefinition:
    """Definition of a metric."""

    name: str
    description: str
    metric_type: MetricType
    category: MetricCategory
    unit: str = ""
    labels: List[str] = field(default_factory=list)
    buckets: Optional[List[float]] = None  # For histograms

    def get_prometheus_name(self) -> str:
        """Get Prometheus-compatible metric name."""
        return self.name.replace(".", "_").replace("-", "_")

    def to_prometheus_format(
        self, value: Union[int, float], labels: Optional[Dict[str, str]] = None
    ) -> str:
        """Convert metric to Prometheus format."""
        prom_name = self.get_prometheus_name()
        label_str = ""

        if labels:
            label_parts = [f'{k}="{v}"' for k, v in labels.items()]
            label_str = f"{{{','.join(label_parts)}}}"

        return f"{prom_name}{label_str} {value}"


@dataclass
class MetricValue:
    """A metric value with metadata."""

    definition: MetricDefinition
    value: Union[int, float]
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_prometheus(self) -> str:
        """Convert to Prometheus format."""
        return self.definition.to_prometheus_format(self.value, self.labels)


@dataclass
class AlertRule:
    """Prometheus alerting rule."""

    name: str
    query: str
    duration: str = "5m"
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)

    def to_prometheus_rule(self) -> Dict[str, Any]:
        """Convert to Prometheus rule format."""
        return {
            "alert": self.name,
            "expr": self.query,
            "for": self.duration,
            "labels": self.labels,
            "annotations": self.annotations,
        }


@dataclass
class GrafanaDashboard:
    """Grafana dashboard configuration."""

    title: str
    description: str
    tags: List[str] = field(default_factory=lambda: ["hwa-new", "auto-generated"])
    panels: List[Dict[str, Any]] = field(default_factory=list)
    time_range: Dict[str, str] = field(
        default_factory=lambda: {"from": "now-1h", "to": "now"}
    )
    refresh: str = "30s"

    def to_grafana_format(self) -> Dict[str, Any]:
        """Convert to Grafana dashboard JSON format."""
        return {
            "dashboard": {
                "title": self.title,
                "description": self.description,
                "tags": self.tags,
                "panels": self.panels,
                "time": self.time_range,
                "refresh": self.refresh,
                "schemaVersion": 27,
                "version": 1,
                "links": [],
                "templating": {"list": []},
                "annotations": {"list": []},
                "editable": True,
                "gnetId": None,
                "graphTooltip": 0,
                "hideControls": False,
                "id": None,
                "style": "dark",
                "timezone": "browser",
            }
        }


@dataclass
class MetricsCollectorConfig:
    """Configuration for metrics collection system."""

    # Prometheus configuration
    prometheus_port: int = 9090
    prometheus_path: str = "/metrics"
    collect_interval_seconds: int = 15

    # System metrics
    enable_system_metrics: bool = True
    enable_process_metrics: bool = True

    # Application metrics
    enable_http_metrics: bool = True
    enable_db_metrics: bool = True
    enable_cache_metrics: bool = True

    # Business metrics
    enable_business_metrics: bool = True

    # Grafana integration
    grafana_url: Optional[str] = None
    grafana_api_key: Optional[str] = None
    auto_create_dashboards: bool = True

    # Alerting
    enable_alerting: bool = True
    alert_rules_file: str = "alert_rules.yml"

    # Performance
    max_metrics_buffer: int = 10000
    metrics_retention_hours: int = 24


class MetricsCollector:
    """
    Comprehensive metrics collection system with Prometheus and Grafana integration.

    Features:
    - Prometheus-compatible metrics endpoint
    - Automatic system and application metrics
    - Custom business metrics registration
    - Grafana dashboard auto-generation
    - Alerting rules management
    - Real-time metrics streaming
    - Performance and health monitoring
    """

    def __init__(self, config: Optional[MetricsCollectorConfig] = None):
        self.config = config or MetricsCollectorConfig()

        # Core components
        self.metrics_definitions: Dict[str, MetricDefinition] = {}
        self.metrics_buffer: deque = deque(maxlen=self.config.max_metrics_buffer)
        self.custom_collectors: List[Callable] = []

        # HTTP server for Prometheus endpoint
        self.http_app: Optional[web.Application] = None
        self.http_runner: Optional[web.AppRunner] = None

        # Grafana integration
        self.grafana_session: Optional[aiohttp.ClientSession] = None

        # Alerting
        self.alert_rules: List[AlertRule] = []

        # Runtime state
        self._running = False
        self._collection_task: Optional[asyncio.Task] = None
        self._http_task: Optional[asyncio.Task] = None

        # Initialize standard metrics
        self._initialize_standard_metrics()

    def _initialize_standard_metrics(self) -> None:
        """Initialize standard metrics definitions."""
        standard_metrics = [
            # System metrics
            MetricDefinition(
                name="system.cpu.usage",
                description="CPU usage percentage",
                metric_type=MetricType.GAUGE,
                category=MetricCategory.SYSTEM,
                unit="percent",
            ),
            MetricDefinition(
                name="system.memory.usage",
                description="Memory usage percentage",
                metric_type=MetricType.GAUGE,
                category=MetricCategory.SYSTEM,
                unit="percent",
            ),
            MetricDefinition(
                name="system.disk.usage",
                description="Disk usage percentage",
                metric_type=MetricType.GAUGE,
                category=MetricCategory.SYSTEM,
                unit="percent",
                labels=["mount_point"],
            ),
            # Application metrics
            MetricDefinition(
                name="app.http.requests.total",
                description="Total HTTP requests",
                metric_type=MetricType.COUNTER,
                category=MetricCategory.APPLICATION,
                labels=["method", "endpoint", "status"],
            ),
            MetricDefinition(
                name="app.http.request.duration",
                description="HTTP request duration",
                metric_type=MetricType.HISTOGRAM,
                category=MetricCategory.APPLICATION,
                unit="seconds",
                labels=["method", "endpoint"],
                buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0],
            ),
            # Performance metrics
            MetricDefinition(
                name="app.performance.response_time",
                description="Application response time",
                metric_type=MetricType.HISTOGRAM,
                category=MetricCategory.PERFORMANCE,
                unit="seconds",
                buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
            ),
            MetricDefinition(
                name="app.performance.error_rate",
                description="Application error rate",
                metric_type=MetricType.GAUGE,
                category=MetricCategory.PERFORMANCE,
                unit="percent",
            ),
            # Security metrics
            MetricDefinition(
                name="security.auth.attempts",
                description="Authentication attempts",
                metric_type=MetricType.COUNTER,
                category=MetricCategory.SECURITY,
                labels=["result", "method"],
            ),
            MetricDefinition(
                name="security.threats.detected",
                description="Security threats detected",
                metric_type=MetricType.COUNTER,
                category=MetricCategory.SECURITY,
                labels=["threat_type", "severity"],
            ),
            # Health metrics
            MetricDefinition(
                name="health.service.status",
                description="Service health status",
                metric_type=MetricType.GAUGE,
                category=MetricCategory.HEALTH,
                labels=["service", "component"],
            ),
            # Business metrics
            MetricDefinition(
                name="business.transactions.total",
                description="Total business transactions",
                metric_type=MetricType.COUNTER,
                category=MetricCategory.BUSINESS,
                labels=["type", "status"],
            ),
            MetricDefinition(
                name="business.user.sessions",
                description="Active user sessions",
                metric_type=MetricType.GAUGE,
                category=MetricCategory.BUSINESS,
            ),
        ]

        for metric in standard_metrics:
            self.metrics_definitions[metric.name] = metric

    async def start(self) -> None:
        """Start the metrics collection system."""
        if self._running:
            return

        self._running = True

        # Start HTTP server for Prometheus endpoint
        await self._start_http_server()

        # Start Grafana integration
        if self.config.grafana_url:
            await self._initialize_grafana()

        # Start metrics collection
        self._collection_task = asyncio.create_task(self._metrics_collection_worker())

        # Load alert rules
        if self.config.enable_alerting:
            await self._load_alert_rules()

        logger.info("Metrics collector started")

    async def stop(self) -> None:
        """Stop the metrics collection system."""
        if not self._running:
            return

        self._running = False

        # Stop HTTP server
        if self.http_runner:
            await self.http_runner.cleanup()

        # Close Grafana session
        if self.grafana_session:
            await self.grafana_session.close()

        # Cancel tasks
        for task in [self._collection_task, self._http_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        logger.info("Metrics collector stopped")

    async def _start_http_server(self) -> None:
        """Start HTTP server for Prometheus metrics endpoint."""
        self.http_app = web.Application()

        # Add metrics endpoint
        self.http_app.router.add_get(
            self.config.prometheus_path, self._metrics_endpoint
        )

        # Add health endpoint
        self.http_app.router.add_get("/health", self._health_endpoint)

        self.http_runner = web.AppRunner(self.http_app)
        await self.http_runner.setup()

        site = web.TCPSite(self.http_runner, "0.0.0.0", self.config.prometheus_port)
        await site.start()

        logger.info(
            f"Metrics HTTP server started on port {self.config.prometheus_port}"
        )

    async def _initialize_grafana(self) -> None:
        """Initialize Grafana integration."""
        if not self.config.grafana_url or not self.config.grafana_api_key:
            return

        headers = {
            "Authorization": f"Bearer {self.config.grafana_api_key}",
            "Content-Type": "application/json",
        }

        self.grafana_session = aiohttp.ClientSession(headers=headers)

        # Test connection
        try:
            async with self.grafana_session.get(
                f"{self.config.grafana_url}/api/health"
            ) as response:
                if response.status == 200:
                    logger.info("Grafana integration initialized")
                    if self.config.auto_create_dashboards:
                        await self._create_standard_dashboards()
                else:
                    logger.warning("Grafana connection failed")
        except Exception as e:
            logger.error(f"Grafana initialization failed: {e}")

    async def _load_alert_rules(self) -> None:
        """Load alerting rules."""
        # Default alert rules
        self.alert_rules = [
            AlertRule(
                name="HighCPUUsage",
                query="system_cpu_usage > 90",
                duration="5m",
                labels={"severity": "warning"},
                annotations={
                    "summary": "High CPU usage detected",
                    "description": "CPU usage is above 90% for more than 5 minutes",
                },
            ),
            AlertRule(
                name="HighMemoryUsage",
                query="system_memory_usage > 95",
                duration="2m",
                labels={"severity": "critical"},
                annotations={
                    "summary": "High memory usage detected",
                    "description": "Memory usage is above 95% for more than 2 minutes",
                },
            ),
            AlertRule(
                name="HighErrorRate",
                query='rate(app_http_requests_total{status=~"5.."}[5m]) / rate(app_http_requests_total[5m]) > 0.1',
                duration="5m",
                labels={"severity": "critical"},
                annotations={
                    "summary": "High error rate detected",
                    "description": "HTTP error rate is above 10% for more than 5 minutes",
                },
            ),
        ]

        logger.info(f"Loaded {len(self.alert_rules)} alert rules")

    def register_metric(self, definition: MetricDefinition) -> None:
        """Register a custom metric definition."""
        self.metrics_definitions[definition.name] = definition
        logger.info(f"Registered custom metric: {definition.name}")

    def add_custom_collector(self, collector: Callable) -> None:
        """Add a custom metrics collector function."""
        self.custom_collectors.append(collector)
        logger.info("Added custom metrics collector")

    def record_metric(
        self,
        name: str,
        value: Union[int, float],
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a metric value."""
        if name not in self.metrics_definitions:
            logger.warning(f"Metric {name} not registered, ignoring")
            return

        metric_value = MetricValue(
            definition=self.metrics_definitions[name], value=value, labels=labels or {}
        )

        self.metrics_buffer.append(metric_value)

    def increment_counter(
        self, name: str, labels: Optional[Dict[str, str]] = None, value: int = 1
    ) -> None:
        """Increment a counter metric."""
        definition = self.metrics_definitions.get(name)
        if not definition or definition.metric_type != MetricType.COUNTER:
            logger.warning(f"Invalid counter metric: {name}")
            return

        # For counters, we need to maintain state
        # This is a simplified implementation
        self.record_metric(name, value, labels)

    def set_gauge(
        self,
        name: str,
        value: Union[int, float],
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Set a gauge metric value."""
        definition = self.metrics_definitions.get(name)
        if not definition or definition.metric_type != MetricType.GAUGE:
            logger.warning(f"Invalid gauge metric: {name}")
            return

        self.record_metric(name, value, labels)

    def observe_histogram(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Observe a value in a histogram metric."""
        definition = self.metrics_definitions.get(name)
        if not definition or definition.metric_type != MetricType.HISTOGRAM:
            logger.warning(f"Invalid histogram metric: {name}")
            return

        self.record_metric(name, value, labels)

    async def _metrics_endpoint(self, request: web.Request) -> web.Response:
        """Prometheus metrics endpoint."""
        # Collect current metrics
        await self._collect_system_metrics()
        await self._collect_application_metrics()

        # Run custom collectors
        for collector in self.custom_collectors:
            try:
                await collector()
            except Exception as e:
                logger.error(f"Custom collector failed: {e}")

        # Format as Prometheus text format
        output_lines = [
            "# HELP hwa_new_metrics HWA-New application metrics",
            "# TYPE hwa_new_metrics gauge",
            f'hwa_new_metrics {{service="hwa-new",version="1.0.0"}} 1',
            "",
        ]

        # Group metrics by name
        metrics_by_name: Dict[str, List[MetricValue]] = defaultdict(list)
        for metric in self.metrics_buffer:
            metrics_by_name[metric.definition.name].append(metric)

        # Format each metric
        for metric_name, values in metrics_by_name.items():
            definition = values[0].definition

            # Metric metadata
            output_lines.append(
                f"# HELP {definition.get_prometheus_name()} {definition.description}"
            )
            output_lines.append(
                f"# TYPE {definition.get_prometheus_name()} {definition.metric_type.value}"
            )

            # Metric values
            for value in values[-10:]:  # Last 10 values to avoid duplicates
                prom_line = value.to_prometheus()
                output_lines.append(prom_line)

            output_lines.append("")

        response_text = "\n".join(output_lines)
        return web.Response(
            text=response_text, content_type="text/plain; charset=utf-8"
        )

    async def _health_endpoint(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        health_data = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "metrics": {
                "buffer_size": len(self.metrics_buffer),
                "definitions_count": len(self.metrics_definitions),
                "custom_collectors": len(self.custom_collectors),
            },
        }

        return web.json_response(health_data)

    async def _collect_system_metrics(self) -> None:
        """Collect system-level metrics."""
        if not self.config.enable_system_metrics:
            return

        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.set_gauge("system.cpu.usage", cpu_percent)

            # Memory usage
            memory = psutil.virtual_memory()
            self.set_gauge("system.memory.usage", memory.percent)

            # Disk usage
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    self.set_gauge(
                        "system.disk.usage",
                        usage.percent,
                        {"mount_point": partition.mountpoint},
                    )
                except PermissionError:
                    continue

        except Exception as e:
            logger.error(f"System metrics collection failed: {e}")

    async def _collect_application_metrics(self) -> None:
        """Collect application-level metrics."""
        # This would integrate with the actual application components
        # For now, collect basic process metrics

        if self.config.enable_process_metrics:
            try:
                process = psutil.Process()
                memory_info = process.memory_info()

                # Process memory usage
                self.set_gauge("app.process.memory_rss", memory_info.rss)
                self.set_gauge("app.process.memory_vms", memory_info.vms)

                # CPU usage
                cpu_percent = process.cpu_percent()
                self.set_gauge("app.process.cpu_percent", cpu_percent)

            except Exception as e:
                logger.error(f"Process metrics collection failed: {e}")

    async def _create_standard_dashboards(self) -> None:
        """Create standard Grafana dashboards."""
        if not self.grafana_session:
            return

        dashboards = [
            self._create_system_dashboard(),
            self._create_application_dashboard(),
            self._create_security_dashboard(),
            self._create_business_dashboard(),
        ]

        for dashboard in dashboards:
            try:
                async with self.grafana_session.post(
                    f"{self.config.grafana_url}/api/dashboards/db",
                    json=dashboard.to_grafana_format(),
                ) as response:
                    if response.status == 200:
                        logger.info(f"Created Grafana dashboard: {dashboard.title}")
                    else:
                        logger.warning(
                            f"Failed to create dashboard {dashboard.title}: {response.status}"
                        )
            except Exception as e:
                logger.error(f"Dashboard creation failed: {e}")

    def _create_system_dashboard(self) -> GrafanaDashboard:
        """Create system metrics dashboard."""
        dashboard = GrafanaDashboard(
            title="HWA-New System Metrics",
            description="System-level metrics for HWA-New",
        )

        # CPU Usage Panel
        cpu_panel = {
            "title": "CPU Usage",
            "type": "graph",
            "targets": [{"expr": "system_cpu_usage", "legendFormat": "CPU Usage %"}],
            "yAxes": [{"unit": "percent"}],
        }

        # Memory Usage Panel
        memory_panel = {
            "title": "Memory Usage",
            "type": "graph",
            "targets": [
                {"expr": "system_memory_usage", "legendFormat": "Memory Usage %"}
            ],
            "yAxes": [{"unit": "percent"}],
        }

        dashboard.panels = [cpu_panel, memory_panel]
        return dashboard

    def _create_application_dashboard(self) -> GrafanaDashboard:
        """Create application metrics dashboard."""
        dashboard = GrafanaDashboard(
            title="HWA-New Application Metrics",
            description="Application-level metrics for HWA-New",
        )

        # HTTP Requests Panel
        http_panel = {
            "title": "HTTP Requests",
            "type": "graph",
            "targets": [
                {
                    "expr": "rate(app_http_requests_total[5m])",
                    "legendFormat": "Requests/sec",
                }
            ],
        }

        # Response Time Panel
        response_time_panel = {
            "title": "Response Time",
            "type": "heatmap",
            "targets": [
                {"expr": "app_http_request_duration_bucket", "legendFormat": "{{le}}"}
            ],
        }

        dashboard.panels = [http_panel, response_time_panel]
        return dashboard

    def _create_security_dashboard(self) -> GrafanaDashboard:
        """Create security metrics dashboard."""
        dashboard = GrafanaDashboard(
            title="HWA-New Security Metrics",
            description="Security-related metrics for HWA-New",
        )

        # Authentication Attempts Panel
        auth_panel = {
            "title": "Authentication Attempts",
            "type": "graph",
            "targets": [
                {
                    "expr": "rate(security_auth_attempts_total[5m])",
                    "legendFormat": "{{result}}",
                }
            ],
        }

        # Threats Detected Panel
        threats_panel = {
            "title": "Threats Detected",
            "type": "graph",
            "targets": [
                {
                    "expr": "rate(security_threats_detected_total[5m])",
                    "legendFormat": "{{threat_type}}",
                }
            ],
        }

        dashboard.panels = [auth_panel, threats_panel]
        return dashboard

    def _create_business_dashboard(self) -> GrafanaDashboard:
        """Create business metrics dashboard."""
        dashboard = GrafanaDashboard(
            title="HWA-New Business Metrics",
            description="Business-level metrics for HWA-New",
        )

        # Transactions Panel
        transactions_panel = {
            "title": "Business Transactions",
            "type": "graph",
            "targets": [
                {
                    "expr": "rate(business_transactions_total[5m])",
                    "legendFormat": "{{type}} - {{status}}",
                }
            ],
        }

        # User Sessions Panel
        sessions_panel = {
            "title": "Active User Sessions",
            "type": "singlestat",
            "targets": [
                {"expr": "business_user_sessions", "legendFormat": "Active Sessions"}
            ],
        }

        dashboard.panels = [transactions_panel, sessions_panel]
        return dashboard

    async def _metrics_collection_worker(self) -> None:
        """Background worker for periodic metrics collection."""
        while self._running:
            try:
                await asyncio.sleep(self.config.collect_interval_seconds)

                # Collect system metrics
                await self._collect_system_metrics()

                # Collect application metrics
                await self._collect_application_metrics()

                # Clean old metrics from buffer
                cutoff_time = time.time() - (self.config.metrics_retention_hours * 3600)
                while (
                    self.metrics_buffer
                    and self.metrics_buffer[0].timestamp < cutoff_time
                ):
                    self.metrics_buffer.popleft()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics collection worker error: {e}")

    def get_alert_rules_prometheus_format(self) -> str:
        """Get alert rules in Prometheus format."""
        rules = {
            "groups": [
                {
                    "name": "hwa_new_alerts",
                    "rules": [rule.to_prometheus_rule() for rule in self.alert_rules],
                }
            ]
        }
        return json.dumps(rules, indent=2)

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        metrics_by_category = defaultdict(int)
        for definition in self.metrics_definitions.values():
            metrics_by_category[definition.category.value] += 1

        return {
            "configuration": {
                "prometheus_port": self.config.prometheus_port,
                "collect_interval_seconds": self.config.collect_interval_seconds,
                "enable_system_metrics": self.config.enable_system_metrics,
                "enable_business_metrics": self.config.enable_business_metrics,
                "grafana_integration": self.config.grafana_url is not None,
            },
            "metrics": {
                "total_definitions": len(self.metrics_definitions),
                "by_category": dict(metrics_by_category),
                "buffer_size": len(self.metrics_buffer),
                "custom_collectors": len(self.custom_collectors),
            },
            "alerting": {
                "rules_count": len(self.alert_rules),
                "enabled": self.config.enable_alerting,
            },
            "health": {
                "running": self._running,
                "http_server_active": self.http_runner is not None,
            },
        }


# Global metrics collector instance
metrics_collector = MetricsCollector()


async def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    if not metrics_collector._running:
        await metrics_collector.start()
    return metrics_collector
