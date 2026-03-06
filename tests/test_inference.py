"""
Tests for the inference module.

Local-only architecture per ADR-001/ADR-010.

Run with: python -m pytest tests/test_inference.py -v
"""

import asyncio
import os
import pytest
import pytest_asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from hestia.inference import (
    InferenceClient,
    InferenceConfig,
    InferenceResponse,
    TokenCounter,
    TokenLimitExceeded,
    LocalModelFailed,
    Message,
    # Router
    ModelRouter,
    ModelTier,
    ModelConfig,
    RoutingDecision,
)


class TestTokenCounter:
    """Tests for TokenCounter."""

    def test_count_empty(self):
        tc = TokenCounter()
        assert tc.count("") == 0
        assert tc.count(None) == 0

    def test_count_simple(self):
        tc = TokenCounter()
        # "Hello world" is typically 2 tokens
        tokens = tc.count("Hello world")
        assert tokens > 0
        assert tokens < 10

    def test_count_longer_text(self):
        tc = TokenCounter()
        text = "The quick brown fox jumps over the lazy dog. " * 10
        tokens = tc.count(text)
        assert tokens > 50

    def test_count_messages(self):
        tc = TokenCounter()
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there!"),
        ]
        tokens = tc.count_messages(messages)
        # Should include overhead for message structure
        assert tokens > tc.count("Hello") + tc.count("Hi there!")

    def test_truncate_to_limit(self):
        tc = TokenCounter()
        long_text = "word " * 1000
        truncated = tc.truncate_to_limit(long_text, 50)
        assert tc.count(truncated) <= 50


class TestInferenceConfig:
    """Tests for InferenceConfig."""

    def test_default_config(self):
        config = InferenceConfig()
        # Default is now qwen3.5:9b (fast model)
        assert config.model_name == "qwen3.5:9b"
        assert config.context_limit == 32768
        assert config.max_retries == 3

    def test_config_from_yaml(self):
        # Test with actual config file
        config_path = Path(__file__).parent.parent / "hestia" / "config" / "inference.yaml"
        if config_path.exists():
            config = InferenceConfig.from_yaml(config_path)
            assert config.model_name is not None

    def test_config_from_missing_yaml(self):
        config = InferenceConfig.from_yaml(Path("/nonexistent/path.yaml"))
        # Should return default config
        assert config.model_name == "qwen3.5:9b"


class TestInferenceClient:
    """Tests for InferenceClient."""

    def test_client_init(self):
        client = InferenceClient()
        assert client.config is not None
        assert client.token_counter is not None
        assert client.router is not None

    def test_token_limit_check(self):
        client = InferenceClient()

        # Should not raise for small token counts
        client._check_token_limit(1000)

        # Should raise for counts over limit
        with pytest.raises(TokenLimitExceeded):
            client._check_token_limit(50000)

    def test_count_request_tokens(self):
        client = InferenceClient()
        tokens = client._count_request_tokens(
            prompt="What is 2+2?",
            system="You are a helpful assistant.",
        )
        assert tokens > 0
        assert tokens < 100


class TestModelRouter:
    """Tests for ModelRouter (local-only architecture)."""

    def test_router_init(self):
        router = ModelRouter()
        assert router.primary_model is not None
        assert router.complex_model is not None

    def test_route_default_primary(self):
        router = ModelRouter()
        decision = router.route(prompt="Hello", token_count=10)
        assert decision.tier == ModelTier.PRIMARY
        assert decision.reason == "default_primary"

    def test_route_complex_patterns(self):
        # Create router with complex model enabled, coding disabled
        router = ModelRouter()
        router.complex_model.enabled = True
        router.coding_model.enabled = False

        # Test pattern matching
        decision = router.route(prompt="Please analyze this code", token_count=100)
        assert decision.tier == ModelTier.COMPLEX
        assert "complex_request_pattern" in decision.reason

    def test_route_token_threshold(self):
        router = ModelRouter()
        router.complex_model.enabled = True
        router.coding_model.enabled = False

        # Below threshold - should use primary
        decision = router.route(prompt="Short query", token_count=100)
        # May still match patterns

        # Above threshold - should use complex
        decision = router.route(prompt="Simple query", token_count=600)
        assert decision.tier == ModelTier.COMPLEX

    def test_success_resets_failures(self):
        router = ModelRouter()

        # Record failures then success
        router.record_failure(ModelTier.PRIMARY)
        router.record_success(ModelTier.PRIMARY)

        # Failures should be reset
        assert router._failure_counts[ModelTier.PRIMARY] == 0

    def test_get_status(self):
        router = ModelRouter()
        status = router.get_status()

        assert "primary_model" in status
        assert "coding_model" in status
        assert "complex_model" in status
        assert "architecture" in status
        assert status["architecture"] == "local-only"


class TestCodingTier:
    """Tests for CODING model tier routing."""

    def test_coding_tier_routes_code_patterns(self):
        """Coding model is selected for code-related prompts when enabled."""
        router = ModelRouter()
        assert router.coding_model is not None
        assert router.coding_model.enabled is True
        decision = router.route("write code for a REST endpoint")
        assert decision.tier == ModelTier.CODING
        assert decision.model_config.name == "qwen2.5-coder:7b"

    def test_coding_tier_fallback_when_disabled(self):
        """Falls back to primary when coding model is disabled."""
        router = ModelRouter()
        router.coding_model.enabled = False
        decision = router.route("write code for a REST endpoint")
        assert decision.tier == ModelTier.PRIMARY
        assert decision.model_config.name == "qwen3.5:9b"

    def test_coding_tier_in_config_for_tier(self):
        """_get_config_for_tier returns coding model."""
        router = ModelRouter()
        config = router._get_config_for_tier(ModelTier.CODING)
        assert config is not None
        assert config.name == "qwen2.5-coder:7b"

    def test_long_noncoding_prompt_routes_to_complex_not_coding(self):
        """Long prompts without coding keywords go to COMPLEX, not CODING."""
        router = ModelRouter()
        router.complex_model.enabled = True
        # Token count above threshold but no coding/complex keyword
        decision = router.route("tell me about the history of Rome", token_count=600)
        assert decision.tier == ModelTier.COMPLEX
        assert decision.reason == "complex_request_pattern"

    def test_coding_keywords_only_no_token_threshold(self):
        """Coding tier triggers on keywords, not token count alone."""
        router = ModelRouter()
        # Short prompt with coding keyword → CODING
        decision = router.route("write code for a parser")
        assert decision.tier == ModelTier.CODING
        # Long prompt with no coding keyword, complex disabled → PRIMARY
        router.complex_model.enabled = False
        decision = router.route("tell me about the weather today", token_count=600)
        assert decision.tier == ModelTier.PRIMARY


class TestHardwareAdaptation:
    """Tests for hardware-aware model adaptation (speed-based)."""

    def test_adaptation_not_checked_initially(self):
        router = ModelRouter()
        assert router._adaptation_checked is False
        assert router._adaptation_applied is False

    def test_adaptation_skipped_when_disabled(self):
        router = ModelRouter()
        router.hardware_adaptation.enabled = False
        router.check_hardware_adaptation(tokens_out=50, duration_ms=20000)
        assert router._adaptation_checked is True
        assert router._adaptation_applied is False
        assert router.primary_model.name == "qwen3.5:9b"

    def test_adaptation_skipped_with_env_override(self):
        router = ModelRouter()
        with patch.dict(os.environ, {"HESTIA_PRIMARY_MODEL": "custom:model"}):
            router._adaptation_checked = False  # Reset
            router.check_hardware_adaptation(tokens_out=50, duration_ms=20000)
        assert router._adaptation_applied is False

    def test_adaptation_swaps_model_when_too_slow(self):
        """When generation speed is below threshold, swap to fallback."""
        router = ModelRouter()
        # 50 tokens in 20s = 2.5 tok/s (well below 8.0 threshold)
        router.check_hardware_adaptation(tokens_out=50, duration_ms=20000)
        assert router._adaptation_applied is True
        assert router.primary_model.name == "qwen2.5:7b"

    def test_adaptation_keeps_model_when_fast_enough(self):
        """When generation speed is above threshold, keep primary."""
        router = ModelRouter()
        # 50 tokens in 2s = 25 tok/s (well above 8.0 threshold)
        router.check_hardware_adaptation(tokens_out=50, duration_ms=2000)
        assert router._adaptation_applied is False
        assert router.primary_model.name == "qwen3.5:9b"

    def test_adaptation_enables_cloud_smart(self):
        """When adaptation triggers, cloud smart mode is auto-enabled."""
        router = ModelRouter()
        assert router.cloud_routing.state == "disabled"
        # Slow: 3 tok/s
        router.check_hardware_adaptation(tokens_out=30, duration_ms=10000)
        assert router.cloud_routing.state == "enabled_smart"
        assert router.cloud_model.enabled is True

    def test_adaptation_runs_only_once(self):
        """Check runs only once per server lifecycle."""
        router = ModelRouter()
        router._adaptation_checked = True
        original_name = router.primary_model.name
        # Even with slow speed, should no-op since already checked
        router.check_hardware_adaptation(tokens_out=10, duration_ms=50000)
        assert router.primary_model.name == original_name

    def test_adaptation_retries_on_trivial_response(self):
        """Responses with <5 tokens are too short to measure — retry next time."""
        router = ModelRouter()
        router.check_hardware_adaptation(tokens_out=2, duration_ms=1000)
        assert router._adaptation_checked is False  # Will retry
        assert router._adaptation_applied is False

    def test_adaptation_status_in_get_status(self):
        router = ModelRouter()
        status = router.get_status()
        assert "hardware_adaptation" in status
        assert status["hardware_adaptation"]["enabled"] is True
        assert status["hardware_adaptation"]["checked"] is False

    def test_adaptation_skips_if_already_on_fallback(self):
        """Don't adapt if primary is already the fallback model."""
        router = ModelRouter()
        router.primary_model.name = "qwen2.5:7b"
        router.hardware_adaptation.fallback_primary = "qwen2.5:7b"
        # Slow speed but already on fallback
        router.check_hardware_adaptation(tokens_out=50, duration_ms=20000)
        assert router._adaptation_applied is False


class TestLocalInference:
    """Tests for local-only inference flow."""

    @pytest.mark.asyncio
    async def test_local_inference_success(self):
        """Test that local inference works correctly."""
        client = InferenceClient()

        # Mock Ollama response
        with patch.object(client, '_call_ollama') as mock_ollama:
            mock_ollama.return_value = InferenceResponse(
                content="4",
                model="qwen3.5:9b",
                tokens_in=10,
                tokens_out=1,
                duration_ms=100,
            )

            response = await client.complete("What is 2+2?")

            assert response.content == "4"
            assert response.tier == "primary"
            mock_ollama.assert_called_once()

        await client.close()

    @pytest.mark.asyncio
    async def test_response_includes_tier(self):
        """Test that response includes tier information."""
        client = InferenceClient()

        with patch.object(client, '_call_ollama') as mock_ollama:
            mock_ollama.return_value = InferenceResponse(
                content="Hello!",
                model="qwen3.5:9b",
                tokens_in=5,
                tokens_out=2,
                duration_ms=50,
            )

            response = await client.complete("Say hi")

            assert response.tier is not None
            assert response.fallback_used == False

        await client.close()


class TestNativeToolCalling:
    """Tests for native Ollama tool calling support."""

    def test_inference_response_tool_calls_default_none(self):
        """InferenceResponse.tool_calls defaults to None."""
        response = InferenceResponse(
            content="Hello",
            model="qwen3.5:9b",
            tokens_in=5,
            tokens_out=2,
            duration_ms=50,
        )
        assert response.tool_calls is None

    def test_inference_response_with_tool_calls(self):
        """InferenceResponse can hold structured tool_calls."""
        tool_calls = [{"function": {"name": "get_today_events", "arguments": {}}}]
        response = InferenceResponse(
            content="",
            model="qwen3.5:9b",
            tokens_in=100,
            tokens_out=10,
            duration_ms=200,
            tool_calls=tool_calls,
        )
        assert response.tool_calls is not None
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["function"]["name"] == "get_today_events"

    def test_validation_allows_empty_content_with_tool_calls(self):
        """Validation should not reject empty content when tool_calls present."""
        client = InferenceClient()
        response = InferenceResponse(
            content="",
            model="qwen3.5:9b",
            tokens_in=100,
            tokens_out=10,
            duration_ms=200,
            tool_calls=[{"function": {"name": "list_events", "arguments": {"days": 1}}}],
        )
        # Should not raise ValidationError
        client._validate_response(response)

    def test_validation_rejects_empty_content_without_tool_calls(self):
        """Validation should reject empty content when no tool_calls."""
        from hestia.inference.client import ValidationError
        client = InferenceClient()
        response = InferenceResponse(
            content="",
            model="qwen3.5:9b",
            tokens_in=100,
            tokens_out=10,
            duration_ms=200,
        )
        with pytest.raises(ValidationError):
            client._validate_response(response)

    @pytest.mark.asyncio
    async def test_tools_param_threaded_to_ollama(self):
        """Verify tools param is passed through chat → routing → ollama."""
        client = InferenceClient()
        tools = [{"type": "function", "function": {"name": "test_tool", "parameters": {}}}]

        with patch.object(client, '_call_ollama') as mock_ollama:
            mock_ollama.return_value = InferenceResponse(
                content="I'll help you.",
                model="qwen3.5:9b",
                tokens_in=100,
                tokens_out=10,
                duration_ms=200,
            )

            response = await client.chat(
                messages=[Message(role="user", content="Hello")],
                tools=tools,
            )

            # Verify _call_ollama was called with tools
            call_kwargs = mock_ollama.call_args
            assert call_kwargs.kwargs.get("tools") == tools or \
                   (len(call_kwargs.args) > 0 and "tools" in str(call_kwargs))

        await client.close()

    @pytest.mark.asyncio
    async def test_tool_calls_extracted_from_ollama_response(self):
        """Verify tool_calls are extracted from mock Ollama response."""
        client = InferenceClient()

        with patch.object(client, '_call_ollama') as mock_ollama:
            mock_ollama.return_value = InferenceResponse(
                content="",
                model="qwen3.5:9b",
                tokens_in=100,
                tokens_out=10,
                duration_ms=200,
                tool_calls=[{"function": {"name": "get_today_events", "arguments": {}}}],
            )

            response = await client.chat(
                messages=[Message(role="user", content="What's on my calendar?")],
                tools=[{"type": "function", "function": {"name": "get_today_events"}}],
            )

            assert response.tool_calls is not None
            assert response.tool_calls[0]["function"]["name"] == "get_today_events"

        await client.close()

    @pytest.mark.asyncio
    async def test_chat_without_tools_works_unchanged(self):
        """Verify chat without tools param still works (backward compat)."""
        client = InferenceClient()

        with patch.object(client, '_call_ollama') as mock_ollama:
            mock_ollama.return_value = InferenceResponse(
                content="Hello!",
                model="qwen3.5:9b",
                tokens_in=5,
                tokens_out=2,
                duration_ms=50,
            )

            response = await client.chat(
                messages=[Message(role="user", content="Hi")],
            )

            assert response.content == "Hello!"
            assert response.tool_calls is None
            # Verify tools was not passed (or passed as None)
            call_kwargs = mock_ollama.call_args.kwargs
            assert call_kwargs.get("tools") is None

        await client.close()


@pytest.mark.integration
class TestDefaultAgentPerTier:
    """Tests for default_agent on ModelConfig (Sprint 11.5 Task B3)."""

    def test_primary_default_agent_from_config(self):
        """Primary model loads default_agent from inference.yaml."""
        router = ModelRouter()
        assert router.primary_model.default_agent == "tia"

    def test_coding_default_agent_from_config(self):
        """Coding model loads default_agent from inference.yaml."""
        router = ModelRouter()
        assert router.coding_model.default_agent == "olly"

    def test_complex_default_agent_from_config(self):
        """Complex model loads default_agent from inference.yaml."""
        router = ModelRouter()
        assert router.complex_model.default_agent == "mira"

    def test_cloud_no_default_agent(self):
        """Cloud model has no default_agent (None)."""
        router = ModelRouter()
        assert router.cloud_model.default_agent is None

    def test_get_suggested_agent_primary(self):
        """Simple prompt suggests tia (primary tier)."""
        router = ModelRouter()
        agent = router.get_suggested_agent("hello how are you")
        assert agent == "tia"

    def test_get_suggested_agent_coding(self):
        """Coding prompt suggests olly (coding tier)."""
        router = ModelRouter()
        agent = router.get_suggested_agent("write code for a REST API")
        assert agent == "olly"

    def test_get_suggested_agent_cloud_full(self):
        """Cloud full mode returns None (no default agent on cloud)."""
        router = ModelRouter(cloud_state="enabled_full")
        agent = router.get_suggested_agent("hello")
        assert agent is None

    def test_routing_decision_carries_default_agent(self):
        """RoutingDecision.model_config has default_agent from tier config."""
        router = ModelRouter()
        decision = router.route("write code for a parser")
        assert decision.tier == ModelTier.CODING
        assert decision.model_config.default_agent == "olly"

    def test_default_agent_none_when_not_configured(self):
        """ModelConfig default_agent is None when not set."""
        config = ModelConfig(name="test-model")
        assert config.default_agent is None

    def test_default_agent_overridable(self):
        """default_agent can be set to custom value."""
        router = ModelRouter()
        router.primary_model.default_agent = "custom"
        assert router.get_suggested_agent("hello") == "custom"


class TestInferenceClientIntegration:
    """
    Integration tests that require Ollama running.

    These tests are skipped if Ollama is not available.
    Run on Mac Mini with: pytest tests/test_inference.py -v -m integration
    """

    @pytest_asyncio.fixture
    async def client(self):
        client = InferenceClient()
        yield client
        await client.close()

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.timeout(30)  # Health check should be fast
    async def test_health_check(self, client):
        """Test health check endpoint."""
        health = await client.health_check()
        assert "status" in health
        assert "local" in health
        assert "router" in health
        assert "architecture" in health
        assert health["architecture"] == "local-only"

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.timeout(120)  # Qwen 2.5 7B should be faster
    async def test_simple_completion(self, client):
        """Test simple completion with fast model."""
        response = await client.complete(
            prompt="What is 2+2? Reply with just the number.",
            temperature=0.0,
            max_tokens=10,
        )
        assert isinstance(response, InferenceResponse)
        assert response.content is not None
        assert "4" in response.content
        assert response.tokens_in > 0
        assert response.tokens_out > 0
        assert response.tier is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.timeout(120)  # Qwen 2.5 7B should be faster
    async def test_chat_completion(self, client):
        """Test chat completion."""
        messages = [
            Message(role="user", content="Say hello in exactly 3 words."),
        ]
        response = await client.chat(
            messages=messages,
            system="You are a helpful assistant.",
            temperature=0.0,
        )
        assert isinstance(response, InferenceResponse)
        assert response.content is not None
        assert response.tier is not None


if __name__ == "__main__":
    # Quick manual test
    async def main():
        print("Testing inference client (local-only architecture)...")

        # Test token counter
        tc = TokenCounter()
        print(f"Token count for 'Hello world': {tc.count('Hello world')}")

        # Test client init
        client = InferenceClient()
        print(f"Config: {client.config.model_name}")
        print(f"Router primary: {client.router.primary_model.name}")
        print(f"Router complex: {client.router.complex_model.name} (enabled: {client.router.complex_model.enabled})")

        # Test health check
        health = await client.health_check()
        print(f"\nHealth status: {health.get('status')}")
        print(f"  Local: {health.get('local', {}).get('status')}")
        print(f"  Architecture: {health.get('architecture')}")

        if health.get("local", {}).get("ollama_available"):
            # Test completion
            print("\nTesting completion with fast model...")
            try:
                response = await client.complete(
                    prompt="What is the capital of France? Reply in one word.",
                    max_tokens=10,
                )
                print(f"Response: {response.content}")
                print(f"Model: {response.model}")
                print(f"Tier: {response.tier}")
                print(f"Tokens: {response.tokens_in} in, {response.tokens_out} out")
                print(f"Duration: {response.duration_ms:.0f}ms")
            except Exception as e:
                print(f"Error: {e}")
        else:
            print("\nOllama not available, skipping completion test")

        await client.close()

    asyncio.run(main())
