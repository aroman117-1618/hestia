"""
Cloud LLM provider models for Hestia.

Defines cloud provider configuration, model metadata,
and usage tracking structures.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class CloudProvider(Enum):
    """Supported cloud LLM providers."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"


class CloudProviderState(Enum):
    """Provider operational state."""
    DISABLED = "disabled"
    ENABLED_FULL = "enabled_full"
    ENABLED_SMART = "enabled_smart"


@dataclass
class CloudModel:
    """A cloud model available from a provider."""
    model_id: str
    provider: CloudProvider
    display_name: str
    context_window: int
    max_output_tokens: int
    cost_per_1k_input: float
    cost_per_1k_output: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model_id": self.model_id,
            "provider": self.provider.value,
            "display_name": self.display_name,
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "cost_per_1k_input": self.cost_per_1k_input,
            "cost_per_1k_output": self.cost_per_1k_output,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CloudModel":
        """Create from dictionary."""
        return cls(
            model_id=data["model_id"],
            provider=CloudProvider(data["provider"]),
            display_name=data["display_name"],
            context_window=data["context_window"],
            max_output_tokens=data["max_output_tokens"],
            cost_per_1k_input=data["cost_per_1k_input"],
            cost_per_1k_output=data["cost_per_1k_output"],
        )


@dataclass
class ProviderConfig:
    """Configuration for a single cloud provider."""
    id: str
    provider: CloudProvider
    state: CloudProviderState
    credential_key: str
    active_model_id: Optional[str] = None
    available_models: List[str] = field(default_factory=list)
    base_url: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_health_check: Optional[datetime] = None
    health_status: str = "unknown"

    def to_sqlite_row(self) -> Dict[str, Any]:
        """Convert to SQLite row format."""
        return {
            "id": self.id,
            "provider": self.provider.value,
            "state": self.state.value,
            "credential_key": self.credential_key,
            "active_model_id": self.active_model_id,
            "available_models": json.dumps(self.available_models),
            "base_url": self.base_url,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
            "health_status": self.health_status,
        }

    @classmethod
    def from_sqlite_row(cls, row: Dict[str, Any]) -> "ProviderConfig":
        """Create from SQLite row."""
        return cls(
            id=row["id"],
            provider=CloudProvider(row["provider"]),
            state=CloudProviderState(row["state"]),
            credential_key=row["credential_key"],
            active_model_id=row["active_model_id"],
            available_models=json.loads(row["available_models"]) if row["available_models"] else [],
            base_url=row["base_url"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            last_health_check=datetime.fromisoformat(row["last_health_check"]) if row["last_health_check"] else None,
            health_status=row["health_status"] or "unknown",
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API-safe dictionary (never includes raw API key)."""
        return {
            "id": self.id,
            "provider": self.provider.value,
            "state": self.state.value,
            "active_model_id": self.active_model_id,
            "available_models": self.available_models,
            "base_url": self.base_url,
            "has_api_key": bool(self.credential_key),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "health_status": self.health_status,
        }

    @classmethod
    def create(
        cls,
        provider: CloudProvider,
        credential_key: str,
        state: CloudProviderState = CloudProviderState.ENABLED_SMART,
        active_model_id: Optional[str] = None,
    ) -> "ProviderConfig":
        """Factory method to create a new provider config."""
        defaults = PROVIDER_DEFAULTS.get(provider, {})
        return cls(
            id=f"prov-{uuid4().hex[:12]}",
            provider=provider,
            state=state,
            credential_key=credential_key,
            active_model_id=active_model_id or defaults.get("default_model"),
            base_url=defaults.get("base_url"),
        )


@dataclass
class CloudUsageRecord:
    """A single cloud API usage record for cost tracking."""
    id: str
    provider: CloudProvider
    model_id: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    duration_ms: float
    request_id: str
    mode: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_sqlite_row(self) -> Dict[str, Any]:
        """Convert to SQLite row format."""
        return {
            "id": self.id,
            "provider": self.provider.value,
            "model_id": self.model_id,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost_usd": self.cost_usd,
            "duration_ms": self.duration_ms,
            "request_id": self.request_id,
            "mode": self.mode,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_sqlite_row(cls, row: Dict[str, Any]) -> "CloudUsageRecord":
        """Create from SQLite row."""
        return cls(
            id=row["id"],
            provider=CloudProvider(row["provider"]),
            model_id=row["model_id"],
            tokens_in=row["tokens_in"],
            tokens_out=row["tokens_out"],
            cost_usd=row["cost_usd"],
            duration_ms=row["duration_ms"],
            request_id=row["request_id"],
            mode=row["mode"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )

    @classmethod
    def create(
        cls,
        provider: CloudProvider,
        model_id: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
        duration_ms: float,
        request_id: str,
        mode: str = "tia",
    ) -> "CloudUsageRecord":
        """Factory method to create a new usage record."""
        return cls(
            id=f"usage-{uuid4().hex[:12]}",
            provider=provider,
            model_id=model_id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            duration_ms=duration_ms,
            request_id=request_id,
            mode=mode,
        )


def calculate_cost(
    provider: CloudProvider,
    model_id: str,
    tokens_in: int,
    tokens_out: int,
) -> float:
    """Calculate cost for a cloud API call."""
    defaults = PROVIDER_DEFAULTS.get(provider, {})
    models = defaults.get("models", [])

    for model in models:
        if model.model_id == model_id:
            input_cost = (tokens_in / 1000.0) * model.cost_per_1k_input
            output_cost = (tokens_out / 1000.0) * model.cost_per_1k_output
            return round(input_cost + output_cost, 6)

    # Unknown model — estimate with default rates
    return round((tokens_in + tokens_out) / 1000.0 * 0.01, 6)


# Curated model lists with pricing (updated periodically)
PROVIDER_DEFAULTS: Dict[CloudProvider, Dict[str, Any]] = {
    CloudProvider.ANTHROPIC: {
        "base_url": "https://api.anthropic.com",
        "default_model": "claude-sonnet-4-20250514",
        "models": [
            CloudModel(
                "claude-sonnet-4-20250514",
                CloudProvider.ANTHROPIC,
                "Claude Sonnet 4",
                200000, 8192,
                0.003, 0.015,
            ),
            CloudModel(
                "claude-haiku-3-5-20241022",
                CloudProvider.ANTHROPIC,
                "Claude 3.5 Haiku",
                200000, 8192,
                0.001, 0.005,
            ),
        ],
    },
    CloudProvider.OPENAI: {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "models": [
            CloudModel(
                "gpt-4o",
                CloudProvider.OPENAI,
                "GPT-4o",
                128000, 4096,
                0.005, 0.015,
            ),
            CloudModel(
                "gpt-4o-mini",
                CloudProvider.OPENAI,
                "GPT-4o Mini",
                128000, 16384,
                0.00015, 0.0006,
            ),
        ],
    },
    CloudProvider.GOOGLE: {
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "default_model": "gemini-2.0-flash",
        "models": [
            CloudModel(
                "gemini-2.0-flash",
                CloudProvider.GOOGLE,
                "Gemini 2.0 Flash",
                1048576, 8192,
                0.00035, 0.0015,
            ),
            CloudModel(
                "gemini-2.0-pro",
                CloudProvider.GOOGLE,
                "Gemini 2.0 Pro",
                1048576, 8192,
                0.00125, 0.005,
            ),
        ],
    },
}
