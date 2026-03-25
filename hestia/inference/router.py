"""
Model router for Hestia inference.

Routes requests to the appropriate model tier based on:
- Request complexity (token count, patterns)
- Model availability (health checks)
- Cloud provider state (disabled, enabled_full, enabled_smart)

Tiers:
1. Primary: Fast local model (Qwen 3.5 9B) - default for routine queries
2. Coding: Code specialist (Qwen 2.5 Coder 7B) - for programming tasks
3. Complex: Large local model (Mixtral 8x7B) - for complex reasoning (when 64GB RAM available)
4. Cloud: Cloud LLM provider - for full cloud mode or smart spillover after local failure
"""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from hestia.logging import get_logger, LogComponent, EventType


class ModelTier(Enum):
    """Model tiers for routing."""
    PRIMARY = "primary"      # Fast local (Qwen 3.5 9B)
    CODING = "coding"        # Code specialist (Qwen 2.5 Coder 7B)
    COMPLEX = "complex"      # Large local (Mixtral 8x7B, when 64GB available)
    CLOUD = "cloud"          # Cloud LLM (Anthropic/OpenAI/Google)


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
    default_agent: Optional[str] = None  # Suggested agent persona for this tier
    supports_tools: bool = True  # Whether this model supports Ollama native tool calling


@dataclass
class CloudRoutingConfig:
    """Configuration for cloud routing."""
    # Cloud state: "disabled", "enabled_full", "enabled_smart"
    state: str = "disabled"
    # Smart mode: route to cloud if token count exceeds this
    spillover_token_threshold: int = 16000
    # Smart mode: fall back to cloud after local retries exhausted
    spillover_on_local_failure: bool = True
    # Cloud-specific timeout
    request_timeout: float = 60.0
    # Cloud-specific retries
    max_retries: int = 2
    # Route tool-calling requests to cloud for better selection accuracy.
    # Disable when local hardware can run 70B+ models with good tool calling.
    tool_call_cloud_routing: bool = True


@dataclass
class HardwareAdaptationConfig:
    """Configuration for hardware-aware model adaptation."""
    enabled: bool = True
    fallback_primary: str = "qwen2.5:7b"
    auto_cloud_smart: bool = True
    min_tokens_per_sec: float = 8.0


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
    Routes inference requests to appropriate model tier.

    Supports local tiers (primary, complex) and cloud tier.
    Cloud state can be set dynamically by CloudManager.
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        cloud_state: Optional[str] = None,
    ):
        """
        Initialize router with configuration.

        Args:
            config_path: Path to inference.yaml config file.
            cloud_state: Override cloud state ("disabled", "enabled_full", "enabled_smart").
        """
        self.logger = get_logger()

        # Load configuration
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "inference.yaml"

        self._load_config(config_path)

        # Environment variable override for primary model
        env_model = os.environ.get("HESTIA_PRIMARY_MODEL")
        if env_model:
            self.primary_model.name = env_model
            self.logger.info(
                f"Primary model overridden by HESTIA_PRIMARY_MODEL: {env_model}",
                component=LogComponent.INFERENCE,
            )

        # Hardware adaptation state (checked once after first inference)
        self._adaptation_checked = False
        self._adaptation_applied = False

        # Override cloud state if provided
        if cloud_state is not None:
            valid_states = {"disabled", "enabled_full", "enabled_smart"}
            if cloud_state not in valid_states:
                raise ValueError(
                    f"Invalid cloud_state: {cloud_state}. Must be one of {valid_states}"
                )
            self.cloud_routing.state = cloud_state
            self.cloud_model.enabled = cloud_state != "disabled"

        # Track failure counts for escalation
        self._failure_counts: Dict[ModelTier, int] = {
            ModelTier.PRIMARY: 0,
            ModelTier.CODING: 0,
            ModelTier.COMPLEX: 0,
            ModelTier.CLOUD: 0,
        }

        # Track last successful inference per tier
        self._last_success: Dict[ModelTier, Optional[datetime]] = {
            ModelTier.PRIMARY: None,
            ModelTier.CODING: None,
            ModelTier.COMPLEX: None,
            ModelTier.CLOUD: None,
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
            name=primary_data.get("name", "qwen3.5:9b"),
            context_limit=primary_data.get("context_limit", 32768),
            max_tokens=primary_data.get("max_tokens", 2048),
            temperature=primary_data.get("temperature", 0.0),
            request_timeout=primary_data.get("request_timeout", 60.0),
            enabled=primary_data.get("enabled", True),
            default_agent=primary_data.get("default_agent"),
        )

        complex_data = data.get("complex_model", {})
        self.complex_model = ModelConfig(
            name=complex_data.get("name", "mixtral:8x7b-instruct-v0.1-q4_K_M"),
            context_limit=complex_data.get("context_limit", 32768),
            max_tokens=complex_data.get("max_tokens", 4096),
            temperature=complex_data.get("temperature", 0.0),
            request_timeout=complex_data.get("request_timeout", 300.0),
            enabled=complex_data.get("enabled", False),
            default_agent=complex_data.get("default_agent"),
            supports_tools=complex_data.get("supports_tools", True),
        )

        coding_data = data.get("coding_model", {})
        self.coding_model = ModelConfig(
            name=coding_data.get("name", "qwen2.5-coder:7b"),
            context_limit=coding_data.get("context_limit", 32768),
            max_tokens=coding_data.get("max_tokens", 4096),
            temperature=coding_data.get("temperature", 0.0),
            request_timeout=coding_data.get("request_timeout", 90.0),
            enabled=coding_data.get("enabled", False),
            default_agent=coding_data.get("default_agent"),
        )

        # Cloud routing config
        cloud_data = data.get("cloud", {})
        self.cloud_routing = CloudRoutingConfig(
            state=cloud_data.get("state", "disabled"),
            spillover_token_threshold=cloud_data.get("spillover_token_threshold", 16000),
            spillover_on_local_failure=cloud_data.get("spillover_on_local_failure", True),
            request_timeout=cloud_data.get("request_timeout", 60.0),
            max_retries=cloud_data.get("max_retries", 2),
            tool_call_cloud_routing=cloud_data.get("tool_call_cloud_routing", True),
        )

        # Cloud model config (used when routing to cloud tier)
        self.cloud_model = ModelConfig(
            name="cloud",  # Placeholder — actual model selected by CloudManager
            context_limit=200000,
            max_tokens=4096,
            temperature=0.0,
            request_timeout=self.cloud_routing.request_timeout,
            enabled=self.cloud_routing.state != "disabled",
        )

        # Parse routing config
        routing_data = data.get("routing", {})
        self.routing = RoutingConfig(
            complex_patterns=routing_data.get("complex_patterns", []),
            complex_token_threshold=routing_data.get("complex_token_threshold", 500),
        )

        # Parse hardware adaptation config
        hw_data = data.get("hardware_adaptation", {})
        self.hardware_adaptation = HardwareAdaptationConfig(
            enabled=hw_data.get("enabled", True),
            fallback_primary=hw_data.get("fallback_primary", "qwen2.5:7b"),
            auto_cloud_smart=hw_data.get("auto_cloud_smart", True),
            min_tokens_per_sec=hw_data.get("min_tokens_per_sec", 8.0),
        )

        # Store ollama host
        self.ollama_host = data.get("ollama_host", "http://localhost:11434")

    def route(
        self,
        prompt: str,
        token_count: int = 0,
        force_tier: Optional[ModelTier] = None,
        has_tools: bool = False,
    ) -> RoutingDecision:
        """
        Determine which model tier to use for a request.

        Cloud routing logic:
        - disabled: local-only (primary/complex)
        - enabled_full: always cloud
        - enabled_smart: local first, cloud fallback on failure or high token count
        - enabled_smart + has_tools + tool_call_cloud_routing: always cloud

        Args:
            prompt: The user prompt (for pattern matching).
            token_count: Estimated token count of the request.
            force_tier: Force a specific tier (overrides routing logic).
            has_tools: Whether tool definitions are included in this request.
                When True and cloud is enabled_smart with tool_call_cloud_routing,
                routes directly to cloud for better tool selection accuracy.

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

        cloud_state = self.cloud_routing.state

        # enabled_full: always route to cloud
        if cloud_state == "enabled_full" and self.cloud_model.enabled:
            return RoutingDecision(
                tier=ModelTier.CLOUD,
                model_config=self.cloud_model,
                reason="cloud_full_mode",
                fallback_tier=ModelTier.PRIMARY,
            )

        # enabled_smart: check spillover conditions
        if cloud_state == "enabled_smart" and self.cloud_model.enabled:
            # Tool-calling requests → route to cloud for accurate tool selection
            if has_tools and self.cloud_routing.tool_call_cloud_routing:
                return RoutingDecision(
                    tier=ModelTier.CLOUD,
                    model_config=self.cloud_model,
                    reason="cloud_smart_tool_routing",
                    fallback_tier=ModelTier.PRIMARY,
                )

            # High token count → route directly to cloud
            if token_count >= self.cloud_routing.spillover_token_threshold:
                return RoutingDecision(
                    tier=ModelTier.CLOUD,
                    model_config=self.cloud_model,
                    reason="cloud_smart_token_spillover",
                    fallback_tier=ModelTier.PRIMARY,
                )

            # Otherwise: local first with cloud fallback
            fallback = ModelTier.CLOUD if self.cloud_routing.spillover_on_local_failure else None

            # Check for coding patterns (coding takes priority over complex)
            if self.coding_model.enabled and self._matches_keyword_patterns(prompt):
                return RoutingDecision(
                    tier=ModelTier.CODING,
                    model_config=self.coding_model,
                    reason="coding_request_pattern",
                    fallback_tier=fallback,
                )

            # Check for complex patterns — skip if request has tools and
            # the complex model doesn't support them (e.g. deepseek-r1)
            supports_tools = getattr(self.complex_model, "supports_tools", True)
            if (
                self.complex_model.enabled
                and (not has_tools or supports_tools)
                and self._matches_routing_patterns(prompt, token_count)
            ):
                return RoutingDecision(
                    tier=ModelTier.COMPLEX,
                    model_config=self.complex_model,
                    reason="complex_request_pattern",
                    fallback_tier=fallback,
                )

            return RoutingDecision(
                tier=ModelTier.PRIMARY,
                model_config=self.primary_model,
                reason="default_primary",
                fallback_tier=fallback,
            )

        # disabled (or no cloud configured): local-only routing
        if self.coding_model.enabled and self._matches_keyword_patterns(prompt):
            return RoutingDecision(
                tier=ModelTier.CODING,
                model_config=self.coding_model,
                reason="coding_request_pattern",
                fallback_tier=ModelTier.PRIMARY,
            )

        supports_tools = getattr(self.complex_model, "supports_tools", True)
        if (
            self.complex_model.enabled
            and (not has_tools or supports_tools)
            and self._matches_routing_patterns(prompt, token_count)
        ):
            return RoutingDecision(
                tier=ModelTier.COMPLEX,
                model_config=self.complex_model,
                reason="complex_request_pattern",
                fallback_tier=ModelTier.PRIMARY,
            )

        return RoutingDecision(
            tier=ModelTier.PRIMARY,
            model_config=self.primary_model,
            reason="default_primary",
            fallback_tier=None,
        )

    def _matches_keyword_patterns(self, prompt: str) -> bool:
        """Check if request matches keyword patterns (coding tier: keywords only)."""
        prompt_lower = prompt.lower()
        for pattern in self.routing.complex_patterns:
            if re.search(pattern, prompt_lower, re.IGNORECASE):
                return True
        return False

    def _matches_routing_patterns(self, prompt: str, token_count: int) -> bool:
        """Check if request matches routing patterns (complex tier: keywords + token threshold)."""
        if token_count >= self.routing.complex_token_threshold:
            return True
        return self._matches_keyword_patterns(prompt)

    def _get_config_for_tier(self, tier: ModelTier) -> Optional[ModelConfig]:
        """Get model config for a tier."""
        return {
            ModelTier.PRIMARY: self.primary_model,
            ModelTier.CODING: self.coding_model,
            ModelTier.COMPLEX: self.complex_model,
            ModelTier.CLOUD: self.cloud_model,
        }.get(tier)

    def _get_fallback_tier(self, tier: ModelTier) -> Optional[ModelTier]:
        """Get fallback tier for a given tier."""
        cloud_state = self.cloud_routing.state

        if tier == ModelTier.PRIMARY:
            # Primary can fall back to cloud in smart mode
            if cloud_state == "enabled_smart" and self.cloud_routing.spillover_on_local_failure:
                return ModelTier.CLOUD
            return None
        elif tier == ModelTier.CODING:
            return ModelTier.PRIMARY
        elif tier == ModelTier.COMPLEX:
            # Complex falls back to cloud (smart) or primary
            if cloud_state == "enabled_smart" and self.cloud_routing.spillover_on_local_failure:
                return ModelTier.CLOUD
            return ModelTier.PRIMARY
        elif tier == ModelTier.CLOUD:
            return ModelTier.PRIMARY  # Cloud falls back to primary
        return None

    def set_cloud_state(self, state: str) -> None:
        """
        Dynamically update cloud routing state.

        Called by CloudManager when provider state changes.

        Args:
            state: "disabled", "enabled_full", or "enabled_smart"
        """
        self.cloud_routing.state = state
        self.cloud_model.enabled = state != "disabled"
        self.logger.info(
            f"Cloud routing state updated: {state}",
            component=LogComponent.INFERENCE,
        )

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
            ModelTier.CODING: 0,
            ModelTier.COMPLEX: 0,
            ModelTier.CLOUD: 0,
        }

    def check_hardware_adaptation(
        self,
        tokens_out: int = 0,
        duration_ms: float = 0,
    ) -> None:
        """
        Check if primary model runs fast enough on this hardware.

        Called once after first successful local inference. Uses the actual
        generation speed (tokens/sec) from the response to decide if the
        model is too heavy for this machine.

        Args:
            tokens_out: Number of tokens generated in the response.
            duration_ms: Total inference duration in milliseconds.
        """
        if self._adaptation_checked:
            return
        self._adaptation_checked = True

        if not self.hardware_adaptation.enabled:
            return
        if os.environ.get("HESTIA_PRIMARY_MODEL"):
            return  # Manual override takes precedence

        # Need meaningful output to measure speed (skip trivial responses)
        if tokens_out < 5 or duration_ms <= 0:
            self._adaptation_checked = False  # Retry on next inference
            return

        tokens_per_sec = tokens_out / (duration_ms / 1000)
        threshold = self.hardware_adaptation.min_tokens_per_sec

        self.logger.info(
            f"Hardware check: {self.primary_model.name} generating at "
            f"{tokens_per_sec:.1f} tok/s (threshold: {threshold:.1f})",
            component=LogComponent.INFERENCE,
            data={
                "model": self.primary_model.name,
                "tokens_per_sec": round(tokens_per_sec, 1),
                "threshold": threshold,
                "tokens_out": tokens_out,
                "duration_ms": round(duration_ms),
            },
        )

        if tokens_per_sec >= threshold:
            self.logger.info(
                f"Primary model speed OK ({tokens_per_sec:.1f} tok/s), no adaptation needed",
                component=LogComponent.INFERENCE,
            )
            return

        # Model too slow — apply adaptation
        fallback = self.hardware_adaptation.fallback_primary
        original = self.primary_model.name

        # Don't adapt if already using the fallback model
        if original == fallback:
            return

        self.primary_model.name = fallback
        self._adaptation_applied = True

        self.logger.warning(
            f"Hardware adaptation: {original} → {fallback} "
            f"({tokens_per_sec:.1f} tok/s < {threshold:.1f} threshold)",
            component=LogComponent.INFERENCE,
            data={
                "original_model": original,
                "fallback_model": fallback,
                "tokens_per_sec": round(tokens_per_sec, 1),
            },
        )

        # Auto-enable cloud smart mode for additional capacity
        if (
            self.hardware_adaptation.auto_cloud_smart
            and self.cloud_routing.state == "disabled"
        ):
            self.set_cloud_state("enabled_smart")
            self.logger.info(
                "Hardware adaptation: auto-enabled cloud smart mode",
                component=LogComponent.INFERENCE,
            )

    def get_suggested_agent(
        self,
        prompt: str,
        token_count: int = 0,
    ) -> Optional[str]:
        """
        Get the default agent for the tier this request would route to.

        Returns None if the tier has no default agent configured.
        """
        decision = self.route(prompt=prompt, token_count=token_count)
        return decision.model_config.default_agent

    def route_for_agent(self, agent_name: str) -> Optional[ModelTier]:
        """
        Get the preferred model tier for a specific agent.

        Looks up agent_model_preferences from orchestration config (if loaded).
        Returns None if no preference is configured or tier is unavailable.
        """
        if not hasattr(self, "_agent_model_preferences"):
            return None

        pref = self._agent_model_preferences.get(agent_name.lower())
        if not pref:
            return None

        # Map tier string to ModelTier enum
        tier_map = {
            "primary": ModelTier.PRIMARY,
            "coding": ModelTier.CODING,
            "complex": ModelTier.COMPLEX,
            "cloud": ModelTier.CLOUD,
        }
        tier = tier_map.get(pref.preferred_tier)
        if not tier:
            return None

        # Verify the tier's model is enabled
        config = self._get_config_for_tier(tier)
        if config and config.enabled:
            return tier

        self.logger.info(
            f"Agent {agent_name} preferred tier {pref.preferred_tier} unavailable, falling back",
            component=LogComponent.INFERENCE,
        )
        return None

    def set_agent_model_preferences(
        self,
        preferences: Dict[str, Any],
    ) -> None:
        """Load agent model preferences from orchestrator config."""
        self._agent_model_preferences = preferences

    def get_status(self) -> Dict[str, Any]:
        """Get current router status."""
        cloud_state = self.cloud_routing.state
        architecture = "local-only" if cloud_state == "disabled" else f"hybrid ({cloud_state})"

        status: Dict[str, Any] = {
            "primary_model": {
                "name": self.primary_model.name,
                "enabled": self.primary_model.enabled,
                "failures": self._failure_counts.get(ModelTier.PRIMARY, 0),
                "last_success": self._last_success.get(ModelTier.PRIMARY),
            },
            "coding_model": {
                "name": self.coding_model.name,
                "enabled": self.coding_model.enabled,
                "failures": self._failure_counts.get(ModelTier.CODING, 0),
                "last_success": self._last_success.get(ModelTier.CODING),
            },
            "complex_model": {
                "name": self.complex_model.name,
                "enabled": self.complex_model.enabled,
                "failures": self._failure_counts.get(ModelTier.COMPLEX, 0),
                "last_success": self._last_success.get(ModelTier.COMPLEX),
            },
            "cloud": {
                "state": cloud_state,
                "enabled": self.cloud_model.enabled,
                "failures": self._failure_counts.get(ModelTier.CLOUD, 0),
                "last_success": self._last_success.get(ModelTier.CLOUD),
                "spillover_token_threshold": self.cloud_routing.spillover_token_threshold,
                "spillover_on_local_failure": self.cloud_routing.spillover_on_local_failure,
                "tool_call_cloud_routing": self.cloud_routing.tool_call_cloud_routing,
            },
            "architecture": architecture,
            "hardware_adaptation": {
                "enabled": self.hardware_adaptation.enabled,
                "checked": self._adaptation_checked,
                "applied": self._adaptation_applied,
                "fallback_primary": self.hardware_adaptation.fallback_primary,
            },
        }
        return status


# Module-level convenience function
_default_router: Optional[ModelRouter] = None


def get_router() -> ModelRouter:
    """Get or create the default model router."""
    global _default_router
    if _default_router is None:
        _default_router = ModelRouter()
    return _default_router
