# Plan Audit: Sprint 15 — MetaMonitor + Memory Health + Trigger Metrics

**Date:** 2026-03-16
**Auditor:** Claude (Opus 4.6)
**Discovery Report:** `docs/discoveries/metamonitor-memory-health-triggers-2026-03-16.md`
**Roadmap Context:** `docs/plans/sprint-7-14-master-roadmap.md`
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary

Sprint 15 introduces Hestia's first self-awareness infrastructure: a MetaMonitor (hourly SQL analysis of outcomes + routing quality), a Memory Health Monitor (daily cross-system diagnostics of ChromaDB + knowledge graph), and a Trigger Metrics system (configurable threshold monitoring injected into daily briefings). All three share a new `hestia/learning/` module with ~70 tests. A prerequisite Chunk 0 decomposes handler.py before adding new hooks.

---

## Phase 2: Scale Assessment

| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|----------------|-------------------|
| Single user | Yes | None — designed for this | N/A |
| Family (2-5) | Mostly | MetaMonitor SQL aggregation needs `user_id` in all queries (already planned). Trigger thresholds are global — would need per-user overrides. learning.db needs user_id scoping. | Low — adding `WHERE user_id = ?` is trivial if done from day one |
| Community (5-20) | Partially | Hourly analysis per-user becomes N hourly jobs. Redundancy sampling (100 random chunks, pairwise cosine) scales as O(n²) — 100 chunks = 4,950 comparisons, fine. But per-user ChromaDB collections would need separate health checks. | Medium — architecture holds but scheduling needs rework |
| Multi-tenant | No | ChromaDB doesn't support multi-tenant isolation natively. SQLite per-tenant would work but isn't designed here. | High — requires ChromaDB rearchitecture |

**Assessment:** The plan correctly targets single-user and incidentally supports family scale if user_id scoping is consistent. No multi-tenant concerns are relevant to Hestia's roadmap.

**Flag:** Ensure `learning.db` tables include `user_id` columns from day one. The discovery report mentions `user_id-scoped` for routing audit but doesn't explicitly confirm it for `monitor_reports`, `health_snapshots`, or `trigger_log` tables. This must be explicit in the schema.

---

## Phase 3: Front-Line Engineering Review

### Feasibility
**Assessment: Highly feasible.** Every data source the plan reads from already exists (outcomes.db, routing_audit, ChromaDB, research.db). Every scheduling mechanism exists (APScheduler via Orders). Every integration point has a clear pattern (briefing sections, tool registration).

The explorer validated all 8 technical assumptions:
- `OutcomeRecord.metadata` is a `Dict[str, Any]` stored as JSON — chunk IDs fit directly
- `MemorySearchResult` has `chunk.id` accessible post-search
- Routing audit DB has indexed `(user_id, timestamp)` for fast joins
- APScheduler supports hourly via `CronTrigger` or `IntervalTrigger`
- BriefingGenerator has a section builder pattern ready for `_add_system_alerts_section()`

### Hidden Prerequisites
1. **handler.py decomposition (Chunk 0)** — correctly identified as prerequisite. ~2,440 lines currently. Extracting `handle_agentic()` (~300 lines) and `_try_orchestrated_response()` (~150 lines) is mechanical but must be done carefully — these methods have complex state dependencies on `self._memory_manager`, `self._inference_client`, etc.

2. **`retrieval_count` migration** — WS2 proposes adding a `retrieval_count` column to memory SQLite. This is a schema migration that needs the standard `ALTER TABLE` pattern used elsewhere (e.g., `revoked_at` on `registered_devices`). Not mentioned in the implementation order — should be explicit in WS2 task list.

3. **`agent_route` and `route_confidence` on outcomes** — The discovery assumes these exist. The explorer confirmed they do (added in Sprint 14). Good.

4. **LogComponent enum** — New `hestia/learning/` module needs a `LEARNING` LogComponent. The CLAUDE.md new module checklist requires this. Not mentioned in the discovery.

### Complexity Assessment
- **WS1 (MetaMonitor):** The confusion loop detection is the only non-trivial algorithm. Routing quality correlation and acceptance trend are straightforward SQL GROUP BY queries. Estimated 5 days is reasonable.
- **WS2 (Memory Health):** Redundancy estimation via pairwise cosine similarity is the heaviest computation. Sampling 100 chunks → 4,950 comparisons. At ~0.1ms per comparison, this is ~0.5s total. Fine for daily batch. 3 days is reasonable.
- **WS3 (Trigger Metrics):** Thin YAML config + threshold check + briefing injection. 2 days might be generous — this could be 1 day.
- **Outcome Pipeline + Correction + Settings:** 3 days combined is tight if `PrincipleStore.distill_principles()` needs LLM calls. Need to confirm whether the pipeline is pure SQL or requires inference.

### Testing Strategy
70 tests across 6-7 workstreams. Test distribution seems reasonable. Key testing challenges:
- **MetaMonitor confusion loop detection** — needs realistic multi-turn conversation fixtures with mixed signals. Risk of testing the happy path and missing edge cases.
- **Trigger cooldown logic** — time-dependent tests need careful mocking of `datetime.now()`.
- **Briefing injection** — integration test needed: trigger fires → alert stored → briefing includes it. Unit tests alone won't catch wiring bugs.

---

## Phase 4: Architecture Review

### Architecture Fit
**Good.** New `hestia/learning/` module follows the established manager pattern (`models.py` + `database.py` + manager files). Singleton via `get_X_manager()` async factory. Consistent with all other modules.

### API Design
Proposed endpoints:
- `GET /v1/monitor/report` — latest MetaMonitor report
- `GET /v1/monitor/routing-quality` — route comparison stats
- `GET /v1/monitor/memory-health` — latest health snapshot
- `GET /v1/monitor/memory-health/history?days=30` — health trend
- `GET /v1/system/metrics` — current system metrics

**Concern:** The `/v1/monitor/` prefix is new. Existing patterns use `/v1/{resource}/` (e.g., `/v1/research/`, `/v1/proactive/`). Consider `/v1/learning/` to match the module name. Alternatively, `/v1/monitor/` is acceptable if it's understood as the API namespace for all Sprint 15+ observability.

**Recommendation:** Use `/v1/learning/` for consistency with the module name. The route module should be `hestia/api/routes/learning.py`.

### Data Model
- `learning.db` with 3 tables (`monitor_reports`, `health_snapshots`, `trigger_log`) is clean
- Report retention (7 days hourly → daily for 90 days) needs a consolidation job — who runs it? Should be self-cleaning (e.g., `_cleanup_old_reports()` called at the start of each hourly run)
- `trigger_log` needs `cooldown_until` or `last_fired_at` to implement the 30-day cooldown suppression

### Integration Points
| Integration | Risk | Notes |
|-------------|------|-------|
| handler.py → outcome tracking (chunk IDs) | Low | ~1-line change to existing `track_response()` call |
| Orders → MetaMonitor hourly job | Low | APScheduler pattern well-established |
| Orders → Memory Health daily job | Low | Same pattern |
| Orders → Trigger daily job | Low | Same pattern |
| BriefingGenerator → System Alerts section | Low | Section builder pattern matches existing code |
| Outcome Pipeline → PrincipleStore | Medium | Needs clarification on whether `distill_principles()` calls LLM |

### Dependency Risk
No new Python packages needed. All computation uses SQLite, ChromaDB client, and existing managers. Zero dependency risk.

---

## Phase 5: Product Review

### User Value
**Assessment: Indirect but real.** Sprint 15 doesn't deliver a feature Andrew will interact with daily. Its value is systemic:

1. **Retrieval feedback loop** — invisible to the user but directly improves memory quality in Sprint 16
2. **Trigger alerts in briefing** — visible, actionable, but infrequent (by design: 30-day cooldown)
3. **Routing quality analysis** — invisible but adjusts orchestrator thresholds that affect every conversation

The risk is building infrastructure that produces no visible improvement for months. The mitigation is correct: trigger alerts in the briefing provide periodic visible value, and the retrieval feedback loop starts collecting data immediately.

### Edge Cases
- **Empty data:** MetaMonitor runs with 0 outcomes → should return report with `status: "insufficient_data"`, not error. Minimum sample sizes must be enforced.
- **First-time setup:** All three monitors need graceful handling of empty databases. No health snapshots exist yet → first run establishes baseline, not "100% degradation."
- **Offline / server restart:** Hourly jobs should survive server restarts (APScheduler persistence). Verify whether current Orders/APScheduler configuration persists jobs across restarts or re-registers them at startup.

### Multi-Device
Not directly relevant — Sprint 15 is backend-only. The API endpoints work from any client. Health snapshots and reports are per-user, not per-device.

### Opportunity Cost
While building Sprint 15, we are NOT building:
- Sprint 16 (Memory Lifecycle) — but Sprint 15 is its prerequisite
- Sprint 17 (Graph RAG Lite) — could theoretically start independently, but SYNTHESIS intent detection is better designed with MetaMonitor data
- Sprint 18 (Command Center) — needs MetaMonitor data to display

Sprint 15 is on the critical path. There's no shortcut.

### Scope
**Right-sized.** Three loosely-coupled workstreams with clear deliverables. The "additional items" (outcome pipeline, correction classification, settings tools) could be cut without losing the core value. Good scoping.

---

## Phase 6: UX Review

**Skipped** — Sprint 15 has no UI component. API endpoints only. Command Center visualization is Sprint 18.

---

## Phase 7: Infrastructure Review

### Deployment Impact
- **Server restart required:** Yes — new module, new routes, new scheduled jobs
- **Database migration:** New `learning.db` file (auto-created). Plus `retrieval_count` column migration on existing memory SQLite
- **Config change:** New `config/triggers.yaml` file
- **New scheduled jobs:** 3 (MetaMonitor hourly, Memory Health daily, Trigger check daily)

### New Dependencies
None. All computation uses existing Python stdlib + SQLite + ChromaDB client.

### Monitoring
The irony: Sprint 15 IS the monitoring. But who monitors the monitor?
- MetaMonitor errors should be logged via `get_logger()` with `LogComponent.LEARNING`
- Scheduled job failures should not crash the server — wrap in try/except with error logging
- Health endpoint (`/v1/ready`) should include learning module status

### Rollback Strategy
**Clean.** `hestia/learning/` is a new module with no upstream dependencies. Removing it requires:
1. Delete `hestia/learning/` directory
2. Remove route registration from `server.py`
3. Remove scheduled job registration from server lifecycle
4. Remove chunk attribution line from handler.py

The chunk attribution in outcome metadata is the only change to existing code. It's a single metadata key — removing it has zero side effects.

### Resource Impact
- **CPU:** MetaMonitor hourly: ~100ms (SQL aggregation). Memory Health daily: ~500ms (pairwise similarity). Trigger daily: ~10ms. Total: negligible.
- **Memory:** No new models loaded. SQLite connections are lightweight.
- **Storage:** learning.db with 7 days of hourly reports + 90 days of daily summaries. ~50KB/report × 168/week × 4 + 90 daily = ~40MB/year. Negligible.

**Verdict: No resource concerns on M1 16GB.**

---

## Phase 8: Executive Verdicts

### CISO Review
**Verdict: Acceptable**

Sprint 15 is read-only analytics over existing data. No new credential handling. No new communication paths. No new external data sources.

Specific checks:
- `learning.db` contains aggregate statistics, not raw user content — low sensitivity
- Trigger alerts go into the briefing (existing authenticated channel) — no new attack surface
- MetaMonitor reads from outcomes and routing audit — both already user_id-scoped
- No new LLM calls means no new prompt injection surface (unless Outcome Pipeline calls `distill_principles()` — clarify)

One concern: **Correction classification** uses keyword matching on follow-up message content. If the matched keywords are stored in `metadata["correction_type"]`, this is fine. If the raw message content is stored in trigger alerts or reports, that could leak user content into monitoring infrastructure. **Condition: correction classifier should store type labels only, not raw content.**

### CTO Review
**Verdict: Acceptable with minor conditions**

Architecture is sound. The plan follows established patterns, introduces no new dependencies, and has a clean rollback strategy. Technical assumptions are validated.

Conditions:
1. **API namespace:** Use `/v1/learning/` not `/v1/monitor/` — consistency with module name
2. **Report self-cleanup:** MetaMonitor must clean up old reports during each run, not rely on a separate job
3. **LogComponent.LEARNING:** Must be added to the enum before any code is written
4. **user_id scoping:** All learning.db tables must include `user_id` from day one
5. **Clarify Outcome Pipeline inference:** Does `distill_principles()` call LLM? If yes, the "no inference calls" claim for the learning module doesn't hold for this sub-workstream

### CPO Review
**Verdict: Acceptable**

Sprint 15 is correctly positioned as infrastructure with systemic value. The trigger alerts in briefings provide periodic visible value. The retrieval feedback loop is the single most important deliverable.

Priority ordering is correct: chunk attribution → memory health → MetaMonitor → triggers → pipeline → corrections. The "additional items" (outcome pipeline, correction classification, settings tools) are correctly positioned as nice-to-have and can be cut if velocity drops.

The cold-start concern is real but not blocking — MetaMonitor with confidence scores and minimum sample sizes is honest infrastructure, not premature optimization.

---

## Phase 9: Sustained Devil's Advocate

### 9.1 The Counter-Plan

**Alternative: Skip MetaMonitor entirely. Build Sprint 16 (Memory Lifecycle) directly with manual observation.**

The argument: Sprint 15's MetaMonitor produces hourly reports that nobody reads. The retrieval feedback loop (chunk attribution) is the only part that Sprint 16 actually needs. So build ONLY the retrieval feedback loop (~1 day) and memory health metrics (~2 days), skip MetaMonitor and triggers entirely, and go straight to Sprint 16's importance scoring and consolidation.

**Why it's appealing:**
- Saves ~7 days (MetaMonitor + Triggers + Pipeline + Corrections)
- Gets to Sprint 16 faster (the first sprint with visible memory improvement)
- The "monitoring before data" objection is strongest against MetaMonitor specifically

**Why it's wrong:**
- MetaMonitor's routing quality analysis is the ONLY mechanism to validate the Sprint 14 orchestrator. Without it, we have no data on whether ARTEMIS/APOLLO routing is actually improving responses. We'd be building Sprint 17 (Graph RAG Lite, which feeds SYNTHESIS → ARTEMIS) without knowing if ARTEMIS routing works.
- Trigger metrics are thin (~1-2 days) and provide the activation mechanism for the entire research brief. Cutting them saves almost no time.
- The outcome pipeline connects outcomes to PrincipleStore — this is Sprint 19's training data. Building it early is correct sequencing.

**Verdict: Counter-plan is weaker.** The retrieval feedback loop alone doesn't validate the orchestrator. MetaMonitor is the validation mechanism.

**However:** If velocity is a concern, the half-time cut list (9.4.3) identifies what to defer.

### 9.2 Future Regret Analysis

**3 months (Sprint 16-17 timeframe):**
- If MetaMonitor produces "insufficient data" reports for 3 months, it'll feel like dead infrastructure. **Mitigation:** The confidence-gated reporting makes this transparent rather than misleading.
- If trigger thresholds are wrong, Andrew may disable alerts after 2-3 false positives. **Mitigation:** Start with very few triggers (3-4) and 30-day cooldowns. Better to under-alert.

**6 months (Sprint 18-19 timeframe):**
- The `hestia/learning/` module will have grown. Sprint 19 (Active Inference) will add World Model, Prediction Engine, Surprise Detector to it. If the module boundary between "monitoring" and "learning" isn't clean, we'll regret putting everything in `learning/`. **Mitigation:** Sprint 19 should evaluate whether `hestia/learning/` should split into `hestia/monitoring/` (read-only analytics) and `hestia/learning/` (predictive models). Flag this now.

**12 months (Anticipatory Autonomy era):**
- Sprint 19 replaces MetaMonitor's heuristic thresholds with mathematical prediction error tracking. MetaMonitor becomes legacy code. **This is expected and acceptable** — MetaMonitor is a scaffold, not an end state. The data it collects (outcome-chunk correlations, routing quality history) survives the transition. The analysis code doesn't need to.

### 9.3 The Uncomfortable Questions

**"Do we actually need this?"**
The retrieval feedback loop: yes, unambiguously. Sprint 16 can't function without chunk attribution data.
MetaMonitor: yes, because it's the only validation mechanism for the Sprint 14 orchestrator.
Trigger metrics: marginal. The research brief could remain a static document for 6 more months without consequence. But at ~1-2 days of effort, the ROI is acceptable.
Outcome Pipeline: useful but deferrable. PrincipleStore distillation doesn't need to happen in Sprint 15.

**"Are we building this because it's valuable, or because it's interesting?"**
The MetaMonitor architecture (hourly SQL analysis, routing quality correlation, confusion detection) is genuinely interesting. But it's also genuinely necessary — without it, the orchestrator runs on static thresholds forever, with no data-driven adjustment. The interest and the value align.

**"What's the cost of doing nothing?"**
- No chunk attribution → Sprint 16 importance scoring has no signal → memory consolidation is guesswork
- No routing quality data → orchestrator thresholds never improve → ARTEMIS/APOLLO routing may be hurting instead of helping, and we'd never know
- No memory health baseline → Sprint 16 can't demonstrate improvement

The cost of doing nothing is flying blind on the intelligence infrastructure era.

**"Who benefits?"**
Future Andrew benefits from better memory retrieval (Sprint 16), validated routing (MetaMonitor), and active system monitoring (triggers). Current Andrew benefits from trigger alerts in briefings. The value chain is real but delayed.

### 9.4 Final Stress Tests

**1. Most likely failure: MetaMonitor produces noise, not signal, due to low data volume.**

The MetaMonitor runs hourly but may have only 5-10 new outcomes per day (single user, ~12hr/week). With 7-day rolling windows, analyses run on ~35-70 data points. Statistical significance is low.

*Mitigation:* Minimum sample size gates (n ≥ 20 per analysis category). Reports include confidence indicators. MetaMonitor is honest about its uncertainty. This is more of a "delayed value" than a "failure" — the data will eventually accumulate.

**2. Critical assumption: The retrieval feedback loop assumption — that chunk IDs from memory search are the same chunks that influence the response.**

This assumption could be wrong. The LLM receives context with memory chunks embedded, but may ignore some and fixate on others. We can't know which chunks actually influenced the response without attention analysis (not available via Ollama API). We're logging "chunks that were in context" and correlating with outcome quality, but the true causal chain is: chunks in context → LLM attention → response quality → user signal.

*Validation:* Accept this as a proxy metric. Industry RAG evaluation uses the same proxy (chunks retrieved, not chunks attended to). The correlation between "chunks present" and "response quality" is imperfect but actionable. Sprint 17's Graph RAG Lite quality comparison will provide a natural A/B test.

**3. Half-time cut list: If we had half the time, what would we cut?**

Keep:
- Chunk 0 (handler.py decomposition) — prerequisite, non-negotiable
- WS2 retrieval feedback loop (chunk attribution) — highest ROI
- WS2 memory health metrics — Sprint 16 prerequisite
- WS1 MetaMonitor routing quality analysis — orchestrator validation

Cut:
- WS3 Trigger metrics — defer to Sprint 18 when Command Center can display them
- Outcome Pipeline — defer to Sprint 16 or 17
- Correction classification — defer
- Settings tools — defer

This reduces Sprint 15 to ~6-7 days and ~35 tests while preserving the core value: chunk attribution + memory health baselines + routing quality validation.

---

## Conditions for Approval

The plan is approved with these conditions:

### Must-Have (before implementation starts)
1. **Add `LEARNING` to `LogComponent` enum** — new module checklist item
2. **All `learning.db` tables must include `user_id` column** — multi-user readiness from day one
3. **API namespace: `/v1/learning/`** not `/v1/monitor/` — consistency with module name
4. **Clarify whether `distill_principles()` calls LLM** — affects resource and security assessment
5. **Correction classifier stores type labels only, not raw message content** — security posture

### Should-Have (during implementation)
6. **`retrieval_count` migration** must be explicit in WS2 task list
7. **Report self-cleanup** in MetaMonitor (clean old reports during each hourly run)
8. **Minimum sample size gates** (n ≥ 20) on all MetaMonitor analyses
9. **Integration test** for full trigger flow: threshold crossed → alert stored → briefing includes it
10. **`auto-test.sh` mapping** for `hestia/learning/` → `tests/test_learning*.py`

### Nice-to-Have (defer if velocity drops)
11. Outcome → Principle pipeline (can wait for Sprint 16)
12. Correction classification (can wait for Sprint 16)
13. Read-only settings tools (can wait for Sprint 18)

### Future Flag
14. **At Sprint 19 planning:** evaluate whether `hestia/learning/` should split into `hestia/monitoring/` (read-only analytics) and `hestia/learning/` (predictive models)

---

## Risk Summary

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Cold-start noise | High | Low | Confidence-gated reporting, minimum sample sizes |
| Confusion loop false positives | Medium | Low | Require negative signals, not just turn count |
| handler.py decomposition breaks things | Low | High | Chunk 0 is mechanical extraction + full test suite |
| Trigger alert fatigue | Low | Medium | 3-4 triggers only, 30-day cooldowns |
| MetaMonitor becomes dead code at Sprint 19 | Expected | Low | Data survives, analysis code is scaffolding |
| PrincipleStore LLM calls in batch pipeline | Medium | Medium | Clarify before building; if yes, add rate limiting |

---

## Approval Decision

**APPROVE WITH CONDITIONS.**

Sprint 15 is correctly positioned on the critical path. The technical assumptions are validated. The architecture follows established patterns. The resource impact is negligible. The cold-start concern is real but mitigated by honest confidence reporting. The 5 must-have conditions address the audit's findings without changing the plan's scope or direction.

The half-time cut list (keep chunk attribution + memory health + routing quality; cut triggers + pipeline + corrections) provides a fallback if velocity drops. This is a well-designed sprint with clear value for the intelligence infrastructure era.

Proceed to implementation planning.
