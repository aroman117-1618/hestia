"""
Model router for Hestia local inference.

Routes requests to the appropriate local model tier based on:
- Request complexity (token count, patterns)
- Model availability (health checks)

Tiers:
1. Primary: Fast local model (Qwen 2.5 7B) - default for routine queries
2. Complex: Large local model (Mixtral 8x7B) - for complex reasoning (when 64GB RAM available)

Note: Cloud fallback has been removed per ADR-001/ADR-010 (local-only architecture).
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from hestia.logging import get_logger, LogComponent, EventType


class ModelTier(Enum):
    """Model tiers for routing (local-only)."""
    PRIMARY = "primary"      # Fast local (Qwen 2.5 7B)
    COMPLEX = "complex"      # Large local (Mixtral 8x7B, when 64GB available)


@dataclass
class ModelConfig:
    """Configuration for a single model."""
    name: str
    context_limit: int = 32768
    max_tokens: int = 2048
    temperature: float = 0.0
    request_timeout: float = 60.0
    enabled: bool = True
    api_key_credential: Optional[str] = None  # For cloud models


@dataclass
class RoutingConfig:
    """Configuration for model routing."""
    complex_patterns: List[str] = field(default_factory=list)
    complex_token_threshold: int = 500


@dataclass
class RoutingDecision:
    """Result of a routing decision."""
    tier: ModelTier
    model_config: ModelConfig
    reason: str
    fallback_tier: Optional[ModelTier] = None


class ModelRouter:
    """
    Routes inference requests to appropriate local model tier.

    Maintains failure counts for monitoring. All inference is local-only.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize router with configuration.

        Args:
            config_path: Path to inference.yaml config file.
        """
        self.logger = get_logger()

        # Load configuration
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "inference.yaml"

        self._load_config(config_path)

        # Track failure counts for escalation
        self._failure_counts: Dict[ModelTier, int] = {
            ModelTier.PRIMARY: 0,
            ModelTier.COMPLEX: 0,
        }

        # Track last successful inference per tier
        self._last_success: Dict[ModelTier, Optional[datetime]] = {
            ModelTier.PRIMARY: None,
            ModelTier.COMPLEX: None,
        }

    def _load_config(self, config_path: Path) -> None:
        """Load configuration from YAML file."""
        data: Dict[str, Any] = {}

        if config_path.exists():
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}

        # Parse model configs
        primary_data = data.get("primary_model", {})
        self.primary_model = ModelConfig(
            name=primary_data.get("name", "qwen2.5:7b"),
            context_limit=primary_data.get("context_limit", 32768),
            max_tokens=primary_data.get("max_tokens", 2048),
            temperature=primary_data.get("temperature", 0.0),
            request_timeout=primary_data.get("request_timeout", 60.0),
            enabled=primary_data.get("enabled", True),
        )

        complex_data = data.get("complex_model", {})
        self.complex_model = ModelConfig(
            name=complex_data.get("name", "mixtral:8x7b-instruct-v0.1-q4_K_M"),
            context_limit=complex_data.get("context_limit", 32768),
            max_tokens=complex_data.get("max_tokens", 4096),
            temperature=complex_data.get("temperature", 0.0),
            request_timeout=complex_data.get("request_timeout", 300.0),
            enabled=complex_data.get("enabled", False),
        )

        # Cloud model removed - local-only architecture per ADR-001/ADR-010

        # Parse routing config
        routing_data = data.get("routing", {})
        self.routing = RoutingConfig(
            complex_patterns=routing_data.get("complex_patterns", []),
            complex_token_threshold=routing_data.get("complex_token_threshold", 500),
        )

        # Store ollama host
        self.ollama_host = data.get("ollama_host", "http://localhost:11434")

    def route(
        self,
        prompt: str,
        token_count: int = 0,
        force_tier: Optional[ModelTier] = None,
    ) -> RoutingDecision:
        """
        Determine which local model tier to use for a request.

        Args:
            prompt: The user prompt (for pattern matching).
            token_count: Estimated token count of the request.
            force_tier: Force a specific tier (overrides routing logic).

        Returns:
            RoutingDecision with selected tier and configuration.
        """
        # Force specific tier if requested
        if force_tier:
            config = self._get_config_for_tier(force_tier)
            if config and config.enabled:
                return RoutingDecision(
                    tier=force_tier,
                    model_config=config,
                    reason=f"forced_tier_{force_tier.value}",
                    fallback_tier=self._get_fallback_tier(force_tier),
                )

        # Check for complex patterns (only if complex model is enabled, i.e., 64GB RAM available)
        if self.complex_model.enabled and self._is_complex_request(prompt, token_count):
            return RoutingDecision(
                tier=ModelTier.COMPLEX,
                model_config=self.complex_model,
                reason="complex_request_pattern",
                fallback_tier=ModelTier.PRIMARY,
            )

        # Default to primary model (Qwen 2.5 7B)
        return RoutingDecision(
            tier=ModelTier.PRIMARY,
            model_config=self.primary_model,
            reason="default_primary",
            fallback_tier=None,
        )

    def _is_complex_request(self, prompt: str, token_count: int) -> bool:
        """Check if request should use complex model."""
        # Check token threshold
        if token_count >= self.routing.complex_token_threshold:
            return True

        # Check patterns
        prompt_lower = prompt.lower()
        for pattern in self.routing.complex_patterns:
            if re.search(pattern, prompt_lower, re.IGNORECASE):
                return True

        return False

    def _get_config_for_tier(self, tier: ModelTier) -> Optional[ModelConfig]:
        """Get model config for a tier."""
        return {
            ModelTier.PRIMARY: self.primary_model,
            ModelTier.COMPLEX: self.complex_model,
        }.get(tier)

    def _get_fallback_tier(self, tier: ModelTier) -> Optional[ModelTier]:
        """Get fallback tier for a given tier (local models only)."""
        if tier == ModelTier.PRIMARY:
            return None  # No fallback for primary
        elif tier == ModelTier.COMPLEX:
            return ModelTier.PRIMARY  # Fall back to primary if complex fails
        return None

    def record_success(self, tier: ModelTier) -> None:
        """Record successful inference for a tier."""
        self._failure_counts[tier] = 0
        self._last_success[tier] = datetime.now(timezone.utc)

        self.logger.debug(
            f"Recorded success for {tier.value}",
            component=LogComponent.INFERENCE,
        )

    def record_failure(self, tier: ModelTier) -> None:
        """Record failed inference for a tier."""
        if tier in self._failure_counts:
            self._failure_counts[tier] += 1

        self.logger.warning(
            f"Recorded failure for {tier.value} (count: {self._failure_counts.get(tier, 0)})",
            component=LogComponent.INFERENCE,
            data={"tier": tier.value, "failure_count": self._failure_counts.get(tier, 0)},
        )

    def reset_failure_counts(self) -> None:
        """Reset all failure counts."""
        self._failure_counts = {
            ModelTier.PRIMARY: 0,
            ModelTier.COMPLEX: 0,
        }

    def get_status(self) -> Dict[str, Any]:
        """Get current router status (local models only)."""
        return {
            "primary_model": {
                "name": self.primary_model.name,
                "enabled": self.primary_model.enabled,
                "failures": self._failure_counts.get(ModelTier.PRIMARY, 0),
                "last_success": self._last_success.get(ModelTier.PRIMARY),
            },
            "complex_model": {
                "name": self.complex_model.name,
                "enabled": self.complex_model.enabled,
                "failures": self._failure_counts.get(ModelTier.COMPLEX, 0),
                "last_success": self._last_success.get(ModelTier.COMPLEX),
            },
            "architecture": "local-only",
        }


# Module-level convenience function
_default_router: Optional[ModelRouter] = None


def get_router() -> ModelRouter:
    """Get or create the default model router."""
    global _default_router
    if _default_router is None:
        _default_router = ModelRouter()
    return _default_router
