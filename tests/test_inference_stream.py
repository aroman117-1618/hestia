"""
Tests for InferenceClient.chat_stream() streaming method.

Tests the streaming chat interface that yields tokens incrementally
from Ollama /api/chat with stream=True, including cloud fallback.

Run with: python -m pytest tests/test_inference_stream.py -v
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from hestia.inference import (
    InferenceClient,
    InferenceConfig,
    InferenceResponse,
    Message,
    LocalModelFailed,
    ModelRouter,
    ModelTier,
    ModelConfig,
    RoutingDecision,
)


# ============== Helpers ==============


class MockStreamResponse:
    """Mock httpx streaming response for Ollama /api/chat."""

    def __init__(self, lines: list[str], status_code: int = 200):
        self._lines = lines
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=MagicMock(),
                response=MagicMock(status_code=self.status_code),
            )

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def make_ollama_stream_lines(tokens: list[str], prompt_eval_count: int = 50, eval_count: int = 10) -> list[str]:
    """Build Ollama streaming response lines from a list of tokens."""
    lines = []
    for token in tokens:
        lines.append(json.dumps({
            "model": "qwen2.5:7b",
            "message": {"role": "assistant", "content": token},
            "done": False,
        }))
    # Final event with metrics
    lines.append(json.dumps({
        "model": "qwen2.5:7b",
        "message": {"role": "assistant", "content": ""},
        "done": True,
        "done_reason": "stop",
        "prompt_eval_count": prompt_eval_count,
        "eval_count": eval_count,
        "total_duration": 500000000,
    }))
    return lines


def make_ollama_tool_call_lines(tool_name: str, arguments: dict) -> list[str]:
    """Build Ollama streaming response lines with a tool call."""
    lines = [
        json.dumps({
            "model": "qwen2.5:7b",
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": tool_name, "arguments": arguments}}],
            },
            "done": False,
        }),
        json.dumps({
            "model": "qwen2.5:7b",
            "message": {"role": "assistant", "content": ""},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 30,
            "eval_count": 5,
        }),
    ]
    return lines


def make_routing_decision(tier: ModelTier = ModelTier.PRIMARY) -> RoutingDecision:
    """Create a routing decision for testing."""
    return RoutingDecision(
        tier=tier,
        model_config=ModelConfig(name="qwen2.5:7b", context_limit=32768),
        reason="test routing",
        fallback_tier=ModelTier.CLOUD if tier == ModelTier.PRIMARY else ModelTier.PRIMARY,
    )


# ============== Tests ==============


class TestChatStream:
    """Tests for InferenceClient.chat_stream()."""

    @pytest.mark.asyncio
    async def test_stream_yields_tokens_then_response(self):
        """Verify chat_stream yields string tokens then a final InferenceResponse."""
        client = InferenceClient()
        tokens_text = ["Hello", " ", "world", "!"]
        lines = make_ollama_stream_lines(tokens_text, prompt_eval_count=50, eval_count=4)

        mock_http = AsyncMock()
        mock_http.stream = MagicMock(return_value=MockStreamResponse(lines))

        with patch.object(client, '_get_client', return_value=mock_http), \
             patch.object(client.router, 'route', return_value=make_routing_decision()), \
             patch.object(client.router, 'record_success'):

            items = [item async for item in client.chat_stream(
                messages=[Message(role="user", content="Hi")],
            )]

        # Should have 4 string tokens + 1 InferenceResponse
        str_items = [i for i in items if isinstance(i, str)]
        resp_items = [i for i in items if isinstance(i, InferenceResponse)]

        assert str_items == tokens_text
        assert len(resp_items) == 1
        assert resp_items[0].content == "Hello world!"
        assert resp_items[0].tokens_in == 50
        assert resp_items[0].tokens_out == 4

    @pytest.mark.asyncio
    async def test_stream_with_tool_calls(self):
        """Verify tool calls are included in the final InferenceResponse."""
        client = InferenceClient()
        lines = make_ollama_tool_call_lines("list_events", {"days": 1})

        mock_http = AsyncMock()
        mock_http.stream = MagicMock(return_value=MockStreamResponse(lines))

        with patch.object(client, '_get_client', return_value=mock_http), \
             patch.object(client.router, 'route', return_value=make_routing_decision()), \
             patch.object(client.router, 'record_success'):

            items = [item async for item in client.chat_stream(
                messages=[Message(role="user", content="Show calendar")],
            )]

        resp_items = [i for i in items if isinstance(i, InferenceResponse)]
        assert len(resp_items) == 1
        assert resp_items[0].tool_calls is not None
        assert resp_items[0].tool_calls[0]["function"]["name"] == "list_events"

    @pytest.mark.asyncio
    async def test_stream_cloud_fallback_yields_single_chunk(self):
        """When routed to cloud, entire response is yielded as one token chunk."""
        client = InferenceClient()
        cloud_response = InferenceResponse(
            content="Cloud says hello!",
            model="claude-3",
            tokens_in=20,
            tokens_out=5,
            duration_ms=300,
        )

        cloud_routing = make_routing_decision(ModelTier.CLOUD)

        with patch.object(client.router, 'route', return_value=cloud_routing), \
             patch.object(client, '_call_cloud', return_value=cloud_response), \
             patch.object(client.router, 'record_success'):

            items = [item async for item in client.chat_stream(
                messages=[Message(role="user", content="Hello cloud")],
            )]

        str_items = [i for i in items if isinstance(i, str)]
        resp_items = [i for i in items if isinstance(i, InferenceResponse)]

        assert str_items == ["Cloud says hello!"]
        assert len(resp_items) == 1
        assert resp_items[0].model == "claude-3"

    @pytest.mark.asyncio
    async def test_stream_empty_tokens_skipped(self):
        """Empty content tokens from Ollama should not be yielded."""
        client = InferenceClient()
        lines = [
            json.dumps({"model": "qwen2.5:7b", "message": {"role": "assistant", "content": ""}, "done": False}),
            json.dumps({"model": "qwen2.5:7b", "message": {"role": "assistant", "content": "Hi"}, "done": False}),
            json.dumps({"model": "qwen2.5:7b", "message": {"role": "assistant", "content": ""}, "done": True, "done_reason": "stop", "prompt_eval_count": 10, "eval_count": 1}),
        ]

        mock_http = AsyncMock()
        mock_http.stream = MagicMock(return_value=MockStreamResponse(lines))

        with patch.object(client, '_get_client', return_value=mock_http), \
             patch.object(client.router, 'route', return_value=make_routing_decision()), \
             patch.object(client.router, 'record_success'):

            items = [item async for item in client.chat_stream(
                messages=[Message(role="user", content="Hi")],
            )]

        str_items = [i for i in items if isinstance(i, str)]
        assert str_items == ["Hi"]

    @pytest.mark.asyncio
    async def test_stream_system_prompt_injected(self):
        """System prompt should be passed through to the Ollama request."""
        client = InferenceClient()
        lines = make_ollama_stream_lines(["OK"])

        mock_http = AsyncMock()
        mock_http.stream = MagicMock(return_value=MockStreamResponse(lines))

        with patch.object(client, '_get_client', return_value=mock_http), \
             patch.object(client.router, 'route', return_value=make_routing_decision()), \
             patch.object(client.router, 'record_success'):

            items = [item async for item in client.chat_stream(
                messages=[Message(role="user", content="Hi")],
                system="You are a test assistant.",
                temperature=0.5,
                max_tokens=100,
            )]

        # Verify mock was called (stream method invoked)
        mock_http.stream.assert_called_once()
        call_args = mock_http.stream.call_args
        # POST method
        assert call_args[0][0] == "POST"
        # URL contains /api/chat
        assert "/api/chat" in call_args[0][1]
        # Check request body has system message
        request_json = call_args[1]["json"]
        system_msgs = [m for m in request_json["messages"] if m["role"] == "system"]
        assert len(system_msgs) == 1
        assert system_msgs[0]["content"] == "You are a test assistant."

    @pytest.mark.asyncio
    async def test_stream_tools_passed_to_ollama(self):
        """Tool definitions should be included in the Ollama request."""
        client = InferenceClient()
        lines = make_ollama_stream_lines(["Done"])
        tool_defs = [{"type": "function", "function": {"name": "test_tool", "parameters": {}}}]

        mock_http = AsyncMock()
        mock_http.stream = MagicMock(return_value=MockStreamResponse(lines))

        with patch.object(client, '_get_client', return_value=mock_http), \
             patch.object(client.router, 'route', return_value=make_routing_decision()), \
             patch.object(client.router, 'record_success'):

            items = [item async for item in client.chat_stream(
                messages=[Message(role="user", content="Use tool")],
                tools=tool_defs,
            )]

        request_json = mock_http.stream.call_args[1]["json"]
        assert "tools" in request_json
        assert request_json["tools"] == tool_defs

    @pytest.mark.asyncio
    async def test_stream_local_failure_falls_back_to_cloud(self):
        """When local streaming fails and cloud is fallback, should yield cloud response."""
        import httpx
        client = InferenceClient()

        cloud_response = InferenceResponse(
            content="Cloud fallback response",
            model="claude-3",
            tokens_in=10,
            tokens_out=5,
            duration_ms=200,
        )

        # Routing: primary with cloud fallback
        routing = make_routing_decision(ModelTier.PRIMARY)

        with patch.object(client.router, 'route', return_value=routing), \
             patch.object(client, '_stream_ollama_chat', side_effect=LocalModelFailed("timeout")), \
             patch.object(client, '_call_cloud', return_value=cloud_response), \
             patch.object(client.router, 'record_success'):

            items = [item async for item in client.chat_stream(
                messages=[Message(role="user", content="Hello")],
            )]

        str_items = [i for i in items if isinstance(i, str)]
        resp_items = [i for i in items if isinstance(i, InferenceResponse)]

        assert str_items == ["Cloud fallback response"]
        assert resp_items[0].fallback_used is True

    @pytest.mark.asyncio
    async def test_stream_malformed_json_lines_skipped(self):
        """Malformed JSON lines from Ollama should be silently skipped."""
        client = InferenceClient()
        lines = [
            "not valid json",
            json.dumps({"model": "qwen2.5:7b", "message": {"role": "assistant", "content": "OK"}, "done": False}),
            "",  # empty line
            json.dumps({"model": "qwen2.5:7b", "message": {"role": "assistant", "content": ""}, "done": True, "done_reason": "stop", "prompt_eval_count": 5, "eval_count": 1}),
        ]

        mock_http = AsyncMock()
        mock_http.stream = MagicMock(return_value=MockStreamResponse(lines))

        with patch.object(client, '_get_client', return_value=mock_http), \
             patch.object(client.router, 'route', return_value=make_routing_decision()), \
             patch.object(client.router, 'record_success'):

            items = [item async for item in client.chat_stream(
                messages=[Message(role="user", content="Hi")],
            )]

        str_items = [i for i in items if isinstance(i, str)]
        assert str_items == ["OK"]

    @pytest.mark.asyncio
    async def test_stream_metrics_fallback_when_ollama_omits_counts(self):
        """If Ollama doesn't provide token counts, fallback estimation should kick in."""
        client = InferenceClient()
        lines = [
            json.dumps({"model": "qwen2.5:7b", "message": {"role": "assistant", "content": "test"}, "done": False}),
            # Final event with 0 counts (Ollama omits them sometimes)
            json.dumps({"model": "qwen2.5:7b", "message": {"role": "assistant", "content": ""}, "done": True, "done_reason": "stop", "prompt_eval_count": 0, "eval_count": 0}),
        ]

        mock_http = AsyncMock()
        mock_http.stream = MagicMock(return_value=MockStreamResponse(lines))

        with patch.object(client, '_get_client', return_value=mock_http), \
             patch.object(client.router, 'route', return_value=make_routing_decision()), \
             patch.object(client.router, 'record_success'):

            items = [item async for item in client.chat_stream(
                messages=[Message(role="user", content="Hi")],
            )]

        resp_items = [i for i in items if isinstance(i, InferenceResponse)]
        # Fallback estimation should produce non-zero counts
        assert resp_items[0].tokens_in > 0
        assert resp_items[0].tokens_out > 0
