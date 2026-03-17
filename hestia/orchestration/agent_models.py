"""
Agent orchestrator data models.

Defines types for the coordinate/analyze/delegate agent model:
- AgentRoute: routing decisions (hestia_solo, artemis, apollo, artemis_apollo)
- AgentTask/AgentResult: specialist dispatch and response
- ExecutionPlan/ExecutionStep: orchestration plans
- AgentByline: response attribution
- RoutingAuditEntry: observability
- OrchestratorConfig: loaded from config/orchestration.yaml
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class AgentRoute(str, Enum):
    """Agent routing decision produced by the orchestrator."""

    HESTIA_SOLO = "hestia_solo"
    ARTEMIS = "artemis"
    APOLLO = "apollo"
    ARTEMIS_THEN_APOLLO = "artemis_apollo"

    @property
    def is_multi_agent(self) -> bool:
        """Whether this route involves multiple specialist agents."""
        return self == AgentRoute.ARTEMIS_THEN_APOLLO

    @property
    def involves_specialist(self) -> bool:
        """Whether this route involves any specialist agent."""
        return self != AgentRoute.HESTIA_SOLO

    @property
    def display_name(self) -> str:
        """Human-readable name."""
        names = {
            "hestia_solo": "Hestia",
            "artemis": "Artemis",
            "apollo": "Apollo",
            "artemis_apollo": "Artemis \u2192 Apollo",
        }
        return names.get(self.value, self.value)


@dataclass
class AgentTask:
    """A task to be executed by a specialist agent."""

    agent_id: AgentRoute
    prompt: str
    context_slice: Dict[str, Any]
    model_preference: Optional[str] = None  # e.g., "coding" for Apollo


@dataclass
class AgentResult:
    """Result from a specialist agent's execution."""

    agent_id: AgentRoute
    content: str
    confidence: float = 1.0
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tokens_used: int = 0
    duration_ms: int = 0
    error: Optional[str] = None

    def is_low_confidence(self, threshold: float = 0.4) -> bool:
        """Whether this result is below the confidence threshold."""
        return self.confidence < threshold


@dataclass
class ExecutionStep:
    """A single step in an execution plan. Multiple tasks = parallel group."""

    tasks: List[AgentTask]
    depends_on: Optional[int] = None  # Index of step this depends on


@dataclass
class ExecutionPlan:
    """Orchestration plan built by the planner."""

    steps: List[ExecutionStep]
    rationale: str
    route: AgentRoute = AgentRoute.HESTIA_SOLO

    @property
    def estimated_hops(self) -> int:
        """Total number of inference calls needed."""
        return len(self.steps)

    @property
    def has_parallel_steps(self) -> bool:
        """Whether any step has multiple parallel tasks."""
        return any(len(step.tasks) > 1 for step in self.steps)


AGENT_ICONS = {
    AgentRoute.ARTEMIS: "\U0001f4d0",
    AgentRoute.APOLLO: "\u26a1",
    AgentRoute.HESTIA_SOLO: "\U0001f3e0",
}

AGENT_DISPLAY_NAMES = {
    AgentRoute.ARTEMIS: "Artemis",
    AgentRoute.APOLLO: "Apollo",
    AgentRoute.HESTIA_SOLO: "Hestia",
}


@dataclass
class AgentByline:
    """Attribution for a specialist agent's contribution to a response."""

    agent: AgentRoute
    contribution_type: str  # "analysis", "implementation", "tool_result"
    summary: str

    def format(self) -> str:
        """Format byline for display."""
        icon = AGENT_ICONS.get(self.agent, "")
        name = AGENT_DISPLAY_NAMES.get(self.agent, self.agent.value)
        return f"{icon} {name} \u2014 {self.summary}"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API response."""
        return {
            "agent": self.agent.value,
            "contribution": self.contribution_type,
            "summary": self.summary,
        }


@dataclass
class RoutingAuditEntry:
    """Audit log entry for a routing decision."""

    id: str
    user_id: str
    request_id: str
    timestamp: datetime
    intent: str  # IntentType value
    route_chosen: str  # AgentRoute value
    route_confidence: float
    actual_agents: List[str]  # AgentRoute values actually invoked
    chain_collapsed: bool = False
    fallback_triggered: bool = False
    total_inference_calls: int = 1
    total_duration_ms: int = 0

    @classmethod
    def create(
        cls,
        user_id: str,
        request_id: str,
        intent: str,
        route_chosen: str,
        route_confidence: float,
    ) -> "RoutingAuditEntry":
        """Factory with auto-generated ID and timestamp."""
        return cls(
            id=f"raud-{uuid4().hex[:12]}",
            user_id=user_id,
            request_id=request_id,
            timestamp=datetime.now(timezone.utc),
            intent=intent,
            route_chosen=route_chosen,
            route_confidence=route_confidence,
            actual_agents=[],
        )


@dataclass
class OrchestratorConfig:
    """Configuration for the agent orchestrator, loaded from orchestration.yaml."""

    enabled: bool = True
    full_dispatch_threshold: float = 0.8
    enriched_solo_threshold: float = 0.5
    min_specialist_confidence: float = 0.4
    min_words_for_chain: int = 15
    max_hops_local: int = 2
    max_hops_cloud: int = 4
    analysis_keywords: List[str] = field(default_factory=lambda: [
        "analyze", "compare", "trade-off", "tradeoff", "pros and cons",
        "evaluate", "assess", "review", "explain why", "help me think",
        "what are the options", "should i", "debate", "argue",
        "research", "investigate", "deep dive",
    ])
    execution_keywords: List[str] = field(default_factory=lambda: [
        "write", "build", "implement", "create", "scaffold",
        "generate", "code", "fix", "refactor", "migrate",
        "deploy", "script", "function", "class", "test",
    ])

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrchestratorConfig":
        """Load from YAML config dict."""
        thresholds = data.get("confidence_thresholds", {})
        chain = data.get("chain_validation", {})
        fallback = data.get("fallback", {})
        return cls(
            enabled=data.get("enabled", True),
            full_dispatch_threshold=thresholds.get("full_dispatch", 0.8),
            enriched_solo_threshold=thresholds.get("enriched_solo", 0.5),
            min_specialist_confidence=fallback.get(
                "min_specialist_confidence", 0.4
            ),
            min_words_for_chain=chain.get("min_words_for_chain", 15),
            max_hops_local=chain.get("max_hops_local", 2),
            max_hops_cloud=chain.get("max_hops_cloud", 4),
            analysis_keywords=data.get("analysis_keywords", cls().analysis_keywords),
            execution_keywords=data.get("execution_keywords", cls().execution_keywords),
        )
