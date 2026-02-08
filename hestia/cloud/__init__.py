"""
Cloud LLM provider support for Hestia.

Manages cloud provider configuration, API key storage,
model detection, and usage/cost tracking.

Providers: Anthropic, OpenAI, Google.
Three states: disabled, enabled_full, enabled_smart.
"""

from .models import (
    CloudProvider,
    CloudProviderState,
    CloudModel,
    ProviderConfig,
    CloudUsageRecord,
    PROVIDER_DEFAULTS,
)
from .database import CloudDatabase, get_cloud_database
from .manager import CloudManager, get_cloud_manager
from .client import (
    CloudInferenceClient,
    CloudInferenceError,
    CloudAuthError,
    CloudRateLimitError,
    CloudModelError,
    get_cloud_inference_client,
)

__all__ = [
    "CloudProvider",
    "CloudProviderState",
    "CloudModel",
    "ProviderConfig",
    "CloudUsageRecord",
    "PROVIDER_DEFAULTS",
    "CloudDatabase",
    "get_cloud_database",
    "CloudManager",
    "get_cloud_manager",
    "CloudInferenceClient",
    "CloudInferenceError",
    "CloudAuthError",
    "CloudRateLimitError",
    "CloudModelError",
    "get_cloud_inference_client",
]
