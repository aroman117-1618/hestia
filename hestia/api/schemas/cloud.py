"""
Cloud LLM provider schemas (WS1).
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CloudProviderEnum(str, Enum):
    """Supported cloud LLM providers."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"


class CloudProviderStateEnum(str, Enum):
    """Cloud provider operational state."""
    DISABLED = "disabled"
    ENABLED_FULL = "enabled_full"
    ENABLED_SMART = "enabled_smart"


class CloudProviderAddRequest(BaseModel):
    """Request to add a cloud provider."""
    provider: CloudProviderEnum = Field(
        ...,
        description="Cloud provider type (anthropic, openai, google)"
    )
    api_key: str = Field(
        ...,
        min_length=1,
        description="API key for the provider (stored in Keychain)"
    )
    state: CloudProviderStateEnum = Field(
        default=CloudProviderStateEnum.ENABLED_SMART,
        description="Initial provider state"
    )
    model_id: Optional[str] = Field(
        None,
        description="Preferred model ID (uses provider default if omitted)"
    )


class CloudProviderStateUpdateRequest(BaseModel):
    """Request to update a provider's routing state."""
    state: CloudProviderStateEnum = Field(
        ...,
        description="New provider state"
    )


class CloudProviderModelUpdateRequest(BaseModel):
    """Request to select a provider's active model."""
    model_id: str = Field(
        ...,
        min_length=1,
        description="Model ID to use for this provider"
    )


class CloudProviderResponse(BaseModel):
    """Cloud provider configuration (never exposes raw API key)."""
    id: str = Field(description="Provider config identifier")
    provider: CloudProviderEnum = Field(description="Provider type")
    state: CloudProviderStateEnum = Field(description="Operational state")
    active_model_id: Optional[str] = Field(None, description="Currently selected model")
    available_models: List[str] = Field(default_factory=list, description="Available model IDs")
    has_api_key: bool = Field(description="Whether an API key is configured")
    health_status: str = Field(default="unknown", description="Last health check result")
    last_health_check: Optional[datetime] = Field(None, description="Last health check timestamp")
    created_at: datetime = Field(description="When provider was added")
    updated_at: datetime = Field(description="Last update timestamp")


class CloudProviderListResponse(BaseModel):
    """Response listing cloud providers."""
    providers: List[CloudProviderResponse] = Field(description="Configured providers")
    count: int = Field(description="Number of providers")
    cloud_state: str = Field(description="Effective cloud routing state")


class CloudProviderDeleteResponse(BaseModel):
    """Response after removing a cloud provider."""
    provider: CloudProviderEnum = Field(description="Removed provider")
    deleted: bool = Field(description="Whether deletion succeeded")
    message: str = Field(description="Status message")


class CloudUsageSummaryResponse(BaseModel):
    """Cloud usage and cost summary."""
    period_days: int = Field(description="Summary period in days")
    total_requests: int = Field(default=0, description="Total cloud API requests")
    total_tokens_in: int = Field(default=0, description="Total input tokens")
    total_tokens_out: int = Field(default=0, description="Total output tokens")
    total_cost_usd: float = Field(default=0.0, description="Total cost in USD")
    by_provider: Dict[str, Any] = Field(default_factory=dict, description="Breakdown by provider")
    by_model: Dict[str, Any] = Field(default_factory=dict, description="Breakdown by model")


class CloudHealthCheckResponse(BaseModel):
    """Response from a provider health check."""
    provider: CloudProviderEnum = Field(description="Provider checked")
    healthy: bool = Field(description="Whether the provider is reachable")
    health_status: str = Field(description="Health status string")
    message: str = Field(description="Status message")
