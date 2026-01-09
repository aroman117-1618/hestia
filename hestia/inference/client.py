"""
Inference client for Hestia.

Provides async interface to local models via Ollama.

Features:
- Local-only inference: routes to fast local model (Qwen 2.5 7B) or complex local (Mixtral)
- Token counting and context window management (32K budget)
- Retry logic with exponential backoff
- Response validation
- Comprehensive logging

Note: Cloud LLM fallback has been removed per ADR-001/ADR-010 (local-only architecture).
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
    model_name: str = "qwen2.5:7b"  # Default to fast model

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
    Async client for LLM inference with local model routing.

    Tiers (local-only per ADR-001/ADR-010):
    1. Primary: Fast local model (Qwen 2.5 7B) - default
    2. Complex: Large local model (Mixtral 8x7B) - when enabled (64GB RAM) and pattern matches

    Features:
    - Smart model routing based on request complexity
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
    ):
        """
        Initialize inference client.

        Args:
            config: InferenceConfig instance. If None, loads from config_path.
            config_path: Path to YAML config. Defaults to hestia/config/inference.yaml
            router: ModelRouter instance. If None, creates default.
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

        # Extract response content
        if messages:
            content = data.get("message", {}).get("content", "")
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
        )

    async def _call_with_routing(
        self,
        prompt: str,
        system: Optional[str] = None,
        messages: Optional[List[Message]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> InferenceResponse:
        """
        Call inference with smart local model routing.

        Args:
            prompt: The prompt to complete.
            system: Optional system prompt.
            messages: Optional message list for chat.
            temperature: Override default temperature.
            max_tokens: Override default max tokens.

        Returns:
            InferenceResponse with generated content.
        """
        # Get routing decision (local models only per ADR-001/ADR-010)
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
            },
        )

        # Try local model
        last_error: Optional[Exception] = None
        for attempt in range(self.config.max_retries):
            try:
                response = await self._call_ollama(
                    prompt=prompt,
                    model_name=routing.model_config.name,
                    system=system,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=routing.model_config.request_timeout,
                )
                response.tier = routing.tier.value
                self.router.record_success(routing.tier)
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
                    data={"model": routing.model_config.name, "attempt": attempt + 1},
                )

            except httpx.ConnectError as e:
                last_error = e
                self.logger.error(
                    f"Cannot connect to Ollama: {e}",
                    component=LogComponent.INFERENCE,
                )
                break  # Don't retry connection errors

            except Exception as e:
                last_error = e
                self.logger.error(
                    f"Unexpected error during inference: {e}",
                    component=LogComponent.INFERENCE,
                    data={"error": str(e), "attempt": attempt + 1}
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

        # Local model failed - no cloud fallback (local-only architecture)
        self.router.record_failure(routing.tier)
        raise LocalModelFailed(
            f"Local model failed after {self.config.max_retries} attempts: {last_error}"
        ) from last_error

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
                f"Inference failed: {e}",
                component=LogComponent.INFERENCE,
                event_type=EventType.ERROR,
                data={"error": str(e), "error_type": type(e).__name__}
            )
            raise

    async def chat(
        self,
        messages: List[Message],
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        validate: bool = True,
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
                f"Chat inference failed: {e}",
                component=LogComponent.INFERENCE,
                data={"error": str(e), "message_count": len(messages)}
            )
            raise

    def _validate_response(self, response: InferenceResponse) -> None:
        """
        Validate inference response.

        Checks:
        - Content is not empty
        - Content is not truncated unexpectedly
        - No error indicators in response
        """
        if not response.content or not response.content.strip():
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
                "error": str(e),
            }

        # Overall status based on local only (local-only architecture per ADR-001/ADR-010)
        local_ok = result["local"].get("status") in ("healthy", "degraded")
        result["status"] = "healthy" if local_ok else "unhealthy"

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

        Uses local models only (local-only architecture per ADR-001/ADR-010).

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
