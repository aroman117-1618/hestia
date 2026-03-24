"""Tests for DAG executor — topological ordering, parallelism, branching, failure."""

import asyncio
from graphlib import CycleError
from typing import Any, Dict
from unittest.mock import AsyncMock

import pytest

from hestia.workflows.event_bus import WorkflowEventBus
from hestia.workflows.executor import DAGExecutor, validate_dag
from hestia.workflows.models import (
    NodeExecution,
    NodeExecutionStatus,
    NodeType,
    RunStatus,
    WorkflowEdge,
    WorkflowNode,
    WorkflowRun,
)
from hestia.workflows.nodes import (
    NODE_EXECUTORS,
    evaluate_condition,
    execute_if_else,
    execute_log,
    execute_trigger_noop,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _node(node_id: str, node_type: NodeType = NodeType.LOG, **config) -> WorkflowNode:
    return WorkflowNode(
        id=node_id,
        workflow_id="wf-test",
        node_type=node_type,
        label=node_id,
        config=config if config else {"message": f"Node {node_id}"},
    )


def _edge(source: str, target: str, label: str = "") -> WorkflowEdge:
    return WorkflowEdge(
        workflow_id="wf-test",
        source_node_id=source,
        target_node_id=target,
        edge_label=label,
    )


def _run() -> WorkflowRun:
    return WorkflowRun(workflow_id="wf-test", status=RunStatus.RUNNING)


# ── Condition Evaluator Tests ────────────────────────────────────────


class TestConditionEvaluator:
    def test_eq_true(self) -> None:
        result = evaluate_condition(
            {"field": "status", "operator": "eq", "value": "ok"},
            {"status": "ok"},
        )
        assert result is True

    def test_eq_false(self) -> None:
        result = evaluate_condition(
            {"field": "status", "operator": "eq", "value": "ok"},
            {"status": "error"},
        )
        assert result is False

    def test_gt(self) -> None:
        result = evaluate_condition(
            {"field": "confidence", "operator": "gt", "value": 0.8},
            {"confidence": 0.9},
        )
        assert result is True

    def test_contains(self) -> None:
        result = evaluate_condition(
            {"field": "response", "operator": "contains", "value": "urgent"},
            {"response": "This is urgent!"},
        )
        assert result is True

    def test_is_empty_true(self) -> None:
        result = evaluate_condition(
            {"field": "data", "operator": "is_empty", "value": None},
            {"data": ""},
        )
        assert result is True

    def test_is_empty_false(self) -> None:
        result = evaluate_condition(
            {"field": "data", "operator": "is_empty", "value": None},
            {"data": "something"},
        )
        assert result is False

    def test_dot_path(self) -> None:
        result = evaluate_condition(
            {"field": "nested.value", "operator": "eq", "value": 42},
            {"nested": {"value": 42}},
        )
        assert result is True

    def test_unknown_operator_returns_false(self) -> None:
        result = evaluate_condition(
            {"field": "x", "operator": "magical_op", "value": 1},
            {"x": 1},
        )
        assert result is False

    def test_type_mismatch_returns_false(self) -> None:
        result = evaluate_condition(
            {"field": "x", "operator": "gt", "value": "not_a_number"},
            {"x": 5},
        )
        assert result is False

    def test_missing_field_returns_none(self) -> None:
        result = evaluate_condition(
            {"field": "nonexistent", "operator": "is_true", "value": None},
            {"other": "data"},
        )
        assert result is False


# ── Node Executor Tests ──────────────────────────────────────────────


class TestNodeExecutors:
    @pytest.mark.asyncio
    async def test_log_executor(self) -> None:
        result = await execute_log({"message": "Test log", "level": "info"}, {})
        assert result["logged"] is True
        assert result["message"] == "Test log"

    @pytest.mark.asyncio
    async def test_log_executor_warning(self) -> None:
        result = await execute_log({"message": "Warning!", "level": "warning"}, {})
        assert result["logged"] is True
        assert result["level"] == "warning"

    @pytest.mark.asyncio
    async def test_trigger_noop(self) -> None:
        result = await execute_trigger_noop({}, {})
        assert result["triggered"] is True

    @pytest.mark.asyncio
    async def test_if_else_true(self) -> None:
        result = await execute_if_else(
            {"condition": {"field": "value", "operator": "gt", "value": 5}},
            {"value": 10},
        )
        assert result["branch"] == "true"

    @pytest.mark.asyncio
    async def test_if_else_false(self) -> None:
        result = await execute_if_else(
            {"condition": {"field": "value", "operator": "gt", "value": 5}},
            {"value": 3},
        )
        assert result["branch"] == "false"

    @pytest.mark.asyncio
    async def test_if_else_no_condition(self) -> None:
        result = await execute_if_else({}, {})
        assert result["branch"] == "false"

    def test_all_node_types_have_executors(self) -> None:
        for nt in NodeType:
            assert nt in NODE_EXECUTORS, f"Missing executor for {nt}"


# ── DAG Executor Tests ───────────────────────────────────────────────


class TestDAGExecutorLinear:
    """Test linear DAG: A -> B -> C"""

    @pytest.mark.asyncio
    async def test_linear_three_node(self) -> None:
        nodes = [
            _node("a", NodeType.MANUAL),
            _node("b", NodeType.LOG, message="Step B"),
            _node("c", NodeType.LOG, message="Step C"),
        ]
        edges = [_edge("a", "b"), _edge("b", "c")]
        run = _run()

        executor = DAGExecutor()
        result = await executor.execute(nodes, edges, run)

        assert result.status == RunStatus.SUCCESS
        assert result.completed_at is not None
        assert result.duration_ms is not None

    @pytest.mark.asyncio
    async def test_empty_workflow(self) -> None:
        run = _run()
        executor = DAGExecutor()
        result = await executor.execute([], [], run)
        assert result.status == RunStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_single_node(self) -> None:
        nodes = [_node("a", NodeType.LOG, message="Solo")]
        run = _run()
        executor = DAGExecutor()
        result = await executor.execute(nodes, [], run)
        assert result.status == RunStatus.SUCCESS


class TestDAGExecutorParallel:
    """Test parallel fan-out: A -> [B, C] -> D"""

    @pytest.mark.asyncio
    async def test_fan_out_fan_in(self) -> None:
        nodes = [
            _node("trigger", NodeType.MANUAL),
            _node("branch_a", NodeType.LOG, message="Branch A"),
            _node("branch_b", NodeType.LOG, message="Branch B"),
            _node("join", NodeType.LOG, message="Joined"),
        ]
        edges = [
            _edge("trigger", "branch_a"),
            _edge("trigger", "branch_b"),
            _edge("branch_a", "join"),
            _edge("branch_b", "join"),
        ]
        run = _run()
        executor = DAGExecutor()
        result = await executor.execute(nodes, edges, run)
        assert result.status == RunStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_fan_in_input_data_keyed_by_source(self) -> None:
        """When a node has multiple predecessors, input_data is keyed by source_node_id."""
        nodes = [
            _node("a", NodeType.LOG, message="From A"),
            _node("b", NodeType.LOG, message="From B"),
            _node("join", NodeType.LOG, message="Joined"),
        ]
        edges = [_edge("a", "join"), _edge("b", "join")]

        collected_inputs = {}

        async def on_complete(ne: NodeExecution, action: str) -> None:
            if action == "update" and ne.node_id == "join" and ne.status == NodeExecutionStatus.RUNNING:
                collected_inputs.update(ne.input_data)

        run = _run()
        executor = DAGExecutor()
        result = await executor.execute(nodes, edges, run, on_node_complete=on_complete)
        assert result.status == RunStatus.SUCCESS
        # Fan-in: input_data should have keys "a" and "b"
        assert "a" in collected_inputs
        assert "b" in collected_inputs


class TestDAGExecutorBranching:
    """Test if_else branching — true path executes, false path skipped."""

    @pytest.mark.asyncio
    async def test_if_else_true_branch(self) -> None:
        """Condition evaluates true -> true-path runs, false-path skipped."""
        nodes = [
            _node("trigger", NodeType.MANUAL),
            _node("condition", NodeType.IF_ELSE,
                  condition={"field": "triggered", "operator": "is_true", "value": None}),
            _node("true_path", NodeType.LOG, message="Took true path"),
            _node("false_path", NodeType.LOG, message="Took false path"),
        ]
        edges = [
            _edge("trigger", "condition"),
            _edge("condition", "true_path", label="true"),
            _edge("condition", "false_path", label="false"),
        ]

        executions_log = {}

        async def on_complete(ne: NodeExecution, action: str) -> None:
            if action == "update" and ne.status in (
                NodeExecutionStatus.SUCCESS,
                NodeExecutionStatus.SKIPPED,
            ):
                executions_log[ne.node_id] = ne.status

        run = _run()
        executor = DAGExecutor()
        result = await executor.execute(nodes, edges, run, on_node_complete=on_complete)
        assert result.status == RunStatus.SUCCESS
        assert executions_log.get("true_path") == NodeExecutionStatus.SUCCESS
        assert executions_log.get("false_path") == NodeExecutionStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_if_else_false_branch(self) -> None:
        """Condition evaluates false -> false-path runs, true-path skipped."""
        nodes = [
            _node("trigger", NodeType.MANUAL),
            _node("condition", NodeType.IF_ELSE,
                  condition={"field": "value", "operator": "gt", "value": 100}),
            _node("true_path", NodeType.LOG, message="High value"),
            _node("false_path", NodeType.LOG, message="Low value"),
        ]
        edges = [
            _edge("trigger", "condition"),
            _edge("condition", "true_path", label="true"),
            _edge("condition", "false_path", label="false"),
        ]

        executions_log = {}

        async def on_complete(ne: NodeExecution, action: str) -> None:
            if action == "update" and ne.status in (
                NodeExecutionStatus.SUCCESS,
                NodeExecutionStatus.SKIPPED,
            ):
                executions_log[ne.node_id] = ne.status

        run = _run()
        executor = DAGExecutor()
        result = await executor.execute(nodes, edges, run, on_node_complete=on_complete)
        assert result.status == RunStatus.SUCCESS
        assert executions_log.get("true_path") == NodeExecutionStatus.SKIPPED
        assert executions_log.get("false_path") == NodeExecutionStatus.SUCCESS


class TestDAGExecutorFailure:
    """Test failure modes — node failure, timeout, cycle detection."""

    @pytest.mark.asyncio
    async def test_node_failure_fails_run(self) -> None:
        """If a node raises, the run should fail."""
        # Register a temporary failing executor
        original = NODE_EXECUTORS.get(NodeType.LOG)

        async def failing_executor(config, input_data, **kwargs):
            raise RuntimeError("Intentional failure")

        NODE_EXECUTORS[NodeType.LOG] = failing_executor
        try:
            nodes = [_node("a", NodeType.LOG, message="Will fail")]
            run = _run()
            executor = DAGExecutor()
            result = await executor.execute(nodes, [], run)
            assert result.status == RunStatus.FAILED
            assert "Intentional failure" in result.error_message
        finally:
            NODE_EXECUTORS[NodeType.LOG] = original

    @pytest.mark.asyncio
    async def test_timeout_fails_node(self) -> None:
        """Node that exceeds timeout should fail."""
        original = NODE_EXECUTORS.get(NodeType.LOG)

        async def slow_executor(config, input_data, **kwargs):
            await asyncio.sleep(5)
            return {"result": "too slow"}

        NODE_EXECUTORS[NodeType.LOG] = slow_executor
        try:
            nodes = [_node("a", NodeType.LOG)]
            run = _run()
            executor = DAGExecutor(node_timeout=1)  # 1 second timeout
            result = await executor.execute(nodes, [], run)
            assert result.status == RunStatus.FAILED
            assert "Timeout" in (result.error_message or "")
        finally:
            NODE_EXECUTORS[NodeType.LOG] = original

    @pytest.mark.asyncio
    async def test_cycle_detection(self) -> None:
        """Cycles should be detected and fail the run."""
        nodes = [
            _node("a", NodeType.LOG),
            _node("b", NodeType.LOG),
        ]
        edges = [_edge("a", "b"), _edge("b", "a")]
        run = _run()
        executor = DAGExecutor()
        result = await executor.execute(nodes, edges, run)
        assert result.status == RunStatus.FAILED
        assert "Cycle" in (result.error_message or "")


class TestDAGExecutorSemaphore:
    """Test concurrency limiting via semaphore."""

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrent_prompts(self) -> None:
        """At most max_concurrent_llm RunPrompt nodes should run concurrently."""
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        original = NODE_EXECUTORS.get(NodeType.RUN_PROMPT)

        async def tracking_executor(config, input_data, **kwargs):
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                max_concurrent = max(max_concurrent, current_concurrent)
            await asyncio.sleep(0.1)
            async with lock:
                current_concurrent -= 1
            return {"response": "ok"}

        NODE_EXECUTORS[NodeType.RUN_PROMPT] = tracking_executor
        try:
            # 4 parallel prompt nodes, semaphore of 2
            nodes = [
                _node("trigger", NodeType.MANUAL),
                _node("p1", NodeType.RUN_PROMPT, prompt="a"),
                _node("p2", NodeType.RUN_PROMPT, prompt="b"),
                _node("p3", NodeType.RUN_PROMPT, prompt="c"),
                _node("p4", NodeType.RUN_PROMPT, prompt="d"),
            ]
            edges = [
                _edge("trigger", "p1"),
                _edge("trigger", "p2"),
                _edge("trigger", "p3"),
                _edge("trigger", "p4"),
            ]
            run = _run()
            executor = DAGExecutor(max_concurrent_llm=2)
            result = await executor.execute(nodes, edges, run)
            assert result.status == RunStatus.SUCCESS
            assert max_concurrent <= 2
        finally:
            NODE_EXECUTORS[NodeType.RUN_PROMPT] = original


class TestDAGExecutorEvents:
    """Test SSE event publishing."""

    @pytest.mark.asyncio
    async def test_events_published(self) -> None:
        event_bus = WorkflowEventBus()
        queue = event_bus.subscribe()

        nodes = [_node("a", NodeType.LOG, message="Test")]
        run = _run()
        executor = DAGExecutor(event_bus=event_bus)
        await executor.execute(nodes, [], run)

        events = []
        while not queue.empty():
            events.append(await queue.get())

        event_types = [e.event_type for e in events]
        assert "run_started" in event_types
        assert "node_started" in event_types
        assert "node_completed" in event_types
        assert "run_completed" in event_types

    @pytest.mark.asyncio
    async def test_node_execution_callback(self) -> None:
        """on_node_complete callback should be called for each node."""
        callbacks = []

        async def on_complete(ne: NodeExecution, action: str) -> None:
            callbacks.append((ne.node_id, action, ne.status.value))

        nodes = [_node("a", NodeType.LOG, message="Test")]
        run = _run()
        executor = DAGExecutor()
        await executor.execute(nodes, [], run, on_node_complete=on_complete)

        # Should have: create, running update, completed update
        assert len(callbacks) >= 2
        actions = [c[1] for c in callbacks]
        assert "create" in actions
        assert "update" in actions


# ── validate_dag Tests ───────────────────────────────────────────────


class TestValidateDAG:
    def test_valid_dag(self) -> None:
        nodes = [_node("a"), _node("b"), _node("c")]
        edges = [_edge("a", "b"), _edge("b", "c")]
        validate_dag(nodes, edges)  # Should not raise

    def test_cycle_raises(self) -> None:
        nodes = [_node("a"), _node("b")]
        edges = [_edge("a", "b"), _edge("b", "a")]
        with pytest.raises(CycleError):
            validate_dag(nodes, edges)

    def test_self_loop_raises(self) -> None:
        nodes = [_node("a")]
        edges = [_edge("a", "a")]
        with pytest.raises(CycleError):
            validate_dag(nodes, edges)

    def test_empty_is_valid(self) -> None:
        validate_dag([], [])  # Should not raise

    def test_disconnected_is_valid(self) -> None:
        nodes = [_node("a"), _node("b")]
        validate_dag(nodes, [])  # Disconnected nodes are valid
