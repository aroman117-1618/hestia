# Agentic Development System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 4-tier autonomous development agent system (Architect/Opus, Researcher/Gemini, Engineer/Sonnet, Validator/Haiku) that can discover, plan, and execute development tasks on its own codebase with full memory integration and audit trail.

**Architecture:** New `hestia/dev/` module following the manager pattern. DevSessionManager orchestrates sessions through a state machine. Each agent tier has its own module with tailored context builder and tool access. SQLite persistence for sessions and events. Memory bridge stores 4 types (summaries, learnings, failures, invariants). API routes expose session CRUD + approval. CLI `/dev` command family. macOS proposal cards in Command tab.

**Tech Stack:** Python 3.12, FastAPI, SQLite (aiosqlite), existing CloudInferenceClient, existing ToolExecutor/ToolRegistry, existing MemoryManager, existing notification relay.

**Spec:** `docs/superpowers/specs/2026-03-28-agentic-dev-system-design.md`

---

## File Structure

```
Create: hestia/dev/__init__.py          — Module exports + get_dev_session_manager()
Create: hestia/dev/models.py            — Enums, dataclasses (DevSession, DevEvent, Proposal, etc.)
Create: hestia/dev/database.py          — SQLite persistence (dev_sessions, dev_session_events)
Create: hestia/dev/manager.py           — DevSessionManager singleton — session lifecycle
Create: hestia/dev/architect.py         — Architect agent (Opus) — plan, review, decompose
Create: hestia/dev/engineer.py          — Engineer agent (Sonnet) — code execution tool loop
Create: hestia/dev/researcher.py        — Researcher agent (Gemini) — deep analysis, cross-model review
Create: hestia/dev/validator.py         — Validator agent (Haiku) — test/lint, background monitoring
Create: hestia/dev/context_builder.py   — Per-tier context assembly
Create: hestia/dev/memory_bridge.py     — Store/retrieve 4 memory types
Create: hestia/dev/discovery.py         — Background work discovery (test monitor, GitHub, quality)
Create: hestia/dev/proposal.py          — Proposal creation + delivery (GitHub, macOS, CLI)
Create: hestia/dev/safety.py            — Authority matrix, token budget, rate limiting
Create: hestia/dev/tools.py             — New tool definitions (run_tests, git_push, etc.)
Create: hestia/api/routes/dev.py        — API routes (session CRUD, approval, events)
Create: tests/test_dev_models.py        — Model/enum tests
Create: tests/test_dev_database.py      — Database schema + CRUD tests
Create: tests/test_dev_manager.py       — Session lifecycle state machine tests
Create: tests/test_dev_architect.py     — Architect agent tests
Create: tests/test_dev_engineer.py      — Engineer agent tests
Create: tests/test_dev_safety.py        — Authority matrix + safety invariant tests
Create: tests/test_dev_context.py       — Context builder tests
Create: tests/test_dev_memory.py        — Memory bridge tests
Create: tests/test_dev_routes.py        — API route tests
Modify: hestia/logging/structured_logger.py:66 — Add DEV LogComponent
Modify: hestia/cloud/models.py:243-261  — Add Opus 4 + Haiku 4.5 to Anthropic models
Modify: hestia/api/server.py:819+       — Register dev router
Modify: hestia/execution/tools/__init__.py:39+ — Register new dev tools
Modify: scripts/auto-test.sh            — Add dev module → test mappings
```

---

### Task 1: Models & Enums

**Files:**
- Create: `hestia/dev/__init__.py`
- Create: `hestia/dev/models.py`
- Create: `tests/test_dev_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dev_models.py
"""Tests for dev module models and enums."""
import pytest
from hestia.dev.models import (
    DevSessionState,
    DevSessionSource,
    DevComplexity,
    DevPriority,
    AgentTier,
    DevSession,
    DevEvent,
    DevEventType,
    Proposal,
)


class TestDevSessionState:
    def test_all_states_defined(self):
        states = {s.value for s in DevSessionState}
        assert states == {
            "queued", "planning", "researching", "proposed",
            "executing", "validating", "reviewing", "complete",
            "failed", "blocked", "cancelled",
        }

    def test_pre_approval_states(self):
        pre = DevSessionState.pre_approval_states()
        assert DevSessionState.QUEUED in pre
        assert DevSessionState.PLANNING in pre
        assert DevSessionState.PROPOSED in pre
        assert DevSessionState.EXECUTING not in pre

    def test_post_approval_states(self):
        post = DevSessionState.post_approval_states()
        assert DevSessionState.EXECUTING in post
        assert DevSessionState.VALIDATING in post
        assert DevSessionState.PROPOSED not in post


class TestDevSession:
    def test_create(self):
        session = DevSession.create(
            title="Fix memory bug",
            description="Memory consolidator skips short exchanges",
            source=DevSessionSource.CLI,
        )
        assert session.id.startswith("dev-")
        assert session.state == DevSessionState.QUEUED
        assert session.title == "Fix memory bug"
        assert session.priority == DevPriority.NORMAL
        assert session.total_tokens == 0

    def test_can_transition_valid(self):
        session = DevSession.create(
            title="Test", description="Test", source=DevSessionSource.CLI
        )
        assert session.can_transition(DevSessionState.PLANNING) is True

    def test_can_transition_invalid(self):
        session = DevSession.create(
            title="Test", description="Test", source=DevSessionSource.CLI
        )
        assert session.can_transition(DevSessionState.EXECUTING) is False


class TestDevEvent:
    def test_create(self):
        event = DevEvent.create(
            session_id="dev-abc123",
            agent=AgentTier.ARCHITECT,
            event_type=DevEventType.PLAN_CREATED,
            detail={"plan": "Fix the bug"},
        )
        assert event.session_id == "dev-abc123"
        assert event.agent == AgentTier.ARCHITECT


class TestAgentTier:
    def test_all_tiers(self):
        tiers = {t.value for t in AgentTier}
        assert tiers == {"architect", "engineer", "researcher", "validator"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_dev_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'hestia.dev'`

- [ ] **Step 3: Create module init**

```python
# hestia/dev/__init__.py
"""Hestia Agentic Development System.

4-tier agent hierarchy for autonomous codebase development:
- Architect (Opus): plans, reviews, decomposes
- Researcher (Gemini): deep analysis, cross-model review
- Engineer (Sonnet): code execution, tool loop
- Validator (Haiku): test/lint, background monitoring
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hestia.dev.manager import DevSessionManager

_manager: DevSessionManager | None = None


async def get_dev_session_manager() -> DevSessionManager:
    """Get or create the singleton DevSessionManager."""
    global _manager
    if _manager is None:
        from hestia.dev.manager import DevSessionManager
        _manager = DevSessionManager()
        await _manager.initialize()
    return _manager
```

- [ ] **Step 4: Write models**

```python
# hestia/dev/models.py
"""Models and enums for the Agentic Development System."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class DevSessionState(Enum):
    """States in the dev session lifecycle."""
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
    def pre_approval_states(cls) -> set[DevSessionState]:
        return {cls.QUEUED, cls.PLANNING, cls.RESEARCHING, cls.PROPOSED}

    @classmethod
    def post_approval_states(cls) -> set[DevSessionState]:
        return {cls.EXECUTING, cls.VALIDATING, cls.REVIEWING, cls.COMPLETE}


# Valid state transitions
VALID_TRANSITIONS: Dict[DevSessionState, set[DevSessionState]] = {
    DevSessionState.QUEUED: {DevSessionState.PLANNING, DevSessionState.CANCELLED},
    DevSessionState.PLANNING: {
        DevSessionState.RESEARCHING, DevSessionState.PROPOSED,
        DevSessionState.BLOCKED, DevSessionState.CANCELLED,
    },
    DevSessionState.RESEARCHING: {
        DevSessionState.PROPOSED, DevSessionState.PLANNING,
        DevSessionState.BLOCKED, DevSessionState.CANCELLED,
    },
    DevSessionState.PROPOSED: {
        DevSessionState.EXECUTING, DevSessionState.CANCELLED,
    },
    DevSessionState.EXECUTING: {
        DevSessionState.VALIDATING, DevSessionState.BLOCKED,
        DevSessionState.CANCELLED,
    },
    DevSessionState.VALIDATING: {
        DevSessionState.EXECUTING, DevSessionState.REVIEWING,
        DevSessionState.FAILED, DevSessionState.BLOCKED,
        DevSessionState.CANCELLED,
    },
    DevSessionState.REVIEWING: {
        DevSessionState.COMPLETE, DevSessionState.EXECUTING,
        DevSessionState.PROPOSED, DevSessionState.BLOCKED,
        DevSessionState.CANCELLED,
    },
    DevSessionState.FAILED: {
        DevSessionState.EXECUTING, DevSessionState.PROPOSED,
        DevSessionState.BLOCKED, DevSessionState.CANCELLED,
    },
    DevSessionState.BLOCKED: {DevSessionState.CANCELLED},
    DevSessionState.COMPLETE: set(),
    DevSessionState.CANCELLED: set(),
}


class DevSessionSource(Enum):
    """Where a dev session originated."""
    CLI = "cli"
    GITHUB = "github"
    SELF_DISCOVERED = "self_discovered"
    SCHEDULED = "scheduled"


class DevComplexity(Enum):
    """Task complexity assessment."""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    CRITICAL = "critical"


class DevPriority(Enum):
    """Task priority levels."""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


class AgentTier(Enum):
    """Agent tiers in the hierarchy."""
    ARCHITECT = "architect"
    RESEARCHER = "researcher"
    ENGINEER = "engineer"
    VALIDATOR = "validator"


class DevEventType(Enum):
    """Types of events in a dev session."""
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


class ApprovalType(Enum):
    """Types of approval requests."""
    PLAN_APPROVAL = "plan_approval"
    PROTECTED_PATH = "protected_path"
    GIT_PUSH = "git_push"
    PR_CREATE = "pr_create"
    PR_MERGE = "pr_merge"


@dataclass
class DevSession:
    """A single development task lifecycle."""
    id: str
    title: str
    description: str
    source: DevSessionSource
    source_ref: Optional[str] = None
    state: DevSessionState = DevSessionState.QUEUED
    priority: DevPriority = DevPriority.NORMAL
    complexity: Optional[DevComplexity] = None
    branch_name: Optional[str] = None
    plan: Optional[Dict[str, Any]] = None
    subtasks: Optional[List[Dict[str, Any]]] = None
    current_subtask: int = 0
    architect_model: str = "claude-opus-4-20250514"
    engineer_model: str = "claude-sonnet-4-20250514"
    researcher_model: str = "gemini-2.0-pro"
    validator_model: str = "claude-haiku-4-5-20251001"
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    error_log: Optional[str] = None
    retry_count: int = 0
    replan_count: int = 0

    MAX_RETRIES: int = 3
    MAX_REPLANS: int = 2
    DEFAULT_TOKEN_BUDGET: int = 500_000

    @classmethod
    def create(
        cls,
        title: str,
        description: str,
        source: DevSessionSource,
        source_ref: Optional[str] = None,
        priority: DevPriority = DevPriority.NORMAL,
    ) -> DevSession:
        now = datetime.now(timezone.utc).isoformat()
        session_id = f"dev-{uuid4().hex[:12]}"
        return cls(
            id=session_id,
            title=title,
            description=description,
            source=source,
            source_ref=source_ref,
            priority=priority,
            created_at=now,
        )

    def can_transition(self, target: DevSessionState) -> bool:
        return target in VALID_TRANSITIONS.get(self.state, set())

    def transition(self, target: DevSessionState) -> None:
        if not self.can_transition(target):
            raise ValueError(
                f"Invalid transition: {self.state.value} → {target.value}"
            )
        self.state = target

    def can_retry(self) -> bool:
        return self.retry_count < self.MAX_RETRIES

    def can_replan(self) -> bool:
        return self.replan_count < self.MAX_REPLANS

    def within_token_budget(self, budget: Optional[int] = None) -> bool:
        limit = budget or self.DEFAULT_TOKEN_BUDGET
        return self.total_tokens < limit


@dataclass
class DevEvent:
    """A single event in a dev session's audit trail."""
    id: Optional[int]
    session_id: str
    timestamp: str
    agent: AgentTier
    event_type: DevEventType
    detail: Dict[str, Any] = field(default_factory=dict)
    tokens_used: int = 0
    model: Optional[str] = None
    files_affected: List[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        session_id: str,
        agent: AgentTier,
        event_type: DevEventType,
        detail: Optional[Dict[str, Any]] = None,
        tokens_used: int = 0,
        model: Optional[str] = None,
        files_affected: Optional[List[str]] = None,
    ) -> DevEvent:
        return cls(
            id=None,
            session_id=session_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent=agent,
            event_type=event_type,
            detail=detail or {},
            tokens_used=tokens_used,
            model=model,
            files_affected=files_affected or [],
        )


@dataclass
class Proposal:
    """A plan awaiting Andrew's approval."""
    session_id: str
    title: str
    description: str
    plan_steps: List[str]
    files_affected: List[str]
    complexity: DevComplexity
    priority: DevPriority
    estimated_minutes: int
    risk: str  # "low", "medium", "high"
    source: DevSessionSource
    source_ref: Optional[str] = None
    created_at: str = ""

    @classmethod
    def from_session(cls, session: DevSession) -> Proposal:
        plan = session.plan or {}
        return cls(
            session_id=session.id,
            title=session.title,
            description=session.description,
            plan_steps=plan.get("steps", []),
            files_affected=plan.get("files", []),
            complexity=session.complexity or DevComplexity.MEDIUM,
            priority=session.priority,
            estimated_minutes=plan.get("estimated_minutes", 15),
            risk=plan.get("risk", "medium"),
            source=session.source,
            source_ref=session.source_ref,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_dev_models.py -v`
Expected: All tests PASS

- [ ] **Step 6: Add DEV to LogComponent enum**

In `hestia/logging/structured_logger.py`, add after line 67 (`WORKFLOW = "workflow"`):

```python
    DEV = "dev"
```

- [ ] **Step 7: Commit**

```bash
git add hestia/dev/__init__.py hestia/dev/models.py tests/test_dev_models.py hestia/logging/structured_logger.py
git commit -m "feat(dev): add models, enums, and state machine for agentic dev system"
```

---

### Task 2: Database Layer

**Files:**
- Create: `hestia/dev/database.py`
- Create: `tests/test_dev_database.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dev_database.py
"""Tests for dev session database persistence."""
import json
import pytest
import pytest_asyncio
from pathlib import Path

from hestia.dev.database import DevDatabase
from hestia.dev.models import (
    DevSession, DevEvent, DevSessionState, DevSessionSource,
    DevPriority, AgentTier, DevEventType,
)


@pytest_asyncio.fixture
async def db(tmp_path):
    database = DevDatabase(db_path=tmp_path / "test_dev.db")
    await database.connect()
    yield database
    await database.close()


class TestDevDatabase:
    @pytest.mark.asyncio
    async def test_save_and_get_session(self, db):
        session = DevSession.create(
            title="Fix bug",
            description="Fix the memory bug",
            source=DevSessionSource.CLI,
        )
        await db.save_session(session)
        loaded = await db.get_session(session.id)
        assert loaded is not None
        assert loaded.title == "Fix bug"
        assert loaded.state == DevSessionState.QUEUED

    @pytest.mark.asyncio
    async def test_update_session_state(self, db):
        session = DevSession.create(
            title="Test", description="Test", source=DevSessionSource.CLI
        )
        await db.save_session(session)
        session.state = DevSessionState.PLANNING
        await db.update_session(session)
        loaded = await db.get_session(session.id)
        assert loaded.state == DevSessionState.PLANNING

    @pytest.mark.asyncio
    async def test_list_sessions_by_state(self, db):
        s1 = DevSession.create(title="A", description="A", source=DevSessionSource.CLI)
        s2 = DevSession.create(title="B", description="B", source=DevSessionSource.CLI)
        s2.state = DevSessionState.PROPOSED
        await db.save_session(s1)
        await db.save_session(s2)
        queued = await db.list_sessions(state=DevSessionState.QUEUED)
        assert len(queued) == 1
        assert queued[0].title == "A"

    @pytest.mark.asyncio
    async def test_save_and_list_events(self, db):
        session = DevSession.create(
            title="Test", description="Test", source=DevSessionSource.CLI
        )
        await db.save_session(session)
        event = DevEvent.create(
            session_id=session.id,
            agent=AgentTier.ARCHITECT,
            event_type=DevEventType.PLAN_CREATED,
            detail={"plan": "Do the thing"},
            files_affected=["hestia/memory/manager.py"],
        )
        await db.save_event(event)
        events = await db.list_events(session.id)
        assert len(events) == 1
        assert events[0].agent == AgentTier.ARCHITECT
        assert events[0].detail == {"plan": "Do the thing"}

    @pytest.mark.asyncio
    async def test_get_pending_proposals(self, db):
        s1 = DevSession.create(title="A", description="A", source=DevSessionSource.SELF_DISCOVERED)
        s1.state = DevSessionState.PROPOSED
        s1.plan = {"steps": ["step1"], "files": ["file.py"], "risk": "low"}
        await db.save_session(s1)
        proposals = await db.get_pending_proposals()
        assert len(proposals) == 1
        assert proposals[0].id == s1.id

    @pytest.mark.asyncio
    async def test_session_not_found(self, db):
        loaded = await db.get_session("nonexistent")
        assert loaded is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_dev_database.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'hestia.dev.database'`

- [ ] **Step 3: Write database implementation**

```python
# hestia/dev/database.py
"""SQLite persistence for dev sessions and events."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import aiosqlite

from hestia.database import BaseDatabase
from hestia.logging import get_logger, LogComponent
from hestia.dev.models import (
    DevSession, DevEvent, DevSessionState, DevSessionSource,
    DevPriority, DevComplexity, AgentTier, DevEventType,
)

logger = get_logger()

_DB_PATH = Path.home() / "hestia" / "data" / "dev.db"
_instance: Optional["DevDatabase"] = None


class DevDatabase(BaseDatabase):
    """SQLite database for dev sessions and audit events."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        super().__init__("dev", db_path or _DB_PATH)

    async def _init_schema(self) -> None:
        await self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS dev_sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                source TEXT NOT NULL,
                source_ref TEXT,
                state TEXT NOT NULL DEFAULT 'queued',
                priority INTEGER NOT NULL DEFAULT 3,
                complexity TEXT,
                branch_name TEXT,
                plan TEXT,
                subtasks TEXT,
                current_subtask INTEGER DEFAULT 0,
                architect_model TEXT,
                engineer_model TEXT,
                researcher_model TEXT,
                validator_model TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                approved_at TEXT,
                approved_by TEXT,
                total_tokens INTEGER DEFAULT 0,
                total_cost_usd REAL DEFAULT 0.0,
                error_log TEXT,
                retry_count INTEGER DEFAULT 0,
                replan_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS dev_session_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES dev_sessions(id),
                timestamp TEXT NOT NULL,
                agent TEXT NOT NULL,
                event_type TEXT NOT NULL,
                detail TEXT DEFAULT '{}',
                tokens_used INTEGER DEFAULT 0,
                model TEXT,
                files_affected TEXT DEFAULT '[]'
            );

            CREATE INDEX IF NOT EXISTS idx_dev_events_session
                ON dev_session_events(session_id);
            CREATE INDEX IF NOT EXISTS idx_dev_sessions_state
                ON dev_sessions(state);
        """)

    async def save_session(self, session: DevSession) -> None:
        await self.connection.execute(
            """INSERT INTO dev_sessions (
                id, title, description, source, source_ref, state, priority,
                complexity, branch_name, plan, subtasks, current_subtask,
                architect_model, engineer_model, researcher_model, validator_model,
                created_at, started_at, completed_at, approved_at, approved_by,
                total_tokens, total_cost_usd, error_log, retry_count, replan_count
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?
            )""",
            (
                session.id, session.title, session.description,
                session.source.value, session.source_ref,
                session.state.value, session.priority.value,
                session.complexity.value if session.complexity else None,
                session.branch_name,
                json.dumps(session.plan) if session.plan else None,
                json.dumps(session.subtasks) if session.subtasks else None,
                session.current_subtask,
                session.architect_model, session.engineer_model,
                session.researcher_model, session.validator_model,
                session.created_at, session.started_at, session.completed_at,
                session.approved_at, session.approved_by,
                session.total_tokens, session.total_cost_usd,
                session.error_log, session.retry_count, session.replan_count,
            ),
        )
        await self.connection.commit()

    async def update_session(self, session: DevSession) -> None:
        await self.connection.execute(
            """UPDATE dev_sessions SET
                state=?, priority=?, complexity=?, branch_name=?,
                plan=?, subtasks=?, current_subtask=?,
                started_at=?, completed_at=?, approved_at=?, approved_by=?,
                total_tokens=?, total_cost_usd=?, error_log=?,
                retry_count=?, replan_count=?
            WHERE id=?""",
            (
                session.state.value, session.priority.value,
                session.complexity.value if session.complexity else None,
                session.branch_name,
                json.dumps(session.plan) if session.plan else None,
                json.dumps(session.subtasks) if session.subtasks else None,
                session.current_subtask,
                session.started_at, session.completed_at,
                session.approved_at, session.approved_by,
                session.total_tokens, session.total_cost_usd,
                session.error_log, session.retry_count, session.replan_count,
                session.id,
            ),
        )
        await self.connection.commit()

    async def get_session(self, session_id: str) -> Optional[DevSession]:
        cursor = await self.connection.execute(
            "SELECT * FROM dev_sessions WHERE id = ?", (session_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_session(row)

    async def list_sessions(
        self,
        state: Optional[DevSessionState] = None,
        limit: int = 50,
    ) -> List[DevSession]:
        if state:
            cursor = await self.connection.execute(
                "SELECT * FROM dev_sessions WHERE state = ? ORDER BY created_at DESC LIMIT ?",
                (state.value, limit),
            )
        else:
            cursor = await self.connection.execute(
                "SELECT * FROM dev_sessions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        rows = await cursor.fetchall()
        return [self._row_to_session(r) for r in rows]

    async def get_pending_proposals(self) -> List[DevSession]:
        return await self.list_sessions(state=DevSessionState.PROPOSED)

    async def save_event(self, event: DevEvent) -> int:
        cursor = await self.connection.execute(
            """INSERT INTO dev_session_events (
                session_id, timestamp, agent, event_type, detail,
                tokens_used, model, files_affected
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.session_id, event.timestamp,
                event.agent.value, event.event_type.value,
                json.dumps(event.detail), event.tokens_used,
                event.model, json.dumps(event.files_affected),
            ),
        )
        await self.connection.commit()
        return cursor.lastrowid

    async def list_events(
        self,
        session_id: str,
        event_type: Optional[DevEventType] = None,
    ) -> List[DevEvent]:
        if event_type:
            cursor = await self.connection.execute(
                "SELECT * FROM dev_session_events WHERE session_id = ? AND event_type = ? ORDER BY timestamp",
                (session_id, event_type.value),
            )
        else:
            cursor = await self.connection.execute(
                "SELECT * FROM dev_session_events WHERE session_id = ? ORDER BY timestamp",
                (session_id,),
            )
        rows = await cursor.fetchall()
        return [self._row_to_event(r) for r in rows]

    def _row_to_session(self, row) -> DevSession:
        return DevSession(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            source=DevSessionSource(row["source"]),
            source_ref=row["source_ref"],
            state=DevSessionState(row["state"]),
            priority=DevPriority(row["priority"]),
            complexity=DevComplexity(row["complexity"]) if row["complexity"] else None,
            branch_name=row["branch_name"],
            plan=json.loads(row["plan"]) if row["plan"] else None,
            subtasks=json.loads(row["subtasks"]) if row["subtasks"] else None,
            current_subtask=row["current_subtask"],
            architect_model=row["architect_model"],
            engineer_model=row["engineer_model"],
            researcher_model=row["researcher_model"],
            validator_model=row["validator_model"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            approved_at=row["approved_at"],
            approved_by=row["approved_by"],
            total_tokens=row["total_tokens"],
            total_cost_usd=row["total_cost_usd"],
            error_log=row["error_log"],
            retry_count=row["retry_count"],
            replan_count=row["replan_count"],
        )

    def _row_to_event(self, row) -> DevEvent:
        return DevEvent(
            id=row["id"],
            session_id=row["session_id"],
            timestamp=row["timestamp"],
            agent=AgentTier(row["agent"]),
            event_type=DevEventType(row["event_type"]),
            detail=json.loads(row["detail"]) if row["detail"] else {},
            tokens_used=row["tokens_used"],
            model=row["model"],
            files_affected=json.loads(row["files_affected"]) if row["files_affected"] else [],
        )


async def get_dev_database() -> DevDatabase:
    global _instance
    if _instance is None:
        _instance = DevDatabase()
        await _instance.connect()
    return _instance
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dev_database.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/dev/database.py tests/test_dev_database.py
git commit -m "feat(dev): add SQLite persistence for dev sessions and events"
```

---

### Task 3: Safety Module — Authority Matrix & Token Budget

**Files:**
- Create: `hestia/dev/safety.py`
- Create: `tests/test_dev_safety.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dev_safety.py
"""Tests for dev agent safety module — authority matrix, token budgets, rate limiting."""
import pytest
from unittest.mock import AsyncMock

from hestia.dev.models import AgentTier, ApprovalType
from hestia.dev.safety import (
    AuthorityMatrix,
    TokenBudgetTracker,
    NotificationRateLimiter,
)


class TestAuthorityMatrix:
    def test_engineer_can_edit_file(self):
        assert AuthorityMatrix.can_use_tool(AgentTier.ENGINEER, "edit_file") is True

    def test_researcher_cannot_edit_file(self):
        assert AuthorityMatrix.can_use_tool(AgentTier.RESEARCHER, "edit_file") is False

    def test_validator_cannot_edit_file(self):
        assert AuthorityMatrix.can_use_tool(AgentTier.VALIDATOR, "edit_file") is False

    def test_all_tiers_can_read(self):
        for tier in AgentTier:
            assert AuthorityMatrix.can_use_tool(tier, "read_file") is True

    def test_validator_can_run_tests(self):
        assert AuthorityMatrix.can_use_tool(AgentTier.VALIDATOR, "run_tests") is True

    def test_engineer_git_push_requires_approval(self):
        assert AuthorityMatrix.requires_approval(AgentTier.ENGINEER, "git_push") == ApprovalType.GIT_PUSH

    def test_engineer_edit_normal_path_no_approval(self):
        assert AuthorityMatrix.requires_approval(AgentTier.ENGINEER, "edit_file", path="hestia/memory/manager.py") is None

    def test_engineer_edit_protected_path_requires_approval(self):
        assert AuthorityMatrix.requires_approval(
            AgentTier.ENGINEER, "edit_file", path="hestia/security/credential_manager.py"
        ) == ApprovalType.PROTECTED_PATH

    def test_architect_can_create_pr(self):
        assert AuthorityMatrix.can_use_tool(AgentTier.ARCHITECT, "create_github_pr") is True

    def test_engineer_cannot_create_pr(self):
        assert AuthorityMatrix.can_use_tool(AgentTier.ENGINEER, "create_github_pr") is False

    def test_validator_cannot_create_issues(self):
        assert AuthorityMatrix.can_use_tool(AgentTier.VALIDATOR, "create_github_issue") is False

    def test_architect_can_create_issues(self):
        assert AuthorityMatrix.can_use_tool(AgentTier.ARCHITECT, "create_github_issue") is True


class TestTokenBudgetTracker:
    def test_within_budget(self):
        tracker = TokenBudgetTracker(budget=100_000)
        tracker.add(50_000)
        assert tracker.within_budget() is True

    def test_exceeds_budget(self):
        tracker = TokenBudgetTracker(budget=100_000)
        tracker.add(110_000)
        assert tracker.within_budget() is False

    def test_warning_threshold(self):
        tracker = TokenBudgetTracker(budget=100_000)
        tracker.add(85_000)
        assert tracker.within_budget() is True
        assert tracker.near_limit() is True

    def test_remaining(self):
        tracker = TokenBudgetTracker(budget=100_000)
        tracker.add(30_000)
        assert tracker.remaining() == 70_000


class TestNotificationRateLimiter:
    def test_normal_within_limit(self):
        limiter = NotificationRateLimiter()
        for _ in range(5):
            assert limiter.can_send("normal") is True
            limiter.record("normal")

    def test_normal_exceeds_limit(self):
        limiter = NotificationRateLimiter()
        for _ in range(10):
            limiter.record("normal")
        assert limiter.can_send("normal") is False

    def test_critical_always_allowed(self):
        limiter = NotificationRateLimiter()
        for _ in range(100):
            limiter.record("critical")
        assert limiter.can_send("critical") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_dev_safety.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write safety implementation**

```python
# hestia/dev/safety.py
"""Authority matrix, token budget tracking, and rate limiting for dev agents."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, List, Optional, Set

from hestia.dev.models import AgentTier, ApprovalType

# Protected paths that require Andrew's explicit approval
PROTECTED_PATHS = [
    "hestia/security/",
    "hestia/config/",
    ".env",
    ".claude/",
]

# Tools each tier can use
TIER_TOOLS: Dict[AgentTier, Set[str]] = {
    AgentTier.ARCHITECT: {
        "read_file", "glob_files", "grep_files",
        "git_status", "git_diff", "git_log", "git_branch",
        "run_tests", "server_restart",
        "create_github_issue", "create_github_pr", "merge_github_pr",
        "git_push", "notify_andrew",
    },
    AgentTier.RESEARCHER: {
        "read_file", "glob_files", "grep_files",
        "git_status", "git_diff", "git_log",
    },
    AgentTier.ENGINEER: {
        "read_file", "glob_files", "grep_files",
        "git_status", "git_diff", "git_log", "git_branch",
        "edit_file", "write_file", "git_add", "git_commit",
        "run_tests", "xcode_build", "run_command",
        "server_restart", "git_push", "notify_andrew",
    },
    AgentTier.VALIDATOR: {
        "read_file", "glob_files", "grep_files",
        "git_status", "git_diff", "git_log",
        "run_tests", "xcode_build", "pip_audit",
        "notify_andrew",
    },
}

# Tools that require soft approval per tier
APPROVAL_REQUIRED: Dict[str, ApprovalType] = {
    "git_push": ApprovalType.GIT_PUSH,
    "create_github_pr": ApprovalType.PR_CREATE,
    "merge_github_pr": ApprovalType.PR_MERGE,
    "run_command": ApprovalType.GIT_PUSH,  # reuse soft approval type
}


class AuthorityMatrix:
    """Static authority checks for agent tool access."""

    @staticmethod
    def can_use_tool(tier: AgentTier, tool_name: str) -> bool:
        return tool_name in TIER_TOOLS.get(tier, set())

    @staticmethod
    def requires_approval(
        tier: AgentTier,
        tool_name: str,
        path: Optional[str] = None,
    ) -> Optional[ApprovalType]:
        if tool_name == "edit_file" and path:
            for protected in PROTECTED_PATHS:
                if protected in path:
                    return ApprovalType.PROTECTED_PATH
        return APPROVAL_REQUIRED.get(tool_name)

    @staticmethod
    def is_protected_path(path: str) -> bool:
        return any(p in path for p in PROTECTED_PATHS)


class TokenBudgetTracker:
    """Track token usage against a per-session budget."""

    def __init__(self, budget: int = 500_000) -> None:
        self._budget = budget
        self._used = 0
        self._warning_threshold = 0.85

    def add(self, tokens: int) -> None:
        self._used += tokens

    @property
    def used(self) -> int:
        return self._used

    def remaining(self) -> int:
        return max(0, self._budget - self._used)

    def within_budget(self) -> bool:
        return self._used < self._budget

    def near_limit(self) -> bool:
        return self._used >= self._budget * self._warning_threshold


class NotificationRateLimiter:
    """Rate limit notifications by priority level."""

    LIMITS: Dict[str, int] = {
        "critical": 0,  # 0 = unlimited
        "high": 10,
        "normal": 10,
        "background": 2,
    }
    WINDOW_SECONDS: int = 3600  # 1 hour

    def __init__(self) -> None:
        self._timestamps: Dict[str, List[float]] = defaultdict(list)

    def can_send(self, priority: str) -> bool:
        limit = self.LIMITS.get(priority, 10)
        if limit == 0:
            return True
        self._prune(priority)
        return len(self._timestamps[priority]) < limit

    def record(self, priority: str) -> None:
        self._timestamps[priority].append(time.time())

    def _prune(self, priority: str) -> None:
        cutoff = time.time() - self.WINDOW_SECONDS
        self._timestamps[priority] = [
            t for t in self._timestamps[priority] if t > cutoff
        ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dev_safety.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/dev/safety.py tests/test_dev_safety.py
git commit -m "feat(dev): add authority matrix, token budget tracking, and rate limiting"
```

---

### Task 4: Context Builder — Per-Tier Context Assembly

**Files:**
- Create: `hestia/dev/context_builder.py`
- Create: `tests/test_dev_context.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dev_context.py
"""Tests for per-tier context assembly."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from hestia.dev.models import AgentTier, DevSession, DevSessionSource
from hestia.dev.context_builder import DevContextBuilder


class TestDevContextBuilder:
    @pytest.fixture
    def builder(self):
        return DevContextBuilder()

    @pytest.fixture
    def session(self):
        s = DevSession.create(
            title="Fix bug", description="Fix the bug",
            source=DevSessionSource.CLI,
        )
        s.plan = {
            "steps": ["Read file", "Edit file"],
            "files": ["hestia/memory/manager.py"],
        }
        s.subtasks = [{"title": "Edit manager.py", "files": ["hestia/memory/manager.py"]}]
        return s

    @pytest.mark.asyncio
    async def test_architect_context_has_conventions(self, builder, session):
        with patch("hestia.dev.context_builder.Path") as mock_path:
            mock_path.return_value.read_text.return_value = "# CLAUDE.md content"
            mock_path.return_value.exists.return_value = True
            ctx = await builder.build_architect_context(session, task_description="Fix the bug")
        assert "system_prompt" in ctx
        assert "messages" in ctx

    @pytest.mark.asyncio
    async def test_engineer_context_has_subtask(self, builder, session):
        subtask = {"title": "Edit manager.py", "files": ["hestia/memory/manager.py"]}
        ctx = await builder.build_engineer_context(session, subtask=subtask)
        assert "system_prompt" in ctx
        assert "Edit manager.py" in ctx["system_prompt"] or "Edit manager.py" in str(ctx["messages"])

    @pytest.mark.asyncio
    async def test_validator_context_has_diff(self, builder, session):
        ctx = await builder.build_validator_context(
            session,
            diff="--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new",
            test_output="PASSED",
        )
        assert "diff" in str(ctx["messages"]).lower() or "diff" in ctx["system_prompt"].lower()

    def test_tier_to_builder_method(self, builder):
        assert hasattr(builder, "build_architect_context")
        assert hasattr(builder, "build_engineer_context")
        assert hasattr(builder, "build_researcher_context")
        assert hasattr(builder, "build_validator_context")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_dev_context.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write context builder**

```python
# hestia/dev/context_builder.py
"""Per-tier context assembly for dev agents."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent
from hestia.dev.models import DevSession

logger = get_logger()

PROJECT_ROOT = Path.home() / "hestia"

# Context budget caps (tokens, approximate)
ARCHITECT_BUDGET = 80_000
ENGINEER_BUDGET = 60_000
RESEARCHER_BUDGET = 500_000
VALIDATOR_BUDGET = 30_000

ARCHITECT_ROLE = """You are the Architect agent for Hestia's autonomous development system.
Your role: analyze tasks, produce implementation plans, decompose into subtasks, review completed work.
You NEVER write code directly. You plan, review, and decide.

Key responsibilities:
- Assess task complexity (simple/medium/complex/critical)
- Produce a step-by-step implementation plan with specific files and changes
- Decompose into subtasks that the Engineer can execute independently
- Review Engineer output for correctness and quality
- Decide: approve, request retry, replan, or escalate to Andrew

When producing a plan, output JSON with this structure:
{"steps": ["step1", "step2"], "files": ["path/to/file.py"], "risk": "low|medium|high", "estimated_minutes": 15, "complexity": "simple|medium|complex|critical"}
"""

ENGINEER_ROLE = """You are the Engineer agent for Hestia's autonomous development system.
Your role: execute code changes according to the Architect's plan.

Key responsibilities:
- Follow the subtask plan precisely — do not deviate
- Use edit_file for surgical replacements, write_file for new files
- Run targeted tests after each change (run_tests tool)
- Commit after each logical unit with descriptive messages prefixed [hestia-auto]
- Report results back: files changed, tests passed/failed, any issues

IMPORTANT:
- Stay within the approved plan. If you discover the plan is insufficient, report back — do NOT freelance.
- Protected paths (security/, config/, .env, .claude/) require elevated approval. If your subtask requires editing these, request elevation.
- Commits go on the session's feature branch, never on main.
"""

VALIDATOR_ROLE = """You are the Validator agent for Hestia's autonomous development system.
Your role: verify code changes through automated checks.

Key responsibilities:
- Run the full test suite and report pass/fail with details
- Run linters and type checks on changed files
- Report findings as structured JSON: {"passed": bool, "failures": [...], "warnings": [...]}
- You NEVER modify code. You observe and report.
"""

RESEARCHER_ROLE = """You are the Researcher agent for Hestia's autonomous development system.
Your role: perform deep codebase analysis when the Architect needs broader context.

Key responsibilities:
- Analyze full module source trees to understand architecture
- Identify cross-cutting concerns and dependencies
- Provide second-opinion code review (you are a different model than the author)
- Report findings clearly: what you found, what it means, recommendations

You NEVER write code. You analyze and advise.
"""


class DevContextBuilder:
    """Build tailored context for each agent tier."""

    async def build_architect_context(
        self,
        session: DevSession,
        task_description: str,
        memory_context: Optional[str] = None,
        researcher_findings: Optional[str] = None,
    ) -> Dict[str, Any]:
        parts = [ARCHITECT_ROLE]

        # Project conventions
        claude_md = PROJECT_ROOT / "CLAUDE.md"
        if claude_md.exists():
            content = claude_md.read_text()[:4000]
            parts.append(f"\n## Project Conventions\n{content}")

        # Sprint state
        sprint_md = PROJECT_ROOT / "SPRINT.md"
        if sprint_md.exists():
            content = sprint_md.read_text()[:2000]
            parts.append(f"\n## Current Sprint\n{content}")

        system_prompt = "\n".join(parts)

        messages_content = f"## Task\n{task_description}\n\nTitle: {session.title}\nDescription: {session.description}"

        # Git state
        git_log = self._run_git("log", "--oneline", "-20")
        git_status = self._run_git("status", "--short")
        if git_log:
            messages_content += f"\n\n## Recent Git History\n```\n{git_log}\n```"
        if git_status:
            messages_content += f"\n\n## Git Status\n```\n{git_status}\n```"

        if memory_context:
            messages_content += f"\n\n## Relevant Memory\n{memory_context}"

        if researcher_findings:
            messages_content += f"\n\n## Researcher Analysis\n{researcher_findings}"

        return {
            "system_prompt": system_prompt,
            "messages": [{"role": "user", "content": messages_content}],
        }

    async def build_engineer_context(
        self,
        session: DevSession,
        subtask: Dict[str, Any],
        memory_learnings: Optional[str] = None,
        codebase_invariants: Optional[str] = None,
    ) -> Dict[str, Any]:
        parts = [ENGINEER_ROLE]

        # Code conventions (condensed)
        claude_md = PROJECT_ROOT / "CLAUDE.md"
        if claude_md.exists():
            content = claude_md.read_text()[:3000]
            parts.append(f"\n## Code Conventions\n{content}")

        if codebase_invariants:
            parts.append(f"\n## Codebase Invariants (always follow)\n{codebase_invariants}")

        system_prompt = "\n".join(parts)

        messages_content = f"## Subtask\n{subtask.get('title', 'Untitled')}\n"
        if subtask.get("description"):
            messages_content += f"\n{subtask['description']}\n"

        # Include target file contents
        for file_path in subtask.get("files", []):
            full_path = PROJECT_ROOT / file_path
            if full_path.exists() and full_path.is_file():
                try:
                    content = full_path.read_text()[:10000]
                    messages_content += f"\n### {file_path}\n```python\n{content}\n```\n"
                except Exception:
                    pass

        if memory_learnings:
            messages_content += f"\n## Technical Notes (from past sessions)\n{memory_learnings}"

        return {
            "system_prompt": system_prompt,
            "messages": [{"role": "user", "content": messages_content}],
        }

    async def build_researcher_context(
        self,
        session: DevSession,
        architect_questions: str,
        module_paths: List[str],
        memory_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        parts = [RESEARCHER_ROLE]
        system_prompt = "\n".join(parts)

        messages_content = f"## Architect's Questions\n{architect_questions}\n"

        # Load full module source trees (leveraging 1M context)
        for module_path in module_paths:
            full_path = PROJECT_ROOT / module_path
            if full_path.is_dir():
                for py_file in sorted(full_path.rglob("*.py")):
                    try:
                        content = py_file.read_text()
                        rel = py_file.relative_to(PROJECT_ROOT)
                        messages_content += f"\n### {rel}\n```python\n{content}\n```\n"
                    except Exception:
                        pass
            elif full_path.is_file():
                try:
                    content = full_path.read_text()
                    messages_content += f"\n### {module_path}\n```python\n{content}\n```\n"
                except Exception:
                    pass

        if memory_context:
            messages_content += f"\n## Past Session Context\n{memory_context}"

        return {
            "system_prompt": system_prompt,
            "messages": [{"role": "user", "content": messages_content}],
        }

    async def build_validator_context(
        self,
        session: DevSession,
        diff: str = "",
        test_output: str = "",
        lint_output: str = "",
    ) -> Dict[str, Any]:
        system_prompt = VALIDATOR_ROLE

        messages_content = f"## Session: {session.title}\n"
        if diff:
            messages_content += f"\n## Git Diff\n```diff\n{diff[:15000]}\n```\n"
        if test_output:
            messages_content += f"\n## Test Output\n```\n{test_output[:10000]}\n```\n"
        if lint_output:
            messages_content += f"\n## Lint Output\n```\n{lint_output[:5000]}\n```\n"

        return {
            "system_prompt": system_prompt,
            "messages": [{"role": "user", "content": messages_content}],
        }

    def _run_git(self, *args: str) -> str:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=str(PROJECT_ROOT),
                capture_output=True, text=True, timeout=10,
            )
            return result.stdout.strip()
        except Exception:
            return ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dev_context.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/dev/context_builder.py tests/test_dev_context.py
git commit -m "feat(dev): add per-tier context builder with role prompts"
```

---

### Task 5: Memory Bridge — Store/Retrieve 4 Memory Types

**Files:**
- Create: `hestia/dev/memory_bridge.py`
- Create: `tests/test_dev_memory.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dev_memory.py
"""Tests for dev session memory bridge."""
import hashlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from hestia.dev.memory_bridge import DevMemoryBridge, MemoryType


class TestDevMemoryBridge:
    @pytest.fixture
    def mock_memory_manager(self):
        mm = AsyncMock()
        mm.store_exchange = AsyncMock()
        mm.build_context = AsyncMock(return_value="relevant memory context")
        return mm

    @pytest.fixture
    def bridge(self, mock_memory_manager):
        return DevMemoryBridge(memory_manager=mock_memory_manager)

    @pytest.mark.asyncio
    async def test_store_session_summary(self, bridge, mock_memory_manager):
        await bridge.store_session_summary(
            session_id="dev-abc",
            title="Fix memory bug",
            description="Fixed consolidator threshold",
            files_changed=["hestia/memory/consolidator.py"],
            key_decisions=["Used per-type threshold instead of global"],
        )
        mock_memory_manager.store_exchange.assert_called_once()
        call_args = mock_memory_manager.store_exchange.call_args
        assert "Fix memory bug" in str(call_args)

    @pytest.mark.asyncio
    async def test_store_technical_learning(self, bridge, mock_memory_manager):
        await bridge.store_technical_learning(
            session_id="dev-abc",
            file_path="hestia/memory/consolidator.py",
            learning="Consolidator tests need isolated ChromaDB instance",
            file_content_hash="abc123",
        )
        mock_memory_manager.store_exchange.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_failure_pattern(self, bridge, mock_memory_manager):
        await bridge.store_failure_pattern(
            session_id="dev-abc",
            approach="Mocked ToolRegistry singleton",
            failure_reason="Singleton caches across tests",
            resolution="Use fresh registry fixture",
        )
        mock_memory_manager.store_exchange.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_codebase_invariant(self, bridge, mock_memory_manager):
        await bridge.store_codebase_invariant(
            invariant="Never import from hestia.logging.logger — module doesn't exist",
            discovered_in="dev-abc",
        )
        mock_memory_manager.store_exchange.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_for_architect(self, bridge, mock_memory_manager):
        result = await bridge.retrieve_for_architect("Fix memory consolidator")
        mock_memory_manager.build_context.assert_called_once()
        assert result is not None

    def test_compute_file_hash(self, bridge):
        h = bridge.compute_file_hash("hello world")
        assert h == hashlib.sha256("hello world".encode()).hexdigest()[:16]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_dev_memory.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write memory bridge**

```python
# hestia/dev/memory_bridge.py
"""Bridge between dev sessions and Hestia's memory pipeline.

Stores 4 memory types: session summaries, technical learnings,
failure patterns, and codebase invariants.
"""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent

logger = get_logger()


class MemoryType(Enum):
    SESSION_SUMMARY = "dev_session_summary"
    TECHNICAL_LEARNING = "dev_technical_learning"
    FAILURE_PATTERN = "dev_failure_pattern"
    CODEBASE_INVARIANT = "dev_codebase_invariant"


class DevMemoryBridge:
    """Store and retrieve dev-specific memories via MemoryManager."""

    def __init__(self, memory_manager: Any) -> None:
        self._memory = memory_manager

    async def store_session_summary(
        self,
        session_id: str,
        title: str,
        description: str,
        files_changed: List[str],
        key_decisions: List[str],
    ) -> None:
        content = (
            f"[DEV SESSION SUMMARY] {title}\n"
            f"Session: {session_id}\n"
            f"Description: {description}\n"
            f"Files changed: {', '.join(files_changed)}\n"
            f"Key decisions: {'; '.join(key_decisions)}"
        )
        await self._memory.store_exchange(
            user_message=f"Dev session completed: {title}",
            assistant_message=content,
            metadata={"type": MemoryType.SESSION_SUMMARY.value, "session_id": session_id},
        )
        logger.info(
            f"Stored session summary for {session_id}",
            component=LogComponent.DEV,
        )

    async def store_technical_learning(
        self,
        session_id: str,
        file_path: str,
        learning: str,
        file_content_hash: str,
    ) -> None:
        content = (
            f"[DEV TECHNICAL LEARNING] {file_path}\n"
            f"Session: {session_id}\n"
            f"File hash: {file_content_hash}\n"
            f"Learning: {learning}"
        )
        await self._memory.store_exchange(
            user_message=f"Technical learning for {file_path}",
            assistant_message=content,
            metadata={
                "type": MemoryType.TECHNICAL_LEARNING.value,
                "session_id": session_id,
                "file_path": file_path,
                "file_hash": file_content_hash,
            },
        )

    async def store_failure_pattern(
        self,
        session_id: str,
        approach: str,
        failure_reason: str,
        resolution: str,
    ) -> None:
        content = (
            f"[DEV FAILURE PATTERN]\n"
            f"Session: {session_id}\n"
            f"Approach tried: {approach}\n"
            f"Why it failed: {failure_reason}\n"
            f"What worked instead: {resolution}"
        )
        await self._memory.store_exchange(
            user_message=f"Dev failure pattern: {approach}",
            assistant_message=content,
            metadata={"type": MemoryType.FAILURE_PATTERN.value, "session_id": session_id},
        )

    async def store_codebase_invariant(
        self,
        invariant: str,
        discovered_in: str,
    ) -> None:
        content = (
            f"[DEV CODEBASE INVARIANT]\n"
            f"Discovered in session: {discovered_in}\n"
            f"Rule: {invariant}"
        )
        await self._memory.store_exchange(
            user_message=f"Codebase invariant discovered: {invariant[:80]}",
            assistant_message=content,
            metadata={"type": MemoryType.CODEBASE_INVARIANT.value},
        )

    async def retrieve_for_architect(self, task_description: str) -> str:
        return await self._memory.build_context(
            f"dev session planning: {task_description}"
        )

    async def retrieve_for_engineer(self, file_paths: List[str]) -> str:
        query = "dev technical learnings for: " + ", ".join(file_paths)
        return await self._memory.build_context(query)

    async def retrieve_for_researcher(self, topic: str) -> str:
        return await self._memory.build_context(
            f"dev research context: {topic}"
        )

    async def retrieve_invariants(self) -> str:
        return await self._memory.build_context(
            "dev codebase invariants always follow"
        )

    @staticmethod
    def compute_file_hash(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:16]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dev_memory.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/dev/memory_bridge.py tests/test_dev_memory.py
git commit -m "feat(dev): add memory bridge for 4 dev-specific memory types"
```

---

### Task 6: Cloud Model Registry — Add Opus 4 + Haiku 4.5

**Files:**
- Modify: `hestia/cloud/models.py:243-261`

- [ ] **Step 1: Read current Anthropic model list**

Run: `head -265 hestia/cloud/models.py | tail -25`
Verify you see the current Anthropic models (Sonnet 4, Haiku 3.5).

- [ ] **Step 2: Add Opus 4 and update Haiku**

In `hestia/cloud/models.py`, replace the Anthropic models section:

```python
    CloudProvider.ANTHROPIC: {
        "base_url": "https://api.anthropic.com",
        "default_model": "claude-sonnet-4-20250514",
        "models": [
            CloudModel(
                "claude-opus-4-20250514",
                CloudProvider.ANTHROPIC,
                "Claude Opus 4",
                200000, 32768,
                0.015, 0.075,
            ),
            CloudModel(
                "claude-sonnet-4-20250514",
                CloudProvider.ANTHROPIC,
                "Claude Sonnet 4",
                200000, 8192,
                0.003, 0.015,
            ),
            CloudModel(
                "claude-haiku-4-5-20251001",
                CloudProvider.ANTHROPIC,
                "Claude Haiku 4.5",
                200000, 8192,
                0.001, 0.005,
            ),
        ],
    },
```

- [ ] **Step 3: Run existing cloud tests**

Run: `python -m pytest tests/test_cloud_models.py -v`
Expected: PASS (or adapt if test asserts exact model count)

- [ ] **Step 4: Commit**

```bash
git add hestia/cloud/models.py
git commit -m "feat(cloud): add Claude Opus 4 and Haiku 4.5 to Anthropic model registry"
```

---

### Task 7: New Tool Definitions

**Files:**
- Create: `hestia/dev/tools.py`
- Modify: `hestia/execution/tools/__init__.py`

- [ ] **Step 1: Write tool definitions**

```python
# hestia/dev/tools.py
"""Tool definitions for the agentic development system.

New tools: run_tests, git_push, git_branch, create_github_issue,
create_github_pr, xcode_build, server_restart, pip_audit, notify_andrew.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from hestia.execution.models import Tool, ToolParam, ToolParamType
from hestia.logging import get_logger, LogComponent

logger = get_logger()

PROJECT_ROOT = Path.home() / "hestia"


async def run_tests_handler(
    path: str = "",
    marker: str = "",
    verbose: bool = True,
) -> Dict[str, Any]:
    """Run pytest with optional path filter and marker."""
    cmd = ["python", "-m", "pytest"]
    if path:
        cmd.append(path)
    if marker:
        cmd.extend(["-m", marker])
    if verbose:
        cmd.append("-v")
    cmd.extend(["--timeout=60", "--tb=short", "-q"])

    try:
        result = subprocess.run(
            cmd, cwd=str(PROJECT_ROOT),
            capture_output=True, text=True, timeout=120,
        )
        passed = result.returncode == 0
        return {
            "passed": passed,
            "returncode": result.returncode,
            "stdout": result.stdout[-5000:] if result.stdout else "",
            "stderr": result.stderr[-2000:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"passed": False, "error": "Test run timed out after 120s"}
    except Exception as e:
        return {"passed": False, "error": str(e)}


async def git_push_handler(branch: str = "") -> Dict[str, Any]:
    """Push current or specified branch to origin."""
    cmd = ["git", "push", "origin"]
    if branch:
        cmd.append(branch)

    # Safety: never push to main directly
    if not branch:
        check = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True,
        )
        current = check.stdout.strip()
        if current in ("main", "master"):
            return {"success": False, "error": "Cannot push directly to main. Use a feature branch."}

    try:
        result = subprocess.run(
            cmd, cwd=str(PROJECT_ROOT),
            capture_output=True, text=True, timeout=30,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def git_branch_handler(name: str, checkout: bool = True) -> Dict[str, Any]:
    """Create and optionally checkout a new branch."""
    try:
        cmd = ["git", "checkout", "-b", name] if checkout else ["git", "branch", name]
        result = subprocess.run(
            cmd, cwd=str(PROJECT_ROOT),
            capture_output=True, text=True, timeout=10,
        )
        return {
            "success": result.returncode == 0,
            "branch": name,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def server_restart_handler() -> Dict[str, Any]:
    """Kill stale server processes and restart."""
    import signal
    try:
        # Kill stale processes on port 8443
        lsof = subprocess.run(
            ["lsof", "-i", ":8443", "-t"],
            capture_output=True, text=True, timeout=5,
        )
        pids = [p.strip() for p in lsof.stdout.split("\n") if p.strip()]
        killed = []
        for pid in pids:
            try:
                import os
                os.kill(int(pid), signal.SIGKILL)
                killed.append(pid)
            except (ProcessLookupError, ValueError):
                pass

        return {"success": True, "killed_pids": killed, "message": f"Killed {len(killed)} stale processes"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def xcode_build_handler(
    scheme: str = "HestiaWorkspace",
    destination: str = "platform=macOS",
) -> Dict[str, Any]:
    """Run xcodebuild to check compilation."""
    cmd = [
        "xcodebuild", "-scheme", scheme,
        "-destination", destination,
        "build",
        "-quiet",
    ]
    try:
        result = subprocess.run(
            cmd, cwd=str(PROJECT_ROOT / "HestiaApp"),
            capture_output=True, text=True, timeout=300,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[-3000:] if result.stdout else "",
            "stderr": result.stderr[-3000:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Build timed out after 300s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Tool object definitions ──────────────────────────────────────────────

run_tests_tool = Tool(
    name="run_tests",
    description="Run pytest test suite. Optionally filter by path or marker.",
    parameters=[
        ToolParam("path", ToolParamType.STRING, "Test file or directory path (relative to project root)", required=False),
        ToolParam("marker", ToolParamType.STRING, "Pytest marker to filter (e.g., 'integration')", required=False),
        ToolParam("verbose", ToolParamType.BOOLEAN, "Show verbose output", required=False),
    ],
    handler=run_tests_handler,
    category="development",
    requires_approval=False,
)

git_push_tool = Tool(
    name="git_push",
    description="Push branch to origin. Never pushes to main directly.",
    parameters=[
        ToolParam("branch", ToolParamType.STRING, "Branch name to push (default: current)", required=False),
    ],
    handler=git_push_handler,
    category="development",
    requires_approval=True,
)

git_branch_tool = Tool(
    name="git_branch",
    description="Create a new git branch and optionally switch to it.",
    parameters=[
        ToolParam("name", ToolParamType.STRING, "Branch name", required=True),
        ToolParam("checkout", ToolParamType.BOOLEAN, "Switch to the new branch", required=False),
    ],
    handler=git_branch_handler,
    category="development",
    requires_approval=False,
)

server_restart_tool = Tool(
    name="server_restart",
    description="Kill stale server processes on port 8443.",
    parameters=[],
    handler=server_restart_handler,
    category="development",
    requires_approval=False,
)

xcode_build_tool = Tool(
    name="xcode_build",
    description="Run xcodebuild to verify Swift code compiles.",
    parameters=[
        ToolParam("scheme", ToolParamType.STRING, "Xcode scheme (default: HestiaWorkspace)", required=False),
        ToolParam("destination", ToolParamType.STRING, "Build destination", required=False),
    ],
    handler=xcode_build_handler,
    category="development",
    requires_approval=False,
)


def get_dev_tools() -> List[Tool]:
    """Get all development tools."""
    return [
        run_tests_tool,
        git_push_tool,
        git_branch_tool,
        server_restart_tool,
        xcode_build_tool,
    ]
```

- [ ] **Step 2: Register dev tools in tools/__init__.py**

In `hestia/execution/tools/__init__.py`, add import and registration:

```python
# At top with other imports:
from hestia.dev.tools import get_dev_tools

# Inside register_builtin_tools(), after code tools registration:
    # Development tools (run_tests, git_push, etc.)
    for tool in get_dev_tools():
        registry.register(tool)
```

- [ ] **Step 3: Run existing tool registry tests**

Run: `python -m pytest tests/test_tool_registry.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add hestia/dev/tools.py hestia/execution/tools/__init__.py
git commit -m "feat(dev): add development tools (run_tests, git_push, git_branch, xcode_build, server_restart)"
```

---

### Task 8: DevSession Manager — Session Lifecycle Orchestration

**Files:**
- Create: `hestia/dev/manager.py`
- Create: `tests/test_dev_manager.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dev_manager.py
"""Tests for DevSessionManager — session lifecycle and state machine."""
import pytest
import pytest_asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from hestia.dev.models import (
    DevSession, DevSessionState, DevSessionSource, DevPriority,
    AgentTier, DevEventType,
)
from hestia.dev.manager import DevSessionManager


@pytest_asyncio.fixture
async def manager(tmp_path):
    m = DevSessionManager(db_path=tmp_path / "test_dev.db")
    await m.initialize()
    yield m
    await m.shutdown()


class TestDevSessionManager:
    @pytest.mark.asyncio
    async def test_create_session(self, manager):
        session = await manager.create_session(
            title="Fix bug",
            description="Fix the memory bug",
            source=DevSessionSource.CLI,
        )
        assert session.state == DevSessionState.QUEUED
        assert session.id.startswith("dev-")

    @pytest.mark.asyncio
    async def test_get_session(self, manager):
        session = await manager.create_session(
            title="Test", description="Test", source=DevSessionSource.CLI,
        )
        loaded = await manager.get_session(session.id)
        assert loaded is not None
        assert loaded.title == "Test"

    @pytest.mark.asyncio
    async def test_transition_valid(self, manager):
        session = await manager.create_session(
            title="Test", description="Test", source=DevSessionSource.CLI,
        )
        updated = await manager.transition(session.id, DevSessionState.PLANNING)
        assert updated.state == DevSessionState.PLANNING

    @pytest.mark.asyncio
    async def test_transition_invalid(self, manager):
        session = await manager.create_session(
            title="Test", description="Test", source=DevSessionSource.CLI,
        )
        with pytest.raises(ValueError, match="Invalid transition"):
            await manager.transition(session.id, DevSessionState.COMPLETE)

    @pytest.mark.asyncio
    async def test_approve_session(self, manager):
        session = await manager.create_session(
            title="Test", description="Test", source=DevSessionSource.CLI,
        )
        await manager.transition(session.id, DevSessionState.PLANNING)
        await manager.transition(session.id, DevSessionState.PROPOSED)
        approved = await manager.approve_session(session.id, approved_by="andrew_cli")
        assert approved.state == DevSessionState.EXECUTING
        assert approved.approved_by == "andrew_cli"

    @pytest.mark.asyncio
    async def test_cancel_session(self, manager):
        session = await manager.create_session(
            title="Test", description="Test", source=DevSessionSource.CLI,
        )
        cancelled = await manager.cancel_session(session.id)
        assert cancelled.state == DevSessionState.CANCELLED

    @pytest.mark.asyncio
    async def test_list_pending_proposals(self, manager):
        s = await manager.create_session(
            title="Proposal", description="Test", source=DevSessionSource.SELF_DISCOVERED,
        )
        await manager.transition(s.id, DevSessionState.PLANNING)
        await manager.transition(s.id, DevSessionState.PROPOSED)
        proposals = await manager.list_pending_proposals()
        assert len(proposals) == 1

    @pytest.mark.asyncio
    async def test_record_event(self, manager):
        session = await manager.create_session(
            title="Test", description="Test", source=DevSessionSource.CLI,
        )
        await manager.record_event(
            session_id=session.id,
            agent=AgentTier.ARCHITECT,
            event_type=DevEventType.PLAN_CREATED,
            detail={"plan": "do the thing"},
        )
        events = await manager.get_events(session.id)
        assert len(events) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_dev_manager.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write manager implementation**

```python
# hestia/dev/manager.py
"""DevSessionManager — orchestrates dev session lifecycle."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from hestia.logging import get_logger, LogComponent
from hestia.dev.database import DevDatabase
from hestia.dev.models import (
    DevSession, DevEvent, DevSessionState, DevSessionSource,
    DevPriority, AgentTier, DevEventType,
)

logger = get_logger()


class DevSessionManager:
    """Manages dev session lifecycle, state transitions, and event recording."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db = DevDatabase(db_path=db_path) if db_path else DevDatabase()
        self._initialized = False

    async def initialize(self) -> None:
        if not self._initialized:
            await self._db.connect()
            self._initialized = True
            logger.info("DevSessionManager initialized", component=LogComponent.DEV)

    async def shutdown(self) -> None:
        if self._initialized:
            await self._db.close()
            self._initialized = False

    async def create_session(
        self,
        title: str,
        description: str,
        source: DevSessionSource,
        source_ref: Optional[str] = None,
        priority: DevPriority = DevPriority.NORMAL,
    ) -> DevSession:
        session = DevSession.create(
            title=title,
            description=description,
            source=source,
            source_ref=source_ref,
            priority=priority,
        )
        await self._db.save_session(session)
        logger.info(
            f"Created dev session {session.id}: {title}",
            component=LogComponent.DEV,
            data={"session_id": session.id, "source": source.value},
        )
        return session

    async def get_session(self, session_id: str) -> Optional[DevSession]:
        return await self._db.get_session(session_id)

    async def transition(
        self,
        session_id: str,
        target_state: DevSessionState,
    ) -> DevSession:
        session = await self._db.get_session(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id}")

        session.transition(target_state)

        if target_state == DevSessionState.EXECUTING and not session.started_at:
            session.started_at = datetime.now(timezone.utc).isoformat()
        if target_state == DevSessionState.COMPLETE:
            session.completed_at = datetime.now(timezone.utc).isoformat()

        await self._db.update_session(session)

        await self.record_event(
            session_id=session_id,
            agent=AgentTier.ARCHITECT,
            event_type=DevEventType.STATE_CHANGE,
            detail={"from": session.state.value, "to": target_state.value},
        )

        logger.info(
            f"Session {session_id} → {target_state.value}",
            component=LogComponent.DEV,
        )
        return session

    async def approve_session(
        self,
        session_id: str,
        approved_by: str = "andrew",
    ) -> DevSession:
        session = await self._db.get_session(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id}")
        if session.state != DevSessionState.PROPOSED:
            raise ValueError(f"Session {session_id} is not in PROPOSED state")

        session.approved_at = datetime.now(timezone.utc).isoformat()
        session.approved_by = approved_by
        session.transition(DevSessionState.EXECUTING)
        await self._db.update_session(session)

        await self.record_event(
            session_id=session_id,
            agent=AgentTier.ARCHITECT,
            event_type=DevEventType.APPROVAL_GRANTED,
            detail={"approved_by": approved_by},
        )

        logger.info(
            f"Session {session_id} approved by {approved_by}",
            component=LogComponent.DEV,
        )
        return session

    async def cancel_session(self, session_id: str) -> DevSession:
        session = await self._db.get_session(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id}")

        session.transition(DevSessionState.CANCELLED)
        session.completed_at = datetime.now(timezone.utc).isoformat()
        await self._db.update_session(session)

        logger.info(f"Session {session_id} cancelled", component=LogComponent.DEV)
        return session

    async def list_sessions(
        self,
        state: Optional[DevSessionState] = None,
        limit: int = 50,
    ) -> List[DevSession]:
        return await self._db.list_sessions(state=state, limit=limit)

    async def list_pending_proposals(self) -> List[DevSession]:
        return await self._db.get_pending_proposals()

    async def record_event(
        self,
        session_id: str,
        agent: AgentTier,
        event_type: DevEventType,
        detail: Optional[dict] = None,
        tokens_used: int = 0,
        model: Optional[str] = None,
        files_affected: Optional[List[str]] = None,
    ) -> None:
        event = DevEvent.create(
            session_id=session_id,
            agent=agent,
            event_type=event_type,
            detail=detail,
            tokens_used=tokens_used,
            model=model,
            files_affected=files_affected,
        )
        await self._db.save_event(event)

    async def get_events(
        self,
        session_id: str,
        event_type: Optional[DevEventType] = None,
    ) -> List[DevEvent]:
        return await self._db.list_events(session_id, event_type=event_type)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dev_manager.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/dev/manager.py tests/test_dev_manager.py
git commit -m "feat(dev): add DevSessionManager with session lifecycle and state machine"
```

---

### Task 9: Architect Agent

**Files:**
- Create: `hestia/dev/architect.py`
- Create: `tests/test_dev_architect.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dev_architect.py
"""Tests for the Architect agent — planning, review, decomposition."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from hestia.dev.architect import ArchitectAgent
from hestia.dev.models import (
    DevSession, DevSessionSource, DevComplexity,
)


@pytest.fixture
def mock_cloud_client():
    from hestia.inference import InferenceResponse
    client = AsyncMock()
    client.complete = AsyncMock(return_value=InferenceResponse(
        content=json.dumps({
            "steps": ["Read file", "Edit function", "Run tests"],
            "files": ["hestia/memory/consolidator.py"],
            "risk": "low",
            "estimated_minutes": 15,
            "complexity": "simple",
            "subtasks": [
                {"title": "Fix threshold logic", "description": "Change threshold from 0.90 to per-type", "files": ["hestia/memory/consolidator.py"]},
            ],
        }),
        tokens_in=500,
        tokens_out=200,
    ))
    return client


@pytest.fixture
def architect(mock_cloud_client):
    return ArchitectAgent(cloud_client=mock_cloud_client)


class TestArchitectAgent:
    @pytest.mark.asyncio
    async def test_plan_produces_structured_output(self, architect):
        session = DevSession.create(
            title="Fix consolidator",
            description="Fix similarity threshold",
            source=DevSessionSource.CLI,
        )
        plan = await architect.create_plan(session, "Fix the consolidator threshold")
        assert "steps" in plan
        assert "files" in plan
        assert "subtasks" in plan
        assert len(plan["subtasks"]) > 0

    @pytest.mark.asyncio
    async def test_plan_sets_complexity(self, architect):
        session = DevSession.create(
            title="Test", description="Test", source=DevSessionSource.CLI,
        )
        plan = await architect.create_plan(session, "Fix a bug")
        assert plan.get("complexity") in ("simple", "medium", "complex", "critical")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_dev_architect.py -v`
Expected: FAIL

- [ ] **Step 3: Write Architect agent**

```python
# hestia/dev/architect.py
"""Architect agent — plans, reviews, decomposes tasks using Claude Opus."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from hestia.inference import InferenceResponse, Message
from hestia.logging import get_logger, LogComponent
from hestia.dev.context_builder import DevContextBuilder
from hestia.dev.models import DevSession, DevComplexity

logger = get_logger()


class ArchitectAgent:
    """Plans tasks, reviews output, decomposes into subtasks."""

    def __init__(
        self,
        cloud_client: Any,
        memory_bridge: Optional[Any] = None,
    ) -> None:
        self._cloud = cloud_client
        self._memory = memory_bridge
        self._context_builder = DevContextBuilder()

    async def create_plan(
        self,
        session: DevSession,
        task_description: str,
        researcher_findings: Optional[str] = None,
    ) -> Dict[str, Any]:
        memory_context = None
        if self._memory:
            memory_context = await self._memory.retrieve_for_architect(task_description)

        ctx = await self._context_builder.build_architect_context(
            session=session,
            task_description=task_description,
            memory_context=memory_context,
            researcher_findings=researcher_findings,
        )

        messages = [Message(role=m["role"], content=m["content"]) for m in ctx["messages"]]

        response: InferenceResponse = await self._cloud.complete(
            provider=self._get_provider(),
            model_id=session.architect_model,
            api_key=await self._get_api_key(),
            messages=messages,
            system=ctx["system_prompt"],
            max_tokens=8192,
            temperature=0.0,
        )

        plan = self._parse_plan(response.content)
        return plan

    async def review_diff(
        self,
        session: DevSession,
        diff: str,
        test_results: str,
    ) -> Dict[str, Any]:
        ctx = await self._context_builder.build_architect_context(
            session=session,
            task_description=(
                f"Review the completed work for session '{session.title}'.\n\n"
                f"## Diff\n```diff\n{diff[:20000]}\n```\n\n"
                f"## Test Results\n```\n{test_results[:5000]}\n```\n\n"
                "Respond with JSON: {\"approved\": true/false, \"feedback\": \"...\", \"issues\": [...]}"
            ),
        )

        messages = [Message(role=m["role"], content=m["content"]) for m in ctx["messages"]]

        response = await self._cloud.complete(
            provider=self._get_provider(),
            model_id=session.architect_model,
            api_key=await self._get_api_key(),
            messages=messages,
            system=ctx["system_prompt"],
            max_tokens=4096,
            temperature=0.0,
        )

        return self._parse_json_response(response.content, default={"approved": False, "feedback": response.content})

    def _parse_plan(self, content: str) -> Dict[str, Any]:
        """Extract JSON plan from model response."""
        plan = self._parse_json_response(content, default={
            "steps": [],
            "files": [],
            "risk": "medium",
            "estimated_minutes": 30,
            "complexity": "medium",
            "subtasks": [],
        })
        # Ensure required fields
        plan.setdefault("steps", [])
        plan.setdefault("files", [])
        plan.setdefault("subtasks", [])
        plan.setdefault("risk", "medium")
        plan.setdefault("complexity", "medium")
        plan.setdefault("estimated_minutes", 30)
        return plan

    def _parse_json_response(self, content: str, default: Dict) -> Dict:
        """Try to extract JSON from response content."""
        # Try direct parse
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        # Try extracting from markdown code block
        if "```json" in content:
            start = content.index("```json") + 7
            end = content.index("```", start)
            try:
                return json.loads(content[start:end].strip())
            except (json.JSONDecodeError, ValueError):
                pass
        if "```" in content:
            start = content.index("```") + 3
            end = content.index("```", start)
            try:
                return json.loads(content[start:end].strip())
            except (json.JSONDecodeError, ValueError):
                pass
        return default

    def _get_provider(self):
        from hestia.cloud.models import CloudProvider
        return CloudProvider.ANTHROPIC

    async def _get_api_key(self) -> str:
        from hestia.cloud import get_cloud_manager
        manager = await get_cloud_manager()
        return await manager.get_api_key(self._get_provider())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dev_architect.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/dev/architect.py tests/test_dev_architect.py
git commit -m "feat(dev): add Architect agent (Opus) — planning, review, decomposition"
```

---

### Task 10: Engineer Agent

**Files:**
- Create: `hestia/dev/engineer.py`
- Create: `tests/test_dev_engineer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dev_engineer.py
"""Tests for the Engineer agent — code execution tool loop."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from hestia.dev.engineer import EngineerAgent
from hestia.dev.models import DevSession, DevSessionSource, AgentTier
from hestia.dev.safety import AuthorityMatrix


class TestEngineerAgent:
    @pytest.fixture
    def mock_cloud_client(self):
        from hestia.inference import InferenceResponse
        client = AsyncMock()
        # First call: model uses a tool; second call: model responds with text
        client.complete = AsyncMock(side_effect=[
            InferenceResponse(content="Done. File edited successfully.", tokens_in=300, tokens_out=100, tool_calls=None),
        ])
        return client

    @pytest.fixture
    def engineer(self, mock_cloud_client):
        return EngineerAgent(cloud_client=mock_cloud_client)

    @pytest.mark.asyncio
    async def test_execute_subtask_returns_result(self, engineer):
        session = DevSession.create(
            title="Test", description="Test", source=DevSessionSource.CLI,
        )
        subtask = {
            "title": "Edit file",
            "description": "Change the threshold",
            "files": ["hestia/memory/consolidator.py"],
        }
        result = await engineer.execute_subtask(session, subtask)
        assert "content" in result
        assert result["tokens_used"] > 0

    def test_authority_check(self):
        assert AuthorityMatrix.can_use_tool(AgentTier.ENGINEER, "edit_file") is True
        assert AuthorityMatrix.can_use_tool(AgentTier.ENGINEER, "create_github_pr") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_dev_engineer.py -v`
Expected: FAIL

- [ ] **Step 3: Write Engineer agent**

```python
# hestia/dev/engineer.py
"""Engineer agent — executes code changes using Claude Sonnet with tool loop."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from hestia.inference import InferenceResponse, Message
from hestia.execution import ToolCall, get_tool_executor, get_tool_registry
from hestia.logging import get_logger, LogComponent
from hestia.dev.context_builder import DevContextBuilder
from hestia.dev.models import DevSession, AgentTier
from hestia.dev.safety import AuthorityMatrix

logger = get_logger()

MAX_TOOL_ITERATIONS = 25
MAX_TOKENS_PER_SUBTASK = 150_000


class EngineerAgent:
    """Executes subtasks via cloud inference + tool loop."""

    def __init__(
        self,
        cloud_client: Any,
        memory_bridge: Optional[Any] = None,
    ) -> None:
        self._cloud = cloud_client
        self._memory = memory_bridge
        self._context_builder = DevContextBuilder()

    async def execute_subtask(
        self,
        session: DevSession,
        subtask: Dict[str, Any],
    ) -> Dict[str, Any]:
        memory_learnings = None
        invariants = None
        if self._memory:
            file_paths = subtask.get("files", [])
            if file_paths:
                memory_learnings = await self._memory.retrieve_for_engineer(file_paths)
            invariants = await self._memory.retrieve_invariants()

        ctx = await self._context_builder.build_engineer_context(
            session=session,
            subtask=subtask,
            memory_learnings=memory_learnings,
            codebase_invariants=invariants,
        )

        messages = [Message(role=m["role"], content=m["content"]) for m in ctx["messages"]]

        # Get tool definitions filtered by Engineer authority
        registry = get_tool_registry()
        all_tools = registry.get_definitions_as_list()
        engineer_tools = [
            t for t in all_tools
            if AuthorityMatrix.can_use_tool(AgentTier.ENGINEER, t["function"]["name"])
        ]

        total_tokens = 0
        iteration = 0
        last_content = ""
        files_affected: List[str] = []

        while iteration < MAX_TOOL_ITERATIONS:
            iteration += 1

            response: InferenceResponse = await self._cloud.complete(
                provider=self._get_provider(),
                model_id=session.engineer_model,
                api_key=await self._get_api_key(),
                messages=messages,
                system=ctx["system_prompt"],
                tools=engineer_tools,
                max_tokens=8192,
                temperature=0.0,
            )

            total_tokens += response.tokens_in + response.tokens_out
            last_content = response.content or ""

            if not response.tool_calls:
                break  # Model is done

            # Execute tool calls
            messages.append(Message(role="assistant", content=last_content, tool_calls=response.tool_calls))

            executor = await get_tool_executor()
            for tc in response.tool_calls:
                tool_name = tc.get("function", {}).get("name", "unknown") if isinstance(tc, dict) else "unknown"
                tool_args = tc.get("function", {}).get("arguments", {}) if isinstance(tc, dict) else {}
                tool_call_id = tc.get("id", "") if isinstance(tc, dict) else ""

                # Track files
                if "path" in tool_args:
                    files_affected.append(tool_args["path"])

                tool_call = ToolCall.create(tool_name=tool_name, arguments=tool_args if isinstance(tool_args, dict) else {})
                result = await executor.execute(tool_call)

                messages.append(Message(
                    role="user",
                    content=f"[TOOL DATA for {tool_name}]\n{result.to_message_content()}\n[END TOOL DATA]",
                    tool_call_id=tool_call_id,
                ))

            if total_tokens > MAX_TOKENS_PER_SUBTASK:
                break

        return {
            "content": last_content,
            "tokens_used": total_tokens,
            "iterations": iteration,
            "files_affected": list(set(files_affected)),
        }

    def _get_provider(self):
        from hestia.cloud.models import CloudProvider
        return CloudProvider.ANTHROPIC

    async def _get_api_key(self) -> str:
        from hestia.cloud import get_cloud_manager
        manager = await get_cloud_manager()
        return await manager.get_api_key(self._get_provider())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dev_engineer.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/dev/engineer.py tests/test_dev_engineer.py
git commit -m "feat(dev): add Engineer agent (Sonnet) — tool loop execution with authority filtering"
```

---

### Task 11: API Routes

**Files:**
- Create: `hestia/api/routes/dev.py`
- Create: `tests/test_dev_routes.py`
- Modify: `hestia/api/server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dev_routes.py
"""Tests for dev session API routes."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def mock_auth():
    with patch("hestia.api.routes.dev.get_device_token", return_value="test-device"):
        yield


@pytest.fixture
def mock_manager():
    from hestia.dev.models import DevSession, DevSessionSource, DevSessionState
    manager = AsyncMock()
    session = DevSession.create(title="Test", description="Test", source=DevSessionSource.CLI)
    manager.create_session = AsyncMock(return_value=session)
    manager.get_session = AsyncMock(return_value=session)
    manager.list_sessions = AsyncMock(return_value=[session])
    manager.list_pending_proposals = AsyncMock(return_value=[session])
    manager.approve_session = AsyncMock(return_value=session)
    manager.cancel_session = AsyncMock(return_value=session)
    manager.get_events = AsyncMock(return_value=[])
    return manager


class TestDevRoutes:
    @pytest.mark.asyncio
    async def test_create_session(self, mock_auth, mock_manager):
        with patch("hestia.api.routes.dev.get_dev_session_manager", return_value=mock_manager):
            from hestia.api.routes.dev import router
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)
            response = client.post(
                "/v1/dev/sessions",
                json={"title": "Fix bug", "description": "Fix it", "source": "cli"},
                headers={"X-Hestia-Device-Token": "test"},
            )
            assert response.status_code == 200
            assert "id" in response.json()

    @pytest.mark.asyncio
    async def test_list_sessions(self, mock_auth, mock_manager):
        with patch("hestia.api.routes.dev.get_dev_session_manager", return_value=mock_manager):
            from hestia.api.routes.dev import router
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)
            response = client.get(
                "/v1/dev/sessions",
                headers={"X-Hestia-Device-Token": "test"},
            )
            assert response.status_code == 200
            assert "sessions" in response.json()

    @pytest.mark.asyncio
    async def test_approve_session(self, mock_auth, mock_manager):
        with patch("hestia.api.routes.dev.get_dev_session_manager", return_value=mock_manager):
            from hestia.api.routes.dev import router
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)
            response = client.post(
                "/v1/dev/sessions/dev-test/approve",
                headers={"X-Hestia-Device-Token": "test"},
            )
            assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_dev_routes.py -v`
Expected: FAIL

- [ ] **Step 3: Write API routes**

```python
# hestia/api/routes/dev.py
"""API routes for the Agentic Development System."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from hestia.api.auth import get_device_token
from hestia.api.errors import sanitize_for_log
from hestia.logging import get_logger, LogComponent
from hestia.dev import get_dev_session_manager
from hestia.dev.models import (
    DevSessionState, DevSessionSource, DevPriority,
)

logger = get_logger()

router = APIRouter(prefix="/v1/dev", tags=["dev"])


class CreateSessionRequest(BaseModel):
    title: str
    description: str
    source: str = "cli"
    source_ref: Optional[str] = None
    priority: int = 3


class SessionResponse(BaseModel):
    id: str
    title: str
    description: str
    state: str
    source: str
    priority: int
    branch_name: Optional[str]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    total_tokens: int
    retry_count: int
    replan_count: int


class SessionListResponse(BaseModel):
    sessions: List[SessionResponse]


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    device_id: str = Depends(get_device_token),
):
    manager = await get_dev_session_manager()
    session = await manager.create_session(
        title=request.title,
        description=request.description,
        source=DevSessionSource(request.source),
        source_ref=request.source_ref,
        priority=DevPriority(request.priority),
    )
    return _session_to_response(session)


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    state: Optional[str] = None,
    limit: int = 50,
    device_id: str = Depends(get_device_token),
):
    manager = await get_dev_session_manager()
    state_enum = DevSessionState(state) if state else None
    sessions = await manager.list_sessions(state=state_enum, limit=limit)
    return SessionListResponse(
        sessions=[_session_to_response(s) for s in sessions]
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    device_id: str = Depends(get_device_token),
):
    manager = await get_dev_session_manager()
    session = await manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_to_response(session)


@router.post("/sessions/{session_id}/approve", response_model=SessionResponse)
async def approve_session(
    session_id: str,
    device_id: str = Depends(get_device_token),
):
    manager = await get_dev_session_manager()
    try:
        session = await manager.approve_session(session_id, approved_by=device_id)
        return _session_to_response(session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{session_id}/cancel", response_model=SessionResponse)
async def cancel_session(
    session_id: str,
    device_id: str = Depends(get_device_token),
):
    manager = await get_dev_session_manager()
    try:
        session = await manager.cancel_session(session_id)
        return _session_to_response(session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/proposals")
async def list_proposals(
    device_id: str = Depends(get_device_token),
):
    manager = await get_dev_session_manager()
    proposals = await manager.list_pending_proposals()
    return {"proposals": [_session_to_response(p) for p in proposals]}


@router.get("/sessions/{session_id}/events")
async def get_session_events(
    session_id: str,
    device_id: str = Depends(get_device_token),
):
    manager = await get_dev_session_manager()
    events = await manager.get_events(session_id)
    return {
        "events": [
            {
                "id": e.id,
                "timestamp": e.timestamp,
                "agent": e.agent.value,
                "event_type": e.event_type.value,
                "detail": e.detail,
                "tokens_used": e.tokens_used,
                "model": e.model,
                "files_affected": e.files_affected,
            }
            for e in events
        ]
    }


def _session_to_response(session) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        title=session.title,
        description=session.description,
        state=session.state.value,
        source=session.source.value,
        priority=session.priority.value,
        branch_name=session.branch_name,
        created_at=session.created_at,
        started_at=session.started_at,
        completed_at=session.completed_at,
        total_tokens=session.total_tokens,
        retry_count=session.retry_count,
        replan_count=session.replan_count,
    )
```

- [ ] **Step 4: Register route in server.py**

In `hestia/api/server.py`, add with the other router imports and registrations:

```python
from hestia.api.routes.dev import router as dev_router
# ...
app.include_router(dev_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_dev_routes.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add hestia/api/routes/dev.py tests/test_dev_routes.py hestia/api/server.py
git commit -m "feat(dev): add API routes for dev sessions (CRUD, approve, cancel, events)"
```

---

### Task 12: CLI /dev Command Family

**Files:**
- Modify: `hestia-cli/hestia_cli/commands.py`

- [ ] **Step 1: Read current commands.py structure**

Run: `grep -n "def handle_" hestia-cli/hestia_cli/commands.py`
Understand the pattern for adding new commands.

- [ ] **Step 2: Add /dev command handlers**

Add to `hestia-cli/hestia_cli/commands.py`, following the existing pattern for `/cloud` and `/code`:

```python
async def handle_dev_command(args: str, client, console: Console) -> None:
    """Handle /dev command family for agentic development sessions."""
    parts = args.strip().split(maxsplit=1)
    subcommand = parts[0] if parts else ""
    sub_args = parts[1] if len(parts) > 1 else ""

    base_url = client._base_url.replace("ws://", "http://").replace("wss://", "https://").rstrip("/ws/chat")
    headers = {"X-Hestia-Device-Token": client._token}

    if not subcommand:
        # /dev — show help
        console.print(Panel(
            "[bold]Dev Session Commands[/bold]\n\n"
            "  /dev <task>              Start a new dev session\n"
            "  /dev queue               List active/queued sessions\n"
            "  /dev proposals           List pending proposals\n"
            "  /dev status <id>         Session status and progress\n"
            "  /dev approve <id>        Approve a proposal\n"
            "  /dev cancel <id>         Cancel a session\n"
            "  /dev log <id>            View session audit log\n",
            title="[bold]Agentic Development[/bold]",
            border_style="blue",
        ))
        return

    import httpx

    if subcommand == "queue":
        async with httpx.AsyncClient(verify=False) as http:
            resp = await http.get(f"{base_url}/v1/dev/sessions", headers=headers)
            data = resp.json()
            sessions = data.get("sessions", [])
            if not sessions:
                console.print("[dim]No dev sessions.[/dim]")
                return
            for s in sessions:
                state_color = {"queued": "white", "proposed": "yellow", "executing": "blue", "complete": "green", "failed": "red", "blocked": "red"}.get(s["state"], "white")
                console.print(f"  [{state_color}]{s['state']:12}[/{state_color}] {s['id'][:16]}  {s['title']}")

    elif subcommand == "proposals":
        async with httpx.AsyncClient(verify=False) as http:
            resp = await http.get(f"{base_url}/v1/dev/proposals", headers=headers)
            data = resp.json()
            proposals = data.get("proposals", [])
            if not proposals:
                console.print("[dim]No pending proposals.[/dim]")
                return
            for p in proposals:
                console.print(f"  [yellow]PROPOSED[/yellow]  {p['id'][:16]}  {p['title']}")
            console.print(f"\n[dim]Approve with: /dev approve <id>[/dim]")

    elif subcommand == "approve" and sub_args:
        session_id = sub_args.strip()
        async with httpx.AsyncClient(verify=False) as http:
            resp = await http.post(f"{base_url}/v1/dev/sessions/{session_id}/approve", headers=headers)
            if resp.status_code == 200:
                console.print(f"[green]Approved[/green] {session_id}")
            else:
                console.print(f"[red]Failed:[/red] {resp.json().get('detail', 'Unknown error')}")

    elif subcommand == "cancel" and sub_args:
        session_id = sub_args.strip()
        async with httpx.AsyncClient(verify=False) as http:
            resp = await http.post(f"{base_url}/v1/dev/sessions/{session_id}/cancel", headers=headers)
            if resp.status_code == 200:
                console.print(f"[yellow]Cancelled[/yellow] {session_id}")
            else:
                console.print(f"[red]Failed:[/red] {resp.json().get('detail', 'Unknown error')}")

    elif subcommand == "status" and sub_args:
        session_id = sub_args.strip()
        async with httpx.AsyncClient(verify=False) as http:
            resp = await http.get(f"{base_url}/v1/dev/sessions/{session_id}", headers=headers)
            if resp.status_code == 200:
                s = resp.json()
                console.print(Panel(
                    f"[bold]{s['title']}[/bold]\n"
                    f"State: {s['state']}  Priority: {s['priority']}\n"
                    f"Tokens: {s['total_tokens']:,}  Retries: {s['retry_count']}/{3}\n"
                    f"Branch: {s.get('branch_name', 'N/A')}\n"
                    f"Created: {s['created_at'][:19]}",
                    title=f"Session {session_id}",
                ))
            else:
                console.print(f"[red]Session not found[/red]")

    elif subcommand == "log" and sub_args:
        session_id = sub_args.strip()
        async with httpx.AsyncClient(verify=False) as http:
            resp = await http.get(f"{base_url}/v1/dev/sessions/{session_id}/events", headers=headers)
            if resp.status_code == 200:
                events = resp.json().get("events", [])
                for e in events:
                    console.print(f"  {e['timestamp'][:19]}  [{e['agent']}] {e['event_type']}")
            else:
                console.print(f"[red]Session not found[/red]")

    else:
        # /dev <task description> — start a new session
        task = args.strip()
        async with httpx.AsyncClient(verify=False) as http:
            resp = await http.post(
                f"{base_url}/v1/dev/sessions",
                json={"title": task[:80], "description": task, "source": "cli"},
                headers=headers,
            )
            if resp.status_code == 200:
                s = resp.json()
                console.print(f"[green]Created[/green] dev session {s['id']}: {s['title']}")
            else:
                console.print(f"[red]Failed to create session[/red]")
```

- [ ] **Step 3: Register /dev in the command dispatcher**

In the command dispatch section of `commands.py`, add:

```python
    elif command == "/dev":
        await handle_dev_command(args, client, console)
```

Also add to the `/help` output and tab completion list.

- [ ] **Step 4: Commit**

```bash
git add hestia-cli/hestia_cli/commands.py
git commit -m "feat(cli): add /dev command family for agentic development sessions"
```

---

### Task 13: Update auto-test.sh Mappings

**Files:**
- Modify: `scripts/auto-test.sh`

- [ ] **Step 1: Add dev module mappings**

Add to the case statement in `scripts/auto-test.sh`:

```bash
    hestia/dev/models.py)          TEST_FILE="tests/test_dev_models.py" ;;
    hestia/dev/database.py)        TEST_FILE="tests/test_dev_database.py" ;;
    hestia/dev/manager.py)         TEST_FILE="tests/test_dev_manager.py" ;;
    hestia/dev/architect.py)       TEST_FILE="tests/test_dev_architect.py" ;;
    hestia/dev/engineer.py)        TEST_FILE="tests/test_dev_engineer.py" ;;
    hestia/dev/safety.py)          TEST_FILE="tests/test_dev_safety.py" ;;
    hestia/dev/context_builder.py) TEST_FILE="tests/test_dev_context.py" ;;
    hestia/dev/memory_bridge.py)   TEST_FILE="tests/test_dev_memory.py" ;;
    hestia/api/routes/dev.py)      TEST_FILE="tests/test_dev_routes.py" ;;
```

- [ ] **Step 2: Commit**

```bash
git add scripts/auto-test.sh
git commit -m "chore: add dev module mappings to auto-test.sh"
```

---

### Task 14: Integration Test — Full Session Lifecycle

**Files:**
- Create: `tests/test_dev_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_dev_integration.py
"""Integration test — full dev session lifecycle from QUEUED to COMPLETE."""
import pytest
import pytest_asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

from hestia.dev.models import (
    DevSessionState, DevSessionSource, AgentTier, DevEventType,
)
from hestia.dev.manager import DevSessionManager


@pytest_asyncio.fixture
async def manager(tmp_path):
    m = DevSessionManager(db_path=tmp_path / "integration_dev.db")
    await m.initialize()
    yield m
    await m.shutdown()


class TestFullSessionLifecycle:
    @pytest.mark.asyncio
    async def test_queued_to_complete(self, manager):
        """Simulate: create → plan → propose → approve → execute → validate → review → complete."""
        # Create
        session = await manager.create_session(
            title="Fix memory bug",
            description="Consolidator skips short exchanges",
            source=DevSessionSource.CLI,
        )
        assert session.state == DevSessionState.QUEUED

        # Plan
        session = await manager.transition(session.id, DevSessionState.PLANNING)
        assert session.state == DevSessionState.PLANNING

        # Record plan event
        await manager.record_event(
            session_id=session.id,
            agent=AgentTier.ARCHITECT,
            event_type=DevEventType.PLAN_CREATED,
            detail={"steps": ["Edit consolidator.py"], "files": ["hestia/memory/consolidator.py"]},
        )

        # Propose
        session = await manager.transition(session.id, DevSessionState.PROPOSED)
        assert session.state == DevSessionState.PROPOSED

        # Approve (Andrew)
        session = await manager.approve_session(session.id, approved_by="andrew_cli")
        assert session.state == DevSessionState.EXECUTING
        assert session.approved_by == "andrew_cli"

        # Execute → Validate
        await manager.record_event(
            session_id=session.id,
            agent=AgentTier.ENGINEER,
            event_type=DevEventType.FILE_EDITED,
            detail={"path": "hestia/memory/consolidator.py", "before_hash": "abc", "after_hash": "def"},
            files_affected=["hestia/memory/consolidator.py"],
        )
        session = await manager.transition(session.id, DevSessionState.VALIDATING)

        # Validate passes → Review
        await manager.record_event(
            session_id=session.id,
            agent=AgentTier.VALIDATOR,
            event_type=DevEventType.TEST_RUN,
            detail={"passed": True, "total": 3037, "failed": 0},
        )
        session = await manager.transition(session.id, DevSessionState.REVIEWING)

        # Review → Complete
        await manager.record_event(
            session_id=session.id,
            agent=AgentTier.ARCHITECT,
            event_type=DevEventType.REVIEW,
            detail={"approved": True, "feedback": "Looks good"},
        )
        session = await manager.transition(session.id, DevSessionState.COMPLETE)
        assert session.state == DevSessionState.COMPLETE
        assert session.completed_at is not None

        # Verify audit trail
        events = await manager.get_events(session.id)
        event_types = [e.event_type for e in events]
        assert DevEventType.PLAN_CREATED in event_types
        assert DevEventType.FILE_EDITED in event_types
        assert DevEventType.TEST_RUN in event_types
        assert DevEventType.REVIEW in event_types

    @pytest.mark.asyncio
    async def test_failure_and_retry(self, manager):
        """Simulate: execute → validate fails → retry → validate passes."""
        session = await manager.create_session(
            title="Test retry", description="Test", source=DevSessionSource.CLI,
        )
        await manager.transition(session.id, DevSessionState.PLANNING)
        await manager.transition(session.id, DevSessionState.PROPOSED)
        await manager.approve_session(session.id)

        # Execute
        # Validate fails
        session = await manager.transition(session.id, DevSessionState.VALIDATING)
        session = await manager.transition(session.id, DevSessionState.FAILED)

        # Retry back to executing
        loaded = await manager.get_session(session.id)
        assert loaded.can_retry()
        session = await manager.transition(session.id, DevSessionState.EXECUTING)
        assert session.state == DevSessionState.EXECUTING

    @pytest.mark.asyncio
    async def test_cancel_at_any_state(self, manager):
        """Sessions can be cancelled from any state."""
        session = await manager.create_session(
            title="Cancel test", description="Test", source=DevSessionSource.CLI,
        )
        await manager.transition(session.id, DevSessionState.PLANNING)
        cancelled = await manager.cancel_session(session.id)
        assert cancelled.state == DevSessionState.CANCELLED
```

- [ ] **Step 2: Run integration tests**

Run: `python -m pytest tests/test_dev_integration.py -v`
Expected: All tests PASS

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=60`
Expected: All existing tests still pass + new dev tests pass

- [ ] **Step 4: Commit**

```bash
git add tests/test_dev_integration.py
git commit -m "test(dev): add integration test for full session lifecycle"
```

---

## Deferred Tasks (Phase 2)

These tasks are designed in the spec but should be implemented after the core system (Tasks 1-14) is working:

### Phase 2A: Researcher + Validator Agents
- `hestia/dev/researcher.py` — Gemini-based deep analysis agent
- `hestia/dev/validator.py` — Haiku-based test/lint background monitor
- Background discovery scheduler (`hestia/dev/discovery.py`)

### Phase 2B: Proposal Delivery
- `hestia/dev/proposal.py` — GitHub issue creation + macOS notification delivery
- macOS Command tab `ProposalCardView` in `Shared/Views/Command/`
- Briefing integration with `hestia/proactive/`

### Phase 2C: Full Orchestration Loop
- Wire Architect → Engineer → Validator flow into DevSessionManager
- Background execution via asyncio tasks
- Session branch management (auto-create, auto-cleanup)
- Compensating actions on cancel (delete remote branch, close PR)

### Phase 2D: CLI Streaming
- Wire `/dev <task>` to stream session progress in real-time
- Show tool calls, test results, state transitions live in terminal

---

## Summary

| Task | Scope | Est. Time |
|------|-------|-----------|
| 1. Models & Enums | State machine, data models | ~30 min |
| 2. Database Layer | SQLite persistence | ~45 min |
| 3. Safety Module | Authority matrix, budgets | ~30 min |
| 4. Context Builder | Per-tier context assembly | ~45 min |
| 5. Memory Bridge | 4 memory types store/retrieve | ~30 min |
| 6. Cloud Models | Add Opus 4 + Haiku 4.5 | ~15 min |
| 7. Tool Definitions | run_tests, git_push, etc. | ~45 min |
| 8. Session Manager | Lifecycle orchestration | ~45 min |
| 9. Architect Agent | Planning + review (Opus) | ~45 min |
| 10. Engineer Agent | Tool loop execution (Sonnet) | ~45 min |
| 11. API Routes | Session CRUD + approval | ~45 min |
| 12. CLI Commands | /dev command family | ~30 min |
| 13. auto-test.sh | Test mappings | ~5 min |
| 14. Integration Test | Full lifecycle validation | ~30 min |
| **Total Phase 1** | | **~7.5 hours** |
