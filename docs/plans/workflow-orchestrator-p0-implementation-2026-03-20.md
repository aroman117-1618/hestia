# Workflow Orchestrator Phase 0: Handler Adapter & Execution Wire-Up

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire Orders execution to the handler pipeline via a WorkflowHandlerAdapter, proving that background execution works and validating the integration path for P1.

**Architecture:** A `WorkflowHandlerAdapter` sits between the workflow/orders execution layer and the `RequestHandler`. It constructs synthetic `Request` objects with configurable session strategy, memory scope, and agent routing. The adapter adds a new `RequestSource.WORKFLOW` to distinguish background execution from interactive chat. Auth is not a concern — `handler.handle()` has no internal auth check (auth is a FastAPI dependency at the route level).

**Tech Stack:** Python 3.12, asyncio, existing RequestHandler, APScheduler (OrderScheduler)

**Estimated effort:** 8-10 hours

**Success criteria:** Running `POST /v1/orders/{id}/execute` on an active Order actually sends the prompt through the handler pipeline, gets an LLM response, and records it in the execution history. A pytest integration test proves the round-trip.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `hestia/workflows/__init__.py` | Create | Package init — empty for now, grows in P1 |
| `hestia/workflows/adapter.py` | Create | `WorkflowHandlerAdapter` — constructs Request, calls handler, manages session strategy and memory scope |
| `hestia/workflows/models.py` | Create | `SessionStrategy` enum, `WorkflowExecutionConfig` dataclass |
| `hestia/orchestration/models.py` | Modify | Add `WORKFLOW` to `RequestSource` enum |
| `hestia/logging/structured_logger.py` | Modify | Add `WORKFLOW` to `LogComponent` enum |
| `hestia/orders/manager.py` | Modify | Wire `execute_order()` to use `WorkflowHandlerAdapter` |
| `hestia/orders/scheduler.py` | Modify | Wire `_execute_order()` callback to call manager's real execution |
| `hestia/api/routes/orders.py` | Modify | Update `execute_order` route to return real response content |
| `scripts/auto-test.sh` | Modify | Add workflow test file mapping |
| `tests/test_workflow_adapter.py` | Create | Unit + integration tests for the adapter |

---

## Task 1: Add RequestSource.WORKFLOW and LogComponent.WORKFLOW

**Files:**
- Modify: `hestia/orchestration/models.py:46-51` (RequestSource enum)
- Modify: `hestia/logging/structured_logger.py:42-66` (LogComponent enum)

- [ ] **Step 1: Add WORKFLOW to RequestSource**

In `hestia/orchestration/models.py`, add to the `RequestSource` enum:

```python
class RequestSource(Enum):
    """Source of incoming request."""
    API = "api"
    CLI = "cli"
    IOS_SHORTCUT = "ios_shortcut"
    QUICK_CHAT = "quick_chat"
    WORKFLOW = "workflow"           # Background workflow/order execution
```

- [ ] **Step 2: Add WORKFLOW to LogComponent**

In `hestia/logging/structured_logger.py`, add to the `LogComponent` enum after NOTIFICATION:

```python
    WORKFLOW = "workflow"
```

- [ ] **Step 3: Run existing tests to verify no breakage**

Run: `python -m pytest tests/test_orchestration.py tests/test_logging.py -v --timeout=30`
Expected: All existing tests pass (enums are additive, no breaking change).

- [ ] **Step 4: Commit**

```bash
git add hestia/orchestration/models.py hestia/logging/structured_logger.py
git commit -m "feat(workflow): add WORKFLOW to RequestSource and LogComponent enums"
```

---

## Task 2: Create Workflow Models (SessionStrategy + ExecutionConfig)

**Files:**
- Create: `hestia/workflows/__init__.py`
- Create: `hestia/workflows/models.py`
- Test: `tests/test_workflow_adapter.py`

- [ ] **Step 1: Create the workflows package**

```bash
mkdir -p hestia/workflows
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_workflow_adapter.py`:

```python
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
        # PER_RUN without explicit session_id should be handled by adapter
        assert config.session_id is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_workflow_adapter.py::TestWorkflowModels -v --timeout=30`
Expected: FAIL with `ModuleNotFoundError: No module named 'hestia.workflows'`

- [ ] **Step 4: Write the implementation**

Create `hestia/workflows/__init__.py`:

```python
"""Workflow orchestration engine for Hestia."""
```

Create `hestia/workflows/models.py`:

```python
"""Data models for the workflow execution system."""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class SessionStrategy(str, Enum):
    """How workflow executions manage conversation sessions."""
    EPHEMERAL = "ephemeral"     # No session — stateless, one-shot
    PER_RUN = "per_run"         # Fresh session per workflow run
    PERSISTENT = "persistent"   # Reuse session across runs (builds context)


@dataclass
class WorkflowExecutionConfig:
    """Configuration for how a workflow node calls the handler.

    Controls session management, memory scope, agent routing,
    and tool access for background execution.
    """
    # Session strategy — how conversation state is managed
    session_strategy: SessionStrategy = SessionStrategy.EPHEMERAL

    # Explicit session ID (required for PERSISTENT, auto-generated for PER_RUN)
    session_id: Optional[str] = None

    # Memory scope
    memory_write: bool = False    # Store response in long-term memory
    memory_read: bool = True      # Include memory context in prompt

    # Inference control
    force_local: bool = False     # Force local model (skip cloud routing)
    agent_mode: Optional[str] = None  # Force specific agent ("artemis", "apollo")

    # Tool access (None = all tools available)
    allowed_tools: Optional[List[str]] = None

    # Execution metadata for audit trail
    workflow_id: Optional[str] = None
    workflow_name: Optional[str] = None
    node_id: Optional[str] = None
    run_id: Optional[str] = None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_workflow_adapter.py::TestWorkflowModels -v --timeout=30`
Expected: All 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add hestia/workflows/__init__.py hestia/workflows/models.py tests/test_workflow_adapter.py
git commit -m "feat(workflow): add SessionStrategy enum and WorkflowExecutionConfig"
```

---

## Task 3: Build the WorkflowHandlerAdapter

**Files:**
- Create: `hestia/workflows/adapter.py`
- Modify: `tests/test_workflow_adapter.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_workflow_adapter.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch
from hestia.workflows.adapter import WorkflowHandlerAdapter
from hestia.workflows.models import SessionStrategy, WorkflowExecutionConfig
from hestia.orchestration.models import RequestSource, Mode


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
        return WorkflowHandlerAdapter(handler=mock_handler)

    @pytest.mark.asyncio
    async def test_execute_basic_prompt(self, adapter, mock_handler):
        """Basic prompt execution with default config."""
        result = await adapter.execute("What's on my calendar today?")

        mock_handler.handle.assert_called_once()
        call_request = mock_handler.handle.call_args[0][0]
        assert call_request.content == "What's on my calendar today?"
        assert call_request.source == RequestSource.WORKFLOW
        assert result.content == "Test response from Hestia"

    @pytest.mark.asyncio
    async def test_ephemeral_session_generates_unique_id(self, adapter, mock_handler):
        """Ephemeral strategy generates a unique session ID per call."""
        await adapter.execute("prompt 1")
        await adapter.execute("prompt 2")

        calls = mock_handler.handle.call_args_list
        session_1 = calls[0][0][0].session_id
        session_2 = calls[1][0][0].session_id
        assert session_1 != session_2
        assert session_1.startswith("wf-eph-")

    @pytest.mark.asyncio
    async def test_per_run_session_uses_run_id(self, adapter, mock_handler):
        """PER_RUN strategy uses run_id as session basis."""
        config = WorkflowExecutionConfig(
            session_strategy=SessionStrategy.PER_RUN,
            run_id="run-abc123",
        )
        await adapter.execute("prompt", config=config)

        call_request = mock_handler.handle.call_args[0][0]
        assert call_request.session_id == "wf-run-abc123"

    @pytest.mark.asyncio
    async def test_persistent_session_reuses_id(self, adapter, mock_handler):
        """PERSISTENT strategy reuses the configured session ID."""
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
        """force_local config propagates to Request."""
        config = WorkflowExecutionConfig(force_local=True)
        await adapter.execute("prompt", config=config)

        call_request = mock_handler.handle.call_args[0][0]
        assert call_request.force_local is True

    @pytest.mark.asyncio
    async def test_agent_mode_sets_request_mode(self, adapter, mock_handler):
        """Explicit agent mode overrides default."""
        config = WorkflowExecutionConfig(agent_mode="artemis")
        await adapter.execute("analyze this", config=config)

        call_request = mock_handler.handle.call_args[0][0]
        assert call_request.mode == Mode.ARTEMIS

    @pytest.mark.asyncio
    async def test_context_hints_include_workflow_metadata(self, adapter, mock_handler):
        """Workflow metadata is passed via context_hints."""
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
        """Handler exceptions are caught and returned as error responses."""
        mock_handler.handle.side_effect = Exception("Inference failed")

        result = await adapter.execute("prompt")

        assert result.content == ""
        assert result.error_code == "workflow_execution_error"
        assert "Inference failed" in result.error_message

    @pytest.mark.asyncio
    async def test_memory_write_config_in_context_hints(self, adapter, mock_handler):
        """memory_write flag is passed to handler via context_hints."""
        config = WorkflowExecutionConfig(memory_write=True)
        await adapter.execute("remember this", config=config)

        call_request = mock_handler.handle.call_args[0][0]
        assert call_request.context_hints.get("memory_write") is True

    @pytest.mark.asyncio
    async def test_default_config_disables_memory_write(self, adapter, mock_handler):
        """Default config disables memory write."""
        await adapter.execute("don't remember this")

        call_request = mock_handler.handle.call_args[0][0]
        assert call_request.context_hints.get("memory_write") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_workflow_adapter.py::TestWorkflowHandlerAdapter -v --timeout=30`
Expected: FAIL with `ModuleNotFoundError: No module named 'hestia.workflows.adapter'`

- [ ] **Step 3: Write the implementation**

Create `hestia/workflows/adapter.py`:

```python
"""WorkflowHandlerAdapter — bridge between workflow engine and RequestHandler.

This adapter constructs synthetic Request objects for background execution,
handling session management, memory scope, and agent routing configuration.
The handler has no internal auth check (auth is at the FastAPI route level),
so the adapter can call handler.handle() directly.
"""
import uuid
from typing import Optional

from hestia.logging import get_logger
from hestia.orchestration.models import Mode, Request, RequestSource, Response
from hestia.workflows.models import SessionStrategy, WorkflowExecutionConfig

logger = get_logger()

# Mode name mapping (lowercase string -> Mode enum)
_MODE_MAP = {
    "tia": Mode.TIA,
    "hestia": Mode.TIA,
    "artemis": Mode.ARTEMIS,
    "mira": Mode.ARTEMIS,
    "apollo": Mode.APOLLO,
    "olly": Mode.APOLLO,
}


class WorkflowHandlerAdapter:
    """Adapts workflow execution requests into handler-compatible Requests.

    Sits between the workflow/orders execution layer and the RequestHandler.
    Controls session strategy, memory scope, agent routing, and tool access
    for background execution.

    Usage:
        handler = await get_request_handler()
        adapter = WorkflowHandlerAdapter(handler=handler)
        response = await adapter.execute("Summarize my email", config=config)
    """

    def __init__(self, handler) -> None:
        self._handler = handler

    async def execute(
        self,
        prompt: str,
        config: Optional[WorkflowExecutionConfig] = None,
    ) -> Response:
        """Execute a prompt through the handler pipeline.

        Args:
            prompt: The prompt text to send to the handler.
            config: Execution configuration (session, memory, agent, tools).
                    Defaults to ephemeral session, memory_read=True, memory_write=False.

        Returns:
            Response from the handler (content, metrics, errors).
        """
        if config is None:
            config = WorkflowExecutionConfig()

        request = self._build_request(prompt, config)

        logger.info(
            "Workflow adapter executing prompt",
            component="workflow",
            data={
                "request_id": request.id,
                "session_strategy": config.session_strategy.value,
                "session_id": request.session_id,
                "workflow_id": config.workflow_id,
                "node_id": config.node_id,
                "memory_write": config.memory_write,
            },
        )

        try:
            response = await self._handler.handle(request)
            logger.info(
                "Workflow adapter execution complete",
                component="workflow",
                data={
                    "request_id": request.id,
                    "tokens_in": response.tokens_in,
                    "tokens_out": response.tokens_out,
                    "duration_ms": response.duration_ms,
                },
            )
            return response
        except Exception as e:
            logger.error(
                f"Workflow adapter execution failed: {type(e).__name__}",
                component="workflow",
                data={
                    "request_id": request.id,
                    "workflow_id": config.workflow_id,
                    "node_id": config.node_id,
                },
            )
            return Response(
                request_id=request.id,
                content="",
                error_code="workflow_execution_error",
                error_message=f"Workflow execution failed: {type(e).__name__}: {e}",
            )

    def _build_request(
        self,
        prompt: str,
        config: WorkflowExecutionConfig,
    ) -> Request:
        """Construct a Request from workflow config."""
        session_id = self._resolve_session_id(config)
        mode = self._resolve_mode(config)

        context_hints = {
            "source_type": "workflow",
            "memory_write": config.memory_write,
            "memory_read": config.memory_read,
        }
        if config.workflow_id:
            context_hints["workflow_id"] = config.workflow_id
        if config.workflow_name:
            context_hints["workflow_name"] = config.workflow_name
        if config.node_id:
            context_hints["node_id"] = config.node_id
        if config.run_id:
            context_hints["run_id"] = config.run_id
        if config.allowed_tools is not None:
            context_hints["allowed_tools"] = config.allowed_tools

        return Request.create(
            content=prompt,
            mode=mode,
            source=RequestSource.WORKFLOW,
            session_id=session_id,
            force_local=config.force_local,
            context_hints=context_hints,
        )

    def _resolve_session_id(self, config: WorkflowExecutionConfig) -> str:
        """Generate or return the session ID based on strategy."""
        if config.session_strategy == SessionStrategy.EPHEMERAL:
            return f"wf-eph-{uuid.uuid4().hex[:12]}"
        elif config.session_strategy == SessionStrategy.PER_RUN:
            run_id = config.run_id or uuid.uuid4().hex[:12]
            return f"wf-run-{run_id}"
        elif config.session_strategy == SessionStrategy.PERSISTENT:
            if config.session_id:
                return config.session_id
            # Fallback: use workflow_id as session anchor
            wf_id = config.workflow_id or uuid.uuid4().hex[:12]
            return f"wf-persist-{wf_id}"
        return f"wf-{uuid.uuid4().hex[:12]}"

    def _resolve_mode(self, config: WorkflowExecutionConfig) -> Mode:
        """Resolve the agent mode from config."""
        if config.agent_mode:
            return _MODE_MAP.get(config.agent_mode.lower(), Mode.TIA)
        return Mode.TIA
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_workflow_adapter.py::TestWorkflowHandlerAdapter -v --timeout=30`
Expected: All 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add hestia/workflows/adapter.py tests/test_workflow_adapter.py
git commit -m "feat(workflow): WorkflowHandlerAdapter with session strategy and memory scope"
```

---

## Task 4: Wire execute_order() to the Adapter

**Files:**
- Modify: `hestia/orders/manager.py:470-509` (execute_order method)
- Modify: `tests/test_workflow_adapter.py` (add order execution tests)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_workflow_adapter.py`:

```python
from hestia.orders.models import Order, OrderStatus, OrderFrequency, FrequencyType


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
        """execute_order sends the order's prompt through the adapter."""
        from hestia.orders.manager import OrderManager

        manager = OrderManager(database=mock_order_db)
        adapter = WorkflowHandlerAdapter(handler=mock_handler)
        manager._workflow_adapter = adapter
        # Mock manager-level execution methods to avoid DB round-trips
        manager.start_execution = AsyncMock(return_value=mock_execution)
        manager.complete_execution = AsyncMock(return_value=mock_execution)

        execution = await manager.execute_order("order-test123")

        # Verify handler was called with the order's prompt
        mock_handler.handle.assert_called_once()
        call_request = mock_handler.handle.call_args[0][0]
        assert "Summarize my calendar and email" in call_request.content
        assert call_request.source == RequestSource.WORKFLOW

    @pytest.mark.asyncio
    async def test_execute_order_records_success(
        self, mock_order_db, mock_handler, mock_execution
    ):
        """Successful execution completes with response content."""
        from hestia.orders.manager import OrderManager

        manager = OrderManager(database=mock_order_db)
        adapter = WorkflowHandlerAdapter(handler=mock_handler)
        manager._workflow_adapter = adapter
        manager.start_execution = AsyncMock(return_value=mock_execution)
        manager.complete_execution = AsyncMock(return_value=mock_execution)

        await manager.execute_order("order-test123")

        # Verify complete_execution was called with response content
        manager.complete_execution.assert_called_once()
        call_kwargs = manager.complete_execution.call_args
        assert call_kwargs[1]["full_response"] == "Good morning! Here's your brief: 3 meetings today..."
        assert call_kwargs[1]["hestia_read"] is not None

    @pytest.mark.asyncio
    async def test_execute_order_records_failure(
        self, mock_order_db, mock_handler, mock_execution
    ):
        """Handler failure records error in execution."""
        mock_handler.handle.side_effect = Exception("Ollama unavailable")

        from hestia.orders.manager import OrderManager

        manager = OrderManager(database=mock_order_db)
        adapter = WorkflowHandlerAdapter(handler=mock_handler)
        manager._workflow_adapter = adapter
        manager.start_execution = AsyncMock(return_value=mock_execution)
        manager.fail_execution = AsyncMock(return_value=mock_execution)

        await manager.execute_order("order-test123")

        # Verify fail_execution was called with error details
        manager.fail_execution.assert_called_once()
        call_args = manager.fail_execution.call_args
        assert "Ollama unavailable" in call_args[1]["error_message"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_workflow_adapter.py::TestOrderExecution -v --timeout=30`
Expected: FAIL — `OrderManager` has no `_workflow_adapter` attribute, `execute_order` is still a stub.

- [ ] **Step 3: Modify execute_order() in manager.py**

Replace lines 470-509 of `hestia/orders/manager.py` — the stubbed `execute_order()` — with:

```python
    async def execute_order(self, order_id: str) -> "OrderExecution":
        """Execute an order by sending its prompt through the handler pipeline.

        Uses the WorkflowHandlerAdapter to construct a synthetic Request
        and route it through the full handler pipeline (council, memory,
        agent routing, tool execution).

        Args:
            order_id: The order to execute.

        Returns:
            OrderExecution with results from the handler.

        Raises:
            ValueError: If order not found or not active.
        """
        order = await self.database.get_order(order_id)
        if not order:
            raise ValueError(f"Order not found: {order_id}")

        logger.info(
            f"Executing order: {order.name}",
            component="workflow",
            data={"order_id": order_id, "status": order.status.value},
        )

        # Start execution tracking
        execution = await self.start_execution(order_id)

        try:
            # Get or create the adapter
            adapter = await self._get_adapter()

            # Build execution config for this order
            config = WorkflowExecutionConfig(
                session_strategy=SessionStrategy.PER_RUN,
                run_id=execution.id,
                workflow_id=order_id,
                workflow_name=order.name,
                memory_write=False,
                memory_read=True,
            )

            # Execute through the handler pipeline
            response = await adapter.execute(order.prompt, config=config)

            # Check for errors
            if response.error_code:
                execution = await self.fail_execution(
                    execution.id,
                    error_message=response.error_message or "Unknown error",
                )
                return execution

            # Generate a concise "hestia_read" summary (first 500 chars)
            hestia_read = response.content[:500] if response.content else ""

            # Record success
            execution = await self.complete_execution(
                execution.id,
                hestia_read=hestia_read,
                full_response=response.content,
            )

            logger.info(
                f"Order executed successfully: {order.name}",
                component="workflow",
                data={
                    "order_id": order_id,
                    "execution_id": execution.id,
                    "tokens_in": response.tokens_in,
                    "tokens_out": response.tokens_out,
                    "duration_ms": response.duration_ms,
                },
            )

            return execution

        except Exception as e:
            logger.error(
                f"Order execution failed: {type(e).__name__}",
                component="workflow",
                data={"order_id": order_id, "execution_id": execution.id},
            )
            execution = await self.fail_execution(
                execution.id,
                error_message=f"{type(e).__name__}: {e}",
            )
            return execution

    async def _get_adapter(self) -> "WorkflowHandlerAdapter":
        """Get or create the workflow handler adapter."""
        if hasattr(self, "_workflow_adapter") and self._workflow_adapter:
            return self._workflow_adapter

        from hestia.orchestration.handler import get_request_handler
        from hestia.workflows.adapter import WorkflowHandlerAdapter

        handler = await get_request_handler()
        self._workflow_adapter = WorkflowHandlerAdapter(handler=handler)
        return self._workflow_adapter
```

Also add these imports at the top of `hestia/orders/manager.py`:

```python
from hestia.workflows.models import SessionStrategy, WorkflowExecutionConfig
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_workflow_adapter.py::TestOrderExecution -v --timeout=30`
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add hestia/orders/manager.py tests/test_workflow_adapter.py
git commit -m "feat(workflow): wire execute_order() to WorkflowHandlerAdapter — replaces stub (ADR-021)"
```

---

## Task 5: Wire the OrderScheduler Callback

**Files:**
- Modify: `hestia/orders/scheduler.py:256-284` (_execute_order callback)
- Modify: `tests/test_workflow_adapter.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_workflow_adapter.py`:

```python
class TestSchedulerCallback:
    """Test that the APScheduler callback routes through real execution."""

    @pytest.mark.asyncio
    async def test_scheduler_callback_calls_execute_order(self):
        """APScheduler callback should call manager.execute_order()."""
        from hestia.orders.scheduler import OrderScheduler

        mock_manager = AsyncMock()
        mock_manager.execute_order = AsyncMock()
        mock_manager.get_order = AsyncMock(return_value=MagicMock(
            status=OrderStatus.ACTIVE
        ))

        scheduler = OrderScheduler(manager=mock_manager)
        await scheduler._execute_order("order-test123")

        mock_manager.execute_order.assert_called_once_with("order-test123")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_workflow_adapter.py::TestSchedulerCallback -v --timeout=30`
Expected: FAIL — current `_execute_order` doesn't call `manager.execute_order()` or calls the stubbed version.

- [ ] **Step 3: Update the scheduler callback**

In `hestia/orders/scheduler.py`, replace the `_execute_order` method (lines 256-284) with:

```python
    async def _execute_order(self, order_id: str) -> None:
        """APScheduler callback — execute an order through the handler pipeline.

        Called by APScheduler when a trigger fires. Routes through
        OrderManager.execute_order() which uses the WorkflowHandlerAdapter.
        """
        try:
            order = await self.manager.get_order(order_id)
            if not order or order.status != OrderStatus.ACTIVE:
                logger.warning(
                    f"Skipping execution — order inactive or not found",
                    component="workflow",
                    data={"order_id": order_id},
                )
                return

            logger.info(
                f"Scheduled execution triggered: {order.name}",
                component="workflow",
                data={"order_id": order_id},
            )

            await self.manager.execute_order(order_id)

        except Exception as e:
            logger.error(
                f"Scheduled execution failed: {type(e).__name__}",
                component="workflow",
                data={"order_id": order_id},
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_workflow_adapter.py::TestSchedulerCallback -v --timeout=30`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add hestia/orders/scheduler.py tests/test_workflow_adapter.py
git commit -m "feat(workflow): wire OrderScheduler callback to real execution pipeline"
```

---

## Task 6: Update the Execute API Route

**Files:**
- Modify: `hestia/api/routes/orders.py:484-521`
- Modify: `tests/test_workflow_adapter.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_workflow_adapter.py`:

```python
class TestExecuteRoute:
    """Test the /v1/orders/{id}/execute API response includes real content."""

    @pytest.mark.asyncio
    async def test_execute_response_includes_content(self):
        """The execute endpoint should return the handler's response content."""
        from hestia.orders.models import OrderExecution, ExecutionStatus

        # Create a completed execution with real content
        execution = OrderExecution(
            id="exec-abc",
            order_id="order-123",
            timestamp="2026-03-20T08:00:00Z",
            status=ExecutionStatus.SUCCESS,
            hestia_read="Good morning! You have 3 meetings today.",
            full_response="Good morning! You have 3 meetings today. Here are the details...",
        )

        assert execution.hestia_read is not None
        assert "3 meetings" in execution.hestia_read
        assert execution.status == ExecutionStatus.SUCCESS
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python -m pytest tests/test_workflow_adapter.py::TestExecuteRoute -v --timeout=30`
Expected: PASS (this is a smoke test for the data model — the real route test would require a running server).

- [ ] **Step 3: Update the execute route to include response content**

The current `OrderExecuteResponse` schema has: `order_id`, `execution_id`, `status`, `message`. The `message` field is hardcoded to "Order execution started". Now that execution is real, update the route to include the actual response.

In `hestia/api/routes/orders.py`, update lines 510-515:

```python
        # Build message from execution result
        if execution.status == ExecutionStatus.SUCCESS:
            message = execution.hestia_read or "Order executed successfully"
        elif execution.status == ExecutionStatus.FAILED:
            message = f"Execution failed: {execution.error_message or 'Unknown error'}"
        else:
            message = f"Execution status: {execution.status.value}"

        return OrderExecuteResponse(
            order_id=order_id,
            execution_id=execution.id,
            status=ExecutionStatusEnum(execution.status.value),
            message=message,
        )
```

Also add the import at the top of the route file if not present:
```python
from hestia.orders.models import ExecutionStatus
```

- [ ] **Step 4: Commit**

```bash
git add hestia/api/routes/orders.py tests/test_workflow_adapter.py
git commit -m "feat(workflow): update execute route to return real handler response"
```

---

## Task 7: Update auto-test.sh Mapping

**Files:**
- Modify: `scripts/auto-test.sh`

- [ ] **Step 1: Add workflow mapping to auto-test.sh**

Add to the `get_test_file()` case statement in `scripts/auto-test.sh`:

```bash
    hestia/workflows/*)
        echo "tests/test_workflow_adapter.py"
        ;;
```

- [ ] **Step 2: Commit**

```bash
git add scripts/auto-test.sh
git commit -m "chore: add workflow module to auto-test.sh mapping"
```

---

## Task 8: Full Test Suite Validation

- [ ] **Step 1: Run the complete test suite**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: All tests pass (existing + 18 new workflow adapter tests). No regressions.

- [ ] **Step 2: Run the workflow tests in isolation**

Run: `python -m pytest tests/test_workflow_adapter.py -v --timeout=30`
Expected: 18 tests pass:
- TestWorkflowModels: 4 tests
- TestWorkflowHandlerAdapter: 10 tests
- TestOrderExecution: 3 tests
- TestSchedulerCallback: 1 test

- [ ] **Step 3: Verify the handler integration assumption**

This is the critical validation: can `handler.handle()` be called with a synthetic Request that has no HTTP context?

Run: `python -m pytest tests/test_workflow_adapter.py -v -k "handler" --timeout=30`

If all handler adapter tests pass with mocked handler, the integration is proven at the unit level. For the live validation (calling the real handler with a real Ollama model), that happens on the Mac Mini after deploy.

- [ ] **Step 4: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "test: validate full test suite with workflow adapter integration"
```

---

## Roadmap: P1-P4 Overview (Separate Plans)

This section outlines what comes next. Each phase gets its own implementation plan.

### P1: DAG Engine + List UI (~30-38h) — Next Plan

**Backend:**
- `hestia/workflows/database.py` — SQLite tables (workflows, workflow_nodes, workflow_edges, workflow_runs, node_executions, workflow_versions)
- `hestia/workflows/manager.py` — WorkflowManager singleton (CRUD, version snapshotting, 20-node limit)
- `hestia/workflows/executor.py` — DAGExecutor (TaskGroup, dead path elimination, SQLite checkpointing)
- `hestia/workflows/scheduler.py` — WorkflowScheduler (APScheduler + trigger registration)
- `hestia/workflows/nodes/actions.py` — RunPrompt (via adapter), CallTool, Notify, Log
- `hestia/workflows/nodes/triggers.py` — Schedule, Manual
- `hestia/workflows/nodes/conditions.py` — IfElse (simple expression evaluator)
- `hestia/workflows/nodes/registry.py` — NodeRegistry (subtype → implementation)
- `hestia/workflows/semaphore.py` — Global inference semaphore (max N concurrent Ollama calls)
- `hestia/workflows/migration.py` — Orders → Workflows migration
- `hestia/api/routes/workflows.py` — 12 REST endpoints + 1 SSE endpoint
- `hestia/config/workflows.yaml` — Configuration
- Cycle detection at save time, fan-in data merging, retention policy on node_executions

**macOS UI:**
- WorkflowListView (replaces OrdersPanel)
- WorkflowDetailView (node list, drag to reorder, config forms)
- WorkflowRunHistoryView (execution history with per-node status inspection)
- SSE-driven execution feedback

**Tests:** ~80-100 new tests

### P2: WebView + React Flow Canvas (~25-35h)

**Frontend (React):**
- React Flow canvas with custom node types (Trigger, Action, Condition, Control)
- Node palette sidebar, inspector panel
- Click-click connection model
- Real-time execution feedback (green/red borders via SSE)
- Data pinning (persist output, replay from pin)

**macOS Integration:**
- WKWebView wrapper in SwiftUI
- JavaScript bridge for workflow CRUD (Swift ↔ React)
- Sugiyama auto-layout via dagre (JS library, not GraphKit)

**Backend:**
- Switch condition node, Confidence Gate
- Variable interpolation (`{{node.output.field}}`)
- Sub-Workflow node
- Code node (sandboxed Python via existing Sandbox)

### P3: Events + Trading Integration (~18-22h)

**Backend:**
- `hestia/workflows/event_bus.py` — Generic EventBus (callback-based, not queue-based)
- Email, Calendar, Health, Webhook trigger nodes
- Market Condition trigger (subscribes to TradingEventBus)
- Start/Stop/Pause Bot action nodes (thin wrappers around BotOrchestrator)
- HMAC-SHA256 webhook authentication
- Token budget enforcement
- Keyed debouncing

### P4: Polish + Templates (~8-10h)

- 6 pre-built workflow templates
- Export/import (JSON)
- Duplicate workflow
- Execution replay with checkpoint visualization
- Keyboard shortcuts
- iOS summary view (read-only workflow status)
