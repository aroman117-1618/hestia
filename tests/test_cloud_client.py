"""
Tests for Hestia cloud inference client.

Tests the CloudInferenceClient which makes actual LLM calls
to Anthropic, OpenAI, and Google providers. All HTTP calls are mocked.
"""

import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from hestia.cloud.client import (
    CloudInferenceClient,
    CloudInferenceError,
    CloudAuthError,
    CloudRateLimitError,
    CloudModelError,
    get_cloud_inference_client,
)
from hestia.cloud.models import CloudProvider, CloudUsageRecord
from hestia.inference.client import InferenceResponse, Message


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def client() -> CloudInferenceClient:
    """Provide a CloudInferenceClient."""
    return CloudInferenceClient(request_timeout=30.0)


@pytest.fixture
def messages() -> list:
    """Sample conversation messages."""
    return [
        Message(role="user", content="What is the capital of France?"),
    ]


@pytest.fixture
def multi_turn_messages() -> list:
    """Multi-turn conversation."""
    return [
        Message(role="user", content="Hello"),
        Message(role="assistant", content="Hi there!"),
        Message(role="user", content="What is 2+2?"),
    ]


# ── Helpers ────────────────────────────────────────────────────────────


def _mock_response(
    status_code: int = 200,
    json_data: dict = None,
    headers: dict = None,
) -> httpx.Response:
    """Create a mock httpx.Response."""
    resp = httpx.Response(
        status_code=status_code,
        json=json_data or {},
        headers=headers or {},
        request=httpx.Request("POST", "https://example.com"),
    )
    return resp


# ── Test: Anthropic Provider ──────────────────────────────────────────


class TestAnthropicProvider:
    """Tests for Anthropic API integration."""

    @pytest.mark.asyncio
    async def test_anthropic_basic_completion(self, client: CloudInferenceClient, messages: list) -> None:
        mock_resp = _mock_response(200, {
            "content": [{"type": "text", "text": "The capital of France is Paris."}],
            "model": "claude-sonnet-4-20250514",
            "usage": {"input_tokens": 15, "output_tokens": 10},
            "stop_reason": "end_turn",
        })

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            response = await client.complete(
                provider=CloudProvider.ANTHROPIC,
                model_id="claude-sonnet-4-20250514",
                api_key="sk-ant-test-key",
                messages=messages,
                system="You are a helpful assistant.",
            )

        assert response.content == "The capital of France is Paris."
        assert response.tokens_in == 15
        assert response.tokens_out == 10
        assert response.tier == "cloud"
        assert response.model == "claude-sonnet-4-20250514"

    @pytest.mark.asyncio
    async def test_anthropic_system_prompt_sent(self, client: CloudInferenceClient, messages: list) -> None:
        mock_resp = _mock_response(200, {
            "content": [{"type": "text", "text": "Response"}],
            "model": "claude-sonnet-4-20250514",
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "stop_reason": "end_turn",
        })

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            await client.complete(
                provider=CloudProvider.ANTHROPIC,
                model_id="claude-sonnet-4-20250514",
                api_key="sk-ant-key",
                messages=messages,
                system="Be concise.",
            )

            # Verify system was passed as top-level field
            call_args = mock_http.post.call_args
            body = call_args.kwargs.get("json", call_args[1].get("json", {}))
            assert body.get("system") == "Be concise."

    @pytest.mark.asyncio
    async def test_anthropic_multi_content_blocks(self, client: CloudInferenceClient, messages: list) -> None:
        mock_resp = _mock_response(200, {
            "content": [
                {"type": "text", "text": "Part 1. "},
                {"type": "text", "text": "Part 2."},
            ],
            "model": "claude-sonnet-4-20250514",
            "usage": {"input_tokens": 10, "output_tokens": 8},
            "stop_reason": "end_turn",
        })

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            response = await client.complete(
                provider=CloudProvider.ANTHROPIC,
                model_id="claude-sonnet-4-20250514",
                api_key="sk-ant-key",
                messages=messages,
            )

        assert response.content == "Part 1. Part 2."

    @pytest.mark.asyncio
    async def test_anthropic_filters_system_messages(self, client: CloudInferenceClient) -> None:
        """Anthropic API expects user/assistant only — system messages should be filtered."""
        messages_with_system = [
            Message(role="system", content="System text"),
            Message(role="user", content="Hello"),
        ]
        mock_resp = _mock_response(200, {
            "content": [{"type": "text", "text": "Hi"}],
            "model": "claude-sonnet-4-20250514",
            "usage": {"input_tokens": 5, "output_tokens": 2},
            "stop_reason": "end_turn",
        })

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            await client.complete(
                provider=CloudProvider.ANTHROPIC,
                model_id="claude-sonnet-4-20250514",
                api_key="sk-ant-key",
                messages=messages_with_system,
            )

            call_args = mock_http.post.call_args
            body = call_args.kwargs.get("json", call_args[1].get("json", {}))
            msg_roles = [m["role"] for m in body["messages"]]
            assert "system" not in msg_roles


# ── Test: OpenAI Provider ─────────────────────────────────────────────


class TestOpenAIProvider:
    """Tests for OpenAI API integration."""

    @pytest.mark.asyncio
    async def test_openai_basic_completion(self, client: CloudInferenceClient, messages: list) -> None:
        mock_resp = _mock_response(200, {
            "choices": [
                {"message": {"content": "Paris is the capital."}, "finish_reason": "stop"}
            ],
            "model": "gpt-4o",
            "usage": {"prompt_tokens": 12, "completion_tokens": 8},
        })

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            response = await client.complete(
                provider=CloudProvider.OPENAI,
                model_id="gpt-4o",
                api_key="sk-openai-test-key",
                messages=messages,
            )

        assert response.content == "Paris is the capital."
        assert response.tokens_in == 12
        assert response.tokens_out == 8
        assert response.tier == "cloud"

    @pytest.mark.asyncio
    async def test_openai_system_in_messages(self, client: CloudInferenceClient, messages: list) -> None:
        mock_resp = _mock_response(200, {
            "choices": [{"message": {"content": "Ok"}, "finish_reason": "stop"}],
            "model": "gpt-4o",
            "usage": {"prompt_tokens": 10, "completion_tokens": 2},
        })

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            await client.complete(
                provider=CloudProvider.OPENAI,
                model_id="gpt-4o",
                api_key="sk-oai-key",
                messages=messages,
                system="Be brief.",
            )

            # OpenAI puts system as first message
            call_args = mock_http.post.call_args
            body = call_args.kwargs.get("json", call_args[1].get("json", {}))
            assert body["messages"][0]["role"] == "system"
            assert body["messages"][0]["content"] == "Be brief."

    @pytest.mark.asyncio
    async def test_openai_empty_choices(self, client: CloudInferenceClient, messages: list) -> None:
        mock_resp = _mock_response(200, {
            "choices": [],
            "model": "gpt-4o",
            "usage": {"prompt_tokens": 10, "completion_tokens": 0},
        })

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            response = await client.complete(
                provider=CloudProvider.OPENAI,
                model_id="gpt-4o",
                api_key="sk-oai-key",
                messages=messages,
            )

        assert response.content == ""


# ── Test: Google Gemini Provider ──────────────────────────────────────


class TestGoogleProvider:
    """Tests for Google Gemini API integration."""

    @pytest.mark.asyncio
    async def test_google_basic_completion(self, client: CloudInferenceClient, messages: list) -> None:
        mock_resp = _mock_response(200, {
            "candidates": [
                {"content": {"parts": [{"text": "Paris."}]}, "finishReason": "STOP"}
            ],
            "usageMetadata": {"promptTokenCount": 8, "candidatesTokenCount": 3},
        })

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            response = await client.complete(
                provider=CloudProvider.GOOGLE,
                model_id="gemini-2.0-flash",
                api_key="google-api-key",
                messages=messages,
            )

        assert response.content == "Paris."
        assert response.tokens_in == 8
        assert response.tokens_out == 3
        assert response.tier == "cloud"

    @pytest.mark.asyncio
    async def test_google_system_instruction(self, client: CloudInferenceClient, messages: list) -> None:
        mock_resp = _mock_response(200, {
            "candidates": [{"content": {"parts": [{"text": "Ok"}]}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 1},
        })

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            await client.complete(
                provider=CloudProvider.GOOGLE,
                model_id="gemini-2.0-flash",
                api_key="google-key",
                messages=messages,
                system="You are Hestia.",
            )

            call_args = mock_http.post.call_args
            body = call_args.kwargs.get("json", call_args[1].get("json", {}))
            assert "systemInstruction" in body
            assert body["systemInstruction"]["parts"][0]["text"] == "You are Hestia."

    @pytest.mark.asyncio
    async def test_google_role_mapping(self, client: CloudInferenceClient, multi_turn_messages: list) -> None:
        mock_resp = _mock_response(200, {
            "candidates": [{"content": {"parts": [{"text": "4"}]}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 1},
        })

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            await client.complete(
                provider=CloudProvider.GOOGLE,
                model_id="gemini-2.0-flash",
                api_key="google-key",
                messages=multi_turn_messages,
            )

            call_args = mock_http.post.call_args
            body = call_args.kwargs.get("json", call_args[1].get("json", {}))
            roles = [c["role"] for c in body["contents"]]
            assert roles == ["user", "model", "user"]

    @pytest.mark.asyncio
    async def test_google_multi_part_response(self, client: CloudInferenceClient, messages: list) -> None:
        mock_resp = _mock_response(200, {
            "candidates": [
                {"content": {"parts": [{"text": "Part A. "}, {"text": "Part B."}]}, "finishReason": "STOP"}
            ],
            "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 5},
        })

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            response = await client.complete(
                provider=CloudProvider.GOOGLE,
                model_id="gemini-2.0-flash",
                api_key="google-key",
                messages=messages,
            )

        assert response.content == "Part A. Part B."


# ── Test: Error Handling ──────────────────────────────────────────────


class TestCloudErrorHandling:
    """Tests for error handling across providers."""

    @pytest.mark.asyncio
    async def test_auth_error_401(self, client: CloudInferenceClient, messages: list) -> None:
        mock_resp = _mock_response(401, {"error": {"message": "Invalid API key"}})

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            with pytest.raises(CloudAuthError, match="authentication failed"):
                await client.complete(
                    provider=CloudProvider.ANTHROPIC,
                    model_id="claude-sonnet-4-20250514",
                    api_key="bad-key",
                    messages=messages,
                )

    @pytest.mark.asyncio
    async def test_auth_error_403(self, client: CloudInferenceClient, messages: list) -> None:
        mock_resp = _mock_response(403, {"error": {"message": "Forbidden"}})

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            with pytest.raises(CloudAuthError):
                await client.complete(
                    provider=CloudProvider.OPENAI,
                    model_id="gpt-4o",
                    api_key="bad-key",
                    messages=messages,
                )

    @pytest.mark.asyncio
    async def test_rate_limit_429(self, client: CloudInferenceClient, messages: list) -> None:
        mock_resp = _mock_response(
            429,
            {"error": {"message": "Rate limited"}},
            headers={"retry-after": "30"},
        )

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            with pytest.raises(CloudRateLimitError) as exc_info:
                await client.complete(
                    provider=CloudProvider.ANTHROPIC,
                    model_id="claude-sonnet-4-20250514",
                    api_key="sk-ant-key",
                    messages=messages,
                )
            assert exc_info.value.retry_after == 30.0

    @pytest.mark.asyncio
    async def test_model_not_found_404(self, client: CloudInferenceClient, messages: list) -> None:
        mock_resp = _mock_response(404, {"error": {"message": "Model not found"}})

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            with pytest.raises(CloudModelError, match="not found"):
                await client.complete(
                    provider=CloudProvider.OPENAI,
                    model_id="nonexistent-model",
                    api_key="sk-key",
                    messages=messages,
                )

    @pytest.mark.asyncio
    async def test_server_error_500(self, client: CloudInferenceClient, messages: list) -> None:
        mock_resp = _mock_response(500, {"error": {"message": "Internal error"}})

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            with pytest.raises(CloudInferenceError, match="server error"):
                await client.complete(
                    provider=CloudProvider.GOOGLE,
                    model_id="gemini-2.0-flash",
                    api_key="google-key",
                    messages=messages,
                )

    @pytest.mark.asyncio
    async def test_no_api_key_raises(self, client: CloudInferenceClient, messages: list) -> None:
        with pytest.raises(CloudAuthError, match="No API key"):
            await client.complete(
                provider=CloudProvider.ANTHROPIC,
                model_id="claude-sonnet-4-20250514",
                api_key="",
                messages=messages,
            )

    @pytest.mark.asyncio
    async def test_timeout_error(self, client: CloudInferenceClient, messages: list) -> None:
        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(side_effect=httpx.ReadTimeout("timeout"))
            mock_get.return_value = mock_http

            with pytest.raises(CloudInferenceError, match="timed out"):
                await client.complete(
                    provider=CloudProvider.ANTHROPIC,
                    model_id="claude-sonnet-4-20250514",
                    api_key="sk-key",
                    messages=messages,
                )

    @pytest.mark.asyncio
    async def test_connect_error(self, client: CloudInferenceClient, messages: list) -> None:
        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_get.return_value = mock_http

            with pytest.raises(CloudInferenceError, match="Cannot connect"):
                await client.complete(
                    provider=CloudProvider.OPENAI,
                    model_id="gpt-4o",
                    api_key="sk-key",
                    messages=messages,
                )


# ── Test: Usage Record Building ───────────────────────────────────────


class TestUsageRecordBuilding:
    """Tests for usage record creation from responses."""

    def test_build_usage_record(self, client: CloudInferenceClient) -> None:
        response = InferenceResponse(
            content="Test",
            model="claude-sonnet-4-20250514",
            tokens_in=100,
            tokens_out=50,
            duration_ms=1500.0,
            tier="cloud",
        )
        record = client.build_usage_record(
            provider=CloudProvider.ANTHROPIC,
            model_id="claude-sonnet-4-20250514",
            response=response,
            request_id="req-123",
            mode="tia",
        )
        assert isinstance(record, CloudUsageRecord)
        assert record.provider == CloudProvider.ANTHROPIC
        assert record.tokens_in == 100
        assert record.tokens_out == 50
        assert record.cost_usd > 0
        assert record.request_id == "req-123"
        assert record.mode == "tia"

    def test_build_usage_record_cost_calculation(self, client: CloudInferenceClient) -> None:
        response = InferenceResponse(
            content="Test",
            model="gpt-4o",
            tokens_in=1000,
            tokens_out=500,
            duration_ms=2000.0,
            tier="cloud",
        )
        record = client.build_usage_record(
            provider=CloudProvider.OPENAI,
            model_id="gpt-4o",
            response=response,
        )
        # GPT-4o: 0.005/1K in + 0.015/1K out = 0.005 + 0.0075 = 0.0125
        expected_cost = (1000 / 1000) * 0.005 + (500 / 1000) * 0.015
        assert record.cost_usd == pytest.approx(expected_cost, abs=0.001)


# ── Test: Client Lifecycle ────────────────────────────────────────────


class TestClientLifecycle:
    """Tests for client creation and cleanup."""

    @pytest.mark.asyncio
    async def test_close_client(self) -> None:
        client = CloudInferenceClient()
        # Force client creation
        http = await client._get_client()
        assert http is not None
        await client.close()
        assert client._http_client is None

    @pytest.mark.asyncio
    async def test_close_idempotent(self) -> None:
        client = CloudInferenceClient()
        await client.close()
        await client.close()  # Should not raise

    def test_default_timeout(self) -> None:
        client = CloudInferenceClient()
        assert client.request_timeout == 60.0

    def test_custom_timeout(self) -> None:
        client = CloudInferenceClient(request_timeout=120.0)
        assert client.request_timeout == 120.0


# ── Test: Router Cloud Integration ────────────────────────────────────


class TestRouterCloudIntegration:
    """Tests for cloud routing in the ModelRouter."""

    def test_cloud_tier_exists(self) -> None:
        from hestia.inference.router import ModelTier
        assert hasattr(ModelTier, "CLOUD")
        assert ModelTier.CLOUD.value == "cloud"

    def test_router_disabled_no_cloud(self) -> None:
        from hestia.inference.router import ModelRouter
        router = ModelRouter(cloud_state="disabled")
        decision = router.route("hello", token_count=10)
        assert decision.tier.value == "primary"
        assert decision.fallback_tier is None

    def test_router_enabled_full_routes_to_cloud(self) -> None:
        from hestia.inference.router import ModelRouter, ModelTier
        router = ModelRouter(cloud_state="enabled_full")
        decision = router.route("hello", token_count=10)
        assert decision.tier == ModelTier.CLOUD
        assert decision.reason == "cloud_full_mode"

    def test_router_enabled_smart_low_tokens_local(self) -> None:
        from hestia.inference.router import ModelRouter, ModelTier
        router = ModelRouter(cloud_state="enabled_smart")
        decision = router.route("hello", token_count=100)
        assert decision.tier == ModelTier.PRIMARY
        assert decision.fallback_tier == ModelTier.CLOUD

    def test_router_enabled_smart_high_tokens_cloud(self) -> None:
        from hestia.inference.router import ModelRouter, ModelTier
        router = ModelRouter(cloud_state="enabled_smart")
        decision = router.route("analyze this very long prompt", token_count=20000)
        assert decision.tier == ModelTier.CLOUD
        assert decision.reason == "cloud_smart_token_spillover"

    def test_router_set_cloud_state(self) -> None:
        from hestia.inference.router import ModelRouter
        router = ModelRouter(cloud_state="disabled")
        assert router.cloud_routing.state == "disabled"
        assert not router.cloud_model.enabled

        router.set_cloud_state("enabled_smart")
        assert router.cloud_routing.state == "enabled_smart"
        assert router.cloud_model.enabled

    def test_router_status_includes_cloud(self) -> None:
        from hestia.inference.router import ModelRouter
        router = ModelRouter(cloud_state="enabled_smart")
        status = router.get_status()
        assert "cloud" in status
        assert status["cloud"]["state"] == "enabled_smart"
        assert status["architecture"] == "hybrid (enabled_smart)"

    def test_router_status_local_only(self) -> None:
        from hestia.inference.router import ModelRouter
        router = ModelRouter(cloud_state="disabled")
        status = router.get_status()
        assert status["cloud"]["state"] == "disabled"
        assert status["architecture"] == "local-only"

    def test_router_fallback_primary_to_cloud_smart(self) -> None:
        from hestia.inference.router import ModelRouter, ModelTier
        router = ModelRouter(cloud_state="enabled_smart")
        fallback = router._get_fallback_tier(ModelTier.PRIMARY)
        assert fallback == ModelTier.CLOUD

    def test_router_fallback_primary_no_cloud_disabled(self) -> None:
        from hestia.inference.router import ModelRouter, ModelTier
        router = ModelRouter(cloud_state="disabled")
        fallback = router._get_fallback_tier(ModelTier.PRIMARY)
        assert fallback is None

    def test_router_fallback_cloud_to_primary(self) -> None:
        from hestia.inference.router import ModelRouter, ModelTier
        router = ModelRouter(cloud_state="enabled_full")
        fallback = router._get_fallback_tier(ModelTier.CLOUD)
        assert fallback == ModelTier.PRIMARY

    def test_router_force_cloud_tier(self) -> None:
        from hestia.inference.router import ModelRouter, ModelTier
        router = ModelRouter(cloud_state="enabled_smart")
        decision = router.route("test", force_tier=ModelTier.CLOUD)
        assert decision.tier == ModelTier.CLOUD

    def test_router_failure_tracking_cloud(self) -> None:
        from hestia.inference.router import ModelRouter, ModelTier
        router = ModelRouter(cloud_state="enabled_smart")
        router.record_failure(ModelTier.CLOUD)
        assert router._failure_counts[ModelTier.CLOUD] == 1
        router.record_success(ModelTier.CLOUD)
        assert router._failure_counts[ModelTier.CLOUD] == 0

    def test_router_reset_includes_cloud(self) -> None:
        from hestia.inference.router import ModelRouter, ModelTier
        router = ModelRouter(cloud_state="enabled_smart")
        router.record_failure(ModelTier.CLOUD)
        router.reset_failure_counts()
        assert router._failure_counts[ModelTier.CLOUD] == 0


# ── Test: Cloud Tool Calling ─────────────────────────────────────────


class TestCloudToolCalling:
    """Tests for tool calling through cloud providers."""

    @pytest.fixture
    def sample_tools(self) -> list:
        """OpenAI-format tool definitions (same as get_definitions_as_list())."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file from the filesystem.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path"},
                        },
                        "required": ["path"],
                    },
                },
            },
        ]

    @pytest.mark.asyncio
    async def test_anthropic_tools_converted_and_sent(
        self, client: CloudInferenceClient, messages: list, sample_tools: list,
    ) -> None:
        """Tools are converted from OpenAI format to Anthropic format in the request."""
        mock_resp = _mock_response(200, {
            "content": [{"type": "text", "text": "I'll read that file."}],
            "model": "claude-sonnet-4-20250514",
            "usage": {"input_tokens": 20, "output_tokens": 10},
            "stop_reason": "end_turn",
        })

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            await client.complete(
                provider=CloudProvider.ANTHROPIC,
                model_id="claude-sonnet-4-20250514",
                api_key="sk-ant-test-key",
                messages=messages,
                tools=sample_tools,
            )

            call_args = mock_http.post.call_args
            body = call_args.kwargs.get("json", call_args[1].get("json", {}))

            # Verify Anthropic format: {"name", "description", "input_schema"}
            assert "tools" in body
            assert len(body["tools"]) == 1
            tool = body["tools"][0]
            assert tool["name"] == "read_file"
            assert tool["description"] == "Read a file from the filesystem."
            assert "input_schema" in tool
            assert tool["input_schema"]["type"] == "object"

    @pytest.mark.asyncio
    async def test_anthropic_tool_use_response_parsed(
        self, client: CloudInferenceClient, messages: list, sample_tools: list,
    ) -> None:
        """Anthropic tool_use content blocks are parsed into Ollama-compatible format."""
        mock_resp = _mock_response(200, {
            "content": [
                {"type": "text", "text": "Let me read that file."},
                {
                    "type": "tool_use",
                    "id": "toolu_01ABC",
                    "name": "read_file",
                    "input": {"path": "/tmp/test.py"},
                },
            ],
            "model": "claude-sonnet-4-20250514",
            "usage": {"input_tokens": 25, "output_tokens": 15},
            "stop_reason": "tool_use",
        })

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            response = await client.complete(
                provider=CloudProvider.ANTHROPIC,
                model_id="claude-sonnet-4-20250514",
                api_key="sk-ant-test-key",
                messages=messages,
                tools=sample_tools,
            )

        assert response.content == "Let me read that file."
        assert response.tool_calls is not None
        assert len(response.tool_calls) == 1
        tc = response.tool_calls[0]
        assert tc["id"] == "toolu_01ABC"
        assert tc["function"]["name"] == "read_file"
        assert tc["function"]["arguments"] == {"path": "/tmp/test.py"}

    @pytest.mark.asyncio
    async def test_anthropic_multiple_tool_calls(
        self, client: CloudInferenceClient, messages: list, sample_tools: list,
    ) -> None:
        """Multiple tool_use blocks in one response are all parsed."""
        mock_resp = _mock_response(200, {
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_01A",
                    "name": "read_file",
                    "input": {"path": "/tmp/a.py"},
                },
                {
                    "type": "tool_use",
                    "id": "toolu_01B",
                    "name": "read_file",
                    "input": {"path": "/tmp/b.py"},
                },
            ],
            "model": "claude-sonnet-4-20250514",
            "usage": {"input_tokens": 30, "output_tokens": 20},
            "stop_reason": "tool_use",
        })

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            response = await client.complete(
                provider=CloudProvider.ANTHROPIC,
                model_id="claude-sonnet-4-20250514",
                api_key="sk-ant-test-key",
                messages=messages,
                tools=sample_tools,
            )

        assert response.tool_calls is not None
        assert len(response.tool_calls) == 2
        assert response.tool_calls[0]["function"]["arguments"]["path"] == "/tmp/a.py"
        assert response.tool_calls[1]["function"]["arguments"]["path"] == "/tmp/b.py"

    @pytest.mark.asyncio
    async def test_anthropic_no_tools_no_tool_calls(
        self, client: CloudInferenceClient, messages: list,
    ) -> None:
        """Without tools parameter, tool_calls is None."""
        mock_resp = _mock_response(200, {
            "content": [{"type": "text", "text": "Plain text response."}],
            "model": "claude-sonnet-4-20250514",
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "stop_reason": "end_turn",
        })

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            response = await client.complete(
                provider=CloudProvider.ANTHROPIC,
                model_id="claude-sonnet-4-20250514",
                api_key="sk-ant-test-key",
                messages=messages,
            )

        assert response.tool_calls is None

    @pytest.mark.asyncio
    async def test_openai_tools_passed_through(
        self, client: CloudInferenceClient, messages: list, sample_tools: list,
    ) -> None:
        """OpenAI tools are passed through unchanged (already correct format)."""
        mock_resp = _mock_response(200, {
            "choices": [{
                "message": {
                    "content": None,
                    "tool_calls": [{
                        "id": "call_abc",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": '{"path": "/tmp/test.py"}',
                        },
                    }],
                },
                "finish_reason": "tool_calls",
            }],
            "model": "gpt-4",
            "usage": {"prompt_tokens": 20, "completion_tokens": 10},
        })

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            response = await client.complete(
                provider=CloudProvider.OPENAI,
                model_id="gpt-4",
                api_key="sk-openai-test-key",
                messages=messages,
                tools=sample_tools,
            )

            # Verify tools passed through as-is
            call_args = mock_http.post.call_args
            body = call_args.kwargs.get("json", call_args[1].get("json", {}))
            assert body["tools"] == sample_tools

        # Verify response parsed correctly
        assert response.tool_calls is not None
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["id"] == "call_abc"
        assert response.tool_calls[0]["function"]["name"] == "read_file"
        assert response.tool_calls[0]["function"]["arguments"] == {"path": "/tmp/test.py"}
        assert response.content == ""

    @pytest.mark.asyncio
    async def test_google_tools_converted(
        self, client: CloudInferenceClient, messages: list, sample_tools: list,
    ) -> None:
        """Google tools are converted to functionDeclarations format."""
        mock_resp = _mock_response(200, {
            "candidates": [{
                "content": {
                    "parts": [{
                        "functionCall": {
                            "name": "read_file",
                            "args": {"path": "/tmp/test.py"},
                        },
                    }],
                },
                "finishReason": "STOP",
            }],
            "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 10},
        })

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            response = await client.complete(
                provider=CloudProvider.GOOGLE,
                model_id="gemini-pro",
                api_key="google-test-key",
                messages=messages,
                tools=sample_tools,
            )

            # Verify Gemini format: {"functionDeclarations": [...]}
            call_args = mock_http.post.call_args
            body = call_args.kwargs.get("json", call_args[1].get("json", {}))
            assert "tools" in body
            assert "functionDeclarations" in body["tools"][0]
            decl = body["tools"][0]["functionDeclarations"][0]
            assert decl["name"] == "read_file"

        # Verify response parsed correctly
        assert response.tool_calls is not None
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["function"]["name"] == "read_file"
        assert response.tool_calls[0]["function"]["arguments"] == {"path": "/tmp/test.py"}

    @pytest.mark.asyncio
    async def test_anthropic_structured_tool_messages(
        self, client: CloudInferenceClient, sample_tools: list,
    ) -> None:
        """Messages with tool_calls/tool_call_id are converted to Anthropic format."""
        # Simulate a multi-turn: user asks → model calls tool → tool result → model responds
        messages = [
            Message(role="user", content="Read /tmp/test.py"),
            Message(
                role="assistant",
                content="I'll read that file.",
                tool_calls=[{
                    "id": "toolu_01ABC",
                    "function": {"name": "read_file", "arguments": {"path": "/tmp/test.py"}},
                }],
            ),
            Message(
                role="user",
                content="[Tool result for read_file]: print('hello')",
                tool_call_id="toolu_01ABC",
            ),
        ]

        mock_resp = _mock_response(200, {
            "content": [{"type": "text", "text": "The file contains a hello print."}],
            "model": "claude-sonnet-4-20250514",
            "usage": {"input_tokens": 50, "output_tokens": 10},
            "stop_reason": "end_turn",
        })

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            await client.complete(
                provider=CloudProvider.ANTHROPIC,
                model_id="claude-sonnet-4-20250514",
                api_key="sk-ant-test-key",
                messages=messages,
                tools=sample_tools,
            )

            call_args = mock_http.post.call_args
            body = call_args.kwargs.get("json", call_args[1].get("json", {}))
            api_messages = body["messages"]

            # Message 0: plain user message
            assert api_messages[0] == {"role": "user", "content": "Read /tmp/test.py"}

            # Message 1: assistant with tool_use block
            assert api_messages[1]["role"] == "assistant"
            assert isinstance(api_messages[1]["content"], list)
            blocks = api_messages[1]["content"]
            assert blocks[0] == {"type": "text", "text": "I'll read that file."}
            assert blocks[1]["type"] == "tool_use"
            assert blocks[1]["id"] == "toolu_01ABC"
            assert blocks[1]["name"] == "read_file"

            # Message 2: user with tool_result block
            assert api_messages[2]["role"] == "user"
            assert isinstance(api_messages[2]["content"], list)
            result_block = api_messages[2]["content"][0]
            assert result_block["type"] == "tool_result"
            assert result_block["tool_use_id"] == "toolu_01ABC"

    def test_convert_tools_to_anthropic(self, sample_tools: list) -> None:
        """Static converter produces correct Anthropic tool format."""
        result = CloudInferenceClient._convert_tools_to_anthropic(sample_tools)
        assert len(result) == 1
        assert result[0]["name"] == "read_file"
        assert "input_schema" in result[0]
        assert "type" not in result[0]  # No OpenAI "type": "function" wrapper

    def test_convert_tools_to_google(self, sample_tools: list) -> None:
        """Static converter produces correct Google functionDeclarations format."""
        result = CloudInferenceClient._convert_tools_to_google(sample_tools)
        assert len(result) == 1
        assert "functionDeclarations" in result[0]
        decls = result[0]["functionDeclarations"]
        assert len(decls) == 1
        assert decls[0]["name"] == "read_file"
