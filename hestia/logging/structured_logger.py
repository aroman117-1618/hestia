"""
Structured logging for Hestia.

Provides JSON-formatted logging with:
- Request ID propagation for tracing
- Credential sanitization
- Log rotation (configurable retention, default 30 days)
- Severity levels
- Component tagging
"""

import json
import os
import re
import uuid
import logging
import fcntl
from datetime import datetime, timezone
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from contextvars import ContextVar


# Context variable for request ID propagation
_request_id: ContextVar[str] = ContextVar('request_id', default='')
_session_id: ContextVar[str] = ContextVar('session_id', default='')
_device_id: ContextVar[str] = ContextVar('device_id', default='')


class LogSeverity(Enum):
    """Log severity levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogComponent(Enum):
    """Hestia components for log categorization."""
    ORCHESTRATION = "orchestration"
    MEMORY = "memory"
    INFERENCE = "inference"
    EXECUTION = "execution"
    SECURITY = "security"
    API = "api"
    SYSTEM = "system"
    VOICE = "voice"
    COUNCIL = "council"
    HEALTH = "health"
    WIKI = "wiki"
    EXPLORER = "explorer"
    NEWSFEED = "newsfeed"
    INVESTIGATE = "investigate"
    RESEARCH = "research"


class EventType(Enum):
    """Common event types."""
    REQUEST = "request"
    RESPONSE = "response"
    MEMORY_ACCESS = "memory_access"
    TOOL_CALL = "tool_call"
    ERROR = "error"
    STATE_CHANGE = "state_change"
    INFERENCE_REQUEST = "inference_request"
    INFERENCE_RESPONSE = "inference_response"
    MODE_SWITCH = "mode_switch"
    STARTUP = "startup"
    SHUTDOWN = "shutdown"


@dataclass
class LogEntry:
    """Structured log entry."""
    timestamp: str
    event_type: str
    severity: str
    component: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    request_id: str = ""
    session_id: str = ""
    device_id: str = ""
    user_id: str = "andrew"

    def to_json(self) -> str:
        """Serialize to JSON string."""
        entry_dict = asdict(self)
        # Remove None values
        entry_dict = {k: v for k, v in entry_dict.items() if v is not None}
        return json.dumps(entry_dict, separators=(',', ':'), default=str)


class CredentialSanitizer:
    """
    Sanitizes sensitive data from log entries.

    Patterns detected and redacted:
    - API keys (sk-*, api_*, key_*)
    - Passwords
    - Credit card numbers
    - SSN
    - Email addresses (partial redaction)
    - OAuth tokens
    """

    # Patterns for sensitive data
    PATTERNS = [
        # API keys (various formats)
        (r'sk-[a-zA-Z0-9\-_]{20,}', '[API_KEY_REDACTED]'),
        (r'api[_-]?key["\s:=]+["\']?([a-zA-Z0-9\-_]{16,})["\']?', r'api_key: [REDACTED]'),

        # Bearer tokens
        (r'Bearer\s+[a-zA-Z0-9\-_\.]+', 'Bearer [TOKEN_REDACTED]'),

        # Credit card numbers (basic pattern)
        (r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b', '[CARD_REDACTED]'),

        # SSN
        (r'\b\d{3}[\s\-]?\d{2}[\s\-]?\d{4}\b', '[SSN_REDACTED]'),

        # Passwords in various formats
        (r'password["\s:=]+["\']?[^"\'\s,}{]+["\']?', 'password: [REDACTED]'),
        (r'passwd["\s:=]+["\']?[^"\'\s,}{]+["\']?', 'passwd: [REDACTED]'),
        (r'secret["\s:=]+["\']?[^"\'\s,}{]+["\']?', 'secret: [REDACTED]'),

        # Generic long tokens (likely secrets)
        (r'\b[a-zA-Z0-9]{40,}\b', '[LONG_TOKEN_REDACTED]'),
    ]

    # Email partial redaction pattern
    EMAIL_PATTERN = re.compile(r'\b([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b')

    def __init__(self):
        self.compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), replacement)
            for pattern, replacement in self.PATTERNS
        ]

    def sanitize(self, value: Any) -> Any:
        """Sanitize a value, recursively handling dicts and lists."""
        if isinstance(value, str):
            return self._sanitize_string(value)
        elif isinstance(value, dict):
            return {k: self.sanitize(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.sanitize(item) for item in value]
        return value

    def _sanitize_string(self, text: str) -> str:
        """Apply all sanitization patterns to a string."""
        result = text

        # Apply regex patterns
        for pattern, replacement in self.compiled_patterns:
            result = pattern.sub(replacement, result)

        # Partial email redaction: user@domain.com -> u***@domain.com
        def redact_email(match):
            local = match.group(1)
            domain = match.group(2)
            if len(local) > 1:
                return f"{local[0]}***@{domain}"
            return f"***@{domain}"

        result = self.EMAIL_PATTERN.sub(redact_email, result)

        return result


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs JSON log entries."""

    def __init__(self, sanitizer: CredentialSanitizer):
        super().__init__()
        self.sanitizer = sanitizer

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Extract extra fields
        data = getattr(record, 'data', {})
        component = getattr(record, 'component', 'system')
        event_type = getattr(record, 'event_type', 'log')
        duration_ms = getattr(record, 'duration_ms', None)

        # Sanitize data
        sanitized_data = self.sanitizer.sanitize(data)
        sanitized_message = self.sanitizer.sanitize(record.getMessage())

        entry = LogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            severity=record.levelname,
            component=component,
            message=sanitized_message,
            data=sanitized_data,
            duration_ms=duration_ms,
            request_id=_request_id.get(),
            session_id=_session_id.get(),
            device_id=_device_id.get()
        )

        return entry.to_json()


class HestiaLogger:
    """
    Main logging interface for Hestia.

    Features:
    - JSON structured logging
    - Automatic credential sanitization
    - Request ID propagation
    - Log rotation (configurable retention, default 30 days from inference.yaml)
    - Component-based filtering
    """

    def __init__(
        self,
        log_dir: Optional[Path] = None,
        log_file: str = "hestia.log",
        retention_days: int = 30,
        level: Union[str, LogSeverity] = LogSeverity.INFO
    ):
        """
        Initialize the Hestia logger.

        Args:
            log_dir: Directory for log files. Defaults to ~/hestia/logs/
            log_file: Name of main log file.
            retention_days: How many days to retain logs.
            level: Minimum log level.
        """
        if log_dir is None:
            log_dir = Path.home() / "hestia" / "logs"

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.log_dir / log_file

        # Set up sanitizer
        self.sanitizer = CredentialSanitizer()

        # Create logger
        self.logger = logging.getLogger("hestia")
        self.logger.setLevel(logging.DEBUG)  # Capture all, filter at handler level

        # Clear existing handlers
        self.logger.handlers.clear()

        # File handler with rotation
        file_handler = TimedRotatingFileHandler(
            self.log_path,
            when='midnight',
            interval=1,
            backupCount=retention_days
        )

        if isinstance(level, LogSeverity):
            level = level.value
        file_handler.setLevel(getattr(logging, level))
        file_handler.setFormatter(JSONFormatter(self.sanitizer))
        self.logger.addHandler(file_handler)

        # Console handler for development (optional)
        if os.environ.get('HESTIA_DEBUG'):
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            console_handler.setFormatter(JSONFormatter(self.sanitizer))
            self.logger.addHandler(console_handler)

    def set_context(
        self,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        device_id: Optional[str] = None
    ) -> None:
        """Set context variables for request tracing."""
        if request_id:
            _request_id.set(request_id)
        if session_id:
            _session_id.set(session_id)
        if device_id:
            _device_id.set(device_id)

    def new_request_id(self) -> str:
        """Generate and set a new request ID."""
        request_id = f"req-{uuid.uuid4().hex[:12]}"
        _request_id.set(request_id)
        return request_id

    def _log(
        self,
        level: int,
        message: str,
        component: Union[str, LogComponent] = LogComponent.SYSTEM,
        event_type: Union[str, EventType] = "log",
        data: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
        exc_info: bool = False
    ) -> None:
        """Internal log method."""
        if isinstance(component, LogComponent):
            component = component.value
        if isinstance(event_type, EventType):
            event_type = event_type.value

        extra = {
            'component': component,
            'event_type': event_type,
            'data': data or {},
            'duration_ms': duration_ms
        }

        self.logger.log(level, message, extra=extra, exc_info=exc_info)

    def debug(
        self,
        message: str,
        component: Union[str, LogComponent] = LogComponent.SYSTEM,
        event_type: Union[str, EventType] = "log",
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log debug message."""
        self._log(logging.DEBUG, message, component, event_type, data)

    def info(
        self,
        message: str,
        component: Union[str, LogComponent] = LogComponent.SYSTEM,
        event_type: Union[str, EventType] = "log",
        data: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None
    ) -> None:
        """Log info message."""
        self._log(logging.INFO, message, component, event_type, data, duration_ms)

    def warning(
        self,
        message: str,
        component: Union[str, LogComponent] = LogComponent.SYSTEM,
        event_type: Union[str, EventType] = "log",
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log warning message."""
        self._log(logging.WARNING, message, component, event_type, data)

    def error(
        self,
        message: str,
        component: Union[str, LogComponent] = LogComponent.SYSTEM,
        event_type: Union[str, EventType] = EventType.ERROR,
        data: Optional[Dict[str, Any]] = None,
        exc_info: bool = True
    ) -> None:
        """Log error message with optional exception info."""
        self._log(logging.ERROR, message, component, event_type, data, exc_info=exc_info)

    def critical(
        self,
        message: str,
        component: Union[str, LogComponent] = LogComponent.SYSTEM,
        event_type: Union[str, EventType] = EventType.ERROR,
        data: Optional[Dict[str, Any]] = None,
        exc_info: bool = True
    ) -> None:
        """Log critical message with optional exception info."""
        self._log(logging.CRITICAL, message, component, event_type, data, exc_info=exc_info)

    # Convenience methods for common operations

    def log_request(
        self,
        endpoint: str,
        method: str = "POST",
        data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Log incoming request and return new request ID."""
        request_id = self.new_request_id()
        self.info(
            f"Request received: {method} {endpoint}",
            component=LogComponent.API,
            event_type=EventType.REQUEST,
            data={"endpoint": endpoint, "method": method, **(data or {})}
        )
        return request_id

    def log_response(
        self,
        status_code: int,
        duration_ms: float,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log outgoing response."""
        self.info(
            f"Response sent: {status_code}",
            component=LogComponent.API,
            event_type=EventType.RESPONSE,
            data={"status_code": status_code, **(data or {})},
            duration_ms=duration_ms
        )

    def log_inference(
        self,
        model: str,
        tokens_in: int,
        tokens_out: int,
        duration_ms: float,
        success: bool = True
    ) -> None:
        """Log inference request."""
        self.info(
            f"Inference completed: {model}",
            component=LogComponent.INFERENCE,
            event_type=EventType.INFERENCE_RESPONSE,
            data={
                "model": model,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "success": success
            },
            duration_ms=duration_ms
        )

    def log_memory_access(
        self,
        operation: str,
        scope: str,
        success: bool = True,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log memory access."""
        self.info(
            f"Memory {operation}: {scope}",
            component=LogComponent.MEMORY,
            event_type=EventType.MEMORY_ACCESS,
            data={"operation": operation, "scope": scope, "success": success, **(data or {})}
        )

    def log_tool_call(
        self,
        tool_name: str,
        success: bool,
        duration_ms: float,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log tool execution."""
        level = logging.INFO if success else logging.WARNING
        self._log(
            level,
            f"Tool executed: {tool_name}",
            component=LogComponent.EXECUTION,
            event_type=EventType.TOOL_CALL,
            data={"tool": tool_name, "success": success, **(data or {})},
            duration_ms=duration_ms
        )

    def log_state_change(
        self,
        from_state: str,
        to_state: str,
        reason: str = ""
    ) -> None:
        """Log state machine transition."""
        self.info(
            f"State change: {from_state} -> {to_state}",
            component=LogComponent.ORCHESTRATION,
            event_type=EventType.STATE_CHANGE,
            data={"from_state": from_state, "to_state": to_state, "reason": reason}
        )

    def log_mode_switch(
        self,
        from_mode: str,
        to_mode: str,
        trigger: str = "explicit"
    ) -> None:
        """Log persona mode switch."""
        self.info(
            f"Mode switch: {from_mode} -> {to_mode}",
            component=LogComponent.ORCHESTRATION,
            event_type=EventType.MODE_SWITCH,
            data={"from_mode": from_mode, "to_mode": to_mode, "trigger": trigger}
        )


# Module-level singleton
_logger: Optional[HestiaLogger] = None


def _read_retention_days_from_config() -> int:
    """Read logging.retention_days from inference.yaml, default 30."""
    try:
        import yaml
        config_path = Path(__file__).parent.parent / "config" / "inference.yaml"
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        return int(data.get("logging", {}).get("retention_days", 30))
    except Exception:
        return 30


def get_logger() -> HestiaLogger:
    """Get or create the singleton logger instance."""
    global _logger
    if _logger is None:
        retention_days = _read_retention_days_from_config()
        _logger = HestiaLogger(retention_days=retention_days)
    return _logger


def set_context(
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
    device_id: Optional[str] = None
) -> None:
    """Set context variables for request tracing."""
    get_logger().set_context(request_id, session_id, device_id)
