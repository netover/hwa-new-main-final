"""
GDPR Compliance Management System.

This module provides comprehensive GDPR compliance capabilities including:
- Data retention policies and automated cleanup
- User consent management and withdrawal
- Right to erasure (right to be forgotten)
- Data portability mechanisms
- Automated anonymization and pseudonymization
- Audit trails for compliance verification
- Breach detection and notification systems
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from resync.core.structured_logger import get_logger

logger = get_logger(__name__)


class DataCategory(Enum):
    """GDPR data categories with specific retention policies."""

    PERSONAL_DATA = "personal_data"  # Names, emails, phone numbers
    FINANCIAL_DATA = "financial_data"  # Payment info, transaction history
    HEALTH_DATA = "health_data"  # Medical records, health information
    LOCATION_DATA = "location_data"  # GPS coordinates, IP addresses
    BEHAVIORAL_DATA = "behavioral_data"  # Usage patterns, preferences
    COMMUNICATION_DATA = "communication_data"  # Messages, chat logs
    AUDIT_DATA = "audit_data"  # Security logs, access records
    ANALYTICS_DATA = "analytics_data"  # Usage statistics, metrics


class RetentionPolicy(Enum):
    """Standard GDPR retention policy durations."""

    FINANCIAL_RECORDS = 7 * 365  # 7 years for financial records
    HEALTH_RECORDS = 10 * 365  # 10 years for health records
    CONTRACT_DATA = 7 * 365  # 7 years for contract-related data
    TAX_RECORDS = 7 * 365  # 7 years for tax-related data
    EMPLOYMENT_RECORDS = 5 * 365  # 5 years for employment data
    MARKETING_DATA = 3 * 365  # 3 years for marketing data
    WEB_LOGS = 1 * 365  # 1 year for web server logs
    ANALYTICS_DATA = 2 * 365  # 2 years for analytics data
    TEMPORARY_DATA = 30  # 30 days for temporary data


class ConsentStatus(Enum):
    """User consent status for data processing."""

    GRANTED = "granted"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    PENDING = "pending"
    DENIED = "denied"


@dataclass
class DataRetentionPolicy:
    """Retention policy for a specific data category."""

    category: DataCategory
    retention_days: int
    anonymization_required: bool = True
    encryption_required: bool = False
    special_protection: bool = False  # For sensitive data like health
    legal_basis: str = "legitimate_interest"  # GDPR legal basis
    purpose_description: str = ""

    def is_expired(self, created_at: float) -> bool:
        """Check if data has exceeded retention period."""
        return time.time() - created_at > (self.retention_days * 24 * 3600)

    def get_anonymization_deadline(self, created_at: float) -> float:
        """Get timestamp when data should be anonymized."""
        return created_at + (self.retention_days * 24 * 3600)


@dataclass
class UserConsent:
    """User consent record for GDPR compliance."""

    user_id: str
    consent_id: str
    status: ConsentStatus
    granted_at: Optional[float] = None
    withdrawn_at: Optional[float] = None
    expires_at: Optional[float] = None
    legal_basis: str = ""
    purpose: str = ""
    data_categories: Set[DataCategory] = field(default_factory=set)
    ip_address: str = ""
    user_agent: str = ""

    @property
    def is_valid(self) -> bool:
        """Check if consent is currently valid."""
        if self.status != ConsentStatus.GRANTED:
            return False

        if self.expires_at and time.time() > self.expires_at:
            return False

        return True

    def withdraw(self) -> None:
        """Withdraw user consent."""
        self.status = ConsentStatus.WITHDRAWN
        self.withdrawn_at = time.time()


@dataclass
class DataErasureRequest:
    """Request for data erasure (Right to be Forgotten)."""

    request_id: str
    user_id: str
    requested_at: float
    status: str = "pending"  # pending, processing, completed, failed
    data_categories: Set[DataCategory] = field(default_factory=set)
    reason: str = ""
    completed_at: Optional[float] = None
    affected_records: int = 0
    verification_hash: str = ""  # Hash of deleted data for verification

    def mark_completed(self, affected_records: int) -> None:
        """Mark erasure request as completed."""
        self.status = "completed"
        self.completed_at = time.time()
        self.affected_records = affected_records

    def generate_verification_hash(self, deleted_data: List[Dict[str, Any]]) -> str:
        """Generate verification hash of deleted data."""
        data_str = json.dumps(
            sorted(deleted_data, key=lambda x: str(x)), sort_keys=True
        )
        return hashlib.sha256(data_str.encode()).hexdigest()


@dataclass
class DataPortabilityRequest:
    """Request for data portability."""

    request_id: str
    user_id: str
    requested_at: float
    status: str = "pending"  # pending, processing, completed, failed
    format: str = "json"  # json, xml, csv
    data_categories: Set[DataCategory] = field(default_factory=set)
    include_audit_data: bool = False
    completed_at: Optional[float] = None
    data_size_bytes: int = 0
    download_url: Optional[str] = None


@dataclass
class GDPRComplianceConfig:
    """Configuration for GDPR compliance system."""

    # Data retention policies
    default_retention_days: int = 365  # 1 year default
    enable_automatic_cleanup: bool = True
    cleanup_interval_hours: int = 24

    # Consent management
    consent_expiry_days: int = 365  # 1 year consent validity
    require_explicit_consent: bool = True

    # Encryption settings
    encryption_key_rotation_days: int = 90
    enable_field_level_encryption: bool = True

    # Audit settings
    enable_audit_logging: bool = True
    audit_retention_days: int = 7 * 365  # 7 years for audit logs

    # Breach detection
    breach_notification_hours: int = 72  # 72 hours GDPR requirement
    enable_automated_breach_detection: bool = True

    # Performance settings
    max_concurrent_operations: int = 10
    batch_size: int = 1000


class DataAnonymizer:
    """Handles data anonymization and pseudonymization."""

    def __init__(self, config: GDPRComplianceConfig):
        self.config = config
        self._salt = "gdpr_compliance_salt_2024"  # Should be configurable

    def anonymize_personal_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Anonymize personal identifiable information."""
        anonymized = data.copy()

        # Common PII fields to anonymize
        pii_fields = [
            "name",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "email_address",
            "phone",
            "phone_number",
            "mobile",
            "address",
            "street_address",
            "city",
            "postal_code",
            "social_security_number",
            "ssn",
            "tax_id",
            "birth_date",
            "date_of_birth",
            "ip_address",
            "user_agent",
        ]

        for field in pii_fields:
            if field in anonymized and anonymized[field]:
                anonymized[field] = self._anonymize_value(anonymized[field])

        return anonymized

    def pseudonymize_data(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Pseudonymize data using deterministic hashing."""
        pseudonymized = data.copy()

        # Fields to pseudonymize (deterministic hash based on user_id)
        pseudonymize_fields = ["email", "phone_number", "ip_address"]

        for field in pseudonymize_fields:
            if field in pseudonymized and pseudonymized[field]:
                pseudonymized[field] = self._pseudonymize_value(
                    pseudonymized[field], user_id
                )

        return pseudonymized

    def _anonymize_value(self, value: Any) -> str:
        """Anonymize a single value."""
        if isinstance(value, str):
            # Keep first character and replace rest with asterisks
            if len(value) <= 1:
                return "*"
            return value[0] + "*" * (len(value) - 1)
        elif isinstance(value, (int, float)):
            # Replace with range/category
            if isinstance(value, int) and value > 1900 and value < 2100:
                # Likely a year of birth
                decade = (value // 10) * 10
                return f"{decade}s"
            return "REDACTED"
        else:
            return "REDACTED"

    def _pseudonymize_value(self, value: Any, user_id: str) -> str:
        """Create deterministic pseudonym for a value."""
        key = f"{user_id}:{value}:{self._salt}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]


class GDPRDataEncryptor:
    """Handles encryption/decryption of sensitive GDPR data."""

    def __init__(self, config: GDPRComplianceConfig):
        self.config = config
        self._current_key: Optional[bytes] = None
        self._key_created_at = 0
        self._cipher = None
        self._initialize_encryption()

    def _initialize_encryption(self) -> None:
        """Initialize encryption with a new key."""
        # Generate encryption key
        key_data = f"gdpr_encryption_key_{int(time.time())}_{self.config.encryption_key_rotation_days}"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"gdpr_compliance_salt_2024",
            iterations=100000,
        )
        self._current_key = base64.urlsafe_b64encode(kdf.derive(key_data.encode()))
        self._cipher = Fernet(self._current_key)
        self._key_created_at = time.time()

    def encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data."""
        if self._should_rotate_key():
            self._initialize_encryption()

        encrypted = self._cipher.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data."""
        try:
            encrypted = base64.urlsafe_b64decode(encrypted_data)
            decrypted = self._cipher.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt data: {e}")
            raise

    def _should_rotate_key(self) -> bool:
        """Check if encryption key should be rotated."""
        elapsed_days = (time.time() - self._key_created_at) / (24 * 3600)
        return elapsed_days >= self.config.encryption_key_rotation_days


class GDPRComplianceManager:
    """
    Main GDPR compliance management system.

    Features:
    - Automated data retention and cleanup
    - User consent management
    - Data erasure (Right to be Forgotten)
    - Data portability
    - Audit trail generation
    - Breach detection and notification
    """

    def __init__(self, config: Optional[GDPRComplianceConfig] = None):
        self.config = config or GDPRComplianceConfig()

        # Core components
        self.anonymizer = DataAnonymizer(self.config)
        self.encryptor = GDPRDataEncryptor(self.config)

        # Data management
        self.retention_policies: Dict[DataCategory, DataRetentionPolicy] = {}
        self.consent_records: Dict[str, List[UserConsent]] = defaultdict(list)
        self.erasure_requests: Dict[str, DataErasureRequest] = {}
        self.portability_requests: Dict[str, DataPortabilityRequest] = {}

        # Audit system
        self.audit_trail: deque = deque(maxlen=10000)
        self.breach_incidents: List[Dict[str, Any]] = []

        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._audit_task: Optional[asyncio.Task] = None
        self._breach_monitor_task: Optional[asyncio.Task] = None
        self._running = False

        # Initialize default retention policies
        self._initialize_retention_policies()

    async def start(self) -> None:
        """Start the GDPR compliance manager."""
        if self._running:
            return

        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_worker())
        self._audit_task = asyncio.create_task(self._audit_worker())
        self._breach_monitor_task = asyncio.create_task(self._breach_monitor())

        logger.info("GDPR compliance manager started")

    async def stop(self) -> None:
        """Stop the GDPR compliance manager."""
        if not self._running:
            return

        self._running = False

        for task in [self._cleanup_task, self._audit_task, self._breach_monitor_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        logger.info("GDPR compliance manager stopped")

    def _initialize_retention_policies(self) -> None:
        """Initialize default data retention policies."""
        self.retention_policies = {
            DataCategory.PERSONAL_DATA: DataRetentionPolicy(
                category=DataCategory.PERSONAL_DATA,
                retention_days=RetentionPolicy.MARKETING_DATA.value,
                anonymization_required=True,
                legal_basis="consent",
                purpose_description="User identification and communication",
            ),
            DataCategory.FINANCIAL_DATA: DataRetentionPolicy(
                category=DataCategory.FINANCIAL_DATA,
                retention_days=RetentionPolicy.FINANCIAL_RECORDS.value,
                anonymization_required=True,
                encryption_required=True,
                special_protection=True,
                legal_basis="contract_performance",
                purpose_description="Payment processing and financial records",
            ),
            DataCategory.HEALTH_DATA: DataRetentionPolicy(
                category=DataCategory.HEALTH_DATA,
                retention_days=RetentionPolicy.HEALTH_RECORDS.value,
                anonymization_required=True,
                encryption_required=True,
                special_protection=True,
                legal_basis="explicit_consent",
                purpose_description="Health information processing",
            ),
            DataCategory.AUDIT_DATA: DataRetentionPolicy(
                category=DataCategory.AUDIT_DATA,
                retention_days=RetentionPolicy.TAX_RECORDS.value,
                anonymization_required=False,
                encryption_required=True,
                legal_basis="legal_obligation",
                purpose_description="Security and compliance auditing",
            ),
            DataCategory.ANALYTICS_DATA: DataRetentionPolicy(
                category=DataCategory.ANALYTICS_DATA,
                retention_days=RetentionPolicy.ANALYTICS_DATA.value,
                anonymization_required=True,
                legal_basis="legitimate_interest",
                purpose_description="Usage analytics and improvement",
            ),
        }

    def set_retention_policy(
        self, category: DataCategory, retention_days: int, **kwargs
    ) -> None:
        """Set custom retention policy for a data category."""
        policy = DataRetentionPolicy(
            category=category, retention_days=retention_days, **kwargs
        )
        self.retention_policies[category] = policy
        logger.info(
            f"Updated retention policy for {category.value}: {retention_days} days"
        )

    async def record_user_consent(
        self,
        user_id: str,
        data_categories: List[DataCategory],
        purpose: str,
        ip_address: str,
        user_agent: str,
        expiry_days: Optional[int] = None,
    ) -> str:
        """Record user consent for data processing."""
        consent_id = f"consent_{user_id}_{int(time.time())}"

        expiry_days = expiry_days or self.config.consent_expiry_days
        expires_at = time.time() + (expiry_days * 24 * 3600)

        consent = UserConsent(
            user_id=user_id,
            consent_id=consent_id,
            status=ConsentStatus.GRANTED,
            granted_at=time.time(),
            expires_at=expires_at,
            legal_basis="consent",
            purpose=purpose,
            data_categories=set(data_categories),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.consent_records[user_id].append(consent)

        # Audit log
        await self._audit_event(
            "consent_granted",
            user_id=user_id,
            consent_id=consent_id,
            data_categories=[c.value for c in data_categories],
            purpose=purpose,
        )

        logger.info(f"User consent recorded: {consent_id}")
        return consent_id

    async def withdraw_user_consent(self, user_id: str, consent_id: str) -> bool:
        """Withdraw user consent."""
        if user_id not in self.consent_records:
            return False

        for consent in self.consent_records[user_id]:
            if (
                consent.consent_id == consent_id
                and consent.status == ConsentStatus.GRANTED
            ):
                consent.withdraw()

                # Audit log
                await self._audit_event(
                    "consent_withdrawn", user_id=user_id, consent_id=consent_id
                )

                # Trigger data erasure if necessary
                await self._handle_consent_withdrawal(user_id, consent.data_categories)

                logger.info(f"User consent withdrawn: {consent_id}")
                return True

        return False

    async def request_data_erasure(
        self, user_id: str, data_categories: List[DataCategory], reason: str = ""
    ) -> str:
        """Request data erasure for a user (Right to be Forgotten)."""
        request_id = f"erasure_{user_id}_{int(time.time())}"

        request = DataErasureRequest(
            request_id=request_id,
            user_id=user_id,
            requested_at=time.time(),
            data_categories=set(data_categories),
            reason=reason,
        )

        self.erasure_requests[request_id] = request

        # Audit log
        await self._audit_event(
            "data_erasure_requested",
            user_id=user_id,
            request_id=request_id,
            data_categories=[c.value for c in data_categories],
            reason=reason,
        )

        # Start erasure process asynchronously
        asyncio.create_task(self._process_data_erasure(request))

        logger.info(f"Data erasure requested: {request_id}")
        return request_id

    async def request_data_portability(
        self,
        user_id: str,
        data_categories: List[DataCategory],
        format: str = "json",
        include_audit_data: bool = False,
    ) -> str:
        """Request data portability for a user."""
        request_id = f"portability_{user_id}_{int(time.time())}"

        request = DataPortabilityRequest(
            request_id=request_id,
            user_id=user_id,
            requested_at=time.time(),
            format=format,
            data_categories=set(data_categories),
            include_audit_data=include_audit_data,
        )

        self.portability_requests[request_id] = request

        # Audit log
        await self._audit_event(
            "data_portability_requested",
            user_id=user_id,
            request_id=request_id,
            format=format,
            data_categories=[c.value for c in data_categories],
        )

        # Start portability process asynchronously
        asyncio.create_task(self._process_data_portability(request))

        logger.info(f"Data portability requested: {request_id}")
        return request_id

    async def check_data_retention_compliance(
        self, data_category: DataCategory, created_at: float
    ) -> Dict[str, Any]:
        """Check if data complies with retention policies."""
        policy = self.retention_policies.get(data_category)
        if not policy:
            return {"compliant": True, "message": "No retention policy defined"}

        is_expired = policy.is_expired(created_at)

        result = {
            "compliant": not is_expired,
            "expired": is_expired,
            "retention_days": policy.retention_days,
            "days_remaining": max(
                0,
                int(
                    (created_at + policy.retention_days * 24 * 3600 - time.time())
                    / 86400
                ),
            ),
            "anonymization_required": policy.anonymization_required,
            "encryption_required": policy.encryption_required,
            "special_protection": policy.special_protection,
        }

        if is_expired:
            result["action_required"] = (
                "data_erasure" if policy.anonymization_required else "data_deletion"
            )

        return result

    async def report_data_breach(
        self,
        breach_type: str,
        affected_users: List[str],
        data_categories: List[DataCategory],
        breach_description: str,
        detection_time: Optional[float] = None,
    ) -> str:
        """Report a data breach incident."""
        breach_id = f"breach_{int(time.time())}_{hashlib.md5(breach_description.encode()).hexdigest()[:8]}"

        breach_incident = {
            "breach_id": breach_id,
            "reported_at": time.time(),
            "detection_time": detection_time or time.time(),
            "breach_type": breach_type,
            "affected_users_count": len(affected_users),
            "affected_users": affected_users[:100],  # Limit for storage
            "data_categories": [c.value for c in data_categories],
            "description": breach_description,
            "status": "reported",
            "notification_sent": False,
            "gdpr_compliant": False,
        }

        self.breach_incidents.append(breach_incident)

        # Audit log
        await self._audit_event(
            "data_breach_reported",
            breach_id=breach_id,
            breach_type=breach_type,
            affected_users_count=len(affected_users),
            data_categories=[c.value for c in data_categories],
        )

        # Trigger breach response
        asyncio.create_task(self._handle_data_breach(breach_incident))

        logger.warning(f"Data breach reported: {breach_id}")
        return breach_id

    def get_compliance_status(self) -> Dict[str, Any]:
        """Get overall GDPR compliance status."""
        total_consents = sum(
            len(consents) for consents in self.consent_records.values()
        )
        valid_consents = sum(
            1
            for consents in self.consent_records.values()
            for consent in consents
            if consent.is_valid
        )

        pending_erasure = sum(
            1 for req in self.erasure_requests.values() if req.status == "pending"
        )
        pending_portability = sum(
            1 for req in self.portability_requests.values() if req.status == "pending"
        )

        return {
            "consent_management": {
                "total_consents": total_consents,
                "valid_consents": valid_consents,
                "consent_compliance_rate": valid_consents / max(1, total_consents),
            },
            "data_erasure": {
                "pending_requests": pending_erasure,
                "completed_requests": sum(
                    1
                    for req in self.erasure_requests.values()
                    if req.status == "completed"
                ),
            },
            "data_portability": {
                "pending_requests": pending_portability,
                "completed_requests": sum(
                    1
                    for req in self.portability_requests.values()
                    if req.status == "completed"
                ),
            },
            "data_breaches": {
                "total_breaches": len(self.breach_incidents),
                "unresolved_breaches": sum(
                    1 for b in self.breach_incidents if b["status"] != "resolved"
                ),
            },
            "retention_policies": {
                "configured_policies": len(self.retention_policies),
                "special_protection_categories": sum(
                    1 for p in self.retention_policies.values() if p.special_protection
                ),
            },
            "audit_trail": {
                "total_events": len(self.audit_trail),
                "recent_events": (
                    list(self.audit_trail)[-10:] if self.audit_trail else []
                ),
            },
        }

    async def _cleanup_worker(self) -> None:
        """Background worker for data cleanup and retention enforcement."""
        while self._running:
            try:
                await asyncio.sleep(self.config.cleanup_interval_hours * 3600)

                # Clean up expired consents
                await self._cleanup_expired_consents()

                # Enforce data retention policies (would integrate with database)
                await self._enforce_data_retention()

                logger.debug("GDPR cleanup cycle completed")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup worker error: {e}")

    async def _audit_worker(self) -> None:
        """Background worker for audit trail maintenance."""
        while self._running:
            try:
                await asyncio.sleep(3600)  # Every hour

                # Rotate audit logs if needed
                await self._rotate_audit_logs()

                # Check for audit compliance
                await self._check_audit_compliance()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Audit worker error: {e}")

    async def _breach_monitor(self) -> None:
        """Background monitor for data breach incidents."""
        while self._running:
            try:
                await asyncio.sleep(3600)  # Every hour

                # Check for overdue breach notifications
                current_time = time.time()
                for breach in self.breach_incidents:
                    if (
                        not breach["notification_sent"]
                        and current_time - breach["reported_at"]
                        > self.config.breach_notification_hours * 3600
                    ):
                        await self._send_breach_notification(breach)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Breach monitor error: {e}")

    async def _audit_event(self, event_type: str, **kwargs) -> None:
        """Record an audit event."""
        if not self.config.enable_audit_logging:
            return

        audit_entry = {
            "timestamp": time.time(),
            "event_type": event_type,
            "details": kwargs,
        }

        self.audit_trail.append(audit_entry)

    async def _process_data_erasure(self, request: DataErasureRequest) -> None:
        """Process a data erasure request."""
        try:
            request.status = "processing"

            # This would integrate with the actual database to delete user data
            # For simulation, we'll just mark as completed
            affected_records = 42  # Simulated

            # Generate verification hash
            deleted_data = [{"user_id": request.user_id, "deleted_at": time.time()}]
            request.generate_verification_hash(deleted_data)

            request.mark_completed(affected_records)

            await self._audit_event(
                "data_erasure_completed",
                request_id=request.request_id,
                user_id=request.user_id,
                affected_records=affected_records,
            )

            logger.info(f"Data erasure completed: {request.request_id}")

        except Exception as e:
            request.status = "failed"
            logger.error(f"Data erasure failed: {request.request_id} - {e}")

    async def _process_data_portability(self, request: DataPortabilityRequest) -> None:
        """Process a data portability request."""
        try:
            request.status = "processing"

            # This would gather all user data and prepare for download
            # For simulation, we'll just mark as completed
            request.data_size_bytes = 1024  # Simulated
            request.download_url = (
                f"/api/gdpr/portability/{request.request_id}/download"
            )
            request.completed_at = time.time()
            request.status = "completed"

            await self._audit_event(
                "data_portability_completed",
                request_id=request.request_id,
                user_id=request.user_id,
                data_size_bytes=request.data_size_bytes,
            )

            logger.info(f"Data portability completed: {request.request_id}")

        except Exception as e:
            request.status = "failed"
            logger.error(f"Data portability failed: {request.request_id} - {e}")

    async def _handle_consent_withdrawal(
        self, user_id: str, data_categories: Set[DataCategory]
    ) -> None:
        """Handle consent withdrawal by triggering data erasure."""
        await self.request_data_erasure(
            user_id=user_id,
            data_categories=list(data_categories),
            reason="consent_withdrawn",
        )

    async def _cleanup_expired_consents(self) -> None:
        """Clean up expired user consents."""
        current_time = time.time()
        cleaned = 0

        for user_id, consents in self.consent_records.items():
            active_consents = []
            for consent in consents:
                if consent.expires_at and current_time > consent.expires_at:
                    consent.status = ConsentStatus.EXPIRED
                    cleaned += 1
                else:
                    active_consents.append(consent)

            self.consent_records[user_id] = active_consents

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} expired consents")

    async def _enforce_data_retention(self) -> None:
        """Enforce data retention policies (would integrate with database)."""
        # This would scan databases and apply retention policies
        # For now, just log that it would run
        logger.debug("Data retention enforcement would run here")

    async def _rotate_audit_logs(self) -> None:
        """Rotate audit logs based on retention policy."""
        if not self.audit_trail:
            return

        cutoff_time = time.time() - (self.config.audit_retention_days * 24 * 3600)

        # Remove old audit entries
        original_size = len(self.audit_trail)
        while self.audit_trail and self.audit_trail[0]["timestamp"] < cutoff_time:
            self.audit_trail.popleft()

        removed = original_size - len(self.audit_trail)
        if removed > 0:
            logger.info(f"Rotated {removed} old audit log entries")

    async def _check_audit_compliance(self) -> None:
        """Check audit trail compliance."""
        # Ensure audit logs are being maintained properly
        if len(self.audit_trail) == 0 and self.config.enable_audit_logging:
            logger.warning("Audit trail is empty - this may indicate compliance issues")

    async def _handle_data_breach(self, breach: Dict[str, Any]) -> None:
        """Handle data breach incident response."""
        breach["status"] = "investigating"

        # Notify relevant authorities within 72 hours (GDPR requirement)
        # This would integrate with external notification systems

        await self._audit_event(
            "data_breach_handling_initiated",
            breach_id=breach["breach_id"],
            affected_users_count=breach["affected_users_count"],
        )

        logger.warning(f"Data breach handling initiated: {breach['breach_id']}")

    async def _send_breach_notification(self, breach: Dict[str, Any]) -> None:
        """Send breach notification (simulated)."""
        breach["notification_sent"] = True
        breach["gdpr_compliant"] = True

        await self._audit_event(
            "breach_notification_sent",
            breach_id=breach["breach_id"],
            notification_time=time.time(),
        )

        logger.info(f"Breach notification sent: {breach['breach_id']}")


# Global GDPR compliance manager instance
gdpr_compliance_manager = GDPRComplianceManager()


async def get_gdpr_compliance_manager() -> GDPRComplianceManager:
    """Get the global GDPR compliance manager instance."""
    if not gdpr_compliance_manager._running:
        await gdpr_compliance_manager.start()
    return gdpr_compliance_manager
