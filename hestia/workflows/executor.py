"""
DAG executor — runs workflow nodes in topological order with parallel fan-out.

Uses graphlib.TopologicalSorter for ordering and asyncio for concurrency.
Key safeguards:
- asyncio.Event prevents busy-wait deadlock
- asyncio.Semaphore caps concurrent LLM calls (M1 constraint)
- done() always called in finally block (prevents graph hang)
- Per-node timeout with configurable limits
"""

import asyncio
from datetime import datetime, timezone
from graphlib import CycleError, TopologicalSorter
from typing import Any, Dict, List, Optional, Set

from hestia.logging import get_logger, LogComponent
from hestia.workflows.event_bus import WorkflowEvent, WorkflowEventBus
from hestia.workflows.models import (
    NodeExecution,
    NodeExecutionStatus,
    NodeType,
    RunStatus,
    WorkflowEdge,
    WorkflowNode,
    WorkflowRun,
)
from hestia.workflows.interpolation import interpolate_config
from hestia.workflows.nodes import NODE_EXECUTORS, NodeExecutorFn

logger = get_logger()

# Default timeouts (overridable via config)
DEFAULT_PROMPT_TIMEOUT = 120  # seconds
DEFAULT_NODE_TIMEOUT = 30  # seconds


class DAGExecutor:
    """
    Executes workflow DAGs with topological ordering and parallel fan-out.

    The executor:
    1. Loads nodes + edges from the database
    2. Validates the graph (cycle detection)
    3. Executes nodes level-by-level via TopologicalSorter
    4. Handles if_else branching by marking dead-path nodes as skipped
    5. Records NodeExecution records for every node
    6. Publishes SSE events for real-time UI feedback
    """

    def __init__(
        self,
        event_bus: Optional[WorkflowEventBus] = None,
        max_concurrent_llm: int = 2,
        prompt_timeout: int = DEFAULT_PROMPT_TIMEOUT,
        node_timeout: int = DEFAULT_NODE_TIMEOUT,
    ) -> None:
        self._event_bus = event_bus or WorkflowEventBus()
        self._semaphore = asyncio.Semaphore(max_concurrent_llm)
        self._prompt_timeout = prompt_timeout
        self._node_timeout = node_timeout

    async def execute(
        self,
        nodes: List[WorkflowNode],
        edges: List[WorkflowEdge],
        run: WorkflowRun,
        on_node_complete: Optional[Any] = None,
    ) -> WorkflowRun:
        """
        Execute a workflow DAG.

        Args:
            nodes: All nodes in the workflow
            edges: All edges connecting nodes
            run: Pre-created WorkflowRun (status should be RUNNING)
            on_node_complete: Optional async callback(node_execution) for persistence

        Returns:
            Updated WorkflowRun with final status
        """
        if not nodes:
            run.complete(success=True)
            return run

        # Build node lookup and adjacency
        node_map: Dict[str, WorkflowNode] = {n.id: n for n in nodes}
        adjacency = self._build_adjacency(nodes, edges)

        # Build reverse adjacency for input data resolution
        predecessors: Dict[str, List[str]] = {n.id: [] for n in nodes}
        for edge in edges:
            predecessors[edge.target_node_id].append(edge.source_node_id)

        # Build edge label lookup for if_else routing
        edge_labels: Dict[str, Dict[str, str]] = {}  # {source: {target: label}}
        for edge in edges:
            edge_labels.setdefault(edge.source_node_id, {})[edge.target_node_id] = edge.edge_label

        # Validate graph (raises CycleError if cycle)
        try:
            sorter = TopologicalSorter(adjacency)
            sorter.prepare()
        except CycleError as e:
            run.complete(success=False, error_message=f"Cycle detected: {e}")
            return run

        self._publish_event("run_started", run)

        # Execution state
        results: Dict[str, Dict[str, Any]] = {}  # node_id -> output_data
        executions: Dict[str, NodeExecution] = {}  # node_id -> NodeExecution
        skipped_nodes: Set[str] = set()
        failed = False
        error_msg: Optional[str] = None

        # Create NodeExecution records for all nodes
        for node in nodes:
            ne = NodeExecution(run_id=run.id, node_id=node.id)
            executions[node.id] = ne
            if on_node_complete:
                await on_node_complete(ne, "create")

        # Event for signaling node completion (prevents busy-wait)
        ready_event = asyncio.Event()
        ready_event.set()  # Initially ready

        while sorter.is_active():
            ready_event.clear()
            ready_ids = sorter.get_ready()

            if not ready_ids:
                # Wait for a node to complete before checking again
                await ready_event.wait()
                continue

            # Execute ready nodes in parallel
            tasks = []
            for node_id in ready_ids:
                if node_id in skipped_nodes:
                    # Mark skipped and notify sorter
                    ne = executions[node_id]
                    ne.skip("Dead path from condition")
                    if on_node_complete:
                        await on_node_complete(ne, "update")
                    sorter.done(node_id)
                    ready_event.set()
                    continue

                tasks.append(
                    self._execute_node_task(
                        node_id=node_id,
                        node=node_map[node_id],
                        predecessors=predecessors.get(node_id, []),
                        edge_labels=edge_labels,
                        results=results,
                        executions=executions,
                        skipped_nodes=skipped_nodes,
                        sorter=sorter,
                        ready_event=ready_event,
                        run=run,
                        on_node_complete=on_node_complete,
                    )
                )

            if tasks:
                task_results = await asyncio.gather(*tasks, return_exceptions=True)
                for tr in task_results:
                    if isinstance(tr, Exception):
                        failed = True
                        error_msg = f"{type(tr).__name__}: {tr}"
                        break
                if failed:
                    break

        # Check if any node failed
        if not failed:
            for ne in executions.values():
                if ne.status == NodeExecutionStatus.FAILED:
                    failed = True
                    error_msg = ne.error_message
                    break

        run.complete(success=not failed, error_message=error_msg)
        self._publish_event("run_completed", run, {"success": not failed})
        return run

    async def _execute_node_task(
        self,
        node_id: str,
        node: WorkflowNode,
        predecessors: List[str],
        edge_labels: Dict[str, Dict[str, str]],
        results: Dict[str, Dict[str, Any]],
        executions: Dict[str, NodeExecution],
        skipped_nodes: Set[str],
        sorter: TopologicalSorter,
        ready_event: asyncio.Event,
        run: WorkflowRun,
        on_node_complete: Optional[Any] = None,
    ) -> None:
        """Execute a single node with timeout, semaphore, and error handling."""
        ne = executions[node_id]

        # Build input data before marking as running (so callbacks see it)
        input_data = self._build_input_data(predecessors, results)
        ne.input_data = input_data
        ne.start()

        if on_node_complete:
            await on_node_complete(ne, "update")
        self._publish_event("node_started", run, {"node_id": node_id, "label": node.label})

        try:

            # Get executor function
            executor_fn = NODE_EXECUTORS.get(node.node_type)
            if executor_fn is None:
                raise ValueError(f"No executor for node type: {node.node_type}")

            # Interpolate config with prior node results
            interpolated_config = interpolate_config(node.config, results)

            # Determine timeout
            timeout = (
                self._prompt_timeout
                if node.node_type == NodeType.RUN_PROMPT
                else self._node_timeout
            )

            # Acquire semaphore for LLM nodes only
            if node.node_type == NodeType.RUN_PROMPT:
                async with self._semaphore:
                    output = await asyncio.wait_for(
                        executor_fn(interpolated_config, input_data),
                        timeout=timeout,
                    )
            else:
                output = await asyncio.wait_for(
                    executor_fn(interpolated_config, input_data),
                    timeout=timeout,
                )

            # Handle if_else branching — mark dead-path nodes as skipped
            if node.node_type == NodeType.IF_ELSE and isinstance(output, dict):
                branch = output.get("branch", "false")
                self._mark_dead_paths(
                    node_id, branch, edge_labels, results, skipped_nodes, sorter
                )

            ne.complete(output)
            results[node_id] = output

            if on_node_complete:
                await on_node_complete(ne, "update")
            self._publish_event(
                "node_completed", run,
                {"node_id": node_id, "label": node.label},
            )

        except asyncio.TimeoutError:
            ne.fail(f"Timeout after {self._prompt_timeout if node.node_type == NodeType.RUN_PROMPT else self._node_timeout}s")
            results[node_id] = {"error": ne.error_message}
            if on_node_complete:
                await on_node_complete(ne, "update")
            self._publish_event(
                "node_failed", run,
                {"node_id": node_id, "error": ne.error_message},
            )

        except Exception as e:
            ne.fail(f"{type(e).__name__}: {e}")
            results[node_id] = {"error": ne.error_message}
            if on_node_complete:
                await on_node_complete(ne, "update")
            self._publish_event(
                "node_failed", run,
                {"node_id": node_id, "error": ne.error_message},
            )

        finally:
            sorter.done(node_id)
            ready_event.set()

    def _build_adjacency(
        self,
        nodes: List[WorkflowNode],
        edges: List[WorkflowEdge],
    ) -> Dict[str, Set[str]]:
        """Build adjacency dict for TopologicalSorter.

        TopologicalSorter expects {node: {predecessors}} format.
        """
        adj: Dict[str, Set[str]] = {n.id: set() for n in nodes}
        for edge in edges:
            if edge.target_node_id in adj:
                adj[edge.target_node_id].add(edge.source_node_id)
        return adj

    def _build_input_data(
        self,
        predecessors: List[str],
        results: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build input data from predecessor node outputs.

        For a single predecessor, the output is used directly.
        For multiple predecessors (fan-in), outputs are keyed by node_id.
        """
        if not predecessors:
            return {}
        if len(predecessors) == 1:
            return results.get(predecessors[0], {})
        return {pid: results.get(pid, {}) for pid in predecessors}

    def _mark_dead_paths(
        self,
        condition_node_id: str,
        branch: str,
        edge_labels: Dict[str, Dict[str, str]],
        results: Dict[str, Dict[str, Any]],
        skipped_nodes: Set[str],
        sorter: TopologicalSorter,
    ) -> None:
        """Mark nodes on the dead path of an if_else as skipped.

        If branch is "true", skip nodes on "false" edges and vice versa.
        """
        targets = edge_labels.get(condition_node_id, {})
        dead_label = "false" if branch == "true" else "true"

        for target_id, label in targets.items():
            if label == dead_label:
                self._collect_downstream(target_id, edge_labels, skipped_nodes)

    def _collect_downstream(
        self,
        node_id: str,
        edge_labels: Dict[str, Dict[str, str]],
        skipped_nodes: Set[str],
    ) -> None:
        """Recursively collect all downstream nodes from a dead path."""
        if node_id in skipped_nodes:
            return
        skipped_nodes.add(node_id)
        for target_id in edge_labels.get(node_id, {}):
            self._collect_downstream(target_id, edge_labels, skipped_nodes)

    def _publish_event(
        self,
        event_type: str,
        run: WorkflowRun,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Publish a workflow event to the SSE bus."""
        self._event_bus.publish(
            WorkflowEvent(
                event_type=event_type,
                workflow_id=run.workflow_id,
                run_id=run.id,
                data=data or {},
            )
        )


def validate_dag(nodes: List[WorkflowNode], edges: List[WorkflowEdge]) -> None:
    """
    Validate that nodes + edges form a valid DAG (no cycles).

    Raises CycleError if a cycle is detected.
    """
    adj: Dict[str, Set[str]] = {n.id: set() for n in nodes}
    for edge in edges:
        if edge.target_node_id in adj:
            adj[edge.target_node_id].add(edge.source_node_id)
    sorter = TopologicalSorter(adj)
    sorter.prepare()  # Raises CycleError if cycle exists
