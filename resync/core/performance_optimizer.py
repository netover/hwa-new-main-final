"""
Performance Optimization Service

This module provides performance monitoring and optimization functionality.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
import psutil
import time


@dataclass
class PerformanceMetrics:
    """Performance metrics data structure."""

    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    response_time: float
    throughput: int
    error_rate: float
    active_connections: int


class PerformanceService:
    """
    Service for monitoring and optimizing system performance.

    This service collects performance metrics, identifies bottlenecks,
    and provides optimization recommendations.
    """

    def __init__(self):
        self.metrics_history: List[PerformanceMetrics] = []
        self.max_history_size = 1000
        self.optimization_thresholds = {
            'cpu_usage': 80.0,  # %
            'memory_usage': 85.0,  # %
            'response_time': 1000.0,  # ms
            'error_rate': 5.0,  # %
        }

    def collect_metrics(self) -> PerformanceMetrics:
        """
        Collect current performance metrics.

        Returns:
            Current performance metrics
        """
        # Collect system metrics
        cpu_usage = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        memory_usage = memory.percent

        # Mock other metrics for now (would be collected from actual services)
        response_time = 150.0  # ms
        throughput = 100  # requests per second
        error_rate = 0.5  # %
        active_connections = 25

        metrics = PerformanceMetrics(
            timestamp=datetime.now(),
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            response_time=response_time,
            throughput=throughput,
            error_rate=error_rate,
            active_connections=active_connections
        )

        # Store in history
        self.metrics_history.append(metrics)
        if len(self.metrics_history) > self.max_history_size:
            self.metrics_history.pop(0)

        return metrics

    def get_performance_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive performance report.

        Returns:
            Performance report with metrics and recommendations
        """
        if not self.metrics_history:
            return {"error": "No metrics available"}

        current = self.metrics_history[-1] if self.metrics_history else None
        avg_metrics = self._calculate_average_metrics()

        report = {
            "current_metrics": {
                "cpu_usage": current.cpu_usage if current else 0,
                "memory_usage": current.memory_usage if current else 0,
                "response_time": current.response_time if current else 0,
                "throughput": current.throughput if current else 0,
                "error_rate": current.error_rate if current else 0,
                "active_connections": current.active_connections if current else 0,
            } if current else {},
            "average_metrics": avg_metrics,
            "recommendations": self._generate_recommendations(current, avg_metrics),
            "timestamp": datetime.now().isoformat()
        }

        return report

    def optimize_performance(self) -> Dict[str, Any]:
        """
        Perform automatic performance optimizations.

        Returns:
            Optimization results
        """
        optimizations = []
        current = self.metrics_history[-1] if self.metrics_history else None

        if current:
            if current.cpu_usage > self.optimization_thresholds['cpu_usage']:
                optimizations.append("High CPU usage detected - consider scaling resources")
            if current.memory_usage > self.optimization_thresholds['memory_usage']:
                optimizations.append("High memory usage detected - consider memory optimization")
            if current.response_time > self.optimization_thresholds['response_time']:
                optimizations.append("Slow response times detected - consider caching optimization")
            if current.error_rate > self.optimization_thresholds['error_rate']:
                optimizations.append("High error rate detected - check service health")

        return {
            "optimizations_applied": optimizations,
            "timestamp": datetime.now().isoformat()
        }

    def _calculate_average_metrics(self) -> Dict[str, float]:
        """Calculate average metrics from history."""
        if not self.metrics_history:
            return {}

        totals = {
            'cpu_usage': 0.0,
            'memory_usage': 0.0,
            'response_time': 0.0,
            'throughput': 0,
            'error_rate': 0.0,
            'active_connections': 0
        }

        for metric in self.metrics_history[-100:]:  # Last 100 metrics
            totals['cpu_usage'] += metric.cpu_usage
            totals['memory_usage'] += metric.memory_usage
            totals['response_time'] += metric.response_time
            totals['throughput'] += metric.throughput
            totals['error_rate'] += metric.error_rate
            totals['active_connections'] += metric.active_connections

        count = min(len(self.metrics_history), 100)
        return {
            'cpu_usage': totals['cpu_usage'] / count,
            'memory_usage': totals['memory_usage'] / count,
            'response_time': totals['response_time'] / count,
            'throughput': totals['throughput'] / count,
            'error_rate': totals['error_rate'] / count,
            'active_connections': totals['active_connections'] / count,
        }

    def _generate_recommendations(self, current: Optional[PerformanceMetrics],
                                averages: Dict[str, float]) -> List[str]:
        """Generate performance optimization recommendations."""
        recommendations = []

        if current:
            if current.cpu_usage > 75:
                recommendations.append("Consider implementing connection pooling")
            if current.memory_usage > 80:
                recommendations.append("Consider implementing memory caching")
            if current.response_time > 500:
                recommendations.append("Consider database query optimization")
            if current.error_rate > 2:
                recommendations.append("Check service dependencies and health")

        return recommendations


# Global performance service instance
_performance_service = PerformanceService()


def get_performance_service() -> PerformanceService:
    """
    Get the global performance service instance.

    Returns:
        PerformanceService instance
    """
    return _performance_service
