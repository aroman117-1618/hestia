"""
Inference client for Hestia.

Provides async interface to local models via Ollama and cloud providers.

Features:
- Local inference: fast local model (Qwen 2.5 7B) or complex local (Mixtral)
- Cloud inference: Anthropic, OpenAI, Google via CloudInferenceClient
- Smart routing: local-first with cloud spillover (enabled_smart mode)
- Token counting and context window management (32K budget)
- Retry logic with exponential backoff
- Response validation
- Comprehensive logging
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import httpx
import tiktoken
import yaml

from hestia.logging import get_logger, LogComponent, EventType
from hestia.security import get_credential_manager

from .router import ModelRouter, ModelTier, RoutingDecision, get_router


class ContextSize(Enum):
    """Context window sizes for local models."""
    STANDARD = 32768    # Qwen 2.5 7B / Mixtral 8x7B local (32K)


class InferenceError(Exception):
    """Base exception for inference errors."""
    pass


class TokenLimitExceeded(InferenceError):
    """Raised when request exceeds context window."""
    def __init__(self, tokens: int, limit: int):
        self.tokens = tokens
        self.limit = limit
        super().__init__(f"Token count {tokens} exceeds limit {limit}")


class ValidationError(InferenceError):
    """Raised when response validation fails."""
    pass


class ModelUnavailable(InferenceError):
    """Raised when model is not available."""
    pass


class LocalModelFailed(InferenceError):
    """Raised when local model fails."""
    pass


@dataclass
class InferenceConfig:
    """Configuration for inference client."""
    # Ollama settings
    ollama_host: str = "http://localhost:11434"
    model_name: str = "qwen3.5:9b"  # Default to fast model

    # Generation parameters
    temperature: float = 0.0
    max_tokens: int = 2048
    top_p: float = 0.9

    # Context window management (ADR-011)
    context_limit: int = 32768
    context_warning_threshold: float = 0.9  # Warn at 90%

    # Token budget allocation
    system_prompt_budget: int = 2000
    tool_definitions_budget: int = 1000
    user_model_budget: int = 2000
    # Remaining ~27K for conversation + memory retrieval

    # Retry settings
    max_retries: int = 3
    retry_base_delay: float = 1.0  # seconds
    retry_max_delay: float = 30.0  # seconds

    # Timeout settings (generous for model cold starts on M1)
    request_timeout: float = 300.0  # seconds (5 min for cold start + generation)
    connect_timeout: float = 30.0   # seconds (allow time for Ollama to start)

    @classmethod
    def from_yaml(cls, path: Path) -> "InferenceConfig":
        """Load config from YAML file."""
        if not path.exists():
            return cls()

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})


@dataclass
class InferenceResponse:
    """Response from inference request."""
    content: str
    model: str
    tokens_in: int
    tokens_out: int
    duration_ms: float
    finish_reason: str = "stop"
    raw_response: Dict[str, Any] = field(default_factory=dict)
    # Track which tier was used
    tier: Optional[str] = None
    fallback_used: bool = False
    # Native tool calls from Ollama API (structured, not text-parsed)
    tool_calls: Optional[List[Dict[str, Any]]] = None

    @property
    def total_tokens(self) -> int:
        return self.tokens_in + self.tokens_out

    @property
    def prompt_tokens(self) -> int:
        """Alias for tokens_in."""
        return self.tokens_in

    @property
    def completion_tokens(self) -> int:
        """Alias for tokens_out."""
        return self.tokens_out


@dataclass
class Message:
    """Chat message."""
    role: str  # "system", "user", "assistant"
    content: str


class TokenCounter:
    """
    Token counting using tiktoken.

    Uses cl100k_base encoding (GPT-4/Claude compatible).
    Mixtral uses a different tokenizer but cl100k_base provides
    a reasonable approximation for budget management.
    """

    def __init__(self):
        # cl100k_base is a good approximation for most modern models
        self._encoding = tiktoken.get_encoding("cl100k_base")

    def count(self, text: str) -> int:
        """Count tokens in text."""
        if not text:
            return 0
        return len(self._encoding.encode(text))

    def count_messages(self, messages: List[Message]) -> int:
        """Count tokens in message list."""
        total = 0
        for msg in messages:
            # Add overhead for message structure (~4 tokens per message)
            total += 4
            total += self.count(msg.role)
            total += self.count(msg.content)
        # Add overhead for conversation structure
        total += 3
        return total

    def truncate_to_limit(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token limit."""
        tokens = self._encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return self._encoding.decode(tokens[:max_tokens])


class InferenceClient:
    """
    Async client for LLM inference with local and cloud model routing.

    Tiers:
    1. Primary: Fast local model (Qwen 2.5 7B) - default
    2. Complex: Large local model (Mixtral 8x7B) - when enabled (64GB RAM)
    3. Cloud: Cloud LLM (Anthropic/OpenAI/Google) - when cloud enabled

    Features:
    - Smart model routing based on request complexity and cloud state
    - Cloud spillover when local fails (enabled_smart mode)
    - Token counting and context window management
    - Retry logic with exponential backoff
    - Response validation
    - Comprehensive logging via HestiaLogger
    """

    def __init__(
        self,
        config: Optional[InferenceConfig] = None,
        config_path: Optional[Path] = None,
        router: Optional[ModelRouter] = None,
        cloud_inference_client: Optional[Any] = None,
        cloud_manager: Optional[Any] = None,
    ):
        """
        Initialize inference client.

        Args:
            config: InferenceConfig instance. If None, loads from config_path.
            config_path: Path to YAML config. Defaults to hestia/config/inference.yaml
            router: ModelRouter instance. If None, creates default.
            cloud_inference_client: CloudInferenceClient for cloud calls.
            cloud_manager: CloudManager for provider/key management.
        """
        if config:
            self.config = config
        elif config_path:
            self.config = InferenceConfig.from_yaml(config_path)
        else:
            # Default config path
            default_path = Path(__file__).parent.parent / "config" / "inference.yaml"
            self.config = InferenceConfig.from_yaml(default_path)

        self.logger = get_logger()
        self.token_counter = TokenCounter()
        self._http_client: Optional[httpx.AsyncClient] = None

        # Router for model selection
        self.router = router or get_router()

        # Cloud inference (lazy-loaded if not provided)
        self._cloud_inference_client = cloud_inference_client
        self._cloud_manager = cloud_manager

    async def _get_client(self, timeout: Optional[float] = None) -> httpx.AsyncClient:
        """Get or create HTTP client with optional custom timeout."""
        request_timeout = timeout or self.config.request_timeout

        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=self.config.connect_timeout,
                    read=request_timeout,
                    write=request_timeout,
                    pool=request_timeout,
                )
            )
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def __aenter__(self) -> "InferenceClient":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    def _count_request_tokens(
        self,
        prompt: str,
        system: Optional[str] = None,
        messages: Optional[List[Message]] = None,
    ) -> int:
        """Count total tokens in request."""
        total = 0

        if system:
            total += self.token_counter.count(system)

        if messages:
            total += self.token_counter.count_messages(messages)

        if prompt:
            total += self.token_counter.count(prompt)

        return total

    def _check_token_limit(self, tokens: int, limit: Optional[int] = None) -> None:
        """Check if token count is within limits."""
        limit = limit or self.config.context_limit
        warning_threshold = int(limit * self.config.context_warning_threshold)

        if tokens > limit:
            raise TokenLimitExceeded(tokens, limit)

        if tokens > warning_threshold:
            self.logger.warning(
                f"Token count {tokens} approaching limit {limit} ({tokens/limit*100:.1f}%)",
                component=LogComponent.INFERENCE,
                data={"tokens": tokens, "limit": limit, "percentage": tokens/limit*100}
            )

    async def _call_ollama(
        self,
        prompt: str,
        model_name: str,
        system: Optional[str] = None,
        messages: Optional[List[Message]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> InferenceResponse:
        """Make request to Ollama API."""
        # Create client with appropriate timeout
        client = await self._get_client(timeout)

        # Build request
        request_data: Dict[str, Any] = {
            "model": model_name,
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else self.config.temperature,
                "num_predict": max_tokens or self.config.max_tokens,
                "top_p": self.config.top_p,
            }
        }

        # Use chat endpoint if messages provided, otherwise generate
        if messages:
            request_data["messages"] = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]
            if system:
                request_data["messages"].insert(0, {"role": "system", "content": system})
            # Pass native tool definitions to Ollama (structured tool calling)
            if tools:
                request_data["tools"] = tools
            endpoint = f"{self.config.ollama_host}/api/chat"
        else:
            request_data["prompt"] = prompt
            if system:
                request_data["system"] = system
            endpoint = f"{self.config.ollama_host}/api/generate"

        start_time = time.perf_counter()

        response = await client.post(endpoint, json=request_data)
        response.raise_for_status()

        duration_ms = (time.perf_counter() - start_time) * 1000
        data = response.json()

        # Extract response content and native tool calls
        tool_calls_response = None
        if messages:
            message_data = data.get("message", {})
            content = message_data.get("content", "")
            # Ollama returns tool_calls as list of {"function": {"name": ..., "arguments": {...}}}
            raw_tool_calls = message_data.get("tool_calls")
            if raw_tool_calls:
                tool_calls_response = raw_tool_calls
        else:
            content = data.get("response", "")

        # Get token counts from response or estimate
        tokens_in = data.get("prompt_eval_count", 0)
        tokens_out = data.get("eval_count", 0)

        # Fallback to estimation if not provided
        if tokens_in == 0:
            tokens_in = self._count_request_tokens(prompt, system, messages)
        if tokens_out == 0:
            tokens_out = self.token_counter.count(content)

        return InferenceResponse(
            content=content,
            model=model_name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_ms=duration_ms,
            finish_reason=data.get("done_reason", "stop"),
            raw_response=data,
            tool_calls=tool_calls_response,
        )

    async def _call_with_routing(
        self,
        prompt: str,
        system: Optional[str] = None,
        messages: Optional[List[Message]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> InferenceResponse:
        """
        Call inference with smart model routing (local + cloud).

        Routing logic:
        - If routing says CLOUD tier → go straight to cloud
        - If routing says PRIMARY/COMPLEX → try local, then fall back to cloud if configured

        Args:
            prompt: The prompt to complete.
            system: Optional system prompt.
            messages: Optional message list for chat.
            temperature: Override default temperature.
            max_tokens: Override default max tokens.

        Returns:
            InferenceResponse with generated content.
        """
        token_count = self._count_request_tokens(prompt, system, messages)
        routing = self.router.route(
            prompt=prompt or (messages[-1].content if messages else ""),
            token_count=token_count,
        )

        self.logger.info(
            f"Routing decision: {routing.tier.value} ({routing.reason})",
            component=LogComponent.INFERENCE,
            data={
                "tier": routing.tier.value,
                "model": routing.model_config.name,
                "reason": routing.reason,
                "token_count": token_count,
                "fallback_tier": routing.fallback_tier.value if routing.fallback_tier else None,
            },
        )

        # Direct cloud routing (enabled_full or smart spillover by token count)
        if routing.tier == ModelTier.CLOUD:
            try:
                response = await self._call_cloud(
                    messages=messages,
                    system=system,
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                self.router.record_success(ModelTier.CLOUD)
                return response
            except Exception as cloud_error:
                self.router.record_failure(ModelTier.CLOUD)
                self.logger.warning(
                    f"Cloud inference failed: {type(cloud_error).__name__}",
                    component=LogComponent.INFERENCE,
                )
                # If cloud was primary, try falling back to local
                if routing.fallback_tier in (ModelTier.PRIMARY, ModelTier.COMPLEX):
                    self.logger.info(
                        f"Falling back from cloud to {routing.fallback_tier.value}",
                        component=LogComponent.INFERENCE,
                    )
                    return await self._call_local_with_retries(
                        prompt=prompt,
                        model_name=self.router._get_config_for_tier(routing.fallback_tier).name,
                        system=system,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        timeout=self.router._get_config_for_tier(routing.fallback_tier).request_timeout,
                        tier=routing.fallback_tier,
                        tools=tools,
                    )
                raise LocalModelFailed(
                    f"Cloud inference failed and no local fallback: {cloud_error}"
                ) from cloud_error

        # Local routing (PRIMARY or COMPLEX)
        try:
            return await self._call_local_with_retries(
                prompt=prompt,
                model_name=routing.model_config.name,
                system=system,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=routing.model_config.request_timeout,
                tier=routing.tier,
                tools=tools,
            )
        except LocalModelFailed as local_error:
            # Local failed — try cloud fallback if available
            if routing.fallback_tier == ModelTier.CLOUD:
                self.logger.info(
                    f"Local model failed, attempting cloud spillover",
                    component=LogComponent.INFERENCE,
                    data={"local_error": type(local_error).__name__},
                )
                try:
                    response = await self._call_cloud(
                        messages=messages,
                        system=system,
                        prompt=prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    response.fallback_used = True
                    self.router.record_success(ModelTier.CLOUD)
                    return response
                except Exception as cloud_error:
                    self.router.record_failure(ModelTier.CLOUD)
                    self.logger.error(
                        f"Cloud spillover also failed: {type(cloud_error).__name__}",
                        component=LogComponent.INFERENCE,
                    )
                    # Raise the original local error — cloud was just a fallback
                    raise local_error from cloud_error
            raise

    async def _call_local_with_retries(
        self,
        prompt: str,
        model_name: str,
        system: Optional[str],
        messages: Optional[List[Message]],
        temperature: Optional[float],
        max_tokens: Optional[int],
        timeout: float,
        tier: ModelTier,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> InferenceResponse:
        """
        Call local Ollama model with retry logic.

        Args:
            prompt: The prompt text.
            model_name: Ollama model name.
            system: Optional system prompt.
            messages: Optional message list.
            temperature: Sampling temperature.
            max_tokens: Max output tokens.
            timeout: Request timeout.
            tier: Which tier this is (for tracking).

        Returns:
            InferenceResponse from local model.

        Raises:
            LocalModelFailed: After all retries exhausted.
        """
        last_error: Optional[Exception] = None
        for attempt in range(self.config.max_retries):
            try:
                response = await self._call_ollama(
                    prompt=prompt,
                    model_name=model_name,
                    system=system,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                    tools=tools,
                )
                response.tier = tier.value
                self.router.record_success(tier)
                return response

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code >= 500:
                    pass  # Server error, retry
                else:
                    raise InferenceError(f"HTTP error: {e.response.status_code}") from e

            except httpx.TimeoutException as e:
                last_error = e
                self.logger.warning(
                    f"Local inference timeout (attempt {attempt + 1}/{self.config.max_retries})",
                    component=LogComponent.INFERENCE,
                    data={"model": model_name, "attempt": attempt + 1},
                )

            except httpx.ConnectError as e:
                last_error = e
                self.logger.error(
                    f"Cannot connect to Ollama: {type(e).__name__}",
                    component=LogComponent.INFERENCE,
                )
                break  # Don't retry connection errors

            except Exception as e:
                last_error = e
                self.logger.error(
                    f"Unexpected error during inference: {type(e).__name__}",
                    component=LogComponent.INFERENCE,
                    data={"error_type": type(e).__name__, "attempt": attempt + 1}
                )

            # Exponential backoff
            if attempt < self.config.max_retries - 1:
                delay = min(
                    self.config.retry_base_delay * (2 ** attempt),
                    self.config.retry_max_delay
                )
                self.logger.warning(
                    f"Inference attempt {attempt + 1} failed, retrying in {delay:.1f}s",
                    component=LogComponent.INFERENCE,
                    data={"attempt": attempt + 1, "delay": delay, "error": str(last_error)}
                )
                await asyncio.sleep(delay)

        # All retries exhausted
        self.router.record_failure(tier)
        raise LocalModelFailed(
            f"Local model failed after {self.config.max_retries} attempts: {last_error}"
        ) from last_error

    async def _call_cloud(
        self,
        messages: Optional[List[Message]] = None,
        system: Optional[str] = None,
        prompt: str = "",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> InferenceResponse:
        """
        Call cloud LLM provider.

        Retrieves active provider and API key from CloudManager,
        then delegates to CloudInferenceClient.

        Returns:
            InferenceResponse with tier="cloud".

        Raises:
            LocalModelFailed: If no cloud provider is configured.
            CloudInferenceError: If cloud call fails.
        """
        from hestia.cloud.client import get_cloud_inference_client, CloudInferenceError
        from hestia.cloud.manager import get_cloud_manager

        cloud_manager = self._cloud_manager
        if cloud_manager is None:
            cloud_manager = await get_cloud_manager()
            self._cloud_manager = cloud_manager

        cloud_client = self._cloud_inference_client
        if cloud_client is None:
            cloud_client = get_cloud_inference_client(
                request_timeout=self.router.cloud_routing.request_timeout,
            )
            self._cloud_inference_client = cloud_client

        # Get active provider
        active_provider = await cloud_manager.get_active_provider()
        if active_provider is None:
            raise LocalModelFailed("No cloud provider configured or enabled")

        # Get API key
        api_key = await cloud_manager.get_api_key(active_provider.provider)
        if not api_key:
            raise LocalModelFailed(
                f"No API key available for {active_provider.provider.value}"
            )

        # Build message list if only prompt provided
        chat_messages = messages or []
        if not chat_messages and prompt:
            chat_messages = [Message(role="user", content=prompt)]

        # Call cloud provider (wrap to sanitize any credential leaks in errors)
        try:
            response = await cloud_client.complete(
                provider=active_provider.provider,
                model_id=active_provider.active_model_id or "default",
                api_key=api_key,
                messages=chat_messages,
                system=system,
                temperature=temperature if temperature is not None else self.config.temperature,
                max_tokens=max_tokens or self.config.max_tokens,
            )
        except Exception as e:
            # Sanitize error message to prevent credential leakage in logs
            safe_msg = str(e)
            if api_key and len(api_key) > 8:
                safe_msg = safe_msg.replace(api_key, "***REDACTED***")
                safe_msg = safe_msg.replace(api_key[:8], "***")
            raise type(e)(safe_msg) from None

        # Track usage
        try:
            usage_record = cloud_client.build_usage_record(
                provider=active_provider.provider,
                model_id=active_provider.active_model_id or "default",
                response=response,
            )
            await cloud_manager.record_usage(usage_record)
        except Exception as e:
            self.logger.warning(
                f"Failed to record cloud usage: {type(e).__name__}",
                component=LogComponent.INFERENCE,
            )

        return response

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        validate: bool = True,
    ) -> InferenceResponse:
        """
        Generate completion for prompt.

        Args:
            prompt: The prompt to complete.
            system: Optional system prompt.
            temperature: Override default temperature.
            max_tokens: Override default max tokens.
            validate: Whether to validate response.

        Returns:
            InferenceResponse with generated content.

        Raises:
            TokenLimitExceeded: If request exceeds context window.
            InferenceError: If inference fails after retries.
            ValidationError: If response validation fails.
            LocalModelFailed: If local model fails.
        """
        request_id = self.logger.new_request_id()

        # Count tokens before sending
        token_count = self._count_request_tokens(prompt, system)
        self._check_token_limit(token_count)

        # Log request
        self.logger.info(
            f"Inference request: {token_count} tokens",
            component=LogComponent.INFERENCE,
            event_type=EventType.INFERENCE_REQUEST,
            data={
                "tokens_in": token_count,
                "temperature": temperature or self.config.temperature,
                "max_tokens": max_tokens or self.config.max_tokens,
            }
        )

        try:
            response = await self._call_with_routing(
                prompt=prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Validate response
            if validate:
                self._validate_response(response)

            # Log success
            self.logger.log_inference(
                model=response.model,
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
                duration_ms=response.duration_ms,
                success=True,
            )

            return response

        except Exception as e:
            self.logger.error(
                f"Inference failed: {type(e).__name__}",
                component=LogComponent.INFERENCE,
                event_type=EventType.ERROR,
                data={"error_type": type(e).__name__}
            )
            raise

    async def chat(
        self,
        messages: List[Message],
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        validate: bool = True,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> InferenceResponse:
        """
        Generate response for chat conversation.

        Args:
            messages: List of conversation messages.
            system: Optional system prompt.
            temperature: Override default temperature.
            max_tokens: Override default max tokens.
            validate: Whether to validate response.

        Returns:
            InferenceResponse with generated content.
        """
        request_id = self.logger.new_request_id()

        # Count tokens
        token_count = self._count_request_tokens("", system, messages)
        self._check_token_limit(token_count)

        # Log request
        self.logger.info(
            f"Chat inference request: {len(messages)} messages, {token_count} tokens",
            component=LogComponent.INFERENCE,
            event_type=EventType.INFERENCE_REQUEST,
            data={
                "message_count": len(messages),
                "tokens_in": token_count,
            }
        )

        try:
            response = await self._call_with_routing(
                prompt="",
                system=system,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
            )

            if validate:
                self._validate_response(response)

            self.logger.log_inference(
                model=response.model,
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
                duration_ms=response.duration_ms,
                success=True,
            )

            return response

        except Exception as e:
            self.logger.error(
                f"Chat inference failed: {type(e).__name__}",
                component=LogComponent.INFERENCE,
                data={"error_type": type(e).__name__, "message_count": len(messages)}
            )
            raise

    async def chat_stream(
        self,
        messages: List[Message],
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[Union[str, InferenceResponse], None]:
        """
        Stream chat tokens as they are generated.

        Uses the same routing logic as chat() to determine local vs cloud,
        but streams tokens incrementally instead of waiting for complete response.

        For local (Ollama): streams token-by-token from /api/chat with stream=True.
        For cloud: falls back to non-streaming (yields complete response as single chunk).

        Yields:
            str: Individual tokens during generation.
            InferenceResponse: Final yield with aggregated metrics and any tool_calls.
        """
        # Count tokens and check limits
        token_count = self._count_request_tokens("", system, messages)
        self._check_token_limit(token_count)

        self.logger.info(
            f"Chat stream request: {len(messages)} messages, {token_count} tokens",
            component=LogComponent.INFERENCE,
            event_type=EventType.INFERENCE_REQUEST,
            data={
                "message_count": len(messages),
                "tokens_in": token_count,
                "streaming": True,
            }
        )

        # Determine routing (same logic as _call_with_routing but we need the decision)
        routing = self.router.route(
            prompt=messages[-1].content if messages else "",
            token_count=token_count,
        )

        self.logger.info(
            f"Stream routing: {routing.tier.value} ({routing.reason})",
            component=LogComponent.INFERENCE,
            data={"tier": routing.tier.value, "model": routing.model_config.name},
        )

        # Cloud routing: fall back to non-streaming (yield complete response as one chunk)
        if routing.tier == ModelTier.CLOUD:
            try:
                response = await self._call_cloud(
                    messages=messages,
                    system=system,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                self.router.record_success(ModelTier.CLOUD)
                # Yield the complete content as a single token
                if response.content:
                    yield response.content
                yield response
                return
            except Exception as cloud_error:
                self.router.record_failure(ModelTier.CLOUD)
                # Try local fallback if available
                if routing.fallback_tier in (ModelTier.PRIMARY, ModelTier.COMPLEX):
                    self.logger.info(
                        f"Cloud stream failed, falling back to local streaming",
                        component=LogComponent.INFERENCE,
                    )
                    model_name = self.router._get_config_for_tier(routing.fallback_tier).name
                    timeout = self.router._get_config_for_tier(routing.fallback_tier).request_timeout
                    async for item in self._stream_ollama_chat(
                        model_name=model_name,
                        messages=messages,
                        system=system,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        timeout=timeout,
                        tier=routing.fallback_tier,
                        tools=tools,
                    ):
                        yield item
                    return
                raise

        # Local routing: stream from Ollama
        try:
            async for item in self._stream_ollama_chat(
                model_name=routing.model_config.name,
                messages=messages,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=routing.model_config.request_timeout,
                tier=routing.tier,
                tools=tools,
            ):
                yield item
        except (LocalModelFailed, httpx.ConnectError) as local_error:
            # Try cloud fallback if available
            if routing.fallback_tier == ModelTier.CLOUD:
                self.logger.info(
                    f"Local stream failed, attempting cloud fallback",
                    component=LogComponent.INFERENCE,
                )
                try:
                    response = await self._call_cloud(
                        messages=messages,
                        system=system,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    response.fallback_used = True
                    self.router.record_success(ModelTier.CLOUD)
                    if response.content:
                        yield response.content
                    yield response
                    return
                except Exception:
                    raise local_error
            raise

    async def _stream_ollama_chat(
        self,
        model_name: str,
        messages: List[Message],
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        tier: Optional[ModelTier] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[Union[str, InferenceResponse], None]:
        """
        Stream tokens from Ollama /api/chat endpoint.

        Handles the Ollama streaming protocol: line-delimited JSON with
        {"message": {"content": "token"}, "done": false} for each chunk
        and {"done": true, ...metrics...} for the final event.

        Yields:
            str: Individual tokens.
            InferenceResponse: Final yield with metrics and tool_calls.
        """
        import json as json_mod

        client = await self._get_client(timeout)
        start_time = time.perf_counter()

        request_data: Dict[str, Any] = {
            "model": model_name,
            "stream": True,
            "messages": [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ],
            "options": {
                "temperature": temperature if temperature is not None else self.config.temperature,
                "num_predict": max_tokens or self.config.max_tokens,
                "top_p": self.config.top_p,
            }
        }

        if system:
            request_data["messages"].insert(0, {"role": "system", "content": system})

        if tools:
            request_data["tools"] = tools

        content_buffer = ""
        tool_calls_response = None
        tokens_in = 0
        tokens_out = 0
        finish_reason = "stop"

        try:
            async with client.stream(
                "POST",
                f"{self.config.ollama_host}/api/chat",
                json=request_data,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    try:
                        data = json_mod.loads(line)
                    except json_mod.JSONDecodeError:
                        continue

                    # Extract streaming token from message content
                    message_data = data.get("message", {})
                    token = message_data.get("content", "")

                    if token:
                        content_buffer += token
                        yield token

                    # Check for tool calls in the message
                    raw_tool_calls = message_data.get("tool_calls")
                    if raw_tool_calls:
                        tool_calls_response = raw_tool_calls

                    # Final event with metrics
                    if data.get("done"):
                        tokens_in = data.get("prompt_eval_count", 0)
                        tokens_out = data.get("eval_count", 0)
                        finish_reason = data.get("done_reason", "stop")
                        break

        except httpx.ConnectError:
            raise
        except httpx.TimeoutException as e:
            self.logger.warning(
                f"Ollama stream timeout after {(time.perf_counter() - start_time)*1000:.0f}ms",
                component=LogComponent.INFERENCE,
            )
            raise LocalModelFailed(f"Stream timeout: {type(e).__name__}") from e
        except httpx.HTTPStatusError as e:
            raise InferenceError(f"Ollama stream HTTP error: {e.response.status_code}") from e

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Fallback token estimation if Ollama didn't provide counts
        if tokens_in == 0:
            tokens_in = self._count_request_tokens("", system, messages)
        if tokens_out == 0:
            tokens_out = self.token_counter.count(content_buffer)

        if tier:
            self.router.record_success(tier)

        # Log completion
        self.logger.log_inference(
            model=model_name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_ms=duration_ms,
            success=True,
        )

        # Final yield: InferenceResponse with aggregated metrics
        yield InferenceResponse(
            content=content_buffer,
            model=model_name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_ms=duration_ms,
            finish_reason=finish_reason,
            raw_response={},
            tier=tier.value if tier else None,
            tool_calls=tool_calls_response,
        )

    def _validate_response(self, response: InferenceResponse) -> None:
        """
        Validate inference response.

        Checks:
        - Content is not empty
        - Content is not truncated unexpectedly
        - No error indicators in response
        """
        if not response.content or not response.content.strip():
            # Native tool calls may have empty content — that's valid
            if response.tool_calls:
                self.logger.debug(
                    "Empty content with native tool_calls — validation bypassed",
                    component=LogComponent.INFERENCE,
                    data={"model": response.model, "tool_count": len(response.tool_calls)},
                )
                return
            self.logger.warning(
                "Empty response from model",
                component=LogComponent.INFERENCE,
                data={"model": response.model, "tokens_out": response.tokens_out}
            )
            raise ValidationError("Empty response from model")

        # Check for common error patterns
        error_patterns = [
            "I cannot",
            "I'm unable to",
            "Error:",
            "Exception:",
        ]

        content_lower = response.content.lower()
        for pattern in error_patterns:
            if content_lower.startswith(pattern.lower()):
                self.logger.warning(
                    f"Potential error response detected: {pattern}",
                    component=LogComponent.INFERENCE,
                    data={"pattern": pattern, "content_preview": response.content[:100]}
                )
                # Don't raise, just log - model might legitimately say these things

    async def health_check(self) -> Dict[str, Any]:
        """
        Check if inference systems are available.

        Returns:
            Dict with health status for local models.
        """
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "local": {},
            "router": self.router.get_status(),
            "architecture": "local-only",
        }

        # Check local (Ollama)
        try:
            client = await self._get_client()
            response = await client.get(f"{self.config.ollama_host}/api/tags")
            response.raise_for_status()

            models = response.json().get("models", [])
            model_names = [m.get("name", "") for m in models]

            # Check primary and complex models
            primary_available = any(
                self.router.primary_model.name in name or name in self.router.primary_model.name
                for name in model_names
            )
            complex_available = any(
                self.router.complex_model.name in name or name in self.router.complex_model.name
                for name in model_names
            )

            result["local"] = {
                "status": "healthy" if primary_available else "degraded",
                "ollama_available": True,
                "primary_model_available": primary_available,
                "complex_model_available": complex_available,
                "available_models": model_names,
            }

        except Exception as e:
            result["local"] = {
                "status": "unhealthy",
                "ollama_available": False,
                "error": type(e).__name__,
            }

        # Cloud health (if configured)
        cloud_state = self.router.cloud_routing.state
        if cloud_state != "disabled":
            result["cloud"] = {
                "state": cloud_state,
                "status": "configured",
            }

        # Overall status
        local_ok = result["local"].get("status") in ("healthy", "degraded")
        if cloud_state == "enabled_full":
            # In full cloud mode, local being down is less critical
            result["status"] = "healthy" if local_ok else "degraded"
        else:
            result["status"] = "healthy" if local_ok else "unhealthy"

        result["architecture"] = "local-only" if cloud_state == "disabled" else f"hybrid ({cloud_state})"

        return result

    async def stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream completion tokens as they are generated.

        Uses local models only (streaming not yet supported for cloud).

        Args:
            prompt: The prompt to complete.
            system: Optional system prompt.
            temperature: Override default temperature.
            max_tokens: Override default max tokens.

        Yields:
            Generated tokens as strings.
        """
        # Get routing decision for model selection (local models only)
        token_count = self._count_request_tokens(prompt, system)
        routing = self.router.route(prompt=prompt, token_count=token_count)

        client = await self._get_client(routing.model_config.request_timeout)

        request_data = {
            "model": routing.model_config.name,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature or self.config.temperature,
                "num_predict": max_tokens or self.config.max_tokens,
            }
        }

        if system:
            request_data["system"] = system

        async with client.stream(
            "POST",
            f"{self.config.ollama_host}/api/generate",
            json=request_data,
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line:
                    import json
                    data = json.loads(line)
                    if "response" in data:
                        yield data["response"]
                    if data.get("done"):
                        break


# Module-level convenience functions

_default_client: Optional[InferenceClient] = None


def get_inference_client() -> InferenceClient:
    """Get or create the default inference client."""
    global _default_client
    if _default_client is None:
        _default_client = InferenceClient()
    return _default_client


async def complete(prompt: str, **kwargs) -> InferenceResponse:
    """Convenience function for quick completions."""
    client = get_inference_client()
    return await client.complete(prompt, **kwargs)


async def chat(messages: List[Message], **kwargs) -> InferenceResponse:
    """Convenience function for quick chat completions."""
    client = get_inference_client()
    return await client.chat(messages, **kwargs)
