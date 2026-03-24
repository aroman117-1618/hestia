"""
Tests for Switch node — N-ary condition branching.

Covers:
- execute_switch unit tests (matching, default, dot-path)
- DAG-level integration tests (routing to correct branch, skipping dead paths)
"""

import pytest
from unittest.mock import AsyncMock, patch

from hestia.workflows.models import (
    NodeType,
    WorkflowNode,
    WorkflowEdge,
    WorkflowRun,
    NodeExecutionStatus,
)
from hestia.workflows.nodes import execute_switch
from hestia.workflows.executor import DAGExecutor


def _node(nid: str, ntype: NodeType = NodeType.LOG, config: dict = None) -> WorkflowNode:
    return WorkflowNode(
        id=nid,
        workflow_id="wf-test",
        node_type=ntype,
        label=nid,
        config=config or {},
    )


def _edge(src: str, tgt: str, label: str = "") -> WorkflowEdge:
    return WorkflowEdge(
        id=f"e-{src}-{tgt}",
        workflow_id="wf-test",
        source_node_id=src,
        target_node_id=tgt,
        edge_label=label,
    )


def _run() -> WorkflowRun:
    from datetime import datetime, timezone

    return WorkflowRun(
        id="run-test",
        workflow_id="wf-test",
        workflow_version=1,
        started_at=datetime.now(timezone.utc),
        trigger_source="manual",
    )


class TestSwitchExecutor:
    @pytest.mark.asyncio
    async def test_switch_matches_case(self) -> None:
        config = {
            "field": "category",
            "cases": [
                {"value": "urgent", "label": "case_urgent"},
                {"value": "normal", "label": "case_normal"},
            ],
            "default_label": "case_default",
        }
        result = await execute_switch(config, {"category": "urgent"})
        assert result["branch"] == "case_urgent"
        assert result["matched_value"] == "urgent"

    @pytest.mark.asyncio
    async def test_switch_second_case(self) -> None:
        config = {
            "field": "category",
            "cases": [
                {"value": "urgent", "label": "case_urgent"},
                {"value": "normal", "label": "case_normal"},
            ],
            "default_label": "case_default",
        }
        result = await execute_switch(config, {"category": "normal"})
        assert result["branch"] == "case_normal"

    @pytest.mark.asyncio
    async def test_switch_default(self) -> None:
        config = {
            "field": "category",
            "cases": [{"value": "urgent", "label": "case_urgent"}],
            "default_label": "case_default",
        }
        result = await execute_switch(config, {"category": "unknown"})
        assert result["branch"] == "case_default"

    @pytest.mark.asyncio
    async def test_switch_no_cases_returns_default(self) -> None:
        config = {"field": "x", "cases": [], "default_label": "fallback"}
        result = await execute_switch(config, {"x": "anything"})
        assert result["branch"] == "fallback"

    @pytest.mark.asyncio
    async def test_switch_dot_path(self) -> None:
        config = {
            "field": "response.type",
            "cases": [{"value": "error", "label": "handle_error"}],
            "default_label": "handle_ok",
        }
        result = await execute_switch(config, {"response": {"type": "error"}})
        assert result["branch"] == "handle_error"


class TestSwitchDAGExecution:
    @pytest.mark.asyncio
    async def test_switch_routes_to_correct_branch(self) -> None:
        """Switch routes to matched case, skips other branches."""
        nodes = [
            _node("trigger", NodeType.MANUAL),
            _node(
                "switch",
                NodeType.SWITCH,
                config={
                    "field": "category",
                    "cases": [
                        {"value": "urgent", "label": "case_urgent"},
                        {"value": "normal", "label": "case_normal"},
                    ],
                    "default_label": "case_default",
                },
            ),
            _node("urgent_handler", config={"message": "handling urgent"}),
            _node("normal_handler", config={"message": "handling normal"}),
            _node("default_handler", config={"message": "handling default"}),
        ]
        edges = [
            _edge("trigger", "switch"),
            _edge("switch", "urgent_handler", label="case_urgent"),
            _edge("switch", "normal_handler", label="case_normal"),
            _edge("switch", "default_handler", label="case_default"),
        ]

        mock_trigger = AsyncMock(return_value={"category": "urgent"})

        executions = {}

        async def capture(ne, _action):
            executions[ne.node_id] = ne

        with patch.dict(
            "hestia.workflows.nodes.NODE_EXECUTORS",
            {NodeType.MANUAL: mock_trigger},
        ):
            executor = DAGExecutor()
            await executor.execute(nodes, edges, _run(), on_node_complete=capture)

        assert executions["urgent_handler"].status == NodeExecutionStatus.SUCCESS
        assert executions["normal_handler"].status == NodeExecutionStatus.SKIPPED
        assert executions["default_handler"].status == NodeExecutionStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_switch_default_route(self) -> None:
        """Switch falls through to default when no case matches."""
        nodes = [
            _node("trigger", NodeType.MANUAL),
            _node(
                "switch",
                NodeType.SWITCH,
                config={
                    "field": "category",
                    "cases": [{"value": "urgent", "label": "case_urgent"}],
                    "default_label": "case_default",
                },
            ),
            _node("urgent_handler", config={"message": "urgent"}),
            _node("default_handler", config={"message": "default"}),
        ]
        edges = [
            _edge("trigger", "switch"),
            _edge("switch", "urgent_handler", label="case_urgent"),
            _edge("switch", "default_handler", label="case_default"),
        ]

        mock_trigger = AsyncMock(return_value={"category": "something_else"})

        executions = {}

        async def capture(ne, _action):
            executions[ne.node_id] = ne

        with patch.dict(
            "hestia.workflows.nodes.NODE_EXECUTORS",
            {NodeType.MANUAL: mock_trigger},
        ):
            executor = DAGExecutor()
            await executor.execute(nodes, edges, _run(), on_node_complete=capture)

        assert executions["urgent_handler"].status == NodeExecutionStatus.SKIPPED
        assert executions["default_handler"].status == NodeExecutionStatus.SUCCESS
