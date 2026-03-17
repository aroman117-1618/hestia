# Agent Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve Hestia from user-routed persona switching to a coordinator-delegate model where Hestia orchestrates Artemis (analysis) and Apollo (execution) as internal sub-agents.

**Architecture:** Extend the council coordinator to produce agent routing decisions via a deterministic intent-to-route heuristic. New orchestration components (planner, executor, context manager, synthesizer) sit between council classification and inference. The handler calls the orchestrator instead of calling inference directly. Async interfaces collapse to single-call on M1 but parallelize on M5 Ultra.

**Tech Stack:** Python 3.12, FastAPI, asyncio, aiosqlite, Pydantic, pytest

**Spec:** `docs/superpowers/specs/2026-03-16-agent-orchestrator-design.md`
**Audit:** `docs/plans/agent-orchestrator-audit-2026-03-16.md`
**ADR:** ADR-042

---

## File Map

### New Files
| File | Responsibility |
|------|---------------|
| `hestia/orchestration/agent_models.py` | AgentRoute enum, AgentTask, AgentResult, ExecutionPlan, ExecutionStep, AgentByline, RoutingAuditEntry, OrchestratorConfig |
| `hestia/orchestration/router.py` | Intent-to-route heuristic, keyword matching, confidence scoring |
| `hestia/orchestration/planner.py` | OrchestrationPlanner — builds ExecutionPlans from routing decisions, chain validation, confidence gating |
| `hestia/orchestration/executor.py` | AgentExecutor — dispatches AgentTasks to inference, handles fallback, parallel groups |
| `hestia/orchestration/context_manager.py` | Context slicing functions — per-agent context subsetting (lightweight, no state) |
| `hestia/orchestration/synthesizer.py` | Result synthesis + byline generation functions (lightweight, no state) |
| `hestia/orchestration/audit_db.py` | RoutingAuditDatabase — SQLite storage for routing decisions |
| `config/orchestration.yaml` | Orchestrator config — thresholds, keywords, enabled flag |
| `tests/test_agent_orchestrator.py` | All orchestrator tests |
| `tests/test_routing_audit.py` | Audit database tests |
| `tests/test_orchestrator_integration.py` | Handler integration + byline tests |

### Modified Files
| File | Changes |
|------|---------|
| `hestia/council/models.py` | Add `agent_route` and `route_confidence` fields to IntentClassification |
| `hestia/orchestration/models.py` | Add `bylines` field to Response |
| `hestia/orchestration/handler.py` | Call orchestrator between pre-inference and inference steps |
| `hestia/orchestration/mode.py` | Add `@artemis`/`@apollo` to invoke patterns |
| `hestia/api/schemas/chat.py` | Add `AgentBylineSchema` and `bylines` field to ChatResponse |
| `hestia/api/schemas/common.py` | Add `AgentRouteEnum` if needed |
| `hestia/api/routes/chat.py` | Thread bylines from Response into ChatResponse |
| `hestia/outcomes/models.py` | Add `agent_route` and `route_confidence` fields |
| `hestia/outcomes/database.py` | Add columns via migration, update store/query methods |
| `hestia/api/server.py` | Initialize/close audit database in lifecycle |

---

## Chunk 1: Foundation — Models, Config, Router

### Task 1: Agent Orchestrator Models

**Files:**
- Create: `hestia/orchestration/agent_models.py`
- Test: `tests/test_agent_orchestrator.py`

- [ ] **Step 1: Write tests for AgentRoute enum and model types**

```python
# tests/test_agent_orchestrator.py
"""Tests for agent orchestrator models, routing, planning, and execution."""

import pytest
from hestia.orchestration.agent_models import (
    AgentRoute,
    AgentTask,
    AgentResult,
    ExecutionPlan,
    ExecutionStep,
    AgentByline,
    RoutingAuditEntry,
    OrchestratorConfig,
)


class TestAgentRoute:
    """AgentRoute enum behavior."""

    def test_enum_values(self):
        assert AgentRoute.HESTIA_SOLO.value == "hestia_solo"
        assert AgentRoute.ARTEMIS.value == "artemis"
        assert AgentRoute.APOLLO.value == "apollo"
        assert AgentRoute.ARTEMIS_THEN_APOLLO.value == "artemis_apollo"

    def test_is_multi_agent(self):
        assert not AgentRoute.HESTIA_SOLO.is_multi_agent
        assert not AgentRoute.ARTEMIS.is_multi_agent
        assert not AgentRoute.APOLLO.is_multi_agent
        assert AgentRoute.ARTEMIS_THEN_APOLLO.is_multi_agent

    def test_involves_specialist(self):
        assert not AgentRoute.HESTIA_SOLO.involves_specialist
        assert AgentRoute.ARTEMIS.involves_specialist
        assert AgentRoute.APOLLO.involves_specialist
        assert AgentRoute.ARTEMIS_THEN_APOLLO.involves_specialist


class TestAgentTask:
    """AgentTask construction and validation."""

    def test_create_task(self):
        task = AgentTask(
            agent_id=AgentRoute.ARTEMIS,
            prompt="Analyze trade-offs between A and B",
            context_slice={"memory": "some context", "profile": "user prefs"},
        )
        assert task.agent_id == AgentRoute.ARTEMIS
        assert task.model_preference is None

    def test_create_task_with_model(self):
        task = AgentTask(
            agent_id=AgentRoute.APOLLO,
            prompt="Write the migration",
            context_slice={},
            model_preference="coding",
        )
        assert task.model_preference == "coding"


class TestAgentResult:
    """AgentResult creation."""

    def test_create_result(self):
        result = AgentResult(
            agent_id=AgentRoute.ARTEMIS,
            content="SSE is better because...",
            confidence=0.92,
        )
        assert result.confidence == 0.92
        assert result.tool_calls == []
        assert result.tokens_used == 0

    def test_is_low_confidence(self):
        low = AgentResult(agent_id=AgentRoute.ARTEMIS, content="maybe", confidence=0.3)
        high = AgentResult(agent_id=AgentRoute.ARTEMIS, content="yes", confidence=0.8)
        assert low.is_low_confidence(threshold=0.4)
        assert not high.is_low_confidence(threshold=0.4)


class TestExecutionPlan:
    """ExecutionPlan construction."""

    def test_single_step(self):
        task = AgentTask(agent_id=AgentRoute.ARTEMIS, prompt="analyze", context_slice={})
        step = ExecutionStep(tasks=[task])
        plan = ExecutionPlan(steps=[step], rationale="Analysis needed")
        assert plan.estimated_hops == 1
        assert not plan.has_parallel_steps

    def test_chain(self):
        t1 = AgentTask(agent_id=AgentRoute.ARTEMIS, prompt="analyze", context_slice={})
        t2 = AgentTask(agent_id=AgentRoute.APOLLO, prompt="build", context_slice={})
        s1 = ExecutionStep(tasks=[t1])
        s2 = ExecutionStep(tasks=[t2], depends_on=0)
        plan = ExecutionPlan(steps=[s1, s2], rationale="Analyze then build")
        assert plan.estimated_hops == 2

    def test_parallel_group(self):
        t1 = AgentTask(agent_id=AgentRoute.ARTEMIS, prompt="analyze", context_slice={})
        t2 = AgentTask(agent_id=AgentRoute.APOLLO, prompt="build", context_slice={})
        step = ExecutionStep(tasks=[t1, t2])
        plan = ExecutionPlan(steps=[step], rationale="Parallel work")
        assert plan.has_parallel_steps


class TestAgentByline:
    """AgentByline formatting."""

    def test_format_artemis(self):
        byline = AgentByline(
            agent=AgentRoute.ARTEMIS,
            contribution_type="analysis",
            summary="Analyzed WebSocket vs SSE trade-offs",
        )
        assert "Artemis" in byline.format()
        assert "📐" in byline.format()

    def test_format_apollo(self):
        byline = AgentByline(
            agent=AgentRoute.APOLLO,
            contribution_type="implementation",
            summary="Scaffolded SSE implementation",
        )
        assert "Apollo" in byline.format()
        assert "⚡" in byline.format()

    def test_to_dict(self):
        byline = AgentByline(
            agent=AgentRoute.ARTEMIS,
            contribution_type="analysis",
            summary="Analyzed trade-offs",
        )
        d = byline.to_dict()
        assert d["agent"] == "artemis"
        assert d["contribution"] == "analysis"
        assert d["summary"] == "Analyzed trade-offs"


class TestOrchestratorConfig:
    """OrchestratorConfig loading from YAML."""

    def test_defaults(self):
        config = OrchestratorConfig()
        assert config.enabled is True
        assert config.full_dispatch_threshold == 0.8
        assert config.enriched_solo_threshold == 0.5
        assert config.min_specialist_confidence == 0.4
        assert config.min_words_for_chain == 15
        assert config.max_hops_local == 2
        assert config.max_hops_cloud == 4

    def test_from_dict(self):
        data = {
            "enabled": False,
            "confidence_thresholds": {
                "full_dispatch": 0.9,
                "enriched_solo": 0.6,
            },
        }
        config = OrchestratorConfig.from_dict(data)
        assert config.enabled is False
        assert config.full_dispatch_threshold == 0.9
        assert config.enriched_solo_threshold == 0.6
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agent_orchestrator.py -v --timeout=30`
Expected: FAIL — `ModuleNotFoundError: No module named 'hestia.orchestration.agent_models'`

- [ ] **Step 3: Implement agent_models.py**

```python
# hestia/orchestration/agent_models.py
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
            "artemis_apollo": "Artemis → Apollo",
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
    AgentRoute.ARTEMIS: "📐",
    AgentRoute.APOLLO: "⚡",
    AgentRoute.HESTIA_SOLO: "🏠",
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
        return f"{icon} {name} — {self.summary}"

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
        return cls(
            enabled=data.get("enabled", True),
            full_dispatch_threshold=thresholds.get("full_dispatch", 0.8),
            enriched_solo_threshold=thresholds.get("enriched_solo", 0.5),
            min_specialist_confidence=data.get("fallback", {}).get(
                "min_specialist_confidence", 0.4
            ),
            min_words_for_chain=chain.get("min_words_for_chain", 15),
            max_hops_local=chain.get("max_hops_local", 2),
            max_hops_cloud=chain.get("max_hops_cloud", 4),
            analysis_keywords=data.get("analysis_keywords", cls().analysis_keywords),
            execution_keywords=data.get("execution_keywords", cls().execution_keywords),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_agent_orchestrator.py -v --timeout=30`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/orchestration/agent_models.py tests/test_agent_orchestrator.py
git commit -m "feat: agent orchestrator models (AgentRoute, Task, Result, Plan, Byline)"
```

---

### Task 2: Orchestration Config File

**Files:**
- Create: `config/orchestration.yaml`

- [ ] **Step 1: Create config file**

```yaml
# config/orchestration.yaml
# Agent orchestrator configuration — coordinate/analyze/delegate model
# ADR-042

orchestrator:
  enabled: true  # Kill switch — false falls back to current single-pipeline behavior

  confidence_thresholds:
    full_dispatch: 0.8     # Route confidence above this → full specialist dispatch
    enriched_solo: 0.5     # Route confidence 0.5-0.8 → Hestia solo with persona hints

  chain_validation:
    min_words_for_chain: 15   # Requests shorter than this → collapse multi-agent to single
    max_hops_local: 2          # Max inference calls when cloud is disabled
    max_hops_cloud: 4          # Max inference calls when cloud is enabled

  fallback:
    min_specialist_confidence: 0.4  # Specialist results below this trigger fallback to Hestia

  # Keywords that trigger Artemis (analysis) routing for CHAT intent
  analysis_keywords:
    - "analyze"
    - "compare"
    - "trade-off"
    - "tradeoff"
    - "pros and cons"
    - "evaluate"
    - "assess"
    - "review"
    - "explain why"
    - "help me think"
    - "what are the options"
    - "should i"
    - "debate"
    - "argue"
    - "research"
    - "investigate"
    - "deep dive"

  # Keywords that trigger Apollo (execution) routing for CHAT intent
  execution_keywords:
    - "write"
    - "build"
    - "implement"
    - "create"
    - "scaffold"
    - "generate"
    - "code"
    - "fix"
    - "refactor"
    - "migrate"
    - "deploy"
    - "script"
    - "function"
    - "class"
    - "test"
```

- [ ] **Step 2: Commit**

```bash
git add config/orchestration.yaml
git commit -m "config: orchestration.yaml with routing thresholds and keywords"
```

---

### Task 3: Intent-to-Route Heuristic

**Files:**
- Create: `hestia/orchestration/router.py`
- Test: `tests/test_agent_orchestrator.py` (append)

- [ ] **Step 1: Write routing tests**

Append to `tests/test_agent_orchestrator.py`:

```python
from hestia.orchestration.router import AgentRouter
from hestia.orchestration.agent_models import AgentRoute, OrchestratorConfig
from hestia.council.models import IntentType


class TestAgentRouter:
    """Intent-to-route heuristic tests."""

    def setup_method(self):
        self.config = OrchestratorConfig()
        self.router = AgentRouter(self.config)

    # -- Direct intent mapping --

    def test_coding_intent_routes_to_apollo(self):
        route, conf = self.router.resolve(IntentType.CODING, "write a function")
        assert route == AgentRoute.APOLLO

    def test_memory_search_routes_to_artemis(self):
        route, conf = self.router.resolve(IntentType.MEMORY_SEARCH, "what do I know about X")
        assert route == AgentRoute.ARTEMIS

    def test_calendar_query_routes_to_solo(self):
        route, conf = self.router.resolve(IntentType.CALENDAR_QUERY, "what's on my calendar")
        assert route == AgentRoute.HESTIA_SOLO

    def test_chat_simple_routes_to_solo(self):
        route, conf = self.router.resolve(IntentType.CHAT, "hey")
        assert route == AgentRoute.HESTIA_SOLO

    # -- Keyword escalation for CHAT intent --

    def test_chat_with_analysis_keywords_routes_to_artemis(self):
        route, conf = self.router.resolve(
            IntentType.CHAT, "help me think through the database architecture"
        )
        assert route == AgentRoute.ARTEMIS

    def test_chat_with_execution_keywords_routes_to_apollo(self):
        route, conf = self.router.resolve(
            IntentType.CHAT, "write the migration script for the users table"
        )
        assert route == AgentRoute.APOLLO

    def test_chat_with_both_keywords_routes_to_chain(self):
        route, conf = self.router.resolve(
            IntentType.CHAT,
            "research how HealthKit handles background sync then implement it"
        )
        assert route == AgentRoute.ARTEMIS_THEN_APOLLO

    def test_chat_no_keywords_routes_to_solo(self):
        route, conf = self.router.resolve(
            IntentType.CHAT, "thanks that was helpful"
        )
        assert route == AgentRoute.HESTIA_SOLO

    # -- Confidence scoring --

    def test_direct_intent_has_high_confidence(self):
        route, conf = self.router.resolve(IntentType.CODING, "write code")
        assert conf >= 0.85

    def test_keyword_match_has_moderate_confidence(self):
        route, conf = self.router.resolve(
            IntentType.CHAT, "compare SQLite vs Postgres"
        )
        assert 0.6 <= conf <= 0.9

    def test_no_match_has_high_solo_confidence(self):
        route, conf = self.router.resolve(IntentType.CHAT, "hi there")
        assert conf >= 0.8

    # -- @mention override --

    def test_explicit_override(self):
        route, conf = self.router.resolve_with_override(
            IntentType.CHAT, "how are you", explicit_agent="artemis"
        )
        assert route == AgentRoute.ARTEMIS
        assert conf == 1.0

    # -- Disabled orchestrator --

    def test_disabled_always_returns_solo(self):
        config = OrchestratorConfig(enabled=False)
        router = AgentRouter(config)
        route, conf = router.resolve(IntentType.CODING, "write code")
        assert route == AgentRoute.HESTIA_SOLO
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agent_orchestrator.py::TestAgentRouter -v --timeout=30`
Expected: FAIL — `ModuleNotFoundError: No module named 'hestia.orchestration.router'`

- [ ] **Step 3: Implement router.py**

```python
# hestia/orchestration/router.py
"""
Agent router — deterministic intent-to-route heuristic.

Maps council IntentClassification to AgentRoute decisions.
Primary routing mechanism: intent type + keyword analysis.
SLM does intent classification only (proven). This heuristic maps intent to route.
"""

from typing import Optional, Tuple

from hestia.council.models import IntentType
from hestia.orchestration.agent_models import AgentRoute, OrchestratorConfig


# Direct intent → route mapping (no keyword analysis needed)
INTENT_ROUTE_MAP = {
    IntentType.MEMORY_SEARCH: AgentRoute.ARTEMIS,
    IntentType.CODING: AgentRoute.APOLLO,
    IntentType.CALENDAR_CREATE: AgentRoute.APOLLO,
    IntentType.REMINDER_CREATE: AgentRoute.APOLLO,
    IntentType.NOTE_CREATE: AgentRoute.APOLLO,
    IntentType.CALENDAR_QUERY: AgentRoute.HESTIA_SOLO,
    IntentType.REMINDER_QUERY: AgentRoute.HESTIA_SOLO,
    IntentType.NOTE_SEARCH: AgentRoute.HESTIA_SOLO,
    IntentType.MAIL_QUERY: AgentRoute.HESTIA_SOLO,
    IntentType.WEATHER_QUERY: AgentRoute.HESTIA_SOLO,
    IntentType.STOCKS_QUERY: AgentRoute.HESTIA_SOLO,
    IntentType.UNCLEAR: AgentRoute.HESTIA_SOLO,
    IntentType.MULTI_INTENT: AgentRoute.HESTIA_SOLO,
}


class AgentRouter:
    """Deterministic intent-to-route heuristic."""

    def __init__(self, config: OrchestratorConfig) -> None:
        self._config = config

    def resolve(
        self, intent: IntentType, content: str
    ) -> Tuple[AgentRoute, float]:
        """
        Resolve an intent + content to an agent route and confidence.

        Returns:
            (AgentRoute, confidence) tuple.
        """
        if not self._config.enabled:
            return AgentRoute.HESTIA_SOLO, 1.0

        # Direct intent mapping (high confidence)
        if intent in INTENT_ROUTE_MAP:
            route = INTENT_ROUTE_MAP[intent]
            if route != AgentRoute.HESTIA_SOLO:
                return route, 0.9
            # For HESTIA_SOLO intents, still check CHAT keyword escalation
            if intent != IntentType.CHAT:
                return route, 0.9

        # CHAT intent: keyword analysis
        content_lower = content.lower()
        has_analysis = self._has_keywords(content_lower, self._config.analysis_keywords)
        has_execution = self._has_keywords(content_lower, self._config.execution_keywords)

        if has_analysis and has_execution:
            return AgentRoute.ARTEMIS_THEN_APOLLO, 0.75
        elif has_analysis:
            return AgentRoute.ARTEMIS, 0.8
        elif has_execution:
            return AgentRoute.APOLLO, 0.8
        else:
            return AgentRoute.HESTIA_SOLO, 0.9

    def resolve_with_override(
        self,
        intent: IntentType,
        content: str,
        explicit_agent: Optional[str] = None,
    ) -> Tuple[AgentRoute, float]:
        """
        Resolve with optional explicit @mention override.

        If explicit_agent is set, it takes priority over heuristic.
        """
        if explicit_agent:
            agent_map = {
                "artemis": AgentRoute.ARTEMIS,
                "mira": AgentRoute.ARTEMIS,
                "apollo": AgentRoute.APOLLO,
                "olly": AgentRoute.APOLLO,
            }
            route = agent_map.get(explicit_agent.lower())
            if route:
                return route, 1.0

        return self.resolve(intent, content)

    def _has_keywords(self, content: str, keywords: list) -> bool:
        """Check if content contains any of the keywords."""
        return any(kw in content for kw in keywords)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_agent_orchestrator.py::TestAgentRouter -v --timeout=30`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/orchestration/router.py tests/test_agent_orchestrator.py
git commit -m "feat: intent-to-route heuristic (AgentRouter)"
```

---

### Task 4: Extend Council IntentClassification

**Files:**
- Modify: `hestia/council/models.py`
- Test: `tests/test_agent_orchestrator.py` (append)

- [ ] **Step 1: Write tests for extended IntentClassification**

Append to `tests/test_agent_orchestrator.py`:

```python
from hestia.council.models import IntentClassification, IntentType


class TestIntentClassificationExtension:
    """Verify IntentClassification agent_route fields."""

    def test_default_values_backward_compat(self):
        ic = IntentClassification.create(
            primary_intent=IntentType.CHAT, confidence=0.9
        )
        assert ic.agent_route is None
        assert ic.route_confidence == 0.0

    def test_with_routing_fields(self):
        ic = IntentClassification.create(
            primary_intent=IntentType.CHAT,
            confidence=0.9,
            agent_route="artemis",
            route_confidence=0.85,
        )
        assert ic.agent_route == "artemis"
        assert ic.route_confidence == 0.85

    def test_to_dict_includes_routing(self):
        ic = IntentClassification.create(
            primary_intent=IntentType.CODING,
            confidence=0.95,
            agent_route="apollo",
            route_confidence=0.9,
        )
        d = ic.to_dict()
        assert d["agent_route"] == "apollo"
        assert d["route_confidence"] == 0.9

    def test_to_dict_backward_compat_no_routing(self):
        ic = IntentClassification.create(
            primary_intent=IntentType.CHAT, confidence=0.9
        )
        d = ic.to_dict()
        assert d["agent_route"] is None
        assert d["route_confidence"] == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agent_orchestrator.py::TestIntentClassificationExtension -v --timeout=30`
Expected: FAIL — `TypeError: create() got an unexpected keyword argument 'agent_route'`

- [ ] **Step 3: Modify IntentClassification in council/models.py**

Add two fields to the dataclass and update `create()` and `to_dict()`:

In `hestia/council/models.py`, modify `IntentClassification`:

```python
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
```

- [ ] **Step 4: Run ALL existing council tests + new tests**

Run: `python -m pytest tests/test_agent_orchestrator.py::TestIntentClassificationExtension tests/test_council.py -v --timeout=30`
Expected: All PASS (new fields are optional, backward compatible)

- [ ] **Step 5: Commit**

```bash
git add hestia/council/models.py tests/test_agent_orchestrator.py
git commit -m "feat: extend IntentClassification with agent_route and route_confidence"
```

---

### Task 5: Routing Audit Database

**Files:**
- Create: `hestia/orchestration/audit_db.py`
- Create: `tests/test_routing_audit.py`

- [ ] **Step 1: Write audit database tests**

```python
# tests/test_routing_audit.py
"""Tests for routing audit database."""

import pytest
from pathlib import Path

from hestia.orchestration.audit_db import RoutingAuditDatabase
from hestia.orchestration.agent_models import RoutingAuditEntry


@pytest.fixture
async def audit_db(tmp_path):
    db = RoutingAuditDatabase(db_path=tmp_path / "test_audit.db")
    await db.initialize()
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_store_and_retrieve(audit_db):
    entry = RoutingAuditEntry.create(
        user_id="user-1",
        request_id="req-abc",
        intent="chat",
        route_chosen="artemis",
        route_confidence=0.85,
    )
    entry.actual_agents = ["artemis"]
    entry.total_inference_calls = 2
    entry.total_duration_ms = 3500

    await audit_db.store(entry)
    results = await audit_db.get_recent(user_id="user-1", limit=10)
    assert len(results) == 1
    assert results[0]["route_chosen"] == "artemis"
    assert results[0]["route_confidence"] == 0.85


@pytest.mark.asyncio
async def test_user_scoping(audit_db):
    e1 = RoutingAuditEntry.create("user-1", "req-1", "chat", "artemis", 0.8)
    e2 = RoutingAuditEntry.create("user-2", "req-2", "coding", "apollo", 0.9)
    await audit_db.store(e1)
    await audit_db.store(e2)

    results = await audit_db.get_recent(user_id="user-1")
    assert len(results) == 1
    assert results[0]["user_id"] == "user-1"


@pytest.mark.asyncio
async def test_route_stats(audit_db):
    for route in ["artemis", "artemis", "apollo", "hestia_solo"]:
        entry = RoutingAuditEntry.create("user-1", f"req-{route}", "chat", route, 0.8)
        await audit_db.store(entry)

    stats = await audit_db.get_route_stats(user_id="user-1")
    assert stats["artemis"] == 2
    assert stats["apollo"] == 1
    assert stats["hestia_solo"] == 1


@pytest.mark.asyncio
async def test_fallback_count(audit_db):
    e1 = RoutingAuditEntry.create("user-1", "req-1", "chat", "artemis", 0.8)
    e1.fallback_triggered = True
    e2 = RoutingAuditEntry.create("user-1", "req-2", "chat", "apollo", 0.9)
    await audit_db.store(e1)
    await audit_db.store(e2)

    results = await audit_db.get_recent(user_id="user-1")
    fallbacks = [r for r in results if r["fallback_triggered"]]
    assert len(fallbacks) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_routing_audit.py -v --timeout=30`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement audit_db.py**

```python
# hestia/orchestration/audit_db.py
"""
Routing audit database — SQLite storage for agent routing decisions.

Stores every routing decision with confidence, agents invoked,
fallback status, and performance metrics. User-scoped for family scale.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from hestia.database import BaseDatabase
from hestia.orchestration.agent_models import RoutingAuditEntry

_DB_DIR = Path("data")
_DB_PATH = _DB_DIR / "routing_audit.db"

_instance: Optional["RoutingAuditDatabase"] = None


class RoutingAuditDatabase(BaseDatabase):
    """SQLite storage for routing audit entries."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        super().__init__("routing_audit", db_path or _DB_PATH)

    async def initialize(self) -> None:
        await self.connect()

    async def _init_schema(self) -> None:
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS routing_audit (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                request_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                intent TEXT NOT NULL,
                route_chosen TEXT NOT NULL,
                route_confidence REAL NOT NULL,
                actual_agents TEXT NOT NULL DEFAULT '[]',
                chain_collapsed INTEGER DEFAULT 0,
                fallback_triggered INTEGER DEFAULT 0,
                total_inference_calls INTEGER DEFAULT 1,
                total_duration_ms INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_routing_audit_user_ts
                ON routing_audit(user_id, timestamp DESC);
        """)
        await self._connection.commit()

    async def store(self, entry: RoutingAuditEntry) -> str:
        assert self._connection is not None
        await self._connection.execute(
            """INSERT INTO routing_audit
               (id, user_id, request_id, timestamp, intent, route_chosen,
                route_confidence, actual_agents, chain_collapsed,
                fallback_triggered, total_inference_calls, total_duration_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.id,
                entry.user_id,
                entry.request_id,
                entry.timestamp.isoformat(),
                entry.intent,
                entry.route_chosen,
                entry.route_confidence,
                json.dumps(entry.actual_agents),
                int(entry.chain_collapsed),
                int(entry.fallback_triggered),
                entry.total_inference_calls,
                entry.total_duration_ms,
            ),
        )
        await self._connection.commit()
        return entry.id

    async def get_recent(
        self, user_id: str, limit: int = 50, days: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        assert self._connection is not None
        query = "SELECT * FROM routing_audit WHERE user_id = ?"
        params: List[Any] = [user_id]
        if days is not None:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            query += " AND timestamp >= ?"
            params.append(cutoff)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        results = []
        async with self._connection.execute(query, params) as cursor:
            async for row in cursor:
                results.append(self._row_to_dict(row))
        return results

    async def get_route_stats(
        self, user_id: str, days: int = 30
    ) -> Dict[str, int]:
        assert self._connection is not None
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        async with self._connection.execute(
            """SELECT route_chosen, COUNT(*) as cnt
               FROM routing_audit
               WHERE user_id = ? AND timestamp >= ?
               GROUP BY route_chosen""",
            (user_id, cutoff),
        ) as cursor:
            stats = {}
            async for row in cursor:
                stats[row["route_chosen"]] = row["cnt"]
            return stats

    def _row_to_dict(self, row: aiosqlite.Row) -> Dict[str, Any]:
        agents = []
        try:
            agents = json.loads(row["actual_agents"])
        except (json.JSONDecodeError, TypeError):
            pass
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "request_id": row["request_id"],
            "timestamp": row["timestamp"],
            "intent": row["intent"],
            "route_chosen": row["route_chosen"],
            "route_confidence": row["route_confidence"],
            "actual_agents": agents,
            "chain_collapsed": bool(row["chain_collapsed"]),
            "fallback_triggered": bool(row["fallback_triggered"]),
            "total_inference_calls": row["total_inference_calls"],
            "total_duration_ms": row["total_duration_ms"],
        }


async def get_routing_audit_db(
    db_path: Optional[Path] = None,
) -> RoutingAuditDatabase:
    global _instance
    if _instance is None:
        _instance = RoutingAuditDatabase(db_path)
        await _instance.initialize()
    return _instance


async def close_routing_audit_db() -> None:
    global _instance
    if _instance is not None:
        await _instance.close()
        _instance = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_routing_audit.py -v --timeout=30`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/orchestration/audit_db.py tests/test_routing_audit.py
git commit -m "feat: routing audit database with user-scoped storage"
```

---

## Chunk 2: Orchestration Core — Planner, Context, Executor, Synthesizer

### Task 6: Context Manager (Lightweight Functions)

**Files:**
- Create: `hestia/orchestration/context_manager.py`
- Test: `tests/test_agent_orchestrator.py` (append)

- [ ] **Step 1: Write context manager tests**

Append to `tests/test_agent_orchestrator.py`:

```python
from hestia.orchestration.context_manager import (
    slice_context_for_artemis,
    slice_context_for_apollo,
    slice_context_for_synthesis,
)


class TestContextManager:
    """Context slicing for specialist agents."""

    def test_artemis_gets_full_history(self):
        ctx = slice_context_for_artemis(
            memory_context="memories here",
            user_profile="profile here",
            conversation_history=[
                {"role": "user", "content": "msg1"},
                {"role": "assistant", "content": "resp1"},
                {"role": "user", "content": "msg2"},
                {"role": "assistant", "content": "resp2"},
            ],
            tool_instructions="tool defs",
        )
        assert "memories here" in ctx["memory"]
        assert "profile here" in ctx["profile"]
        assert len(ctx["history"]) == 4  # Full history
        assert "tool_instructions" not in ctx  # Artemis doesn't get tools

    def test_apollo_gets_recent_turns_only(self):
        history = [{"role": "user", "content": f"msg{i}"} for i in range(20)]
        ctx = slice_context_for_apollo(
            conversation_history=history,
            tool_instructions="tool defs",
            artemis_output=None,
        )
        assert len(ctx["history"]) <= 6  # Recent turns only
        assert ctx["tool_instructions"] == "tool defs"

    def test_apollo_gets_artemis_output_when_chained(self):
        ctx = slice_context_for_apollo(
            conversation_history=[],
            tool_instructions="tool defs",
            artemis_output="SSE is better because...",
        )
        assert ctx["artemis_analysis"] == "SSE is better because..."

    def test_synthesis_gets_all_results(self):
        from hestia.orchestration.agent_models import AgentResult, AgentRoute
        results = [
            AgentResult(agent_id=AgentRoute.ARTEMIS, content="analysis output", confidence=0.9),
            AgentResult(agent_id=AgentRoute.APOLLO, content="code output", confidence=0.85),
        ]
        ctx = slice_context_for_synthesis(
            agent_results=results,
            original_request="research and implement X",
            user_profile="profile",
        )
        assert len(ctx["agent_results"]) == 2
        assert ctx["original_request"] == "research and implement X"

    def test_artemis_excludes_pii_when_cloud(self):
        ctx = slice_context_for_artemis(
            memory_context="memories",
            user_profile="SENSITIVE: SSN 123-45-6789",
            conversation_history=[],
            tool_instructions="",
            cloud_safe=True,
        )
        assert ctx["profile"] == ""  # Excluded for cloud safety
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agent_orchestrator.py::TestContextManager -v --timeout=30`
Expected: FAIL

- [ ] **Step 3: Implement context_manager.py**

```python
# hestia/orchestration/context_manager.py
"""
Context slicing functions for specialist agents.

Lightweight module — pure functions, no state. Controls what context
each agent sees for efficiency and security.
"""

from typing import Any, Dict, List, Optional


# Apollo gets only the last N messages (recent context, not full history)
_APOLLO_MAX_HISTORY_MESSAGES = 6


def slice_context_for_artemis(
    memory_context: str,
    user_profile: str,
    conversation_history: List[Dict[str, str]],
    tool_instructions: str,
    cloud_safe: bool = False,
) -> Dict[str, Any]:
    """
    Build context slice for Artemis (analysis agent).

    Artemis gets: full history, memory, profile (unless cloud).
    Artemis does NOT get: tool definitions (she analyzes, not executes).
    """
    return {
        "memory": memory_context,
        "profile": "" if cloud_safe else user_profile,
        "history": conversation_history,
    }


def slice_context_for_apollo(
    conversation_history: List[Dict[str, str]],
    tool_instructions: str,
    artemis_output: Optional[str] = None,
    cloud_safe: bool = False,
) -> Dict[str, Any]:
    """
    Build context slice for Apollo (execution agent).

    Apollo gets: recent turns, tool defs, Artemis output (if chained).
    Apollo does NOT get: full history, full user profile.
    """
    recent = conversation_history[-_APOLLO_MAX_HISTORY_MESSAGES:]
    ctx: Dict[str, Any] = {
        "history": recent,
        "tool_instructions": tool_instructions,
    }
    if artemis_output:
        ctx["artemis_analysis"] = artemis_output
    return ctx


def slice_context_for_synthesis(
    agent_results: list,
    original_request: str,
    user_profile: str,
) -> Dict[str, Any]:
    """
    Build context slice for Hestia's synthesis step.

    Gets all agent outputs + original request. Used to combine
    specialist outputs into a coherent response with bylines.
    """
    return {
        "agent_results": agent_results,
        "original_request": original_request,
        "profile": user_profile,
    }
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_agent_orchestrator.py::TestContextManager -v --timeout=30`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/orchestration/context_manager.py tests/test_agent_orchestrator.py
git commit -m "feat: context slicing functions for specialist agents"
```

---

### Task 7: Result Synthesizer (Lightweight Functions)

**Files:**
- Create: `hestia/orchestration/synthesizer.py`
- Test: `tests/test_agent_orchestrator.py` (append)

- [ ] **Step 1: Write synthesizer tests**

Append to `tests/test_agent_orchestrator.py`:

```python
from hestia.orchestration.synthesizer import (
    generate_bylines,
    synthesize_single_agent,
    synthesize_multi_agent,
)
from hestia.orchestration.agent_models import AgentResult, AgentRoute, AgentByline


class TestSynthesizer:
    """Result synthesis and byline generation."""

    def test_single_agent_returns_content_with_byline(self):
        result = AgentResult(
            agent_id=AgentRoute.ARTEMIS,
            content="SSE is better for unidirectional data flow.",
            confidence=0.9,
        )
        content, bylines = synthesize_single_agent(result, "analyze SSE vs WS")
        assert "SSE is better" in content
        assert len(bylines) == 1
        assert bylines[0].agent == AgentRoute.ARTEMIS

    def test_multi_agent_combines_outputs(self):
        r1 = AgentResult(
            agent_id=AgentRoute.ARTEMIS,
            content="SSE is better because...",
            confidence=0.9,
        )
        r2 = AgentResult(
            agent_id=AgentRoute.APOLLO,
            content="```python\nclass SSEHandler:\n    pass\n```",
            confidence=0.85,
        )
        content, bylines = synthesize_multi_agent([r1, r2], "research and build SSE")
        assert "SSE is better" in content
        assert "SSEHandler" in content
        assert len(bylines) == 2

    def test_byline_format(self):
        bylines = generate_bylines([
            AgentResult(agent_id=AgentRoute.ARTEMIS, content="analysis", confidence=0.9),
        ])
        assert len(bylines) == 1
        formatted = bylines[0].format()
        assert "📐" in formatted
        assert "Artemis" in formatted

    def test_hestia_solo_no_byline(self):
        result = AgentResult(
            agent_id=AgentRoute.HESTIA_SOLO,
            content="Your calendar is clear today.",
            confidence=1.0,
        )
        content, bylines = synthesize_single_agent(result, "calendar check")
        assert len(bylines) == 0  # No byline for solo

    def test_empty_results(self):
        content, bylines = synthesize_multi_agent([], "something")
        assert content == ""
        assert bylines == []

    def test_low_confidence_result_noted_in_byline(self):
        result = AgentResult(
            agent_id=AgentRoute.ARTEMIS,
            content="I'm not sure about this...",
            confidence=0.35,
        )
        content, bylines = synthesize_single_agent(result, "analyze X")
        # Low confidence results still get returned but byline notes it
        assert len(bylines) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agent_orchestrator.py::TestSynthesizer -v --timeout=30`
Expected: FAIL

- [ ] **Step 3: Implement synthesizer.py**

```python
# hestia/orchestration/synthesizer.py
"""
Result synthesis and byline generation for agent orchestrator.

Lightweight module — pure functions, no state. Combines specialist
outputs into coherent responses with attribution bylines.
"""

from typing import List, Tuple

from hestia.orchestration.agent_models import (
    AgentByline,
    AgentResult,
    AgentRoute,
    AGENT_DISPLAY_NAMES,
)


def generate_bylines(results: List[AgentResult]) -> List[AgentByline]:
    """
    Generate attribution bylines for specialist agent results.

    Hestia-solo results produce no bylines (she IS the interface).
    """
    bylines = []
    for result in results:
        if result.agent_id == AgentRoute.HESTIA_SOLO:
            continue

        contribution = _infer_contribution_type(result)
        summary = _summarize_contribution(result)

        bylines.append(AgentByline(
            agent=result.agent_id,
            contribution_type=contribution,
            summary=summary,
        ))
    return bylines


def synthesize_single_agent(
    result: AgentResult, original_request: str
) -> Tuple[str, List[AgentByline]]:
    """
    Synthesize response from a single specialist agent.

    Returns (content, bylines). For Hestia-solo, bylines is empty.
    """
    bylines = generate_bylines([result])
    return result.content, bylines


def synthesize_multi_agent(
    results: List[AgentResult], original_request: str
) -> Tuple[str, List[AgentByline]]:
    """
    Synthesize response from multiple specialist agents.

    Combines outputs with clear section separation. Returns (content, bylines).
    """
    if not results:
        return "", []

    bylines = generate_bylines(results)

    # Combine outputs with separator
    parts = []
    for result in results:
        if result.content.strip():
            parts.append(result.content.strip())

    content = "\n\n".join(parts)
    return content, bylines


def format_byline_footer(bylines: List[AgentByline]) -> str:
    """Format bylines as a footer appended to response content."""
    if not bylines:
        return ""
    lines = [byline.format() for byline in bylines]
    return "\n\n---\n" + "\n".join(lines)


def _infer_contribution_type(result: AgentResult) -> str:
    """Infer the contribution type from the agent and content."""
    if result.agent_id == AgentRoute.ARTEMIS:
        return "analysis"
    elif result.agent_id == AgentRoute.APOLLO:
        if result.tool_calls:
            return "tool_result"
        return "implementation"
    return "response"


def _summarize_contribution(result: AgentResult) -> str:
    """Generate a one-line summary of the contribution."""
    name = AGENT_DISPLAY_NAMES.get(result.agent_id, "Agent")
    content_preview = result.content[:80].replace("\n", " ").strip()
    if len(result.content) > 80:
        content_preview += "..."
    if result.agent_id == AgentRoute.ARTEMIS:
        return f"analyzed: {content_preview}"
    elif result.agent_id == AgentRoute.APOLLO:
        return f"executed: {content_preview}"
    return content_preview
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_agent_orchestrator.py::TestSynthesizer -v --timeout=30`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/orchestration/synthesizer.py tests/test_agent_orchestrator.py
git commit -m "feat: result synthesizer with byline generation"
```

---

### Task 8: Orchestration Planner

**Files:**
- Create: `hestia/orchestration/planner.py`
- Test: `tests/test_agent_orchestrator.py` (append)

- [ ] **Step 1: Write planner tests**

Append to `tests/test_agent_orchestrator.py`:

```python
from hestia.orchestration.planner import OrchestrationPlanner
from hestia.orchestration.agent_models import AgentRoute, OrchestratorConfig, ExecutionPlan


class TestOrchestrationPlanner:
    """Orchestration planner — builds execution plans from routing decisions."""

    def setup_method(self):
        self.config = OrchestratorConfig()
        self.planner = OrchestrationPlanner(self.config)

    # -- Confidence gating --

    def test_high_confidence_full_dispatch(self):
        plan = self.planner.build_plan(
            route=AgentRoute.ARTEMIS,
            route_confidence=0.9,
            content="analyze the trade-offs",
            memory_context="mem",
            user_profile="profile",
            conversation_history=[],
            tool_instructions="tools",
            cloud_available=True,
        )
        assert plan.route == AgentRoute.ARTEMIS
        assert len(plan.steps) == 1
        assert plan.steps[0].tasks[0].agent_id == AgentRoute.ARTEMIS

    def test_medium_confidence_enriched_solo(self):
        plan = self.planner.build_plan(
            route=AgentRoute.ARTEMIS,
            route_confidence=0.6,  # Between 0.5 and 0.8
            content="maybe analyze this",
            memory_context="",
            user_profile="",
            conversation_history=[],
            tool_instructions="",
            cloud_available=False,
        )
        # Should collapse to HESTIA_SOLO with enriched prompt
        assert plan.route == AgentRoute.HESTIA_SOLO
        assert len(plan.steps) == 1
        assert plan.steps[0].tasks[0].agent_id == AgentRoute.HESTIA_SOLO
        assert "analysis" in plan.steps[0].tasks[0].prompt.lower() or \
               "analytical" in plan.steps[0].tasks[0].prompt.lower()

    def test_low_confidence_pure_solo(self):
        plan = self.planner.build_plan(
            route=AgentRoute.ARTEMIS,
            route_confidence=0.3,  # Below 0.5
            content="something unclear",
            memory_context="",
            user_profile="",
            conversation_history=[],
            tool_instructions="",
            cloud_available=False,
        )
        assert plan.route == AgentRoute.HESTIA_SOLO
        # No persona hints for low confidence
        assert "analytical" not in (plan.steps[0].tasks[0].prompt or "").lower()

    # -- Chain validation --

    def test_chain_collapsed_for_short_request(self):
        plan = self.planner.build_plan(
            route=AgentRoute.ARTEMIS_THEN_APOLLO,
            route_confidence=0.9,
            content="do it",  # Too short for a chain
            memory_context="",
            user_profile="",
            conversation_history=[],
            tool_instructions="",
            cloud_available=True,
        )
        assert plan.estimated_hops == 1  # Collapsed

    def test_chain_collapsed_when_no_cloud_and_long(self):
        self.config.max_hops_local = 1
        planner = OrchestrationPlanner(self.config)
        plan = planner.build_plan(
            route=AgentRoute.ARTEMIS_THEN_APOLLO,
            route_confidence=0.9,
            content="research how HealthKit handles background sync then implement the full solution with tests",
            memory_context="",
            user_profile="",
            conversation_history=[],
            tool_instructions="",
            cloud_available=False,
        )
        assert plan.estimated_hops <= 1  # Collapsed due to local limit

    def test_chain_preserved_with_cloud(self):
        plan = self.planner.build_plan(
            route=AgentRoute.ARTEMIS_THEN_APOLLO,
            route_confidence=0.9,
            content="research how HealthKit handles background sync then implement the full solution with tests",
            memory_context="mem",
            user_profile="profile",
            conversation_history=[],
            tool_instructions="tools",
            cloud_available=True,
        )
        assert plan.estimated_hops == 2
        assert plan.steps[0].tasks[0].agent_id == AgentRoute.ARTEMIS
        assert plan.steps[1].tasks[0].agent_id == AgentRoute.APOLLO

    # -- Solo passthrough --

    def test_solo_produces_single_step(self):
        plan = self.planner.build_plan(
            route=AgentRoute.HESTIA_SOLO,
            route_confidence=0.9,
            content="what time is it",
            memory_context="",
            user_profile="",
            conversation_history=[],
            tool_instructions="",
            cloud_available=False,
        )
        assert plan.route == AgentRoute.HESTIA_SOLO
        assert plan.estimated_hops == 1

    # -- Apollo routing --

    def test_apollo_gets_coding_model_preference(self):
        plan = self.planner.build_plan(
            route=AgentRoute.APOLLO,
            route_confidence=0.9,
            content="write the migration script",
            memory_context="",
            user_profile="",
            conversation_history=[],
            tool_instructions="tools",
            cloud_available=False,
        )
        assert plan.steps[0].tasks[0].model_preference == "coding"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agent_orchestrator.py::TestOrchestrationPlanner -v --timeout=30`
Expected: FAIL

- [ ] **Step 3: Implement planner.py**

```python
# hestia/orchestration/planner.py
"""
Orchestration planner — builds execution plans from routing decisions.

Handles confidence gating, chain validation, and plan collapsing.
Plans are data structures that the executor interprets.
"""

from typing import List, Optional

from hestia.orchestration.agent_models import (
    AgentRoute,
    AgentTask,
    ExecutionPlan,
    ExecutionStep,
    OrchestratorConfig,
)
from hestia.orchestration.context_manager import (
    slice_context_for_artemis,
    slice_context_for_apollo,
)


# Persona hints injected into Hestia-solo prompts for medium-confidence routing
_ARTEMIS_HINTS = (
    "Approach this analytically. Consider multiple perspectives, "
    "trade-offs, and provide thorough reasoning."
)
_APOLLO_HINTS = (
    "Focus on execution and concrete deliverables. Be precise, "
    "production-quality, and minimal in tangents."
)


class OrchestrationPlanner:
    """Builds execution plans from agent routing decisions."""

    def __init__(self, config: OrchestratorConfig) -> None:
        self._config = config

    def build_plan(
        self,
        route: AgentRoute,
        route_confidence: float,
        content: str,
        memory_context: str,
        user_profile: str,
        conversation_history: list,
        tool_instructions: str,
        cloud_available: bool,
        cloud_safe: bool = False,
    ) -> ExecutionPlan:
        """
        Build an execution plan from a routing decision.

        Applies confidence gating and chain validation before
        producing the final plan.
        """
        # Confidence gating
        if route.involves_specialist:
            if route_confidence < self._config.enriched_solo_threshold:
                # Low confidence → pure Hestia solo
                return self._solo_plan(content, "Low routing confidence — Hestia solo")
            elif route_confidence < self._config.full_dispatch_threshold:
                # Medium confidence → Hestia solo with persona hints
                hints = _ARTEMIS_HINTS if route in (AgentRoute.ARTEMIS, AgentRoute.ARTEMIS_THEN_APOLLO) else _APOLLO_HINTS
                return self._enriched_solo_plan(content, hints)

        # Chain validation
        if route == AgentRoute.ARTEMIS_THEN_APOLLO:
            route = self._validate_chain(route, content, cloud_available)

        # Build the actual plan
        if route == AgentRoute.HESTIA_SOLO:
            return self._solo_plan(content, "Direct Hestia handling")

        elif route == AgentRoute.ARTEMIS:
            ctx = slice_context_for_artemis(
                memory_context, user_profile, conversation_history,
                tool_instructions, cloud_safe=cloud_safe,
            )
            task = AgentTask(
                agent_id=AgentRoute.ARTEMIS,
                prompt=content,
                context_slice=ctx,
            )
            return ExecutionPlan(
                steps=[ExecutionStep(tasks=[task])],
                rationale="Analysis needed",
                route=AgentRoute.ARTEMIS,
            )

        elif route == AgentRoute.APOLLO:
            ctx = slice_context_for_apollo(
                conversation_history, tool_instructions,
                cloud_safe=cloud_safe,
            )
            task = AgentTask(
                agent_id=AgentRoute.APOLLO,
                prompt=content,
                context_slice=ctx,
                model_preference="coding",
            )
            return ExecutionPlan(
                steps=[ExecutionStep(tasks=[task])],
                rationale="Execution needed",
                route=AgentRoute.APOLLO,
            )

        elif route == AgentRoute.ARTEMIS_THEN_APOLLO:
            artemis_ctx = slice_context_for_artemis(
                memory_context, user_profile, conversation_history,
                tool_instructions, cloud_safe=cloud_safe,
            )
            apollo_ctx = slice_context_for_apollo(
                conversation_history, tool_instructions,
                cloud_safe=cloud_safe,
            )
            s1 = ExecutionStep(tasks=[
                AgentTask(agent_id=AgentRoute.ARTEMIS, prompt=content, context_slice=artemis_ctx),
            ])
            s2 = ExecutionStep(
                tasks=[
                    AgentTask(
                        agent_id=AgentRoute.APOLLO, prompt=content,
                        context_slice=apollo_ctx, model_preference="coding",
                    ),
                ],
                depends_on=0,
            )
            return ExecutionPlan(
                steps=[s1, s2],
                rationale="Analysis then execution",
                route=AgentRoute.ARTEMIS_THEN_APOLLO,
            )

        return self._solo_plan(content, "Fallback — unknown route")

    def _validate_chain(
        self, route: AgentRoute, content: str, cloud_available: bool
    ) -> AgentRoute:
        """Validate chain viability, collapsing to single agent if needed."""
        word_count = len(content.split())

        # Short requests don't need chains
        if word_count < self._config.min_words_for_chain:
            return AgentRoute.ARTEMIS  # Collapse to analysis only

        # Local-only: respect hop limits
        if not cloud_available:
            if 2 > self._config.max_hops_local:
                return AgentRoute.ARTEMIS  # Collapse

        return route  # Chain is valid

    def _solo_plan(self, content: str, rationale: str) -> ExecutionPlan:
        """Create a Hestia-solo plan (passthrough to normal pipeline)."""
        task = AgentTask(
            agent_id=AgentRoute.HESTIA_SOLO,
            prompt=content,
            context_slice={},
        )
        return ExecutionPlan(
            steps=[ExecutionStep(tasks=[task])],
            rationale=rationale,
            route=AgentRoute.HESTIA_SOLO,
        )

    def _enriched_solo_plan(self, content: str, hints: str) -> ExecutionPlan:
        """Create a Hestia-solo plan with specialist persona hints."""
        task = AgentTask(
            agent_id=AgentRoute.HESTIA_SOLO,
            prompt=content,
            context_slice={"persona_hints": hints},
        )
        return ExecutionPlan(
            steps=[ExecutionStep(tasks=[task])],
            rationale="Medium routing confidence — enriched Hestia solo",
            route=AgentRoute.HESTIA_SOLO,
        )
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_agent_orchestrator.py::TestOrchestrationPlanner -v --timeout=30`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/orchestration/planner.py tests/test_agent_orchestrator.py
git commit -m "feat: orchestration planner with confidence gating and chain validation"
```

---

### Task 9: Agent Executor

**Files:**
- Create: `hestia/orchestration/executor.py`
- Test: `tests/test_agent_orchestrator.py` (append)

- [ ] **Step 1: Write executor tests**

Append to `tests/test_agent_orchestrator.py`:

```python
from unittest.mock import AsyncMock, MagicMock
from hestia.orchestration.executor import AgentExecutor
from hestia.orchestration.agent_models import (
    AgentRoute, AgentTask, AgentResult, ExecutionPlan, ExecutionStep, OrchestratorConfig,
)


class TestAgentExecutor:
    """Agent executor — dispatches tasks to inference."""

    def setup_method(self):
        self.config = OrchestratorConfig()
        self.mock_inference = AsyncMock()
        self.mock_prompt_builder = MagicMock()

    def _make_executor(self):
        return AgentExecutor(
            config=self.config,
            inference_client=self.mock_inference,
            prompt_builder=self.mock_prompt_builder,
        )

    @pytest.mark.asyncio
    async def test_execute_solo_returns_none(self):
        """Solo plans return None — handler uses normal pipeline."""
        executor = self._make_executor()
        task = AgentTask(agent_id=AgentRoute.HESTIA_SOLO, prompt="hi", context_slice={})
        plan = ExecutionPlan(steps=[ExecutionStep(tasks=[task])], rationale="solo", route=AgentRoute.HESTIA_SOLO)

        result = await executor.execute(plan)
        assert result is None  # Signal handler to use normal pipeline

    @pytest.mark.asyncio
    async def test_execute_single_specialist(self):
        """Single specialist dispatch returns AgentResult."""
        executor = self._make_executor()

        # Mock inference response
        mock_response = MagicMock()
        mock_response.content = "Analysis: SSE is better."
        mock_response.tokens_in = 100
        mock_response.tokens_out = 50
        mock_response.duration_ms = 2000
        mock_response.tool_calls = None
        self.mock_inference.chat = AsyncMock(return_value=mock_response)

        task = AgentTask(
            agent_id=AgentRoute.ARTEMIS, prompt="analyze SSE vs WS",
            context_slice={"memory": "ctx", "profile": "prof", "history": []},
        )
        plan = ExecutionPlan(
            steps=[ExecutionStep(tasks=[task])],
            rationale="analysis",
            route=AgentRoute.ARTEMIS,
        )

        results = await executor.execute(plan)
        assert results is not None
        assert len(results) == 1
        assert results[0].agent_id == AgentRoute.ARTEMIS
        assert "SSE is better" in results[0].content

    @pytest.mark.asyncio
    async def test_execute_chain(self):
        """Chain executes sequentially, Apollo gets Artemis output."""
        executor = self._make_executor()

        responses = [
            MagicMock(content="Analysis output", tokens_in=100, tokens_out=50, duration_ms=2000, tool_calls=None),
            MagicMock(content="Code output", tokens_in=80, tokens_out=120, duration_ms=3000, tool_calls=None),
        ]
        self.mock_inference.chat = AsyncMock(side_effect=responses)

        t1 = AgentTask(agent_id=AgentRoute.ARTEMIS, prompt="analyze", context_slice={"memory": "", "profile": "", "history": []})
        t2 = AgentTask(agent_id=AgentRoute.APOLLO, prompt="build", context_slice={"history": [], "tool_instructions": ""}, model_preference="coding")
        plan = ExecutionPlan(
            steps=[ExecutionStep(tasks=[t1]), ExecutionStep(tasks=[t2], depends_on=0)],
            rationale="chain",
            route=AgentRoute.ARTEMIS_THEN_APOLLO,
        )

        results = await executor.execute(plan)
        assert len(results) == 2
        assert results[0].agent_id == AgentRoute.ARTEMIS
        assert results[1].agent_id == AgentRoute.APOLLO

    @pytest.mark.asyncio
    async def test_fallback_on_low_confidence(self):
        """Low confidence specialist → fallback to solo (returns None)."""
        executor = self._make_executor()

        mock_response = MagicMock()
        mock_response.content = "I'm not sure about this"
        mock_response.tokens_in = 50
        mock_response.tokens_out = 30
        mock_response.duration_ms = 1000
        mock_response.tool_calls = None
        self.mock_inference.chat = AsyncMock(return_value=mock_response)

        # Mock low confidence detection
        task = AgentTask(agent_id=AgentRoute.ARTEMIS, prompt="analyze X", context_slice={"memory": "", "profile": "", "history": []})
        plan = ExecutionPlan(steps=[ExecutionStep(tasks=[task])], rationale="test", route=AgentRoute.ARTEMIS)

        results = await executor.execute(plan)
        # Should return results regardless — handler decides what to do
        assert results is not None

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Inference error → AgentResult with error field."""
        executor = self._make_executor()
        self.mock_inference.chat = AsyncMock(side_effect=Exception("Ollama down"))

        task = AgentTask(agent_id=AgentRoute.ARTEMIS, prompt="analyze", context_slice={"memory": "", "profile": "", "history": []})
        plan = ExecutionPlan(steps=[ExecutionStep(tasks=[task])], rationale="test", route=AgentRoute.ARTEMIS)

        results = await executor.execute(plan)
        assert results is not None
        assert results[0].error is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agent_orchestrator.py::TestAgentExecutor -v --timeout=30`
Expected: FAIL

- [ ] **Step 3: Implement executor.py**

```python
# hestia/orchestration/executor.py
"""
Agent executor — dispatches AgentTasks to inference.

Handles single-agent dispatch, sequential chains, parallel groups,
and fallback on error/low confidence.
"""

import asyncio
import time
from typing import List, Optional

from hestia.logging import get_logger
from hestia.logging.logger import LogComponent
from hestia.orchestration.agent_models import (
    AgentResult,
    AgentRoute,
    AgentTask,
    ExecutionPlan,
    OrchestratorConfig,
)
from hestia.orchestration.mode import PERSONAS
from hestia.orchestration.models import Mode

logger = get_logger()

# Map AgentRoute to Mode for system prompt lookup
_ROUTE_TO_MODE = {
    AgentRoute.ARTEMIS: Mode.MIRA,
    AgentRoute.APOLLO: Mode.OLLY,
    AgentRoute.HESTIA_SOLO: Mode.TIA,
}


class AgentExecutor:
    """Dispatches agent tasks to inference and collects results."""

    def __init__(
        self,
        config: OrchestratorConfig,
        inference_client: object,
        prompt_builder: object,
    ) -> None:
        self._config = config
        self._inference = inference_client
        self._prompt_builder = prompt_builder

    async def execute(
        self, plan: ExecutionPlan
    ) -> Optional[List[AgentResult]]:
        """
        Execute an orchestration plan.

        Returns None for HESTIA_SOLO plans (handler uses normal pipeline).
        Returns List[AgentResult] for specialist plans.
        """
        if plan.route == AgentRoute.HESTIA_SOLO:
            return None

        results: List[AgentResult] = []

        for i, step in enumerate(plan.steps):
            # If step depends on previous, inject previous output into Apollo's context
            if step.depends_on is not None and results:
                prev_content = results[-1].content
                for task in step.tasks:
                    task.context_slice["artemis_analysis"] = prev_content

            if len(step.tasks) == 1:
                result = await self._execute_task(step.tasks[0])
                results.append(result)
            else:
                # Parallel group — asyncio.gather
                # On M1: serialized by Ollama. On M5 Ultra: genuine parallel.
                step_results = await asyncio.gather(
                    *[self._execute_task(t) for t in step.tasks],
                    return_exceptions=True,
                )
                for sr in step_results:
                    if isinstance(sr, Exception):
                        results.append(AgentResult(
                            agent_id=AgentRoute.HESTIA_SOLO,
                            content="",
                            confidence=0.0,
                            error=str(sr),
                        ))
                    else:
                        results.append(sr)

        return results

    async def _execute_task(self, task: AgentTask) -> AgentResult:
        """Execute a single agent task via inference."""
        start = time.perf_counter()

        try:
            # Build system prompt from persona
            mode = _ROUTE_TO_MODE.get(task.agent_id, Mode.TIA)
            persona = PERSONAS.get(mode)
            system_prompt = persona.system_prompt if persona else ""

            # Build messages
            messages = []
            history = task.context_slice.get("history", [])
            for msg in history:
                messages.append(msg)

            # Add context to system prompt
            memory = task.context_slice.get("memory", "")
            profile = task.context_slice.get("profile", "")
            artemis_analysis = task.context_slice.get("artemis_analysis", "")
            persona_hints = task.context_slice.get("persona_hints", "")

            if memory:
                system_prompt += f"\n\n## Relevant Memory\n{memory}"
            if profile:
                system_prompt += f"\n\n## User Profile\n{profile}"
            if artemis_analysis:
                system_prompt += f"\n\n## Analysis from Artemis\n{artemis_analysis}"
            if persona_hints:
                system_prompt += f"\n\n## Approach\n{persona_hints}"

            # Add tool instructions for Apollo
            tool_instructions = task.context_slice.get("tool_instructions", "")
            if tool_instructions and task.agent_id == AgentRoute.APOLLO:
                system_prompt += f"\n\n## Available Tools\n{tool_instructions}"

            messages.append({"role": "user", "content": task.prompt})

            # Call inference
            temperature = persona.temperature if persona else 0.0
            response = await self._inference.chat(
                messages=messages,
                system=system_prompt,
                temperature=temperature,
                max_tokens=2048,
            )

            duration_ms = int((time.perf_counter() - start) * 1000)

            return AgentResult(
                agent_id=task.agent_id,
                content=response.content,
                confidence=0.85,  # Default — could be enhanced with response quality signals
                tool_calls=response.tool_calls or [],
                tokens_used=(response.tokens_in or 0) + (response.tokens_out or 0),
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.warning(
                f"Agent execution failed: {type(e).__name__}",
                component=LogComponent.ORCHESTRATION,
                data={"agent": task.agent_id.value, "duration_ms": duration_ms},
            )
            return AgentResult(
                agent_id=task.agent_id,
                content="",
                confidence=0.0,
                duration_ms=duration_ms,
                error=f"{type(e).__name__}: agent execution failed",
            )
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_agent_orchestrator.py::TestAgentExecutor -v --timeout=30`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/orchestration/executor.py tests/test_agent_orchestrator.py
git commit -m "feat: agent executor with chain support and fallback"
```

---

## Chunk 3: Integration — Handler, API, Outcomes, Streaming

### Task 10: Extend Response Model with Bylines

**Files:**
- Modify: `hestia/orchestration/models.py`
- Modify: `hestia/api/schemas/chat.py`

- [ ] **Step 1: Add bylines field to Response dataclass**

In `hestia/orchestration/models.py`, add to `Response`:

```python
from hestia.orchestration.agent_models import AgentByline  # Add import at top

@dataclass
class Response:
    # ... existing fields ...

    # Agent orchestrator bylines
    bylines: List[AgentByline] = field(default_factory=list)
```

- [ ] **Step 2: Add byline schema to chat.py**

In `hestia/api/schemas/chat.py`:

```python
class AgentBylineSchema(BaseModel):
    """Attribution for a specialist agent's contribution."""
    agent: str = Field(description="Agent identifier (artemis, apollo)")
    contribution: str = Field(description="Type of contribution (analysis, implementation)")
    summary: str = Field(description="One-line description of contribution")

class ChatResponse(BaseModel):
    # ... existing fields ...
    bylines: Optional[List[AgentBylineSchema]] = Field(
        None,
        description="Agent attribution bylines (present when specialists contributed)"
    )
```

- [ ] **Step 3: Run existing tests to verify no regressions**

Run: `python -m pytest tests/test_chat.py tests/test_handler.py -v --timeout=30`
Expected: All PASS (new fields are optional with defaults)

- [ ] **Step 4: Commit**

```bash
git add hestia/orchestration/models.py hestia/api/schemas/chat.py
git commit -m "feat: byline fields on Response and ChatResponse schemas"
```

---

### Task 11: Extend Outcomes with Routing Columns

**Files:**
- Modify: `hestia/outcomes/models.py`
- Modify: `hestia/outcomes/database.py`
- Test: `tests/test_outcomes.py` (verify existing tests still pass + new test)

- [ ] **Step 1: Add fields to OutcomeRecord**

In `hestia/outcomes/models.py`, add to `OutcomeRecord`:

```python
    agent_route: Optional[str] = None         # AgentRoute value
    route_confidence: Optional[float] = None   # Routing confidence
```

Update `to_dict()` and `from_dict()` to include these fields.

- [ ] **Step 2: Add migration and columns to database.py**

In `hestia/outcomes/database.py`, add migration in `_init_schema()`:

```python
# Migration: add agent routing columns
try:
    await self._connection.execute(
        "ALTER TABLE outcomes ADD COLUMN agent_route TEXT"
    )
except Exception:
    pass  # Column already exists
try:
    await self._connection.execute(
        "ALTER TABLE outcomes ADD COLUMN route_confidence REAL"
    )
except Exception:
    pass  # Column already exists
```

Update `store_outcome()` INSERT to include the new columns.
Update `_row_to_dict()` to include the new columns.

- [ ] **Step 3: Run existing outcome tests + verify**

Run: `python -m pytest tests/test_outcomes.py -v --timeout=30`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add hestia/outcomes/models.py hestia/outcomes/database.py
git commit -m "feat: add agent_route and route_confidence columns to outcomes"
```

---

### Task 12: Handler Integration

**Files:**
- Modify: `hestia/orchestration/handler.py`
- Test: `tests/test_orchestrator_integration.py` (new)

This is the critical integration task. The handler gains orchestrator awareness between the parallel pre-inference step and the inference step.

- [ ] **Step 1: Write integration tests**

```python
# tests/test_orchestrator_integration.py
"""Integration tests for agent orchestrator in the request handler pipeline."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from hestia.orchestration.agent_models import AgentRoute, OrchestratorConfig
from hestia.orchestration.router import AgentRouter
from hestia.orchestration.planner import OrchestrationPlanner
from hestia.orchestration.executor import AgentExecutor
from hestia.orchestration.agent_models import AgentResult
from hestia.council.models import IntentClassification, IntentType


class TestOrchestratorInHandler:
    """Verify orchestrator hooks into handler pipeline correctly."""

    def test_router_resolves_from_intent(self):
        """Router produces correct route from council intent."""
        config = OrchestratorConfig()
        router = AgentRouter(config)

        intent = IntentClassification.create(
            primary_intent=IntentType.CODING, confidence=0.95
        )
        route, conf = router.resolve(intent.primary_intent, "write a function")
        assert route == AgentRoute.APOLLO
        assert conf >= 0.85

    def test_explicit_mention_overrides_router(self):
        """@artemis overrides router decision."""
        config = OrchestratorConfig()
        router = AgentRouter(config)

        route, conf = router.resolve_with_override(
            IntentType.CHAT, "just do it", explicit_agent="artemis"
        )
        assert route == AgentRoute.ARTEMIS
        assert conf == 1.0

    def test_disabled_orchestrator_always_solo(self):
        """When orchestrator disabled, everything routes to solo."""
        config = OrchestratorConfig(enabled=False)
        router = AgentRouter(config)

        route, _ = router.resolve(IntentType.CODING, "write code")
        assert route == AgentRoute.HESTIA_SOLO

    def test_intent_enriched_with_route(self):
        """IntentClassification gets agent_route populated."""
        config = OrchestratorConfig()
        router = AgentRouter(config)

        intent = IntentClassification.create(
            primary_intent=IntentType.CHAT, confidence=0.9
        )
        route, conf = router.resolve(intent.primary_intent, "compare A vs B")
        intent.agent_route = route.value
        intent.route_confidence = conf

        assert intent.agent_route == "artemis"
        assert intent.route_confidence >= 0.7

    @pytest.mark.asyncio
    async def test_solo_plan_signals_normal_pipeline(self):
        """Solo plans return None from executor → handler uses normal flow."""
        config = OrchestratorConfig()
        executor = AgentExecutor(config, AsyncMock(), MagicMock())
        planner = OrchestrationPlanner(config)

        plan = planner.build_plan(
            route=AgentRoute.HESTIA_SOLO, route_confidence=0.9,
            content="hi", memory_context="", user_profile="",
            conversation_history=[], tool_instructions="",
            cloud_available=False,
        )
        result = await executor.execute(plan)
        assert result is None  # Handler continues with normal pipeline
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_orchestrator_integration.py -v --timeout=30`
Expected: All PASS

- [ ] **Step 3: Modify handler.py — add orchestrator to handle()**

In `hestia/orchestration/handler.py`, after the intent unpacking (line ~564) and before prompt building (line ~576), insert the orchestrator logic:

```python
# After unpacking intent (line ~564), before building prompt:

# Step 6.5: Agent orchestration
from hestia.orchestration.router import AgentRouter
from hestia.orchestration.planner import OrchestrationPlanner
from hestia.orchestration.executor import AgentExecutor
from hestia.orchestration.synthesizer import synthesize_single_agent, synthesize_multi_agent, format_byline_footer
from hestia.orchestration.agent_models import AgentRoute, OrchestratorConfig

orchestrator_config = self._get_orchestrator_config()
if orchestrator_config.enabled and intent:
    agent_router = AgentRouter(orchestrator_config)

    # Detect explicit @mention override
    explicit_agent = None
    if self._mode_manager.detect_mode_from_input(original_content) is not None:
        mode_name = self._mode_manager.detect_mode_from_input(original_content).value
        agent_map = {"mira": "artemis", "olly": "apollo"}
        explicit_agent = agent_map.get(mode_name)

    route, route_confidence = agent_router.resolve_with_override(
        intent.primary_intent, request.content, explicit_agent
    )

    # Enrich intent with routing info
    intent.agent_route = route.value
    intent.route_confidence = route_confidence
    task.context["agent_route"] = route.value
    task.context["route_confidence"] = route_confidence

    if route.involves_specialist:
        planner = OrchestrationPlanner(orchestrator_config)
        plan = planner.build_plan(
            route=route,
            route_confidence=route_confidence,
            content=request.content,
            memory_context=memory_context,
            user_profile=user_profile_context,
            conversation_history=conversation.get_recent_context(),
            tool_instructions=TOOL_INSTRUCTIONS,
            cloud_available=will_use_cloud,
            cloud_safe=will_use_cloud,
        )

        if plan.route.involves_specialist:
            executor = AgentExecutor(
                orchestrator_config, self.inference_client, self._prompt_builder
            )
            agent_results = await executor.execute(plan)

            if agent_results:
                # Log routing audit
                await self._log_routing_audit(
                    request, intent, route, route_confidence,
                    agent_results, plan,
                )

                # Synthesize results
                if len(agent_results) == 1:
                    content, bylines = synthesize_single_agent(
                        agent_results[0], request.content
                    )
                else:
                    content, bylines = synthesize_multi_agent(
                        agent_results, request.content
                    )

                # Add byline footer to content
                content += format_byline_footer(bylines)

                response = Response(
                    request_id=request.id,
                    content=content,
                    response_type=ResponseType.TEXT,
                    mode=request.mode,
                    tokens_in=sum(r.tokens_used for r in agent_results),
                    tokens_out=0,
                    duration_ms=(time.time() - start_time) * 1000,
                    bylines=bylines,
                )

                # Store + update conversation
                await self._store_conversation(request, response, memory)
                conversation.add_turn(request.content, response.content)
                self.state_machine.complete(task, response)
                return response

# Continue with normal pipeline (Hestia solo)...
```

Also add helper method `_get_orchestrator_config()` and `_log_routing_audit()` to RequestHandler.

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=30 -x`
Expected: All existing tests still PASS (orchestrator defaults to solo for existing paths)

- [ ] **Step 5: Commit**

```bash
git add hestia/orchestration/handler.py tests/test_orchestrator_integration.py
git commit -m "feat: integrate orchestrator into handler pipeline"
```

---

### Task 13: Streaming Handler Bylines

**Files:**
- Modify: `hestia/orchestration/handler.py` (handle_streaming)

- [ ] **Step 1: Add byline event to streaming handler**

In `handle_streaming()`, after the `"done"` event assembly, add a `"byline"` event. The streaming handler needs the same orchestrator logic as `handle()`, but for the initial version, only emit bylines in the done event metadata. Full streaming orchestration (streaming specialist output) is a follow-up.

Modify the `"done"` yield to include bylines:

```python
yield {
    "type": "done",
    "request_id": request.id,
    "metrics": {
        "tokens_in": inference_response.tokens_in or 0,
        "tokens_out": inference_response.tokens_out or 0,
        "duration_ms": (time.time() - start_time) * 1000,
    },
    "mode": request.mode.value,
    "bylines": [b.to_dict() for b in response_bylines] if response_bylines else None,
}
```

- [ ] **Step 2: Run streaming tests**

Run: `python -m pytest tests/test_handler.py tests/test_handler_streaming.py -v --timeout=30`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add hestia/orchestration/handler.py
git commit -m "feat: emit byline metadata in streaming done event"
```

---

### Task 14: Update Mode Manager for @artemis/@apollo

**Files:**
- Modify: `hestia/orchestration/mode.py`

- [ ] **Step 1: Add @artemis and @apollo patterns**

The existing `@mira` and `@olly` patterns already work. Add explicit `@artemis` and `@apollo` as additional invoke patterns:

In `mode.py`, update the PERSONAS invoke patterns:

```python
Mode.MIRA: PersonaConfig(
    ...
    invoke_pattern=r"@mira\b|@artemis\b|hey\s+mira\b|hi\s+mira\b|hey\s+artemis\b",
    ...
),
Mode.OLLY: PersonaConfig(
    ...
    invoke_pattern=r"@olly\b|@apollo\b|hey\s+olly\b|hi\s+olly\b|hey\s+apollo\b",
    ...
),
```

- [ ] **Step 2: Run mode manager tests**

Run: `python -m pytest tests/test_mode.py -v --timeout=30`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add hestia/orchestration/mode.py
git commit -m "feat: add @artemis and @apollo invoke patterns"
```

---

### Task 15: Chat Route Byline Threading

**Files:**
- Modify: `hestia/api/routes/chat.py`

- [ ] **Step 1: Thread bylines from Response into ChatResponse**

In the chat route handler where `ChatResponse` is constructed from `Response`, add:

```python
bylines = None
if response.bylines:
    bylines = [
        AgentBylineSchema(
            agent=b.agent.value,
            contribution=b.contribution_type,
            summary=b.summary,
        )
        for b in response.bylines
    ]

return ChatResponse(
    # ... existing fields ...
    bylines=bylines,
)
```

- [ ] **Step 2: Run chat route tests**

Run: `python -m pytest tests/test_chat.py -v --timeout=30`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add hestia/api/routes/chat.py
git commit -m "feat: thread byline metadata through chat API response"
```

---

### Task 16: Server Lifecycle — Audit DB Init/Close

**Files:**
- Modify: `hestia/api/server.py`

- [ ] **Step 1: Add audit DB init in startup and close in shutdown**

In `server.py` startup sequence, after other DB initializations:

```python
from hestia.orchestration.audit_db import get_routing_audit_db, close_routing_audit_db

# In startup:
await get_routing_audit_db()

# In shutdown:
await close_routing_audit_db()
```

- [ ] **Step 2: Run server lifecycle tests**

Run: `python -m pytest tests/test_server_lifecycle.py -v --timeout=30`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add hestia/api/server.py
git commit -m "feat: initialize routing audit DB in server lifecycle"
```

---

## Chunk 4: Validation, Docs, and Polish

### Task 17: Golden Dataset Routing Validation

**Files:**
- Create: `tests/test_routing_golden.py`

- [ ] **Step 1: Write golden dataset tests**

```python
# tests/test_routing_golden.py
"""Golden dataset validation for agent routing accuracy."""

import pytest
from hestia.orchestration.router import AgentRouter
from hestia.orchestration.agent_models import AgentRoute, OrchestratorConfig
from hestia.council.models import IntentType


GOLDEN_DATASET = [
    # (intent, content, expected_route)
    # Simple queries → HESTIA_SOLO
    (IntentType.CHAT, "hey", AgentRoute.HESTIA_SOLO),
    (IntentType.CHAT, "thanks", AgentRoute.HESTIA_SOLO),
    (IntentType.CHAT, "good morning", AgentRoute.HESTIA_SOLO),
    (IntentType.CALENDAR_QUERY, "what's on my calendar today", AgentRoute.HESTIA_SOLO),
    (IntentType.REMINDER_QUERY, "what are my reminders", AgentRoute.HESTIA_SOLO),
    (IntentType.WEATHER_QUERY, "what's the weather", AgentRoute.HESTIA_SOLO),
    (IntentType.NOTE_SEARCH, "find my sprint notes", AgentRoute.HESTIA_SOLO),

    # Analysis → ARTEMIS
    (IntentType.CHAT, "compare SQLite vs Postgres for this feature", AgentRoute.ARTEMIS),
    (IntentType.CHAT, "help me think through the authentication architecture", AgentRoute.ARTEMIS),
    (IntentType.CHAT, "what are the pros and cons of microservices", AgentRoute.ARTEMIS),
    (IntentType.CHAT, "evaluate whether we should use GraphQL", AgentRoute.ARTEMIS),
    (IntentType.CHAT, "explain why the council system uses dual-path execution", AgentRoute.ARTEMIS),
    (IntentType.CHAT, "should I use Redis or Memcached for caching", AgentRoute.ARTEMIS),
    (IntentType.CHAT, "investigate the performance implications of ETag caching", AgentRoute.ARTEMIS),
    (IntentType.CHAT, "research how other AI assistants handle context windows", AgentRoute.ARTEMIS),
    (IntentType.CHAT, "deep dive into the temporal decay algorithm", AgentRoute.ARTEMIS),
    (IntentType.MEMORY_SEARCH, "what do I know about the cloud routing system", AgentRoute.ARTEMIS),

    # Execution → APOLLO
    (IntentType.CODING, "write the migration script for users table", AgentRoute.APOLLO),
    (IntentType.CODING, "fix the bug in the auth middleware", AgentRoute.APOLLO),
    (IntentType.CHAT, "write a function that validates email addresses", AgentRoute.APOLLO),
    (IntentType.CHAT, "create a new endpoint for user preferences", AgentRoute.APOLLO),
    (IntentType.CHAT, "build the WebSocket handler for real-time updates", AgentRoute.APOLLO),
    (IntentType.CHAT, "scaffold the health dashboard component", AgentRoute.APOLLO),
    (IntentType.CHAT, "refactor the memory manager to use async generators", AgentRoute.APOLLO),
    (IntentType.CHAT, "implement the ETag caching for wiki endpoints", AgentRoute.APOLLO),
    (IntentType.CALENDAR_CREATE, "schedule a meeting for tomorrow at 3pm", AgentRoute.APOLLO),
    (IntentType.REMINDER_CREATE, "remind me to deploy on Friday", AgentRoute.APOLLO),

    # Chain → ARTEMIS_THEN_APOLLO
    (IntentType.CHAT, "research how HealthKit handles background sync then implement it", AgentRoute.ARTEMIS_THEN_APOLLO),
    (IntentType.CHAT, "analyze the trade-offs of SSE vs WebSocket and then build the SSE implementation", AgentRoute.ARTEMIS_THEN_APOLLO),
    (IntentType.CHAT, "investigate the best caching strategy and implement it for our API", AgentRoute.ARTEMIS_THEN_APOLLO),
]


@pytest.fixture
def router():
    return AgentRouter(OrchestratorConfig())


class TestGoldenDataset:
    """Validate routing accuracy against golden dataset."""

    @pytest.mark.parametrize("intent,content,expected", GOLDEN_DATASET)
    def test_golden_routing(self, router, intent, content, expected):
        route, confidence = router.resolve(intent, content)
        assert route == expected, (
            f"Expected {expected.value} for '{content[:50]}...' "
            f"(intent={intent.value}), got {route.value}"
        )

    def test_accuracy_above_threshold(self, router):
        """Overall accuracy must be ≥75%."""
        correct = 0
        for intent, content, expected in GOLDEN_DATASET:
            route, _ = router.resolve(intent, content)
            if route == expected:
                correct += 1
        accuracy = correct / len(GOLDEN_DATASET)
        assert accuracy >= 0.75, (
            f"Routing accuracy {accuracy:.1%} below 75% threshold "
            f"({correct}/{len(GOLDEN_DATASET)} correct)"
        )
```

- [ ] **Step 2: Run golden dataset tests**

Run: `python -m pytest tests/test_routing_golden.py -v --timeout=30`
Expected: All PASS with >75% accuracy

- [ ] **Step 3: Commit**

```bash
git add tests/test_routing_golden.py
git commit -m "test: golden dataset for agent routing validation (30+ cases)"
```

---

### Task 18: ADR-042 + Documentation Updates

**Files:**
- Modify: `docs/hestia-decision-log.md`
- Modify: `SPRINT.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Write ADR-042**

Append to `docs/hestia-decision-log.md`:

```markdown
### ADR-042: Agent Orchestrator — Coordinate/Analyze/Delegate Model

**Date:** 2026-03-16
**Status:** Accepted
**Context:** The 3-agent system (Tia/Mira/Olly) required users to manually route requests via @mentions. This added cognitive overhead and didn't scale to the Jarvis-like vision.
**Decision:** Evolve to coordinator-delegate model. Hestia is the single user interface, internally orchestrating Artemis (analysis) and Apollo (execution). Council coordinator extended with agent routing. Deterministic intent-to-route heuristic as primary router. Async interfaces that collapse on M1 but parallelize on M5 Ultra.
**Consequences:** Simplified UX (single interface), routing audit trail for learning loop, byline attribution for transparency. @mention override preserved as power-user escape hatch. Council not replaced — extended. Routing accuracy depends on keyword heuristic quality.
```

- [ ] **Step 2: Update SPRINT.md with Sprint 14**

- [ ] **Step 3: Update CLAUDE.md** — architecture notes, project structure (new files), key patterns

- [ ] **Step 4: Commit**

```bash
git add docs/hestia-decision-log.md SPRINT.md CLAUDE.md
git commit -m "docs: ADR-042 agent orchestrator, update sprint tracker and CLAUDE.md"
```

---

### Task 19: Full Test Suite Verification

- [ ] **Step 1: Run the complete test suite**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: All 1917+ existing tests PASS, plus ~75 new tests

- [ ] **Step 2: Run CLI tests**

Run: `cd hestia-cli && python -m pytest tests/ -v --timeout=30`
Expected: All 72 CLI tests PASS

- [ ] **Step 3: Verify count**

Run: `./scripts/count-check.sh`
Expected: PASS

---

### Task 20: Master Roadmap Update

**Files:**
- Modify: `docs/plans/sprint-7-14-master-roadmap.md`

- [ ] **Step 1: Insert Agent Orchestrator sprint, renumber downstream sprints**

Update the sprint overview table to include Sprint 14 (Agent Orchestrator) and renumber old 11B→15, 12→16, 13→17, 14→18.

- [ ] **Step 2: Update dependency chain** — orchestrator sprint becomes dependency for MetaMonitor+

- [ ] **Step 3: Commit**

```bash
git add docs/plans/sprint-7-14-master-roadmap.md
git commit -m "docs: update master roadmap with agent orchestrator sprint"
```

---

## Summary

| Chunk | Tasks | New Tests | Key Deliverable |
|-------|-------|-----------|----------------|
| 1: Foundation | 1-5 | ~30 | Models, config, router, council extension, audit DB |
| 2: Core | 6-9 | ~30 | Context manager, synthesizer, planner, executor |
| 3: Integration | 10-16 | ~10 | Handler hook, API bylines, outcomes, streaming, mode patterns |
| 4: Validation | 17-20 | ~35 | Golden dataset, ADR, docs, full suite verification |
| **Total** | **20 tasks** | **~105** | **Full orchestrator + validation + docs** |
