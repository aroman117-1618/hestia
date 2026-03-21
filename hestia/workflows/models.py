"""Data models for the workflow execution system."""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


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
