"""
Data models for Hestia orchestration layer.

Defines request/response structures, task states, and conversation models.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from hestia.orchestration.agent_models import AgentByline


class TaskState(Enum):
    """
    Task lifecycle states.

    State machine transitions:
    RECEIVED -> PROCESSING -> COMPLETED
    RECEIVED -> PROCESSING -> AWAITING_TOOL -> PROCESSING -> COMPLETED
    RECEIVED -> PROCESSING -> FAILED
    Any state -> CANCELLED (user initiated)
    """
    RECEIVED = "received"           # Request received, not yet processed
    PROCESSING = "processing"       # Inference in progress
    AWAITING_TOOL = "awaiting_tool" # Waiting for tool execution
    COMPLETED = "completed"         # Successfully completed
    FAILED = "failed"               # Error occurred
    CANCELLED = "cancelled"         # User cancelled


class Mode(Enum):
    """
    Hestia persona modes.

    Each mode has different personality traits and focus areas.
    """
    TIA = "tia"     # Default: daily ops, quick queries, efficient
    MIRA = "mira"   # Learning: Socratic teaching, research, explanatory
    OLLY = "olly"   # Projects: focused dev, minimal tangents, technical


class RequestSource(Enum):
    """Source of incoming request."""
    API = "api"                 # REST API call
    CLI = "cli"                 # Command line
    IOS_SHORTCUT = "ios_shortcut"  # iOS Shortcut integration
    QUICK_CHAT = "quick_chat"   # Quick chat widget


class ResponseType(Enum):
    """Type of response generated."""
    TEXT = "text"               # Plain text response
    STRUCTURED = "structured"   # JSON structured response
    TOOL_CALL = "tool_call"     # Request to execute tool
    ERROR = "error"             # Error response
    CLARIFICATION = "clarification"  # Need more info from user


@dataclass
class Request:
    """
    Incoming request to Hestia.
    """
    id: str
    content: str
    mode: Mode = Mode.TIA
    source: RequestSource = RequestSource.API
    session_id: Optional[str] = None
    device_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Privacy control
    force_local: bool = False

    # Optional context hints
    context_hints: Dict[str, Any] = field(default_factory=dict)

    # For continuation of tool-calling conversations
    tool_results: Optional[List[Dict[str, Any]]] = None

    @classmethod
    def create(
        cls,
        content: str,
        mode: Mode = Mode.TIA,
        source: RequestSource = RequestSource.API,
        session_id: Optional[str] = None,
        **kwargs
    ) -> "Request":
        """Factory method to create request with auto-generated ID."""
        return cls(
            id=f"req-{uuid4().hex[:12]}",
            content=content,
            mode=mode,
            source=source,
            session_id=session_id or f"session-{uuid4().hex[:8]}",
            **kwargs
        )


@dataclass
class Response:
    """
    Response from Hestia.
    """
    request_id: str
    content: str
    response_type: ResponseType = ResponseType.TEXT
    mode: Mode = Mode.TIA
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Metrics
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: float = 0.0

    # Tool call info (if response_type == TOOL_CALL)
    tool_calls: Optional[List[Dict[str, Any]]] = None

    # Error info (if response_type == ERROR)
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    # Memory operations performed
    memory_operations: List[str] = field(default_factory=list)

    # Agent orchestrator bylines
    bylines: List["AgentByline"] = field(default_factory=list)

    # Retrieval feedback loop — chunk IDs used in context (Sprint 15)
    retrieved_chunk_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        result = {
            "request_id": self.request_id,
            "content": self.content,
            "response_type": self.response_type.value,
            "mode": self.mode.value,
            "timestamp": self.timestamp.isoformat(),
            "metrics": {
                "tokens_in": self.tokens_in,
                "tokens_out": self.tokens_out,
                "duration_ms": self.duration_ms,
            }
        }

        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        if self.error_code:
            result["error"] = {
                "code": self.error_code,
                "message": self.error_message,
            }

        return result


@dataclass
class Task:
    """
    Internal task representation for state machine.
    """
    request: Request
    state: TaskState = TaskState.RECEIVED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Processing context
    context: Dict[str, Any] = field(default_factory=dict)

    # State history for debugging
    state_history: List[Dict[str, Any]] = field(default_factory=list)

    # Response (populated on completion)
    response: Optional[Response] = None

    # Error info (if failed)
    error: Optional[Exception] = None

    def transition_to(self, new_state: TaskState, reason: str = "") -> None:
        """
        Transition to a new state.

        Records state change in history for debugging.
        """
        old_state = self.state
        self.state = new_state
        self.updated_at = datetime.now(timezone.utc)

        self.state_history.append({
            "from": old_state.value,
            "to": new_state.value,
            "timestamp": self.updated_at.isoformat(),
            "reason": reason,
        })

    @property
    def duration_ms(self) -> float:
        """Calculate task duration in milliseconds."""
        return (self.updated_at - self.created_at).total_seconds() * 1000


@dataclass
class Conversation:
    """
    Represents an ongoing conversation session.
    """
    session_id: str
    mode: Mode = Mode.TIA
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Conversation history (for context)
    messages: List[Dict[str, str]] = field(default_factory=list)

    # Metadata
    device_id: Optional[str] = None
    turn_count: int = 0

    def add_turn(self, user_message: str, assistant_message: str) -> None:
        """Add a conversation turn."""
        self.messages.append({"role": "user", "content": user_message})
        self.messages.append({"role": "assistant", "content": assistant_message})
        self.turn_count += 1
        self.last_activity = datetime.now(timezone.utc)

    def get_recent_context(self, max_turns: int = 10) -> List[Dict[str, str]]:
        """Get recent messages for context injection."""
        # Each turn has 2 messages (user + assistant)
        max_messages = max_turns * 2
        return self.messages[-max_messages:] if self.messages else []


# Valid state transitions
VALID_TRANSITIONS = {
    TaskState.RECEIVED: {TaskState.PROCESSING, TaskState.CANCELLED, TaskState.FAILED},
    TaskState.PROCESSING: {TaskState.COMPLETED, TaskState.AWAITING_TOOL, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.AWAITING_TOOL: {TaskState.PROCESSING, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.COMPLETED: set(),  # Terminal state
    TaskState.FAILED: set(),     # Terminal state
    TaskState.CANCELLED: set(),  # Terminal state
}


def is_valid_transition(from_state: TaskState, to_state: TaskState) -> bool:
    """Check if a state transition is valid."""
    return to_state in VALID_TRANSITIONS.get(from_state, set())
