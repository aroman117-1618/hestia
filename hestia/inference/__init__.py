"""Inference module - LLM integration and model management.

Supports local models via Ollama and cloud providers (Anthropic, OpenAI, Google).
Cloud routing is configurable: disabled, enabled_full, or enabled_smart.
"""

from hestia.inference.client import (
    InferenceClient,
    InferenceConfig,
    InferenceResponse,
    InferenceError,
    TokenLimitExceeded,
    ValidationError,
    ModelUnavailable,
    LocalModelFailed,
    Message,
    TokenCounter,
    ContextSize,
    get_inference_client,
    complete,
    chat,
)

from hestia.inference.router import (
    ModelRouter,
    ModelTier,
    ModelConfig,
    RoutingConfig,
    CloudRoutingConfig,
    RoutingDecision,
    get_router,
)

__all__ = [
    # Client
    "InferenceClient",
    "InferenceConfig",
    "InferenceResponse",
    # Errors
    "InferenceError",
    "TokenLimitExceeded",
    "ValidationError",
    "ModelUnavailable",
    "LocalModelFailed",
    # Types
    "Message",
    "TokenCounter",
    "ContextSize",
    # Convenience functions
    "get_inference_client",
    "complete",
    "chat",
    # Router
    "ModelRouter",
    "ModelTier",
    "ModelConfig",
    "RoutingConfig",
    "CloudRoutingConfig",
    "RoutingDecision",
    "get_router",
]
