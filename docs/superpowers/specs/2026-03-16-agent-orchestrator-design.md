# Agent Orchestrator Design Spec

**Date:** 2026-03-16
**Status:** APPROVED
**ADR:** ADR-042 (pending)
**Sprint:** 14 (Agent Orchestrator)

---

## Overview

Evolve Hestia from user-routed persona switching to a coordinator-delegate model. Hestia becomes the single user interface, internally orchestrating Artemis (analysis) and Apollo (execution) as sub-agents. The council coordinator is extended to produce agent routing decisions. Architecture uses async interfaces that collapse to single-call on M1 but parallelize on M5 Ultra.

## Agent Roles

| Agent | Role | Invocation | System Prompt Focus | Temperature |
|-------|------|-----------|-------------------|-------------|
| **Hestia** | Coordinator | Always — she IS the interface | Context management, routing, synthesis, Jarvis personality | 0.0 |
| **Artemis** | Analyst | Routed by Hestia when analysis needed | Socratic depth, multi-perspective reasoning, thoroughness | 0.3 |
| **Apollo** | Executor | Routed by Hestia when execution needed | Laser focus, minimal tangents, production-quality output | 0.0 |

## Architecture

### New Types

```python
class AgentRoute(str, Enum):
    HESTIA_SOLO = "hestia_solo"
    ARTEMIS = "artemis"
    APOLLO = "apollo"
    ARTEMIS_THEN_APOLLO = "artemis_apollo"

class AgentTask:
    agent_id: AgentRoute
    prompt: str
    context_slice: ContextSlice
    model_preference: Optional[ModelTier]

class AgentResult:
    agent_id: AgentRoute
    content: str
    confidence: float
    tool_calls: List[ToolCall]
    tokens_used: int
    duration_ms: int

class ExecutionPlan:
    steps: List[ExecutionStep]
    estimated_hops: int
    rationale: str

class ExecutionStep:
    tasks: List[AgentTask]  # 1 = sequential, N = parallel group
    depends_on: Optional[int]

class AgentByline:
    agent: AgentRoute
    contribution_type: str  # "analysis", "implementation", "tool_result"
    summary: str

class RoutingAuditEntry:
    id: str
    user_id: str                       # Family-scale ready
    request_id: str
    timestamp: datetime
    intent: IntentType
    route_chosen: AgentRoute
    route_confidence: float
    actual_agents_invoked: List[str]
    chain_collapsed: bool
    fallback_triggered: bool
    total_inference_calls: int
    total_duration_ms: int
    # No input_summary — CISO finding: avoid PII in audit log
```

### Council Extension

Extend `IntentClassification` with 2 new optional fields:

```python
@dataclass
class IntentClassification:
    primary_intent: IntentType
    confidence: float
    reasoning: str
    # NEW
    agent_route: AgentRoute = AgentRoute.HESTIA_SOLO
    route_confidence: float = 0.0
```

### Intent-to-Route Heuristic (Primary Routing)

Deterministic mapping as the primary routing mechanism. SLM does intent classification only (proven, tested). The heuristic maps intent to route:

```python
INTENT_ROUTE_MAP = {
    # Analysis-oriented intents → Artemis
    IntentType.MEMORY_SEARCH: AgentRoute.ARTEMIS,

    # Execution-oriented intents → Apollo
    IntentType.CODING: AgentRoute.APOLLO,
    IntentType.CALENDAR_CREATE: AgentRoute.APOLLO,
    IntentType.REMINDER_CREATE: AgentRoute.APOLLO,
    IntentType.NOTE_CREATE: AgentRoute.APOLLO,

    # Simple intents → Hestia solo
    IntentType.CHAT: AgentRoute.HESTIA_SOLO,
    IntentType.CALENDAR_QUERY: AgentRoute.HESTIA_SOLO,
    IntentType.REMINDER_QUERY: AgentRoute.HESTIA_SOLO,
    IntentType.NOTE_SEARCH: AgentRoute.HESTIA_SOLO,
    IntentType.MAIL_QUERY: AgentRoute.HESTIA_SOLO,
    IntentType.WEATHER_QUERY: AgentRoute.HESTIA_SOLO,
    IntentType.STOCKS_QUERY: AgentRoute.HESTIA_SOLO,
    IntentType.UNCLEAR: AgentRoute.HESTIA_SOLO,
}

# Complexity heuristic for CHAT intent (overrides HESTIA_SOLO)
ANALYSIS_KEYWORDS = [
    "analyze", "compare", "trade-off", "tradeoff", "pros and cons",
    "evaluate", "assess", "review", "explain why", "help me think",
    "what are the options", "should i", "debate", "argue",
    "research", "investigate", "deep dive",
]

EXECUTION_KEYWORDS = [
    "write", "build", "implement", "create", "scaffold",
    "generate", "code", "fix", "refactor", "migrate",
    "deploy", "script", "function", "class", "test",
]
```

When intent is CHAT but content matches ANALYSIS_KEYWORDS → ARTEMIS.
When intent is CHAT but content matches EXECUTION_KEYWORDS → APOLLO.
When intent is CHAT and content matches BOTH → ARTEMIS_THEN_APOLLO.
When cloud is active, council classifier can override heuristic with model-based routing.

### Confidence Gating

| Route Confidence | Behavior |
|-----------------|----------|
| > 0.8 | Full specialist dispatch (separate inference call) |
| 0.5 - 0.8 | Hestia solo with specialist persona hints in prompt |
| < 0.5 | Hestia solo, default persona |

### Chain Validation

Before executing multi-step plans:
- Short requests (<15 words) with >1 hop → collapse to single agent
- Cloud disabled + >2 hops → collapse to single agent
- Heuristic: does the request actually need both analysis AND execution?

### Step-Level Fallback

If specialist returns confidence < 0.4 or errors:
- Fallback to Hestia-solo with enriched context
- Log fallback in routing audit

### @Mention Override

Explicit `@artemis` or `@apollo` overrides orchestrator routing. Existing `ModeManager.detect_mode_from_input()` handles detection. Priority: explicit @mention > orchestrator > default.

### Context Slicing (ContextManager)

| Agent | Gets | Doesn't Get |
|-------|------|------------|
| Artemis | Full conversation history, memory context, user profile, research/facts | Tool definitions (unless analysis of tools requested) |
| Apollo | Artemis output (if chained), tool definitions, relevant code context, recent turns only | Full conversation history, full user profile |
| Hestia (synthesis) | All agent outputs, original request, user profile | Raw memory chunks |

### Result Synthesis

For single-agent dispatch: agent's output IS the response, Hestia adds byline.
For multi-agent chains: Hestia synthesizes outputs into a coherent response with per-agent attribution.

Byline format in response:
```
[Response content...]

---
📐 Artemis — analyzed WebSocket vs SSE trade-offs
⚡ Apollo — scaffolded SSE implementation (3 files)
```

### Response Schema Extension

```python
class ChatResponse(BaseModel):
    # ... existing fields ...
    bylines: Optional[List[AgentBylineSchema]] = None

class AgentBylineSchema(BaseModel):
    agent: str           # "artemis", "apollo"
    contribution: str    # "analysis", "implementation"
    summary: str         # One-line description

# SSE: new "byline" event type emitted before "done"
```

### Outcome Tracking Extension

Add columns to OutcomeRecord (not metadata dict — designed for frequent analysis queries):

```sql
ALTER TABLE outcomes ADD COLUMN agent_route TEXT;
ALTER TABLE outcomes ADD COLUMN route_confidence REAL;
```

### Routing Audit Table

```sql
CREATE TABLE routing_audit (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    intent TEXT NOT NULL,
    route_chosen TEXT NOT NULL,
    route_confidence REAL NOT NULL,
    actual_agents TEXT NOT NULL,  -- JSON list
    chain_collapsed INTEGER DEFAULT 0,
    fallback_triggered INTEGER DEFAULT 0,
    total_inference_calls INTEGER DEFAULT 1,
    total_duration_ms INTEGER DEFAULT 0
);
```

### Configuration

New section in `config/orchestration.yaml`:

```yaml
orchestrator:
  enabled: true  # Kill switch
  confidence_thresholds:
    full_dispatch: 0.8
    enriched_solo: 0.5
  chain_validation:
    min_words_for_chain: 15
    max_hops_local: 2
    max_hops_cloud: 4
  fallback:
    min_specialist_confidence: 0.4
  analysis_keywords: [...]
  execution_keywords: [...]
```

### File Layout

```
hestia/orchestration/
├── handler.py              # MODIFIED — call orchestrator instead of direct inference
├── mode.py                 # MODIFIED — updated regex for @artemis/@apollo
├── prompt.py               # EXISTING — already supports per-mode prompts
├── planner.py              # NEW — OrchestrationPlanner (route selection, plan generation)
├── executor.py             # NEW — AgentExecutor (task dispatch, fallback, parallel groups)
├── context_manager.py      # NEW — context slicing functions (lightweight, no state)
├── synthesizer.py          # NEW — result combination + byline generation (lightweight)
└── models.py               # NEW — AgentRoute, AgentTask, AgentResult, ExecutionPlan, etc.
```

5 new files, 2 modified files in orchestration layer.

### iOS/macOS Byline Rendering

**iOS (Chat):**
- Parse `bylines` from `ChatResponse`
- Render below message content using `HestiaTypography.caption` + `HestiaColors.secondaryText`
- Agent emoji: 📐 Artemis, ⚡ Apollo
- VoiceOver: "Artemis analyzed [summary]"
- When `bylines` is nil: show nothing

**macOS (Chat panel):**
- Same rendering as iOS
- Use `MacTypography.caption` + `MacColors.secondaryText`

**SSE streaming:**
- Parse `"byline"` event type
- Display after streaming completes, before final message state

### Roadmap Impact

| Item | Change |
|------|--------|
| This sprint | Sprint 14: Agent Orchestrator (new) |
| Sprint 11B (MetaMonitor) | Consumes routing audit data as input source |
| Sprint 13 (World Model) | Routine Layer tracks routing preferences |
| Sprint 14-old (Anticipatory) | Renumber to Sprint 15. Anticipation routes through orchestrator |
| Master roadmap | Insert orchestrator sprint, update dependency chain |
| CLAUDE.md | Update architecture notes, endpoint count, project structure |

### Testing Strategy

| Component | Tests | Type |
|-----------|-------|------|
| Intent-to-route heuristic | 10-12 | Unit — keyword matching, edge cases, BOTH keywords |
| OrchestrationPlanner | 12-15 | Unit — route selection, confidence gating, chain validation, collapsing |
| AgentExecutor | 8-10 | Unit — dispatch, fallback, timeout, parallel groups |
| ContextManager | 6-8 | Unit — slicing per agent, token budgets, PII exclusion |
| ResultSynthesizer | 5-7 | Unit — byline generation, multi-agent combination, empty results |
| Council extension | 8-10 | Unit — new fields, backward compat, fast-path preserved |
| Handler integration | 6-8 | Unit — pipeline hook, streaming bylines, @mention override |
| Routing audit | 4-5 | Unit — entry creation, querying, user_id scoping |
| Outcome extension | 3-4 | Unit — new columns, migration, querying by route |
| A/B prompt quality | 10-15 | Validation — golden dataset, specialist vs solo quality |
| **Total** | **72-94** | |

### Golden Dataset for Routing Validation

Create 30-50 example inputs with expected routes. Validate routing accuracy >75% before sprint completion:

```python
GOLDEN_ROUTING_DATASET = [
    ("What's on my calendar today?", AgentRoute.HESTIA_SOLO),
    ("Compare SQLite vs Postgres for this feature", AgentRoute.ARTEMIS),
    ("Write the migration script", AgentRoute.APOLLO),
    ("Research HealthKit background sync then implement it", AgentRoute.ARTEMIS_THEN_APOLLO),
    ("Hey", AgentRoute.HESTIA_SOLO),
    ("Help me think through the auth architecture", AgentRoute.ARTEMIS),
    # ... 25-45 more examples
]
```

### Definition of Done

- [ ] `AgentRoute` enum and all model types in `orchestration/models.py`
- [ ] Intent-to-route heuristic with keyword matching
- [ ] `IntentClassification` extended with `agent_route` and `route_confidence`
- [ ] `OrchestrationPlanner` with confidence gating and chain validation
- [ ] `AgentExecutor` with single-agent dispatch and fallback
- [ ] `ContextManager` with per-agent context slicing
- [ ] `ResultSynthesizer` with byline generation
- [ ] `orchestrator_enabled` config flag in `orchestration.yaml`
- [ ] Handler integration (both `handle()` and `handle_streaming()`)
- [ ] `@mention` override preserved
- [ ] `ChatResponse.bylines` optional field added
- [ ] SSE `"byline"` event type emitted
- [ ] `routing_audit` table with `user_id` column
- [ ] `outcomes` table extended with `agent_route` and `route_confidence` columns
- [ ] iOS byline rendering in chat
- [ ] macOS byline rendering in chat panel
- [ ] `orchestrator_enabled: false` falls back cleanly to current behavior
- [ ] Golden dataset: routing accuracy >75%
- [ ] A/B prompt validation: specialist prompts produce meaningfully different responses
- [ ] 72+ new tests passing
- [ ] All 1917 existing tests still passing
- [ ] CLAUDE.md updated (architecture, structure, endpoint notes)
- [ ] ADR-042 written in decision log
- [ ] `SPRINT.md` updated
- [ ] Master roadmap updated with renumbered sprints
