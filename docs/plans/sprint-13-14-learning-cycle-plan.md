# Sprints 13–14: Neural Net Learning Cycle — Active Inference

**Created:** 2026-03-03
**Status:** PLANNED (Future — depends on Sprints 7–12 completion)
**Priority:** P2 — Intelligence evolution
**Estimated Effort:** Sprint 13: ~12 days, Sprint 14: ~10 days (~132 hours total)
**Prerequisites:** All prior sprints (especially PrincipleStore, OutcomeTracker, MetaMonitor)
**Learning Cycle Phase:** C — Active Inference (endgame)

**Reference:** [Neural Net Learning Cycle Research](../discoveries/neural-net-learning-cycle-research.md)

---

## Context

Sprints 7–12 close the feedback loop and build the data infrastructure:
- Sprint 8: PrincipleStore (distilled knowledge)
- Sprint 10: OutcomeTracker (implicit feedback signals)
- Sprint 11: MetaMonitor + ConfidenceCalibrator + KnowledgeGapDetector (self-awareness)
- Sprint 12: Health data (personal state signals)

Sprints 13–14 use all of this to build the Active Inference Engine — making Hestia genuinely anticipatory, curious, and self-improving.

---

## Sprint 13: Active Inference Foundation (~12 days)

### Objective

Build the hierarchical Generative World Model, Prediction Engine, Surprise Detector, and Curiosity Drive. These are the mathematical foundations for making commands obsolete.

### 13.1 Generative World Model (~4 days)

**New module:**
```
hestia/learning/world_model/
├── __init__.py
├── models.py             # WorldState, AbstractLayer, RoutineLayer, SituationalLayer
├── manager.py            # WorldModelManager
├── database.py           # SQLite for world model state
└── updater.py            # EMA belief updater (was Bayesian — changed per audit)
```

**Three hierarchical layers:**

| Layer | What It Models | Update Frequency | Data Source |
|-------|---------------|-----------------|-------------|
| **Abstract** | Andrew's personality, goals, values, work style | Monthly | Principles, MIND.md, long-term memories |
| **Routine** | Weekly patterns, preferences, habits | Weekly | PatternDetector, OutcomeTracker, calendar patterns |
| **Situational** | Current task, active context, immediate needs, emotional state | Per-interaction | Current session, recent messages, health data |

**State representation:**
```python
class WorldState(BaseModel):
    """Complete model of Andrew's current state across all layers."""

    # Abstract layer (slow-changing)
    abstract: AbstractLayer  # personality traits, goals, communication_style
    # Routine layer (weekly-changing)
    routine: RoutineLayer    # weekly_patterns, preferences, habits
    # Situational layer (per-interaction)
    situational: SituationalLayer  # current_task, active_context, energy_level, mood_proxy

class AbstractLayer(BaseModel):
    communication_style: Dict[str, float]  # {"concise": 0.7, "detailed": 0.3}
    # Audit note: These values are populated via explicit extraction prompt that maps
    # MIND.md free-text → structured values. Version the extraction prompt.
    work_domains: Dict[str, float]         # {"coding": 0.4, "management": 0.3, ...}
    decision_patterns: Dict[str, str]      # {"risk": "moderate", "speed": "fast"}
    values: List[str]                      # Extracted from MIND.md
    last_updated: datetime

class RoutineLayer(BaseModel):
    weekly_schedule: Dict[str, List[str]]  # {"monday": ["standup", "coding"], ...}
    preferences: Dict[str, Dict[str, float]]  # {"email": {"morning": 0.8, "evening": 0.2}}
    habits: List[Habit]
    active_projects: List[str]
    last_updated: datetime

class SituationalLayer(BaseModel):
    current_session_topic: Optional[str]
    recent_tools_used: List[str]
    energy_proxy: float          # Derived from time-of-day + health data
    calendar_density: float      # How busy today
    last_interaction_mood: Optional[str]  # Inferred from message tone
    updated_at: datetime
```

**Belief update mechanism — Exponential Moving Average (EMA):**

> ⚠️ **Audit finding (2026-03-03):** Original "simplified Bayesian" approach (`belief + learning_rate * prediction_error`) is mathematically infeasible — Qwen 2.5 7B doesn't produce calibrated probability distributions required for Bayesian updates. **Replaced with EMA**, which provides the same adaptive behavior without distributional assumptions.

```python
# Exponential Moving Average per domain d:
belief[d] = alpha[d] * new_signal + (1 - alpha[d]) * belief[d]

# Where alpha (smoothing factor) varies by layer:
ALPHA_RATES = {
    "abstract": 0.05,      # Very slow learning (personality doesn't change fast)
    "routine": 0.15,       # Moderate (habits shift over weeks)
    "situational": 0.5,    # Fast (current context changes every interaction)
}

# new_signal: derived from concrete observables (tool usage, calendar patterns,
# OutcomeTracker signals), NOT from LLM output probabilities
```

### 13.2 Prediction Engine (~3 days)

**File:** `hestia/learning/prediction_engine.py`

**Before each interaction, generate predictions:**
```python
class PredictionEngine:
    async def predict(self, world_state: WorldState, context: Dict) -> List[Prediction]:
        """Generate predictions about what Andrew likely needs."""
        predictions = []

        # Time-based predictions (routine layer)
        time_predictions = self._predict_from_time(world_state.routine, context["time"])

        # Context-based predictions (situational layer)
        context_predictions = self._predict_from_context(world_state.situational)

        # Pattern-based predictions (routine + abstract)
        pattern_predictions = self._predict_from_patterns(world_state)

        return self._rank_and_deduplicate(
            time_predictions + context_predictions + pattern_predictions
        )

class Prediction(BaseModel):
    id: str
    domain: str                # "scheduling", "email", "coding", etc.
    content: str               # "Andrew will want to check email"
    confidence: float          # 0.0–1.0
    source: str                # "routine_pattern", "time_of_day", "context"
    generated_at: datetime
    validated: Optional[bool]  # Set after interaction completes
    actual_outcome: Optional[str]
```

**Prediction logging:** Every prediction is stored in SQLite. After the interaction, predictions are scored against actual outcomes (via OutcomeTracker). This feeds back into ConfidenceCalibrator.

### 13.3 Surprise Detector (~2 days)

**File:** `hestia/learning/surprise_detector.py`

**Mathematical formalism (replacing heuristic thresholds from MetaMonitor):**

```python
class SurpriseDetector:
    async def compute_surprise(self, predictions: List[Prediction],
                                actual: InteractionOutcome) -> SurpriseReport:
        """Compute prediction error (surprise) for this interaction."""
        errors = []
        for pred in predictions:
            error = self._compute_prediction_error(pred, actual)
            errors.append(PredictionError(
                prediction_id=pred.id,
                domain=pred.domain,
                error=error,
                # Surprise signal: quadratic error (complexity penalty dropped per audit —
                # the quadratic term alone provides sufficient surprise signal)
                surprise_signal=error**2,
            ))

        # Update running exponential moving average per domain
        for err in errors:
            self.ema[err.domain] = (
                self.alpha * err.error +
                (1 - self.alpha) * self.ema.get(err.domain, 0.5)
            )

        return SurpriseReport(
            total_surprise=sum(e.surprise_signal for e in errors),
            per_domain=errors,
            high_surprise_domains=[
                d for d, v in self.ema.items() if v > self.surprise_threshold
            ]
        )
```

**Threshold: surprise > 0.5 triggers curiosity drive for that domain.**

### 13.4 Write Settings Tools with Tiered Risk (~1 day)

> **Added 2026-03-04** from Self-Healing Loop Assessment. Enables Tia to apply approved corrections.

**New file:** `hestia/execution/tools/settings_write_tools.py`

**Tool:** `update_user_setting(key, value)` — writes to UserSettings with risk-gated approval.

**Tiered Risk Classification:**

| Setting Category | Risk | Gate | Examples |
|-----------------|------|------|----------|
| Display preferences | SUGGEST | Queued → principles view → approve/reject | timezone, date format, greeting style |
| Behavioral preferences | SUGGEST | Queued → principles view → approve/reject | default mode, temperature, verbosity |
| Security settings | NEVER | Always manual | auth timeout, biometric config |
| System settings | NEVER | Always manual | model selection, provider config |

**Default mode: SUGGEST for all categories.** Auto-apply (SILENT) is a future enhancement gated on a confidence weight that accounts for urgency, impact, security sensitivity, and correction frequency. The scoring framework:

```python
class CorrectionConfidence:
    urgency: float        # How time-sensitive (timezone wrong = high, greeting style = low)
    impact: float         # How many features affected (timezone = high, verbosity = low)
    security_risk: float  # Risk of wrong application (timezone = zero, auth = critical)
    frequency: float      # How often this correction has been made (3+ times = high confidence)

    @property
    def auto_apply_score(self) -> float:
        """Score > 0.8 enables SILENT mode. Reviewed in principles view."""
        return (self.urgency * 0.2 + self.impact * 0.2 +
                (1 - self.security_risk) * 0.4 + self.frequency * 0.2)
```

**UX:** All suggested corrections surface in the existing `/research/principles` view/modal alongside knowledge principles. Tagged with `source=correction` and `correction_type`. Andrew approves or rejects. Approved corrections apply immediately via `update_user_setting()`.

**Future (post-Sprint 14):** Once confidence scoring is validated against real correction data, settings with `auto_apply_score > 0.8` can be promoted to SILENT. This requires sufficient OutcomeTracker data to calibrate the weights — not before Sprint 14 completion at earliest.

### 13.5 Curiosity Drive (~3 days)

**File:** `hestia/learning/curiosity_drive.py`

**Information-theoretic curiosity:**
```python
class CuriosityDrive:
    async def rank_curiosity(self) -> List[CuriosityTarget]:
        """Rank domains by expected information gain."""
        targets = []
        for domain in self.calibrator.domains:
            # Shannon entropy of current beliefs
            current_entropy = self._compute_entropy(self.world_model.get_beliefs(domain))
            # Expected entropy reduction from one more data point
            expected_info_gain = current_entropy * self._data_scarcity_factor(domain)
            # Surprise momentum (how much surprise has been accumulating)
            surprise_momentum = self.surprise_detector.ema.get(domain, 0)

            curiosity_score = expected_info_gain * (1 + surprise_momentum)

            targets.append(CuriosityTarget(
                domain=domain,
                curiosity_score=curiosity_score,
                current_entropy=current_entropy,
                expected_info_gain=expected_info_gain,
                suggested_question=await self._generate_question(domain),
            ))

        return sorted(targets, key=lambda t: t.curiosity_score, reverse=True)

    async def _generate_question(self, domain: str) -> str:
        """Use LLM to generate a high-value question for this domain.

        Audit note: Ground questions in CONCRETE OBSERVABLES (calendar patterns,
        tool usage counts, health metrics), not abstract model metrics.
        Self-referential questions about LLM performance create a loop risk.
        """
        knowledge_gaps = self.gap_detector.get_gaps(domain)
        recent_surprises = self.surprise_detector.get_recent(domain, days=7)
        # Ground in observables, not abstract model state
        concrete_observations = await self._get_concrete_observations(domain)

        prompt = f"""
        Domain: {domain}
        Concrete observations: {concrete_observations}
        Knowledge gaps: {knowledge_gaps}
        Recent surprises (things I predicted wrong): {recent_surprises}

        Generate one specific, natural question grounded in the concrete observations above.
        The question should reference observable behavior (calendar patterns, tool usage,
        health data trends), NOT abstract AI metrics or model performance.
        It should feel like a thoughtful colleague noticing something, not an interrogation.
        """
        return await self.inference.generate(prompt)
```

**Surfacing questions:** CuriosityDrive generates questions ranked by expected information gain. Top questions are surfaced via:
1. Daily briefing (highest-priority question of the day)
2. Contextual moments (after a surprise, Hestia asks a follow-up)
3. InterruptionPolicy gating (respects quiet hours, focus mode, etc.)

**API endpoints:**
```
GET /v1/learning/world-model          → Current world state (all 3 layers)
GET /v1/learning/predictions          → Recent predictions + validation status
GET /v1/learning/surprise             → Surprise report (per-domain EMA)
GET /v1/learning/curiosity            → Ranked curiosity targets + suggested questions
```

---

## Sprint 14: Anticipatory Execution (~10 days)

### Objective

The three operating regimes go live. Hestia starts proactively acting on high-confidence predictions, asking strategic questions in high-uncertainty domains, and silently observing in medium-confidence domains.

### 14.1 Three Operating Regimes (~3 days)

```python
class OperatingRegime(str, Enum):
    ANTICIPATORY = "anticipatory"  # High confidence → act proactively
    CURIOUS = "curious"            # High uncertainty → ask questions
    OBSERVANT = "observant"        # Medium → watch and learn

class RegimeSelector:
    """Selects operating regime per domain.

    Audit notes:
    - Thresholds are configurable via config/learning.yaml (not hardcoded)
    - Includes hysteresis to prevent rapid regime switching
    - "Was this proactive action helpful?" feedback button tunes thresholds
    """

    def __init__(self, config: dict):
        # Configurable thresholds (from config/learning.yaml)
        self.anticipatory_confidence = config.get("anticipatory_confidence", 0.8)
        self.anticipatory_surprise = config.get("anticipatory_surprise", 0.2)
        self.curious_confidence = config.get("curious_confidence", 0.4)
        self.curious_surprise = config.get("curious_surprise", 0.5)
        self.min_data_points = config.get("min_data_points_anticipatory", 20)
        # Hysteresis: require threshold + margin to switch regimes (prevents flapping)
        self.hysteresis_margin = config.get("hysteresis_margin", 0.05)
        self._current_regimes: Dict[str, OperatingRegime] = {}

    async def select_regime(self, domain: str) -> OperatingRegime:
        confidence = self.calibrator.get_calibration(domain)
        surprise = self.surprise_detector.ema.get(domain, 0.5)
        data_points = self.world_model.get_data_count(domain)

        current = self._current_regimes.get(domain, OperatingRegime.OBSERVANT)
        margin = self.hysteresis_margin if current != OperatingRegime.OBSERVANT else 0

        if (confidence > self.anticipatory_confidence + margin
                and surprise < self.anticipatory_surprise - margin
                and data_points > self.min_data_points):
            new_regime = OperatingRegime.ANTICIPATORY
        elif (confidence < self.curious_confidence - margin
                or (surprise > self.curious_surprise + margin and data_points < 10)):
            new_regime = OperatingRegime.CURIOUS
        else:
            new_regime = OperatingRegime.OBSERVANT

        self._current_regimes[domain] = new_regime
        return new_regime
```

**Regime behaviors:**

| Regime | Confidence | Surprise | Hestia's Behavior |
|--------|-----------|---------|-------------------|
| Anticipatory | >0.8 | <0.2 | Quietly does things before asked. Creates draft orders. Pre-stages information. |
| Curious | <0.4 | >0.5 | Asks strategic questions. Proposes hypotheses. Seeks new data sources. |
| Observant | 0.4–0.8 | 0.2–0.5 | Watches and learns. Logs patterns. Builds model silently. No proactive actions. |

### 14.2 Anticipation Executor (~3 days)

**File:** `hestia/learning/anticipation_executor.py`

**When regime = ANTICIPATORY:**
1. PredictionEngine generates prediction with confidence > 0.8
2. AnticipationExecutor evaluates: Is this actionable? Is the cost of being wrong low?
3. If yes: Creates a **draft order** (status: `drafted`) for Andrew to approve
4. If the action is very low-risk (e.g., pre-fetching calendar data): execute silently

**Risk classification:**
```python
class ActionRisk(str, Enum):
    SILENT = "silent"      # Pre-fetch data, prepare briefing sections
    DRAFT = "draft"        # Create draft order for approval
    SUGGEST = "suggest"    # Mention in briefing or next interaction
    NEVER = "never"        # Never auto-execute (send email, delete files, etc.)

# Risk mapping (updated per audit 2026-03-03)
# Audit finding: summarize_emails moved DRAFT → SUGGEST (auto-generating email
# summaries without consent is too permissive). Only truly read-only, zero-side-effect
# operations should be SILENT.
ACTION_RISK = {
    "fetch_calendar": ActionRisk.SILENT,
    "prepare_briefing": ActionRisk.SILENT,
    "summarize_emails": ActionRisk.SUGGEST,   # Was DRAFT — too permissive
    "schedule_reminder": ActionRisk.SUGGEST,
    "send_email": ActionRisk.NEVER,
    "delete_file": ActionRisk.NEVER,
    "create_order": ActionRisk.DRAFT,         # Auto-suggested orders need approval
    # Granular settings risk (replaces blanket "modify_settings: NEVER")
    # 2026-03-04: All start as SUGGEST. Auto-apply gated on CorrectionConfidence
    # scoring framework (see Sprint 13.4). Promotion to SILENT requires validated
    # correction data from OutcomeTracker.
    "update_display_setting": ActionRisk.SUGGEST,     # timezone, date format
    "update_behavioral_setting": ActionRisk.SUGGEST,  # default mode, verbosity
    "update_security_setting": ActionRisk.NEVER,      # auth, biometric — always manual
    "update_system_setting": ActionRisk.NEVER,        # model, provider — always manual
}
```

**Integration with Orders:** Auto-generated draft orders appear in Command → Orders → Scheduled with `drafted` status and a "🤖 Auto-suggested" tag. Andrew can approve (→ scheduled) or dismiss.

### 14.3 Command Center Regime Visualization (~2 days)

**New component:** `macOS/Views/Command/RegimeIndicator.swift`

Shows current operating regime per domain in the contextual metrics area:

```
┌──────────────────────────────┐
│  Operating Regimes            │
│                               │
│  📧 Email:     🟢 Anticipatory│  ← Hestia knows your email habits
│  📅 Schedule:  🟢 Anticipatory│  ← Calendar well-understood
│  💻 Coding:    🟡 Observant   │  ← Learning your coding style
│  🏥 Health:    🔵 Curious     │  ← Asking questions to understand
│  📊 Finance:   🔵 Curious     │  ← Insufficient data yet
└──────────────────────────────┘
```

### 14.4 Curiosity Questions in Chat (~2 days)

When regime = CURIOUS for a relevant domain and context is appropriate:

```
┌──────────────────────────────────────────────────────┐
│  💡 Hestia is curious:                                │
│                                                        │
│  "I've noticed you've been spending more time on       │
│  health data endpoints but haven't mentioned fitness    │
│  goals recently. Is there a connection I should         │
│  understand?"                                          │
│                                                        │
│  [Answer]  [Not now]  [Don't ask about this]          │
└──────────────────────────────────────────────────────┘
```

**Rules for surfacing questions:**
- Max 1 curiosity question per day
- Never during focus mode or quiet hours
- Respect "Don't ask about this" dismissals (stored as negative signal)
- Prefer to append to daily briefing rather than interrupt chat

**API endpoints (Sprint 14):**
```
GET  /v1/learning/regimes              → Per-domain operating regime
POST /v1/learning/anticipate           → Trigger anticipation check (manual)
GET  /v1/learning/suggestions          → Auto-generated draft orders
POST /v1/learning/curiosity/{id}/dismiss  → Dismiss a curiosity question
```

---

## Testing Plan

### Sprint 13
| Area | Test Count | Type |
|------|-----------|------|
| WorldModel layer updates | 5 | Unit |
| WorldModel abstract layer updated monthly (NOT daily) | 1 | Unit |
| WorldModel routine layer updated weekly | 1 | Unit |
| WorldModel situational updated per-interaction | 1 | Unit |
| EMA belief updater (was Bayesian) | 4 | Unit |
| EMA numerical stability (NaN, infinity, division by zero) | 3 | Unit |
| EMA cold start (empty domain history) | 1 | Unit |
| EMA concurrent update safety | 1 | Unit |
| PredictionEngine generation + scoring | 5 | Unit |
| SurpriseDetector EMA computation | 4 | Unit |
| CuriosityDrive ranking | 4 | Unit |
| CuriosityDrive question generation with empty knowledge gaps | 1 | Unit |
| CuriosityDrive questions grounded in observables (not abstract) | 1 | Integration |
| Learning API endpoints | 3 | API |
| Write settings tools — risk classification | 3 | Unit |
| Write settings tools — NEVER-risk blocked | 2 | Security |
| Write settings tools — SUGGEST queues for approval | 2 | Integration |
| CorrectionConfidence scoring (urgency, impact, security, frequency) | 3 | Unit |
| **Subtotal** | **~45** | |

### Sprint 14
| Area | Test Count | Type |
|------|-----------|------|
| RegimeSelector classification | 5 | Unit |
| RegimeSelector hysteresis (no rapid switching) | 3 | Unit |
| RegimeSelector configurable thresholds | 2 | Unit |
| AnticipationExecutor risk classification | 4 | Unit |
| AnticipationExecutor NEVER-risk actions blocked | 3 | Security |
| AnticipationExecutor risk for unknown action type | 1 | Unit |
| Draft order auto-generation | 4 | Integration |
| Curiosity question generation | 3 | Integration |
| Regime visualization data | 2 | UI |
| Dismissal handling + persistence | 3 | API |
| **Subtotal** | **~30** | |

## SWOT (Combined 13+14)

| | Positive | Negative |
|---|---|---|
| **Strengths** | Most theoretically principled (neuroscience + info theory). Naturally produces all 3 desired behaviors (anticipation, self-evaluation, curiosity). Hierarchical world model matches cognitive structure. Three regimes directly answer Andrew's design goals. Math is explainable and tunable. | Highest theoretical complexity. Bayesian inference on 7B model outputs needs approximation. World model abstraction layers are hard to get right. Risk of premature anticipation if model overfits. |
| **Opportunities** | Active inference is frontier AGI research. If implemented well, Hestia becomes a research contribution. Foundation for everything else (fine-tuning, multi-modal, long-term planning). | No off-the-shelf implementation exists. Computational cost of continuous world model updates. Systematic model errors → systematic behavioral errors. Academic elegance ≠ practical utility. |

## Definition of Done (Sprint 13)

- [ ] WorldModel with 3 layers persisted in SQLite, updating at correct frequencies
- [ ] EMA belief updater (not Bayesian) — numerically stable, handles edge cases
- [ ] AbstractLayer.communication_style populated via versioned extraction prompt from MIND.md
- [ ] PredictionEngine generating pre-interaction predictions, logged and scored
- [ ] SurpriseDetector computing per-domain prediction error (quadratic, no complexity penalty)
- [ ] CuriosityDrive ranking domains by expected information gain
- [ ] CuriosityDrive questions grounded in concrete observables (not abstract model metrics)
- [ ] Learning API endpoints returning real-time data
- [ ] Write settings tools with tiered risk classification (SUGGEST for display/behavioral, NEVER for security/system)
- [ ] CorrectionConfidence scoring framework implemented (urgency/impact/security/frequency)
- [ ] Suggested corrections surface in `/research/principles` view with `source=correction` tag
- [ ] All tests passing (existing + ~45 new)

## Definition of Done (Sprint 14)

- [ ] Three operating regimes (anticipatory/curious/observant) functional
- [ ] Regime thresholds configurable via `config/learning.yaml` (not hardcoded)
- [ ] Regime switching includes hysteresis (no rapid flapping between regimes)
- [ ] AnticipationExecutor creating draft orders for high-confidence predictions
- [ ] AnticipationExecutor: `summarize_emails` = SUGGEST (not DRAFT), NEVER-risk actions blocked
- [ ] Curiosity questions surfaced in briefing (max 1/day, respects interruption policy)
- [ ] Regime indicator visible in Command Center
- [ ] "Don't ask about this" dismissal working and persisted
- [ ] "Was this proactive action helpful?" feedback button implemented
- [ ] All tests passing (existing + ~30 new)
