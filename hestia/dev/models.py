"""Models, enums, and state machine for the Hestia Agentic Development System."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DevSessionState(str, Enum):
    """Lifecycle states for an agentic dev session."""

    QUEUED = "queued"
    PLANNING = "planning"
    RESEARCHING = "researching"
    PROPOSED = "proposed"
    EXECUTING = "executing"
    VALIDATING = "validating"
    REVIEWING = "reviewing"
    COMPLETE = "complete"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"

    @classmethod
    def pre_approval_states(cls) -> list[DevSessionState]:
        """States that occur before human approval of the plan."""
        return [cls.QUEUED, cls.PLANNING, cls.RESEARCHING, cls.PROPOSED]

    @classmethod
    def post_approval_states(cls) -> list[DevSessionState]:
        """States that occur after human approval — execution phase and beyond."""
        return [cls.EXECUTING, cls.VALIDATING, cls.REVIEWING, cls.COMPLETE, cls.FAILED, cls.BLOCKED, cls.CANCELLED]


class DevSessionSource(str, Enum):
    """Origin of a dev session request."""

    CLI = "cli"
    GITHUB = "github"
    SELF_DISCOVERED = "self_discovered"
    SCHEDULED = "scheduled"


class DevComplexity(str, Enum):
    """Estimated complexity of a dev task."""

    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    CRITICAL = "critical"


class DevPriority(int, Enum):
    """Execution priority — lower value = higher urgency."""

    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


class AgentTier(str, Enum):
    """Tiers in the 4-tier autonomous agent hierarchy."""

    ARCHITECT = "architect"
    RESEARCHER = "researcher"
    ENGINEER = "engineer"
    VALIDATOR = "validator"


class DevEventType(str, Enum):
    """Types of events that can occur during a dev session."""

    STATE_CHANGE = "state_change"
    PLAN_CREATED = "plan_created"
    SUBTASK_STARTED = "subtask_started"
    SUBTASK_COMPLETED = "subtask_completed"
    FILE_EDITED = "file_edited"
    FILE_CREATED = "file_created"
    TEST_RUN = "test_run"
    LINT_RUN = "lint_run"
    BUILD_CHECK = "build_check"
    COMMIT = "commit"
    REVIEW = "review"
    RESEARCH = "research"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    ERROR = "error"
    TOKEN_BUDGET_WARNING = "token_budget_warning"
    NOTIFICATION_SENT = "notification_sent"


class ApprovalType(str, Enum):
    """Categories of actions that require human approval."""

    PLAN_APPROVAL = "plan_approval"
    PROTECTED_PATH = "protected_path"
    GIT_PUSH = "git_push"
    PR_CREATE = "pr_create"
    PR_MERGE = "pr_merge"


# ---------------------------------------------------------------------------
# Valid state transitions
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[DevSessionState, list[DevSessionState]] = {
    DevSessionState.QUEUED: [
        DevSessionState.PLANNING,
        DevSessionState.CANCELLED,
    ],
    DevSessionState.PLANNING: [
        DevSessionState.RESEARCHING,
        DevSessionState.PROPOSED,
        DevSessionState.FAILED,
        DevSessionState.CANCELLED,
    ],
    DevSessionState.RESEARCHING: [
        DevSessionState.PROPOSED,
        DevSessionState.PLANNING,
        DevSessionState.FAILED,
        DevSessionState.CANCELLED,
    ],
    DevSessionState.PROPOSED: [
        DevSessionState.EXECUTING,
        DevSessionState.PLANNING,
        DevSessionState.CANCELLED,
    ],
    DevSessionState.EXECUTING: [
        DevSessionState.VALIDATING,
        DevSessionState.BLOCKED,
        DevSessionState.FAILED,
        DevSessionState.CANCELLED,
    ],
    DevSessionState.VALIDATING: [
        DevSessionState.REVIEWING,
        DevSessionState.EXECUTING,
        DevSessionState.FAILED,
        DevSessionState.CANCELLED,
    ],
    DevSessionState.REVIEWING: [
        DevSessionState.COMPLETE,
        DevSessionState.EXECUTING,
        DevSessionState.FAILED,
        DevSessionState.CANCELLED,
    ],
    DevSessionState.COMPLETE: [],
    DevSessionState.FAILED: [
        DevSessionState.PLANNING,
        DevSessionState.CANCELLED,
    ],
    DevSessionState.BLOCKED: [
        DevSessionState.EXECUTING,
        DevSessionState.CANCELLED,
    ],
    DevSessionState.CANCELLED: [],
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class DevSession:
    """Represents a single agentic development session."""

    # Class constants (not instance fields)
    MAX_RETRIES: int = field(default=3, init=False, repr=False, compare=False)
    MAX_REPLANS: int = field(default=2, init=False, repr=False, compare=False)
    DEFAULT_TOKEN_BUDGET: int = field(default=500_000, init=False, repr=False, compare=False)

    # Required fields
    id: str
    title: str
    description: str
    source: DevSessionSource

    # Optional origin tracking
    source_ref: Optional[str] = None  # issue #, CLI session ID, etc.

    # State and scheduling
    state: DevSessionState = DevSessionState.QUEUED
    priority: DevPriority = DevPriority.NORMAL
    complexity: Optional[DevComplexity] = None

    # Git
    branch_name: Optional[str] = None  # git branch for this session

    # Architect output
    plan: Optional[Dict[str, Any]] = None        # Architect's plan, stored as JSON
    subtasks: Optional[List[Dict[str, Any]]] = None  # Decomposed subtasks
    current_subtask: int = 0                     # Progress tracker index

    # Agent model assignments
    architect_model: str = "claude-opus-4-20250514"
    engineer_model: str = "claude-sonnet-4-20250514"
    researcher_model: str = "gemini-2.0-pro"
    validator_model: str = "claude-haiku-4-5-20251001"

    # Timestamps — ISO format strings for clean SQLite round-tripping
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None

    # Token tracking
    token_budget: int = 500_000
    tokens_used: int = 0
    total_tokens: int = 0    # Cumulative across replans/retries

    # Cost tracking
    total_cost_usd: float = 0.0

    # Error / retry state
    error_log: Optional[str] = None
    retry_count: int = 0
    replan_count: int = 0

    # Freeform metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    # updated_at is maintained internally — not exposed as a constructor arg
    updated_at: str = ""

    @classmethod
    def create(
        cls,
        title: str,
        description: str,
        source: DevSessionSource = DevSessionSource.CLI,
        source_ref: Optional[str] = None,
        complexity: Optional[DevComplexity] = None,
        priority: DevPriority = DevPriority.NORMAL,
        branch_name: Optional[str] = None,
        token_budget: int = 500_000,
        architect_model: str = "claude-opus-4-20250514",
        engineer_model: str = "claude-sonnet-4-20250514",
        researcher_model: str = "gemini-2.0-pro",
        validator_model: str = "claude-haiku-4-5-20251001",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DevSession:
        """Factory — creates a new session in the QUEUED state."""
        now = datetime.now(tz=timezone.utc).isoformat()
        session_id = f"dev-{uuid.uuid4().hex[:12]}"
        return cls(
            id=session_id,
            title=title,
            description=description,
            source=source,
            source_ref=source_ref,
            state=DevSessionState.QUEUED,
            priority=priority,
            complexity=complexity,
            branch_name=branch_name,
            plan=None,
            subtasks=None,
            current_subtask=0,
            architect_model=architect_model,
            engineer_model=engineer_model,
            researcher_model=researcher_model,
            validator_model=validator_model,
            created_at=now,
            updated_at=now,
            started_at=None,
            completed_at=None,
            approved_at=None,
            approved_by=None,
            token_budget=token_budget,
            tokens_used=0,
            total_tokens=0,
            total_cost_usd=0.0,
            error_log=None,
            retry_count=0,
            replan_count=0,
            metadata=metadata or {},
        )

    def can_transition(self, target: DevSessionState) -> bool:
        """Return True if transitioning to *target* is allowed from the current state."""
        return target in VALID_TRANSITIONS.get(self.state, [])

    def transition(self, target: DevSessionState) -> None:
        """Apply a state transition, raising ValueError if invalid."""
        if not self.can_transition(target):
            raise ValueError(
                f"Invalid transition: {self.state.value} -> {target.value}"
            )
        self.state = target
        self.updated_at = datetime.now(tz=timezone.utc).isoformat()

    def can_retry(self) -> bool:
        """Return True if this session is eligible for a retry attempt."""
        return self.state == DevSessionState.FAILED and self.retry_count < self.MAX_RETRIES

    def can_replan(self) -> bool:
        """Return True if this session can generate a revised plan."""
        return self.replan_count < self.MAX_REPLANS

    def within_token_budget(self, budget: Optional[int] = None) -> bool:
        """Return True if tokens consumed are within the budget.

        Args:
            budget: Optional override. If None, uses self.token_budget.
        """
        effective_budget = budget if budget is not None else self.token_budget
        return self.tokens_used < effective_budget


@dataclass
class DevEvent:
    """An immutable audit record of something that happened during a session."""

    id: str
    session_id: str
    event_type: DevEventType
    agent_tier: AgentTier | None
    timestamp: str  # ISO format string
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        session_id: str,
        event_type: DevEventType,
        agent_tier: AgentTier | None = None,
        data: dict[str, Any] | None = None,
    ) -> DevEvent:
        """Factory — creates a new event with a generated id and current timestamp."""
        return cls(
            id=str(uuid.uuid4()),
            session_id=session_id,
            event_type=event_type,
            agent_tier=agent_tier,
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            data=data or {},
        )


@dataclass
class Proposal:
    """A structured plan produced by the Architect tier awaiting approval."""

    id: str
    session_id: str
    summary: str
    steps: list[str]
    affected_files: list[str]
    estimated_tokens: int
    created_at: str  # ISO format string
    approved: bool | None = None  # None = pending
    approval_notes: str = ""

    @classmethod
    def from_session(
        cls,
        session: DevSession,
        summary: str,
        steps: list[str],
        affected_files: list[str],
        estimated_tokens: int = 0,
    ) -> Proposal:
        """Factory — creates a proposal tied to a specific dev session."""
        return cls(
            id=str(uuid.uuid4()),
            session_id=session.id,
            summary=summary,
            steps=steps,
            affected_files=affected_files,
            estimated_tokens=estimated_tokens,
            created_at=datetime.now(tz=timezone.utc).isoformat(),
            approved=None,
            approval_notes="",
        )
