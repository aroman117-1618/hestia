"""
Data models for the execution layer.

Defines Tool, ToolCall, ToolResult, and related dataclasses.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import uuid


class ToolParamType(Enum):
    """Supported parameter types for tools."""
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


@dataclass
class ToolParam:
    """Definition of a tool parameter."""
    type: ToolParamType
    description: str = ""
    required: bool = False
    default: Any = None
    enum: Optional[List[Any]] = None  # Allowed values

    def to_json_schema(self) -> Dict[str, Any]:
        """Convert to JSON Schema format for prompt injection."""
        schema = {
            "type": self.type.value,
            "description": self.description,
        }
        if self.enum:
            schema["enum"] = self.enum
        if self.default is not None:
            schema["default"] = self.default
        return schema


@dataclass
class Tool:
    """
    Definition of an executable tool.

    Tools are registered with the ToolRegistry and can be invoked
    by the model during conversation.
    """
    name: str                                    # Unique identifier (e.g., "read_file")
    description: str                             # Human-readable description for prompts
    parameters: Dict[str, ToolParam]             # Parameter definitions
    handler: Callable[..., Any]                  # Async function to execute
    requires_approval: bool = False              # Requires external communication gate
    timeout: float = 30.0                        # Per-tool timeout in seconds
    allowed_paths: Optional[List[str]] = None    # File access restrictions (expanded ~)
    category: str = "general"                    # Tool category for organization

    def __post_init__(self):
        """Validate tool definition."""
        if not self.name:
            raise ValueError("Tool name cannot be empty")
        if not self.description:
            raise ValueError("Tool description cannot be empty")
        if not callable(self.handler):
            raise ValueError("Tool handler must be callable")

    def get_required_params(self) -> List[str]:
        """Get list of required parameter names."""
        return [name for name, param in self.parameters.items() if param.required]

    def to_json_schema(self) -> Dict[str, Any]:
        """
        Convert tool definition to JSON Schema format.

        Used for injecting tool definitions into model prompts.
        """
        properties = {}
        required = []

        for name, param in self.parameters.items():
            properties[name] = param.to_json_schema()
            if param.required:
                required.append(name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                }
            }
        }


@dataclass
class ToolCall:
    """
    A request to execute a tool.

    Created when the model outputs a tool call in its response.
    """
    id: str                                      # Unique call ID (tc-{uuid})
    tool_name: str                               # Name of tool to execute
    arguments: Dict[str, Any] = field(default_factory=dict)  # Arguments to pass

    @classmethod
    def create(cls, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> "ToolCall":
        """Create a new ToolCall with generated ID."""
        return cls(
            id=f"tc-{uuid.uuid4().hex[:12]}",
            tool_name=tool_name,
            arguments=arguments or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolCall":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            tool_name=data["tool_name"],
            arguments=data.get("arguments", {}),
        )


class ToolResultStatus(Enum):
    """Status of a tool execution."""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    DENIED = "denied"  # Gate denied execution
    NOT_FOUND = "not_found"  # Tool not registered


@dataclass
class ToolResult:
    """
    Result of executing a tool.

    Contains the output or error from tool execution.
    """
    call_id: str                                 # ID of the ToolCall this is for
    tool_name: str                               # Name of executed tool
    status: ToolResultStatus                     # Execution status
    output: Any = None                           # Tool output (if success)
    error: Optional[str] = None                  # Error message (if failed)
    duration_ms: float = 0.0                     # Execution time
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def success(self) -> bool:
        """Check if execution was successful."""
        return self.status == ToolResultStatus.SUCCESS

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolResult":
        """Create from dictionary."""
        return cls(
            call_id=data["call_id"],
            tool_name=data["tool_name"],
            status=ToolResultStatus(data["status"]),
            output=data.get("output"),
            error=data.get("error"),
            duration_ms=data.get("duration_ms", 0.0),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.utcnow(),
        )

    def to_message_content(self) -> str:
        """Format result for inclusion in model conversation."""
        if self.success:
            return f"Tool '{self.tool_name}' executed successfully:\n{self.output}"
        else:
            return f"Tool '{self.tool_name}' failed ({self.status.value}): {self.error}"


class GateDecision(Enum):
    """Decision from external communication gate."""
    APPROVED = "approved"
    DENIED = "denied"
    PENDING = "pending"


@dataclass
class GateRequest:
    """Request for approval from external communication gate."""
    id: str
    service: str                                 # Service being accessed
    action: str                                  # Action being performed
    tool_name: str                               # Tool requesting access
    reason: str                                  # Why access is needed
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def create(cls, service: str, action: str, tool_name: str, reason: str) -> "GateRequest":
        """Create a new gate request."""
        return cls(
            id=f"gate-{uuid.uuid4().hex[:12]}",
            service=service,
            action=action,
            tool_name=tool_name,
            reason=reason,
        )


@dataclass
class SandboxConfig:
    """Configuration for sandbox execution."""
    enabled: bool = True
    mode: str = "subprocess"                     # subprocess | docker | sandbox-exec
    default_timeout: float = 30.0
    max_timeout: float = 300.0
    allowed_directories: List[str] = field(default_factory=list)
    auto_approve_write_dirs: List[str] = field(default_factory=list)
    blocked_commands: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Set defaults if not provided."""
        if not self.allowed_directories:
            self.allowed_directories = [
                "~/hestia/data", "~/hestia/logs", "/tmp/hestia",
                "~/Documents", "~/Desktop",
                "~/Library/Mobile Documents/com~apple~CloudDocs",
                "~/Library/Mobile Documents",
            ]
        if not self.auto_approve_write_dirs:
            self.auto_approve_write_dirs = ["~/hestia/data"]
        if not self.blocked_commands:
            self.blocked_commands = ["rm -rf", "sudo", "chmod", "chown"]


# Validation result for tool calls
@dataclass
class ToolValidationResult:
    """Result of validating a tool call."""
    valid: bool
    error_type: Optional[str] = None
    message: Optional[str] = None

    @classmethod
    def success(cls) -> "ToolValidationResult":
        """Create successful validation result."""
        return cls(valid=True)

    @classmethod
    def failure(cls, error_type: str, message: str) -> "ToolValidationResult":
        """Create failed validation result."""
        return cls(valid=False, error_type=error_type, message=message)
