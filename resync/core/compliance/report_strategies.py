"""
Compliance Report Generation Strategies.

This module implements the Strategy pattern for generating different parts of the SOC 2 compliance report.
Each strategy is responsible for a specific component of the report, making the code more modular,
testable, and maintainable.
"""

import logging
from typing import Dict, Any, List, Optional, Protocol, runtime_checkable
from collections import defaultdict
from abc import ABC, abstractmethod

# Custom exceptions for better error handling
class ComplianceCalculationError(Exception):
    """Raised when there's an error in compliance calculation."""
    pass


class StrategyValidationError(ValueError):
    """Raised when strategy validation fails."""
    pass


# Lazy import to avoid circular dependency
def _get_soc2_classes():
    """Lazy import to avoid circular dependency."""
    from resync.core.compliance.types import SOC2TrustServiceCriteria
    # Get the actual implementation from soc2_compliance_refactored
    from resync.core.soc2_compliance_refactored import SOC2ComplianceManager
    return SOC2ComplianceManager, SOC2TrustServiceCriteria


# Setup logging
logger = logging.getLogger(__name__)


@runtime_checkable
class ComplianceManagerProtocol(Protocol):
    """Protocol defining the interface expected by report strategies."""

    @property
    def controls(self) -> Dict[str, Any]:
        """Dictionary of compliance controls."""
        ...

    @property
    def evidence(self) -> Dict[str, Any]:
        """Dictionary of compliance evidence."""
        ...

    @property
    def availability_metrics(self) -> List[Any]:
        """List of availability metrics."""
        ...

    @property
    def processing_checks(self) -> List[Any]:
        """List of processing integrity checks."""
        ...

    @property
    def confidentiality_incidents(self) -> List[Any]:
        """List of confidentiality incidents."""
        ...

    @property
    def config(self) -> Any:
        """Configuration object with compliance settings."""
        ...

    def get_current_timestamp(self) -> str:
        """Get current timestamp for report generation."""
        ...

    def get_period_start(self) -> str:
        """Get start of reporting period."""
        ...

    def get_period_end(self) -> str:
        """Get end of reporting period."""
        ...


class ReportStrategy(ABC):
    """Base interface for report generation strategies with enhanced error handling."""

    def validate_manager(self, manager: Any) -> None:
        """Validate that manager implements required protocol."""
        if not isinstance(manager, ComplianceManagerProtocol):
            raise StrategyValidationError(
                "Manager must implement ComplianceManagerProtocol"
            )

    def execute(self, manager: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        """Execute the strategy and return the report component.

        Args:
            manager: The compliance manager instance
            context: Optional context data for strategy execution

        Returns:
            The strategy result data

        Raises:
            StrategyValidationError: If manager validation fails
            ComplianceCalculationError: If calculation fails
        """
        try:
            self.validate_manager(manager)
            return self._execute_strategy(manager, context or {})
        except Exception as e:
            logger.error(f"Error executing strategy {self.__class__.__name__}: {e}")
            if isinstance(e, (StrategyValidationError, ComplianceCalculationError)):
                raise
            raise ComplianceCalculationError(f"Strategy execution failed: {e}")

    @abstractmethod
    def _execute_strategy(self, manager: Any, context: Dict[str, Any]) -> Any:
        """Internal strategy execution method to be implemented by subclasses.

        Args:
            manager: The compliance manager instance
            context: Strategy execution context

        Returns:
            The strategy result data
        """
        raise NotImplementedError("Subclasses must implement _execute_strategy method")


class ControlComplianceStrategy(ReportStrategy):
    """Strategy for calculating control compliance statistics.

    This strategy calculates:
    - Total number of compliance controls
    - Number of controls that are currently compliant
    - Overall compliance rate as a percentage

    Returns:
        Dict containing compliance statistics with keys:
        'total_controls', 'compliant_controls', 'compliance_rate'
    """

    def _execute_strategy(self, manager: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate control compliance statistics with enhanced error handling."""
        try:
            total_controls = len(manager.controls)
            if total_controls == 0:
                logger.warning("No controls found in compliance manager")
                return {
                    "total_controls": 0,
                    "compliant_controls": 0,
                    "compliance_rate": 0.0
                }

            compliant_controls = sum(1 for c in manager.controls.values() if c.is_compliant())

            compliance_rate = compliant_controls / total_controls

            logger.info(f"Control compliance calculated: {compliant_controls}/{total_controls} "
                       f"({compliance_rate:.2%})")

            return {
                "total_controls": total_controls,
                "compliant_controls": compliant_controls,
                "compliance_rate": compliance_rate
            }

        except AttributeError as e:
            raise ComplianceCalculationError(f"Manager missing required attributes: {e}")
        except Exception as e:
            raise ComplianceCalculationError(f"Error calculating control compliance: {e}")


class CriteriaScoresStrategy(ReportStrategy):
    """Strategy for calculating scores for each SOC 2 trust service criteria.

    This strategy analyzes how well each SOC 2 trust service criteria
    (Security, Availability, Processing Integrity, Confidentiality, Privacy)
    is being met based on control compliance.

    Returns:
        Dict mapping criteria names to their scores and statistics
    """

    def _execute_strategy(self, manager: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate criteria scores with enhanced error handling."""
        try:
            criteria_compliance = defaultdict(lambda: {"total": 0, "compliant": 0})

            for control in manager.controls.values():
                for criterion in control.criteria:
                    criteria_compliance[criterion]["total"] += 1
                    if control.is_compliant():
                        criteria_compliance[criterion]["compliant"] += 1

            if not criteria_compliance:
                logger.warning("No criteria found in controls")
                return {}

            criteria_scores = {}
            for criterion, scores in criteria_compliance.items():
                score = scores["compliant"] / max(1, scores["total"])
                criteria_scores[criterion.value] = {
                    "score": score,
                    "compliant_controls": scores["compliant"],
                    "total_controls": scores["total"],
                }

                logger.debug(f"Criteria {criterion.value}: {scores['compliant']}/{scores['total']} "
                           f"({score:.2%})")

            return criteria_scores

        except AttributeError as e:
            raise ComplianceCalculationError(f"Manager or control missing required attributes: {e}")
        except Exception as e:
            raise ComplianceCalculationError(f"Error calculating criteria scores: {e}")


class OverallComplianceStrategy(ReportStrategy):
    """Strategy for calculating overall compliance score.

    This strategy calculates a weighted average compliance score across all
    SOC 2 trust service criteria, using the following weights:
    - Security: 30%
    - Availability: 25%
    - Processing Integrity: 20%
    - Confidentiality: 15%
    - Privacy: 10%

    Returns:
        Float representing the overall compliance score (0.0 to 1.0)
    """

    def _execute_strategy(self, manager: Any, context: Dict[str, Any]) -> float:
        """Calculate weighted average overall compliance score with enhanced error handling."""
        try:
            # Get criteria scores from context if available, otherwise calculate
            criteria_scores = context.get("criteria_scores")
            if criteria_scores is None:
                criteria_strategy = CriteriaScoresStrategy()
                criteria_scores = criteria_strategy.execute(manager)

            if not criteria_scores:
                logger.warning("No criteria scores available for overall calculation")
                return 0.0

            # Lazy import to avoid circular dependency
            _, SOC2TrustServiceCriteria = _get_soc2_classes()

            weights = {
                SOC2TrustServiceCriteria.SECURITY: 0.3,
                SOC2TrustServiceCriteria.AVAILABILITY: 0.25,
                SOC2TrustServiceCriteria.PROCESSING_INTEGRITY: 0.2,
                SOC2TrustServiceCriteria.CONFIDENTIALITY: 0.15,
                SOC2TrustServiceCriteria.PRIVACY: 0.1,
            }

            weighted_score = 0.0
            total_weight = 0.0

            for criterion, weight in weights.items():
                if criterion.value in criteria_scores:
                    score = criteria_scores[criterion.value]["score"]
                    weighted_score += score * weight
                    total_weight += weight
                    logger.debug(f"Criterion {criterion.value}: score={score:.3f}, weight={weight}")

            if total_weight == 0.0:
                logger.warning("No valid criteria found for overall score calculation")
                return 0.0

            overall_score = weighted_score / total_weight
            logger.info(f"Overall compliance score calculated: {overall_score:.3f}")

            return overall_score

        except Exception as e:
            raise ComplianceCalculationError(f"Error calculating overall compliance score: {e}")


class ControlStatusSummaryStrategy(ReportStrategy):
    """Strategy for generating control status summary.

    This strategy counts controls by their current status
    (compliant, non-compliant, pending, etc.).

    Returns:
        Dict mapping status values to their counts
    """

    def _execute_strategy(self, manager: Any, context: Dict[str, Any]) -> Dict[str, int]:
        """Generate summary of control status counts with enhanced error handling."""
        try:
            status_counts = defaultdict(int)

            for control in manager.controls.values():
                status_counts[control.status.value] += 1

            result = dict(status_counts)
            logger.info(f"Control status summary: {result}")

            return result

        except AttributeError as e:
            raise ComplianceCalculationError(f"Manager or control missing required attributes: {e}")
        except Exception as e:
            raise ComplianceCalculationError(f"Error generating control status summary: {e}")


class EvidenceSummaryStrategy(ReportStrategy):
    """Strategy for generating evidence summary.

    This strategy analyzes valid compliance evidence and categorizes it
    by evidence type to provide insights into the evidence landscape.

    Returns:
        Dict containing total valid evidence count and breakdown by type
    """

    def _execute_strategy(self, manager: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary of valid evidence with enhanced error handling."""
        try:
            evidence_counts = defaultdict(int)

            for evidence in manager.evidence.values():
                if evidence.is_valid():
                    key = getattr(evidence.evidence_type, "value", evidence.evidence_type)
                    evidence_counts[key] += 1

            total_valid = sum(evidence_counts.values())
            result = {
                "total_valid_evidence": total_valid,
                "by_type": dict(evidence_counts),
            }

            logger.info(f"Evidence summary: {total_valid} valid evidence items across "
                       f"{len(evidence_counts)} types")

            return result

        except AttributeError as e:
            raise ComplianceCalculationError(f"Manager or evidence missing required attributes: {e}")
        except Exception as e:
            raise ComplianceCalculationError(f"Error generating evidence summary: {e}")


class AvailabilitySummaryStrategy(ReportStrategy):
    """Strategy for generating availability summary.

    This strategy analyzes system availability metrics to determine:
    - Average availability percentage
    - Total downtime in seconds
    - Whether target availability is being met

    Returns:
        Dict containing availability statistics and target compliance status
    """

    def _execute_strategy(self, manager: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary of availability metrics with enhanced error handling."""
        try:
            if not manager.availability_metrics:
                logger.warning("No availability metrics found")
                return {}

            avg_availability = sum(
                m.availability_score for m in manager.availability_metrics
            ) / len(manager.availability_metrics)

            total_downtime = sum(
                m.total_downtime_seconds for m in manager.availability_metrics
            )

            target_availability = manager.config.target_availability_percentage
            meets_target = avg_availability >= target_availability

            result = {
                "average_availability": avg_availability,
                "total_downtime_seconds": total_downtime,
                "target_availability": target_availability,
                "meets_target": meets_target,
            }

            logger.info(f"Availability summary: {avg_availability:.2%} avg availability, "
                       f"{total_downtime}s downtime, meets target: {meets_target}")

            return result

        except AttributeError as e:
            raise ComplianceCalculationError(f"Manager or metrics missing required attributes: {e}")
        except ZeroDivisionError:
            raise ComplianceCalculationError("Cannot calculate average with empty metrics list")
        except Exception as e:
            raise ComplianceCalculationError(f"Error generating availability summary: {e}")


class ProcessingIntegritySummaryStrategy(ReportStrategy):
    """Strategy for generating processing integrity summary.

    This strategy analyzes data processing integrity checks to determine:
    - Average integrity score across all checks
    - Number of failed integrity checks
    - Whether integrity target (99.9%) is being met

    Returns:
        Dict containing integrity statistics and target compliance status
    """

    def _execute_strategy(self, manager: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary of processing integrity metrics with enhanced error handling."""
        try:
            if not manager.processing_checks:
                logger.warning("No processing integrity checks found")
                return {}

            avg_integrity = sum(
                c.integrity_score for c in manager.processing_checks
            ) / len(manager.processing_checks)

            failed_checks = sum(1 for c in manager.processing_checks if not c.is_valid())

            integrity_target = 99.9
            meets_target = avg_integrity >= integrity_target

            result = {
                "average_integrity_score": avg_integrity,
                "failed_checks": failed_checks,
                "total_checks": len(manager.processing_checks),
                "integrity_target": integrity_target,
                "meets_target": meets_target,
            }

            logger.info(f"Processing integrity: {avg_integrity:.1f}% avg score, "
                       f"{failed_checks}/{len(manager.processing_checks)} failed, "
                       f"meets target: {meets_target}")

            return result

        except AttributeError as e:
            raise ComplianceCalculationError(f"Manager or checks missing required attributes: {e}")
        except ZeroDivisionError:
            raise ComplianceCalculationError("Cannot calculate average with empty checks list")
        except Exception as e:
            raise ComplianceCalculationError(f"Error generating processing integrity summary: {e}")


class ConfidentialityIncidentsSummaryStrategy(ReportStrategy):
    """Strategy for generating confidentiality incidents summary.

    This strategy analyzes confidentiality incidents to provide insights on:
    - Total number of confidentiality incidents
    - Breakdown by severity level
    - Count of unresolved incidents

    Returns:
        Dict containing incident statistics and severity breakdown
    """

    def _execute_strategy(self, manager: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary of confidentiality incidents with enhanced error handling."""
        try:
            incident_counts = defaultdict(int)
            for incident in manager.confidentiality_incidents:
                key = getattr(incident.severity, "value", incident.severity)
                incident_counts[key] += 1

            unresolved_incidents = sum(
                1 for i in manager.confidentiality_incidents if not i.resolved
            )

            result = {
                "total_incidents": len(manager.confidentiality_incidents),
                "by_severity": dict(incident_counts),
                "unresolved_incidents": unresolved_incidents,
            }

            logger.info(f"Confidentiality incidents: {len(manager.confidentiality_incidents)} total, "
                       f"{unresolved_incidents} unresolved")

            return result

        except AttributeError as e:
            raise ComplianceCalculationError(f"Manager or incidents missing required attributes: {e}")
        except Exception as e:
            raise ComplianceCalculationError(f"Error generating confidentiality incidents summary: {e}")


class RecommendationsStrategy(ReportStrategy):
    """Strategy for generating recommendations based on compliance analysis.

    This strategy analyzes the complete compliance report and generates
    actionable recommendations for improving SOC 2 compliance posture.

    Returns:
        List of recommendation dictionaries with suggested improvements
    """

    def _execute_strategy(self, manager: Any, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate recommendations based on compliance report with enhanced error handling."""
        try:
            # Get report from context or create basic structure
            report = context.get("report")
            if report is None:
                logger.warning("No report provided in context, generating basic recommendations")
                report = {"overall_compliance_score": 0.0}

            # Reuse the existing _generate_recommendations method
            recommendations = manager._generate_recommendations(report)

            logger.info(f"Generated {len(recommendations)} recommendations")

            return recommendations

        except AttributeError as e:
            raise ComplianceCalculationError(f"Manager missing _generate_recommendations method: {e}")
        except Exception as e:
            raise ComplianceCalculationError(f"Error generating recommendations: {e}")

    def execute(self, manager: Any, report: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Legacy method for backward compatibility.

        Args:
            manager: The compliance manager instance
            report: Optional compliance report for context

        Returns:
            List of recommendation dictionaries
        """
        context = {"report": report} if report is not None else {}
        return super().execute(manager, context)


class ReportGenerator:
    """Facade for generating complete compliance reports using strategies."""
    
    def __init__(self):
        self.strategies = {
            "control_compliance": ControlComplianceStrategy(),
            "criteria_scores": CriteriaScoresStrategy(),
            "overall_compliance": OverallComplianceStrategy(),
            "control_status": ControlStatusSummaryStrategy(),
            "evidence_summary": EvidenceSummaryStrategy(),
            "availability_summary": AvailabilitySummaryStrategy(),
            "processing_integrity_summary": ProcessingIntegritySummaryStrategy(),
            "confidentiality_incidents": ConfidentialityIncidentsSummaryStrategy(),
            "recommendations": RecommendationsStrategy(),
        }
    
    def generate_report(self, manager: Any) -> Dict[str, Any]:
        """Generate a complete compliance report using all strategies with enhanced error handling."""
        try:
            # Validate manager before proceeding
            if not isinstance(manager, ComplianceManagerProtocol):
                raise StrategyValidationError("Manager must implement ComplianceManagerProtocol")

            # Get timestamps safely
            get_ts = getattr(manager, "get_current_timestamp", None)
            generated_at = get_ts() if callable(get_ts) else manager._get_current_timestamp()
            get_start = getattr(manager, "get_period_start", None)
            period_start = get_start() if callable(get_start) else manager._get_period_start()
            get_end = getattr(manager, "get_period_end", None)
            period_end = get_end() if callable(get_end) else manager._get_period_end()

            report = {
                "generated_at": generated_at,
                "period_start": period_start,
                "period_end": period_end,
                "overall_compliance_score": 0.0,
                "criteria_scores": {},
                "control_status": {},
                "evidence_summary": {},
                "availability_summary": {},
                "processing_integrity_summary": {},
                "confidentiality_incidents": {},
                "recommendations": [],
            }

            logger.info("Starting compliance report generation")

            # Execute strategies in dependency order
            report["control_compliance"] = self.strategies["control_compliance"].execute(manager)
            report["criteria_scores"] = self.strategies["criteria_scores"].execute(manager)

            # Pass criteria scores as context to overall compliance calculation
            overall_context = {"criteria_scores": report["criteria_scores"]}
            report["overall_compliance_score"] = self.strategies["overall_compliance"].execute(manager, overall_context)

            report["control_status"] = self.strategies["control_status"].execute(manager)
            report["evidence_summary"] = self.strategies["evidence_summary"].execute(manager)
            report["availability_summary"] = self.strategies["availability_summary"].execute(manager)
            report["processing_integrity_summary"] = self.strategies["processing_integrity_summary"].execute(manager)
            report["confidentiality_incidents"] = self.strategies["confidentiality_incidents"].execute(manager)

            # Pass complete report as context for recommendations
            recommendations_context = {"report": report}
            report["recommendations"] = self.strategies["recommendations"].execute(manager, recommendations_context)

            logger.info(f"Compliance report generated successfully with overall score: "
                       f"{report['overall_compliance_score']:.3f}")

            return report

        except StrategyValidationError:
            raise
        except Exception as e:
            logger.error(f"Error generating compliance report: {e}")
            raise ComplianceCalculationError(f"Failed to generate compliance report: {e}")
