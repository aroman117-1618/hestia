"""Inference module - LLM integration and model management.

Local-only architecture: All inference runs on local models via Ollama.
Cloud LLM fallback has been removed per ADR-001/ADR-010.
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
    "RoutingDecision",
    "get_router",
]
