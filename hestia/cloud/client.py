"""
Cloud inference client for Hestia.

Makes actual LLM completion calls to cloud providers (Anthropic, OpenAI, Google).
Returns normalized InferenceResponse objects with cost tracking.

Each provider has its own request/response format:
- Anthropic: POST /v1/messages (x-api-key header)
- OpenAI: POST /v1/chat/completions (Bearer token)
- Google Gemini: POST /v1beta/models/{model}:generateContent (key param)
"""

import time
from typing import Any, Dict, List, Optional

import httpx

from hestia.logging import get_logger, LogComponent
from hestia.inference.client import InferenceResponse, Message

from .models import (
    CloudProvider,
    CloudUsageRecord,
    PROVIDER_DEFAULTS,
    calculate_cost,
)


class CloudInferenceError(Exception):
    """Base exception for cloud inference errors."""
    pass


class CloudAuthError(CloudInferenceError):
    """Raised when API key is invalid or missing."""
    pass


class CloudRateLimitError(CloudInferenceError):
    """Raised when provider rate limit is hit."""

    def __init__(self, message: str, retry_after: Optional[float] = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class CloudModelError(CloudInferenceError):
    """Raised when the requested model is unavailable."""
    pass


class CloudInferenceClient:
    """
    Async client for making LLM completion calls to cloud providers.

    Normalizes responses from Anthropic, OpenAI, and Google into
    a common InferenceResponse format. Tracks usage for cost reporting.
    """

    def __init__(self, request_timeout: float = 60.0) -> None:
        self.request_timeout = request_timeout
        self.logger = get_logger()
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=self.request_timeout,
                    write=self.request_timeout,
                    pool=self.request_timeout,
                )
            )
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def complete(
        self,
        provider: CloudProvider,
        model_id: str,
        api_key: str,
        messages: List[Message],
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        request_id: str = "",
        mode: str = "tia",
    ) -> InferenceResponse:
        """
        Make a completion call to a cloud provider.

        Args:
            provider: Which cloud provider to call.
            model_id: The model ID to use.
            api_key: The API key for authentication.
            messages: Conversation messages.
            system: Optional system prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.
            request_id: Request ID for tracking.
            mode: Current persona mode for usage tracking.

        Returns:
            Normalized InferenceResponse.

        Raises:
            CloudAuthError: If API key is invalid.
            CloudRateLimitError: If rate limited.
            CloudModelError: If model is unavailable.
            CloudInferenceError: For other cloud errors.
        """
        if not api_key:
            raise CloudAuthError(f"No API key provided for {provider.value}")

        start_time = time.perf_counter()

        try:
            if provider == CloudProvider.ANTHROPIC:
                response = await self._call_anthropic(
                    model_id, api_key, messages, system, temperature, max_tokens,
                )
            elif provider == CloudProvider.OPENAI:
                response = await self._call_openai(
                    model_id, api_key, messages, system, temperature, max_tokens,
                )
            elif provider == CloudProvider.GOOGLE:
                response = await self._call_google(
                    model_id, api_key, messages, system, temperature, max_tokens,
                )
            else:
                raise CloudInferenceError(f"Unsupported provider: {provider.value}")

            duration_ms = (time.perf_counter() - start_time) * 1000
            response.duration_ms = duration_ms
            response.tier = "cloud"

            self.logger.info(
                f"Cloud inference complete: {provider.value}/{model_id}",
                component=LogComponent.INFERENCE,
                data={
                    "provider": provider.value,
                    "model": model_id,
                    "tokens_in": response.tokens_in,
                    "tokens_out": response.tokens_out,
                    "duration_ms": round(duration_ms, 1),
                    "request_id": request_id,
                },
            )

            return response

        except (CloudAuthError, CloudRateLimitError, CloudModelError):
            raise
        except httpx.TimeoutException as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.logger.error(
                f"Cloud inference timeout: {provider.value}/{model_id}",
                component=LogComponent.INFERENCE,
                data={"duration_ms": round(duration_ms, 1)},
            )
            raise CloudInferenceError(
                f"Cloud inference timed out after {duration_ms:.0f}ms"
            ) from e
        except httpx.ConnectError as e:
            raise CloudInferenceError(
                f"Cannot connect to {provider.value}: {e}"
            ) from e
        except Exception as e:
            if isinstance(e, CloudInferenceError):
                raise
            raise CloudInferenceError(
                f"Cloud inference failed for {provider.value}: {e}"
            ) from e

    def build_usage_record(
        self,
        provider: CloudProvider,
        model_id: str,
        response: InferenceResponse,
        request_id: str = "",
        mode: str = "tia",
    ) -> CloudUsageRecord:
        """Build a usage record from an inference response."""
        cost = calculate_cost(
            provider=provider,
            model_id=model_id,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
        )
        return CloudUsageRecord.create(
            provider=provider,
            model_id=model_id,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            cost_usd=cost,
            duration_ms=response.duration_ms,
            request_id=request_id,
            mode=mode,
        )

    # ── Anthropic ─────────────────────────────────────────────────────

    async def _call_anthropic(
        self,
        model_id: str,
        api_key: str,
        messages: List[Message],
        system: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> InferenceResponse:
        """Call Anthropic Messages API."""
        client = await self._get_client()

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        # Anthropic format: system is top-level, messages are user/assistant
        request_body: Dict[str, Any] = {
            "model": model_id,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": msg.role, "content": msg.content}
                for msg in messages
                if msg.role in ("user", "assistant")
            ],
        }

        if system:
            request_body["system"] = system

        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=request_body,
        )

        self._check_http_error(response, CloudProvider.ANTHROPIC)

        data = response.json()

        # Extract content from response
        content_blocks = data.get("content", [])
        content = ""
        for block in content_blocks:
            if block.get("type") == "text":
                content += block.get("text", "")

        usage = data.get("usage", {})

        return InferenceResponse(
            content=content,
            model=data.get("model", model_id),
            tokens_in=usage.get("input_tokens", 0),
            tokens_out=usage.get("output_tokens", 0),
            duration_ms=0.0,  # Set by caller
            finish_reason=data.get("stop_reason", "end_turn"),
            raw_response=data,
        )

    # ── OpenAI ────────────────────────────────────────────────────────

    async def _call_openai(
        self,
        model_id: str,
        api_key: str,
        messages: List[Message],
        system: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> InferenceResponse:
        """Call OpenAI Chat Completions API."""
        client = await self._get_client()

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # OpenAI format: system message in messages array
        oai_messages: List[Dict[str, str]] = []
        if system:
            oai_messages.append({"role": "system", "content": system})
        for msg in messages:
            oai_messages.append({"role": msg.role, "content": msg.content})

        request_body: Dict[str, Any] = {
            "model": model_id,
            "messages": oai_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=request_body,
        )

        self._check_http_error(response, CloudProvider.OPENAI)

        data = response.json()

        choices = data.get("choices", [])
        content = ""
        finish_reason = "stop"
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            finish_reason = choices[0].get("finish_reason", "stop")

        usage = data.get("usage", {})

        return InferenceResponse(
            content=content,
            model=data.get("model", model_id),
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            duration_ms=0.0,
            finish_reason=finish_reason,
            raw_response=data,
        )

    # ── Google Gemini ─────────────────────────────────────────────────

    async def _call_google(
        self,
        model_id: str,
        api_key: str,
        messages: List[Message],
        system: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> InferenceResponse:
        """Call Google Gemini generateContent API."""
        client = await self._get_client()

        # Gemini format: contents array with role "user"/"model"
        contents: List[Dict[str, Any]] = []
        for msg in messages:
            gemini_role = "model" if msg.role == "assistant" else "user"
            contents.append({
                "role": gemini_role,
                "parts": [{"text": msg.content}],
            })

        request_body: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        if system:
            request_body["systemInstruction"] = {
                "parts": [{"text": system}],
            }

        response = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent",
            params={"key": api_key},
            json=request_body,
        )

        self._check_http_error(response, CloudProvider.GOOGLE)

        data = response.json()

        # Extract content
        candidates = data.get("candidates", [])
        content = ""
        finish_reason = "stop"
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            content = "".join(p.get("text", "") for p in parts)
            finish_reason = candidates[0].get("finishReason", "STOP").lower()

        usage = data.get("usageMetadata", {})

        return InferenceResponse(
            content=content,
            model=model_id,
            tokens_in=usage.get("promptTokenCount", 0),
            tokens_out=usage.get("candidatesTokenCount", 0),
            duration_ms=0.0,
            finish_reason=finish_reason,
            raw_response=data,
        )

    # ── Error Handling ────────────────────────────────────────────────

    def _check_http_error(
        self,
        response: httpx.Response,
        provider: CloudProvider,
    ) -> None:
        """Check HTTP response for errors and raise appropriate exceptions."""
        if response.status_code == 200:
            return

        status = response.status_code

        try:
            error_data = response.json()
        except Exception as parse_error:
            self.logger.debug(
                f"Failed to parse error response body: {parse_error}",
                component=LogComponent.INFERENCE,
            )
            error_data = {"raw": response.text[:500]}

        if status == 401 or status == 403:
            raise CloudAuthError(
                f"{provider.value} authentication failed (HTTP {status}): "
                f"check your API key"
            )

        if status == 429:
            retry_after = response.headers.get("retry-after")
            retry_seconds = float(retry_after) if retry_after else None
            raise CloudRateLimitError(
                f"{provider.value} rate limit exceeded",
                retry_after=retry_seconds,
            )

        if status == 404:
            raise CloudModelError(
                f"{provider.value} model not found (HTTP 404): "
                f"check that the model ID is correct"
            )

        if status >= 500:
            raise CloudInferenceError(
                f"{provider.value} server error (HTTP {status}): "
                f"{error_data}"
            )

        raise CloudInferenceError(
            f"{provider.value} request failed (HTTP {status}): "
            f"{error_data}"
        )


# Module-level singleton
_cloud_inference_client: Optional[CloudInferenceClient] = None


def get_cloud_inference_client(
    request_timeout: float = 60.0,
) -> CloudInferenceClient:
    """Get or create the cloud inference client singleton."""
    global _cloud_inference_client
    if _cloud_inference_client is None:
        _cloud_inference_client = CloudInferenceClient(
            request_timeout=request_timeout,
        )
    return _cloud_inference_client
