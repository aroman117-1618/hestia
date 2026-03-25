"""
Data models for the workflow execution system.

Workflows are DAGs of nodes (prompts, tool calls, conditions, notifications)
connected by edges. The DAGExecutor runs them with topological ordering,
parallel fan-out, and condition-based branching.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


# ── P0 models (unchanged) ────────────────────────────────────────────


class SessionStrategy(str, Enum):
    """How workflow executions manage conversation sessions."""
    EPHEMERAL = "ephemeral"
    PER_RUN = "per_run"
    PERSISTENT = "persistent"


@dataclass
class WorkflowExecutionConfig:
    """Configuration for how a workflow node calls the handler."""
    session_strategy: SessionStrategy = SessionStrategy.EPHEMERAL
    session_id: Optional[str] = None
    memory_write: bool = False
    memory_read: bool = True
    force_local: bool = False
    agent_mode: Optional[str] = None
    allowed_tools: Optional[List[str]] = None
    workflow_id: Optional[str] = None
    workflow_name: Optional[str] = None
    node_id: Optional[str] = None
    run_id: Optional[str] = None
    # Inference routing: "local" (force local), "smart_cloud" (local-first,
    # cloud fallback), "full_cloud" (always cloud). Default None = use force_local.
    inference_route: Optional[str] = None


# ── P1 enums ─────────────────────────────────────────────────────────


class WorkflowStatus(str, Enum):
    """Workflow lifecycle states."""
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class NodeType(str, Enum):
    """Available node types in workflow DAGs."""
    # Action nodes
    RUN_PROMPT = "run_prompt"
    CALL_TOOL = "call_tool"
    NOTIFY = "notify"
    LOG = "log"
    # Condition nodes
    IF_ELSE = "if_else"
    SWITCH = "switch"
    # Trigger nodes
    SCHEDULE = "schedule"
    MANUAL = "manual"
    # Timing nodes
    DELAY = "delay"


class TriggerType(str, Enum):
    """How a workflow is triggered."""
    MANUAL = "manual"
    SCHEDULE = "schedule"


class RunStatus(str, Enum):
    """Workflow run lifecycle states."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeExecutionStatus(str, Enum):
    """Per-node execution states within a run."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


# ── P1 dataclasses ───────────────────────────────────────────────────


@dataclass
class Workflow:
    """Top-level workflow definition."""
    id: str = field(default_factory=lambda: f"wf-{uuid4().hex[:12]}")
    name: str = ""
    description: str = ""
    status: WorkflowStatus = WorkflowStatus.DRAFT
    trigger_type: TriggerType = TriggerType.MANUAL
    trigger_config: Dict[str, Any] = field(default_factory=dict)
    session_strategy: SessionStrategy = SessionStrategy.EPHEMERAL
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    activated_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    run_count: int = 0
    success_count: int = 0
    migrated_from_order_id: Optional[str] = None

    @property
    def success_rate(self) -> float:
        if self.run_count == 0:
            return 0.0
        return self.success_count / self.run_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "trigger_type": self.trigger_type.value,
            "trigger_config": self.trigger_config,
            "session_strategy": self.session_strategy.value,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "run_count": self.run_count,
            "success_count": self.success_count,
            "success_rate": self.success_rate,
            "migrated_from_order_id": self.migrated_from_order_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Workflow":
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            status=WorkflowStatus(data["status"]),
            trigger_type=TriggerType(data["trigger_type"]),
            trigger_config=data.get("trigger_config", {}),
            session_strategy=SessionStrategy(data.get("session_strategy", "ephemeral")),
            version=data.get("version", 1),
            created_at=_parse_dt(data["created_at"]),
            updated_at=_parse_dt(data["updated_at"]),
            activated_at=_parse_dt(data["activated_at"]) if data.get("activated_at") else None,
            last_run_at=_parse_dt(data["last_run_at"]) if data.get("last_run_at") else None,
            run_count=data.get("run_count", 0),
            success_count=data.get("success_count", 0),
            migrated_from_order_id=data.get("migrated_from_order_id"),
        )

    @classmethod
    def from_sqlite_row(cls, row: Dict[str, Any]) -> "Workflow":
        trigger_config = row.get("trigger_config", "{}")
        if isinstance(trigger_config, str):
            trigger_config = json.loads(trigger_config)
        return cls(
            id=row["id"],
            name=row["name"],
            description=row.get("description", ""),
            status=WorkflowStatus(row["status"]),
            trigger_type=TriggerType(row["trigger_type"]),
            trigger_config=trigger_config,
            session_strategy=SessionStrategy(row.get("session_strategy", "ephemeral")),
            version=row.get("version", 1),
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
            activated_at=_parse_dt(row["activated_at"]) if row.get("activated_at") else None,
            last_run_at=_parse_dt(row["last_run_at"]) if row.get("last_run_at") else None,
            run_count=row.get("run_count", 0),
            success_count=row.get("success_count", 0),
            migrated_from_order_id=row.get("migrated_from_order_id"),
        )

    def validate(self) -> List[str]:
        errors = []
        if not self.name or len(self.name.strip()) < 1:
            errors.append("Workflow name is required")
        if len(self.name) > 200:
            errors.append("Workflow name must be 200 characters or less")
        if self.trigger_type == TriggerType.SCHEDULE and not self.trigger_config:
            errors.append("Schedule trigger requires trigger_config with cron or interval")
        return errors


@dataclass
class WorkflowNode:
    """A single node (step) in a workflow DAG."""
    id: str = field(default_factory=lambda: f"node-{uuid4().hex[:12]}")
    workflow_id: str = ""
    node_type: NodeType = NodeType.RUN_PROMPT
    label: str = "Untitled"
    config: Dict[str, Any] = field(default_factory=dict)
    position_x: float = 0.0
    position_y: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "node_type": self.node_type.value,
            "label": self.label,
            "config": self.config,
            "position_x": self.position_x,
            "position_y": self.position_y,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowNode":
        return cls(
            id=data["id"],
            workflow_id=data["workflow_id"],
            node_type=NodeType(data["node_type"]),
            label=data.get("label", "Untitled"),
            config=data.get("config", {}),
            position_x=data.get("position_x", 0.0),
            position_y=data.get("position_y", 0.0),
        )

    @classmethod
    def from_sqlite_row(cls, row: Dict[str, Any]) -> "WorkflowNode":
        config = row.get("config", "{}")
        if isinstance(config, str):
            config = json.loads(config)
        return cls(
            id=row["id"],
            workflow_id=row["workflow_id"],
            node_type=NodeType(row["node_type"]),
            label=row.get("label", "Untitled"),
            config=config,
            position_x=row.get("position_x", 0.0),
            position_y=row.get("position_y", 0.0),
        )

    def validate(self) -> List[str]:
        errors = []
        if not self.workflow_id:
            errors.append("Node must belong to a workflow")
        if not self.label or len(self.label.strip()) < 1:
            errors.append("Node label is required")
        if self.node_type == NodeType.RUN_PROMPT and not self.config.get("prompt"):
            errors.append("RunPrompt node requires a 'prompt' in config")
        if self.node_type == NodeType.CALL_TOOL and not self.config.get("tool_name"):
            errors.append("CallTool node requires a 'tool_name' in config")
        if self.node_type == NodeType.IF_ELSE and not self.config.get("condition"):
            errors.append("IfElse node requires a 'condition' in config")
        return errors


@dataclass
class WorkflowEdge:
    """A directed edge connecting two nodes in a workflow DAG."""
    id: str = field(default_factory=lambda: f"edge-{uuid4().hex[:12]}")
    workflow_id: str = ""
    source_node_id: str = ""
    target_node_id: str = ""
    edge_label: str = ""  # "true"/"false" for if_else branches

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "edge_label": self.edge_label,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowEdge":
        return cls(
            id=data["id"],
            workflow_id=data["workflow_id"],
            source_node_id=data["source_node_id"],
            target_node_id=data["target_node_id"],
            edge_label=data.get("edge_label", ""),
        )

    @classmethod
    def from_sqlite_row(cls, row: Dict[str, Any]) -> "WorkflowEdge":
        return cls(
            id=row["id"],
            workflow_id=row["workflow_id"],
            source_node_id=row["source_node_id"],
            target_node_id=row["target_node_id"],
            edge_label=row.get("edge_label", ""),
        )


@dataclass
class WorkflowRun:
    """A single execution of a workflow."""
    id: str = field(default_factory=lambda: f"run-{uuid4().hex[:12]}")
    workflow_id: str = ""
    workflow_version: int = 1
    status: RunStatus = RunStatus.PENDING
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    trigger_source: str = "manual"
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "workflow_version": self.workflow_version,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "trigger_source": self.trigger_source,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowRun":
        return cls(
            id=data["id"],
            workflow_id=data["workflow_id"],
            workflow_version=data.get("workflow_version", 1),
            status=RunStatus(data["status"]),
            started_at=_parse_dt(data["started_at"]),
            completed_at=_parse_dt(data["completed_at"]) if data.get("completed_at") else None,
            duration_ms=data.get("duration_ms"),
            trigger_source=data.get("trigger_source", "manual"),
            error_message=data.get("error_message"),
        )

    @classmethod
    def from_sqlite_row(cls, row: Dict[str, Any]) -> "WorkflowRun":
        return cls(
            id=row["id"],
            workflow_id=row["workflow_id"],
            workflow_version=row.get("workflow_version", 1),
            status=RunStatus(row["status"]),
            started_at=_parse_dt(row["started_at"]),
            completed_at=_parse_dt(row["completed_at"]) if row.get("completed_at") else None,
            duration_ms=row.get("duration_ms"),
            trigger_source=row.get("trigger_source", "manual"),
            error_message=row.get("error_message"),
        )

    def complete(self, success: bool, error_message: Optional[str] = None) -> None:
        """Mark run as completed or failed."""
        now = datetime.now(timezone.utc)
        self.completed_at = now
        self.status = RunStatus.SUCCESS if success else RunStatus.FAILED
        self.error_message = error_message
        elapsed = (now - self.started_at).total_seconds() * 1000
        self.duration_ms = round(elapsed, 1)


@dataclass
class NodeExecution:
    """Execution record for a single node within a workflow run."""
    id: str = field(default_factory=lambda: f"nexec-{uuid4().hex[:12]}")
    run_id: str = ""
    node_id: str = ""
    status: NodeExecutionStatus = NodeExecutionStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "node_id": self.node_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodeExecution":
        return cls(
            id=data["id"],
            run_id=data["run_id"],
            node_id=data["node_id"],
            status=NodeExecutionStatus(data["status"]),
            started_at=_parse_dt(data["started_at"]) if data.get("started_at") else None,
            completed_at=_parse_dt(data["completed_at"]) if data.get("completed_at") else None,
            duration_ms=data.get("duration_ms"),
            input_data=data.get("input_data", {}),
            output_data=data.get("output_data", {}),
            error_message=data.get("error_message"),
        )

    @classmethod
    def from_sqlite_row(cls, row: Dict[str, Any]) -> "NodeExecution":
        input_data = row.get("input_data", "{}")
        if isinstance(input_data, str):
            input_data = json.loads(input_data)
        output_data = row.get("output_data", "{}")
        if isinstance(output_data, str):
            output_data = json.loads(output_data)
        return cls(
            id=row["id"],
            run_id=row["run_id"],
            node_id=row["node_id"],
            status=NodeExecutionStatus(row["status"]),
            started_at=_parse_dt(row["started_at"]) if row.get("started_at") else None,
            completed_at=_parse_dt(row["completed_at"]) if row.get("completed_at") else None,
            duration_ms=row.get("duration_ms"),
            input_data=input_data,
            output_data=output_data,
            error_message=row.get("error_message"),
        )

    def start(self) -> None:
        """Mark node execution as running."""
        self.started_at = datetime.now(timezone.utc)
        self.status = NodeExecutionStatus.RUNNING

    def complete(self, output: Dict[str, Any]) -> None:
        """Mark node execution as successful."""
        now = datetime.now(timezone.utc)
        self.completed_at = now
        self.status = NodeExecutionStatus.SUCCESS
        self.output_data = output
        if self.started_at:
            self.duration_ms = round((now - self.started_at).total_seconds() * 1000, 1)

    def fail(self, error: str) -> None:
        """Mark node execution as failed."""
        now = datetime.now(timezone.utc)
        self.completed_at = now
        self.status = NodeExecutionStatus.FAILED
        self.error_message = error
        if self.started_at:
            self.duration_ms = round((now - self.started_at).total_seconds() * 1000, 1)

    def skip(self, reason: str = "Dead path") -> None:
        """Mark node execution as skipped (dead path from condition)."""
        self.status = NodeExecutionStatus.SKIPPED
        self.error_message = reason


# ── Helpers ──────────────────────────────────────────────────────────


def _parse_dt(value: Any) -> datetime:
    """Parse a datetime from ISO string or return as-is if already datetime."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # Handle both with and without timezone
        cleaned = value.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    raise ValueError(f"Cannot parse datetime from {type(value)}: {value}")
