"""Logging module - structured logging and audit trails."""

from hestia.logging.audit_logger import (
    AuditLogger,
    AuditEntry,
    AuditSeverity,
    AuditEventType,
)

from hestia.logging.structured_logger import (
    HestiaLogger,
    LogEntry,
    LogSeverity,
    LogComponent,
    EventType,
    CredentialSanitizer,
    get_logger,
    set_context,
)

__all__ = [
    # Audit logging
    "AuditLogger",
    "AuditEntry",
    "AuditSeverity",
    "AuditEventType",
    # Structured logging
    "HestiaLogger",
    "LogEntry",
    "LogSeverity",
    "LogComponent",
    "EventType",
    "CredentialSanitizer",
    "get_logger",
    "set_context",
]
