"""Tests for DevDatabase — SQLite persistence for dev sessions and events."""
from __future__ import annotations

import pytest
import pytest_asyncio

from hestia.dev.database import DevDatabase
from hestia.dev.models import (
    AgentTier,
    DevComplexity,
    DevEvent,
    DevEventType,
    DevPriority,
    DevSession,
    DevSessionSource,
    DevSessionState,
)


@pytest_asyncio.fixture
async def db(tmp_path):
    database = DevDatabase(db_path=tmp_path / "test_dev.db")
    await database.connect()
    yield database
    await database.close()


def _make_session(**kwargs) -> DevSession:
    defaults = dict(
        title="Test session",
        description="A test dev session",
        source=DevSessionSource.CLI,
        priority=DevPriority.NORMAL,
    )
    defaults.update(kwargs)
    return DevSession.create(**defaults)


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_and_get_session(db: DevDatabase) -> None:
    session = _make_session(title="My first session")
    await db.save_session(session)

    fetched = await db.get_session(session.id)
    assert fetched is not None
    assert fetched.id == session.id
    assert fetched.title == "My first session"
    assert fetched.state == DevSessionState.QUEUED
    assert fetched.source == DevSessionSource.CLI
    assert fetched.priority == DevPriority.NORMAL
    assert fetched.complexity is None
    assert fetched.tokens_used == 0
    assert fetched.token_budget == 500_000
    assert fetched.retry_count == 0
    assert fetched.replan_count == 0
    assert fetched.metadata == {}


@pytest.mark.asyncio
async def test_save_and_get_session_new_fields(db: DevDatabase) -> None:
    """All new fields must round-trip correctly through the database."""
    session = _make_session(
        title="Full fields session",
        source_ref="issue-99",
        complexity=DevComplexity.COMPLEX,
        branch_name="feature/new-module",
        architect_model="claude-opus-custom",
        engineer_model="claude-sonnet-custom",
        researcher_model="gemini-custom",
        validator_model="claude-haiku-custom",
    )
    session.plan = {"steps": ["step1", "step2"], "files": ["foo.py"]}
    session.subtasks = [{"id": "t1", "name": "Do X"}, {"id": "t2", "name": "Do Y"}]
    session.current_subtask = 1
    session.total_tokens = 12345
    session.total_cost_usd = 0.42
    session.error_log = "some error"
    session.started_at = "2026-01-01T10:00:00+00:00"
    session.approved_at = "2026-01-01T11:00:00+00:00"
    session.approved_by = "andrew"

    await db.save_session(session)
    fetched = await db.get_session(session.id)

    assert fetched is not None
    assert fetched.source_ref == "issue-99"
    assert fetched.complexity == DevComplexity.COMPLEX
    assert fetched.branch_name == "feature/new-module"
    assert fetched.architect_model == "claude-opus-custom"
    assert fetched.engineer_model == "claude-sonnet-custom"
    assert fetched.researcher_model == "gemini-custom"
    assert fetched.validator_model == "claude-haiku-custom"
    assert fetched.plan == {"steps": ["step1", "step2"], "files": ["foo.py"]}
    assert fetched.subtasks == [{"id": "t1", "name": "Do X"}, {"id": "t2", "name": "Do Y"}]
    assert fetched.current_subtask == 1
    assert fetched.total_tokens == 12345
    assert fetched.total_cost_usd == pytest.approx(0.42)
    assert fetched.error_log == "some error"
    assert fetched.started_at == "2026-01-01T10:00:00+00:00"
    assert fetched.approved_at == "2026-01-01T11:00:00+00:00"
    assert fetched.approved_by == "andrew"


@pytest.mark.asyncio
async def test_plan_and_subtasks_null_by_default(db: DevDatabase) -> None:
    """plan and subtasks are None by default and survive a round-trip as None."""
    session = _make_session()
    await db.save_session(session)
    fetched = await db.get_session(session.id)
    assert fetched is not None
    assert fetched.plan is None
    assert fetched.subtasks is None


@pytest.mark.asyncio
async def test_timestamps_are_strings(db: DevDatabase) -> None:
    """Timestamps stored and retrieved as ISO strings, not datetime objects."""
    session = _make_session()
    await db.save_session(session)
    fetched = await db.get_session(session.id)
    assert fetched is not None
    assert isinstance(fetched.created_at, str)
    assert isinstance(fetched.updated_at, str)
    assert "T" in fetched.created_at


@pytest.mark.asyncio
async def test_update_session_state(db: DevDatabase) -> None:
    session = _make_session()
    await db.save_session(session)

    session.transition(DevSessionState.PLANNING)
    session.tokens_used = 1500
    await db.update_session(session)

    fetched = await db.get_session(session.id)
    assert fetched is not None
    assert fetched.state == DevSessionState.PLANNING
    assert fetched.tokens_used == 1500


@pytest.mark.asyncio
async def test_update_session_metadata(db: DevDatabase) -> None:
    session = _make_session()
    await db.save_session(session)

    session.metadata = {"branch": "feature/foo", "pr_number": 42}
    await db.update_session(session)

    fetched = await db.get_session(session.id)
    assert fetched is not None
    assert fetched.metadata == {"branch": "feature/foo", "pr_number": 42}


@pytest.mark.asyncio
async def test_update_session_plan_and_subtasks(db: DevDatabase) -> None:
    session = _make_session()
    await db.save_session(session)

    session.plan = {"approach": "incremental"}
    session.subtasks = [{"id": "st1", "done": False}]
    session.current_subtask = 0
    await db.update_session(session)

    fetched = await db.get_session(session.id)
    assert fetched is not None
    assert fetched.plan == {"approach": "incremental"}
    assert fetched.subtasks == [{"id": "st1", "done": False}]
    assert fetched.current_subtask == 0


@pytest.mark.asyncio
async def test_session_not_found_returns_none(db: DevDatabase) -> None:
    result = await db.get_session("does-not-exist")
    assert result is None


# ---------------------------------------------------------------------------
# list_sessions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_sessions_no_filter(db: DevDatabase) -> None:
    s1 = _make_session(title="Session A")
    s2 = _make_session(title="Session B")
    await db.save_session(s1)
    await db.save_session(s2)

    sessions = await db.list_sessions()
    assert len(sessions) == 2
    ids = {s.id for s in sessions}
    assert s1.id in ids
    assert s2.id in ids


@pytest.mark.asyncio
async def test_list_sessions_by_state(db: DevDatabase) -> None:
    queued = _make_session(title="Queued")
    planning = _make_session(title="Planning")
    await db.save_session(queued)
    await db.save_session(planning)

    planning.transition(DevSessionState.PLANNING)
    await db.update_session(planning)

    queued_sessions = await db.list_sessions(state=DevSessionState.QUEUED)
    assert len(queued_sessions) == 1
    assert queued_sessions[0].id == queued.id

    planning_sessions = await db.list_sessions(state=DevSessionState.PLANNING)
    assert len(planning_sessions) == 1
    assert planning_sessions[0].id == planning.id


@pytest.mark.asyncio
async def test_list_sessions_limit(db: DevDatabase) -> None:
    for i in range(5):
        await db.save_session(_make_session(title=f"Session {i}"))

    sessions = await db.list_sessions(limit=3)
    assert len(sessions) == 3


# ---------------------------------------------------------------------------
# get_pending_proposals
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_pending_proposals(db: DevDatabase) -> None:
    # One session that reaches PROPOSED
    proposed = _make_session(title="Proposed session")
    await db.save_session(proposed)
    proposed.transition(DevSessionState.PLANNING)
    proposed.transition(DevSessionState.PROPOSED)
    await db.update_session(proposed)

    # One session that stays QUEUED
    queued = _make_session(title="Still queued")
    await db.save_session(queued)

    proposals = await db.get_pending_proposals()
    assert len(proposals) == 1
    assert proposals[0].id == proposed.id
    assert proposals[0].state == DevSessionState.PROPOSED


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_and_list_events(db: DevDatabase) -> None:
    session = _make_session()
    await db.save_session(session)

    event = DevEvent.create(
        session_id=session.id,
        event_type=DevEventType.STATE_CHANGE,
        agent_tier=AgentTier.ARCHITECT,
        data={"from": "queued", "to": "planning"},
    )
    event_id = await db.save_event(event)
    assert event_id == event.id

    events = await db.list_events(session.id)
    assert len(events) == 1
    e = events[0]
    assert e.id == event.id
    assert e.session_id == session.id
    assert e.event_type == DevEventType.STATE_CHANGE
    assert e.agent_tier == AgentTier.ARCHITECT
    assert e.data == {"from": "queued", "to": "planning"}


@pytest.mark.asyncio
async def test_event_timestamp_is_string(db: DevDatabase) -> None:
    session = _make_session()
    await db.save_session(session)
    event = DevEvent.create(session_id=session.id, event_type=DevEventType.COMMIT)
    await db.save_event(event)
    events = await db.list_events(session.id)
    assert isinstance(events[0].timestamp, str)


@pytest.mark.asyncio
async def test_list_events_filtered_by_type(db: DevDatabase) -> None:
    session = _make_session()
    await db.save_session(session)

    await db.save_event(DevEvent.create(session.id, DevEventType.STATE_CHANGE))
    await db.save_event(DevEvent.create(session.id, DevEventType.FILE_EDITED, data={"file": "foo.py"}))
    await db.save_event(DevEvent.create(session.id, DevEventType.FILE_EDITED, data={"file": "bar.py"}))

    all_events = await db.list_events(session.id)
    assert len(all_events) == 3

    file_events = await db.list_events(session.id, event_type=DevEventType.FILE_EDITED)
    assert len(file_events) == 2
    assert all(e.event_type == DevEventType.FILE_EDITED for e in file_events)


@pytest.mark.asyncio
async def test_list_events_no_agent_tier(db: DevDatabase) -> None:
    session = _make_session()
    await db.save_session(session)

    event = DevEvent.create(
        session_id=session.id,
        event_type=DevEventType.NOTIFICATION_SENT,
        agent_tier=None,
    )
    await db.save_event(event)

    events = await db.list_events(session.id)
    assert len(events) == 1
    assert events[0].agent_tier is None


@pytest.mark.asyncio
async def test_events_isolated_by_session(db: DevDatabase) -> None:
    s1 = _make_session(title="Session 1")
    s2 = _make_session(title="Session 2")
    await db.save_session(s1)
    await db.save_session(s2)

    await db.save_event(DevEvent.create(s1.id, DevEventType.PLAN_CREATED))
    await db.save_event(DevEvent.create(s2.id, DevEventType.COMMIT))

    s1_events = await db.list_events(s1.id)
    s2_events = await db.list_events(s2.id)
    assert len(s1_events) == 1
    assert len(s2_events) == 1
    assert s1_events[0].event_type == DevEventType.PLAN_CREATED
    assert s2_events[0].event_type == DevEventType.COMMIT
