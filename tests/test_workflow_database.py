"""Tests for workflow database — CRUD, cascades, pagination, purge."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio

from hestia.workflows.database import WorkflowDatabase
from hestia.workflows.models import (
    NodeExecution,
    NodeExecutionStatus,
    NodeType,
    RunStatus,
    SessionStrategy,
    TriggerType,
    Workflow,
    WorkflowEdge,
    WorkflowNode,
    WorkflowRun,
    WorkflowStatus,
)


@pytest_asyncio.fixture
async def db(tmp_path: Path):
    """Create a fresh in-memory-like workflow database for each test."""
    db_path = tmp_path / "test_workflows.db"
    database = WorkflowDatabase(db_path)
    await database.connect()
    yield database
    await database.close()


def _make_workflow(**kwargs) -> Workflow:
    defaults = {"name": "Test Workflow", "description": "A test"}
    defaults.update(kwargs)
    return Workflow(**defaults)


def _make_node(workflow_id: str, **kwargs) -> WorkflowNode:
    defaults = {
        "workflow_id": workflow_id,
        "node_type": NodeType.RUN_PROMPT,
        "label": "Test Node",
        "config": {"prompt": "Hello"},
    }
    defaults.update(kwargs)
    return WorkflowNode(**defaults)


def _make_edge(workflow_id: str, source: str, target: str, **kwargs) -> WorkflowEdge:
    return WorkflowEdge(
        workflow_id=workflow_id,
        source_node_id=source,
        target_node_id=target,
        **kwargs,
    )


# ── Workflow CRUD ────────────────────────────────────────────────────


class TestWorkflowCRUD:
    @pytest.mark.asyncio
    async def test_store_and_get(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        loaded = await db.get_workflow(wf.id)
        assert loaded is not None
        assert loaded.name == "Test Workflow"
        assert loaded.status == WorkflowStatus.DRAFT

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, db: WorkflowDatabase) -> None:
        result = await db.get_workflow("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_update(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        wf.name = "Updated Name"
        wf.status = WorkflowStatus.ACTIVE
        await db.update_workflow(wf)
        loaded = await db.get_workflow(wf.id)
        assert loaded.name == "Updated Name"
        assert loaded.status == WorkflowStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_delete(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        deleted = await db.delete_workflow(wf.id)
        assert deleted is True
        assert await db.get_workflow(wf.id) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, db: WorkflowDatabase) -> None:
        deleted = await db.delete_workflow("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_list_all(self, db: WorkflowDatabase) -> None:
        for i in range(3):
            await db.store_workflow(_make_workflow(name=f"WF {i}"))
        workflows, total = await db.list_workflows()
        assert total == 3
        assert len(workflows) == 3

    @pytest.mark.asyncio
    async def test_list_with_status_filter(self, db: WorkflowDatabase) -> None:
        wf1 = _make_workflow(name="Active", status=WorkflowStatus.ACTIVE)
        wf2 = _make_workflow(name="Draft", status=WorkflowStatus.DRAFT)
        await db.store_workflow(wf1)
        await db.store_workflow(wf2)
        workflows, total = await db.list_workflows(status="active")
        assert total == 1
        assert workflows[0].name == "Active"

    @pytest.mark.asyncio
    async def test_list_pagination(self, db: WorkflowDatabase) -> None:
        for i in range(5):
            await db.store_workflow(_make_workflow(name=f"WF {i}"))
        page1, total = await db.list_workflows(limit=2, offset=0)
        page2, _ = await db.list_workflows(limit=2, offset=2)
        assert total == 5
        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0].id != page2[0].id

    @pytest.mark.asyncio
    async def test_trigger_config_json_roundtrip(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow(
            trigger_type=TriggerType.SCHEDULE,
            trigger_config={"cron": "0 7 * * *", "timezone": "US/Eastern"},
        )
        await db.store_workflow(wf)
        loaded = await db.get_workflow(wf.id)
        assert loaded.trigger_config == {"cron": "0 7 * * *", "timezone": "US/Eastern"}


# ── Node CRUD ────────────────────────────────────────────────────────


class TestNodeCRUD:
    @pytest.mark.asyncio
    async def test_add_and_get(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        node = _make_node(wf.id)
        await db.add_node(node)
        loaded = await db.get_node(node.id)
        assert loaded is not None
        assert loaded.label == "Test Node"
        assert loaded.config == {"prompt": "Hello"}

    @pytest.mark.asyncio
    async def test_update_node(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        node = _make_node(wf.id)
        await db.add_node(node)
        node.label = "Updated Label"
        node.config = {"prompt": "New prompt"}
        await db.update_node(node)
        loaded = await db.get_node(node.id)
        assert loaded.label == "Updated Label"
        assert loaded.config["prompt"] == "New prompt"

    @pytest.mark.asyncio
    async def test_delete_node(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        node = _make_node(wf.id)
        await db.add_node(node)
        deleted = await db.delete_node(node.id)
        assert deleted is True
        assert await db.get_node(node.id) is None

    @pytest.mark.asyncio
    async def test_get_nodes_for_workflow(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        for i in range(3):
            await db.add_node(_make_node(wf.id, label=f"Node {i}"))
        nodes = await db.get_nodes_for_workflow(wf.id)
        assert len(nodes) == 3

    @pytest.mark.asyncio
    async def test_node_config_json_roundtrip(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        node = _make_node(
            wf.id,
            node_type=NodeType.CALL_TOOL,
            config={"tool_name": "weather", "arguments": {"city": "NYC", "units": "metric"}},
        )
        await db.add_node(node)
        loaded = await db.get_node(node.id)
        assert loaded.config["arguments"]["city"] == "NYC"


# ── Edge CRUD ────────────────────────────────────────────────────────


class TestEdgeCRUD:
    @pytest.mark.asyncio
    async def test_add_and_get(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        n1 = _make_node(wf.id, label="Source")
        n2 = _make_node(wf.id, label="Target")
        await db.add_node(n1)
        await db.add_node(n2)
        edge = _make_edge(wf.id, n1.id, n2.id)
        await db.add_edge(edge)
        edges = await db.get_edges_for_workflow(wf.id)
        assert len(edges) == 1
        assert edges[0].source_node_id == n1.id
        assert edges[0].target_node_id == n2.id

    @pytest.mark.asyncio
    async def test_delete_edge(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        n1 = _make_node(wf.id, label="A")
        n2 = _make_node(wf.id, label="B")
        await db.add_node(n1)
        await db.add_node(n2)
        edge = _make_edge(wf.id, n1.id, n2.id)
        await db.add_edge(edge)
        deleted = await db.delete_edge(edge.id)
        assert deleted is True
        edges = await db.get_edges_for_workflow(wf.id)
        assert len(edges) == 0

    @pytest.mark.asyncio
    async def test_edge_with_label(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        n1 = _make_node(wf.id, label="Condition")
        n2 = _make_node(wf.id, label="True Path")
        await db.add_node(n1)
        await db.add_node(n2)
        edge = _make_edge(wf.id, n1.id, n2.id, edge_label="true")
        await db.add_edge(edge)
        edges = await db.get_edges_for_workflow(wf.id)
        assert edges[0].edge_label == "true"


# ── Cascade Deletes ──────────────────────────────────────────────────


class TestCascadeDeletes:
    @pytest.mark.asyncio
    async def test_delete_workflow_cascades_nodes(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        await db.add_node(_make_node(wf.id))
        await db.delete_workflow(wf.id)
        nodes = await db.get_nodes_for_workflow(wf.id)
        assert len(nodes) == 0

    @pytest.mark.asyncio
    async def test_delete_workflow_cascades_edges(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        n1 = _make_node(wf.id, label="A")
        n2 = _make_node(wf.id, label="B")
        await db.add_node(n1)
        await db.add_node(n2)
        await db.add_edge(_make_edge(wf.id, n1.id, n2.id))
        await db.delete_workflow(wf.id)
        edges = await db.get_edges_for_workflow(wf.id)
        assert len(edges) == 0

    @pytest.mark.asyncio
    async def test_delete_node_cascades_edges(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        n1 = _make_node(wf.id, label="A")
        n2 = _make_node(wf.id, label="B")
        await db.add_node(n1)
        await db.add_node(n2)
        await db.add_edge(_make_edge(wf.id, n1.id, n2.id))
        await db.delete_node(n1.id)
        edges = await db.get_edges_for_workflow(wf.id)
        assert len(edges) == 0

    @pytest.mark.asyncio
    async def test_delete_workflow_cascades_runs(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        run = WorkflowRun(workflow_id=wf.id)
        await db.create_run(run)
        await db.delete_workflow(wf.id)
        loaded_run = await db.get_run(run.id)
        assert loaded_run is None


# ── Run Lifecycle ────────────────────────────────────────────────────


class TestRunLifecycle:
    @pytest.mark.asyncio
    async def test_create_and_get_run(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        run = WorkflowRun(workflow_id=wf.id, status=RunStatus.RUNNING)
        await db.create_run(run)
        loaded = await db.get_run(run.id)
        assert loaded is not None
        assert loaded.status == RunStatus.RUNNING

    @pytest.mark.asyncio
    async def test_update_run(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        run = WorkflowRun(workflow_id=wf.id, status=RunStatus.RUNNING)
        await db.create_run(run)
        run.complete(success=True)
        await db.update_run(run)
        loaded = await db.get_run(run.id)
        assert loaded.status == RunStatus.SUCCESS
        assert loaded.completed_at is not None

    @pytest.mark.asyncio
    async def test_list_runs(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        for _ in range(3):
            await db.create_run(WorkflowRun(workflow_id=wf.id))
        runs, total = await db.list_runs(wf.id)
        assert total == 3
        assert len(runs) == 3

    @pytest.mark.asyncio
    async def test_list_runs_pagination(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        for _ in range(5):
            await db.create_run(WorkflowRun(workflow_id=wf.id))
        page1, total = await db.list_runs(wf.id, limit=2, offset=0)
        assert total == 5
        assert len(page1) == 2

    @pytest.mark.asyncio
    async def test_increment_run_counts_success(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        await db.increment_run_counts(wf.id, success=True)
        loaded = await db.get_workflow(wf.id)
        assert loaded.run_count == 1
        assert loaded.success_count == 1

    @pytest.mark.asyncio
    async def test_increment_run_counts_failure(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        await db.increment_run_counts(wf.id, success=False)
        loaded = await db.get_workflow(wf.id)
        assert loaded.run_count == 1
        assert loaded.success_count == 0


# ── Node Execution ───────────────────────────────────────────────────


class TestNodeExecution:
    @pytest.mark.asyncio
    async def test_create_and_get(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        node = _make_node(wf.id)
        await db.add_node(node)
        run = WorkflowRun(workflow_id=wf.id)
        await db.create_run(run)

        ne = NodeExecution(run_id=run.id, node_id=node.id)
        ne.start()
        await db.create_node_execution(ne)

        executions = await db.get_executions_for_run(run.id)
        assert len(executions) == 1
        assert executions[0].status == NodeExecutionStatus.RUNNING

    @pytest.mark.asyncio
    async def test_update_node_execution(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        node = _make_node(wf.id)
        await db.add_node(node)
        run = WorkflowRun(workflow_id=wf.id)
        await db.create_run(run)

        ne = NodeExecution(run_id=run.id, node_id=node.id)
        ne.start()
        await db.create_node_execution(ne)
        ne.complete({"response": "Hello"})
        await db.update_node_execution(ne)

        executions = await db.get_executions_for_run(run.id)
        assert executions[0].status == NodeExecutionStatus.SUCCESS
        assert executions[0].output_data == {"response": "Hello"}

    @pytest.mark.asyncio
    async def test_node_execution_json_roundtrip(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        node = _make_node(wf.id)
        await db.add_node(node)
        run = WorkflowRun(workflow_id=wf.id)
        await db.create_run(run)

        ne = NodeExecution(
            run_id=run.id,
            node_id=node.id,
            input_data={"key": [1, 2, 3]},
            output_data={"nested": {"a": True}},
        )
        ne.start()
        ne.complete(ne.output_data)
        await db.create_node_execution(ne)

        executions = await db.get_executions_for_run(run.id)
        assert executions[0].input_data == {"key": [1, 2, 3]}
        assert executions[0].output_data["nested"]["a"] is True


# ── Version Snapshots ────────────────────────────────────────────────


class TestVersionSnapshots:
    @pytest.mark.asyncio
    async def test_store_and_get_snapshot(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        snapshot = {
            "nodes": [{"id": "node-1", "type": "run_prompt"}],
            "edges": [{"source": "node-1", "target": "node-2"}],
        }
        await db.store_version_snapshot("snap-1", wf.id, 1, snapshot)
        loaded = await db.get_version_snapshot(wf.id, 1)
        assert loaded == snapshot

    @pytest.mark.asyncio
    async def test_get_nonexistent_version(self, db: WorkflowDatabase) -> None:
        result = await db.get_version_snapshot("nonexistent", 99)
        assert result is None


# ── Purge ────────────────────────────────────────────────────────────


class TestPurge:
    @pytest.mark.asyncio
    async def test_purge_old_executions(self, db: WorkflowDatabase) -> None:
        wf = _make_workflow()
        await db.store_workflow(wf)
        node = _make_node(wf.id)
        await db.add_node(node)
        run = WorkflowRun(workflow_id=wf.id)
        await db.create_run(run)

        # Create an old execution (40 days ago)
        old_ne = NodeExecution(run_id=run.id, node_id=node.id)
        old_ne.start()
        old_ne.completed_at = datetime.now(timezone.utc) - timedelta(days=40)
        old_ne.status = NodeExecutionStatus.SUCCESS
        await db.create_node_execution(old_ne)

        # Create a recent execution
        new_ne = NodeExecution(run_id=run.id, node_id=node.id)
        new_ne.start()
        new_ne.complete({"result": "fresh"})
        await db.create_node_execution(new_ne)

        deleted = await db.purge_old_executions(days=30)
        assert deleted == 1

        remaining = await db.get_executions_for_run(run.id)
        assert len(remaining) == 1
        assert remaining[0].output_data == {"result": "fresh"}

    @pytest.mark.asyncio
    async def test_purge_nothing_to_delete(self, db: WorkflowDatabase) -> None:
        deleted = await db.purge_old_executions(days=30)
        assert deleted == 0
