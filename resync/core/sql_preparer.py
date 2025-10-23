"""
Intelligent Prepared Statement Caching and Management.

This module provides advanced prepared statement management with:
- LRU-based caching with size limits
- Automatic invalidation on schema changes
- Performance monitoring and metrics
- Statement fingerprinting for deduplication
- Connection-aware statement management
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from resync.core.db_pool import get_multiplex_connection_pool
from resync.core.structured_logger import get_logger

logger = get_logger(__name__)


@dataclass
class PreparedStatementInfo:
    """Information about a prepared statement."""

    statement_id: str
    sql: str
    fingerprint: str
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    use_count: int = 0
    total_execution_time: float = 0.0
    connection_id: str = ""
    is_valid: bool = True
    schema_version: int = 0

    @property
    def age(self) -> float:
        """Get statement age in seconds."""
        return time.time() - self.created_at

    @property
    def idle_time(self) -> float:
        """Get idle time since last use."""
        return time.time() - self.last_used

    @property
    def avg_execution_time(self) -> float:
        """Calculate average execution time."""
        return self.total_execution_time / max(1, self.use_count)

    def should_evict(self, max_age: float, max_idle: float) -> bool:
        """Check if statement should be evicted."""
        return self.age > max_age or self.idle_time > max_idle or not self.is_valid

    def record_execution(self, execution_time: float) -> None:
        """Record statement execution."""
        self.last_used = time.time()
        self.use_count += 1
        self.total_execution_time += execution_time


@dataclass
class StatementCacheConfig:
    """Configuration for prepared statement caching."""

    # Cache limits
    max_cache_size: int = 1000
    max_cache_age: float = 3600.0  # 1 hour
    max_idle_time: float = 1800.0  # 30 minutes

    # Performance thresholds
    min_usage_threshold: int = 2  # Prepare only if used at least twice
    execution_time_threshold: float = 0.01  # 10ms - prepare if slower

    # Schema tracking
    enable_schema_tracking: bool = True
    schema_check_interval: float = 300.0  # 5 minutes

    # Connection awareness
    connection_aware_caching: bool = True
    max_statements_per_connection: int = 50

    # Monitoring
    enable_metrics: bool = True
    metrics_interval: float = 60.0  # 1 minute


@dataclass
class StatementCacheMetrics:
    """Metrics for prepared statement caching."""

    # Cache statistics
    total_statements_cached: int = 0
    active_statements: int = 0
    evicted_statements: int = 0
    invalidated_statements: int = 0

    # Performance metrics
    cache_hit_rate: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_preparation_time: float = 0.0
    total_preparation_time: float = 0.0

    # Usage patterns
    statements_by_frequency: Dict[str, int] = field(default_factory=dict)
    most_used_statements: List[Tuple[str, int]] = field(default_factory=list)

    # Schema changes
    schema_changes_detected: int = 0
    last_schema_check: float = 0.0

    def update_hit_rate(self) -> None:
        """Update cache hit rate."""
        total = self.cache_hits + self.cache_misses
        if total > 0:
            self.cache_hit_rate = self.cache_hits / total

    def record_hit(self) -> None:
        """Record cache hit."""
        self.cache_hits += 1
        self.update_hit_rate()

    def record_miss(self) -> None:
        """Record cache miss."""
        self.cache_misses += 1
        self.update_hit_rate()


class PreparedStatementCache:
    """
    Intelligent prepared statement cache with LRU eviction and schema awareness.

    Features:
    - LRU-based caching with configurable limits
    - Automatic invalidation on schema changes
    - Connection-aware statement management
    - Performance monitoring and optimization
    - Statement deduplication using fingerprints
    """

    def __init__(self, config: Optional[StatementCacheConfig] = None):
        self.config = config or StatementCacheConfig()

        # Cache storage (statement_fingerprint -> PreparedStatementInfo)
        self.cache: OrderedDict[str, PreparedStatementInfo] = OrderedDict()

        # Reverse mapping (statement_id -> fingerprint)
        self.statement_ids: Dict[str, str] = {}

        # Connection-specific caches
        self.connection_caches: Dict[str, Set[str]] = (
            {}
        )  # connection_id -> set of fingerprints

        # Schema tracking
        self.current_schema_version = 0
        self.table_schemas: Dict[str, int] = {}  # table_name -> schema_version

        # Metrics
        self.metrics = StatementCacheMetrics()

        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._schema_check_task: Optional[asyncio.Task] = None
        self._metrics_task: Optional[asyncio.Task] = None
        self._running = False

        # Synchronization
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the prepared statement cache."""
        if self._running:
            return

        self._running = True

        # Start background tasks
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        if self.config.enable_schema_tracking:
            self._schema_check_task = asyncio.create_task(self._schema_check_loop())
        if self.config.enable_metrics:
            self._metrics_task = asyncio.create_task(self._metrics_loop())

        logger.info("Prepared statement cache started")

    async def stop(self) -> None:
        """Stop the prepared statement cache."""
        if not self._running:
            return

        self._running = False

        # Stop background tasks
        for task in [self._cleanup_task, self._schema_check_task, self._metrics_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Clear cache
        async with self._lock:
            self.cache.clear()
            self.statement_ids.clear()
            self.connection_caches.clear()

        logger.info("Prepared statement cache stopped")

    async def get_or_prepare(
        self,
        sql: str,
        connection_id: str = "default",
        execution_time_estimate: Optional[float] = None,
    ) -> Tuple[Optional[str], bool]:
        """
        Get prepared statement ID for SQL, creating if necessary.

        Args:
            sql: SQL statement to prepare
            connection_id: Database connection identifier
            execution_time_estimate: Estimated execution time for optimization decisions

        Returns:
            Tuple of (statement_id, was_cached) - None if not prepared
        """
        fingerprint = self._create_fingerprint(sql)

        # Check if we should prepare this statement
        if not self._should_prepare_statement(sql, execution_time_estimate):
            return None, False

        async with self._lock:
            # Check cache
            if fingerprint in self.cache:
                statement_info = self.cache[fingerprint]

                # Check if still valid
                if (
                    statement_info.is_valid
                    and statement_info.schema_version == self.current_schema_version
                    and statement_info.connection_id == connection_id
                ):

                    # Move to end (most recently used)
                    self.cache.move_to_end(fingerprint)
                    statement_info.last_used = time.time()

                    self.metrics.record_hit()
                    return statement_info.statement_id, True

            # Cache miss - prepare new statement
            statement_id = await self._prepare_statement(
                sql, connection_id, fingerprint
            )

            if statement_id:
                # Add to cache
                statement_info = PreparedStatementInfo(
                    statement_id=statement_id,
                    sql=sql,
                    fingerprint=fingerprint,
                    connection_id=connection_id,
                    schema_version=self.current_schema_version,
                )

                # Check cache size limits
                if len(self.cache) >= self.config.max_cache_size:
                    await self._evict_lru()

                self.cache[fingerprint] = statement_info
                self.statement_ids[statement_id] = fingerprint

                # Update connection cache
                if connection_id not in self.connection_caches:
                    self.connection_caches[connection_id] = set()
                self.connection_caches[connection_id].add(fingerprint)

                # Check per-connection limits
                if (
                    self.config.connection_aware_caching
                    and len(self.connection_caches[connection_id])
                    > self.config.max_statements_per_connection
                ):
                    await self._evict_connection_lru(connection_id)

                self.metrics.total_statements_cached += 1
                self.metrics.record_miss()

                logger.debug(f"Prepared statement cached: {fingerprint[:16]}...")
                return statement_id, False

        return None, False

    async def execute_prepared(
        self, statement_id: str, params: Tuple[Any, ...] = ()
    ) -> Any:
        """
        Execute a prepared statement.

        Args:
            statement_id: Prepared statement identifier
            params: Statement parameters

        Returns:
            Execution result
        """
        fingerprint = self.statement_ids.get(statement_id)
        if not fingerprint or fingerprint not in self.cache:
            raise ValueError(f"Prepared statement not found: {statement_id}")

        statement_info = self.cache[fingerprint]

        # Check if still valid
        if (
            not statement_info.is_valid
            or statement_info.schema_version != self.current_schema_version
        ):
            # Invalidate and re-prepare
            await self.invalidate_statement(statement_id)
            raise ValueError(f"Prepared statement invalidated: {statement_id}")

        start_time = time.time()

        try:
            # Execute using multiplex pool
            pool = await get_multiplex_connection_pool()

            async with pool.execute_operation(
                sql=f"EXECUTE {statement_id}", params=params
            ) as result:
                execution_time = time.time() - start_time
                statement_info.record_execution(execution_time)

                return result

        except Exception as e:
            execution_time = time.time() - start_time
            statement_info.record_execution(execution_time)
            logger.warning(f"Prepared statement execution failed: {e}")
            raise

    async def invalidate_statement(self, statement_id: str) -> bool:
        """
        Invalidate a prepared statement.

        Args:
            statement_id: Statement to invalidate

        Returns:
            True if invalidated, False if not found
        """
        async with self._lock:
            fingerprint = self.statement_ids.get(statement_id)
            if not fingerprint or fingerprint not in self.cache:
                return False

            statement_info = self.cache[fingerprint]
            statement_info.is_valid = False

            # Remove from cache
            del self.cache[fingerprint]
            del self.statement_ids[statement_id]

            # Remove from connection cache
            connection_id = statement_info.connection_id
            if connection_id in self.connection_caches:
                self.connection_caches[connection_id].discard(fingerprint)

            self.metrics.invalidated_statements += 1
            logger.debug(f"Invalidated prepared statement: {statement_id}")

            return True

    async def invalidate_by_connection(self, connection_id: str) -> int:
        """
        Invalidate all statements for a connection.

        Args:
            connection_id: Connection identifier

        Returns:
            Number of statements invalidated
        """
        async with self._lock:
            if connection_id not in self.connection_caches:
                return 0

            fingerprints = self.connection_caches[connection_id].copy()
            invalidated = 0

            for fingerprint in fingerprints:
                if fingerprint in self.cache:
                    statement_info = self.cache[fingerprint]
                    await self.invalidate_statement(statement_info.statement_id)
                    invalidated += 1

            del self.connection_caches[connection_id]
            return invalidated

    async def invalidate_by_table(self, table_name: str) -> int:
        """
        Invalidate statements that depend on a table.

        Args:
            table_name: Table name that changed

        Returns:
            Number of statements invalidated
        """
        async with self._lock:
            invalidated = 0

            # Find statements that reference this table
            to_invalidate = []
            for fingerprint, statement_info in self.cache.items():
                if self._statement_uses_table(statement_info.sql, table_name):
                    to_invalidate.append(statement_info.statement_id)

            for statement_id in to_invalidate:
                if await self.invalidate_statement(statement_id):
                    invalidated += 1

            if invalidated > 0:
                logger.info(
                    f"Invalidated {invalidated} statements due to table change: {table_name}"
                )

            return invalidated

    async def record_schema_change(self, table_name: str) -> None:
        """
        Record that a table schema has changed.

        Args:
            table_name: Name of the changed table
        """
        self.current_schema_version += 1
        self.table_schemas[table_name] = self.current_schema_version
        self.metrics.schema_changes_detected += 1

        # Invalidate all statements for this table
        await self.invalidate_by_table(table_name)

        logger.info(f"Schema change recorded for table: {table_name}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""

        async def _get_stats():
            async with self._lock:
                return {
                    "cache": {
                        "size": len(self.cache),
                        "max_size": self.config.max_cache_size,
                        "hit_rate": self.metrics.cache_hit_rate,
                        "hits": self.metrics.cache_hits,
                        "misses": self.metrics.cache_misses,
                    },
                    "performance": {
                        "total_preparation_time": self.metrics.total_preparation_time,
                        "avg_preparation_time": self.metrics.avg_preparation_time,
                        "evictions": self.metrics.evicted_statements,
                        "invalidations": self.metrics.invalidated_statements,
                    },
                    "usage": {
                        "connections_tracked": len(self.connection_caches),
                        "tables_tracked": len(self.table_schemas),
                        "schema_changes": self.metrics.schema_changes_detected,
                    },
                    "config": {
                        "max_cache_age": self.config.max_cache_age,
                        "max_idle_time": self.config.max_idle_time,
                        "schema_tracking": self.config.enable_schema_tracking,
                        "connection_aware": self.config.connection_aware_caching,
                    },
                }

        # Since this is called from sync context, create a task
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, _get_stats())
            return future.result()

    async def _prepare_statement(
        self, sql: str, connection_id: str, fingerprint: str
    ) -> Optional[str]:
        """Prepare a statement on the database."""
        try:
            start_time = time.time()

            # Use multiplex pool to prepare statement
            pool = await get_multiplex_connection_pool()
            prepared_stmt = await pool.get_prepared_statement(sql)

            preparation_time = time.time() - start_time

            # Update metrics
            self.metrics.total_preparation_time += preparation_time
            if self.metrics.total_statements_cached > 0:
                self.metrics.avg_preparation_time = (
                    self.metrics.total_preparation_time
                    / self.metrics.total_statements_cached
                )

            # Generate statement ID
            statement_id = f"stmt_{fingerprint}_{int(time.time())}"

            logger.debug(
                f"Prepared statement: {fingerprint[:16]}... in {preparation_time:.3f}s"
            )

            return statement_id

        except Exception as e:
            logger.warning(f"Failed to prepare statement: {e}")
            return None

    def _create_fingerprint(self, sql: str) -> str:
        """Create a fingerprint for SQL statement deduplication."""
        # Normalize SQL for fingerprinting
        normalized = self._normalize_sql(sql)
        return hashlib.md5(normalized.encode()).hexdigest()

    def _normalize_sql(self, sql: str) -> str:
        """Normalize SQL for consistent fingerprinting."""
        # Remove extra whitespace
        normalized = re.sub(r"\s+", " ", sql.strip())

        # Remove comments
        normalized = re.sub(r"--.*", "", normalized)
        normalized = re.sub(r"/\*.*?\*/", "", normalized, flags=re.DOTALL)

        # Normalize case for keywords
        # This is a simplified normalization - real implementation would be more comprehensive
        normalized = normalized.lower()

        return normalized

    def _should_prepare_statement(
        self, sql: str, execution_time_estimate: Optional[float]
    ) -> bool:
        """Determine if a statement should be prepared."""
        # Skip very simple queries
        if len(sql.split()) < 3:
            return False

        # Skip DDL statements
        ddl_keywords = ["create", "alter", "drop", "truncate"]
        if any(keyword in sql.lower() for keyword in ddl_keywords):
            return False

        # Check execution time estimate
        if (
            execution_time_estimate is not None
            and execution_time_estimate < self.config.execution_time_threshold
        ):
            return False

        return True

    async def _evict_lru(self) -> None:
        """Evict least recently used statement."""
        if not self.cache:
            return

        # Find oldest entry
        oldest_fingerprint = next(iter(self.cache))
        oldest_info = self.cache[oldest_fingerprint]

        # Remove from caches
        del self.cache[oldest_fingerprint]
        del self.statement_ids[oldest_info.statement_id]

        # Remove from connection cache
        connection_id = oldest_info.connection_id
        if connection_id in self.connection_caches:
            self.connection_caches[connection_id].discard(oldest_fingerprint)

        self.metrics.evicted_statements += 1
        logger.debug(f"Evicted LRU statement: {oldest_fingerprint[:16]}...")

    async def _evict_connection_lru(self, connection_id: str) -> None:
        """Evict LRU statement for a specific connection."""
        if connection_id not in self.connection_caches:
            return

        # Find least recently used for this connection
        connection_fingerprints = self.connection_caches[connection_id]
        if not connection_fingerprints:
            return

        lru_fingerprint = None
        lru_time = float("inf")

        for fingerprint in connection_fingerprints:
            if fingerprint in self.cache:
                last_used = self.cache[fingerprint].last_used
                if last_used < lru_time:
                    lru_time = last_used
                    lru_fingerprint = fingerprint

        if lru_fingerprint:
            statement_info = self.cache[lru_fingerprint]
            await self.invalidate_statement(statement_info.statement_id)

    def _statement_uses_table(self, sql: str, table_name: str) -> bool:
        """Check if SQL statement uses a specific table."""
        # Simple regex check - real implementation would parse SQL properly
        pattern = r"\b" + re.escape(table_name) + r"\b"
        return bool(re.search(pattern, sql, re.IGNORECASE))

    async def _cleanup_loop(self) -> None:
        """Background cleanup of expired statements."""
        while self._running:
            try:
                await asyncio.sleep(300)  # Clean every 5 minutes

                async with self._lock:
                    to_evict = []
                    for fingerprint, statement_info in self.cache.items():
                        if statement_info.should_evict(
                            self.config.max_cache_age, self.config.max_idle_time
                        ):
                            to_evict.append(fingerprint)

                    for fingerprint in to_evict:
                        if fingerprint in self.cache:
                            statement_info = self.cache[fingerprint]
                            del self.cache[fingerprint]
                            del self.statement_ids[statement_info.statement_id]

                            # Remove from connection cache
                            connection_id = statement_info.connection_id
                            if connection_id in self.connection_caches:
                                self.connection_caches[connection_id].discard(
                                    fingerprint
                                )

                            self.metrics.evicted_statements += 1

                    if to_evict:
                        logger.debug(f"Cleaned up {len(to_evict)} expired statements")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")

    async def _schema_check_loop(self) -> None:
        """Background schema checking loop."""
        while self._running:
            try:
                await asyncio.sleep(self.config.schema_check_interval)

                # In real implementation, this would check database schema versions
                # For now, this is a placeholder
                self.metrics.last_schema_check = time.time()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Schema check loop error: {e}")

    async def _metrics_loop(self) -> None:
        """Background metrics collection loop."""
        while self._running:
            try:
                await asyncio.sleep(self.config.metrics_interval)

                async with self._lock:
                    # Update usage patterns
                    self.metrics.statements_by_frequency = {}
                    for statement_info in self.cache.values():
                        freq_range = self._categorize_frequency(
                            statement_info.use_count
                        )
                        self.metrics.statements_by_frequency[freq_range] = (
                            self.metrics.statements_by_frequency.get(freq_range, 0) + 1
                        )

                    # Find most used statements
                    sorted_statements = sorted(
                        self.cache.values(), key=lambda x: x.use_count, reverse=True
                    )[:10]

                    self.metrics.most_used_statements = [
                        (
                            stmt.sql[:50] + "..." if len(stmt.sql) > 50 else stmt.sql,
                            stmt.use_count,
                        )
                        for stmt in sorted_statements
                    ]

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics loop error: {e}")

    def _categorize_frequency(self, use_count: int) -> str:
        """Categorize statement usage frequency."""
        if use_count >= 1000:
            return "very_high"
        elif use_count >= 100:
            return "high"
        elif use_count >= 10:
            return "medium"
        else:
            return "low"


# Global cache instance
prepared_statement_cache = PreparedStatementCache()


async def get_prepared_statement_cache() -> PreparedStatementCache:
    """Get the global prepared statement cache instance."""
    if not prepared_statement_cache._running:
        await prepared_statement_cache.start()
    return prepared_statement_cache
