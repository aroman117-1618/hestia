"""
Audit logger for security-sensitive operations.

Provides tamper-resistant logging for credential access, external actions,
and admin operations. 7-year retention for compliance best practices.
"""

import json
import os
import hashlib
import fcntl
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum


class AuditSeverity(Enum):
    """Severity levels for audit events."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AuditEventType(Enum):
    """Types of auditable events."""
    CREDENTIAL_STORED = "credential_stored"
    CREDENTIAL_RETRIEVED = "credential_retrieved"
    CREDENTIAL_DELETED = "credential_deleted"
    SENSITIVE_CREDENTIAL_STORED = "sensitive_credential_stored"
    SENSITIVE_CREDENTIAL_RETRIEVED = "sensitive_credential_retrieved"
    EXTERNAL_ACTION_REQUESTED = "external_action_requested"
    EXTERNAL_ACTION_DECISION = "external_action_decision"
    ADMIN_COMMAND = "admin_command"
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    SESSION_START = "session_start"
    SESSION_END = "session_end"


@dataclass
class AuditEntry:
    """Structured audit log entry."""
    timestamp: str
    event_type: str
    severity: str
    component: str
    details: dict
    user_id: str = "andrew"  # v1.0: single user
    device_id: str = ""
    request_id: str = ""
    session_id: str = ""
    checksum: str = field(default="", init=False)

    def __post_init__(self):
        """Calculate checksum for tamper detection."""
        if not self.checksum:
            self.checksum = self._calculate_checksum()

    def _calculate_checksum(self) -> str:
        """Calculate SHA-256 checksum of entry contents."""
        content = f"{self.timestamp}|{self.event_type}|{self.severity}|{self.component}|{json.dumps(self.details, sort_keys=True)}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self), separators=(',', ':'))


class AuditLogger:
    """
    Security-focused audit logger with tamper detection.

    Features:
    - JSON structured logging
    - Checksum for tamper detection
    - File locking for concurrent access
    - Never logs credential values
    - 7-year retention (handled by admin scripts)
    """

    def __init__(
        self,
        log_dir: Optional[Path] = None,
        log_file: str = "audit.log"
    ):
        """
        Initialize audit logger.

        Args:
            log_dir: Directory for audit logs. Defaults to ~/hestia/logs/
            log_file: Name of audit log file.
        """
        if log_dir is None:
            log_dir = Path.home() / "hestia" / "logs"

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.log_dir / log_file

        # Ensure log file exists
        if not self.log_path.exists():
            self.log_path.touch()

    def log(
        self,
        event_type: Union[str, AuditEventType],
        details: Dict[str, Any],
        severity: Union[str, AuditSeverity] = AuditSeverity.MEDIUM,
        component: str = "security",
        user_id: str = "andrew",
        device_id: str = "",
        request_id: str = "",
        session_id: str = ""
    ) -> AuditEntry:
        """
        Log an audit event.

        Args:
            event_type: Type of event being logged.
            details: Event-specific details (NEVER include credential values).
            severity: Event severity level.
            component: Component generating the event.
            user_id: User associated with the event.
            device_id: Device generating the event.
            request_id: Request ID for tracing.
            session_id: Session ID for context.

        Returns:
            The created audit entry.
        """
        # Normalize enums to strings
        if isinstance(event_type, AuditEventType):
            event_type = event_type.value
        if isinstance(severity, AuditSeverity):
            severity = severity.value

        # Sanitize details to ensure no credential values
        sanitized_details = self._sanitize_details(details)

        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            severity=severity,
            component=component,
            details=sanitized_details,
            user_id=user_id,
            device_id=device_id,
            request_id=request_id,
            session_id=session_id
        )

        self._write_entry(entry)
        return entry

    def log_credential_access(
        self,
        action: str,
        key: str,
        service: str,
        reason: str = "",
        success: bool = True,
        biometric_used: bool = False
    ) -> AuditEntry:
        """
        Convenience method for credential access logging.

        Args:
            action: The action taken (store, retrieve, delete).
            key: Credential key name (NOT the value).
            service: Keychain service partition.
            reason: Why the access was requested.
            success: Whether the operation succeeded.
            biometric_used: Whether biometric auth was required.
        """
        severity = AuditSeverity.HIGH if service == "sensitive" else AuditSeverity.MEDIUM

        if action == "delete":
            severity = AuditSeverity.CRITICAL

        event_type = f"credential_{action}d" if action != "delete" else "credential_deleted"
        if service == "sensitive":
            event_type = f"sensitive_{event_type}"

        return self.log(
            event_type=event_type,
            details={
                "credential_key": key,
                "service": service,
                "reason": reason,
                "success": success,
                "biometric_used": biometric_used
            },
            severity=severity,
            component="credential_manager"
        )

    def _sanitize_details(self, details: dict) -> dict:
        """
        Remove or redact sensitive values from details.

        Never logs:
        - Passwords
        - API keys
        - Credit card numbers
        - SSN
        - Any value that looks like a secret
        """
        sanitized = {}

        # Keys that should never contain sensitive data
        safe_keys = {
            "credential_key", "key", "service", "reason", "success",
            "biometric_used", "timestamp", "action_type", "destination",
            "decision", "severity", "user_id", "device_id"
        }

        # Patterns that indicate sensitive values
        sensitive_patterns = [
            "sk-", "api_", "key_", "token", "password", "secret",
            "ssn", "credit", "card", "bank", "routing"
        ]

        for key, value in details.items():
            if key.lower() in safe_keys:
                sanitized[key] = value
            elif isinstance(value, str):
                # Check if value looks like a secret
                value_lower = value.lower()
                is_sensitive = any(pattern in value_lower for pattern in sensitive_patterns)

                if is_sensitive or len(value) > 50:
                    # Redact but indicate presence
                    sanitized[key] = f"[REDACTED:{len(value)} chars]"
                else:
                    sanitized[key] = value
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_details(value)
            else:
                sanitized[key] = value

        return sanitized

    def _write_entry(self, entry: AuditEntry) -> None:
        """Write entry to log file with file locking."""
        with open(self.log_path, 'a') as f:
            # Acquire exclusive lock for writing
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(entry.to_json() + "\n")
                f.flush()
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def read_entries(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditEntry]:
        """
        Read and filter audit log entries.

        Args:
            start_time: Filter entries after this time.
            end_time: Filter entries before this time.
            event_type: Filter by event type.
            severity: Filter by severity level.
            limit: Maximum entries to return.

        Returns:
            List of matching audit entries.
        """
        entries = []

        with open(self.log_path, 'r') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        data = json.loads(line)
                        entry = AuditEntry(**data)

                        # Apply filters
                        if event_type and entry.event_type != event_type:
                            continue
                        if severity and entry.severity != severity:
                            continue

                        entry_time = datetime.fromisoformat(entry.timestamp)
                        if start_time and entry_time < start_time:
                            continue
                        if end_time and entry_time > end_time:
                            continue

                        entries.append(entry)

                        if len(entries) >= limit:
                            break
                    except (json.JSONDecodeError, TypeError):
                        continue
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        return entries

    def verify_integrity(self) -> Tuple[int, int]:
        """
        Verify integrity of all log entries.

        Returns:
            Tuple of (valid_count, tampered_count).
        """
        valid = 0
        tampered = 0

        for entry in self.read_entries(limit=10000):
            expected_checksum = entry._calculate_checksum()
            if entry.checksum == expected_checksum:
                valid += 1
            else:
                tampered += 1

        return valid, tampered
