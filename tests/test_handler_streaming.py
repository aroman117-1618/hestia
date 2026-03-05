"""
Tests for RequestHandler.handle_streaming() method.

Tests the streaming pipeline that yields WebSocket protocol events
through the full orchestration pipeline: validation, memory, prompt
building, inference, tool execution, and response caching.

Run with: python -m pytest tests/test_handler_streaming.py -v
"""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from typing import AsyncGenerator, Union

from hestia.orchestration.models import (
    Request,
    Response,
    ResponseType,
    Mode,
    RequestSource,
    Conversation,
)
from hestia.orchestration.handler import RequestHandler, get_request_handler
from hestia.inference.client import InferenceResponse, Message


# ============== Helpers ==============


async def collect_events(gen: AsyncGenerator[dict, None]) -> list[dict]:
    """Collect all events from an async generator."""
    return [event async for event in gen]


def make_request(content: str = "Hello", mode: Mode = Mode.TIA, source: RequestSource = RequestSource.CLI) -> Request:
    """Create a test request."""
    return Request.create(
        content=content,
        mode=mode,
        source=source,
    )


async def mock_chat_stream_tokens(tokens: list[str], model: str = "qwen2.5:7b"):
    """Create a mock chat_stream that yields tokens then InferenceResponse."""
    content = "".join(tokens)
    for token in tokens:
        yield token
    yield InferenceResponse(
        content=content,
        model=model,
        tokens_in=50,
        tokens_out=len(tokens),
        duration_ms=250.0,
    )


async def mock_chat_stream_with_tool_calls(tool_calls: list[dict]):
    """Mock chat_stream that returns tool calls."""
    yield InferenceResponse(
        content="",
        model="qwen2.5:7b",
        tokens_in=50,
        tokens_out=5,
        duration_ms=200.0,
        tool_calls=tool_calls,
    )


# ============== Tests ==============


class TestHandleStreaming:
    """Tests for RequestHandler.handle_streaming()."""

    @pytest.mark.asyncio
    async def test_streaming_yields_expected_event_sequence(self):
        """Verify the standard event sequence: status → tokens → done."""
        handler = RequestHandler.__new__(RequestHandler)
        handler.logger = MagicMock()

        # Mock all the internals
        handler._validation_pipeline = MagicMock()
        handler._validation_pipeline.validate_request.return_value = MagicMock(valid=True)

        handler._mode_manager = MagicMock()
        handler._mode_manager.process_mode_switch.return_value = (Mode.TIA, "Hello")
        handler._mode_manager.get_temperature.return_value = 0.7

        handler.state_machine = MagicMock()
        handler.state_machine.create_task.return_value = MagicMock(context={})

        handler._handle_count = 0
        handler._CLEANUP_INTERVAL = 20
        handler._conversations = {}

        # Mock session/conversation
        mock_conversation = Conversation(session_id="test-session")
        handler._get_or_create_conversation_with_ttl = AsyncMock(return_value=mock_conversation)
        handler._get_session_timeout = AsyncMock(return_value=1800)

        # Mock cache (no hit)
        with patch('hestia.orchestration.handler.get_response_cache') as mock_cache_fn:
            mock_cache = MagicMock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.put = AsyncMock()
            mock_cache_fn.return_value = mock_cache

            # Mock memory
            mock_memory = MagicMock()
            mock_memory.build_context = AsyncMock(return_value="memory context")
            handler._get_memory_manager = AsyncMock(return_value=mock_memory)

            # Mock cloud routing check
            handler._will_route_to_cloud = MagicMock(return_value=False)

            # Mock prompt builder
            handler._prompt_builder = MagicMock()
            handler._prompt_builder.build.return_value = (
                [{"role": "system", "content": "sys"}, {"role": "user", "content": "Hello"}],
                {"system": 100, "user": 10},
            )
            handler._prompt_builder.check_budget.return_value = {"exceeded": False}
            handler._prompt_builder.estimate_response_budget.return_value = 1000

            # Mock council
            mock_council = MagicMock()
            mock_council.classify_intent = AsyncMock(return_value=MagicMock(
                primary_intent=MagicMock(value="CHAT"),
                confidence=0.9,
            ))
            mock_council.run_council = AsyncMock(return_value=MagicMock(
                tool_extraction=None,
                fallback_used=True,
            ))
            handler._get_council_manager = MagicMock(return_value=mock_council)

            # Mock inference client with streaming
            handler._inference_client = MagicMock()
            handler.inference_client.chat_stream = MagicMock(
                return_value=mock_chat_stream_tokens(["Hello", " ", "there", "!"])
            )

            # Mock tool registry
            with patch('hestia.orchestration.handler.get_tool_registry') as mock_registry_fn:
                mock_registry = MagicMock()
                mock_registry.get_definitions_as_list.return_value = []
                mock_registry_fn.return_value = mock_registry

                # Mock user profile loader
                with patch('hestia.user.config_loader.get_user_config_loader', side_effect=Exception("test")):
                    # Mock _looks_like_tool_call
                    handler._looks_like_tool_call = MagicMock(return_value=False)

                    # Mock store conversation
                    handler._store_conversation = AsyncMock()

                    request = make_request()
                    events = await collect_events(handler.handle_streaming(request))

        # Verify event sequence
        event_types = [e["type"] for e in events]
        assert "status" in event_types
        assert "token" in event_types
        assert "done" in event_types

        # Verify status stages
        status_events = [e for e in events if e["type"] == "status"]
        stages = [e["stage"] for e in status_events]
        assert "validating" in stages
        assert "memory" in stages
        assert "building_prompt" in stages
        assert "council" in stages
        assert "inference" in stages

        # Verify tokens
        token_events = [e for e in events if e["type"] == "token"]
        token_content = "".join(e["content"] for e in token_events)
        assert token_content == "Hello there!"

        # Verify done event
        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1
        assert done_events[0]["request_id"] == request.id
        assert "metrics" in done_events[0]
        assert done_events[0]["mode"] == "tia"

    @pytest.mark.asyncio
    async def test_streaming_validation_failure(self):
        """Validation failure should yield error and stop."""
        handler = RequestHandler.__new__(RequestHandler)
        handler.logger = MagicMock()
        handler.state_machine = MagicMock()
        handler.state_machine.create_task.return_value = MagicMock(context={})
        handler._handle_count = 0
        handler._CLEANUP_INTERVAL = 20

        handler._validation_pipeline = MagicMock()
        handler._validation_pipeline.validate_request.return_value = MagicMock(
            valid=False, message="Content too long"
        )

        request = make_request()
        events = await collect_events(handler.handle_streaming(request))

        # Should have status (validating) then error
        assert any(e["type"] == "status" and e["stage"] == "validating" for e in events)
        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert error_events[0]["code"] == "validation_error"
        assert "Content too long" in error_events[0]["message"]

    @pytest.mark.asyncio
    async def test_streaming_cache_hit(self):
        """Cached responses should stream in chunks and return done with cached=True."""
        handler = RequestHandler.__new__(RequestHandler)
        handler.logger = MagicMock()
        handler.state_machine = MagicMock()
        handler.state_machine.create_task.return_value = MagicMock(context={})
        handler._handle_count = 0
        handler._CLEANUP_INTERVAL = 20

        handler._validation_pipeline = MagicMock()
        handler._validation_pipeline.validate_request.return_value = MagicMock(valid=True)

        handler._mode_manager = MagicMock()
        handler._mode_manager.process_mode_switch.return_value = (Mode.TIA, "Hello")

        mock_conversation = Conversation(session_id="test-session")
        handler._get_or_create_conversation_with_ttl = AsyncMock(return_value=mock_conversation)

        # Mock cache hit
        cached_response = MagicMock()
        cached_response.content = "Cached answer"
        cached_response.tokens_in = 10
        cached_response.tokens_out = 5

        with patch('hestia.orchestration.handler.get_response_cache') as mock_cache_fn:
            mock_cache = MagicMock()
            mock_cache.get = AsyncMock(return_value=cached_response)
            mock_cache_fn.return_value = mock_cache

            request = make_request()
            request.force_local = False
            events = await collect_events(handler.handle_streaming(request))

        # Should have cache_hit status, tokens, and done
        assert any(e["type"] == "status" and e.get("stage") == "cache_hit" for e in events)
        token_content = "".join(e["content"] for e in events if e["type"] == "token")
        assert token_content == "Cached answer"
        done = [e for e in events if e["type"] == "done"][0]
        assert done["metrics"]["cached"] is True

    @pytest.mark.asyncio
    async def test_streaming_tool_approval_callback(self):
        """Tool approval callback should be invoked for tool calls."""
        handler = RequestHandler.__new__(RequestHandler)
        handler.logger = MagicMock()

        handler._validation_pipeline = MagicMock()
        handler._validation_pipeline.validate_request.return_value = MagicMock(valid=True)

        handler._mode_manager = MagicMock()
        handler._mode_manager.process_mode_switch.return_value = (Mode.TIA, "Show calendar")
        handler._mode_manager.get_temperature.return_value = 0.7

        handler.state_machine = MagicMock()
        handler.state_machine.create_task.return_value = MagicMock(context={})
        handler._handle_count = 0
        handler._CLEANUP_INTERVAL = 20
        handler._conversations = {}

        mock_conversation = Conversation(session_id="test-session")
        handler._get_or_create_conversation_with_ttl = AsyncMock(return_value=mock_conversation)

        with patch('hestia.orchestration.handler.get_response_cache') as mock_cache_fn:
            mock_cache = MagicMock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.put = AsyncMock()
            mock_cache_fn.return_value = mock_cache

            mock_memory = MagicMock()
            mock_memory.build_context = AsyncMock(return_value="")
            handler._get_memory_manager = AsyncMock(return_value=mock_memory)
            handler._will_route_to_cloud = MagicMock(return_value=False)

            handler._prompt_builder = MagicMock()
            handler._prompt_builder.build.return_value = (
                [{"role": "user", "content": "Show calendar"}],
                {"user": 10},
            )
            handler._prompt_builder.check_budget.return_value = {"exceeded": False}
            handler._prompt_builder.estimate_response_budget.return_value = 1000

            mock_council = MagicMock()
            mock_council.classify_intent = AsyncMock(return_value=MagicMock(
                primary_intent=MagicMock(value="TOOL_USE"),
                confidence=0.95,
            ))
            mock_council.run_council = AsyncMock(return_value=MagicMock(
                tool_extraction=None,
                fallback_used=True,
            ))
            handler._get_council_manager = MagicMock(return_value=mock_council)

            # Stream with tool calls
            tool_calls = [{"function": {"name": "list_events", "arguments": {"days": 1}}}]
            handler._inference_client = MagicMock()
            handler.inference_client.chat_stream = MagicMock(
                return_value=mock_chat_stream_with_tool_calls(tool_calls)
            )

            with patch('hestia.orchestration.handler.get_tool_registry') as mock_registry_fn:
                mock_registry = MagicMock()
                mock_registry.get_definitions_as_list.return_value = []
                mock_registry_fn.return_value = mock_registry

                # Mock _execute_streaming_tool_calls directly
                handler._execute_streaming_tool_calls = AsyncMock(return_value="Calendar events: Meeting at 3pm")

                # Mock approval callback
                approval_callback = AsyncMock(return_value=True)

                handler._looks_like_tool_call = MagicMock(return_value=False)
                handler._store_conversation = AsyncMock()
                handler._format_tool_result_with_personality = AsyncMock(return_value="Here are your calendar events: Meeting at 3pm")

                with patch('hestia.user.config_loader.get_user_config_loader', side_effect=Exception("test")):
                    request = make_request("Show calendar")
                    events = await collect_events(
                        handler.handle_streaming(request, tool_approval_callback=approval_callback)
                    )

        # Should have tool execution status
        assert any(e["type"] == "status" and e.get("stage") == "tools" for e in events)

        # Should have tool_result event (from _execute_streaming_tool_calls returning non-None)
        tool_results = [e for e in events if e["type"] == "tool_result"]
        assert len(tool_results) == 1

        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1

    @pytest.mark.asyncio
    async def test_streaming_internal_error_yields_error_event(self):
        """Unhandled exceptions should yield an error event, not crash."""
        handler = RequestHandler.__new__(RequestHandler)
        handler.logger = MagicMock()
        handler.state_machine = MagicMock()
        handler.state_machine.create_task.return_value = MagicMock(context={})
        handler._handle_count = 0
        handler._CLEANUP_INTERVAL = 20

        handler._validation_pipeline = MagicMock()
        handler._validation_pipeline.validate_request.return_value = MagicMock(valid=True)

        handler._mode_manager = MagicMock()
        handler._mode_manager.process_mode_switch.side_effect = RuntimeError("Unexpected crash")

        request = make_request()
        events = await collect_events(handler.handle_streaming(request))

        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert error_events[0]["code"] == "internal_error"

    @pytest.mark.asyncio
    async def test_streaming_mode_switch(self):
        """@mira prefix should switch mode in events."""
        handler = RequestHandler.__new__(RequestHandler)
        handler.logger = MagicMock()

        handler._validation_pipeline = MagicMock()
        handler._validation_pipeline.validate_request.return_value = MagicMock(valid=True)

        handler._mode_manager = MagicMock()
        handler._mode_manager.process_mode_switch.return_value = (Mode.MIRA, "Explain this")
        handler._mode_manager.get_temperature.return_value = 0.5

        handler.state_machine = MagicMock()
        handler.state_machine.create_task.return_value = MagicMock(context={})
        handler._handle_count = 0
        handler._CLEANUP_INTERVAL = 20

        mock_conversation = Conversation(session_id="test-session")
        handler._get_or_create_conversation_with_ttl = AsyncMock(return_value=mock_conversation)

        with patch('hestia.orchestration.handler.get_response_cache') as mock_cache_fn:
            mock_cache = MagicMock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.put = AsyncMock()
            mock_cache_fn.return_value = mock_cache

            mock_memory = MagicMock()
            mock_memory.build_context = AsyncMock(return_value="")
            handler._get_memory_manager = AsyncMock(return_value=mock_memory)
            handler._will_route_to_cloud = MagicMock(return_value=False)

            handler._prompt_builder = MagicMock()
            handler._prompt_builder.build.return_value = (
                [{"role": "user", "content": "Explain this"}],
                {"user": 10},
            )
            handler._prompt_builder.check_budget.return_value = {"exceeded": False}
            handler._prompt_builder.estimate_response_budget.return_value = 1000

            mock_council = MagicMock()
            mock_council.classify_intent = AsyncMock(return_value=MagicMock(
                primary_intent=MagicMock(value="CHAT"),
                confidence=0.9,
            ))
            mock_council.run_council = AsyncMock(return_value=MagicMock(tool_extraction=None, fallback_used=True))
            handler._get_council_manager = MagicMock(return_value=mock_council)

            handler._inference_client = MagicMock()
            handler.inference_client.chat_stream = MagicMock(
                return_value=mock_chat_stream_tokens(["Let me explain"])
            )

            with patch('hestia.orchestration.handler.get_tool_registry') as mock_registry_fn:
                mock_registry = MagicMock()
                mock_registry.get_definitions_as_list.return_value = []
                mock_registry_fn.return_value = mock_registry

                handler._looks_like_tool_call = MagicMock(return_value=False)
                handler._store_conversation = AsyncMock()

                with patch('hestia.user.config_loader.get_user_config_loader', side_effect=Exception("test")):
                    request = make_request("@mira Explain this")
                    events = await collect_events(handler.handle_streaming(request))

        done = [e for e in events if e["type"] == "done"][0]
        assert done["mode"] == "mira"


class TestExecuteStreamingToolCalls:
    """Tests for _execute_streaming_tool_calls()."""

    @pytest.mark.asyncio
    async def test_tool_execution_with_approval(self):
        """Tool execution with approval callback should call the callback."""
        handler = RequestHandler.__new__(RequestHandler)
        handler.logger = MagicMock()

        mock_tool_result = MagicMock(success=True, output="Event: Meeting at 3pm", error=None)
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=mock_tool_result)
        handler._get_tool_executor = AsyncMock(return_value=mock_executor)
        handler.state_machine = MagicMock()

        with patch('hestia.orchestration.handler.get_tool_registry') as mock_registry_fn:
            mock_registry = MagicMock()
            mock_registry.has_tool.return_value = True
            mock_registry.get.return_value = MagicMock(category="read", requires_approval=False)
            mock_registry_fn.return_value = mock_registry

            approval_cb = AsyncMock(return_value=True)
            tool_calls = [{"function": {"name": "list_events", "arguments": {"days": 1}}}]
            request = make_request()
            task = MagicMock(context={})

            result = await handler._execute_streaming_tool_calls(
                tool_calls, request, task, approval_cb
            )

        assert result is not None
        assert "Meeting at 3pm" in result

    @pytest.mark.asyncio
    async def test_tool_execution_denied(self):
        """Denied tool approval should skip execution and include denial message."""
        handler = RequestHandler.__new__(RequestHandler)
        handler.logger = MagicMock()

        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock()
        handler._get_tool_executor = AsyncMock(return_value=mock_executor)

        with patch('hestia.orchestration.handler.get_tool_registry') as mock_registry_fn:
            mock_registry = MagicMock()
            mock_registry.has_tool.return_value = True
            mock_registry.get.return_value = MagicMock(category="execute", requires_approval=True)
            mock_registry_fn.return_value = mock_registry

            # Approval denied
            approval_cb = AsyncMock(return_value=False)
            tool_calls = [{"function": {"name": "run_command", "arguments": {"command": "ls"}}}]
            request = make_request()
            task = MagicMock(context={})

            result = await handler._execute_streaming_tool_calls(
                tool_calls, request, task, approval_cb
            )

        # Tool approval should have been called
        approval_cb.assert_called_once()
        # The tool executor should NOT have been called since approval was denied
        mock_executor.execute.assert_not_called()
        # Result should contain denial message
        assert result is not None
        assert "denied" in result.lower()

    @pytest.mark.asyncio
    async def test_tool_execution_unknown_tool(self):
        """Unknown tool names should be skipped gracefully."""
        handler = RequestHandler.__new__(RequestHandler)
        handler.logger = MagicMock()

        mock_executor = MagicMock()
        handler._get_tool_executor = AsyncMock(return_value=mock_executor)

        with patch('hestia.orchestration.handler.get_tool_registry') as mock_registry_fn:
            mock_registry = MagicMock()
            mock_registry.has_tool.return_value = False
            mock_registry_fn.return_value = mock_registry

            tool_calls = [{"function": {"name": "nonexistent_tool", "arguments": {}}}]
            request = make_request()
            task = MagicMock(context={})

            result = await handler._execute_streaming_tool_calls(
                tool_calls, request, task, None
            )

        # Should handle gracefully, not crash
        mock_executor.execute.assert_not_called()
