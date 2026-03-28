import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from hestia.dev.orchestrator import DevOrchestrator
from hestia.dev.models import DevSession, DevSessionState, DevSessionSource, DevComplexity, AgentTier


@pytest.fixture
def mock_manager():
    m = AsyncMock()
    session = DevSession.create(title="Fix bug", description="Fix it", source=DevSessionSource.CLI)
    session.plan = {"steps": ["edit"], "files": ["file.py"], "subtasks": [{"title": "Edit file", "files": ["file.py"]}], "complexity": "simple", "risk": "low"}
    session.subtasks = session.plan["subtasks"]

    m.get_session = AsyncMock(return_value=session)
    m.transition = AsyncMock(side_effect=lambda sid, state: _update_state(session, state))
    m.record_event = AsyncMock()
    m.cancel_session = AsyncMock(return_value=session)
    m._db = AsyncMock()
    m._db.update_session = AsyncMock()
    return m, session


def _update_state(session, state):
    session.state = state
    return session


@pytest.fixture
def mock_architect():
    a = AsyncMock()
    a.create_plan = AsyncMock(return_value={
        "steps": ["edit file"], "files": ["file.py"], "risk": "low",
        "estimated_minutes": 10, "complexity": "simple",
        "subtasks": [{"title": "Edit file", "files": ["file.py"]}],
    })
    a.review_diff = AsyncMock(return_value={"approved": True, "feedback": "Looks good", "issues": []})
    return a


@pytest.fixture
def mock_engineer():
    e = AsyncMock()
    e.execute_subtask = AsyncMock(return_value={
        "content": "Done", "tokens_used": 500, "iterations": 2, "files_affected": ["file.py"],
    })
    return e


@pytest.fixture
def mock_validator():
    v = AsyncMock()
    v.validate_session = AsyncMock(return_value={"passed": True, "test_result": {"passed": True}, "lint_result": {"errors": []}, "ai_analysis": None})
    return v


@pytest.fixture
def orchestrator(mock_manager, mock_architect, mock_engineer, mock_validator):
    mgr, session = mock_manager
    return DevOrchestrator(
        manager=mgr, architect=mock_architect, engineer=mock_engineer,
        validator=mock_validator,
    )


class TestPlanningPhase:
    @pytest.mark.asyncio
    async def test_planning_creates_plan(self, orchestrator, mock_manager, mock_architect):
        mgr, session = mock_manager
        with patch.object(orchestrator, "_create_branch"):
            result = await orchestrator.run_planning_phase(session.id)
        mock_architect.create_plan.assert_called_once()
        mgr.transition.assert_any_call(session.id, DevSessionState.PLANNING)
        mgr.transition.assert_any_call(session.id, DevSessionState.PROPOSED)

    @pytest.mark.asyncio
    async def test_planning_invokes_researcher_for_complex(self, mock_manager, mock_architect, mock_engineer, mock_validator):
        mgr, session = mock_manager
        mock_architect.create_plan = AsyncMock(return_value={
            "steps": [], "files": [], "complexity": "complex", "subtasks": [], "risk": "high",
        })
        researcher = AsyncMock()
        researcher.analyze = AsyncMock(return_value={"findings": "Deep insight", "tokens_used": 1000})

        orch = DevOrchestrator(manager=mgr, architect=mock_architect, engineer=mock_engineer, validator=mock_validator, researcher=researcher)
        with patch.object(orch, "_create_branch"):
            await orch.run_planning_phase(session.id)
        researcher.analyze.assert_called_once()
        assert mock_architect.create_plan.call_count == 2  # Initial + post-research


class TestExecutionPhase:
    @pytest.mark.asyncio
    async def test_full_execution_to_complete(self, orchestrator, mock_manager):
        mgr, session = mock_manager
        session.state = DevSessionState.EXECUTING
        session.branch_name = "hestia/dev-test"

        events = []
        with patch.object(orchestrator, "_checkout_branch"):
            with patch.object(orchestrator, "_get_diff", return_value="+new"):
                async for event in orchestrator.run_execution_phase(session.id):
                    events.append(event)

        event_types = [e["type"] for e in events]
        assert "subtask_start" in event_types
        assert "subtask_result" in event_types
        assert "validation" in event_types
        assert "review" in event_types
        # Should reach complete
        state_changes = [e for e in events if e["type"] == "state_change"]
        final_states = [e["state"] for e in state_changes]
        assert "complete" in final_states

    @pytest.mark.asyncio
    async def test_execution_fails_on_validation(self, mock_manager, mock_architect, mock_engineer):
        mgr, session = mock_manager
        session.state = DevSessionState.EXECUTING
        session.branch_name = "hestia/dev-test"

        validator = AsyncMock()
        validator.validate_session = AsyncMock(return_value={"passed": False, "test_result": {"passed": False}})

        orch = DevOrchestrator(manager=mgr, architect=mock_architect, engineer=mock_engineer, validator=validator)
        events = []
        with patch.object(orch, "_checkout_branch"):
            with patch.object(orch, "_get_diff", return_value="+changed code"):
                async for event in orch.run_execution_phase(session.id):
                    events.append(event)

        final_states = [e["state"] for e in events if e["type"] == "state_change"]
        assert "failed" in final_states


class TestCancelSession:
    @pytest.mark.asyncio
    async def test_cancel_with_compensating_actions(self, orchestrator, mock_manager):
        mgr, session = mock_manager
        session.branch_name = "hestia/dev-test"

        with patch.object(orchestrator, "_delete_remote_branch") as mock_delete:
            await orchestrator.cancel_session(session.id)
            mock_delete.assert_called_once_with("hestia/dev-test")
