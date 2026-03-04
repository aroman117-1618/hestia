# Self-Healing Loop Assessment: Timezone + Settings Tools + Learning Cycle Integration

**Date:** 2026-03-04
**Trigger:** Tia hallucinated "I'll update my system" when correcting timezone — revealed an architectural gap
**Scope:** Full roadmap assessment for folding in self-healing capabilities

---

## The Problem Statement

Tia told Andrew "I'll update my system to ensure it reflects the correct local times" — but she has **zero mechanism** to do this. This revealed three gaps:

1. **Timezone handling is broken** — naive `datetime.now()` throughout, no user timezone propagation
2. **No settings write tools** — Tia can't modify her own configuration
3. **No correction feedback loop** — when Tia gets corrected, the correction doesn't persist

The goal is **Level 3 Self-Healing**: Tia detects her own mistakes, proposes corrections, applies them (with appropriate safety gates), and verifies they worked.

---

## Current Infrastructure Inventory

### What Exists (Building Blocks)

| Component | Sprint | Status | Self-Healing Role |
|-----------|--------|--------|-------------------|
| `USER-IDENTITY.md` timezone field | Pre-Sprint | ✅ Exists | Stores `America/Los_Angeles` — but never read by any service |
| `UserConfigLoader._parse_identity_md()` | Pre-Sprint | ✅ Parses timezone | Extracts timezone string from markdown |
| `UserSettings` dataclass | Sprint 7 | ✅ Exists | **Missing `timezone` field** |
| `OutcomeTracker` | Sprint 10 | ✅ Complete | Tracks explicit (thumbs) + implicit (timing) signals |
| `PrincipleStore` | Sprint 8 | ✅ Complete | Distills + stores principles with approval workflow |
| `ToolRegistry` + native tool calling | Sprint 10.5 | ✅ Complete | Tia can call structured tools via Ollama API |
| `ActionRisk` classification | Sprint 14 | 📋 Planned | `modify_settings: NEVER` — needs reconsideration |
| `MetaMonitor` | Sprint 11 | 📋 Planned | Confusion loops, acceptance trends, latency spikes |
| `ConfidenceCalibrator` | Sprint 11 | 📋 Planned | Per-domain accuracy tracking |
| `KnowledgeGapDetector` | Sprint 11 | 📋 Planned | Surfaces questions in daily briefing |
| `WorldModel` | Sprint 13 | 📋 Planned | Hierarchical belief model (abstract/routine/situational) |
| `CuriosityDrive` | Sprint 13 | 📋 Planned | Information-theoretic question ranking |
| `RegimeSelector` | Sprint 14 | 📋 Planned | Anticipatory/Curious/Observant modes |
| `AnticipationExecutor` | Sprint 14 | 📋 Planned | Draft orders for high-confidence predictions |

### What's Missing (The Gaps)

| Gap | Impact | Where It Should Go |
|-----|--------|-------------------|
| **Timezone on `UserSettings`** | All time-dependent features are wrong | Pre-Sprint 11 (immediate) |
| **Timezone-aware datetime in calendar/reminders** | "Today" boundary incorrect | Pre-Sprint 11 (immediate) |
| **Timezone in scheduler/orders** | Orders run at wrong times | Pre-Sprint 11 (immediate) |
| **Timezone in quiet hours** | Quiet hours evaluated in UTC | Pre-Sprint 11 (immediate) |
| **Timezone in briefing greeting** | "Good morning" at wrong time | Pre-Sprint 11 (immediate) |
| **Read-only settings tools** | Tia can't introspect her own config | Sprint 11 (with MetaMonitor) |
| **Write settings tools (safety-gated)** | Tia can't correct her own config | Sprint 13 or 14 (with safety framework) |
| **Outcome → Principle batch pipeline** | Corrections don't become knowledge | Sprint 11 (with MetaMonitor) |
| **Correction-type outcome classification** | Can't distinguish "wrong timezone" from "bad tone" | Sprint 11 (OutcomeTracker enhancement) |

---

## Recommended Integration Plan

### Phase 0: Timezone Fix (Immediate — Before Sprint 11)
**Effort: ~3 hours | No new modules | 6 files touched**

This is a bug fix, not a feature. Do it now.

| File | Change |
|------|--------|
| `hestia/user/models.py` | Add `timezone: str = "America/Los_Angeles"` to `UserSettings` |
| `hestia/user/config_loader.py` | Add `get_user_timezone() -> str` that reads from settings → identity → system fallback |
| `hestia/apple/calendar.py` | `datetime.now()` → `datetime.now(ZoneInfo(user_tz))` in `get_today_events()`, `get_upcoming_events()` |
| `hestia/apple/reminders.py` | Same fix in `get_due_today()`, `get_overdue()` |
| `hestia/orders/scheduler.py` | `timezone="UTC"` → `timezone=user_tz` (line 54) |
| `hestia/proactive/briefing.py` | Greeting time-of-day check uses local time |
| `hestia/proactive/policy.py` | QuietHours evaluation uses local time |

**Testing:** 8-10 new tests for timezone conversion edge cases (DST, midnight boundary, UTC offset).

### Sprint 11 Additions (Fold Into Existing Plan)
**Effort: +4 hours on top of existing ~90 hour estimate**

Sprint 11 already has MetaMonitor. Add these self-healing components:

#### 11.A: Read-Only Settings Tools (+1 hour)
Register 3 new tools in `hestia/execution/tools/settings_tools.py`:

```
get_user_settings()     → Returns UserSettings as JSON
get_system_status()     → Returns health check + active providers + model info
get_user_timezone()     → Returns current timezone setting
```

These are **read-only** — Tia can diagnose ("your timezone is set to Pacific") but not change anything yet. Registered in `register_builtin_tools()`.

#### 11.B: Outcome → Principle Batch Pipeline (+2 hours)
**New file:** `hestia/learning/outcome_pipeline.py`

Connects the two existing systems:
1. Query OutcomeTracker for negative outcomes (last 7 days, `feedback=negative` or `implicit_signal=quick_followup`)
2. Group by domain/topic
3. Feed grouped corrections into `PrincipleStore.distill_principles()`
4. Run daily (alongside MetaMonitor hourly analysis)

This is the **missing link** — corrections become principles, principles affect future responses.

#### 11.C: Correction Classification Enhancement (+1 hour)
Add `correction_type` to OutcomeRecord metadata:
- `timezone` — time-related correction
- `factual` — wrong information
- `preference` — style/tone/format preference
- `tool_usage` — wrong tool or wrong arguments

Detected via simple keyword matching on the follow-up message ("that's EST not PST", "no, I meant...", "the time is wrong").

### Sprint 13 Revision: Add Write Settings Tools
**Effort: +2 hours on top of existing estimate**

Sprint 13 introduces the WorldModel and safety framework. This is where **write-access settings tools** should live, because the safety infrastructure (risk classification, confidence thresholds) is being built here.

#### Tiered Settings Write Access

| Setting Category | Risk Level | Gate | Example |
|-----------------|------------|------|---------|
| **Display preferences** | SILENT | None — apply immediately | timezone, date format, greeting style |
| **Behavioral preferences** | SUGGEST | Surface in briefing, apply on confirmation | default mode, temperature, verbosity |
| **Security settings** | NEVER | Always manual | auth timeout, biometric requirements |
| **System settings** | NEVER | Always manual | model selection, provider config |

Revise Sprint 14's `ActionRisk` mapping:
```python
ACTION_RISK = {
    # Existing...
    "modify_settings": ActionRisk.NEVER,          # DELETE this blanket rule
    # Replace with granular:
    "update_display_setting": ActionRisk.SILENT,   # timezone, date format
    "update_behavioral_setting": ActionRisk.SUGGEST,# default mode, verbosity
    "update_security_setting": ActionRisk.NEVER,   # auth, biometric
    "update_system_setting": ActionRisk.NEVER,     # model, provider
}
```

#### New Tool: `update_user_setting()`
```python
async def update_user_setting(key: str, value: str) -> Dict:
    """Update a user setting. Respects risk classification."""
    risk = get_setting_risk(key)
    if risk == ActionRisk.NEVER:
        return {"error": "This setting cannot be changed automatically"}
    if risk == ActionRisk.SUGGEST:
        # Queue for briefing/confirmation
        return {"status": "queued", "message": f"I'll suggest changing {key} to {value} in your next briefing"}
    # SILENT — apply immediately
    apply_setting(key, value)
    return {"status": "applied", "key": key, "value": value}
```

### Sprint 14: Self-Healing Loop Closes
**No additional effort — already planned, just ensure integration**

With all components in place:
1. **Tia notices a mistake** → OutcomeTracker records negative signal with correction_type
2. **Outcome → Principle pipeline** distills "Andrew is in EST, not PST" into a principle
3. **MetaMonitor detects pattern** — "3 timezone corrections in 7 days"
4. **CuriosityDrive** doesn't need to ask — it's a known correction
5. **AnticipationExecutor** sees timezone setting mismatch, calls `update_user_setting(timezone=...)` with SILENT risk
6. **Next interaction** uses correct timezone automatically

The loop is closed. Tia self-heals.

---

## Integration Map (Visual)

```
NOW (Phase 0)                    SPRINT 11                         SPRINT 13                SPRINT 14
─────────────                    ─────────                         ─────────                ─────────

Fix datetime.now()  ──────────── MetaMonitor ──────────────────── WorldModel ──────────── RegimeSelector
  in calendar.py                   │                                  │                        │
  reminders.py                     ├─ Read Settings Tools             ├─ Write Settings    AnticipationExecutor
  scheduler.py                     │    (diagnose)                    │    Tools (apply)      │
  briefing.py                      │                                  │    (tiered risk)      │
  policy.py                        ├─ Outcome→Principle               │                       │
                                   │    Pipeline                      │                       │
Add timezone to ──────────────     │    (corrections→knowledge)       │                       │
  UserSettings                     │                                  │                       │
                                   ├─ Correction Classification       │                       │
                                   │    (what type of mistake?)       │                       │
                                   │                                  │                       │
                                   ├─ ConfidenceCalibrator            ├─ SurpriseDetector     │
                                   │    (accuracy tracking)           │    (prediction error)  │
                                   │                                  │                       │
                                   └─ KnowledgeGapDetector            └─ CuriosityDrive       │
                                        (what don't I know?)               (what should        │
                                                                            I ask?)             │
                                                                                               │
                                                                                          SELF-HEALING
                                                                                          LOOP CLOSED
```

---

## What Changes in the Master Roadmap

| Sprint | Original Scope | Added |
|--------|---------------|-------|
| Pre-11 | (none) | **Phase 0: Timezone fix** (~3 hours) |
| 11 | MetaMonitor + Command Center | **+11.A** Read settings tools, **+11.B** Outcome→Principle pipeline, **+11.C** Correction classification (+4 hours) |
| 13 | WorldModel + Prediction + Surprise + Curiosity | **+Write settings tools** with tiered risk (+2 hours) |
| 14 | Regimes + Anticipation + Curiosity Questions | **Revise** `ActionRisk` for granular settings (minimal effort — just config) |

**Total additional effort: ~9 hours** across 4 phases. Not a new sprint — woven into existing ones.

---

## Decision Points for Andrew

1. **Phase 0 timing:** Do the timezone fix now (this session) or park it for Sprint 11 prep?
2. **Write settings risk level:** Should `timezone` be SILENT (auto-apply) or SUGGEST (confirm first)?
3. **Outcome → Principle pipeline frequency:** Daily batch (recommended) or real-time per-correction?
4. **Sprint 14 `modify_settings` revision:** Accept the granular risk tiering, or keep blanket NEVER?

---

## Sources

- [Self-Healing AI Systems & Adaptive Autonomy](https://www.msrcosmos.com/blog/self-healing-ai-systems-and-adaptive-autonomy-the-next-evolution-of-agentic-ai/)
- [OpenAI Self-Evolving Agents Cookbook](https://cookbook.openai.com/examples/partners/self_evolving_agents/autonomous_agent_retraining)
- [REFLEX Architecture (Self-Improving AI Agent)](https://medium.com/@nomannayeem/lets-build-a-self-improving-ai-agent-that-learns-from-your-feedback-722d2ce9c2d9)
- Hestia Master Roadmap: `docs/plans/sprint-7-14-master-roadmap.md`
- Sprint 11 Plan: `docs/plans/sprint-11-command-center-plan.md`
- Sprint 13-14 Plan: `docs/plans/sprint-13-14-learning-cycle-plan.md`
