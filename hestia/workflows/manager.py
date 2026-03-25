"""
Workflow manager — CRUD, lifecycle, execution orchestration.

Coordinates between WorkflowDatabase, DAGExecutor, and WorkflowScheduler.
Singleton via get_workflow_manager().
"""

import json
from datetime import datetime, timezone
from graphlib import CycleError
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from hestia.logging import get_logger, LogComponent
from hestia.workflows.database import WorkflowDatabase, get_workflow_database
from hestia.workflows.event_bus import WorkflowEventBus
from hestia.workflows.executor import DAGExecutor, validate_dag
from hestia.workflows.models import (
    NodeExecution,
    RunStatus,
    Workflow,
    WorkflowEdge,
    WorkflowNode,
    WorkflowRun,
    WorkflowStatus,
)

logger = get_logger()

# Module-level singleton
_instance: Optional["WorkflowManager"] = None


class WorkflowManager:
    """Workflow CRUD, lifecycle management, and execution orchestration."""

    def __init__(
        self,
        database: Optional[WorkflowDatabase] = None,
        executor: Optional[DAGExecutor] = None,
        event_bus: Optional[WorkflowEventBus] = None,
    ) -> None:
        self._database = database
        self._executor = executor
        self._event_bus = event_bus or WorkflowEventBus()

    async def initialize(self) -> None:
        """Lazy-initialize dependencies."""
        if self._database is None:
            self._database = await get_workflow_database()
        if self._executor is None:
            self._executor = DAGExecutor(event_bus=self._event_bus)

    async def close(self) -> None:
        """Close resources."""
        pass  # Database closed separately via close_workflow_database()

    @property
    def database(self) -> WorkflowDatabase:
        if self._database is None:
            raise RuntimeError("WorkflowManager not initialized. Call initialize() first.")
        return self._database

    @property
    def executor(self) -> DAGExecutor:
        if self._executor is None:
            raise RuntimeError("WorkflowManager not initialized. Call initialize() first.")
        return self._executor

    @property
    def event_bus(self) -> WorkflowEventBus:
        return self._event_bus

    # ── Workflow CRUD ────────────────────────────────────────────────

    async def create_workflow(
        self,
        name: str,
        description: str = "",
        trigger_type: str = "manual",
        trigger_config: Optional[Dict[str, Any]] = None,
        session_strategy: str = "ephemeral",
    ) -> Workflow:
        """Create a new workflow in draft status."""
        from hestia.workflows.models import TriggerType, SessionStrategy

        wf = Workflow(
            name=name,
            description=description,
            trigger_type=TriggerType(trigger_type),
            trigger_config=trigger_config or {},
            session_strategy=SessionStrategy(session_strategy),
        )

        errors = wf.validate()
        if errors:
            raise ValueError(f"Invalid workflow: {'; '.join(errors)}")

        await self.database.store_workflow(wf)
        logger.info(
            f"Workflow created: {wf.id} ({wf.name})",
            component=LogComponent.WORKFLOW,
        )
        return wf

    async def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Get a workflow by ID."""
        return await self.database.get_workflow(workflow_id)

    async def get_workflow_detail(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get a workflow with its nodes and edges."""
        wf = await self.database.get_workflow(workflow_id)
        if not wf:
            return None

        nodes = await self.database.get_nodes_for_workflow(workflow_id)
        edges = await self.database.get_edges_for_workflow(workflow_id)

        return {
            **wf.to_dict(),
            "nodes": [n.to_dict() for n in nodes],
            "edges": [e.to_dict() for e in edges],
        }

    async def update_workflow(
        self, workflow_id: str, **kwargs: Any
    ) -> Optional[Workflow]:
        """Update workflow metadata (name, description, trigger, session_strategy)."""
        from hestia.workflows.models import TriggerType, SessionStrategy

        wf = await self.database.get_workflow(workflow_id)
        if not wf:
            return None

        if wf.status == WorkflowStatus.ACTIVE:
            raise ValueError("Cannot modify an active workflow. Deactivate first.")

        if "name" in kwargs:
            wf.name = kwargs["name"]
        if "description" in kwargs:
            wf.description = kwargs["description"]
        if "trigger_type" in kwargs:
            wf.trigger_type = TriggerType(kwargs["trigger_type"])
        if "trigger_config" in kwargs:
            wf.trigger_config = kwargs["trigger_config"]
        if "session_strategy" in kwargs:
            wf.session_strategy = SessionStrategy(kwargs["session_strategy"])

        errors = wf.validate()
        if errors:
            raise ValueError(f"Invalid workflow: {'; '.join(errors)}")

        await self.database.update_workflow(wf)
        return wf

    async def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow (cascades to nodes, edges, runs)."""
        deleted = await self.database.delete_workflow(workflow_id)
        if deleted:
            logger.info(
                f"Workflow deleted: {workflow_id}",
                component=LogComponent.WORKFLOW,
            )
        return deleted

    async def list_workflows(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Workflow], int]:
        """List workflows with optional status filter."""
        return await self.database.list_workflows(status, limit, offset)

    # ── Node CRUD ────────────────────────────────────────────────────

    async def add_node(
        self,
        workflow_id: str,
        node_type: str,
        label: str = "Untitled",
        config: Optional[Dict[str, Any]] = None,
        position_x: float = 0.0,
        position_y: float = 0.0,
    ) -> WorkflowNode:
        """Add a node to a workflow."""
        from hestia.workflows.models import NodeType

        wf = await self.database.get_workflow(workflow_id)
        if not wf:
            raise ValueError(f"Workflow not found: {workflow_id}")
        if wf.status == WorkflowStatus.ACTIVE:
            raise ValueError("Cannot modify an active workflow. Deactivate first.")

        node = WorkflowNode(
            workflow_id=workflow_id,
            node_type=NodeType(node_type),
            label=label,
            config=config or {},
            position_x=position_x,
            position_y=position_y,
        )

        errors = node.validate()
        if errors:
            raise ValueError(f"Invalid node: {'; '.join(errors)}")

        await self.database.add_node(node)
        return node

    async def update_node(
        self, node_id: str, **kwargs: Any
    ) -> Optional[WorkflowNode]:
        """Update a node's config, label, or position."""
        from hestia.workflows.models import NodeType

        node = await self.database.get_node(node_id)
        if not node:
            return None

        wf = await self.database.get_workflow(node.workflow_id)
        if wf and wf.status == WorkflowStatus.ACTIVE:
            raise ValueError("Cannot modify an active workflow. Deactivate first.")

        if "label" in kwargs:
            node.label = kwargs["label"]
        if "config" in kwargs:
            node.config = kwargs["config"]
        if "node_type" in kwargs:
            node.node_type = NodeType(kwargs["node_type"])
        if "position_x" in kwargs:
            node.position_x = kwargs["position_x"]
        if "position_y" in kwargs:
            node.position_y = kwargs["position_y"]

        await self.database.update_node(node)
        return node

    async def delete_node(self, node_id: str) -> bool:
        """Delete a node (cascades edges)."""
        return await self.database.delete_node(node_id)

    # ── Edge CRUD ────────────────────────────────────────────────────

    async def add_edge(
        self,
        workflow_id: str,
        source_node_id: str,
        target_node_id: str,
        edge_label: str = "",
    ) -> WorkflowEdge:
        """Add an edge, validating no cycle is introduced."""
        wf = await self.database.get_workflow(workflow_id)
        if not wf:
            raise ValueError(f"Workflow not found: {workflow_id}")
        if wf.status == WorkflowStatus.ACTIVE:
            raise ValueError("Cannot modify an active workflow. Deactivate first.")

        # Create the edge
        edge = WorkflowEdge(
            workflow_id=workflow_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_label=edge_label,
        )

        # Validate no cycle with the new edge included
        nodes = await self.database.get_nodes_for_workflow(workflow_id)
        existing_edges = await self.database.get_edges_for_workflow(workflow_id)
        all_edges = existing_edges + [edge]

        try:
            validate_dag(nodes, all_edges)
        except CycleError:
            raise ValueError(
                f"Adding edge {source_node_id} -> {target_node_id} would create a cycle"
            )

        await self.database.add_edge(edge)
        return edge

    async def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge."""
        return await self.database.delete_edge(edge_id)

    # ── Lifecycle ────────────────────────────────────────────────────

    async def activate(self, workflow_id: str) -> Workflow:
        """Activate a workflow — snapshots version and enables scheduling."""
        wf = await self.database.get_workflow(workflow_id)
        if not wf:
            raise ValueError(f"Workflow not found: {workflow_id}")

        nodes = await self.database.get_nodes_for_workflow(workflow_id)
        edges = await self.database.get_edges_for_workflow(workflow_id)

        if not nodes:
            raise ValueError("Cannot activate a workflow with no nodes")

        # Validate DAG
        try:
            validate_dag(nodes, edges)
        except CycleError:
            raise ValueError("Cannot activate: workflow contains a cycle")

        # Snapshot current state
        wf.version += 1
        snapshot = {
            "nodes": [n.to_dict() for n in nodes],
            "edges": [e.to_dict() for e in edges],
        }
        await self.database.store_version_snapshot(
            f"snap-{uuid4().hex[:12]}", workflow_id, wf.version, snapshot
        )

        wf.status = WorkflowStatus.ACTIVE
        wf.activated_at = datetime.now(timezone.utc)
        await self.database.update_workflow(wf)

        logger.info(
            f"Workflow activated: {wf.id} v{wf.version} ({wf.name})",
            component=LogComponent.WORKFLOW,
        )
        return wf

    async def deactivate(self, workflow_id: str) -> Workflow:
        """Deactivate a workflow — stops scheduling."""
        wf = await self.database.get_workflow(workflow_id)
        if not wf:
            raise ValueError(f"Workflow not found: {workflow_id}")

        wf.status = WorkflowStatus.INACTIVE
        await self.database.update_workflow(wf)

        logger.info(
            f"Workflow deactivated: {wf.id} ({wf.name})",
            component=LogComponent.WORKFLOW,
        )
        return wf

    # ── Execution ────────────────────────────────────────────────────

    async def trigger(
        self, workflow_id: str, trigger_source: str = "manual"
    ) -> WorkflowRun:
        """Trigger a workflow execution (blocks until complete).

        For fire-and-forget, use create_run() + execute_run() separately.
        The scheduler uses this directly since APScheduler manages concurrency.
        """
        run = await self.create_run(workflow_id, trigger_source)
        return await self.execute_run(run)

    async def create_run(
        self, workflow_id: str, trigger_source: str = "manual"
    ) -> WorkflowRun:
        """Create a run record without executing — returns immediately."""
        wf = await self.database.get_workflow(workflow_id)
        if not wf:
            raise ValueError(f"Workflow not found: {workflow_id}")

        run = WorkflowRun(
            workflow_id=workflow_id,
            workflow_version=wf.version,
            status=RunStatus.RUNNING,
            trigger_source=trigger_source,
        )
        await self.database.create_run(run)
        return run

    async def execute_run(self, run: WorkflowRun) -> WorkflowRun:
        """Execute a previously created run. Safe to call as a background task."""
        nodes = await self.database.get_nodes_for_workflow(run.workflow_id)
        edges = await self.database.get_edges_for_workflow(run.workflow_id)

        # Persistence callback
        async def on_node_complete(ne: NodeExecution, action: str) -> None:
            if action == "create":
                await self.database.create_node_execution(ne)
            elif action == "update":
                await self.database.update_node_execution(ne)

        # Execute the DAG
        result = await self.executor.execute(
            nodes, edges, run, on_node_complete=on_node_complete
        )

        # Update run and workflow counters
        await self.database.update_run(result)
        await self.database.increment_run_counts(
            run.workflow_id, success=(result.status == RunStatus.SUCCESS)
        )

        logger.info(
            f"Workflow run completed: {run.id} ({result.status.value})",
            component=LogComponent.WORKFLOW,
            data={"workflow_id": run.workflow_id, "duration_ms": result.duration_ms},
        )
        return result

    async def batch_update_layout(
        self, workflow_id: str, positions: list[dict],
    ) -> int:
        """Batch update node positions (from canvas drag operations)."""
        wf = await self.database.get_workflow(workflow_id)
        if not wf:
            raise ValueError(f"Workflow not found: {workflow_id}")
        return await self.database.batch_update_positions(workflow_id, positions)

    # ── Run History ──────────────────────────────────────────────────

    async def list_runs(
        self,
        workflow_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[WorkflowRun], int]:
        """List run history for a workflow."""
        return await self.database.list_runs(workflow_id, limit, offset)

    async def get_run_detail(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get a run with its node executions."""
        run = await self.database.get_run(run_id)
        if not run:
            return None

        executions = await self.database.get_executions_for_run(run_id)
        return {
            **run.to_dict(),
            "node_executions": [ne.to_dict() for ne in executions],
        }


# ── Singleton Factory ────────────────────────────────────────────────


async def get_workflow_manager(
    database: Optional[WorkflowDatabase] = None,
    executor: Optional[DAGExecutor] = None,
    event_bus: Optional[WorkflowEventBus] = None,
) -> WorkflowManager:
    """Get or create the singleton workflow manager."""
    global _instance
    if _instance is None:
        _instance = WorkflowManager(database, executor, event_bus)
        await _instance.initialize()
    return _instance


async def close_workflow_manager() -> None:
    """Close the singleton workflow manager."""
    global _instance
    if _instance is not None:
        await _instance.close()
        _instance = None
