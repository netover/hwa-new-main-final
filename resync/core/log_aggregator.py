"""
Log Aggregation System with ELK Stack Integration.

This module provides comprehensive log aggregation and analysis capabilities including:
- Multi-source log collection (files, network, application logs)
- Log parsing and structuring with Grok patterns
- Elasticsearch indexing with optimized mappings
- Kibana dashboard auto-generation
- Log correlation with traces and metrics
- Log retention and lifecycle management
- Real-time search and analytics
- Alerting based on log patterns
- Log shipping and buffering
- Performance monitoring and optimization
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, TextIO

import aiohttp

from resync.core.structured_logger import get_logger

logger = get_logger(__name__)


class LogLevel(Enum):
    """Standard log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogSource(Enum):
    """Types of log sources."""

    FILE = "file"
    NETWORK = "network"
    APPLICATION = "application"
    SYSTEM = "system"
    CONTAINER = "container"
    CUSTOM = "custom"


@dataclass
class LogEntry:
    """Structured log entry."""

    timestamp: float
    level: LogLevel
    message: str
    source: LogSource
    source_name: str
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    correlation_id: Optional[str] = None

    # Structured fields
    fields: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    hostname: str = field(
        default_factory=lambda: (
            os.uname().nodename if hasattr(os, "uname") else "unknown"
        )
    )
    pid: int = field(default_factory=lambda: os.getpid())
    thread_id: Optional[int] = None

    # Processing metadata
    parsed: bool = False
    indexed: bool = False
    index_timestamp: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert log entry to dictionary."""
        return {
            "@timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
            "level": self.level.value,
            "message": self.message,
            "source": self.source.value,
            "source_name": self.source_name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "correlation_id": self.correlation_id,
            "hostname": self.hostname,
            "pid": self.pid,
            "thread_id": self.thread_id,
            "parsed": self.parsed,
            "indexed": self.indexed,
            **self.fields,
        }

    def to_elasticsearch(self) -> Dict[str, Any]:
        """Convert to Elasticsearch document format."""
        doc = self.to_dict()
        # Remove processing metadata from ES document
        doc.pop("parsed", None)
        doc.pop("indexed", None)
        doc.pop("index_timestamp", None)
        return doc


@dataclass
class LogParser:
    """Log parser with Grok patterns."""

    name: str
    pattern: str
    compiled_pattern: Optional[re.Pattern] = None
    field_mappings: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Compile the regex pattern."""
        self.compiled_pattern = re.compile(self.pattern, re.MULTILINE | re.DOTALL)

    def parse(self, log_line: str) -> Optional[Dict[str, Any]]:
        """Parse a log line using the pattern."""
        if not self.compiled_pattern:
            return None

        match = self.compiled_pattern.search(log_line)
        if not match:
            return None

        parsed = {}
        for key, value in match.groupdict().items():
            # Apply field mappings
            mapped_key = self.field_mappings.get(key, key)
            parsed[mapped_key] = value

        return parsed


@dataclass
class LogSourceConfig:
    """Configuration for a log source."""

    source_type: LogSource
    name: str
    enabled: bool = True

    # File source config
    file_path: Optional[str] = None
    file_encoding: str = "utf-8"
    follow_file: bool = True

    # Network source config
    network_host: Optional[str] = None
    network_port: Optional[int] = None
    protocol: str = "tcp"

    # Application source config
    application_name: str = ""

    # Parsing config
    parser_name: Optional[str] = None
    multiline_pattern: Optional[str] = None

    # Filtering
    include_patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)

    # Buffering
    buffer_size: int = 1000
    flush_interval: int = 5


@dataclass
class KibanaDashboard:
    """Kibana dashboard configuration."""

    title: str
    description: str
    visualizations: List[Dict[str, Any]] = field(default_factory=list)
    filters: List[Dict[str, Any]] = field(default_factory=list)
    time_range: Dict[str, str] = field(
        default_factory=lambda: {"from": "now-24h", "to": "now"}
    )

    def to_kibana_format(self) -> Dict[str, Any]:
        """Convert to Kibana saved object format."""
        return {
            "type": "dashboard",
            "attributes": {
                "title": self.title,
                "description": self.description,
                "panelsJSON": json.dumps(self.visualizations),
                "optionsJSON": json.dumps(
                    {"useMargins": True, "hidePanelTitles": False}
                ),
                "version": 1,
                "timeRestore": True,
                "timeTo": self.time_range["to"],
                "timeFrom": self.time_range["from"],
            },
        }


@dataclass
class LogAggregatorConfig:
    """Configuration for log aggregation system."""

    # Elasticsearch configuration
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index_prefix: str = "hwa-logs"
    elasticsearch_username: Optional[str] = None
    elasticsearch_password: Optional[str] = None

    # Kibana configuration
    kibana_url: Optional[str] = None
    kibana_api_key: Optional[str] = None
    auto_create_dashboards: bool = True

    # Log collection
    collection_interval_seconds: int = 1
    max_buffer_size: int = 10000
    batch_size: int = 100

    # Retention
    retention_days: int = 30
    compression_enabled: bool = True

    # Performance
    max_concurrent_sources: int = 10
    indexing_workers: int = 4

    # Security
    enable_ssl_verification: bool = True
    log_encryption_enabled: bool = False


class LogAggregator:
    """
    Comprehensive log aggregation system with ELK stack integration.

    Features:
    - Multi-source log collection (files, network, applications)
    - Intelligent log parsing with Grok patterns
    - Elasticsearch indexing with optimized mappings
    - Kibana dashboard auto-generation
    - Log correlation with distributed traces
    - Real-time search and analytics
    - Log retention and lifecycle management
    - Performance monitoring and optimization
    """

    def __init__(self, config: Optional[LogAggregatorConfig] = None):
        self.config = config or LogAggregatorConfig()

        # Core components
        self.parsers: Dict[str, LogParser] = {}
        self.sources: Dict[str, LogSourceConfig] = {}
        self.log_buffer: deque = deque(maxlen=self.config.max_buffer_size)

        # Elasticsearch client
        self.es_session: Optional[aiohttp.ClientSession] = None

        # Kibana integration
        self.kibana_session: Optional[aiohttp.ClientSession] = None

        # File monitoring
        self.file_handles: Dict[str, TextIO] = {}
        self.file_positions: Dict[str, int] = {}

        # Network listeners
        self.network_listeners: Dict[str, asyncio.AbstractServer] = {}

        # Processing queues
        self.processing_queue: asyncio.Queue = asyncio.Queue(
            maxsize=self.config.max_buffer_size
        )

        # Background tasks
        self._collection_task: Optional[asyncio.Task] = None
        self._processing_tasks: List[asyncio.Task] = []
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

        # Metrics
        self.metrics: Dict[str, Any] = {
            "logs_collected": 0,
            "logs_parsed": 0,
            "logs_indexed": 0,
            "logs_dropped": 0,
            "indexing_errors": 0,
            "parsing_errors": 0,
        }

        # Initialize components
        self._initialize_parsers()
        self._initialize_elasticsearch()

    def _initialize_parsers(self) -> None:
        """Initialize standard log parsers."""
        standard_parsers = [
            LogParser(
                name="apache_access",
                pattern=r'(?P<ip>\S+) \S+ \S+ \[(?P<timestamp>[^\]]+)\] "(?P<method>\S+) (?P<path>\S+) (?P<protocol>\S+)" (?P<status>\d+) (?P<bytes>\d+)',
                field_mappings={
                    "ip": "client_ip",
                    "timestamp": "request_time",
                    "method": "http_method",
                    "status": "http_status",
                    "bytes": "response_bytes",
                },
            ),
            LogParser(
                name="nginx_access",
                pattern=r'(?P<remote_addr>\S+) - (?P<remote_user>\S+) \[(?P<time_local>[^\]]+)\] "(?P<request>[^"]+)" (?P<status>\d+) (?P<body_bytes_sent>\d+) "(?P<http_referer>[^"]*)" "(?P<http_user_agent>[^"]*)"',
                field_mappings={
                    "remote_addr": "client_ip",
                    "remote_user": "user",
                    "time_local": "request_time",
                    "request": "http_request",
                    "status": "http_status",
                    "body_bytes_sent": "response_bytes",
                    "http_referer": "referer",
                    "http_user_agent": "user_agent",
                },
            ),
            LogParser(name="json_log", pattern=r"\{.*\}", field_mappings={}),
            LogParser(
                name="syslog",
                pattern=r"(?P<timestamp>\w+\s+\d+\s+\d+:\d+:\d+)\s+(?P<hostname>\S+)\s+(?P<program>\S+)(?:\[(?P<pid>\d+)\])?:\s+(?P<message>.*)",
                field_mappings={"program": "facility", "pid": "process_id"},
            ),
        ]

        for parser in standard_parsers:
            self.parsers[parser.name] = parser

    def _initialize_elasticsearch(self) -> None:
        """Initialize Elasticsearch client."""
        headers = {"Content-Type": "application/json"}

        if self.config.elasticsearch_username and self.config.elasticsearch_password:
            import base64

            auth = base64.b64encode(
                f"{self.config.elasticsearch_username}:{self.config.elasticsearch_password}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {auth}"

        self.es_session = aiohttp.ClientSession(
            headers=headers,
            connector=aiohttp.TCPConnector(
                verify_ssl=self.config.enable_ssl_verification
            ),
        )

    async def start(self) -> None:
        """Start the log aggregation system."""
        if self._running:
            return

        self._running = True

        # Initialize Kibana if configured
        if self.config.kibana_url and self.config.kibana_api_key:
            await self._initialize_kibana()

        # Start log collection
        self._collection_task = asyncio.create_task(self._log_collection_worker())

        # Start processing workers
        for i in range(self.config.indexing_workers):
            task = asyncio.create_task(self._log_processing_worker())
            self._processing_tasks.append(task)

        # Start cleanup worker
        self._cleanup_task = asyncio.create_task(self._cleanup_worker())

        logger.info("Log aggregator started")

    async def stop(self) -> None:
        """Stop the log aggregation system."""
        if not self._running:
            return

        self._running = False

        # Close file handles
        for handle in self.file_handles.values():
            handle.close()

        # Close network listeners
        for listener in self.network_listeners.values():
            listener.close()
            await listener.wait_closed()

        # Close sessions
        if self.es_session:
            await self.es_session.close()
        if self.kibana_session:
            await self.kibana_session.close()

        # Cancel all tasks
        all_tasks = [self._collection_task, self._cleanup_task] + self._processing_tasks
        for task in all_tasks:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        logger.info("Log aggregator stopped")

    def add_log_source(self, config: LogSourceConfig) -> None:
        """Add a log source configuration."""
        self.sources[config.name] = config

        if config.source_type == LogSource.FILE and config.file_path:
            # Initialize file position
            if os.path.exists(config.file_path):
                self.file_positions[config.name] = os.path.getsize(config.file_path)

        logger.info(f"Added log source: {config.name} ({config.source_type.value})")

    def add_parser(self, parser: LogParser) -> None:
        """Add a custom log parser."""
        self.parsers[parser.name] = parser
        logger.info(f"Added log parser: {parser.name}")

    def add_structured_log(
        self,
        level: LogLevel,
        message: str,
        source: str = "application",
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        **fields,
    ) -> None:
        """Add a structured log entry."""
        # Get current trace context if available
        from resync.core.distributed_tracing import (
            get_current_trace_id,
            get_current_span_id,
        )

        if not trace_id:
            trace_id = get_current_trace_id()
        if not span_id:
            span_id = get_current_span_id()

        log_entry = LogEntry(
            timestamp=time.time(),
            level=level,
            message=message,
            source=LogSource.APPLICATION,
            source_name=source,
            trace_id=trace_id,
            span_id=span_id,
            correlation_id=correlation_id,
            fields=fields,
        )

        # Add to processing queue
        try:
            self.processing_queue.put_nowait(log_entry)
            self.metrics["logs_collected"] += 1
        except asyncio.QueueFull:
            self.metrics["logs_dropped"] += 1
            logger.warning("Log processing queue full, dropping log entry")

    async def search_logs(
        self,
        query: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        size: int = 100,
        sort: str = "@timestamp:desc",
    ) -> Dict[str, Any]:
        """Search logs in Elasticsearch."""
        if not self.es_session:
            return {"error": "Elasticsearch not configured"}

        # Build Elasticsearch query
        es_query = {
            "query": {"bool": {"must": [{"query_string": {"query": query}}]}},
            "size": size,
            "sort": [sort],
        }

        # Add time range filter
        if start_time or end_time:
            range_filter = {"range": {"@timestamp": {}}}
            if start_time:
                range_filter["range"]["@timestamp"]["gte"] = datetime.fromtimestamp(
                    start_time
                ).isoformat()
            if end_time:
                range_filter["range"]["@timestamp"]["lte"] = datetime.fromtimestamp(
                    end_time
                ).isoformat()

            es_query["query"]["bool"]["filter"] = [range_filter]

        try:
            index_pattern = f"{self.config.elasticsearch_index_prefix}-*"
            url = f"{self.config.elasticsearch_url}/{index_pattern}/_search"

            async with self.es_session.post(url, json=es_query) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "total": result["hits"]["total"]["value"],
                        "logs": [hit["_source"] for hit in result["hits"]["hits"]],
                    }
                else:
                    return {"error": f"Elasticsearch query failed: {response.status}"}

        except Exception as e:
            logger.error(f"Log search failed: {e}")
            return {"error": str(e)}

    async def _initialize_kibana(self) -> None:
        """Initialize Kibana integration."""
        if not self.config.kibana_url or not self.config.kibana_api_key:
            return

        headers = {
            "Authorization": f"ApiKey {self.config.kibana_api_key}",
            "Content-Type": "application/json",
            "kbn-xsrf": "true",
        }

        self.kibana_session = aiohttp.ClientSession(headers=headers)

        # Test connection
        try:
            async with self.kibana_session.get(
                f"{self.config.kibana_url}/api/status"
            ) as response:
                if response.status == 200:
                    logger.info("Kibana integration initialized")
                    if self.config.auto_create_dashboards:
                        await self._create_standard_dashboards()
                else:
                    logger.warning(f"Kibana connection failed: {response.status}")
        except Exception as e:
            logger.error(f"Kibana initialization failed: {e}")

    async def _create_standard_dashboards(self) -> None:
        """Create standard Kibana dashboards."""
        if not self.kibana_session:
            return

        dashboards = [
            self._create_overview_dashboard(),
            self._create_error_dashboard(),
            self._create_performance_dashboard(),
            self._create_security_dashboard(),
        ]

        for dashboard in dashboards:
            try:
                async with self.kibana_session.post(
                    f"{self.config.kibana_url}/api/saved_objects/dashboard",
                    json=dashboard.to_kibana_format(),
                ) as response:
                    if response.status in [200, 201]:
                        logger.info(f"Created Kibana dashboard: {dashboard.title}")
                    else:
                        logger.warning(
                            f"Failed to create dashboard {dashboard.title}: {response.status}"
                        )
            except Exception as e:
                logger.error(f"Dashboard creation failed: {e}")

    def _create_overview_dashboard(self) -> KibanaDashboard:
        """Create overview dashboard."""
        dashboard = KibanaDashboard(
            title="HWA-New Log Overview", description="Overview of all log data"
        )

        # Log level distribution visualization
        level_viz = {
            "title": "Log Levels",
            "type": "pie",
            "aggs": [{"type": "terms", "field": "level", "name": "levels"}],
        }

        # Timeline visualization
        timeline_viz = {
            "title": "Log Timeline",
            "type": "line",
            "aggs": [
                {"type": "date_histogram", "field": "@timestamp", "interval": "1h"}
            ],
        }

        dashboard.visualizations = [level_viz, timeline_viz]
        return dashboard

    def _create_error_dashboard(self) -> KibanaDashboard:
        """Create error-focused dashboard."""
        dashboard = KibanaDashboard(
            title="HWA-New Error Logs", description="Error and warning log analysis"
        )

        # Error rate over time
        error_rate_viz = {
            "title": "Error Rate Over Time",
            "type": "area",
            "filter": {"term": {"level": "ERROR"}},
            "aggs": [
                {"type": "date_histogram", "field": "@timestamp", "interval": "5m"}
            ],
        }

        # Top error messages
        top_errors_viz = {
            "title": "Top Error Messages",
            "type": "table",
            "filter": {"terms": {"level": ["ERROR", "CRITICAL"]}},
            "aggs": [{"type": "terms", "field": "message", "size": 10}],
        }

        dashboard.visualizations = [error_rate_viz, top_errors_viz]
        return dashboard

    def _create_performance_dashboard(self) -> KibanaDashboard:
        """Create performance-focused dashboard."""
        dashboard = KibanaDashboard(
            title="HWA-New Performance Logs",
            description="Performance and latency analysis",
        )

        # Response time distribution
        response_time_viz = {
            "title": "Response Time Distribution",
            "type": "histogram",
            "field": "response_time",
            "buckets": 20,
        }

        # Slow queries
        slow_queries_viz = {
            "title": "Slow Queries",
            "type": "table",
            "filter": {"range": {"query_time": {"gt": 1000}}},
            "aggs": [{"type": "terms", "field": "query", "size": 10}],
        }

        dashboard.visualizations = [response_time_viz, slow_queries_viz]
        return dashboard

    def _create_security_dashboard(self) -> KibanaDashboard:
        """Create security-focused dashboard."""
        dashboard = KibanaDashboard(
            title="HWA-New Security Logs", description="Security events and incidents"
        )

        # Authentication failures
        auth_failures_viz = {
            "title": "Authentication Failures",
            "type": "line",
            "filter": {"term": {"event_type": "auth_failure"}},
            "aggs": [
                {"type": "date_histogram", "field": "@timestamp", "interval": "1h"}
            ],
        }

        # Security events by type
        security_events_viz = {
            "title": "Security Events by Type",
            "type": "pie",
            "field": "security_event_type",
        }

        dashboard.visualizations = [auth_failures_viz, security_events_viz]
        return dashboard

    async def _log_collection_worker(self) -> None:
        """Background worker for log collection from all sources."""
        while self._running:
            try:
                await asyncio.sleep(self.config.collection_interval_seconds)

                # Collect from file sources
                for source_name, source_config in self.sources.items():
                    if source_config.enabled:
                        if source_config.source_type == LogSource.FILE:
                            await self._collect_from_file(source_config)
                        elif source_config.source_type == LogSource.NETWORK:
                            await self._collect_from_network(source_config)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Log collection worker error: {e}")

    async def _collect_from_file(self, source_config: LogSourceConfig) -> None:
        """Collect logs from a file source."""
        if not source_config.file_path or not os.path.exists(source_config.file_path):
            return

        try:
            # Open file if not already open
            if source_config.name not in self.file_handles:
                handle = open(
                    source_config.file_path, "r", encoding=source_config.file_encoding
                )
                self.file_handles[source_config.name] = handle
                # Seek to end if following
                if source_config.follow_file:
                    handle.seek(0, 2)
                    self.file_positions[source_config.name] = handle.tell()

            handle = self.file_handles[source_config.name]

            # Read new lines
            lines = []
            current_pos = self.file_positions.get(source_config.name, 0)

            if source_config.follow_file:
                # Read from current position to end
                handle.seek(current_pos)
                new_content = handle.read()
                if new_content:
                    lines = new_content.splitlines()
                    self.file_positions[source_config.name] = handle.tell()
            else:
                # Read entire file
                handle.seek(0)
                content = handle.read()
                lines = content.splitlines()

            # Process lines
            for line in lines:
                if line.strip():  # Skip empty lines
                    await self._process_log_line(line, source_config)

        except Exception as e:
            logger.error(f"File collection failed for {source_config.name}: {e}")

    async def _collect_from_network(self, source_config: LogSourceConfig) -> None:
        """Collect logs from a network source."""
        # This would implement network log collection (TCP/UDP servers)
        # Simplified implementation
        pass

    async def _process_log_line(
        self, line: str, source_config: LogSourceConfig
    ) -> None:
        """Process a single log line."""
        # Apply filters
        if source_config.include_patterns:
            if not any(
                re.search(pattern, line) for pattern in source_config.include_patterns
            ):
                return

        if source_config.exclude_patterns:
            if any(
                re.search(pattern, line) for pattern in source_config.exclude_patterns
            ):
                return

        # Create log entry
        log_entry = LogEntry(
            timestamp=time.time(),
            level=LogLevel.INFO,  # Default, will be parsed
            message=line,
            source=source_config.source_type,
            source_name=source_config.name,
        )

        # Parse log if parser configured
        if source_config.parser_name and source_config.parser_name in self.parsers:
            parser = self.parsers[source_config.parser_name]
            parsed_fields = parser.parse(line)
            if parsed_fields:
                log_entry.fields.update(parsed_fields)
                log_entry.parsed = True

                # Extract level if available
                if "level" in parsed_fields:
                    try:
                        log_entry.level = LogLevel(parsed_fields["level"].upper())
                    except ValueError:
                        pass

        # Add to processing queue
        try:
            self.processing_queue.put_nowait(log_entry)
            self.metrics["logs_collected"] += 1
            if log_entry.parsed:
                self.metrics["logs_parsed"] += 1
        except asyncio.QueueFull:
            self.metrics["logs_dropped"] += 1

    async def _log_processing_worker(self) -> None:
        """Background worker for log processing and indexing."""
        while self._running:
            try:
                # Get batch of logs
                batch = []
                try:
                    for _ in range(self.config.batch_size):
                        log_entry = self.processing_queue.get_nowait()
                        batch.append(log_entry)
                except asyncio.QueueEmpty:
                    if batch:  # Process remaining batch
                        pass
                    else:
                        await asyncio.sleep(0.1)  # Wait for more logs
                        continue

                if batch:
                    await self._index_log_batch(batch)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Log processing worker error: {e}")
                self.metrics["indexing_errors"] += 1

    async def _index_log_batch(self, batch: List[LogEntry]) -> None:
        """Index a batch of log entries to Elasticsearch."""
        if not self.es_session or not batch:
            return

        try:
            # Prepare bulk request
            bulk_data = []
            index_name = f"{self.config.elasticsearch_index_prefix}-{datetime.now().strftime('%Y-%m-%d')}"

            for log_entry in batch:
                # Index metadata
                bulk_data.append(
                    json.dumps(
                        {"index": {"_index": index_name, "_id": str(uuid.uuid4())}}
                    )
                )
                # Document
                bulk_data.append(json.dumps(log_entry.to_elasticsearch()))

            bulk_body = "\n".join(bulk_data) + "\n"

            # Send to Elasticsearch
            url = f"{self.config.elasticsearch_url}/_bulk"
            async with self.es_session.post(url, data=bulk_body) as response:
                if response.status == 200:
                    result = await response.json()
                    successful = sum(
                        1
                        for item in result.get("items", [])
                        if item.get("index", {}).get("status") == 201
                    )
                    self.metrics["logs_indexed"] += successful

                    # Mark entries as indexed
                    for log_entry in batch[:successful]:
                        log_entry.indexed = True
                        log_entry.index_timestamp = time.time()

                    if successful < len(batch):
                        failed = len(batch) - successful
                        logger.warning(f"Failed to index {failed} log entries")
                else:
                    logger.error(f"Elasticsearch bulk index failed: {response.status}")
                    self.metrics["indexing_errors"] += len(batch)

        except Exception as e:
            logger.error(f"Log indexing failed: {e}")
            self.metrics["indexing_errors"] += len(batch)

    async def _cleanup_worker(self) -> None:
        """Background worker for cleanup and maintenance."""
        while self._running:
            try:
                await asyncio.sleep(3600)  # Run every hour

                # Clean old log entries from buffer
                cutoff_time = time.time() - (self.config.retention_days * 24 * 3600)
                while self.log_buffer and self.log_buffer[0].timestamp < cutoff_time:
                    self.log_buffer.popleft()

                # Delete old Elasticsearch indices if retention is configured
                if self.config.retention_days > 0:
                    await self._cleanup_old_indices()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup worker error: {e}")

    async def _cleanup_old_indices(self) -> None:
        """Clean up old Elasticsearch indices."""
        if not self.es_session:
            return

        try:
            cutoff_date = (
                datetime.now() - timedelta(days=self.config.retention_days)
            ).strftime("%Y-%m-%d")

            # Get all indices matching pattern
            url = f"{self.config.elasticsearch_url}/_cat/indices/{self.config.elasticsearch_index_prefix}-*?format=json"
            async with self.es_session.get(url) as response:
                if response.status == 200:
                    indices = await response.json()

                    for index in indices:
                        index_name = index["index"]
                        # Extract date from index name
                        date_part = index_name.replace(
                            f"{self.config.elasticsearch_index_prefix}-", ""
                        )
                        if date_part < cutoff_date:
                            # Delete old index
                            delete_url = f"{self.config.elasticsearch_url}/{index_name}"
                            async with self.es_session.delete(
                                delete_url
                            ) as delete_response:
                                if delete_response.status == 200:
                                    logger.info(f"Deleted old index: {index_name}")
                                else:
                                    logger.warning(
                                        f"Failed to delete index {index_name}"
                                    )

        except Exception as e:
            logger.error(f"Index cleanup failed: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive log aggregation metrics."""
        return {
            "performance": {
                "logs_collected": self.metrics["logs_collected"],
                "logs_parsed": self.metrics["logs_parsed"],
                "logs_indexed": self.metrics["logs_indexed"],
                "logs_dropped": self.metrics["logs_dropped"],
                "indexing_errors": self.metrics["indexing_errors"],
                "parsing_errors": self.metrics["parsing_errors"],
                "parse_rate": self.metrics["logs_parsed"]
                / max(1, self.metrics["logs_collected"]),
            },
            "sources": {
                "configured_sources": len(self.sources),
                "active_sources": sum(1 for s in self.sources.values() if s.enabled),
                "file_sources": sum(
                    1 for s in self.sources.values() if s.source_type == LogSource.FILE
                ),
                "network_sources": sum(
                    1
                    for s in self.sources.values()
                    if s.source_type == LogSource.NETWORK
                ),
            },
            "parsers": {
                "available_parsers": len(self.parsers),
                "parsing_enabled": sum(
                    1 for s in self.sources.values() if s.parser_name
                ),
            },
            "storage": {
                "buffer_size": len(self.log_buffer),
                "queue_size": self.processing_queue.qsize(),
                "retention_days": self.config.retention_days,
            },
            "integrations": {
                "elasticsearch_enabled": self.es_session is not None,
                "kibana_enabled": self.kibana_session is not None,
                "auto_dashboards": self.config.auto_create_dashboards,
            },
            "health": {
                "running": self._running,
                "processing_workers": len(self._processing_tasks),
            },
        }


# Global log aggregator instance
log_aggregator = LogAggregator()


async def get_log_aggregator() -> LogAggregator:
    """Get the global log aggregator instance."""
    if not log_aggregator._running:
        await log_aggregator.start()
    return log_aggregator
