"""Tests for DevSessionManager — session lifecycle orchestrator."""
from __future__ import annotations

import pytest
import pytest_asyncio

from hestia.dev.manager import DevSessionManager
from hestia.dev.models import (
    AgentTier,
    DevEventType,
    DevPriority,
    DevSessionSource,
    DevSessionState,
)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def manager(tmp_path):
    m = DevSessionManager(db_path=tmp_path / "test_dev.db")
    await m.initialize()
    yield m
    await m.shutdown()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_session(manager: DevSessionManager, **kwargs):
    defaults = dict(
        title="Test Session",
        description="A test session",
        source=DevSessionSource.CLI,
    )
    defaults.update(kwargs)
    return await manager.create_session(**defaults)


# ---------------------------------------------------------------------------
# create_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_session_returns_queued_session(manager):
    session = await _make_session(manager)

    assert session.id.startswith("dev-")
    assert session.state == DevSessionState.QUEUED
    assert session.title == "Test Session"
    assert session.description == "A test session"
    assert session.source == DevSessionSource.CLI
    assert session.created_at
    assert session.updated_at


@pytest.mark.asyncio
async def test_create_session_with_priority(manager):
    session = await _make_session(manager, priority=DevPriority.HIGH)
    assert session.priority == DevPriority.HIGH


# ---------------------------------------------------------------------------
# get_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_session_returns_created_session(manager):
    created = await _make_session(manager)
    fetched = await manager.get_session(created.id)

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.title == created.title
    assert fetched.state == DevSessionState.QUEUED


@pytest.mark.asyncio
async def test_get_session_returns_none_for_unknown(manager):
    result = await manager.get_session("dev-doesnotexist")
    assert result is None


# ---------------------------------------------------------------------------
# transition
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transition_valid_queued_to_planning(manager):
    session = await _make_session(manager)
    updated = await manager.transition(session.id, DevSessionState.PLANNING)

    assert updated.state == DevSessionState.PLANNING
    # Persisted state should also be updated
    fetched = await manager.get_session(session.id)
    assert fetched.state == DevSessionState.PLANNING


@pytest.mark.asyncio
async def test_transition_invalid_raises_value_error(manager):
    session = await _make_session(manager)
    # QUEUED -> COMPLETE is not a valid transition
    with pytest.raises(ValueError, match="Invalid transition"):
        await manager.transition(session.id, DevSessionState.COMPLETE)


@pytest.mark.asyncio
async def test_transition_sets_started_at_on_executing(manager):
    session = await _make_session(manager)
    # Move through QUEUED -> PLANNING -> PROPOSED -> EXECUTING
    await manager.transition(session.id, DevSessionState.PLANNING)
    await manager.transition(session.id, DevSessionState.PROPOSED)
    updated = await manager.transition(session.id, DevSessionState.EXECUTING)

    assert updated.started_at is not None


@pytest.mark.asyncio
async def test_transition_sets_completed_at_on_cancelled(manager):
    session = await _make_session(manager)
    updated = await manager.transition(session.id, DevSessionState.CANCELLED)

    assert updated.completed_at is not None


@pytest.mark.asyncio
async def test_transition_unknown_session_raises_value_error(manager):
    with pytest.raises(ValueError, match="Session not found"):
        await manager.transition("dev-nonexistent", DevSessionState.PLANNING)


@pytest.mark.asyncio
async def test_transition_logs_state_change_event(manager):
    session = await _make_session(manager)
    await manager.transition(session.id, DevSessionState.PLANNING)

    events = await manager.get_events(session.id, event_type=DevEventType.STATE_CHANGE)
    assert len(events) == 1
    assert events[0].data["from"] == DevSessionState.QUEUED.value
    assert events[0].data["to"] == DevSessionState.PLANNING.value


# ---------------------------------------------------------------------------
# approve_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_session_from_proposed(manager):
    session = await _make_session(manager)
    await manager.transition(session.id, DevSessionState.PLANNING)
    await manager.transition(session.id, DevSessionState.PROPOSED)

    approved = await manager.approve_session(session.id, approved_by="andrew")

    assert approved.state == DevSessionState.EXECUTING
    assert approved.approved_by == "andrew"
    assert approved.approved_at is not None
    assert approved.started_at is not None


@pytest.mark.asyncio
async def test_approve_session_from_non_proposed_raises(manager):
    session = await _make_session(manager)
    # Still in QUEUED state
    with pytest.raises(ValueError, match="PROPOSED"):
        await manager.approve_session(session.id)


@pytest.mark.asyncio
async def test_approve_session_logs_approval_granted_event(manager):
    session = await _make_session(manager)
    await manager.transition(session.id, DevSessionState.PLANNING)
    await manager.transition(session.id, DevSessionState.PROPOSED)
    await manager.approve_session(session.id, approved_by="andrew")

    events = await manager.get_events(session.id, event_type=DevEventType.APPROVAL_GRANTED)
    assert len(events) == 1
    assert events[0].data["approved_by"] == "andrew"


# ---------------------------------------------------------------------------
# cancel_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_session_from_queued(manager):
    session = await _make_session(manager)
    cancelled = await manager.cancel_session(session.id)

    assert cancelled.state == DevSessionState.CANCELLED
    assert cancelled.completed_at is not None


@pytest.mark.asyncio
async def test_cancel_session_from_planning(manager):
    session = await _make_session(manager)
    await manager.transition(session.id, DevSessionState.PLANNING)
    cancelled = await manager.cancel_session(session.id)

    assert cancelled.state == DevSessionState.CANCELLED


@pytest.mark.asyncio
async def test_cancel_session_from_proposed(manager):
    session = await _make_session(manager)
    await manager.transition(session.id, DevSessionState.PLANNING)
    await manager.transition(session.id, DevSessionState.PROPOSED)
    cancelled = await manager.cancel_session(session.id)

    assert cancelled.state == DevSessionState.CANCELLED


# ---------------------------------------------------------------------------
# list_sessions / list_pending_proposals
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_sessions_returns_all(manager):
    await _make_session(manager, title="Session A")
    await _make_session(manager, title="Session B")

    sessions = await manager.list_sessions()
    assert len(sessions) == 2


@pytest.mark.asyncio
async def test_list_sessions_filtered_by_state(manager):
    s1 = await _make_session(manager, title="Will Plan")
    s2 = await _make_session(manager, title="Stays Queued")

    await manager.transition(s1.id, DevSessionState.PLANNING)

    planning = await manager.list_sessions(state=DevSessionState.PLANNING)
    queued = await manager.list_sessions(state=DevSessionState.QUEUED)

    assert len(planning) == 1
    assert planning[0].id == s1.id

    assert len(queued) == 1
    assert queued[0].id == s2.id


@pytest.mark.asyncio
async def test_list_pending_proposals_returns_only_proposed(manager):
    s1 = await _make_session(manager, title="Proposed")
    s2 = await _make_session(manager, title="Still Queued")

    await manager.transition(s1.id, DevSessionState.PLANNING)
    await manager.transition(s1.id, DevSessionState.PROPOSED)

    proposals = await manager.list_pending_proposals()
    assert len(proposals) == 1
    assert proposals[0].id == s1.id


# ---------------------------------------------------------------------------
# record_event / get_events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_and_get_events_roundtrip(manager):
    session = await _make_session(manager)

    await manager.record_event(
        session_id=session.id,
        agent=AgentTier.ENGINEER,
        event_type=DevEventType.FILE_EDITED,
        detail="Edited hestia/dev/manager.py",
        tokens_used=1200,
        model="claude-sonnet-4-20250514",
        files_affected=["hestia/dev/manager.py"],
    )

    events = await manager.get_events(session.id)
    # 1 manual event (no state change event yet)
    file_events = [e for e in events if e.event_type == DevEventType.FILE_EDITED]
    assert len(file_events) == 1

    ev = file_events[0]
    assert ev.session_id == session.id
    assert ev.agent_tier == AgentTier.ENGINEER
    assert ev.data["detail"] == "Edited hestia/dev/manager.py"
    assert ev.data["tokens_used"] == 1200
    assert ev.data["model"] == "claude-sonnet-4-20250514"
    assert ev.data["files_affected"] == ["hestia/dev/manager.py"]


@pytest.mark.asyncio
async def test_get_events_filtered_by_type(manager):
    session = await _make_session(manager)

    await manager.record_event(
        session_id=session.id,
        agent=AgentTier.VALIDATOR,
        event_type=DevEventType.TEST_RUN,
        detail="All 42 tests passed",
    )
    await manager.record_event(
        session_id=session.id,
        agent=AgentTier.ENGINEER,
        event_type=DevEventType.COMMIT,
        detail="feat: add manager",
    )

    test_events = await manager.get_events(session.id, event_type=DevEventType.TEST_RUN)
    assert len(test_events) == 1
    assert test_events[0].data["detail"] == "All 42 tests passed"

    commit_events = await manager.get_events(session.id, event_type=DevEventType.COMMIT)
    assert len(commit_events) == 1


@pytest.mark.asyncio
async def test_get_events_returns_empty_for_unknown_session(manager):
    events = await manager.get_events("dev-nonexistent")
    assert events == []
