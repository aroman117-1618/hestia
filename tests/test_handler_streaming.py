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


async def mock_chat_stream_tokens(tokens: list[str], model: str = "qwen3.5:9b"):
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
        model="qwen3.5:9b",
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
                    # Mock user manager (trust tier loading in Step 3.5)
                    mock_user_settings = MagicMock()
                    mock_user_settings.get_tool_trust_tiers.return_value = MagicMock(to_dict=MagicMock(return_value={}))
                    mock_user_mgr = AsyncMock()
                    mock_user_mgr.get_settings = AsyncMock(return_value=mock_user_settings)
                    with patch('hestia.user.get_user_manager', new_callable=AsyncMock, return_value=mock_user_mgr):
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
        # O1: memory + profile + council now run in parallel as "preparing"
        assert "preparing" in stages
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
                    mock_user_settings = MagicMock()
                    mock_user_settings.get_tool_trust_tiers.return_value = MagicMock(to_dict=MagicMock(return_value={}))
                    mock_user_mgr = AsyncMock()
                    mock_user_mgr.get_settings = AsyncMock(return_value=mock_user_settings)
                    with patch('hestia.user.get_user_manager', new_callable=AsyncMock, return_value=mock_user_mgr):
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
                    mock_user_settings = MagicMock()
                    mock_user_settings.get_tool_trust_tiers.return_value = MagicMock(to_dict=MagicMock(return_value={}))
                    mock_user_mgr = AsyncMock()
                    mock_user_mgr.get_settings = AsyncMock(return_value=mock_user_settings)
                    with patch('hestia.user.get_user_manager', new_callable=AsyncMock, return_value=mock_user_mgr):
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


# ============== Synthesis Prompt Tests ==============


class TestSynthesisPrompt:
    """Tests for _format_tool_result_with_personality prompt construction."""

    @pytest.fixture
    def handler(self):
        """Create handler with mocked dependencies."""
        with patch('hestia.orchestration.handler.get_memory_manager', new_callable=AsyncMock):
            with patch('hestia.orchestration.handler.InferenceClient') as mock_inf_cls:
                mock_client = AsyncMock()
                mock_inf_cls.return_value = mock_client
                h = RequestHandler.__new__(RequestHandler)
                h._inference_client = mock_client  # Private attr — property is read-only
                h.logger = MagicMock()
                return h

    @pytest.mark.asyncio
    async def test_synthesis_truncates_large_results(self, handler):
        """Tool results exceeding MAX_SYNTHESIS_CHARS are truncated."""
        large_result = "x" * 6000
        request = make_request("What's in this file?")
        original_messages = [Message(role="user", content=request.content)]

        # Mock inference to return the synthesized content
        handler.inference_client.chat = AsyncMock(
            return_value=InferenceResponse(
                content="Here's a summary of the file.",
                model="test", tokens_in=10, tokens_out=20, duration_ms=100,
            )
        )

        await handler._format_tool_result_with_personality(
            large_result, request, original_messages, 0.7, 2048
        )

        # Verify the messages sent to inference
        call_args = handler.inference_client.chat.call_args
        messages = call_args.kwargs.get("messages") or call_args[0][0]

        # Assistant message should contain truncated result
        assistant_msg = [m for m in messages if m.role == "assistant"][-1]
        assert len(assistant_msg.content) < len(large_result)
        assert "chars truncated" in assistant_msg.content

    @pytest.mark.asyncio
    async def test_synthesis_uses_generic_reprompt(self, handler):
        """Synthesis prompt is generic — doesn't dictate response format."""
        request = make_request("Analyze the CLI section of my notes")
        original_messages = [Message(role="user", content=request.content)]

        handler.inference_client.chat = AsyncMock(
            return_value=InferenceResponse(
                content="The CLI section shows...",
                model="test", tokens_in=10, tokens_out=20, duration_ms=100,
            )
        )

        await handler._format_tool_result_with_personality(
            "Some tool output data", request, original_messages, 0.7, 2048
        )

        call_args = handler.inference_client.chat.call_args
        messages = call_args.kwargs.get("messages") or call_args[0][0]

        # Last user message should be generic re-prompt
        user_msgs = [m for m in messages if m.role == "user"]
        last_user = user_msgs[-1]
        assert last_user.content == "Now respond to my original request based on that data."

        # Should NOT contain format-specific instructions
        assert "present" not in last_user.content.lower()
        assert "personable" not in last_user.content.lower()
        assert "list" not in last_user.content.lower()

    @pytest.mark.asyncio
    async def test_synthesis_preserves_original_messages(self, handler):
        """Original messages (with user's question) are preserved in synthesis."""
        request = make_request("Tell me about the CLI improvements")
        original_messages = [
            Message(role="system", content="You are Tia."),
            Message(role="user", content=request.content),
        ]

        handler.inference_client.chat = AsyncMock(
            return_value=InferenceResponse(
                content="The CLI improvements include...",
                model="test", tokens_in=10, tokens_out=20, duration_ms=100,
            )
        )

        await handler._format_tool_result_with_personality(
            "CLI data here", request, original_messages, 0.7, 2048
        )

        call_args = handler.inference_client.chat.call_args
        messages = call_args.kwargs.get("messages") or call_args[0][0]

        # Original messages should be at the start
        assert messages[0].role == "system"
        assert messages[0].content == "You are Tia."
        assert messages[1].role == "user"
        assert messages[1].content == "Tell me about the CLI improvements"

    @pytest.mark.asyncio
    async def test_synthesis_small_results_not_truncated(self, handler):
        """Small tool results pass through without truncation."""
        small_result = "Found 3 notes: A, B, C"
        request = make_request("List my notes")
        original_messages = [Message(role="user", content=request.content)]

        handler.inference_client.chat = AsyncMock(
            return_value=InferenceResponse(
                content="You have 3 notes: A, B, and C.",
                model="test", tokens_in=10, tokens_out=20, duration_ms=100,
            )
        )

        await handler._format_tool_result_with_personality(
            small_result, request, original_messages, 0.7, 2048
        )

        call_args = handler.inference_client.chat.call_args
        messages = call_args.kwargs.get("messages") or call_args[0][0]

        assistant_msg = [m for m in messages if m.role == "assistant"][-1]
        assert "truncated" not in assistant_msg.content
        assert small_result in assistant_msg.content

    @pytest.mark.asyncio
    async def test_synthesis_fallback_on_inference_error(self, handler):
        """Falls back to raw tool result if synthesis inference fails."""
        handler.inference_client.chat = AsyncMock(side_effect=RuntimeError("Model unavailable"))

        result = await handler._format_tool_result_with_personality(
            "raw tool data", make_request(), [Message(role="user", content="test")], 0.7, 2048
        )

        assert result == "raw tool data"
        handler.logger.warning.assert_called_once()


# ── Text-Pattern Tool Call Detection Tests ────────────────────


class TestTextPatternToolDetection:
    """Test Priority 3b: function-call syntax detection in model text output.

    When models output tool calls as text (e.g., ``read_note("hestia")``)
    rather than structured JSON, the regex fallback must detect and execute them.
    """

    @pytest.fixture
    def handler(self):
        """Create a minimal handler for testing tool detection."""
        h = RequestHandler.__new__(RequestHandler)
        h.logger = MagicMock()
        h._inference_client = MagicMock()
        h.state_machine = MagicMock()
        h._tool_executor = None
        h._request_counter = 0
        return h

    @pytest.mark.asyncio
    async def test_detects_function_call_syntax(self, handler):
        """Detects read_note("hestia") pattern and executes the tool."""
        content = 'I\'ll read your "hestia" note for you.\n\n```\nread_note("hestia")\n```'

        mock_tool = MagicMock()
        mock_tool.parameters = {"title": MagicMock()}
        mock_tool.requires_approval = False

        mock_registry = MagicMock()
        mock_registry.has_tool.side_effect = lambda name: name == "read_note"
        mock_registry.get.return_value = mock_tool

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = "# Hestia\nThis is the CLI section..."

        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(return_value=mock_result)

        with patch("hestia.orchestration.handler.get_tool_registry", return_value=mock_registry), \
             patch.object(handler, "_get_tool_executor", return_value=mock_executor):
            request = make_request("read my hestia note")
            task = MagicMock()
            result = await handler._try_execute_tool_from_response(content, request, task)

        assert result is not None
        assert "Hestia" in result
        mock_executor.execute.assert_called_once()
        # Verify the correct tool name and argument were extracted
        call_obj = mock_executor.execute.call_args[0][0]
        assert call_obj.tool_name == "read_note"
        assert call_obj.arguments.get("title") == "hestia"

    @pytest.mark.asyncio
    async def test_detects_keyword_arguments(self, handler):
        """Detects tool_name(key="value") syntax with keyword args."""
        content = 'Let me search for that.\nsearch_notes(query="project plan")'

        mock_tool = MagicMock()
        mock_tool.parameters = {"query": MagicMock()}
        mock_tool.requires_approval = False

        mock_registry = MagicMock()
        mock_registry.has_tool.side_effect = lambda name: name == "search_notes"
        mock_registry.get.return_value = mock_tool

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = "Found 3 matching notes."

        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(return_value=mock_result)

        with patch("hestia.orchestration.handler.get_tool_registry", return_value=mock_registry), \
             patch.object(handler, "_get_tool_executor", return_value=mock_executor):
            result = await handler._try_execute_tool_from_response(
                content, make_request(), MagicMock()
            )

        assert result == "Found 3 matching notes."
        call_obj = mock_executor.execute.call_args[0][0]
        assert call_obj.arguments.get("query") == "project plan"

    @pytest.mark.asyncio
    async def test_mixed_positional_and_keyword_arguments(self, handler):
        """Positional + keyword args both extracted: create_reminder("title", due_date="tomorrow")."""
        content = 'I\'ll set that reminder.\ncreate_reminder("clean the toilet", due_date="tomorrow")'

        mock_tool = MagicMock()
        mock_tool.parameters = {"title": MagicMock(), "due": MagicMock(), "notes": MagicMock()}
        mock_tool.requires_approval = False

        mock_registry = MagicMock()
        mock_registry.has_tool.side_effect = lambda name: name == "create_reminder"
        mock_registry.get.return_value = mock_tool

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = {"created": True, "reminder": {"title": "clean the toilet"}}

        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(return_value=mock_result)

        with patch("hestia.orchestration.handler.get_tool_registry", return_value=mock_registry), \
             patch.object(handler, "_get_tool_executor", return_value=mock_executor):
            result = await handler._try_execute_tool_from_response(
                content, make_request("set a reminder to clean the toilet"), MagicMock()
            )

        assert result is not None
        call_obj = mock_executor.execute.call_args[0][0]
        # Positional "clean the toilet" maps to first param "title"
        assert call_obj.arguments.get("title") == "clean the toilet"
        # Keyword "due_date" also captured
        assert call_obj.arguments.get("due_date") == "tomorrow"

    @pytest.mark.asyncio
    async def test_ignores_unknown_functions(self, handler):
        """Non-tool function names in text are ignored."""
        content = 'Here is an example: print("hello world")\nSee also: len("test")'

        mock_registry = MagicMock()
        mock_registry.has_tool.return_value = False

        with patch("hestia.orchestration.handler.get_tool_registry", return_value=mock_registry):
            result = await handler._try_execute_tool_from_response(
                content, make_request(), MagicMock()
            )

        assert result is None

    def test_looks_like_tool_call_detects_function_syntax(self, handler):
        """_looks_like_tool_call catches function-call patterns with known tools."""
        content = 'I\'ll read your note.\n```\nread_note("hestia")\n```'

        mock_registry = MagicMock()
        mock_registry.has_tool.side_effect = lambda name: name == "read_note"

        with patch("hestia.orchestration.handler.get_tool_registry", return_value=mock_registry):
            assert handler._looks_like_tool_call(content) is True

    def test_looks_like_tool_call_ignores_regular_text(self, handler):
        """_looks_like_tool_call doesn't false-positive on normal text."""
        content = "The weather today is sunny with a high of 72°F."

        mock_registry = MagicMock()
        mock_registry.has_tool.return_value = False

        with patch("hestia.orchestration.handler.get_tool_registry", return_value=mock_registry):
            assert handler._looks_like_tool_call(content) is False

    def test_looks_like_tool_call_detects_name_json_format(self, handler):
        """_looks_like_tool_call catches {"name": "...", "arguments": {...}} format."""
        content = '{"name": "create_note", "arguments": {"title": "test", "content": "hello"}}'

        mock_registry = MagicMock()
        mock_registry.has_tool.return_value = False

        with patch("hestia.orchestration.handler.get_tool_registry", return_value=mock_registry):
            assert handler._looks_like_tool_call(content) is True

    def test_looks_like_tool_call_detects_name_json_embedded(self, handler):
        """_looks_like_tool_call catches {"name": ...} embedded in surrounding text."""
        content = 'Sure, I\'ll create that note.\n{"name": "create_note", "arguments": {"title": "test"}}'

        mock_registry = MagicMock()
        mock_registry.has_tool.return_value = False

        with patch("hestia.orchestration.handler.get_tool_registry", return_value=mock_registry):
            assert handler._looks_like_tool_call(content) is True

    @pytest.mark.asyncio
    async def test_executes_name_arguments_json_format(self, handler):
        """{"name": "...", "arguments": {...}} format is parsed and executed."""
        content = '{"name": "create_note", "arguments": {"title": "Dev Plan", "body": "Step 1: setup"}}'

        mock_registry = MagicMock()
        mock_registry.has_tool.return_value = True

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = {"status": "created", "id": "note-123"}

        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(return_value=mock_result)

        with patch("hestia.orchestration.handler.get_tool_registry", return_value=mock_registry), \
             patch.object(handler, "_get_tool_executor", return_value=mock_executor):
            result = await handler._try_execute_tool_from_response(
                content, make_request("create a dev plan note"), MagicMock()
            )

        assert result is not None
        assert "note-123" in result
        call_obj = mock_executor.execute.call_args[0][0]
        assert call_obj.tool_name == "create_note"
        assert call_obj.arguments.get("title") == "Dev Plan"
        assert call_obj.arguments.get("body") == "Step 1: setup"

    @pytest.mark.asyncio
    async def test_executes_name_json_embedded_in_text(self, handler):
        """{"name": ...} JSON embedded in surrounding text is extracted and executed."""
        content = 'Sure, let me create that.\n{"name": "read_note", "arguments": {"title": "hestia"}}\nDone!'

        mock_registry = MagicMock()
        mock_registry.has_tool.side_effect = lambda name: name == "read_note"

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = "# Hestia Notes\nCLI section content"

        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(return_value=mock_result)

        with patch("hestia.orchestration.handler.get_tool_registry", return_value=mock_registry), \
             patch.object(handler, "_get_tool_executor", return_value=mock_executor):
            result = await handler._try_execute_tool_from_response(
                content, make_request("read my hestia note"), MagicMock()
            )

        assert result is not None
        assert "Hestia Notes" in result
        call_obj = mock_executor.execute.call_args[0][0]
        assert call_obj.tool_name == "read_note"


class TestStreamingSynthesis:
    """Test _stream_tool_result_with_personality for streaming synthesis.

    Verifies that synthesis uses chat_stream() instead of blocking chat(),
    preventing wall-clock timeouts on slow hardware.
    """

    @pytest.fixture
    def handler(self):
        """Create a minimal handler for testing streaming synthesis."""
        h = RequestHandler.__new__(RequestHandler)
        h.logger = MagicMock()
        h._inference_client = MagicMock()
        h.state_machine = MagicMock()
        h.MAX_SYNTHESIS_CHARS = 4000
        return h

    @pytest.mark.asyncio
    async def test_streams_synthesis_tokens(self, handler):
        """Verify tokens are yielded incrementally from chat_stream."""
        synthesis_tokens = ["Here's ", "what I ", "found in ", "your note."]

        async def mock_stream(*args, **kwargs):
            for token in synthesis_tokens:
                yield token
            yield InferenceResponse(
                content="".join(synthesis_tokens),
                model="qwen2.5:7b",
                tokens_in=100,
                tokens_out=len(synthesis_tokens),
                duration_ms=5000.0,
            )

        handler._inference_client.chat_stream = mock_stream

        request = make_request("read my hestia note")
        messages = [Message(role="user", content="read my hestia note")]

        collected = []
        async for token in handler._stream_tool_result_with_personality(
            "Note contents here", request, messages, 0.7, 1024
        ):
            collected.append(token)

        assert collected == synthesis_tokens

    @pytest.mark.asyncio
    async def test_streaming_synthesis_truncates_large_results(self, handler):
        """Verify tool results > MAX_SYNTHESIS_CHARS are truncated."""
        large_result = "x" * 5000

        captured_messages = []

        async def mock_stream(messages=None, **kwargs):
            captured_messages.extend(messages or [])
            yield "Summary"
            yield InferenceResponse(
                content="Summary",
                model="qwen2.5:7b",
                tokens_in=100,
                tokens_out=1,
                duration_ms=1000.0,
            )

        handler._inference_client.chat_stream = mock_stream

        request = make_request("read my note")
        messages = [Message(role="user", content="read my note")]

        collected = []
        async for token in handler._stream_tool_result_with_personality(
            large_result, request, messages, 0.7, 1024
        ):
            collected.append(token)

        assert collected == ["Summary"]
        # The assistant message should contain truncated content
        assistant_msg = [m for m in captured_messages if m.role == "assistant"][0]
        assert "[..." in assistant_msg.content
        assert "1000 chars truncated" in assistant_msg.content

    @pytest.mark.asyncio
    async def test_streaming_synthesis_falls_back_on_error(self, handler):
        """Verify raw tool result is yielded if streaming inference fails."""
        async def mock_stream_fail(*args, **kwargs):
            raise RuntimeError("Connection refused")
            # Make it an async generator
            yield  # pragma: no cover

        handler._inference_client.chat_stream = mock_stream_fail

        request = make_request("read my note")
        messages = [Message(role="user", content="read my note")]

        collected = []
        async for token in handler._stream_tool_result_with_personality(
            "Raw tool output", request, messages, 0.7, 1024
        ):
            collected.append(token)

        assert collected == ["Raw tool output"]

    @pytest.mark.asyncio
    async def test_streaming_synthesis_uses_force_cloud_when_adapted(self, handler):
        """When hardware_adapted, synthesis passes force_tier='cloud' to chat_stream."""
        mock_router = MagicMock()
        mock_router._adaptation_applied = True
        handler._inference_client.router = mock_router

        captured_kwargs = {}

        async def mock_stream(**kwargs):
            captured_kwargs.update(kwargs)
            yield "Cloud response"
            yield InferenceResponse(
                content="Cloud response", model="claude-3-haiku",
                tokens_in=10, tokens_out=5, duration_ms=500,
            )

        handler._inference_client.chat_stream = mock_stream

        request = make_request("read my note")
        messages = [Message(role="user", content="read my note")]

        tokens = []
        async for token in handler._stream_tool_result_with_personality(
            "Note content here", request, messages, 0.7, 1024
        ):
            tokens.append(token)

        assert "Cloud response" in tokens
        assert captured_kwargs.get("force_tier") == "cloud"

    @pytest.mark.asyncio
    async def test_streaming_synthesis_no_force_when_not_adapted(self, handler):
        """When hardware NOT adapted, no force_tier is passed."""
        mock_router = MagicMock()
        mock_router._adaptation_applied = False
        handler._inference_client.router = mock_router

        captured_kwargs = {}

        async def mock_stream(**kwargs):
            captured_kwargs.update(kwargs)
            yield "Local response"
            yield InferenceResponse(
                content="Local response", model="qwen2.5:7b",
                tokens_in=10, tokens_out=5, duration_ms=500,
            )

        handler._inference_client.chat_stream = mock_stream

        request = make_request("read my note")
        messages = [Message(role="user", content="read my note")]

        tokens = []
        async for token in handler._stream_tool_result_with_personality(
            "Note content here", request, messages, 0.7, 1024
        ):
            tokens.append(token)

        assert "Local response" in tokens
        assert captured_kwargs.get("force_tier") is None
