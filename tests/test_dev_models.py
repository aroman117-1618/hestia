"""Tests for hestia.dev.models — enums, dataclasses, and state machine."""
from __future__ import annotations

import pytest

from hestia.dev.models import (
    AgentTier,
    ApprovalType,
    DevComplexity,
    DevEvent,
    DevEventType,
    DevPriority,
    DevSession,
    DevSessionSource,
    DevSessionState,
    Proposal,
    VALID_TRANSITIONS,
)


# ---------------------------------------------------------------------------
# TestDevSessionState
# ---------------------------------------------------------------------------

class TestDevSessionState:
    def test_all_states_defined(self) -> None:
        expected = {
            "queued", "planning", "researching", "proposed",
            "executing", "validating", "reviewing",
            "complete", "failed", "blocked", "cancelled",
        }
        actual = {s.value for s in DevSessionState}
        assert actual == expected

    def test_pre_approval_states(self) -> None:
        pre = DevSessionState.pre_approval_states()
        assert DevSessionState.QUEUED in pre
        assert DevSessionState.PLANNING in pre
        assert DevSessionState.RESEARCHING in pre
        assert DevSessionState.PROPOSED in pre
        # Post-approval states must NOT appear
        assert DevSessionState.EXECUTING not in pre
        assert DevSessionState.COMPLETE not in pre

    def test_post_approval_states(self) -> None:
        post = DevSessionState.post_approval_states()
        assert DevSessionState.EXECUTING in post
        assert DevSessionState.VALIDATING in post
        assert DevSessionState.REVIEWING in post
        assert DevSessionState.COMPLETE in post
        assert DevSessionState.FAILED in post
        assert DevSessionState.BLOCKED in post
        assert DevSessionState.CANCELLED in post
        # Pre-approval states must NOT appear
        assert DevSessionState.QUEUED not in post
        assert DevSessionState.PROPOSED not in post

    def test_pre_and_post_are_disjoint(self) -> None:
        pre = set(DevSessionState.pre_approval_states())
        post = set(DevSessionState.post_approval_states())
        assert pre.isdisjoint(post)

    def test_all_states_covered_by_valid_transitions(self) -> None:
        """Every state must have an entry in VALID_TRANSITIONS."""
        for state in DevSessionState:
            assert state in VALID_TRANSITIONS, f"Missing transition entry for {state}"

    def test_terminal_states_have_no_outgoing_transitions(self) -> None:
        assert VALID_TRANSITIONS[DevSessionState.COMPLETE] == []
        assert VALID_TRANSITIONS[DevSessionState.CANCELLED] == []


# ---------------------------------------------------------------------------
# TestDevSession
# ---------------------------------------------------------------------------

class TestDevSession:
    def _make_session(self, **kwargs: object) -> DevSession:
        defaults: dict = {
            "title": "Test session",
            "description": "A test dev session",
        }
        defaults.update(kwargs)
        return DevSession.create(**defaults)  # type: ignore[arg-type]

    def test_create_defaults(self) -> None:
        session = self._make_session()
        assert session.state == DevSessionState.QUEUED
        assert session.source == DevSessionSource.CLI
        assert session.complexity == DevComplexity.MEDIUM
        assert session.priority == DevPriority.NORMAL
        assert session.retry_count == 0
        assert session.replan_count == 0
        assert session.tokens_used == 0
        assert session.token_budget == 500_000
        assert session.id  # non-empty UUID

    def test_create_custom_fields(self) -> None:
        session = self._make_session(
            source=DevSessionSource.GITHUB,
            complexity=DevComplexity.CRITICAL,
            priority=DevPriority.HIGH,
            token_budget=100_000,
            metadata={"issue": 42},
        )
        assert session.source == DevSessionSource.GITHUB
        assert session.complexity == DevComplexity.CRITICAL
        assert session.priority == DevPriority.HIGH
        assert session.token_budget == 100_000
        assert session.metadata == {"issue": 42}

    def test_unique_ids(self) -> None:
        s1 = self._make_session()
        s2 = self._make_session()
        assert s1.id != s2.id

    def test_can_transition_valid(self) -> None:
        session = self._make_session()
        assert session.state == DevSessionState.QUEUED
        assert session.can_transition(DevSessionState.PLANNING)
        assert session.can_transition(DevSessionState.CANCELLED)

    def test_can_transition_invalid(self) -> None:
        session = self._make_session()
        assert not session.can_transition(DevSessionState.COMPLETE)
        assert not session.can_transition(DevSessionState.EXECUTING)
        assert not session.can_transition(DevSessionState.QUEUED)

    def test_transition_applies_state(self) -> None:
        session = self._make_session()
        session.transition(DevSessionState.PLANNING)
        assert session.state == DevSessionState.PLANNING

    def test_transition_invalid_raises(self) -> None:
        session = self._make_session()
        with pytest.raises(ValueError, match="Invalid transition"):
            session.transition(DevSessionState.COMPLETE)

    def test_transition_updates_updated_at(self) -> None:
        session = self._make_session()
        original = session.updated_at
        session.transition(DevSessionState.PLANNING)
        assert session.updated_at >= original

    def test_can_retry_when_failed_and_under_limit(self) -> None:
        session = self._make_session()
        session.state = DevSessionState.FAILED
        session.retry_count = 2
        assert session.can_retry()

    def test_cannot_retry_when_limit_reached(self) -> None:
        session = self._make_session()
        session.state = DevSessionState.FAILED
        session.retry_count = 3
        assert not session.can_retry()

    def test_cannot_retry_when_not_failed(self) -> None:
        session = self._make_session()
        assert not session.can_retry()

    def test_can_replan(self) -> None:
        session = self._make_session()
        assert session.can_replan()
        session.replan_count = 2
        assert not session.can_replan()

    def test_within_token_budget(self) -> None:
        session = self._make_session(token_budget=1000)
        assert session.within_token_budget()
        session.tokens_used = 999
        assert session.within_token_budget()
        session.tokens_used = 1000
        assert not session.within_token_budget()


# ---------------------------------------------------------------------------
# TestDevEvent
# ---------------------------------------------------------------------------

class TestDevEvent:
    def test_create(self) -> None:
        event = DevEvent.create(
            session_id="sess-abc",
            event_type=DevEventType.STATE_CHANGE,
            agent_tier=AgentTier.ARCHITECT,
            data={"from": "queued", "to": "planning"},
        )
        assert event.session_id == "sess-abc"
        assert event.event_type == DevEventType.STATE_CHANGE
        assert event.agent_tier == AgentTier.ARCHITECT
        assert event.data == {"from": "queued", "to": "planning"}
        assert event.id  # non-empty UUID

    def test_create_minimal(self) -> None:
        event = DevEvent.create(session_id="sess-xyz", event_type=DevEventType.ERROR)
        assert event.agent_tier is None
        assert event.data == {}

    def test_unique_ids(self) -> None:
        e1 = DevEvent.create(session_id="s", event_type=DevEventType.COMMIT)
        e2 = DevEvent.create(session_id="s", event_type=DevEventType.COMMIT)
        assert e1.id != e2.id

    def test_all_event_types_defined(self) -> None:
        expected = {
            "state_change", "plan_created", "subtask_started", "subtask_completed",
            "file_edited", "file_created", "test_run", "lint_run", "build_check",
            "commit", "review", "research", "approval_requested", "approval_granted",
            "approval_denied", "error", "token_budget_warning", "notification_sent",
        }
        actual = {e.value for e in DevEventType}
        assert actual == expected


# ---------------------------------------------------------------------------
# TestAgentTier
# ---------------------------------------------------------------------------

class TestAgentTier:
    def test_all_tiers_defined(self) -> None:
        expected = {"architect", "researcher", "engineer", "validator"}
        actual = {t.value for t in AgentTier}
        assert actual == expected

    def test_string_values(self) -> None:
        assert AgentTier.ARCHITECT == "architect"
        assert AgentTier.RESEARCHER == "researcher"
        assert AgentTier.ENGINEER == "engineer"
        assert AgentTier.VALIDATOR == "validator"


# ---------------------------------------------------------------------------
# TestProposal
# ---------------------------------------------------------------------------

class TestProposal:
    def test_from_session(self) -> None:
        session = DevSession.create(title="Proposal test", description="desc")
        proposal = Proposal.from_session(
            session=session,
            summary="Add X feature",
            steps=["Step 1", "Step 2"],
            affected_files=["hestia/x/models.py"],
            estimated_tokens=5000,
        )
        assert proposal.session_id == session.id
        assert proposal.summary == "Add X feature"
        assert proposal.steps == ["Step 1", "Step 2"]
        assert proposal.affected_files == ["hestia/x/models.py"]
        assert proposal.estimated_tokens == 5000
        assert proposal.approved is None  # pending
        assert proposal.approval_notes == ""

    def test_approval_type_values(self) -> None:
        expected = {"plan_approval", "protected_path", "git_push", "pr_create", "pr_merge"}
        actual = {a.value for a in ApprovalType}
        assert actual == expected
