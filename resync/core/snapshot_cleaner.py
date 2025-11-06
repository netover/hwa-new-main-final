"""
Snapshot cleaner for cache management.
"""

from typing import Any, Dict, List


class SnapshotCleaner:
    """Snapshot cleaner implementation."""

    def __init__(self, max_snapshots: int = 10):
        self.max_snapshots = max_snapshots

    def clean_old_snapshots(
        self, snapshots: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Clean old snapshots, keeping only the most recent ones."""
        if len(snapshots) <= self.max_snapshots:
            return snapshots

        # Sort by timestamp (assuming each snapshot has a 'timestamp' field)
        sorted_snapshots = sorted(
            snapshots, key=lambda x: x.get("timestamp", 0), reverse=True
        )

        return sorted_snapshots[: self.max_snapshots]
