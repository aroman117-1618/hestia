"""Tests for the multi-turn tool loop in RequestHandler._execute_tool_loop().

Verifies:
1. Loop iterates when inference returns tool_calls, stops when it doesn't
2. Iteration limit is respected
3. Circuit breaker triggers on consecutive failures
4. Non-workflow requests use single-turn path (unchanged)
5. Message format includes prompt injection markers and tool_call_id
6. Token counts are accumulated across iterations

Run with: python -m pytest tests/test_tool_loop.py -v
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from hestia.orchestration.models import Request, RequestSource, Mode, Response
from hestia.inference.client import InferenceResponse, Message


# ── Helpers ──────────────────────────────────────────────────────────


def _make_inference_response(
    content: str = "",
    tool_calls: list = None,
    tokens_in: int = 100,
    tokens_out: int = 50,
    finish_reason: str = "stop",
    model: str = "claude-sonnet-4-20250514",
) -> InferenceResponse:
    """Create a real InferenceResponse (not a mock)."""
    return InferenceResponse(
        content=content,
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        duration_ms=500.0,
        finish_reason=finish_reason,
        tool_calls=tool_calls,
        inference_source="cloud",
    )


def _make_tool_call(name: str, arguments: dict = None, call_id: str = "") -> dict:
    """Create a tool call in Ollama-normalized format."""
    tc = {"function": {"name": name, "arguments": arguments or {}}}
    if call_id:
        tc["id"] = call_id
    return tc


def _make_workflow_request(content: str = "Run evening research") -> Request:
    """Create a workflow-sourced request."""
    return Request.create(
        content=content,
        mode=Mode.TIA,
        source=RequestSource.WORKFLOW,
        context_hints={
            "source_type": "workflow",
            "allowed_tools": ["list_events", "investigate_url", "create_note"],
            "inference_route": "full_cloud",
        },
    )


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def handler():
    """Create a RequestHandler with mocked dependencies for tool loop testing."""
    with patch("hestia.orchestration.handler.get_tool_registry") as mock_reg, \
         patch("hestia.orchestration.handler.get_tool_executor", new_callable=AsyncMock):

        from hestia.orchestration.handler import RequestHandler

        # Mock memory
        mem = MagicMock()
        mem.build_context = AsyncMock(return_value="")
        mem.build_context_with_score = AsyncMock(return_value=("", 0.0))

        # Mock inference — default: no tool calls
        inf = MagicMock()
        inf.chat = AsyncMock(return_value=_make_inference_response(
            content="Done."
        ))

        # Mock prompt builder
        pb = MagicMock()
        pb.build = MagicMock(return_value=(
            [Message(role="system", content="You are Hestia."),
             Message(role="user", content="placeholder")],
            MagicMock(),
        ))

        # Mock state machine — run_with_timeout must await the async fn
        async def _mock_run_with_timeout(task, fn, **kwargs):
            return await fn(**kwargs)

        sm = MagicMock()
        sm.create_task = MagicMock(return_value=MagicMock())
        sm.run_with_timeout = _mock_run_with_timeout
        sm.await_tool = MagicMock()
        sm.resume_processing = MagicMock()

        h = RequestHandler.__new__(RequestHandler)
        h._memory_manager = mem
        h._inference_client = inf
        h._prompt_builder = pb
        h.state_machine = sm
        h.logger = MagicMock()

        # Mock tool registry
        registry = MagicMock()
        registry.has_tool = MagicMock(return_value=True)
        registry.get_definitions_as_list = MagicMock(return_value=[])
        mock_reg.return_value = registry

        yield h


# ── Tests ────────────────────────────────────────────────────────────


class TestExecuteToolLoop:
    """Test _execute_tool_loop() directly."""

    @pytest.mark.asyncio
    async def test_two_iteration_loop(self, handler):
        """Model calls a tool, sees result, then produces final text."""
        # Iteration 1: model returns tool_calls
        first_response = _make_inference_response(
            content="I'll check the calendar.",
            tool_calls=[_make_tool_call("list_events", {"date": "today"}, "tc-001")],
            tokens_in=100,
            tokens_out=50,
        )
        # Iteration 2: model returns final text (no tool_calls)
        final_response = _make_inference_response(
            content="You have 3 meetings today.",
            tokens_in=200,
            tokens_out=100,
        )

        # Mock _execute_native_tool_calls
        handler._execute_native_tool_calls = AsyncMock(
            return_value='[{"title": "Standup", "time": "9am"}]'
        )
        # Mock inference to return final_response on re-call
        handler.inference_client.chat = AsyncMock(return_value=final_response)

        request = _make_workflow_request()
        task = MagicMock()
        messages = [Message(role="user", content="Run evening research")]

        result = await handler._execute_tool_loop(
            inference_response=first_response,
            messages=messages,
            request=request,
            task=task,
            tool_definitions=[],
            temperature=0.7,
            max_tokens=4096,
            force_cloud=True,
        )

        # Verify: loop ran 1 iteration, final response returned
        assert result.content == "You have 3 meetings today."
        assert result.tokens_in == 300  # 100 + 200
        assert result.tokens_out == 150  # 50 + 100
        handler._execute_native_tool_calls.assert_called_once()
        handler.inference_client.chat.assert_called_once()

        # Verify messages were appended (assistant + tool result)
        assert len(messages) == 3  # original + assistant + tool result
        assert messages[1].role == "assistant"
        assert messages[1].tool_calls == first_response.tool_calls
        assert messages[2].role == "user"
        assert "[TOOL DATA" in messages[2].content
        assert "[END TOOL DATA]" in messages[2].content
        assert messages[2].tool_call_id == "tc-001"

    @pytest.mark.asyncio
    async def test_three_iteration_chain(self, handler):
        """Model chains 3 tool calls: list_events → investigate_url → create_note."""
        responses = [
            # After list_events: model wants to investigate
            _make_inference_response(
                content="Found events. Let me research.",
                tool_calls=[_make_tool_call("investigate_url", {"url": "https://example.com"})],
                tokens_in=150, tokens_out=60,
            ),
            # After investigate_url: model wants to create note
            _make_inference_response(
                content="Research complete. Creating note.",
                tool_calls=[_make_tool_call("create_note", {"title": "Research", "body": "..."})],
                tokens_in=200, tokens_out=80,
            ),
            # Final: no more tool calls
            _make_inference_response(
                content="Evening research complete. Note created.",
                tokens_in=100, tokens_out=40,
            ),
        ]

        handler._execute_native_tool_calls = AsyncMock(
            side_effect=["Calendar data...", "Article content...", "Note created"]
        )
        handler.inference_client.chat = AsyncMock(side_effect=responses)

        request = _make_workflow_request()
        first_response = _make_inference_response(
            content="Starting research.",
            tool_calls=[_make_tool_call("list_events", {"date": "today"})],
            tokens_in=100, tokens_out=50,
        )

        result = await handler._execute_tool_loop(
            inference_response=first_response,
            messages=[Message(role="user", content="Run research")],
            request=request,
            task=MagicMock(),
            tool_definitions=[],
            temperature=0.7,
            max_tokens=4096,
            force_cloud=True,
        )

        assert result.content == "Evening research complete. Note created."
        assert result.tokens_in == 100 + 150 + 200 + 100  # All accumulated
        assert result.tokens_out == 50 + 60 + 80 + 40
        assert handler._execute_native_tool_calls.call_count == 3
        assert handler.inference_client.chat.call_count == 3

    @pytest.mark.asyncio
    async def test_max_iterations_limit(self, handler):
        """Loop breaks at MAX_TOOL_ITERATIONS even if model keeps calling tools."""
        # Every response returns tool_calls — should stop at MAX_TOOL_ITERATIONS
        always_tool_response = _make_inference_response(
            content="Calling another tool...",
            tool_calls=[_make_tool_call("list_events")],
            tokens_in=50, tokens_out=20,
        )
        handler._execute_native_tool_calls = AsyncMock(return_value="tool result")
        handler.inference_client.chat = AsyncMock(return_value=always_tool_response)

        request = _make_workflow_request()
        result = await handler._execute_tool_loop(
            inference_response=always_tool_response,
            messages=[Message(role="user", content="test")],
            request=request,
            task=MagicMock(),
            tool_definitions=[],
            temperature=0.7,
            max_tokens=4096,
            force_cloud=True,
        )

        # Should have hit the limit
        assert handler._execute_native_tool_calls.call_count == handler.MAX_TOOL_ITERATIONS
        # Logger should have logged the exit reason
        handler.logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_circuit_breaker_on_consecutive_failures(self, handler):
        """Loop breaks after 3 consecutive tool failures."""
        tool_response = _make_inference_response(
            content="",
            tool_calls=[_make_tool_call("broken_tool")],
            tokens_in=50, tokens_out=20,
        )
        # All tool calls fail
        handler._execute_native_tool_calls = AsyncMock(
            return_value="Tool broken_tool failed: connection refused"
        )
        handler.inference_client.chat = AsyncMock(return_value=tool_response)

        request = _make_workflow_request()
        result = await handler._execute_tool_loop(
            inference_response=tool_response,
            messages=[Message(role="user", content="test")],
            request=request,
            task=MagicMock(),
            tool_definitions=[],
            temperature=0.7,
            max_tokens=4096,
            force_cloud=True,
        )

        # Should have stopped after 3 failures, not MAX_TOOL_ITERATIONS
        assert handler._execute_native_tool_calls.call_count == 3
        # Circuit breaker warning logged
        handler.logger.warning.assert_called()
        warning_msg = handler.logger.warning.call_args[0][0]
        assert "circuit breaker" in warning_msg.lower()

    @pytest.mark.asyncio
    async def test_no_tool_calls_returns_immediately(self, handler):
        """If initial response has no tool_calls, returns unchanged."""
        response = _make_inference_response(content="Just a text response.")

        result = await handler._execute_tool_loop(
            inference_response=response,
            messages=[Message(role="user", content="test")],
            request=_make_workflow_request(),
            task=MagicMock(),
            tool_definitions=[],
            temperature=0.7,
            max_tokens=4096,
            force_cloud=True,
        )

        assert result is response  # Same object, no loop executed
        assert result.content == "Just a text response."
        handler.logger.info.assert_not_called()  # No iteration logging

    @pytest.mark.asyncio
    async def test_tool_result_none_counts_as_failure(self, handler):
        """None tool result triggers circuit breaker."""
        tool_response = _make_inference_response(
            content="",
            tool_calls=[_make_tool_call("unknown_tool")],
        )
        handler._execute_native_tool_calls = AsyncMock(return_value=None)
        handler.inference_client.chat = AsyncMock(return_value=tool_response)

        request = _make_workflow_request()
        await handler._execute_tool_loop(
            inference_response=tool_response,
            messages=[Message(role="user", content="test")],
            request=request,
            task=MagicMock(),
            tool_definitions=[],
            temperature=0.7,
            max_tokens=4096,
            force_cloud=True,
        )

        # None results count as failures → circuit breaker at 3
        assert handler._execute_native_tool_calls.call_count == 3

    @pytest.mark.asyncio
    async def test_failure_counter_resets_on_success(self, handler):
        """A successful tool call resets the consecutive failure counter."""
        fail_response = _make_inference_response(
            content="", tool_calls=[_make_tool_call("tool1")],
        )
        success_response = _make_inference_response(
            content="", tool_calls=[_make_tool_call("tool2")],
        )
        final_response = _make_inference_response(content="Done.")

        # Pattern: fail, fail, succeed, fail, fail, succeed → should NOT trigger breaker
        handler._execute_native_tool_calls = AsyncMock(side_effect=[
            "Tool tool1 failed: error",  # fail 1
            "Tool tool1 failed: error",  # fail 2
            "Good result",               # success → resets counter
            "Tool tool2 failed: error",  # fail 1
            "Tool tool2 failed: error",  # fail 2
            "Good result",               # success → resets counter
        ])
        handler.inference_client.chat = AsyncMock(side_effect=[
            fail_response, fail_response, success_response,
            fail_response, fail_response, final_response,
        ])

        request = _make_workflow_request()
        result = await handler._execute_tool_loop(
            inference_response=fail_response,
            messages=[Message(role="user", content="test")],
            request=request,
            task=MagicMock(),
            tool_definitions=[],
            temperature=0.7,
            max_tokens=4096,
            force_cloud=True,
        )

        # All 6 iterations ran (no circuit breaker)
        assert handler._execute_native_tool_calls.call_count == 6
        assert result.content == "Done."


class TestToolLoopIntegration:
    """Test that _run_inference_with_retry routes workflow requests to the tool loop."""

    @pytest.mark.asyncio
    async def test_workflow_request_uses_tool_loop(self, handler):
        """Workflow requests with tool_calls go through _execute_tool_loop."""
        handler._execute_tool_loop = AsyncMock(return_value=_make_inference_response(
            content="Research complete.", tokens_in=500, tokens_out=200,
        ))

        # Mock the full handler pipeline dependencies
        handler._mode_manager = MagicMock()
        handler._mode_manager.get_temperature = MagicMock(return_value=0.7)
        handler._prompt_builder = MagicMock()
        handler._prompt_builder.estimate_response_budget = MagicMock(return_value=4096)
        handler._validation_pipeline = MagicMock()
        handler._validation_pipeline.validate_response = MagicMock(
            return_value=MagicMock(valid=True)
        )
        handler._get_council_manager = MagicMock()

        # Inference returns tool_calls
        tool_response = _make_inference_response(
            content="", tool_calls=[_make_tool_call("list_events")],
        )
        handler.inference_client.chat = AsyncMock(return_value=tool_response)

        request = _make_workflow_request()
        task = MagicMock()
        messages = [Message(role="user", content="Run research")]

        response = await handler._run_inference_with_retry(
            task=task,
            request=request,
            messages=messages,
            prompt_components=MagicMock(),
        )

        # Verify tool loop was called
        handler._execute_tool_loop.assert_called_once()
        assert response.content == "Research complete."

    @pytest.mark.asyncio
    async def test_non_workflow_request_skips_tool_loop(self, handler):
        """Non-workflow requests do NOT use the tool loop — single-turn path."""
        handler._execute_tool_loop = AsyncMock()
        handler._execute_native_tool_calls = AsyncMock(return_value="Calendar data")
        handler._format_tool_result_with_personality = AsyncMock(
            return_value="You have 3 meetings."
        )

        handler._mode_manager = MagicMock()
        handler._mode_manager.get_temperature = MagicMock(return_value=0.7)
        handler._prompt_builder = MagicMock()
        handler._prompt_builder.estimate_response_budget = MagicMock(return_value=4096)
        handler._validation_pipeline = MagicMock()
        handler._validation_pipeline.validate_response = MagicMock(
            return_value=MagicMock(valid=True)
        )
        handler._get_council_manager = MagicMock(return_value=MagicMock(
            run_council=AsyncMock(return_value=MagicMock(
                roles_executed=[], roles_failed=[], fallback_used=True,
                tool_extraction=None,
            ))
        ))
        handler._looks_like_tool_call = MagicMock(return_value=False)

        # Inference returns tool_calls
        tool_response = _make_inference_response(
            content="", tool_calls=[_make_tool_call("list_events")],
        )
        handler.inference_client.chat = AsyncMock(return_value=tool_response)

        # CLI request — NOT workflow
        request = Request.create(
            content="What's on my calendar?",
            mode=Mode.TIA,
            source=RequestSource.CLI,
        )
        task = MagicMock()

        response = await handler._run_inference_with_retry(
            task=task,
            request=request,
            messages=[Message(role="user", content="What's on my calendar?")],
            prompt_components=MagicMock(),
        )

        # Tool loop NOT called — single-turn path used
        handler._execute_tool_loop.assert_not_called()
        handler._execute_native_tool_calls.assert_called_once()
