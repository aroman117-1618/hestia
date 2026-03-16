"""
Council data models for Hestia.

Defines intent types, role results, and council configuration.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class IntentType(Enum):
    """User intent classification used by Coordinator role."""

    CALENDAR_QUERY = "calendar_query"
    CALENDAR_CREATE = "calendar_create"
    REMINDER_QUERY = "reminder_query"
    REMINDER_CREATE = "reminder_create"
    NOTE_SEARCH = "note_search"
    NOTE_CREATE = "note_create"
    MAIL_QUERY = "mail_query"
    WEATHER_QUERY = "weather_query"
    STOCKS_QUERY = "stocks_query"
    MEMORY_SEARCH = "memory_search"
    CHAT = "chat"
    CODING = "coding"  # Agentic coding tasks — forces cloud routing (Sprint 13 WS4)
    MULTI_INTENT = "multi_intent"
    UNCLEAR = "unclear"

    @classmethod
    def from_string(cls, value: str) -> "IntentType":
        """Parse intent from string, defaulting to UNCLEAR."""
        try:
            return cls(value.lower().strip())
        except ValueError:
            return cls.UNCLEAR

    @property
    def requires_tools(self) -> bool:
        """Whether this intent typically requires tool execution."""
        return self in {
            IntentType.CALENDAR_QUERY,
            IntentType.CALENDAR_CREATE,
            IntentType.REMINDER_QUERY,
            IntentType.REMINDER_CREATE,
            IntentType.NOTE_SEARCH,
            IntentType.NOTE_CREATE,
            IntentType.MAIL_QUERY,
            IntentType.WEATHER_QUERY,
            IntentType.STOCKS_QUERY,
        }


@dataclass
class IntentClassification:
    """Result from Coordinator role."""

    primary_intent: IntentType
    confidence: float
    secondary_intents: List[IntentType] = field(default_factory=list)
    reasoning: str = ""
    # Agent routing (populated by orchestrator, not council)
    agent_route: Optional[str] = None      # AgentRoute value
    route_confidence: float = 0.0

    @classmethod
    def create(
        cls,
        primary_intent: IntentType,
        confidence: float,
        secondary_intents: Optional[List[IntentType]] = None,
        reasoning: str = "",
        agent_route: Optional[str] = None,
        route_confidence: float = 0.0,
    ) -> "IntentClassification":
        return cls(
            primary_intent=primary_intent,
            confidence=max(0.0, min(1.0, confidence)),
            secondary_intents=secondary_intents or [],
            reasoning=reasoning,
            agent_route=agent_route,
            route_confidence=max(0.0, min(1.0, route_confidence)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_intent": self.primary_intent.value,
            "confidence": self.confidence,
            "secondary_intents": [i.value for i in self.secondary_intents],
            "reasoning": self.reasoning,
            "agent_route": self.agent_route,
            "route_confidence": self.route_confidence,
        }


@dataclass
class ToolExtraction:
    """Result from Analyzer role."""

    tool_calls: List[Dict[str, Any]]
    confidence: float
    reasoning: str = ""

    @classmethod
    def create(
        cls,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        confidence: float = 1.0,
        reasoning: str = "",
    ) -> "ToolExtraction":
        return cls(
            tool_calls=tool_calls or [],
            confidence=max(0.0, min(1.0, confidence)),
            reasoning=reasoning,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_calls": self.tool_calls,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }


@dataclass
class ValidationReport:
    """Result from Validator role."""

    is_safe: bool
    is_high_quality: bool
    quality_score: float
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        is_safe: bool = True,
        is_high_quality: bool = True,
        quality_score: float = 1.0,
        issues: Optional[List[str]] = None,
        suggestions: Optional[List[str]] = None,
    ) -> "ValidationReport":
        return cls(
            is_safe=is_safe,
            is_high_quality=is_high_quality,
            quality_score=max(0.0, min(1.0, quality_score)),
            issues=issues or [],
            suggestions=suggestions or [],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_safe": self.is_safe,
            "is_high_quality": self.is_high_quality,
            "quality_score": self.quality_score,
            "issues": self.issues,
            "suggestions": self.suggestions,
        }


@dataclass
class RoleResult:
    """Result from a single council role execution."""

    role_name: str
    success: bool
    duration_ms: float
    error: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CouncilResult:
    """Aggregate result from council execution."""

    intent: Optional[IntentClassification] = None
    tool_extraction: Optional[ToolExtraction] = None
    validation: Optional[ValidationReport] = None
    synthesized_response: Optional[str] = None

    total_duration_ms: float = 0.0
    roles_executed: List[str] = field(default_factory=list)
    roles_failed: List[str] = field(default_factory=list)
    fallback_used: bool = False
    role_results: List[RoleResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent.to_dict() if self.intent else None,
            "tool_extraction": self.tool_extraction.to_dict() if self.tool_extraction else None,
            "validation": self.validation.to_dict() if self.validation else None,
            "synthesized_response": self.synthesized_response,
            "total_duration_ms": self.total_duration_ms,
            "roles_executed": self.roles_executed,
            "roles_failed": self.roles_failed,
            "fallback_used": self.fallback_used,
        }


@dataclass
class CouncilConfig:
    """Configuration for council behavior, loaded from inference.yaml."""

    enabled: bool = True
    force_local_roles: bool = True  # Council always uses local SLM, never cloud
    cloud_parallel: bool = True
    local_slm_model: str = "qwen2.5:0.5b"
    local_slm_timeout: float = 15.0
    role_timeout: float = 30.0
    fallback_to_single_agent: bool = True

    coordinator_enabled: bool = True
    coordinator_temperature: float = 0.0
    coordinator_max_tokens: int = 256

    analyzer_enabled: bool = True
    analyzer_temperature: float = 0.0
    analyzer_max_tokens: int = 512

    validator_enabled: bool = True
    validator_temperature: float = 0.0
    validator_max_tokens: int = 256

    responder_enabled: bool = True
    responder_temperature: float = 0.3
    responder_max_tokens: int = 2048

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CouncilConfig":
        """Load from YAML config dict."""
        roles = data.get("roles", {})
        coordinator = roles.get("coordinator", {})
        analyzer = roles.get("analyzer", {})
        validator = roles.get("validator", {})
        responder = roles.get("responder", {})

        return cls(
            enabled=data.get("enabled", True),
            force_local_roles=data.get("force_local_roles", True),
            cloud_parallel=data.get("cloud_parallel", True),
            local_slm_model=data.get("local_slm_model", "qwen2.5:0.5b"),
            local_slm_timeout=data.get("local_slm_timeout", 15.0),
            role_timeout=data.get("role_timeout", 30.0),
            fallback_to_single_agent=data.get("fallback_to_single_agent", True),
            coordinator_enabled=coordinator.get("enabled", True),
            coordinator_temperature=coordinator.get("temperature", 0.0),
            coordinator_max_tokens=coordinator.get("max_tokens", 256),
            analyzer_enabled=analyzer.get("enabled", True),
            analyzer_temperature=analyzer.get("temperature", 0.0),
            analyzer_max_tokens=analyzer.get("max_tokens", 512),
            validator_enabled=validator.get("enabled", True),
            validator_temperature=validator.get("temperature", 0.0),
            validator_max_tokens=validator.get("max_tokens", 256),
            responder_enabled=responder.get("enabled", True),
            responder_temperature=responder.get("temperature", 0.3),
            responder_max_tokens=responder.get("max_tokens", 2048),
        )
