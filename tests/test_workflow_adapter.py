"""Tests for the WorkflowHandlerAdapter and supporting models."""
import pytest
from unittest.mock import AsyncMock, MagicMock
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


class TestWorkflowHandlerAdapter:
    """Test the handler adapter for workflow execution."""

    @pytest.fixture
    def mock_handler(self):
        handler = AsyncMock()
        handler.handle = AsyncMock(return_value=MagicMock(
            content="Test response from Hestia",
            request_id="req-test123",
            tokens_in=10,
            tokens_out=20,
            duration_ms=150.0,
        ))
        return handler

    @pytest.fixture
    def adapter(self, mock_handler):
        from hestia.workflows.adapter import WorkflowHandlerAdapter
        return WorkflowHandlerAdapter(handler=mock_handler)

    @pytest.mark.asyncio
    async def test_execute_basic_prompt(self, adapter, mock_handler):
        from hestia.orchestration.models import RequestSource
        result = await adapter.execute("What's on my calendar today?")
        mock_handler.handle.assert_called_once()
        call_request = mock_handler.handle.call_args[0][0]
        assert call_request.content == "What's on my calendar today?"
        assert call_request.source == RequestSource.WORKFLOW
        assert result.content == "Test response from Hestia"

    @pytest.mark.asyncio
    async def test_ephemeral_session_generates_unique_id(self, adapter, mock_handler):
        await adapter.execute("prompt 1")
        await adapter.execute("prompt 2")
        calls = mock_handler.handle.call_args_list
        session_1 = calls[0][0][0].session_id
        session_2 = calls[1][0][0].session_id
        assert session_1 != session_2
        assert session_1.startswith("wf-eph-")

    @pytest.mark.asyncio
    async def test_per_run_session_uses_run_id(self, adapter, mock_handler):
        config = WorkflowExecutionConfig(
            session_strategy=SessionStrategy.PER_RUN,
            run_id="run-abc123",
        )
        await adapter.execute("prompt", config=config)
        call_request = mock_handler.handle.call_args[0][0]
        assert call_request.session_id == "wf-run-run-abc123"

    @pytest.mark.asyncio
    async def test_persistent_session_reuses_id(self, adapter, mock_handler):
        config = WorkflowExecutionConfig(
            session_strategy=SessionStrategy.PERSISTENT,
            session_id="wf-morning-brief",
        )
        await adapter.execute("day 1", config=config)
        await adapter.execute("day 2", config=config)
        calls = mock_handler.handle.call_args_list
        assert calls[0][0][0].session_id == "wf-morning-brief"
        assert calls[1][0][0].session_id == "wf-morning-brief"

    @pytest.mark.asyncio
    async def test_force_local_propagates(self, adapter, mock_handler):
        config = WorkflowExecutionConfig(force_local=True)
        await adapter.execute("prompt", config=config)
        call_request = mock_handler.handle.call_args[0][0]
        assert call_request.force_local is True

    @pytest.mark.asyncio
    async def test_agent_mode_sets_request_mode(self, adapter, mock_handler):
        from hestia.orchestration.models import Mode
        config = WorkflowExecutionConfig(agent_mode="artemis")
        await adapter.execute("analyze this", config=config)
        call_request = mock_handler.handle.call_args[0][0]
        # artemis maps to Mode.MIRA (analysis persona)
        assert call_request.mode == Mode.MIRA

    @pytest.mark.asyncio
    async def test_context_hints_include_workflow_metadata(self, adapter, mock_handler):
        config = WorkflowExecutionConfig(
            workflow_id="wf-abc123",
            workflow_name="Morning Brief",
            node_id="node-xyz",
            run_id="run-456",
        )
        await adapter.execute("prompt", config=config)
        call_request = mock_handler.handle.call_args[0][0]
        assert call_request.context_hints["workflow_id"] == "wf-abc123"
        assert call_request.context_hints["workflow_name"] == "Morning Brief"
        assert call_request.context_hints["node_id"] == "node-xyz"
        assert call_request.context_hints["run_id"] == "run-456"
        assert call_request.context_hints["source_type"] == "workflow"

    @pytest.mark.asyncio
    async def test_handler_error_returns_error_response(self, adapter, mock_handler):
        mock_handler.handle.side_effect = Exception("Inference failed")
        result = await adapter.execute("prompt")
        assert result.content == ""
        assert result.error_code == "workflow_execution_error"
        assert "Inference failed" in result.error_message

    @pytest.mark.asyncio
    async def test_memory_write_config_in_context_hints(self, adapter, mock_handler):
        config = WorkflowExecutionConfig(memory_write=True)
        await adapter.execute("remember this", config=config)
        call_request = mock_handler.handle.call_args[0][0]
        assert call_request.context_hints.get("memory_write") is True

    @pytest.mark.asyncio
    async def test_default_config_disables_memory_write(self, adapter, mock_handler):
        await adapter.execute("don't remember this")
        call_request = mock_handler.handle.call_args[0][0]
        assert call_request.context_hints.get("memory_write") is False


from hestia.orders.models import Order, OrderStatus, OrderFrequency, FrequencyType
from hestia.orchestration.models import RequestSource


class TestOrderExecution:
    """Test that Orders wire through the adapter to the handler.

    These tests mock at the manager level (start_execution, complete_execution,
    fail_execution) rather than the DB layer, because the manager methods have
    internal get_execution calls that would need deep DB mocking.
    """

    @pytest.fixture
    def mock_order_db(self):
        db = AsyncMock()
        db.get_order = AsyncMock(return_value=Order(
            id="order-test123",
            name="Morning Brief",
            prompt="Summarize my calendar and email for today",
            scheduled_time="08:00",
            frequency=OrderFrequency(type=FrequencyType.DAILY),
            resources=set(),
            status=OrderStatus.ACTIVE,
            created_at="2026-03-20T00:00:00Z",
            updated_at="2026-03-20T00:00:00Z",
        ))
        return db

    @pytest.fixture
    def mock_handler(self):
        handler = AsyncMock()
        handler.handle = AsyncMock(return_value=MagicMock(
            content="Good morning! Here's your brief: 3 meetings today...",
            request_id="req-test123",
            tokens_in=50,
            tokens_out=100,
            duration_ms=1200.0,
            error_code=None,
        ))
        return handler

    @pytest.fixture
    def mock_execution(self):
        from hestia.orders.models import OrderExecution, ExecutionStatus
        return OrderExecution(
            id="exec-abc123",
            order_id="order-test123",
            timestamp="2026-03-20T08:00:00Z",
            status=ExecutionStatus.RUNNING,
        )

    @pytest.mark.asyncio
    async def test_execute_order_calls_handler_with_prompt(
        self, mock_order_db, mock_handler, mock_execution
    ):
        from hestia.orders.manager import OrderManager
        from hestia.workflows.adapter import WorkflowHandlerAdapter
        manager = OrderManager(database=mock_order_db)
        adapter = WorkflowHandlerAdapter(handler=mock_handler)
        manager._workflow_adapter = adapter
        manager.start_execution = AsyncMock(return_value=mock_execution)
        manager.complete_execution = AsyncMock(return_value=mock_execution)

        execution = await manager.execute_order("order-test123")

        mock_handler.handle.assert_called_once()
        call_request = mock_handler.handle.call_args[0][0]
        assert "Summarize my calendar and email" in call_request.content
        assert call_request.source == RequestSource.WORKFLOW

    @pytest.mark.asyncio
    async def test_execute_order_records_success(
        self, mock_order_db, mock_handler, mock_execution
    ):
        from hestia.orders.manager import OrderManager
        from hestia.workflows.adapter import WorkflowHandlerAdapter
        manager = OrderManager(database=mock_order_db)
        adapter = WorkflowHandlerAdapter(handler=mock_handler)
        manager._workflow_adapter = adapter
        manager.start_execution = AsyncMock(return_value=mock_execution)
        manager.complete_execution = AsyncMock(return_value=mock_execution)

        await manager.execute_order("order-test123")

        manager.complete_execution.assert_called_once()
        call_kwargs = manager.complete_execution.call_args
        assert call_kwargs[1]["full_response"] == "Good morning! Here's your brief: 3 meetings today..."
        assert call_kwargs[1]["hestia_read"] is not None

    @pytest.mark.asyncio
    async def test_execute_order_records_failure(
        self, mock_order_db, mock_handler, mock_execution
    ):
        mock_handler.handle.side_effect = Exception("Ollama unavailable")
        from hestia.orders.manager import OrderManager
        from hestia.workflows.adapter import WorkflowHandlerAdapter
        manager = OrderManager(database=mock_order_db)
        adapter = WorkflowHandlerAdapter(handler=mock_handler)
        manager._workflow_adapter = adapter
        manager.start_execution = AsyncMock(return_value=mock_execution)
        manager.fail_execution = AsyncMock(return_value=mock_execution)

        await manager.execute_order("order-test123")

        manager.fail_execution.assert_called_once()
        call_args = manager.fail_execution.call_args
        assert "Ollama unavailable" in call_args[1]["error_message"]
