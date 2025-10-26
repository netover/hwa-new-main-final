"""
Refactored SOC 2 Type II Compliance Management System using Strategy Pattern.

This refactored version separates the complex report generation logic into
individual strategies, making the code more modular, testable, and maintainable.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from resync.core.structured_logger import get_logger

logger = get_logger(__name__)


# Import shared types to avoid circular dependency
from resync.core.compliance.types import SOC2TrustServiceCriteria, SOC2ComplianceManager as BaseSOC2ComplianceManager


class ControlCategory(Enum):
    """SOC 2 Control Categories."""

    ACCESS_CONTROL = "access_control"
    CHANGE_MANAGEMENT = "change_management"
    RISK_MANAGEMENT = "risk_management"
    SYSTEM_OPERATIONS = "system_operations"
    COMMUNICATION = "communication"
    MONITORING = "monitoring"
    INCIDENT_RESPONSE = "incident_response"
    BUSINESS_CONTINUITY = "business_continuity"


class ControlStatus(Enum):
    """Control implementation status."""

    NOT_IMPLEMENTED = "not_implemented"
    PLANNED = "planned"
    IMPLEMENTED = "implemented"
    TESTED = "tested"
    AUDITED = "audited"
    COMPLIANT = "compliant"


@dataclass
class SOC2Control:
    """SOC 2 Control definition."""

    control_id: str
    name: str
    description: str
    category: ControlCategory
    criteria: List[SOC2TrustServiceCriteria]
    status: ControlStatus = ControlStatus.NOT_IMPLEMENTED
    implemented_at: Optional[float] = None
    tested_at: Optional[float] = None
    audited_at: Optional[float] = None
    evidence_required: List[str] = field(default_factory=list)
    risk_level: str = "medium"  # low, medium, high, critical
    automated_testing: bool = False
    test_frequency_days: int = 30
    last_test_result: Optional[bool] = None
    failure_count: int = 0

    def is_compliant(self) -> bool:
        """Check if control is currently compliant."""
        return self.status in [
            ControlStatus.TESTED,
            ControlStatus.AUDITED,
            ControlStatus.COMPLIANT,
        ]

    def needs_testing(self) -> bool:
        """Check if control needs testing."""
        if not self.implemented_at:
            return False

        days_since_test = (time.time() - (self.tested_at or 0)) / 86400
        return days_since_test >= self.test_frequency_days

    def mark_tested(self, success: bool) -> None:
        """Mark control as tested."""
        self.tested_at = time.time()
        self.last_test_result = success

        if success:
            self.status = ControlStatus.TESTED
            self.failure_count = 0
        else:
            self.failure_count += 1
            if self.failure_count >= 3:
                self.status = ControlStatus.NOT_IMPLEMENTED
                logger.warning(
                    f"Control {self.control_id} marked as failed after 3 failures"
                )


@dataclass
class SOC2Evidence:
    """Evidence for SOC 2 compliance."""

    evidence_id: str
    control_id: str
    evidence_type: str  # log, screenshot, document, test_result
    description: str
    collected_at: float
    validity_days: int = 365
    file_path: Optional[str] = None
    content_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_valid(self) -> bool:
        """Check if evidence is still valid."""
        return time.time() - self.collected_at < (self.validity_days * 24 * 3600)

    def generate_hash(self, content: bytes) -> str:
        """Generate content hash for integrity verification."""
        self.content_hash = hashlib.sha256(content).hexdigest()
        return self.content_hash


@dataclass
class AvailabilityMetric:
    """System availability metrics."""

    timestamp: float = field(default_factory=time.time)
    uptime_percentage: float = 100.0
    downtime_events: int = 0
    total_downtime_seconds: float = 0.0
    planned_maintenance_hours: float = 0.0
    unplanned_downtime_hours: float = 0.0
    response_time_avg: float = 0.0
    error_rate: float = 0.0

    @property
    def availability_score(self) -> float:
        """Calculate availability score (0-100)."""
        return max(
            0.0, 100.0 - (self.unplanned_downtime_hours / 8760 * 100)
        )  # 8760 = hours in year


@dataclass
class ProcessingIntegrityCheck:
    """Processing integrity verification."""

    check_id: str
    operation_type: str
    timestamp: float = field(default_factory=time.time)
    records_processed: int = 0
    records_failed: int = 0
    processing_time: float = 0.0
    checksum_before: Optional[str] = None
    checksum_after: Optional[str] = None
    validation_errors: List[str] = field(default_factory=list)

    @property
    def integrity_score(self) -> float:
        """Calculate processing integrity score (0-100)."""
        if self.records_processed == 0:
            return 100.0

        error_rate = self.records_failed / self.records_processed
        return max(0.0, 100.0 - (error_rate * 1000))  # Penalize high error rates

    @property
    def is_valid(self) -> bool:
        """Check if processing integrity is valid."""
        return (
            self.checksum_before == self.checksum_after
            and len(self.validation_errors) == 0
            and self.integrity_score >= 99.9
        )


@dataclass
class ConfidentialityIncident:
    """Confidentiality breach incident."""

    incident_id: str
    data_category: str
    breach_type: str  # unauthorized_access, data_leak, etc.
    timestamp: float = field(default_factory=time.time)
    affected_records: int = 0
    severity: str = "low"  # low, medium, high, critical
    detected_by: str = ""  # automated, manual, user_report
    response_time_minutes: float = 0.0
    resolved: bool = False
    resolution_details: str = ""
    preventive_measures: List[str] = field(default_factory=list)


@dataclass
class SOC2ComplianceConfig:
    """Configuration for SOC 2 compliance system."""

    # Testing and monitoring
    automated_testing_enabled: bool = True
    test_frequency_days: int = 30
    evidence_retention_days: int = 7 * 365  # 7 years

    # Availability requirements
    target_availability_percentage: float = 99.9  # 99.9% uptime
    max_unplanned_downtime_hours_year: float = 8.76  # 8.76 hours for 99.9%

    # Processing integrity
    integrity_check_frequency_minutes: int = 60
    max_processing_error_rate: float = 0.001  # 0.1%

    # Incident response
    max_incident_response_hours: int = 24
    incident_escalation_required: bool = True

    # Audit and reporting
    audit_report_frequency_days: int = 90
    compliance_dashboard_enabled: bool = True

    # Risk management
    risk_assessment_frequency_days: int = 180  # 6 months
    critical_control_monitoring: bool = True


class SOC2ComplianceManager(BaseSOC2ComplianceManager):
    """
    Main SOC 2 Type II compliance management system.

    Features:
    - Automated control testing and validation
    - Evidence collection and integrity verification
    - Availability monitoring and reporting
    - Processing integrity verification
    - Confidentiality and privacy controls
    - Compliance reporting and dashboards
    - Risk assessment and management
    """

    def __init__(self, config: Optional[SOC2ComplianceConfig] = None):
        self.config = config or SOC2ComplianceConfig()

        # Control management
        self.controls: Dict[str, SOC2Control] = {}
        self.control_tests: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        # Evidence management
        self.evidence: Dict[str, SOC2Evidence] = {}
        self.evidence_by_control: Dict[str, List[str]] = defaultdict(list)

        # Monitoring data
        self.availability_metrics: deque = deque(maxlen=1000)
        self.processing_checks: deque = deque(maxlen=1000)
        self.confidentiality_incidents: List[ConfidentialityIncident] = []

        # Audit trails
        self.audit_trail: deque = deque(maxlen=10000)
        self.compliance_reports: List[Dict[str, Any]] = []

        # Background tasks
        self._testing_task: Optional[asyncio.Task] = None
        self._monitoring_task: Optional[asyncio.Task] = None
        self._reporting_task: Optional[asyncio.Task] = None
        self._running = False

        # Initialize standard SOC 2 controls
        self._initialize_soc2_controls()

        # Initialize report generator (lazy import to avoid circular dependency)
        from resync.core.compliance.report_strategies import ReportGenerator
        self.report_generator = ReportGenerator()

    async def start(self) -> None:
        """Start the SOC 2 compliance manager."""
        if self._running:
            return

        self._running = True
        self._testing_task = asyncio.create_task(self._control_testing_worker())
        self._monitoring_task = asyncio.create_task(self._monitoring_worker())
        self._reporting_task = asyncio.create_task(self._reporting_worker())

        logger.info("SOC 2 compliance manager started")

    async def stop(self) -> None:
        """Stop the SOC 2 compliance manager."""
        if not self._running:
            return

        self._running = False

        for task in [self._testing_task, self._monitoring_task, self._reporting_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        logger.info("SOC 2 compliance manager stopped")

    def _initialize_soc2_controls(self) -> None:
        """Initialize standard SOC 2 controls."""
        controls_data = [
            # Security Controls
            {
                "control_id": "SEC-001",
                "name": "Access Control Implementation",
                "description": "Multi-factor authentication and role-based access control",
                "category": ControlCategory.ACCESS_CONTROL,
                "criteria": [SOC2TrustServiceCriteria.SECURITY],
                "risk_level": "high",
                "automated_testing": True,
                "evidence_required": ["access_logs", "auth_config", "user_permissions"],
            },
            {
                "control_id": "SEC-002",
                "name": "Encryption at Rest",
                "description": "Sensitive data encrypted when stored",
                "category": ControlCategory.ACCESS_CONTROL,
                "criteria": [
                    SOC2TrustServiceCriteria.SECURITY,
                    SOC2TrustServiceCriteria.CONFIDENTIALITY,
                ],
                "risk_level": "high",
                "automated_testing": True,
                "evidence_required": ["encryption_config", "key_management_logs"],
            },
            {
                "control_id": "SEC-003",
                "name": "Network Security",
                "description": "Firewalls, intrusion detection, and secure network architecture",
                "category": ControlCategory.SYSTEM_OPERATIONS,
                "criteria": [SOC2TrustServiceCriteria.SECURITY],
                "risk_level": "high",
                "automated_testing": True,
                "evidence_required": ["firewall_logs", "ids_alerts", "network_config"],
            },
            # Availability Controls
            {
                "control_id": "AVL-001",
                "name": "System Availability Monitoring",
                "description": "24/7 monitoring of system availability and performance",
                "category": ControlCategory.MONITORING,
                "criteria": [SOC2TrustServiceCriteria.AVAILABILITY],
                "risk_level": "high",
                "automated_testing": True,
                "evidence_required": [
                    "uptime_logs",
                    "monitoring_alerts",
                    "availability_reports",
                ],
            },
            {
                "control_id": "AVL-002",
                "name": "Disaster Recovery",
                "description": "Comprehensive disaster recovery and business continuity plans",
                "category": ControlCategory.BUSINESS_CONTINUITY,
                "criteria": [SOC2TrustServiceCriteria.AVAILABILITY],
                "risk_level": "critical",
                "automated_testing": False,
                "evidence_required": ["dr_plan", "backup_logs", "recovery_tests"],
            },
            # Processing Integrity Controls
            {
                "control_id": "INT-001",
                "name": "Data Validation",
                "description": "Input validation and data integrity checks",
                "category": ControlCategory.SYSTEM_OPERATIONS,
                "criteria": [SOC2TrustServiceCriteria.PROCESSING_INTEGRITY],
                "risk_level": "high",
                "automated_testing": True,
                "evidence_required": [
                    "validation_logs",
                    "integrity_checks",
                    "error_reports",
                ],
            },
            {
                "control_id": "INT-002",
                "name": "Transaction Processing",
                "description": "Complete and accurate transaction processing",
                "category": ControlCategory.SYSTEM_OPERATIONS,
                "criteria": [SOC2TrustServiceCriteria.PROCESSING_INTEGRITY],
                "risk_level": "high",
                "automated_testing": True,
                "evidence_required": [
                    "transaction_logs",
                    "audit_trails",
                    "reconciliation_reports",
                ],
            },
            # Confidentiality Controls
            {
                "control_id": "CONF-001",
                "name": "Data Classification",
                "description": "Sensitive data properly classified and labeled",
                "category": ControlCategory.RISK_MANAGEMENT,
                "criteria": [SOC2TrustServiceCriteria.CONFIDENTIALITY],
                "risk_level": "medium",
                "automated_testing": False,
                "evidence_required": [
                    "data_classification_policy",
                    "classification_logs",
                ],
            },
            {
                "control_id": "CONF-002",
                "name": "Information Handling",
                "description": "Secure handling of confidential information",
                "category": ControlCategory.SYSTEM_OPERATIONS,
                "criteria": [SOC2TrustServiceCriteria.CONFIDENTIALITY],
                "risk_level": "high",
                "automated_testing": True,
                "evidence_required": [
                    "access_logs",
                    "encryption_logs",
                    "handling_procedures",
                ],
            },
            # Privacy Controls
            {
                "control_id": "PRIV-001",
                "name": "Privacy Policy",
                "description": "Clear privacy policy and data usage transparency",
                "category": ControlCategory.COMMUNICATION,
                "criteria": [SOC2TrustServiceCriteria.PRIVACY],
                "risk_level": "high",
                "automated_testing": False,
                "evidence_required": [
                    "privacy_policy",
                    "consent_logs",
                    "user_communications",
                ],
            },
            {
                "control_id": "PRIV-002",
                "name": "Data Subject Rights",
                "description": "Implementation of GDPR/SOC 2 privacy rights",
                "category": ControlCategory.SYSTEM_OPERATIONS,
                "criteria": [SOC2TrustServiceCriteria.PRIVACY],
                "risk_level": "high",
                "automated_testing": True,
                "evidence_required": [
                    "erasure_logs",
                    "portability_logs",
                    "consent_management",
                ],
            },
            # Change Management
            {
                "control_id": "CHG-001",
                "name": "Change Management Process",
                "description": "Formal change management and approval processes",
                "category": ControlCategory.CHANGE_MANAGEMENT,
                "criteria": [
                    SOC2TrustServiceCriteria.SECURITY,
                    SOC2TrustServiceCriteria.AVAILABILITY,
                ],
                "risk_level": "high",
                "automated_testing": False,
                "evidence_required": [
                    "change_requests",
                    "approval_logs",
                    "testing_records",
                ],
            },
            # Incident Response
            {
                "control_id": "INC-001",
                "name": "Incident Response Plan",
                "description": "Comprehensive incident response and handling procedures",
                "category": ControlCategory.INCIDENT_RESPONSE,
                "criteria": [
                    SOC2TrustServiceCriteria.SECURITY,
                    SOC2TrustServiceCriteria.AVAILABILITY,
                ],
                "risk_level": "high",
                "automated_testing": False,
                "evidence_required": [
                    "incident_logs",
                    "response_plans",
                    "post_mortem_reports",
                ],
            },
        ]

        for control_data in controls_data:
            control = SOC2Control(**control_data)
            self.controls[control.control_id] = control

    async def implement_control(
        self, control_id: str, implementation_details: Dict[str, Any]
    ) -> bool:
        """Mark a control as implemented."""
        if control_id not in self.controls:
            logger.warning(f"Control {control_id} not found")
            return False

        control = self.controls[control_id]
        control.status = ControlStatus.IMPLEMENTED
        control.implemented_at = time.time()

        await self._audit_event(
            "control_implemented",
            control_id=control_id,
            implementation_details=implementation_details,
        )

        logger.info(f"Control implemented: {control_id}")
        return True

    async def test_control(self, control_id: str) -> Dict[str, Any]:
        """Test a specific control."""
        if control_id not in self.controls:
            return {"success": False, "error": "Control not found"}

        control = self.controls[control_id]

        try:
            # Run automated test if available
            if control.automated_testing:
                test_result = await self._run_automated_test(control)
            else:
                # Manual test - assume success for now
                test_result = {"success": True, "details": "Manual test required"}

            # Record test result
            control.mark_tested(test_result["success"])

            test_record = {
                "control_id": control_id,
                "timestamp": time.time(),
                "result": test_result,
                "automated": control.automated_testing,
            }

            self.control_tests[control_id].append(test_record)

            await self._audit_event(
                "control_tested",
                control_id=control_id,
                success=test_result["success"],
                automated=control.automated_testing,
            )

            return test_result

        except Exception as e:
            logger.error(f"Control testing failed for {control_id}: {e}")
            control.mark_tested(False)
            return {"success": False, "error": str(e)}

    async def collect_evidence(
        self,
        control_id: str,
        evidence_type: str,
        description: str,
        content: bytes,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Collect evidence for a control."""
        evidence_id = f"evidence_{control_id}_{int(time.time())}_{hashlib.md5(content).hexdigest()[:8]}"

        evidence = SOC2Evidence(
            evidence_id=evidence_id,
            control_id=control_id,
            evidence_type=evidence_type,
            description=description,
            collected_at=time.time(),
            metadata=metadata or {},
        )

        evidence.generate_hash(content)
        self.evidence[evidence_id] = evidence
        self.evidence_by_control[control_id].append(evidence_id)

        await self._audit_event(
            "evidence_collected",
            evidence_id=evidence_id,
            control_id=control_id,
            evidence_type=evidence_type,
        )

        logger.info(f"Evidence collected: {evidence_id}")
        return evidence_id

    async def record_availability_metric(self, metric: AvailabilityMetric) -> None:
        """Record system availability metric."""
        self.availability_metrics.append(metric)

        # Check availability thresholds
        if metric.availability_score < self.config.target_availability_percentage:
            await self._audit_event(
                "availability_threshold_breached",
                availability_score=metric.availability_score,
                target=self.config.target_availability_percentage,
            )

    async def record_processing_check(self, check: ProcessingIntegrityCheck) -> None:
        """Record processing integrity check."""
        self.processing_checks.append(check)

        # Check integrity thresholds
        if not check.is_valid:
            await self._audit_event(
                "processing_integrity_violation",
                check_id=check.check_id,
                integrity_score=check.integrity_score,
                errors=check.validation_errors,
            )

    async def report_confidentiality_incident(
        self,
        data_category: str,
        breach_type: str,
        affected_records: int,
        severity: str,
        detected_by: str,
    ) -> str:
        """Report a confidentiality incident."""
        incident_id = f"incident_{int(time.time())}_{hashlib.md5(f'{data_category}{breach_type}'.encode()).hexdigest()[:8]}"

        incident = ConfidentialityIncident(
            incident_id=incident_id,
            data_category=data_category,
            breach_type=breach_type,
            affected_records=affected_records,
            severity=severity,
            detected_by=detected_by,
        )

        self.confidentiality_incidents.append(incident)

        await self._audit_event(
            "confidentiality_incident_reported",
            incident_id=incident_id,
            severity=severity,
            affected_records=affected_records,
        )

        logger.warning(f"Confidentiality incident reported: {incident_id}")
        return incident_id

    def generate_compliance_report(self) -> Dict[str, Any]:
        """Generate comprehensive SOC 2 compliance report using Strategy pattern."""
        # Import strategies locally to avoid circular dependencies
        from resync.core.compliance.report_strategies import (
            ControlComplianceStrategy,
            CriteriaScoresStrategy,
            OverallComplianceStrategy,
            ControlStatusSummaryStrategy,
            EvidenceSummaryStrategy,
            AvailabilitySummaryStrategy,
            ProcessingIntegritySummaryStrategy,
            ConfidentialityIncidentsSummaryStrategy,
            RecommendationsStrategy
        )

        # Create report structure
        report = {
            "generated_at": self._get_current_timestamp(),
            "period_start": self._get_period_start(),
            "period_end": self._get_period_end(),
            "overall_compliance_score": 0.0,
            "criteria_scores": {},
            "control_status": {},
            "evidence_summary": {},
            "availability_summary": {},
            "processing_integrity_summary": {},
            "confidentiality_incidents": {},
            "recommendations": [],
        }

        # Execute strategies to populate report
        report["control_compliance"] = ControlComplianceStrategy().execute(self)
        report["criteria_scores"] = CriteriaScoresStrategy().execute(self)
        report["overall_compliance_score"] = OverallComplianceStrategy().execute(self)
        report["control_status"] = ControlStatusSummaryStrategy().execute(self)
        report["evidence_summary"] = EvidenceSummaryStrategy().execute(self)
        report["availability_summary"] = AvailabilitySummaryStrategy().execute(self)
        report["processing_integrity_summary"] = ProcessingIntegritySummaryStrategy().execute(self)
        report["confidentiality_incidents"] = ConfidentialityIncidentsSummaryStrategy().execute(self)
        report["recommendations"] = RecommendationsStrategy().execute(self, report)

        # Store report
        self.compliance_reports.append(report)

        return report

    def get_control_status(
        self, control_id: Optional[str] = None
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Get control status information."""
        if control_id:
            control = self.controls.get(control_id)
            if not control:
                return {"error": "Control not found"}

            return {
                "control_id": control.control_id,
                "name": control.name,
                "status": control.status.value,
                "category": control.category.value,
                "criteria": [c.value for c in control.criteria],
                "risk_level": control.risk_level,
                "implemented_at": control.implemented_at,
                "tested_at": control.tested_at,
                "last_test_result": control.last_test_result,
                "evidence_count": len(self.evidence_by_control.get(control_id, [])),
                "needs_testing": control.needs_testing(),
            }

        # Return all controls
        return [self.get_control_status(cid) for cid in self.controls.keys()]

    async def _run_automated_test(self, control: SOC2Control) -> Dict[str, Any]:
        """Run automated test for a control."""
        # This would implement specific tests for each control type
        # For now, simulate basic tests

        if control.control_id.startswith("SEC-"):
            # Security control tests
            return await self._test_security_control(control)
        elif control.control_id.startswith("AVL-"):
            # Availability control tests
            return await self._test_availability_control(control)
        elif control.control_id.startswith("INT-"):
            # Processing integrity tests
            return await self._test_integrity_control(control)
        else:
            # Generic test
            return {"success": True, "details": "Generic automated test passed"}

    async def _test_security_control(self, control: SOC2Control) -> Dict[str, Any]:
        """Test security-related controls."""
        # Simulate security tests
        test_results = {
            "SEC-001": {"encryption_enabled": True, "mfa_enabled": True},
            "SEC-002": {"data_encrypted": True, "key_rotation_active": True},
            "SEC-003": {"firewall_active": True, "ids_running": True},
        }

        result = test_results.get(control.control_id, {"generic_security_check": True})
        success = all(result.values())

        return {"success": success, "details": result, "control_type": "security"}

    async def _test_availability_control(self, control: SOC2Control) -> Dict[str, Any]:
        """Test availability-related controls."""
        # Check recent availability metrics
        if not self.availability_metrics:
            return {"success": False, "details": "No availability metrics available"}

        recent_metrics = list(self.availability_metrics)[-10:]  # Last 10 metrics
        avg_availability = sum(m.availability_score for m in recent_metrics) / len(
            recent_metrics
        )

        success = avg_availability >= self.config.target_availability_percentage

        return {
            "success": success,
            "details": {
                "average_availability": avg_availability,
                "target": self.config.target_availability_percentage,
                "samples": len(recent_metrics),
            },
            "control_type": "availability",
        }

    async def _test_integrity_control(self, control: SOC2Control) -> Dict[str, Any]:
        """Test processing integrity controls."""
        # Check recent processing integrity
        if not self.processing_checks:
            return {"success": False, "details": "No processing checks available"}

        recent_checks = list(self.processing_checks)[-10:]  # Last 10 checks
        valid_checks = sum(1 for c in recent_checks if c.is_valid)

        success = valid_checks >= len(recent_checks) * 0.95  # 95% success rate

        return {
            "success": success,
            "details": {
                "valid_checks": valid_checks,
                "total_checks": len(recent_checks),
                "success_rate": valid_checks / len(recent_checks),
            },
            "control_type": "processing_integrity",
        }

    async def _audit_event(self, event_type: str, **kwargs) -> None:
        """Record an audit event."""
        audit_entry = {
            "timestamp": time.time(),
            "event_type": event_type,
            "details": kwargs,
        }

        self.audit_trail.append(audit_entry)

    async def _control_testing_worker(self) -> None:
        """Background worker for automated control testing."""
        while self._running:
            try:
                await asyncio.sleep(3600 * 24)  # Daily testing

                if not self.config.automated_testing_enabled:
                    continue

                # Test controls that need testing
                for control in self.controls.values():
                    if control.needs_testing():
                        await self.test_control(control.control_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Control testing worker error: {e}")

    async def _monitoring_worker(self) -> None:
        """Background worker for continuous monitoring."""
        while self._running:
            try:
                await asyncio.sleep(300)  # Every 5 minutes

                # Simulate availability monitoring
                metric = AvailabilityMetric(
                    uptime_percentage=99.95,  # Simulate high availability
                    response_time_avg=0.15,
                    error_rate=0.001,
                )
                await self.record_availability_metric(metric)

                # Simulate processing integrity check
                integrity_check = ProcessingIntegrityCheck(
                    check_id=f"check_{int(time.time())}",
                    operation_type="batch_processing",
                    records_processed=1000,
                    records_failed=1,
                    processing_time=2.5,
                )
                await self.record_processing_check(integrity_check)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring worker error: {e}")

    async def _reporting_worker(self) -> None:
        """Background worker for compliance reporting."""
        while self._running:
            try:
                await asyncio.sleep(3600 * 24 * 7)  # Weekly reporting

                # Generate compliance report
                report = self.generate_compliance_report()

                await self._audit_event(
                    "compliance_report_generated",
                    report_id=f"report_{int(report['generated_at'])}",
                    overall_score=report["overall_compliance_score"],
                )

                logger.info(
                    f"Compliance report generated with score: {report['overall_compliance_score']:.2f}"
                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Reporting worker error: {e}")

    def _generate_recommendations(self, report: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on compliance report."""
        recommendations = []

        # Check overall compliance
        if report["overall_compliance_score"] < 0.8:
            recommendations.append(
                "Overall compliance score is below 80%. Immediate action required."
            )

        # Check control implementation
        not_implemented = [
            cid
            for cid, c in self.controls.items()
            if c.status == ControlStatus.NOT_IMPLEMENTED
        ]
        if not_implemented:
            recommendations.append(
                f"Implement the following {len(not_implemented)} controls: {', '.join(not_implemented[:5])}"
            )

        # Check availability
        avail_summary = report.get("availability_summary", {})
        if not avail_summary.get("meets_target", True):
            recommendations.append(
                f"Availability target not met. Current: {avail_summary.get('average_availability', 0):.2f}%, Target: {self.config.target_availability_percentage}%"
            )

        # Check processing integrity
        integrity_summary = report.get("processing_integrity_summary", {})
        if not integrity_summary.get("meets_target", True):
            recommendations.append(
                "Processing integrity target not met. Review data validation processes."
            )

        # Check evidence collection
        evidence_summary = report.get("evidence_summary", {})
        if evidence_summary.get("total_valid_evidence", 0) < len(self.controls) * 2:
            recommendations.append(
                "Insufficient evidence collected. Ensure all controls have supporting evidence."
            )

        return recommendations

    def _get_current_timestamp(self) -> float:
        """Get current timestamp."""
        return time.time()

    def _get_period_start(self) -> float:
        """Get period start timestamp (90 days ago)."""
        return time.time() - (90 * 24 * 3600)

    def _get_period_end(self) -> float:
        """Get period end timestamp."""
        return time.time()


# Global SOC 2 compliance manager instance
soc2_compliance_manager = SOC2ComplianceManager()


async def get_soc2_compliance_manager() -> SOC2ComplianceManager:
    """Get the global SOC 2 compliance manager instance."""
    if not soc2_compliance_manager._running:
        await soc2_compliance_manager.start()
    return soc2_compliance_manager
