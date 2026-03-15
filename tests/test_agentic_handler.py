"""Tests for the agentic tool loop in RequestHandler."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from hestia.orchestration.models import Request, RequestSource, Mode


def _make_mock_inference_response(content="", tool_calls=None):
    """Create a mock InferenceResponse."""
    resp = MagicMock()
    resp.content = content
    resp.tool_calls = tool_calls or []
    resp.usage = MagicMock(total_tokens=100)
    return resp


class TestAgenticHandler:
    """Test the agentic tool loop."""

    @pytest.fixture
    def agentic_request(self):
        return Request(
            id="test-agentic-001",
            content="Read the file hestia/memory/models.py and tell me about it",
            source=RequestSource.API,
            mode=Mode("tia"),
        )

    @pytest.fixture
    def handler(self):
        """Create a handler with mocked dependencies."""
        with patch("hestia.orchestration.handler.get_memory_manager", new_callable=AsyncMock) as mock_mem, \
             patch("hestia.orchestration.handler.get_inference_client", new_callable=AsyncMock) as mock_inf, \
             patch("hestia.orchestration.handler.get_mode_manager", new_callable=AsyncMock) as mock_mode, \
             patch("hestia.orchestration.handler.get_prompt_builder", new_callable=AsyncMock) as mock_prompt, \
             patch("hestia.orchestration.handler.get_tool_registry") as mock_reg, \
             patch("hestia.orchestration.handler.get_tool_executor", new_callable=AsyncMock) as mock_exec:

            from hestia.orchestration.handler import RequestHandler

            # All async factories must be AsyncMock so `await` works
            # The RETURNED objects use MagicMock with selective AsyncMock methods

            # Mock memory
            mem = MagicMock()
            mem.build_context = AsyncMock(return_value="")
            mock_mem.return_value = mem  # AsyncMock patch makes await work

            # Mock inference
            inf = MagicMock()
            inf.chat = AsyncMock(return_value=_make_mock_inference_response(
                content="The file contains memory models including MemoryScope and ChunkType enums."
            ))
            mock_inf.return_value = inf

            # Mock mode manager
            mock_mode.return_value = MagicMock()

            # Mock prompt builder
            pb = MagicMock()
            pb.build_system_prompt = AsyncMock(return_value="You are Hestia.")
            mock_prompt.return_value = pb

            # Mock registry (sync — not awaited)
            reg = MagicMock()
            reg.get_definitions_for_prompt.return_value = "[]"
            reg.get_definitions_as_list.return_value = []
            mock_reg.return_value = reg

            # Mock executor
            executor = MagicMock()
            executor.execute = AsyncMock()
            mock_exec.return_value = executor

            handler = RequestHandler()
            handler._inference = inf
            handler._mock_executor = executor

            yield handler, inf, executor

    def test_single_inference_no_tools(self, handler, agentic_request):
        """Model produces text with no tool calls — loop terminates immediately."""
        h, inf, _ = handler
        events = []
        async def collect():
            async for event in h.handle_agentic(agentic_request):
                events.append(event)

        asyncio.get_event_loop().run_until_complete(collect())

        # Should have: status (preparing), status (inference), token, agentic_done
        types = [e["type"] for e in events]
        assert "token" in types
        assert "agentic_done" in types

        # Check done event
        done = [e for e in events if e["type"] == "agentic_done"][0]
        assert done["iterations"] == 1

    def test_loop_with_tool_call(self, handler, agentic_request):
        """Model calls a tool, sees result, then produces final text."""
        h, inf, executor = handler

        # First call: returns tool call
        tool_response = _make_mock_inference_response(
            content="",
            tool_calls=[{
                "function": {"name": "read_file", "arguments": {"path": "test.py"}}
            }],
        )
        # Second call: returns text (termination)
        text_response = _make_mock_inference_response(
            content="The file contains test code."
        )
        inf.chat = AsyncMock(side_effect=[tool_response, text_response])

        # Mock tool execution
        from hestia.execution.models import ToolResult, ToolResultStatus
        executor.execute = AsyncMock(return_value=ToolResult(
            call_id="tc-test",
            tool_name="read_file",
            status=ToolResultStatus.SUCCESS,
            output="def test(): pass",
        ))

        events = []
        async def collect():
            async for event in h.handle_agentic(agentic_request):
                events.append(event)

        asyncio.get_event_loop().run_until_complete(collect())

        types = [e["type"] for e in events]
        assert "tool_start" in types
        assert "tool_result" in types
        assert "token" in types
        assert "agentic_done" in types

        done = [e for e in events if e["type"] == "agentic_done"][0]
        assert done["iterations"] == 2  # Two inference calls

    def test_loop_terminates_at_max_iterations(self, handler, agentic_request):
        """Loop stops after max_iterations even if model keeps calling tools."""
        h, inf, executor = handler

        # Always return tool calls (never terminates naturally)
        inf.chat = AsyncMock(return_value=_make_mock_inference_response(
            content="",
            tool_calls=[{
                "function": {"name": "read_file", "arguments": {"path": "test.py"}}
            }],
        ))

        from hestia.execution.models import ToolResult, ToolResultStatus
        executor.execute = AsyncMock(return_value=ToolResult(
            call_id="tc-test",
            tool_name="read_file",
            status=ToolResultStatus.SUCCESS,
            output="content",
        ))

        events = []
        async def collect():
            async for event in h.handle_agentic(agentic_request, max_iterations=3):
                events.append(event)

        asyncio.get_event_loop().run_until_complete(collect())

        done = [e for e in events if e["type"] == "agentic_done"][0]
        assert done["iterations"] == 3  # Stopped at max

    def test_error_handling(self, handler, agentic_request):
        """Errors during agentic loop produce error events."""
        h, inf, _ = handler
        inf.chat = AsyncMock(side_effect=RuntimeError("Inference failed"))

        events = []
        async def collect():
            async for event in h.handle_agentic(agentic_request):
                events.append(event)

        asyncio.get_event_loop().run_until_complete(collect())

        types = [e["type"] for e in events]
        assert "error" in types
