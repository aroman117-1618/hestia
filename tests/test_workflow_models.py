"""Tests for workflow data models — enums, dataclasses, serialization."""

import json
from datetime import datetime, timezone

import pytest

from hestia.workflows.models import (
    NodeExecution,
    NodeExecutionStatus,
    NodeType,
    RunStatus,
    SessionStrategy,
    TriggerType,
    Workflow,
    WorkflowEdge,
    WorkflowExecutionConfig,
    WorkflowNode,
    WorkflowRun,
    WorkflowStatus,
    _parse_dt,
)


# ── Enum Tests ───────────────────────────────────────────────────────


class TestEnums:
    def test_workflow_status_values(self) -> None:
        assert WorkflowStatus.DRAFT.value == "draft"
        assert WorkflowStatus.ACTIVE.value == "active"
        assert WorkflowStatus.INACTIVE.value == "inactive"
        assert WorkflowStatus.ARCHIVED.value == "archived"

    def test_node_type_values(self) -> None:
        assert NodeType.RUN_PROMPT.value == "run_prompt"
        assert NodeType.CALL_TOOL.value == "call_tool"
        assert NodeType.NOTIFY.value == "notify"
        assert NodeType.LOG.value == "log"
        assert NodeType.IF_ELSE.value == "if_else"
        assert NodeType.SCHEDULE.value == "schedule"
        assert NodeType.MANUAL.value == "manual"

    def test_trigger_type_values(self) -> None:
        assert TriggerType.MANUAL.value == "manual"
        assert TriggerType.SCHEDULE.value == "schedule"

    def test_run_status_values(self) -> None:
        assert RunStatus.PENDING.value == "pending"
        assert RunStatus.RUNNING.value == "running"
        assert RunStatus.SUCCESS.value == "success"
        assert RunStatus.FAILED.value == "failed"
        assert RunStatus.CANCELLED.value == "cancelled"

    def test_node_execution_status_values(self) -> None:
        assert NodeExecutionStatus.PENDING.value == "pending"
        assert NodeExecutionStatus.RUNNING.value == "running"
        assert NodeExecutionStatus.SUCCESS.value == "success"
        assert NodeExecutionStatus.FAILED.value == "failed"
        assert NodeExecutionStatus.SKIPPED.value == "skipped"

    def test_session_strategy_values(self) -> None:
        assert SessionStrategy.EPHEMERAL.value == "ephemeral"
        assert SessionStrategy.PER_RUN.value == "per_run"
        assert SessionStrategy.PERSISTENT.value == "persistent"

    def test_enum_from_string(self) -> None:
        assert WorkflowStatus("draft") == WorkflowStatus.DRAFT
        assert NodeType("run_prompt") == NodeType.RUN_PROMPT
        assert RunStatus("failed") == RunStatus.FAILED

    def test_invalid_enum_raises(self) -> None:
        with pytest.raises(ValueError):
            WorkflowStatus("nonexistent")


# ── Workflow Tests ───────────────────────────────────────────────────


class TestWorkflow:
    def test_default_creation(self) -> None:
        wf = Workflow()
        assert wf.id.startswith("wf-")
        assert wf.name == ""
        assert wf.status == WorkflowStatus.DRAFT
        assert wf.trigger_type == TriggerType.MANUAL
        assert wf.version == 1
        assert wf.run_count == 0
        assert wf.success_count == 0

    def test_custom_creation(self) -> None:
        wf = Workflow(
            name="Morning Brief",
            description="Daily summary",
            trigger_type=TriggerType.SCHEDULE,
            trigger_config={"cron": "0 7 * * *"},
            session_strategy=SessionStrategy.PERSISTENT,
        )
        assert wf.name == "Morning Brief"
        assert wf.trigger_config == {"cron": "0 7 * * *"}
        assert wf.session_strategy == SessionStrategy.PERSISTENT

    def test_success_rate_zero_runs(self) -> None:
        wf = Workflow()
        assert wf.success_rate == 0.0

    def test_success_rate_with_runs(self) -> None:
        wf = Workflow(run_count=10, success_count=7)
        assert wf.success_rate == 0.7

    def test_to_dict_roundtrip(self) -> None:
        wf = Workflow(name="Test", description="A test workflow")
        d = wf.to_dict()
        restored = Workflow.from_dict(d)
        assert restored.id == wf.id
        assert restored.name == wf.name
        assert restored.description == wf.description
        assert restored.status == wf.status

    def test_to_dict_includes_success_rate(self) -> None:
        wf = Workflow(run_count=4, success_count=3)
        d = wf.to_dict()
        assert d["success_rate"] == 0.75

    def test_from_sqlite_row_parses_json(self) -> None:
        row = {
            "id": "wf-abc123",
            "name": "Test",
            "description": "",
            "status": "active",
            "trigger_type": "schedule",
            "trigger_config": json.dumps({"cron": "0 8 * * *"}),
            "session_strategy": "per_run",
            "version": 2,
            "created_at": "2026-03-23T10:00:00+00:00",
            "updated_at": "2026-03-23T10:00:00+00:00",
            "activated_at": "2026-03-23T10:00:00+00:00",
            "last_run_at": None,
            "run_count": 5,
            "success_count": 4,
            "migrated_from_order_id": None,
        }
        wf = Workflow.from_sqlite_row(row)
        assert wf.trigger_config == {"cron": "0 8 * * *"}
        assert wf.status == WorkflowStatus.ACTIVE
        assert wf.version == 2

    def test_validate_no_name(self) -> None:
        wf = Workflow(name="")
        errors = wf.validate()
        assert any("name" in e.lower() for e in errors)

    def test_validate_schedule_no_config(self) -> None:
        wf = Workflow(name="Test", trigger_type=TriggerType.SCHEDULE, trigger_config={})
        errors = wf.validate()
        assert any("trigger_config" in e.lower() for e in errors)

    def test_validate_clean(self) -> None:
        wf = Workflow(name="Valid Workflow")
        assert wf.validate() == []


# ── WorkflowNode Tests ───────────────────────────────────────────────


class TestWorkflowNode:
    def test_default_creation(self) -> None:
        node = WorkflowNode()
        assert node.id.startswith("node-")
        assert node.node_type == NodeType.RUN_PROMPT
        assert node.label == "Untitled"
        assert node.config == {}

    def test_to_dict_roundtrip(self) -> None:
        node = WorkflowNode(
            workflow_id="wf-123",
            node_type=NodeType.NOTIFY,
            label="Send Alert",
            config={"title": "Alert", "body": "Something happened"},
            position_x=100.0,
            position_y=200.0,
        )
        d = node.to_dict()
        restored = WorkflowNode.from_dict(d)
        assert restored.id == node.id
        assert restored.node_type == NodeType.NOTIFY
        assert restored.config == {"title": "Alert", "body": "Something happened"}
        assert restored.position_x == 100.0

    def test_from_sqlite_row_parses_json_config(self) -> None:
        row = {
            "id": "node-abc",
            "workflow_id": "wf-123",
            "node_type": "call_tool",
            "label": "Fetch Weather",
            "config": json.dumps({"tool_name": "weather", "arguments": {"city": "NYC"}}),
            "position_x": 50.0,
            "position_y": 75.0,
        }
        node = WorkflowNode.from_sqlite_row(row)
        assert node.config["tool_name"] == "weather"

    def test_validate_run_prompt_needs_prompt(self) -> None:
        node = WorkflowNode(workflow_id="wf-1", node_type=NodeType.RUN_PROMPT, config={})
        errors = node.validate()
        assert any("prompt" in e.lower() for e in errors)

    def test_validate_call_tool_needs_tool_name(self) -> None:
        node = WorkflowNode(workflow_id="wf-1", node_type=NodeType.CALL_TOOL, config={})
        errors = node.validate()
        assert any("tool_name" in e.lower() for e in errors)

    def test_validate_if_else_needs_condition(self) -> None:
        node = WorkflowNode(workflow_id="wf-1", node_type=NodeType.IF_ELSE, config={})
        errors = node.validate()
        assert any("condition" in e.lower() for e in errors)

    def test_validate_clean_prompt_node(self) -> None:
        node = WorkflowNode(
            workflow_id="wf-1",
            node_type=NodeType.RUN_PROMPT,
            config={"prompt": "Hello"},
        )
        assert node.validate() == []


# ── WorkflowEdge Tests ───────────────────────────────────────────────


class TestWorkflowEdge:
    def test_default_creation(self) -> None:
        edge = WorkflowEdge()
        assert edge.id.startswith("edge-")
        assert edge.edge_label == ""

    def test_to_dict_roundtrip(self) -> None:
        edge = WorkflowEdge(
            workflow_id="wf-1",
            source_node_id="node-a",
            target_node_id="node-b",
            edge_label="true",
        )
        d = edge.to_dict()
        restored = WorkflowEdge.from_dict(d)
        assert restored.source_node_id == "node-a"
        assert restored.target_node_id == "node-b"
        assert restored.edge_label == "true"

    def test_from_sqlite_row(self) -> None:
        row = {
            "id": "edge-xyz",
            "workflow_id": "wf-1",
            "source_node_id": "node-a",
            "target_node_id": "node-b",
            "edge_label": "false",
        }
        edge = WorkflowEdge.from_sqlite_row(row)
        assert edge.edge_label == "false"


# ── WorkflowRun Tests ────────────────────────────────────────────────


class TestWorkflowRun:
    def test_default_creation(self) -> None:
        run = WorkflowRun()
        assert run.id.startswith("run-")
        assert run.status == RunStatus.PENDING
        assert run.trigger_source == "manual"

    def test_complete_success(self) -> None:
        run = WorkflowRun(workflow_id="wf-1", status=RunStatus.RUNNING)
        run.complete(success=True)
        assert run.status == RunStatus.SUCCESS
        assert run.completed_at is not None
        assert run.duration_ms is not None
        assert run.error_message is None

    def test_complete_failure(self) -> None:
        run = WorkflowRun(workflow_id="wf-1", status=RunStatus.RUNNING)
        run.complete(success=False, error_message="Node X failed")
        assert run.status == RunStatus.FAILED
        assert run.error_message == "Node X failed"

    def test_to_dict_roundtrip(self) -> None:
        run = WorkflowRun(workflow_id="wf-1", trigger_source="schedule")
        d = run.to_dict()
        restored = WorkflowRun.from_dict(d)
        assert restored.workflow_id == "wf-1"
        assert restored.trigger_source == "schedule"


# ── NodeExecution Tests ──────────────────────────────────────────────


class TestNodeExecution:
    def test_default_creation(self) -> None:
        ne = NodeExecution()
        assert ne.id.startswith("nexec-")
        assert ne.status == NodeExecutionStatus.PENDING
        assert ne.input_data == {}
        assert ne.output_data == {}

    def test_start(self) -> None:
        ne = NodeExecution(run_id="run-1", node_id="node-a")
        ne.start()
        assert ne.status == NodeExecutionStatus.RUNNING
        assert ne.started_at is not None

    def test_complete(self) -> None:
        ne = NodeExecution(run_id="run-1", node_id="node-a")
        ne.start()
        ne.complete({"response": "Hello world"})
        assert ne.status == NodeExecutionStatus.SUCCESS
        assert ne.output_data == {"response": "Hello world"}
        assert ne.duration_ms is not None

    def test_fail(self) -> None:
        ne = NodeExecution(run_id="run-1", node_id="node-a")
        ne.start()
        ne.fail("Timeout exceeded")
        assert ne.status == NodeExecutionStatus.FAILED
        assert ne.error_message == "Timeout exceeded"

    def test_skip(self) -> None:
        ne = NodeExecution(run_id="run-1", node_id="node-a")
        ne.skip("Dead path from if_else")
        assert ne.status == NodeExecutionStatus.SKIPPED
        assert ne.error_message == "Dead path from if_else"

    def test_to_dict_roundtrip(self) -> None:
        ne = NodeExecution(
            run_id="run-1",
            node_id="node-a",
            input_data={"key": "value"},
            output_data={"result": 42},
        )
        ne.start()
        ne.complete({"result": 42})
        d = ne.to_dict()
        restored = NodeExecution.from_dict(d)
        assert restored.output_data == {"result": 42}
        assert restored.status == NodeExecutionStatus.SUCCESS

    def test_from_sqlite_row_parses_json(self) -> None:
        row = {
            "id": "nexec-abc",
            "run_id": "run-1",
            "node_id": "node-a",
            "status": "success",
            "started_at": "2026-03-23T10:00:00+00:00",
            "completed_at": "2026-03-23T10:00:01+00:00",
            "duration_ms": 1000.0,
            "input_data": json.dumps({"prompt": "hi"}),
            "output_data": json.dumps({"response": "hello"}),
            "error_message": None,
        }
        ne = NodeExecution.from_sqlite_row(row)
        assert ne.input_data == {"prompt": "hi"}
        assert ne.output_data == {"response": "hello"}


# ── P0 Models Tests ──────────────────────────────────────────────────


class TestP0Models:
    def test_workflow_execution_config_defaults(self) -> None:
        config = WorkflowExecutionConfig()
        assert config.session_strategy == SessionStrategy.EPHEMERAL
        assert config.memory_write is False
        assert config.memory_read is True
        assert config.force_local is False
        assert config.allowed_tools is None

    def test_workflow_execution_config_custom(self) -> None:
        config = WorkflowExecutionConfig(
            session_strategy=SessionStrategy.PERSISTENT,
            memory_write=True,
            agent_mode="artemis",
            workflow_id="wf-123",
        )
        assert config.session_strategy == SessionStrategy.PERSISTENT
        assert config.memory_write is True
        assert config.agent_mode == "artemis"


# ── Helper Tests ─────────────────────────────────────────────────────


class TestParseDt:
    def test_parse_iso_string(self) -> None:
        result = _parse_dt("2026-03-23T10:00:00+00:00")
        assert isinstance(result, datetime)
        assert result.year == 2026

    def test_parse_z_suffix(self) -> None:
        result = _parse_dt("2026-03-23T10:00:00Z")
        assert isinstance(result, datetime)

    def test_passthrough_datetime(self) -> None:
        dt = datetime.now(timezone.utc)
        assert _parse_dt(dt) is dt

    def test_invalid_type_raises(self) -> None:
        with pytest.raises(ValueError):
            _parse_dt(12345)
