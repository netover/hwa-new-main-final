"""Minimal TWS monitor facade used by API endpoints and tests."""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List


class TWSMonitor:
    """In-memory monitor exposing the subset of the legacy API used in tests."""

    def __init__(self) -> None:
        self._alerts: List[Dict[str, Any]] = []

    def get_performance_report(self) -> Dict[str, Any]:
        """Return a stubbed performance report."""
        return {
            "current_metrics": {
                "timestamp": _dt.datetime.utcnow().isoformat(),
                "critical_alerts": 0,
                "warning_alerts": 0,
            },
            "historical_metrics": [],
            "incidents": [],
        }

    def get_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return recent alerts (empty by default)."""
        return self._alerts[:limit]

    def record_alert(self, alert: Dict[str, Any]) -> None:
        """Record an alert for monitoring simulations."""
        self._alerts.append(alert)


tws_monitor = TWSMonitor()

__all__ = ["tws_monitor", "TWSMonitor"]
