"""
Alerting System Module

This module provides the core alerting functionality for the resync system,
including alert rules, severity levels, and alert management.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from resync.api.validation.monitoring import AlertSeverity


@dataclass
class AlertRule:
    """
    Represents an alert rule configuration.

    An alert rule defines the conditions under which an alert should be triggered,
    including the metric to monitor, the condition to check, and the threshold values.
    """

    name: str
    description: str
    metric_name: str
    condition: str  # e.g., ">", "<", ">=", "<=", "==", "!="
    threshold: float
    severity: AlertSeverity

    def __post_init__(self):
        """Validate the alert rule after initialization."""
        if not self.name:
            raise ValueError("Alert rule name cannot be empty")
        if not self.metric_name:
            raise ValueError("Metric name cannot be empty")
        if self.condition not in [">", "<", ">=", "<=", "==", "!="]:
            raise ValueError(f"Invalid condition: {self.condition}")


@dataclass
class Alert:
    """
    Represents an active alert instance.

    An alert is created when an alert rule's conditions are met.
    """

    id: str
    rule_name: str
    message: str
    severity: AlertSeverity
    timestamp: datetime
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    source_ip: Optional[str] = None

    def acknowledge(self, user: str, source_ip: Optional[str] = None) -> None:
        """Mark the alert as acknowledged."""
        self.acknowledged = True
        self.acknowledged_by = user
        self.acknowledged_at = datetime.now()
        self.source_ip = source_ip


class AlertingSystem:
    """
    Central alerting system that manages alert rules and active alerts.

    This class provides the core functionality for:
    - Managing alert rules
    - Monitoring metrics and triggering alerts
    - Tracking and acknowledging active alerts
    """

    def __init__(self):
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_counter = 0

    def add_rule(self, rule: AlertRule) -> None:
        """
        Add a new alert rule to the system.

        Args:
            rule: The alert rule to add
        """
        if rule.name in self.rules:
            raise ValueError(f"Alert rule '{rule.name}' already exists")

        self.rules[rule.name] = rule

    def remove_rule(self, rule_name: str) -> bool:
        """
        Remove an alert rule from the system.

        Args:
            rule_name: Name of the rule to remove

        Returns:
            True if the rule was removed, False if it didn't exist
        """
        if rule_name in self.rules:
            del self.rules[rule_name]
            return True
        return False

    def get_active_alerts(self) -> List[Alert]:
        """
        Get all currently active (non-acknowledged) alerts.

        Returns:
            List of active alerts
        """
        return [alert for alert in self.active_alerts.values() if not alert.acknowledged]

    def acknowledge_alert(self, alert_id: str, source_ip: Optional[str] = None) -> bool:
        """
        Acknowledge an active alert.

        Args:
            alert_id: ID of the alert to acknowledge
            source_ip: IP address of the user acknowledging the alert

        Returns:
            True if the alert was acknowledged, False if not found
        """
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.acknowledge("api_user", source_ip)  # In a real system, this would be the actual user
            return True
        return False

    def trigger_alert(self, rule_name: str, message: str, severity: AlertSeverity) -> str:
        """
        Trigger a new alert.

        Args:
            rule_name: Name of the rule that triggered the alert
            message: Alert message
            severity: Alert severity

        Returns:
            The ID of the created alert
        """
        self.alert_counter += 1
        alert_id = f"alert_{self.alert_counter}"

        alert = Alert(
            id=alert_id,
            rule_name=rule_name,
            message=message,
            severity=severity,
            timestamp=datetime.now()
        )

        self.active_alerts[alert_id] = alert
        return alert_id

    def check_metric(self, metric_name: str, value: float) -> None:
        """
        Check a metric value against all relevant alert rules.

        Args:
            metric_name: Name of the metric to check
            value: Current value of the metric
        """
        for rule in self.rules.values():
            if rule.metric_name == metric_name:
                should_trigger = self._evaluate_condition(value, rule.condition, rule.threshold)
                if should_trigger:
                    message = f"Alert triggered for metric '{metric_name}': {value} {rule.condition} {rule.threshold}"
                    self.trigger_alert(rule.name, message, rule.severity)

    def _evaluate_condition(self, value: float, condition: str, threshold: float) -> bool:
        """
        Evaluate a condition against a metric value.

        Args:
            value: The metric value
            condition: The condition operator
            threshold: The threshold value

        Returns:
            True if the condition is met, False otherwise
        """
        if condition == ">":
            return value > threshold
        elif condition == "<":
            return value < threshold
        elif condition == ">=":
            return value >= threshold
        elif condition == "<=":
            return value <= threshold
        elif condition == "==":
            return value == threshold
        elif condition == "!=":
            return value != threshold
        else:
            return False


# Global alerting system instance
alerting_system = AlertingSystem()
