"""
Tests for the inference module.

Local-only architecture per ADR-001/ADR-010.

Run with: python -m pytest tests/test_inference.py -v
"""

import asyncio
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
        # Default is now qwen2.5:7b (fast model)
        assert config.model_name == "qwen2.5:7b"
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
        assert config.model_name == "qwen2.5:7b"


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
        # Create router with complex model enabled
        router = ModelRouter()
        router.complex_model.enabled = True

        # Test pattern matching
        decision = router.route(prompt="Please analyze this code", token_count=100)
        assert decision.tier == ModelTier.COMPLEX
        assert "complex_request_pattern" in decision.reason

    def test_route_token_threshold(self):
        router = ModelRouter()
        router.complex_model.enabled = True

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
        assert "complex_model" in status
        assert "architecture" in status
        assert status["architecture"] == "local-only"


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
                model="qwen2.5:7b",
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
                model="qwen2.5:7b",
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
            model="qwen2.5:7b",
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
            model="qwen2.5:7b",
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
            model="qwen2.5:7b",
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
            model="qwen2.5:7b",
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
                model="qwen2.5:7b",
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
                model="qwen2.5:7b",
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
                model="qwen2.5:7b",
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
