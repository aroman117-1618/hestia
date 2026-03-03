# Neural Net Learning Cycle — Design Document

**Date:** 2026-03-03
**Status:** Approved
**Discovery:** `docs/discoveries/neural-net-learning-cycle-research.md`
**Decision:** Phased A→B→C (Reflection Engine → Metacognitive Monitoring → Active Inference)

---

## Architecture Decision

**Approach:** New `LearningManager` module following standard manager pattern (`models.py` + `database.py` + `manager.py`). Called from `RequestHandler` post-response via `asyncio.create_task()` — zero latency impact on user-facing responses.

**Why not event bus?** Hestia has no event bus infrastructure today. Adding one would be architectural scope creep. The standard manager + direct call pattern is proven across 22 existing modules.

**Why not inline in RequestHandler?** Separation of concerns. The learning system owns its own storage, its own background processing, and its own LLM interactions.

---

## Phase 1: The Reflection Engine (Sprint-Ready)

### Module Structure

```
hestia/learning/
├── __init__.py
├── models.py          # OutcomeSignal, Principle, ReflectionResult, LearningDomain
├── database.py        # LearningDatabase (SQLite) — extends BaseDatabase
├── manager.py         # LearningManager — singleton, orchestrates all learning
├── outcome_tracker.py # OutcomeTracker — captures implicit signals
├── reflection.py      # ReflectionAgent — LLM self-critique (dual-path: local + cloud-safe)
└── principles.py      # PrincipleStore — ChromaDB collection for distilled strategies
```

### Data Models

```python
class LearningDomain(Enum):
    SCHEDULING = "scheduling"
    COMMUNICATION = "communication"
    TECHNICAL = "technical"
    HEALTH = "health"
    PERSONAL = "personal"
    WORKFLOW = "workflow"
    GENERAL = "general"

class OutcomeSignalType(Enum):
    RESPONSE_ACCEPTED = "accepted"
    FOLLOW_UP_CORRECTION = "correction"
    TOPIC_REVISIT = "revisit"
    QUICK_FOLLOW_UP = "quick_follow_up"
    LONG_GAP = "long_gap"
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    ANTICIPATION_HIT = "anticipation_hit"
    ANTICIPATION_MISS = "anticipation_miss"

@dataclass
class OutcomeSignal:
    id: str
    session_id: str
    interaction_id: str
    signal_type: OutcomeSignalType
    domain: LearningDomain
    value: float                # -1.0 to 1.0
    context: str
    timestamp: datetime
    metadata: Dict[str, Any]

@dataclass
class Principle:
    id: str
    domain: LearningDomain
    content: str                # "Andrew prefers concise responses for scheduling"
    confidence: float           # 0.0 - 1.0
    validation_count: int
    contradiction_count: int
    source_interactions: List[str]
    created_at: datetime
    last_validated: Optional[datetime]
    last_contradicted: Optional[datetime]
    superseded_by: Optional[str]
    active: bool

@dataclass
class ReflectionResult:
    id: str
    session_id: str
    interaction_ids: List[str]
    what_worked: List[str]
    what_failed: List[str]
    signals_missed: List[str]
    new_principles: List[str]
    updated_principles: List[str]
    domain_scores: Dict[str, float]
    timestamp: datetime
```

### Storage

- **SQLite** (`data/learning.db`): OutcomeSignals, Principles (metadata), ReflectionResults
- **ChromaDB** (collection `learning_principles`): Principle content vectors for semantic retrieval
- Same embedding model as memory: `all-MiniLM-L6-v2`

### Component A: OutcomeTracker

Captures implicit and explicit signals about interaction quality.

**Implicit signals (automatic, no user burden):**

| Signal | Detection | Value |
|--------|-----------|-------|
| Response accepted | No correction in next message | +0.5 |
| Follow-up correction | Next message corrects same topic | -0.5 |
| Topic revisit | Same topic in new session | -0.3 |
| Quick follow-up | <30 seconds to next message | -0.2 |
| Long gap | >5 minutes before next message | +0.3 |
| Anticipation hit | Briefing section engaged | +0.7 |
| Anticipation miss | Briefing section ignored | -0.1 |

**Explicit signals (new feedback API):**

| Signal | Value |
|--------|-------|
| Thumbs up | +1.0 |
| Thumbs down | -1.0 |

**"Evaluate on next message" pattern:** When a response is sent, OutcomeTracker stores a "pending evaluation." When the next message arrives, it evaluates the previous interaction (time gap, topic continuity, correction detection). This deferred evaluation is how recommendation engines work — the signal for item N is user behavior on item N+1.

**Domain classification:** Maps council `IntentType` → `LearningDomain`. CALENDAR_* → SCHEDULING, CHAT → COMMUNICATION, etc. Reuses existing intent classification, no extra LLM call.

### Component B: ReflectionAgent

Post-session LLM self-critique that distills interactions into principles.

**Trigger:** Async after session ends, or after N interactions (configurable, default N=10).

**Guard rails:**
- Only runs if >3 interactions have outcome signals
- New principles start at confidence 0.3
- Contradicted principles decrease confidence (never deleted until <0.1)
- Uses local Qwen 2.5 7B by default

**Dual-path reflection (cloud-safe):**
- Cloud disabled → Local only, all data stays on device
- Cloud enabled_smart → Local first, cloud fallback with sanitized data
- Cloud enabled_full → Cloud (sanitized) with local fallback

**Sanitization for cloud:** Strip proper nouns, replace with tokens ("Andrew" → "the user", "Tuesday dentist" → "a scheduling event"). Health data excluded entirely. Only anonymized interaction patterns sent. Follows existing `get_cloud_safe_context()` pattern.

### Component C: PrincipleStore

Semantic storage via ChromaDB collection `learning_principles`.

**Retrieval:** `get_relevant_principles(query, domain, min_confidence)` returns principles sorted by relevance × confidence.

**Lifecycle:**
- Created by ReflectionAgent (confidence 0.3)
- Validated by OutcomeTracker (confidence increases)
- Contradicted by OutcomeTracker (confidence decreases)
- Established at confidence > 0.8 + validation_count > 5 → decay rate matches FACT chunks
- Superseded when newer principle covers same domain

**Integration:** PromptBuilder injects top-K relevant principles into system prompts, giving Hestia learned behavioral guidance.

### Component D: Feedback API

```
POST /v1/chat/{interaction_id}/feedback
  Request:  { rating: int (1 or 5), comment: Optional[str] }
  Response: { recorded: bool, interaction_id: str }
```

### Integration Point: RequestHandler

Minimal change (~5 lines):

```python
if self._learning_manager:
    asyncio.create_task(
        self._learning_manager.record_interaction(
            session_id=session_id,
            user_message=request.message,
            response=response.response,
            intent=intent_result,
            council_result=council_result,
            mode=current_mode,
        )
    )
```

### New API Endpoints (Phase 1)

| Method | Route | Purpose |
|--------|-------|---------|
| POST | `/v1/chat/{interaction_id}/feedback` | Thumbs up/down |
| GET | `/v1/learning/principles` | List active principles |
| GET | `/v1/learning/principles/{id}` | Principle detail |
| GET | `/v1/learning/stats` | Domain scores, signal counts |
| GET | `/v1/learning/reflections` | Recent reflection results |
| POST | `/v1/learning/reflect` | Manual reflection trigger |

### New LogComponent

Add `LEARNING` to `LogComponent` enum.

---

## Phase 2: Metacognitive Monitoring (Design Sketch)

**Prerequisite:** ~4 weeks of Phase 1 outcome data accumulated.

### New Components

```
hestia/learning/
├── metacognition.py    # MetaMonitor — background analysis loop
├── confidence.py       # ConfidenceCalibrator — per-domain accuracy tracking
└── knowledge_gaps.py   # KnowledgeGapDetector — identifies unknown unknowns
```

### Interface Contracts

```python
class MetaMonitor:
    async def run_analysis(self, lookback_days: int = 30) -> MetaReport
    async def get_domain_health(self) -> Dict[LearningDomain, DomainHealth]

class ConfidenceCalibrator:
    async def update(self, domain: LearningDomain, predicted: str, actual: str, match: bool) -> float
    async def get_confidence(self, domain: LearningDomain) -> float
    async def get_calibration_report(self) -> Dict[LearningDomain, CalibrationReport]

class KnowledgeGapDetector:
    async def identify_gaps(self) -> List[KnowledgeGap]
    async def generate_questions(self, max_questions: int = 3) -> List[CuriosityQuestion]
```

### Integration

- MetaMonitor runs as background task (every N hours, configurable)
- ConfidenceCalibrator extends TemporalDecay with feedback dimension
- KnowledgeGapDetector feeds into BriefingGenerator as "questions Hestia wants to ask"
- InterruptionPolicy gates question surfacing
- Results feed into existing BriefingGenerator as new section

### New API Endpoints (Phase 2)

| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/v1/learning/confidence` | Per-domain confidence scores |
| GET | `/v1/learning/gaps` | Knowledge gaps and curiosity questions |
| GET | `/v1/learning/meta-report` | Latest metacognitive analysis |

---

## Phase 3: Active Inference Engine (Design Sketch)

**Prerequisite:** Phase 2 confidence data calibrated across domains.

### New Components

```
hestia/learning/
├── world_model.py      # GenerativeWorldModel — hierarchical belief system
├── prediction.py       # PredictionEngine — predictions scored against reality
└── curiosity.py        # CuriosityDrive — exploration via information gain
```

### Interface Contracts

```python
class GenerativeWorldModel:
    async def update_belief(self, domain: LearningDomain, observation: Any) -> None
    async def get_belief(self, domain: LearningDomain) -> DomainBelief
    async def get_all_beliefs(self) -> Dict[LearningDomain, DomainBelief]

class PredictionEngine:
    async def predict(self, context: InteractionContext) -> Prediction
    async def score(self, prediction: Prediction, actual: OutcomeSignal) -> float

class CuriosityDrive:
    async def compute_curiosity(self) -> Dict[LearningDomain, float]
    async def get_regime(self, domain: LearningDomain) -> OperatingRegime
    async def rank_questions(self, gaps: List[KnowledgeGap]) -> List[RankedQuestion]
```

### Three Operating Regimes

| Regime | Condition | Behavior |
|--------|-----------|----------|
| Anticipatory | confidence > 0.8, PE < 0.2 | Act proactively |
| Curious | confidence < 0.4, entropy > threshold | Ask strategic questions |
| Observant | 0.4 < confidence < 0.8 | Watch and learn silently |

### Hierarchical World Model

- **Abstract layer:** Personality, goals, values (updates weekly, from established principles)
- **Routine layer:** Patterns, preferences, habits (updates daily, from PatternDetector)
- **Situational layer:** Current task, context (updates per-interaction, from council intent)

### Math

```
prediction_error[d] = |predicted - actual|
F[d] = prediction_error[d]² + complexity_penalty[d]
curiosity[d] = entropy(belief[d])
λ_effective = λ_base × (1 - validation_rate)
outcome_weight = sigmoid(Σ(outcome_signals) / n_interactions)
```

---

## Neural Net Visualization Extension

### Phase 1 Visual Additions

| Dimension | Visual Channel | Source |
|-----------|---------------|--------|
| Principle nodes | Gold color (1.0, 0.85, 0.2) | New `ChunkType.PRINCIPLE` |
| Principle strength | Emission glow intensity | `Principle.confidence` |
| Active reflection | Faster pulse (1.5s vs 3s) | Recently reflected nodes |
| Feedback flash | Green/red 0.5s flash | Thumbs up/down recorded |
| Learning heartbeat | Ripple wave animation | Reflection completed |

### Phase 2 Visual Additions

| Dimension | Visual Channel | Source |
|-----------|---------------|--------|
| Domain cluster | Spatial grouping | Force layout groups same-domain principles |
| Confidence halo | Ring opacity | ConfidenceCalibrator scores |
| Knowledge gap | Dim, faded cluster | High curiosity score domains |

### Phase 3 Visual Additions

| Dimension | Visual Channel | Source |
|-----------|---------------|--------|
| Operating regime | Cluster ambient color | Green=anticipatory, Amber=curious, Neutral=observant |
| Prediction accuracy | Edge color gradient | Green (accurate) → Red (inaccurate) |

### Data Pipeline

```
NeuralNetViewModel.loadGraph()
  → searchMemory(query: "*", limit: 50)    // existing
  → GET /v1/learning/principles             // NEW
  → Merge: principles → gold nodes, link via source_interactions
  → computeLayout() with principles included
```

### iOS/macOS UI Changes

- Chat messages: thumbs up/down buttons on assistant responses
- New "Learning" section in Neural Net / Command Center view
- Settings: "Enable learning cycle" toggle + cloud reflection opt-in
- Principle detail card on node tap (shows content, confidence, validations)

---

## Configuration

New section in `config/learning.yaml`:

```yaml
learning:
  enabled: true
  outcome_tracking:
    quick_follow_up_threshold_seconds: 30
    long_gap_threshold_seconds: 300
    correction_keywords: ["no", "actually", "I meant", "not what I", "wrong"]
  reflection:
    trigger_after_interactions: 10
    min_interactions_for_reflection: 3
    new_principle_confidence: 0.3
    established_confidence_threshold: 0.8
    established_validation_threshold: 5
    cloud_fallback_enabled: false  # Opt-in
  principles:
    max_active_principles: 200
    min_confidence_for_prompt_injection: 0.5
    max_principles_in_prompt: 5
    decay_rate: 0.003  # Half-life ~231 days
  metacognition:  # Phase 2
    analysis_interval_hours: 24
    lookback_days: 30
  active_inference:  # Phase 3
    anticipation_confidence_threshold: 0.8
    curiosity_entropy_threshold: 0.6
    prediction_error_curiosity_threshold: 0.5
```

---

## Security Considerations

- All learning data stored locally by default
- Cloud reflection uses sanitized data only (no PII, no health details)
- Principles never contain specific personal data — only behavioral patterns
- Feedback API requires JWT auth (standard middleware)
- No learning data leaves the device unless cloud reflection is explicitly enabled
- Audit logging for all principle creation/supersession events

---

## Testing Strategy

- Unit tests for OutcomeTracker signal detection logic
- Unit tests for Principle lifecycle (create, validate, contradict, supersede)
- Integration tests for ReflectionAgent (mock LLM, verify prompt structure)
- Integration tests for full learning cycle (interaction → signal → reflection → principle)
- API endpoint tests for feedback and learning routes
- Mock ChromaDB for principle store tests (same pattern as memory tests)
