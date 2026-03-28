"""Integration test — full dev session lifecycle."""
import pytest
import pytest_asyncio
from hestia.dev.models import DevSessionState, DevSessionSource, AgentTier, DevEventType
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
        # Create
        session = await manager.create_session(title="Fix bug", description="Fix it", source=DevSessionSource.CLI)
        assert session.state == DevSessionState.QUEUED

        # Plan
        session = await manager.transition(session.id, DevSessionState.PLANNING)
        assert session.state == DevSessionState.PLANNING

        # Record plan
        await manager.record_event(session.id, AgentTier.ARCHITECT, DevEventType.PLAN_CREATED, {"steps": ["edit"]})

        # Propose
        session = await manager.transition(session.id, DevSessionState.PROPOSED)

        # Approve
        session = await manager.approve_session(session.id, approved_by="andrew")
        assert session.state == DevSessionState.EXECUTING
        assert session.approved_by == "andrew"

        # Execute → Validate
        await manager.record_event(session.id, AgentTier.ENGINEER, DevEventType.FILE_EDITED, {"path": "file.py"}, files_affected=["file.py"])
        session = await manager.transition(session.id, DevSessionState.VALIDATING)

        # Validate → Review
        await manager.record_event(session.id, AgentTier.VALIDATOR, DevEventType.TEST_RUN, {"passed": True})
        session = await manager.transition(session.id, DevSessionState.REVIEWING)

        # Review → Complete
        await manager.record_event(session.id, AgentTier.ARCHITECT, DevEventType.REVIEW, {"approved": True})
        session = await manager.transition(session.id, DevSessionState.COMPLETE)
        assert session.state == DevSessionState.COMPLETE
        assert session.completed_at is not None

        # Verify audit trail
        events = await manager.get_events(session.id)
        event_types = [e.event_type for e in events]
        assert DevEventType.PLAN_CREATED in event_types
        assert DevEventType.FILE_EDITED in event_types
        assert DevEventType.TEST_RUN in event_types

    @pytest.mark.asyncio
    async def test_failure_and_retry(self, manager):
        session = await manager.create_session(title="Retry test", description="Test", source=DevSessionSource.CLI)
        await manager.transition(session.id, DevSessionState.PLANNING)
        await manager.transition(session.id, DevSessionState.PROPOSED)
        await manager.approve_session(session.id)

        # Fail
        session = await manager.transition(session.id, DevSessionState.VALIDATING)
        session = await manager.transition(session.id, DevSessionState.FAILED)
        assert session.state == DevSessionState.FAILED

        # Retry
        session = await manager.transition(session.id, DevSessionState.PLANNING)
        assert session.state == DevSessionState.PLANNING

    @pytest.mark.asyncio
    async def test_cancel_from_proposed(self, manager):
        session = await manager.create_session(title="Cancel test", description="Test", source=DevSessionSource.CLI)
        await manager.transition(session.id, DevSessionState.PLANNING)
        await manager.transition(session.id, DevSessionState.PROPOSED)
        session = await manager.cancel_session(session.id)
        assert session.state == DevSessionState.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_from_executing(self, manager):
        session = await manager.create_session(title="Cancel exec", description="Test", source=DevSessionSource.CLI)
        await manager.transition(session.id, DevSessionState.PLANNING)
        await manager.transition(session.id, DevSessionState.PROPOSED)
        await manager.approve_session(session.id)
        session = await manager.cancel_session(session.id)
        assert session.state == DevSessionState.CANCELLED
