# Research Tab Development Plan (v2 — Gemini-Reconciled)

**Date:** 2026-03-18
**Sprint:** 20 (Neural Net Graph Phase 2)
**Scope:** Graph quality framework, source expansion, principles pipeline, notification relay, tooling
**Gemini Review:** Incorporated — DIKW alignment, durability scoring, staged extraction, Log-to-Graph model, visual weight mapping, retroactive crystallization

---

## Executive Summary

The Research tab is the knowledge intelligence layer of Hestia. This plan addresses six workstreams across two sprint phases:

**Phase A (Sprint 20):**
1. **Insight Quality Framework** — DIKW-aligned tiered classification with durability scoring
2. **Principles Pipeline** — Fix empty state, wire auto-distillation, verify full flow
3. **Memory Tab UI Polish** — Sort toggle fix, spacing cleanup
4. **Graph Visual Weight System** — Perceptual mapping for significance/confidence/recency

**Phase B (Sprint 20.5 or 21-adjacent):**
5. **Graph Source Expansion** — Imported Knowledge + External Research categories
6. **Intelligent Notification Relay** — Context-aware bumps to macOS or iPhone

**Tooling (parallel, independent):**
7. **Gemini CLI integration** — Second-opinion pipeline for Artemis
8. **/second-opinion skill** — Replaces /plan-audit (superset)

---

## WS1: Insight Quality Framework (Gemini-Reconciled)

### Synthesis: Claude + Gemini Recommendations

Both analyses converge on the same core architecture: **aggressive pre-filtering with a searchable safety net.** Gemini's "Log-to-Graph" model validates our Memory-as-staging approach — store everything in the searchable index (Memory tab), only promote to the 3D graph what passes the quality gate.

Key Gemini additions incorporated:

| Finding | Impact | Incorporated As |
|---------|--------|-----------------|
| DIKW hierarchy alignment | Naming clarity | Tiers renamed: Ephemeral → Contextual → Durable → Principled |
| Durability score (0-3 numeric) | Richer scoring | New `durability_score` field on facts (0=ephemeral, 1=dynamic, 2=static, 3=atemporal) |
| Modified importance formula | Better ranking | `S = 0.2R + 0.2F + 0.3T + 0.3D` — durability replaces half of type bonus weight |
| Staged extraction (3-phase) | Better for 9B models | Entity ID → Significance filter → Triple extraction pipeline |
| PRISM prompt pattern | Structured output | Persona/Reasoning/Inputs/Sections/Metrics template |
| Retroactive crystallization | Serendipity safety net | Weekly community detection on ephemeral cluster; auto-promote if pattern emerges |
| False negatives > false positives | Philosophy alignment | Aggressive gate with undo path (Memory tab always has everything) |
| Temporal property types | Schema enrichment | Atemporal/Static/Dynamic/Ephemeral as explicit fact metadata |

### Revised Tier System (DIKW-Aligned)

| Tier | DIKW Level | Durability Score | Graph Treatment | Examples |
|------|-----------|-----------------|-----------------|----------|
| **Principled** | Wisdom | 3 (Atemporal) | Largest nodes, highest weight, never decays | "Andrew prefers async over meetings", "Always version APIs with /v1/ prefix" |
| **Durable** | Knowledge | 2 (Static) | Full-size nodes, standard weight | "Hestia uses Qwen 3.5 9B", "Andrew's Mac Mini is M1 16GB" |
| **Contextual** | Information | 1 (Dynamic) | Small nodes, low opacity, decays | "Sprint 16 built memory lifecycle", "ZoomInfo role assessed Q4 2025" |
| **Ephemeral** | Data | 0 (Ephemeral) | **Excluded from graph.** Searchable in Memory only. | "Looking at Figma mockups", "Let me assess the fit" |

### Revised Importance Formula

**Current:** `importance = 0.3 * recency + 0.4 * retrieval_frequency + 0.3 * type_bonus`

**Revised:** `importance = 0.2 * recency + 0.2 * retrieval_frequency + 0.3 * type_bonus + 0.3 * durability_score`

Where `durability_score` is normalized to 0-1 (raw 0-3 divided by 3). This ensures ephemeral observations (durability=0) get a 0.3 penalty, while atemporal principles (durability=3) get a 0.3 boost — they naturally separate.

### Staged Extraction Pipeline (3-Phase)

Replace the single-prompt approach with a decomposed pipeline optimized for 9B models:

**Phase 1: Entity Identification**
```
List all named entities in this text. For each, classify as:
- person, tool, concept, place, project, organization
Output JSON: {"entities": [{"name": "...", "type": "..."}]}
```

**Phase 2: Significance Filter**
```
For each entity, determine if it is a CORE ACTOR (directly relevant to the user's
knowledge, decisions, or relationships) or BACKGROUND DETAIL (mentioned incidentally).
Only CORE ACTORS proceed to triple extraction.
Output JSON: {"core": ["Entity1", "Entity2"], "background": ["Entity3"]}
```

**Phase 3: Triple Extraction (PRISM Pattern)**
```
PERSONA: You are a rigorous knowledge librarian. Only extract facts that belong
in a permanent knowledge base.

REASONING: Before extracting, assess: Is this fact durable (true in 30 days)?
Is it specific (names concrete entities)? Is it non-obvious?

INPUTS: Core entities: {core_entities}. Text: {content}. Current date: {date}.

SECTIONS: Return exactly:
{
  "triples": [{
    "source": "...", "source_type": "...",
    "relation": "SCREAMING_SNAKE_CASE",
    "target": "...", "target_type": "...",
    "fact": "natural language sentence",
    "confidence": 0.0-1.0,
    "durability": 3|2|1|0,
    "temporal_type": "atemporal|static|dynamic|ephemeral"
  }]
}

METRICS: Assign confidence reflecting your certainty. Durability: 3=always true,
2=true for months/years, 1=true for weeks, 0=true only now.
Skip entirely if text is procedural or thinking-out-loud.
Max 5 triples.
```

### Schema Changes

#### Add to `facts` table

```sql
ALTER TABLE facts ADD COLUMN durability_score INTEGER DEFAULT 1;
ALTER TABLE facts ADD COLUMN temporal_type TEXT DEFAULT 'dynamic';
ALTER TABLE facts ADD COLUMN source_category TEXT DEFAULT 'conversation';
ALTER TABLE facts ADD COLUMN import_source_id TEXT;
```

#### Add to `entities` table

```sql
ALTER TABLE entities ADD COLUMN first_seen_source TEXT DEFAULT 'conversation';
```

### Retroactive Crystallization (Gemini's "Weak Ties" Safety Net)

Weekly background task in `LearningScheduler`:

1. Scan ephemeral facts (durability=0) that are >7 days old
2. Run community detection (existing label propagation) on their entity connections
3. If 3+ ephemeral facts cluster around the same entity pair → auto-promote cluster to durability=1 (contextual)
4. Log promotion in learning alerts for user visibility

This catches patterns that individually seem ephemeral but collectively reveal something durable. Gemini's key insight: the risk of aggressive gating is losing "weak ties" — this is the mitigation.

### Backend Implementation

| File | Changes |
|------|---------|
| `hestia/research/models.py` | Add `durability_score`, `temporal_type`, `source_category` to `Fact` dataclass |
| `hestia/research/database.py` | ALTER TABLE migrations, update queries |
| `hestia/research/fact_extractor.py` | Replace single prompt with 3-phase pipeline, add PRISM template |
| `hestia/research/graph_builder.py` | Filter ephemeral (durability=0) from graph, map durability to node visual weight |
| `hestia/memory/importance.py` | Update formula: `0.2R + 0.2F + 0.3T + 0.3D` |
| `hestia/config/memory.yaml` | Add durability weights to importance config |
| `hestia/learning/scheduler.py` | Add retroactive crystallization task (weekly) |

### Estimated Effort

- 3-phase extraction pipeline: 3 hours
- Schema + model changes: 1 hour
- Importance formula update: 1 hour
- Graph builder durability filter: 1 hour
- Retroactive crystallization: 2 hours
- Ingest quality filter: 1 hour
- Retroactive cleanup script: 2 hours
- Tests: 2 hours
- **Total: ~13 hours**

---

## WS2: Principles Pipeline Fix + Auto-Distillation

### Diagnosis

Architecture is fully wired end-to-end. Most likely cause of empty state: no distillation has ever been triggered. The `principles` table is empty because `POST /v1/research/principles/distill` has never been called.

### Verification Steps

1. `curl -k https://localhost:8443/v1/research/principles` — confirm empty
2. `curl -k -X POST https://localhost:8443/v1/research/principles/distill` — trigger
3. Verify principles appear in API + macOS UI

### Auto-Distillation

Add to `LearningScheduler` (weekly, Sunday 3am). Config in `memory.yaml`:

```yaml
principle_distillation:
  enabled: true
  interval_days: 7
  time_range_days: 14
  day_of_week: 0
  hour: 3
```

### Estimated Effort: ~3 hours

---

## WS3: Memory Tab UI Polish

Sort toggle fix: externalize Picker label, add `.labelsHidden()`, widen frame. Plus spacing audit on filter pills, pagination buttons, chunk row cards.

### Estimated Effort: ~2 hours

---

## WS4: Graph Visual Weight System (New — from Gemini)

Gemini's perceptual mapping research recommends explicit visual encoding for three dimensions:

| Visual Property | Maps To | Perceptual Basis |
|----------------|---------|------------------|
| Node diameter | Durability score | Immediate focus on "hub" concepts |
| Node opacity | Confidence score | Drowns out unreliable facts |
| Glow intensity | Recency | Highlights active areas |
| Position (cluster tightness) | Semantic relatedness | Gestalt proximity principle |

### Implementation

In `MacSceneKitGraphView.swift`, update node rendering:

```swift
// Current: uniform node sizing based on blended weight
// New: multi-dimensional visual encoding
let diameter = 0.1 + (durabilityScore / 3.0) * 0.2     // 0.1-0.3 range
let opacity = 0.3 + confidenceScore * 0.7                // 0.3-1.0 range
let glowIntensity = recencyScore * 0.8                    // Fades with age
```

Also update `GraphControlPanel.swift` to add a "Significance" filter slider that hides nodes below a durability threshold.

### Estimated Effort: ~3 hours

---

## WS5: Graph Source Expansion

(Unchanged from v1 — see previous plan for full detail)

New `SourceCategory` enum, `import_sources` table, file import + paste/ingest UI, 3 provider importers (Claude existing, ChatGPT/Gemini new), Memory tab staging workflow.

### Estimated Effort: ~18 hours

---

## WS6: Intelligent Notification Relay

### Vision

When any Claude Code session on Andrew's MacBook needs approval/input, Hestia routes a notification intelligently:
- **MacBook active** → macOS notification center (NSUserNotification)
- **MacBook idle >2 min** → APNs push to iPhone with actionable approve/deny

### Current Infrastructure (40% Built)

**What exists:**
- Push token registration endpoints (`POST/DELETE /v1/user/push-token`)
- Push token SQLite table with device_id, environment (production/sandbox)
- Notification permission request in iOS onboarding
- `APIClient.registerPushToken()` in iOS
- Interruption policy engine (quiet hours, Focus mode, busy calendar checks)
- Proactive briefing generator (content ready, delivery missing)

**What's missing:**
- APNs client (no library to actually send pushes)
- iOS `registerForRemoteNotifications()` call (permission requested but token never captured)
- `UNUserNotificationCenter` delegate (no handling of received notifications)
- macOS notification sending
- Activity detection (idle time check)
- Approval request/response API flow

### Architecture

```
Claude Code session hits decision point
  ↓
POST /v1/notifications/bump
{
  "session_id": "...",
  "title": "Approval Needed",
  "body": "Deploy to Mac Mini?",
  "actions": ["approve", "deny"],
  "context": { "command": "deploy", "target": "production" },
  "callback_id": "uuid"
}
  ↓
NotificationRouter checks idle state
  ↓
┌─ MacBook active (<2min since last input event)
│  → macOS NSUserNotificationCenter / UNUserNotificationCenter
│  → User clicks → POST /v1/notifications/{callback_id}/respond
│
└─ MacBook idle (>2min)
   → APNs push to iPhone
   → iOS actionable notification (force-touch: Approve / Deny)
   → iOS posts → POST /v1/notifications/{callback_id}/respond
  ↓
Claude Code session polls GET /v1/notifications/{callback_id}/status
  → Returns: pending | approved | denied | expired
```

### Idle Detection

```python
# macOS idle time via IOKit (called from Python via subprocess)
# ioreg -c IOHIDSystem | grep HIDIdleTime
# Returns nanoseconds since last input event

async def get_idle_seconds() -> float:
    result = await asyncio.create_subprocess_exec(
        "ioreg", "-c", "IOHIDSystem",
        stdout=asyncio.subprocess.PIPE
    )
    stdout, _ = await result.communicate()
    # Parse HIDIdleTime from output
    match = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', stdout.decode())
    if match:
        return int(match.group(1)) / 1_000_000_000  # ns → seconds
    return 0.0

IDLE_THRESHOLD_SECONDS = 120  # 2 minutes
```

### Guardrails (Intelligent, Not Annoying)

| Rule | Implementation |
|------|----------------|
| **Rate limit** | Max 1 bump per 5 minutes per session. Queue excess, deliver when approved/denied. |
| **Quiet hours** | Respect existing `PushNotificationSettings.quiet_hours` config. No bumps 10pm-8am unless critical. |
| **Batch similar** | If 3+ bumps queue within 60 seconds, consolidate into one notification: "3 items need your attention" |
| **Escalation, not spam** | First attempt: macOS notification. If no response in 60s AND idle: escalate to iPhone. Never both simultaneously. |
| **Session awareness** | If user responds to one bump from a session, suppress further bumps from that session for 10 minutes (they're probably about to engage). |
| **Focus mode** | Check macOS Focus mode. If enabled, delay non-critical bumps until Focus ends. |
| **Expiry** | Bumps expire after 15 minutes. Stale approvals are dangerous. |

### New Backend Module: `hestia/notifications/`

```
hestia/notifications/
├── models.py          # BumpRequest, BumpResponse, BumpStatus, NotificationRoute
├── database.py        # bump_requests table (callback_id, status, created_at, responded_at)
├── router.py          # NotificationRouter (idle detection, route decision, rate limiting)
├── apns_client.py     # APNs HTTP/2 client (aioapns or py-apns2)
├── macos_notifier.py  # macOS notification via osascript or UNUserNotificationCenter
└── manager.py         # NotificationManager singleton
```

### New API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/notifications/bump` | POST | Create a new bump request |
| `/v1/notifications/{callback_id}/status` | GET | Poll bump status (for Claude Code) |
| `/v1/notifications/{callback_id}/respond` | POST | Submit response (approve/deny) |
| `/v1/notifications/history` | GET | List recent bumps with status |
| `/v1/notifications/settings` | GET/PUT | Rate limits, quiet hours, idle threshold |

### iOS Changes

1. **Capture device token:** Add `registerForRemoteNotifications()` in `HestiaApp.swift` init
2. **Handle token:** `application(_:didRegisterForRemoteNotificationsWithDeviceToken:)` → call `APIClient.registerPushToken()`
3. **Actionable notifications:** Register `UNNotificationCategory` with "Approve" and "Deny" actions
4. **Handle response:** `UNUserNotificationCenterDelegate.didReceive` → `POST /v1/notifications/{callback_id}/respond`

### Claude Code Integration

Two options (both work, recommend Option A):

**Option A: Hestia CLI command**
```bash
# In Claude Code, call hestia bump command
hestia bump "Deploy to Mac Mini?" --actions approve,deny --wait
# Blocks until response received, returns exit code 0=approved, 1=denied
```

**Option B: Direct API call**
```bash
# Claude Code calls Hestia API directly
CALLBACK_ID=$(curl -sk -X POST https://localhost:8443/v1/notifications/bump \
  -d '{"title":"Approval Needed","body":"Deploy to Mac Mini?","actions":["approve","deny"]}' \
  | jq -r '.callback_id')

# Poll for response
while true; do
  STATUS=$(curl -sk https://localhost:8443/v1/notifications/{$CALLBACK_ID}/status | jq -r '.status')
  [ "$STATUS" != "pending" ] && break
  sleep 5
done
```

### APNs Setup Requirements

1. Apple Developer account with push notification capability
2. APNs auth key (.p8 file) stored in Keychain
3. iOS app bundle ID registered for push
4. Entitlements file updated with `aps-environment` key

### Estimated Effort

- Backend notification module: 4 hours
- APNs client + macOS notifier: 3 hours
- iOS token capture + actionable notifications: 3 hours
- Idle detection + routing logic: 2 hours
- Rate limiting + guardrails: 2 hours
- CLI bump command: 1 hour
- API endpoints: 2 hours
- Tests: 3 hours
- **Total: ~20 hours**

---

## WS7: Gemini CLI Integration + /second-opinion Skill

### Gemini CLI Install

```bash
npm install -g @google/gemini-cli
```

Free tier: 60 req/min, 1,000/day with personal Google account, Gemini 2.5 Pro.

### /second-opinion Skill Design

**Replaces `/plan-audit` entirely.** The new `/second-opinion` skill is a superset — it absorbs all 9 phases of the current plan-audit AND adds an external cross-model validation phase via Gemini CLI. The old `/plan-audit` skill directory gets removed after migration.

#### Replacement Skill: `.claude/skills/second-opinion/SKILL.md`

**Trigger:** `/second-opinion [topic, plan, or file path]`

**Phases 1-9: Internal Audit (carried over from /plan-audit)**
1. Consume the Plan — read context, validate assumptions
2. Scale Assumptions Check — single-user to multi-tenant scalability
3. Front-Line Engineering Review — feasibility, complexity, hidden prerequisites
4. Backend Engineering Lead Review — architecture fit, API design, data models
5. Product Management Review — user value, edge cases, opportunity cost
6. Design/UX Review — design system compliance, interaction models
7. Infrastructure/SRE Review — deployment impact, monitoring, rollback
8. Executive Panel — CISO, CTO, CPO verdicts
9. Sustained Devil's Advocate — counter-plans, regret analysis, stress tests

**Phase 10: Cross-Model Validation (NEW)**
1. **Prompt Construction** — Build a structured research prompt using the plan context + findings from Phases 1-9
2. **Gemini Dispatch** — Shell out to `gemini` CLI with the prompt, capture full response
3. **Response Parsing** — Extract key findings, agreements, disagreements, novel suggestions
4. **Reconciliation Report** — Side-by-side: Claude's verdict vs Gemini's verdict, with synthesis of where they agree, where they diverge, and which divergences are actionable
5. **Final Verdict** — Unified recommendation incorporating both perspectives

**Output:** Saves to `docs/plans/[plan-name]-second-opinion-[date].md` (replaces old `*-audit-*.md` naming)

**Backward Compatibility:** `/plan-audit` command can be kept as an alias that triggers `/second-opinion` — or removed entirely. Andrew's call.

**Gemini Dispatch Implementation:**
```bash
# Pipe structured prompt to gemini CLI, capture output
echo "$PROMPT" | gemini --model gemini-2.5-pro > /tmp/gemini-response.md
# Parse response back into skill flow
```

**Future: Artemis Integration**
Wire Gemini as an inference backend in `CloudInferenceClient` (Google is already one of the 3 cloud providers). Give Artemis the ability to dispatch sub-queries when it detects high-stakes decisions that benefit from cross-model validation. This fits the ADR-042 coordinator-delegate model: Hestia → Artemis for analysis → Artemis optionally consults Gemini. At that point, `/second-opinion` can route through Artemis instead of shelling out directly.

### Estimated Effort

- /second-opinion skill (absorb plan-audit + Phase 10): 3 hours
- Remove old /plan-audit skill: 15 minutes
- Gemini CLI integration testing: 1 hour
- **Total: ~4.25 hours**

---

## Implementation Roadmap

### Sprint 20A (Current — ~21 hours)

| Order | Workstream | Hours | Dependencies |
|-------|-----------|-------|-------------|
| 1 | WS2: Principles Pipeline Fix | 3 | None |
| 2 | WS3: Memory Tab UI Polish | 2 | None |
| 3 | WS1: Insight Quality Framework | 13 | None |
| 4 | WS4: Graph Visual Weight System | 3 | WS1 (durability scores) |

### Sprint 20B (~23.5 hours)

| Order | Workstream | Hours | Dependencies |
|-------|-----------|-------|-------------|
| 5 | WS5: Graph Source Expansion | 18 | WS1 (quality framework) |
| 6 | WS7: Gemini CLI + /second-opinion (replaces /plan-audit) | 4.25 | None (can parallel) |

### Sprint 20C or Standalone (~20 hours)

| Order | Workstream | Hours | Dependencies |
|-------|-----------|-------|-------------|
| 8 | WS6: Notification Relay | 20 | None (independent module) |

### Total Estimated Effort

| Workstream | Hours |
|-----------|-------|
| WS1: Insight Quality Framework | 13 |
| WS2: Principles Pipeline | 3 |
| WS3: Memory Tab UI | 2 |
| WS4: Visual Weight System | 3 |
| WS5: Source Expansion | 18 |
| WS6: Notification Relay | 20 |
| WS7: Gemini CLI + /second-opinion (replaces /plan-audit) | 4.25 |
| **Total** | **63.25 hours (~5 sprint weeks)** |

---

## Open Questions

1. **ChatGPT/Gemini export formats** — Do you have sample export files? Needed for importer development.
2. **APNs credentials** — Do you have an Apple Developer account with push capability? Needed for WS6.
3. **Graph density preference** — Hard cap on visible nodes, or trust filtering?
4. **Retroactive cleanup scope** — All existing insights, or only clearly low-quality?
5. **Notification relay priority** — Should WS6 run in parallel with Sprint 21 (Trading Foundation), or serialize?

---

## Key Architectural Decisions (for ADR consideration)

| Decision | Rationale |
|----------|-----------|
| DIKW-aligned 4-tier classification | Industry-standard, maps cleanly to existing ChunkType system |
| Durability score (0-3) on facts | Numeric enables formula integration; categorical names enable UI labels |
| 3-phase staged extraction | Compensates for 9B model limitations; each phase is narrow + verifiable |
| Log-to-Graph architecture | Memory tab = full log (everything searchable), Graph = curated visualization |
| Retroactive crystallization | Safety net against aggressive gating; catches emergent patterns |
| Notification relay through Hestia | Makes Hestia the notification hub for all AI tooling (future: not just Claude Code) |
| Escalation not duplication | macOS first, iPhone only if idle — never both simultaneously |
