"""Tests for the WorkflowHandlerAdapter and supporting models."""
import pytest
from hestia.workflows.models import SessionStrategy, WorkflowExecutionConfig


class TestWorkflowModels:
    """Test workflow execution configuration models."""

    def test_session_strategy_enum_values(self):
        assert SessionStrategy.EPHEMERAL.value == "ephemeral"
        assert SessionStrategy.PER_RUN.value == "per_run"
        assert SessionStrategy.PERSISTENT.value == "persistent"

    def test_default_execution_config(self):
        config = WorkflowExecutionConfig()
        assert config.session_strategy == SessionStrategy.EPHEMERAL
        assert config.memory_write is False
        assert config.memory_read is True
        assert config.force_local is False
        assert config.agent_mode is None
        assert config.allowed_tools is None

    def test_execution_config_custom(self):
        config = WorkflowExecutionConfig(
            session_strategy=SessionStrategy.PERSISTENT,
            session_id="wf-morning-brief",
            memory_write=True,
            force_local=True,
            agent_mode="artemis",
            allowed_tools=["calendar", "email"],
        )
        assert config.session_strategy == SessionStrategy.PERSISTENT
        assert config.session_id == "wf-morning-brief"
        assert config.memory_write is True
        assert config.force_local is True
        assert config.agent_mode == "artemis"
        assert config.allowed_tools == ["calendar", "email"]

    def test_execution_config_generates_session_id_for_per_run(self):
        config = WorkflowExecutionConfig(
            session_strategy=SessionStrategy.PER_RUN
        )
        assert config.session_id is None
