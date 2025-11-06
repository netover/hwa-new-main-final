"""
Memory Management Utilities

This module provides comprehensive memory management functionality for health
monitoring systems, including memory usage tracking, cleanup operations, and
memory optimization strategies.
"""

from __future__ import annotations

import asyncio
import contextlib
import gc
from datetime import datetime, timedelta

import psutil
import structlog

logger = structlog.get_logger(__name__)


class MemoryManager:
    """
    Manages memory usage for health monitoring systems.

    This class provides functionality for:
    - Tracking memory usage of health data structures
    - Automatic cleanup based on memory thresholds
    - Memory optimization and garbage collection
    - Memory usage reporting and alerts
    """

    def __init__(
        self,
        memory_threshold_mb: float = 100.0,
        enable_memory_monitoring: bool = True,
        cleanup_interval_minutes: int = 10,
    ):
        """
        Initialize the memory manager.

        Args:
            memory_threshold_mb: Memory usage threshold in MB before cleanup
            enable_memory_monitoring: Whether to enable memory monitoring
            cleanup_interval_minutes: Interval for automatic cleanup checks
        """
        self.memory_threshold_mb = memory_threshold_mb
        self.enable_memory_monitoring = enable_memory_monitoring
        self.cleanup_interval = timedelta(minutes=cleanup_interval_minutes)

        # Memory tracking
        self._current_memory_usage_mb: float = 0.0
        self._peak_memory_usage_mb: float = 0.0
        self._last_memory_check: datetime | None = None
        self._memory_history: list[dict[str, float]] = []

        # Cleanup tracking
        self._last_cleanup: datetime | None = None
        self._cleanup_count = 0
        self._memory_freed_mb = 0.0

        # Locks
        self._memory_lock = asyncio.Lock()
        self._cleanup_lock = asyncio.Lock()

    async def update_memory_usage(self, estimated_usage_mb: float) -> None:
        """
        Update current memory usage estimate.

        Args:
            estimated_usage_mb: Estimated memory usage in MB
        """
        if not self.enable_memory_monitoring:
            return

        async with self._memory_lock:
            self._current_memory_usage_mb = estimated_usage_mb
            self._last_memory_check = datetime.now()

            # Update peak usage
            if estimated_usage_mb > self._peak_memory_usage_mb:
                self._peak_memory_usage_mb = estimated_usage_mb

            # Add to history
            self._memory_history.append(
                {
                    "timestamp": datetime.now(),
                    "usage_mb": estimated_usage_mb,
                    "threshold_mb": self.memory_threshold_mb,
                }
            )

            # Keep only last 1000 history entries
            if len(self._memory_history) > 1000:
                self._memory_history = self._memory_history[-1000:]

            # Check if cleanup is needed
            if estimated_usage_mb > self.memory_threshold_mb:
                logger.warning(
                    "memory_usage_exceeds_threshold",
                    current_usage_mb=estimated_usage_mb,
                    threshold_mb=self.memory_threshold_mb,
                    excess_mb=estimated_usage_mb - self.memory_threshold_mb,
                )
                # Trigger cleanup in background
                asyncio.create_task(self._trigger_memory_cleanup())

    async def _trigger_memory_cleanup(self) -> None:
        """Trigger memory cleanup when threshold is exceeded."""
        try:
            # Wait a bit to avoid too frequent cleanups
            await asyncio.sleep(1)

            current_usage = await self.get_current_memory_usage()
            if current_usage > self.memory_threshold_mb:
                logger.info("triggering_memory_cleanup", usage_mb=current_usage)
                freed_memory = await self.perform_memory_cleanup()
                logger.info("memory_cleanup_completed", freed_mb=freed_memory)

        except Exception as e:
            logger.error("memory_cleanup_trigger_failed", error=str(e))

    async def perform_memory_cleanup(self) -> float:
        """
        Perform memory cleanup operations.

        Returns:
            Amount of memory freed in MB
        """
        async with self._cleanup_lock:
            start_time = datetime.now()
            await self.get_current_memory_usage()

            try:
                # Force garbage collection
                gc.collect()

                # Get process memory before cleanup
                process = psutil.Process()
                memory_before = process.memory_info().rss / (1024 * 1024)  # MB

                # Perform cleanup operations

                # Clear any large data structures if needed
                # This would be extended based on specific cleanup needs

                # Force another garbage collection
                gc.collect()

                # Get memory after cleanup
                memory_after = process.memory_info().rss / (1024 * 1024)  # MB
                memory_freed = memory_before - memory_after

                # Update tracking
                self._cleanup_count += 1
                self._last_cleanup = datetime.now()
                self._memory_freed_mb += memory_freed

                cleanup_time_ms = (datetime.now() - start_time).total_seconds() * 1000

                logger.info(
                    "memory_cleanup_performed",
                    memory_before_mb=memory_before,
                    memory_after_mb=memory_after,
                    memory_freed_mb=memory_freed,
                    cleanup_time_ms=cleanup_time_ms,
                    cleanup_count=self._cleanup_count,
                )

                return memory_freed

            except Exception as e:
                logger.error("memory_cleanup_failed", error=str(e))
                return 0.0

    async def get_current_memory_usage(self) -> float:
        """Get current memory usage from the system."""
        try:
            process = psutil.Process()
            return process.memory_info().rss / (1024 * 1024)  # Convert to MB
        except Exception as e:
            logger.warning("failed_to_get_memory_usage", error=str(e))
            return 0.0

    def get_memory_stats(self) -> dict[str, any]:
        """
        Get comprehensive memory statistics.

        Returns:
            Dictionary with memory usage information
        """
        return {
            "current_usage_mb": round(self._current_memory_usage_mb, 2),
            "peak_usage_mb": round(self._peak_memory_usage_mb, 2),
            "threshold_mb": self.memory_threshold_mb,
            "memory_monitoring_enabled": self.enable_memory_monitoring,
            "last_memory_check": (
                self._last_memory_check.isoformat() if self._last_memory_check else None
            ),
            "last_cleanup": (
                self._last_cleanup.isoformat() if self._last_cleanup else None
            ),
            "cleanup_count": self._cleanup_count,
            "total_memory_freed_mb": round(self._memory_freed_mb, 2),
            "history_entries": len(self._memory_history),
            "threshold_exceeded": self._current_memory_usage_mb
            > self.memory_threshold_mb,
        }

    def get_memory_history(
        self, hours: int = 24, limit: int | None = None
    ) -> list[dict[str, float]]:
        """
        Get memory usage history.

        Args:
            hours: Number of hours to look back
            limit: Maximum number of entries to return

        Returns:
            List of memory usage history entries
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)

        filtered_history = [
            entry for entry in self._memory_history if entry["timestamp"] >= cutoff_time
        ]

        # Sort by timestamp (most recent first)
        filtered_history.sort(key=lambda x: x["timestamp"], reverse=True)

        # Apply limit if specified
        if limit:
            filtered_history = filtered_history[:limit]

        return filtered_history

    async def force_memory_cleanup(self) -> dict[str, any]:
        """
        Force immediate memory cleanup.

        Returns:
            Dictionary with cleanup results
        """
        memory_before = await self.get_current_memory_usage()
        memory_freed = await self.perform_memory_cleanup()
        memory_after = await self.get_current_memory_usage()

        return {
            "memory_before_mb": round(memory_before, 2),
            "memory_after_mb": round(memory_after, 2),
            "memory_freed_mb": round(memory_freed, 2),
            "cleanup_timestamp": datetime.now().isoformat(),
            "threshold_exceeded": memory_after > self.memory_threshold_mb,
        }


class HealthHistoryMemoryManager(MemoryManager):
    """
    Specialized memory manager for health history data.

    This class extends MemoryManager with specific functionality for:
    - Managing health check history memory usage
    - Estimating memory usage of history entries
    - Automatic history cleanup based on memory pressure
    """

    def __init__(
        self,
        max_history_entries: int = 10000,
        history_retention_days: int = 30,
        memory_threshold_mb: float = 100.0,
        **kwargs,
    ):
        """
        Initialize the health history memory manager.

        Args:
            max_history_entries: Maximum number of history entries to keep
            history_retention_days: Number of days to retain history
            memory_threshold_mb: Memory usage threshold in MB
            **kwargs: Additional arguments for parent class
        """
        super().__init__(memory_threshold_mb=memory_threshold_mb, **kwargs)

        self.max_history_entries = max_history_entries
        self.history_retention_days = history_retention_days
        self.history_cleanup_threshold = 0.8  # Cleanup when 80% of max entries reached

        # History-specific tracking
        self._current_history_size = 0
        self._history_cleanup_count = 0

    def estimate_history_memory_usage(self, entry_count: int) -> float:
        """
        Estimate memory usage for health history entries.

        Args:
            entry_count: Number of history entries

        Returns:
            Estimated memory usage in MB
        """
        if entry_count == 0:
            return 0.0

        # Estimate: each entry ~2KB (accounting for metadata and component changes)
        estimated_size_bytes = entry_count * 2048
        return estimated_size_bytes / (1024 * 1024)  # Convert to MB

    async def update_history_memory_usage(self, current_entry_count: int) -> None:
        """
        Update memory usage based on current history entry count.

        Args:
            current_entry_count: Current number of history entries
        """
        estimated_mb = self.estimate_history_memory_usage(current_entry_count)
        await self.update_memory_usage(estimated_mb)

        async with self._memory_lock:
            self._current_history_size = current_entry_count

    def should_cleanup_history(self, current_entries: int) -> bool:
        """
        Determine if history cleanup should be performed.

        Args:
            current_entries: Current number of history entries

        Returns:
            True if cleanup should be performed
        """
        # Cleanup based on entry count
        int(self.max_history_entries * self.history_cleanup_threshold)
        if current_entries > self.max_history_entries:
            return True

        # Cleanup based on age (would need timestamp info)
        # This would be implemented with actual history data

        return False

    async def perform_history_cleanup(
        self, current_entries: int, cleanup_callback=None
    ) -> dict[str, any]:
        """
        Perform cleanup of health history based on memory pressure.

        Args:
            current_entries: Current number of history entries
            cleanup_callback: Optional callback function to perform actual cleanup

        Returns:
            Dictionary with cleanup results
        """
        async with self._cleanup_lock:
            start_time = datetime.now()
            initial_entries = current_entries

            try:
                entries_to_remove = 0

                # Calculate how many entries to remove based on memory pressure
                current_memory_mb = await self.get_current_memory_usage()

                if current_memory_mb > self.memory_threshold_mb:
                    # Remove entries to get back under threshold
                    target_entries = int(
                        self.max_history_entries * 0.7
                    )  # Target 70% of max
                    entries_to_remove = max(0, current_entries - target_entries)
                else:
                    # Remove based on entry count threshold
                    entry_threshold = int(
                        self.max_history_entries * self.history_cleanup_threshold
                    )
                    if current_entries > entry_threshold:
                        entries_to_remove = current_entries - entry_threshold

                # Perform cleanup if callback provided
                if cleanup_callback and entries_to_remove > 0:
                    await cleanup_callback(entries_to_remove)

                # Update tracking
                self._history_cleanup_count += 1
                cleanup_time_ms = (datetime.now() - start_time).total_seconds() * 1000

                logger.info(
                    "history_cleanup_performed",
                    initial_entries=initial_entries,
                    entries_removed=entries_to_remove,
                    remaining_entries=initial_entries - entries_to_remove,
                    cleanup_time_ms=cleanup_time_ms,
                )

                return {
                    "initial_entries": initial_entries,
                    "entries_removed": entries_to_remove,
                    "remaining_entries": initial_entries - entries_to_remove,
                    "cleanup_time_ms": cleanup_time_ms,
                    "memory_before_mb": current_memory_mb,
                    "cleanup_timestamp": datetime.now().isoformat(),
                }

            except Exception as e:
                logger.error("history_cleanup_failed", error=str(e))
                return {
                    "error": str(e),
                    "initial_entries": initial_entries,
                    "entries_removed": 0,
                }

    def get_history_memory_stats(self) -> dict[str, any]:
        """Get memory statistics specific to health history."""
        base_stats = self.get_memory_stats()

        return {
            **base_stats,
            "current_history_size": self._current_history_size,
            "max_history_entries": self.max_history_entries,
            "history_retention_days": self.history_retention_days,
            "history_cleanup_threshold": self.history_cleanup_threshold,
            "history_cleanup_count": self._history_cleanup_count,
            "estimated_entry_size_kb": 2.0,  # Estimated size per entry
        }


class SystemMemoryMonitor:
    """
    Monitors overall system memory usage.

    This class provides functionality for:
    - Monitoring system-wide memory usage
    - Tracking memory trends and patterns
    - Providing memory usage alerts and warnings
    """

    def __init__(self, warning_threshold_percent: float = 80.0):
        """
        Initialize the system memory monitor.

        Args:
            warning_threshold_percent: Memory usage percentage threshold for warnings
        """
        self.warning_threshold_percent = warning_threshold_percent
        self._monitoring_active = False
        self._monitor_task: asyncio.Task | None = None

    async def start_monitoring(self) -> None:
        """Start continuous system memory monitoring."""
        if self._monitoring_active:
            return

        self._monitoring_active = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("system_memory_monitoring_started")

    async def stop_monitoring(self) -> None:
        """Stop continuous system memory monitoring."""
        self._monitoring_active = False
        if self._monitor_task:
            self._monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitor_task
            self._monitor_task = None
        logger.info("system_memory_monitoring_stopped")

    async def _monitoring_loop(self) -> None:
        """Continuous monitoring loop."""
        while self._monitoring_active:
            try:
                memory_info = await self.get_memory_info()

                # Check for warning conditions
                if memory_info["percent"] > self.warning_threshold_percent:
                    logger.warning(
                        "high_system_memory_usage",
                        usage_percent=memory_info["percent"],
                        threshold_percent=self.warning_threshold_percent,
                        available_gb=memory_info["available_gb"],
                    )

                await asyncio.sleep(30)  # Check every 30 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("error_in_memory_monitoring_loop", error=str(e))
                await asyncio.sleep(60)  # Wait longer on error

    async def get_memory_info(self) -> dict[str, float]:
        """
        Get current system memory information.

        Returns:
            Dictionary with memory information
        """
        try:
            memory = psutil.virtual_memory()

            return {
                "total_gb": memory.total / (1024**3),
                "available_gb": memory.available / (1024**3),
                "used_gb": memory.used / (1024**3),
                "free_gb": memory.free / (1024**3),
                "percent": memory.percent,
                "timestamp": datetime.now().timestamp(),
            }

        except Exception as e:
            logger.warning("failed_to_get_memory_info", error=str(e))
            return {
                "total_gb": 0.0,
                "available_gb": 0.0,
                "used_gb": 0.0,
                "free_gb": 0.0,
                "percent": 0.0,
                "timestamp": datetime.now().timestamp(),
                "error": str(e),
            }

    def is_memory_pressure_high(self) -> bool:
        """
        Check if system is under high memory pressure.

        Returns:
            True if memory pressure is high
        """
        try:
            memory = psutil.virtual_memory()
            return memory.percent > self.warning_threshold_percent
        except Exception:
            return False
