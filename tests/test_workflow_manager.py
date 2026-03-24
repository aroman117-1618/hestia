"""Tests for workflow manager — CRUD, lifecycle, execution, edge validation."""

from pathlib import Path

import pytest
import pytest_asyncio

from hestia.workflows.database import WorkflowDatabase
from hestia.workflows.event_bus import WorkflowEventBus
from hestia.workflows.executor import DAGExecutor
from hestia.workflows.manager import WorkflowManager
from hestia.workflows.models import (
    NodeType,
    RunStatus,
    TriggerType,
    WorkflowStatus,
)


@pytest_asyncio.fixture
async def manager(tmp_path: Path):
    """Create a fresh workflow manager with in-memory database."""
    db = WorkflowDatabase(tmp_path / "test_wf_mgr.db")
    await db.connect()
    event_bus = WorkflowEventBus()
    executor = DAGExecutor(event_bus=event_bus, node_timeout=5)
    mgr = WorkflowManager(database=db, executor=executor, event_bus=event_bus)
    yield mgr
    await db.close()


# ── Workflow CRUD ────────────────────────────────────────────────────


class TestWorkflowCRUD:
    @pytest.mark.asyncio
    async def test_create_workflow(self, manager: WorkflowManager) -> None:
        wf = await manager.create_workflow(name="Morning Brief", description="Daily summary")
        assert wf.id.startswith("wf-")
        assert wf.name == "Morning Brief"
        assert wf.status == WorkflowStatus.DRAFT

    @pytest.mark.asyncio
    async def test_create_with_schedule(self, manager: WorkflowManager) -> None:
        wf = await manager.create_workflow(
            name="Hourly Check",
            trigger_type="schedule",
            trigger_config={"cron": "0 * * * *"},
        )
        assert wf.trigger_type == TriggerType.SCHEDULE
        assert wf.trigger_config["cron"] == "0 * * * *"

    @pytest.mark.asyncio
    async def test_create_invalid_raises(self, manager: WorkflowManager) -> None:
        with pytest.raises(ValueError, match="name"):
            await manager.create_workflow(name="")

    @pytest.mark.asyncio
    async def test_get_workflow(self, manager: WorkflowManager) -> None:
        wf = await manager.create_workflow(name="Test")
        loaded = await manager.get_workflow(wf.id)
        assert loaded is not None
        assert loaded.name == "Test"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, manager: WorkflowManager) -> None:
        assert await manager.get_workflow("nonexistent") is None

    @pytest.mark.asyncio
    async def test_update_workflow(self, manager: WorkflowManager) -> None:
        wf = await manager.create_workflow(name="Original")
        updated = await manager.update_workflow(wf.id, name="Renamed", description="New desc")
        assert updated.name == "Renamed"
        assert updated.description == "New desc"

    @pytest.mark.asyncio
    async def test_update_active_raises(self, manager: WorkflowManager) -> None:
        wf = await manager.create_workflow(name="Test")
        await manager.add_node(wf.id, "log", "Step 1", {"message": "hi"})
        await manager.activate(wf.id)
        with pytest.raises(ValueError, match="active"):
            await manager.update_workflow(wf.id, name="Nope")

    @pytest.mark.asyncio
    async def test_delete_workflow(self, manager: WorkflowManager) -> None:
        wf = await manager.create_workflow(name="To Delete")
        assert await manager.delete_workflow(wf.id) is True
        assert await manager.get_workflow(wf.id) is None

    @pytest.mark.asyncio
    async def test_list_workflows(self, manager: WorkflowManager) -> None:
        await manager.create_workflow(name="A")
        await manager.create_workflow(name="B")
        workflows, total = await manager.list_workflows()
        assert total == 2
        assert len(workflows) == 2

    @pytest.mark.asyncio
    async def test_get_workflow_detail(self, manager: WorkflowManager) -> None:
        wf = await manager.create_workflow(name="Detail Test")
        await manager.add_node(wf.id, "log", "Node 1", {"message": "hi"})
        detail = await manager.get_workflow_detail(wf.id)
        assert detail is not None
        assert len(detail["nodes"]) == 1
        assert detail["name"] == "Detail Test"


# ── Node CRUD ────────────────────────────────────────────────────────


class TestNodeCRUD:
    @pytest.mark.asyncio
    async def test_add_node(self, manager: WorkflowManager) -> None:
        wf = await manager.create_workflow(name="Test")
        node = await manager.add_node(
            wf.id, "run_prompt", "Ask Question", {"prompt": "What time is it?"}
        )
        assert node.id.startswith("node-")
        assert node.node_type == NodeType.RUN_PROMPT

    @pytest.mark.asyncio
    async def test_add_node_to_active_raises(self, manager: WorkflowManager) -> None:
        wf = await manager.create_workflow(name="Test")
        await manager.add_node(wf.id, "log", "Step", {"message": "hi"})
        await manager.activate(wf.id)
        with pytest.raises(ValueError, match="active"):
            await manager.add_node(wf.id, "log", "New", {"message": "nope"})

    @pytest.mark.asyncio
    async def test_add_invalid_node_raises(self, manager: WorkflowManager) -> None:
        wf = await manager.create_workflow(name="Test")
        with pytest.raises(ValueError, match="prompt"):
            await manager.add_node(wf.id, "run_prompt", "No Prompt", {})

    @pytest.mark.asyncio
    async def test_update_node(self, manager: WorkflowManager) -> None:
        wf = await manager.create_workflow(name="Test")
        node = await manager.add_node(wf.id, "log", "Original", {"message": "old"})
        updated = await manager.update_node(node.id, label="Updated", config={"message": "new"})
        assert updated.label == "Updated"
        assert updated.config["message"] == "new"

    @pytest.mark.asyncio
    async def test_delete_node(self, manager: WorkflowManager) -> None:
        wf = await manager.create_workflow(name="Test")
        node = await manager.add_node(wf.id, "log", "To Delete", {"message": "bye"})
        assert await manager.delete_node(node.id) is True


# ── Edge CRUD with Cycle Detection ───────────────────────────────────


class TestEdgeCRUD:
    @pytest.mark.asyncio
    async def test_add_edge(self, manager: WorkflowManager) -> None:
        wf = await manager.create_workflow(name="Test")
        n1 = await manager.add_node(wf.id, "manual", "Trigger")
        n2 = await manager.add_node(wf.id, "log", "Step", {"message": "hi"})
        edge = await manager.add_edge(wf.id, n1.id, n2.id)
        assert edge.source_node_id == n1.id
        assert edge.target_node_id == n2.id

    @pytest.mark.asyncio
    async def test_add_edge_creates_cycle_raises(self, manager: WorkflowManager) -> None:
        wf = await manager.create_workflow(name="Test")
        n1 = await manager.add_node(wf.id, "log", "A", {"message": "a"})
        n2 = await manager.add_node(wf.id, "log", "B", {"message": "b"})
        await manager.add_edge(wf.id, n1.id, n2.id)
        with pytest.raises(ValueError, match="cycle"):
            await manager.add_edge(wf.id, n2.id, n1.id)

    @pytest.mark.asyncio
    async def test_add_edge_with_label(self, manager: WorkflowManager) -> None:
        wf = await manager.create_workflow(name="Test")
        n1 = await manager.add_node(wf.id, "if_else", "Check",
                                     {"condition": {"field": "x", "operator": "is_true"}})
        n2 = await manager.add_node(wf.id, "log", "True Path", {"message": "yes"})
        edge = await manager.add_edge(wf.id, n1.id, n2.id, edge_label="true")
        assert edge.edge_label == "true"

    @pytest.mark.asyncio
    async def test_delete_edge(self, manager: WorkflowManager) -> None:
        wf = await manager.create_workflow(name="Test")
        n1 = await manager.add_node(wf.id, "log", "A", {"message": "a"})
        n2 = await manager.add_node(wf.id, "log", "B", {"message": "b"})
        edge = await manager.add_edge(wf.id, n1.id, n2.id)
        assert await manager.delete_edge(edge.id) is True


# ── Lifecycle ────────────────────────────────────────────────────────


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_activate(self, manager: WorkflowManager) -> None:
        wf = await manager.create_workflow(name="Test")
        await manager.add_node(wf.id, "log", "Step", {"message": "hi"})
        activated = await manager.activate(wf.id)
        assert activated.status == WorkflowStatus.ACTIVE
        assert activated.activated_at is not None
        assert activated.version == 2  # Incremented from default 1

    @pytest.mark.asyncio
    async def test_activate_empty_raises(self, manager: WorkflowManager) -> None:
        wf = await manager.create_workflow(name="Empty")
        with pytest.raises(ValueError, match="no nodes"):
            await manager.activate(wf.id)

    @pytest.mark.asyncio
    async def test_activate_creates_version_snapshot(self, manager: WorkflowManager) -> None:
        wf = await manager.create_workflow(name="Test")
        await manager.add_node(wf.id, "log", "Step", {"message": "hi"})
        activated = await manager.activate(wf.id)
        snapshot = await manager.database.get_version_snapshot(wf.id, activated.version)
        assert snapshot is not None
        assert "nodes" in snapshot
        assert len(snapshot["nodes"]) == 1

    @pytest.mark.asyncio
    async def test_deactivate(self, manager: WorkflowManager) -> None:
        wf = await manager.create_workflow(name="Test")
        await manager.add_node(wf.id, "log", "Step", {"message": "hi"})
        await manager.activate(wf.id)
        deactivated = await manager.deactivate(wf.id)
        assert deactivated.status == WorkflowStatus.INACTIVE


# ── Execution ────────────────────────────────────────────────────────


class TestExecution:
    @pytest.mark.asyncio
    async def test_trigger_simple_workflow(self, manager: WorkflowManager) -> None:
        wf = await manager.create_workflow(name="Simple")
        await manager.add_node(wf.id, "manual", "Trigger")
        n2 = await manager.add_node(wf.id, "log", "Log It", {"message": "Hello"})
        n1_nodes = await manager.database.get_nodes_for_workflow(wf.id)
        trigger_node = [n for n in n1_nodes if n.label == "Trigger"][0]
        await manager.add_edge(wf.id, trigger_node.id, n2.id)

        run = await manager.trigger(wf.id)
        assert run.status == RunStatus.SUCCESS
        assert run.duration_ms is not None

    @pytest.mark.asyncio
    async def test_trigger_updates_counters(self, manager: WorkflowManager) -> None:
        wf = await manager.create_workflow(name="Counter Test")
        await manager.add_node(wf.id, "log", "Step", {"message": "hi"})

        await manager.trigger(wf.id)
        updated = await manager.get_workflow(wf.id)
        assert updated.run_count == 1
        assert updated.success_count == 1

    @pytest.mark.asyncio
    async def test_trigger_records_node_executions(self, manager: WorkflowManager) -> None:
        wf = await manager.create_workflow(name="Exec Test")
        await manager.add_node(wf.id, "log", "A", {"message": "first"})
        n2 = await manager.add_node(wf.id, "log", "B", {"message": "second"})

        run = await manager.trigger(wf.id)
        detail = await manager.get_run_detail(run.id)
        assert detail is not None
        assert len(detail["node_executions"]) == 2

    @pytest.mark.asyncio
    async def test_list_runs(self, manager: WorkflowManager) -> None:
        wf = await manager.create_workflow(name="History Test")
        await manager.add_node(wf.id, "log", "Step", {"message": "hi"})

        await manager.trigger(wf.id)
        await manager.trigger(wf.id)

        runs, total = await manager.list_runs(wf.id)
        assert total == 2
        assert len(runs) == 2
