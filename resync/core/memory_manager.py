"""
Memory Management & Cleanup

This module provides intelligent memory management and cleanup capabilities for health monitoring,
including health history cleanup, memory bounds enforcement, and resource optimization.
"""

from __future__ import annotations

import asyncio
import gc
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil
import structlog

logger = structlog.get_logger(__name__)


class MemoryManager:
    """Intelligent memory management system for health monitoring."""

    def __init__(
        self,
        max_history_entries: int = 10000,
        history_retention_days: int = 7,
        memory_usage_threshold_mb: float = 100.0,
        cleanup_interval_seconds: int = 300,  # 5 minutes
        enable_memory_monitoring: bool = True,
    ):
        self.max_history_entries = max_history_entries
        self.history_retention_days = history_retention_days
        self.memory_usage_threshold_mb = memory_usage_threshold_mb
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self.enable_memory_monitoring = enable_memory_monitoring

        # Memory tracking
        self.current_memory_usage_mb: float = 0.0
        self.peak_memory_usage_mb: float = 0.0
        self.last_cleanup_time: Optional[datetime] = None

        # Cleanup configuration
        self.history_cleanup_threshold = 0.8  # Cleanup when 80% of max entries reached
        self.history_cleanup_batch_size = 100  # Remove 100 entries at a time

        # Locks
        self._cleanup_lock = asyncio.Lock()
        self._memory_lock = asyncio.Lock()

        # Monitoring
        self._monitoring_task: Optional[asyncio.Task] = None
        self._is_monitoring = False

    async def start_monitoring(self) -> None:
        """Start continuous memory monitoring."""
        if self._is_monitoring or not self.enable_memory_monitoring:
            return

        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._memory_monitoring_loop())
        logger.info("memory_monitoring_started")

    async def stop_monitoring(self) -> None:
        """Stop continuous memory monitoring."""
        self._is_monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
        logger.info("memory_monitoring_stopped")

    async def _memory_monitoring_loop(self) -> None:
        """Continuous memory monitoring loop."""
        while self._is_monitoring:
            try:
                await self._update_memory_usage()
                await self._check_memory_pressure()
                await asyncio.sleep(self.cleanup_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("error_in_memory_monitoring_loop", error=str(e))
                await asyncio.sleep(60)  # Longer pause on error

    async def cleanup_health_history(self, health_history: List[Any]) -> Dict[str, Any]:
        """
        Perform efficient cleanup of health history based on multiple criteria.

        Args:
            health_history: The health history list to clean up

        Returns:
            Dictionary with cleanup statistics
        """
        async with self._cleanup_lock:
            return await self._perform_cleanup(health_history)

    async def _perform_cleanup(self, health_history: List[Any]) -> Dict[str, Any]:
        """Perform the actual cleanup operation."""
        try:
            current_size = len(health_history)
            original_size = current_size

            # 1. Size-based cleanup
            size_cleanup = await self._cleanup_by_size(health_history)

            # 2. Age-based cleanup
            age_cleanup = await self._cleanup_by_age(health_history)

            # 3. Memory-based cleanup
            memory_cleanup = await self._cleanup_by_memory(health_history)

            # 4. Ensure minimum entries are maintained
            min_entries = max(10, self.history_cleanup_batch_size)
            if len(health_history) < min_entries and original_size >= min_entries:
                # Keep at least some recent history
                health_history[:] = health_history[-min_entries:]

            final_size = len(health_history)

            cleanup_stats = {
                "original_entries": original_size,
                "final_entries": final_size,
                "entries_removed": original_size - final_size,
                "size_based_cleanup": size_cleanup,
                "age_based_cleanup": age_cleanup,
                "memory_based_cleanup": memory_cleanup,
                "cleanup_timestamp": datetime.now().isoformat(),
            }

            if original_size != final_size:
                logger.info("health_history_cleanup_completed", **cleanup_stats)

            return cleanup_stats

        except Exception as e:
            logger.error("error_during_health_history_cleanup", error=str(e))
            return {
                "error": str(e),
                "original_entries": len(health_history),
                "final_entries": len(health_history),
                "entries_removed": 0,
            }

    async def _cleanup_by_size(self, health_history: List[Any]) -> int:
        """Clean up based on maximum entries limit."""
        removed_count = 0

        if len(health_history) > self.max_history_entries:
            # Calculate how many entries to remove
            threshold_entries = int(
                self.max_history_entries * self.history_cleanup_threshold
            )
            entries_to_remove = len(health_history) - threshold_entries

            if entries_to_remove > 0:
                # Remove oldest entries
                del health_history[:entries_to_remove]
                removed_count = entries_to_remove

                logger.debug(
                    "cleaned_up_health_history_by_size",
                    entries_removed=removed_count,
                    remaining_entries=len(health_history),
                )

        return removed_count

    async def _cleanup_by_age(self, health_history: List[Any]) -> int:
        """Clean up based on age limit."""
        removed_count = 0

        if not health_history:
            return removed_count

        try:
            cutoff_date = datetime.now() - timedelta(days=self.history_retention_days)
            original_size = len(health_history)

            # Filter out old entries (assuming entries have timestamp attribute)
            filtered_history = []
            for entry in health_history:
                # Try different timestamp attribute names
                entry_time = None
                if hasattr(entry, "timestamp"):
                    entry_time = entry.timestamp
                elif hasattr(entry, "created_at"):
                    entry_time = entry.created_at
                elif hasattr(entry, "date"):
                    entry_time = entry.date

                if entry_time:
                    # Handle both datetime objects and timestamps
                    if isinstance(entry_time, (int, float)):
                        entry_datetime = datetime.fromtimestamp(entry_time)
                    else:
                        entry_datetime = entry_time

                    if entry_datetime >= cutoff_date:
                        filtered_history.append(entry)
                else:
                    # Keep entries without timestamp to be safe
                    filtered_history.append(entry)

            removed_count = original_size - len(filtered_history)
            health_history[:] = filtered_history

            if removed_count > 0:
                logger.debug(
                    "cleaned_up_health_history_by_age",
                    entries_removed=removed_count,
                    retention_days=self.history_retention_days,
                )

        except Exception as e:
            logger.warning("age_based_cleanup_failed", error=str(e))

        return removed_count

    async def _cleanup_by_memory(self, health_history: List[Any]) -> int:
        """Clean up based on memory usage."""
        removed_count = 0

        try:
            current_usage = await self._get_memory_usage_mb()

            if current_usage > self.memory_usage_threshold_mb:
                # Calculate how much memory is being used by history
                estimated_history_memory = self._estimate_history_memory_usage(
                    health_history
                )

                if estimated_history_memory > (self.memory_usage_threshold_mb * 0.5):
                    # Remove oldest 20% of entries to reduce memory pressure
                    entries_to_remove = max(1, len(health_history) // 5)
                    del health_history[:entries_to_remove]
                    removed_count = entries_to_remove

                    logger.warning(
                        "cleaned_up_health_history_by_memory",
                        entries_removed=removed_count,
                        memory_usage_mb=current_usage,
                        threshold_mb=self.memory_usage_threshold_mb,
                    )

        except Exception as e:
            logger.warning("memory_based_cleanup_failed", error=str(e))

        return removed_count

    async def _update_memory_usage(self) -> None:
        """Update current memory usage tracking."""
        async with self._memory_lock:
            try:
                # Get process memory usage
                process = psutil.Process()
                memory_info = process.memory_info()
                current_usage_mb = memory_info.rss / (1024 * 1024)

                self.current_memory_usage_mb = current_usage_mb
                self.peak_memory_usage_mb = max(
                    self.peak_memory_usage_mb, current_usage_mb
                )

                # Check if memory usage exceeds threshold
                if current_usage_mb > self.memory_usage_threshold_mb:
                    logger.warning(
                        "memory_usage_exceeds_threshold",
                        current_usage_mb=round(current_usage_mb, 2),
                        threshold_mb=self.memory_usage_threshold_mb,
                        peak_usage_mb=round(self.peak_memory_usage_mb, 2),
                    )

            except Exception as e:
                logger.error("error_updating_memory_usage", error=str(e))

    async def _check_memory_pressure(self) -> None:
        """Check for memory pressure and trigger cleanup if needed."""
        try:
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            # If memory usage is high, trigger garbage collection
            if memory_percent > 80:
                logger.warning(
                    "high_memory_usage_detected", memory_percent=memory_percent
                )
                gc.collect()

                # If still high, suggest more aggressive cleanup
                if memory_percent > 90:
                    logger.error("critical_memory_usage", memory_percent=memory_percent)

        except Exception as e:
            logger.error("memory_pressure_check_failed", error=str(e))

    async def _get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB."""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            return memory_info.rss / (1024 * 1024)
        except Exception:
            return 0.0

    def _estimate_history_memory_usage(self, health_history: List[Any]) -> float:
        """Estimate memory usage of health history in MB."""
        try:
            if not health_history:
                return 0.0

            # Rough estimation: each entry ~2KB (accounting for metadata and history)
            estimated_bytes = len(health_history) * 2048
            return estimated_bytes / (1024 * 1024)

        except Exception:
            return 0.0

    async def force_memory_cleanup(self) -> Dict[str, Any]:
        """Force immediate memory cleanup."""
        try:
            # Force garbage collection
            gc.collect()

            # Clear any internal caches
            await self._clear_internal_caches()

            # Update memory usage
            await self._update_memory_usage()

            return {
                "action": "force_memory_cleanup",
                "timestamp": datetime.now().isoformat(),
                "memory_before_mb": self.peak_memory_usage_mb,
                "memory_after_mb": self.current_memory_usage_mb,
                "memory_freed_mb": round(
                    self.peak_memory_usage_mb - self.current_memory_usage_mb, 2
                ),
            }

        except Exception as e:
            logger.error("force_memory_cleanup_failed", error=str(e))
            return {
                "action": "force_memory_cleanup",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    async def _clear_internal_caches(self) -> None:
        """Clear internal caches and temporary data."""
        try:
            # This would clear any internal caches if they exist
            # For now, just log the action
            logger.debug("clearing_internal_caches")
        except Exception as e:
            logger.warning("internal_cache_clear_failed", error=str(e))

    async def cleanup_temp_files(self) -> Dict[str, Any]:
        """Clean up temporary files created during health checks."""
        try:
            temp_dir = Path(tempfile.gettempdir())
            cleanup_count = 0
            freed_space = 0

            # Clean up health check related temp files
            patterns = ["health_check_", "tmp_health_", "resync_temp_"]

            for pattern in patterns:
                for file_path in temp_dir.glob(f"{pattern}*"):
                    if file_path.is_file():
                        try:
                            # Check if file is old (older than 1 hour)
                            file_age = time.time() - file_path.stat().st_mtime
                            if file_age > 3600:  # 1 hour
                                file_size = file_path.stat().st_size
                                file_path.unlink()
                                cleanup_count += 1
                                freed_space += file_size

                        except Exception as e:
                            logger.warning(
                                "failed_to_cleanup_temp_file",
                                file=str(file_path),
                                error=str(e),
                            )

            return {
                "action": "temp_file_cleanup",
                "timestamp": datetime.now().isoformat(),
                "files_cleaned": cleanup_count,
                "space_freed_bytes": freed_space,
                "space_freed_mb": round(freed_space / (1024 * 1024), 2),
            }

        except Exception as e:
            logger.error("temp_file_cleanup_failed", error=str(e))
            return {
                "action": "temp_file_cleanup",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def get_memory_statistics(self) -> Dict[str, Any]:
        """Get current memory usage statistics."""
        return {
            "current_usage_mb": round(self.current_memory_usage_mb, 2),
            "peak_usage_mb": round(self.peak_memory_usage_mb, 2),
            "threshold_mb": self.memory_usage_threshold_mb,
            "usage_percent": (
                round(
                    (
                        self.current_memory_usage_mb
                        / self.memory_usage_threshold_mb
                        * 100
                    ),
                    2,
                )
                if self.memory_usage_threshold_mb > 0
                else 0
            ),
            "last_cleanup": (
                self.last_cleanup_time.isoformat() if self.last_cleanup_time else None
            ),
            "monitoring_enabled": self.enable_memory_monitoring,
            "cleanup_interval_seconds": self.cleanup_interval_seconds,
            "configuration": {
                "max_history_entries": self.max_history_entries,
                "history_retention_days": self.history_retention_days,
                "cleanup_threshold_percent": self.history_cleanup_threshold * 100,
                "cleanup_batch_size": self.history_cleanup_batch_size,
            },
        }

    async def optimize_memory_usage(self) -> Dict[str, Any]:
        """Perform comprehensive memory optimization."""
        optimization_results = {
            "actions_performed": [],
            "memory_before_mb": self.current_memory_usage_mb,
            "timestamp": datetime.now().isoformat(),
        }

        try:
            # 1. Force garbage collection
            gc.collect()
            optimization_results["actions_performed"].append("garbage_collection")

            # 2. Clean up temp files
            temp_cleanup = await self.cleanup_temp_files()
            optimization_results["actions_performed"].append("temp_file_cleanup")
            optimization_results["temp_cleanup"] = temp_cleanup

            # 3. Update memory usage
            await self._update_memory_usage()

            # 4. Check system memory
            memory = psutil.virtual_memory()
            if memory.percent > 85:
                optimization_results["actions_performed"].append(
                    "memory_warning_logged"
                )

            optimization_results["memory_after_mb"] = self.current_memory_usage_mb
            optimization_results["memory_optimized_mb"] = round(
                optimization_results["memory_before_mb"] - self.current_memory_usage_mb,
                2,
            )

            logger.info(
                "memory_optimization_completed",
                actions=len(optimization_results["actions_performed"]),
                memory_optimized_mb=optimization_results["memory_optimized_mb"],
            )

        except Exception as e:
            logger.error("memory_optimization_failed", error=str(e))
            optimization_results["error"] = str(e)

        return optimization_results
