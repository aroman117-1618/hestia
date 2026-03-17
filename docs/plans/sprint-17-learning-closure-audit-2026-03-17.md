# Plan Audit: Sprint 17 — Learning Closure
**Date:** 2026-03-17
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary

Sprint 17 adds two backend components to close the learning feedback loop: a CorrectionClassifier (heuristic keyword matching to categorize user corrections into TIMEZONE/FACTUAL/PREFERENCE/TOOL_USAGE) and an OutcomeDistiller (LLM-powered extraction of behavioral principles from high-signal chat outcomes). Both run as scheduled background loops in LearningScheduler and expose 5 new API endpoints. No iOS/macOS UI changes.

## Scale Assessment

| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|----------------|-------------------|
| Single user | Yes | None | N/A |
| Family (2-5) | Yes | `user_id` scoped throughout. Each user gets own corrections/principles. | Low — already scoped |
| Community | Yes, with config | Scheduler loops run once with `DEFAULT_USER_ID`. Multi-user needs per-user scheduling or batch-all-users pattern. | Medium — refactor loops to iterate users |
| Multi-tenant | No | Single scheduler, single DB path, no tenant isolation | High — but not in roadmap |

**Assessment:** The plan correctly uses `user_id` on all database tables and queries. The only scale gap is the scheduler's `DEFAULT_USER_ID` constant — acceptable for current scope, documented for future.

## Front-Line Engineering

- **Feasibility:** High. Both components are straightforward — the classifier is ~120 lines of regex + keyword matching, the distiller wraps existing PrincipleStore.distill_principles(). No new dependencies.
- **Complexity estimate:** Realistic. 10-14h for both components + tests + API routes tracks with Sprint 16's pace (similar scope, completed in one session).
- **Hidden prerequisites:**
  1. ❌ `OutcomeDatabase.list_outcomes_with_feedback()` — **method doesn't exist**. Plan references it in classifier and distiller. Must use existing `get_outcomes()` + Python-side filtering, or add the method.
  2. ❌ `OutcomeRecord.from_row()` — **method doesn't exist**. Use `from_dict()` instead. `get_outcomes()` returns dicts already.
  3. ⚠️ `ResearchManager.principle_store` — attribute is `_principle_store` (private). Plan should use `research_mgr._principle_store` or the public `distill_principles()` method.
  4. ⚠️ `OutcomeDatabase.get_high_signal_outcomes()` — also doesn't exist yet. Plan correctly notes it should be added.
- **Testing strategy:** Good. Separate test files for each component, fixtures use tmp_path for isolated DB, mocks for inference client and outcome DB. Coverage targets reasonable (80%+).

## Architecture Review

- **Fit:** Excellent. Follows the established manager pattern (class + singleton factory). New files go in `hestia/learning/` where they belong. Database extends LearningDatabase (BaseDatabase subclass). Scheduler integration follows the exact pattern of Sprint 16's loops.
- **Data model:** Clean. Three new tables (`corrections`, `distillation_runs`, `outcome_principles`) with user_id scoping and proper indexes. `corrections.outcome_id UNIQUE` prevents duplicate classification. `outcome_principles` is a proper junction table with lineage tracking.
- **API design:** Consistent with existing `/v1/learning/` endpoints. GET for reads, POST for triggers. Query params for user_id (matching existing pattern). Return envelope `{"data": ...}` is consistent.
- **Integration risk:** Low. Only touches `hestia/learning/` and `hestia/outcomes/database.py` (adding 2 query methods). No changes to handler.py, server.py, or shared infrastructure. The concurrent session's orchestration changes don't conflict.

## Product Review

- **User value:** Indirect but foundational. The correction classifier detects failure patterns. The principle distiller extracts behavioral insights. Neither produces user-visible UI in this sprint, but both produce data that makes Sprint 18-19 UI meaningful. This is the last backend sprint before visible payoff.
- **Scope:** Right-sized. Two tightly related components that compose naturally. Not too big (no UI work), not too small (closes the learning arc).
- **Opportunity cost:** Deferring Neural Net Phase 2 (most visually impressive) and Memory Browser (most immediately useful for debugging). Discovery report argues convincingly that data readiness makes UI premature — data pipeline needs time to accumulate.
- **Edge cases addressed:**
  - Empty data: distiller has `min_outcomes` threshold (default 3), skips gracefully
  - No inference client: distiller returns 0 principles, doesn't crash
  - Duplicate corrections: `INSERT OR IGNORE` on `outcome_id UNIQUE`
  - LLM failure: classifier falls back to heuristic (always available)

## UX Review

N/A — No UI component in this sprint. (The 5 API endpoints will be consumed by future UI work in Sprint 18-19.)

## Infrastructure Review

- **Deployment impact:** Server restart required (new scheduler loops). No database migration script needed — `_init_schema()` uses `CREATE TABLE IF NOT EXISTS` pattern (auto-migration on first connect).
- **New dependencies:** None. Uses existing sqlite, chromadb, and inference infrastructure.
- **Monitoring:** Scheduler loops emit structured logs via `LogComponent.LEARNING`. Correction classification stats and distillation run records are queryable via new API endpoints.
- **Rollback strategy:** Clean. New tables + new files. To rollback: remove the 2 new files, revert scheduler.py changes, and remove routes. Tables are harmless if left in DB (never queried by old code).
- **Resource impact:** Minimal. Correction classifier is pure regex/keyword (microseconds). Distiller runs weekly with cap of 20 outcomes per batch. One LLM inference call per week. No memory or CPU concern on M1.

## Executive Verdicts

- **CISO:** Acceptable — No new credential handling, no external communication, no new attack surface. Correction feedback_note content stays in local SQLite. Principles are stored in existing ChromaDB with same security posture. Error sanitization patterns maintained (`type(e).__name__` in logs, not raw exceptions).

- **CTO:** Acceptable — Architecture follows every established pattern (manager, singleton, BaseDatabase, scheduler loops). Heuristic-first approach is the right call for M1 — avoids inference cost for the common case. The plan correctly defers LLM classification to the M5 era. Two minor API mismatches found (see conditions). The `outcome_principles` junction table is good forward-thinking for principle lineage.

- **CPO:** Acceptable — Three consecutive backend sprints is a concern for user-visible progress, but the learning arc completion is the right priority. The correction classifier + principle distiller produce the data that makes Sprint 18-19 UI meaningful. Without Sprint 17, the Memory Browser and Command Center would launch with empty states. Sequencing is correct: build pipeline → accumulate data → build UI.

## Final Critiques

1. **Most likely failure:** OutcomeDistiller produces low-quality or generic principles ("User likes good responses") because the LLM sees truncated 300-char response excerpts without conversation context. **Mitigation:** The plan's `min_outcomes` threshold (3) and weekly batch schedule means quality can be assessed before the pipeline runs at scale. All principles start as "pending" — user must approve. Add a quality heuristic: reject principles shorter than 10 words or containing only generic terms.

2. **Critical assumption:** The plan assumes `OutcomeDatabase` returns records with `feedback_note` populated when `feedback='correction'`. If the feedback flow doesn't capture notes (e.g., iOS just sends "correction" without a note field), the classifier has no text to classify. **Validation:** Check `OutcomeFeedback` enum and the `/v1/outcomes/{id}/feedback` endpoint to confirm note capture. The `feedback_note` field exists on `OutcomeRecord` — verify the mobile app sends it.

3. **Half-time cut list:** If we had half the time:
   - **Keep:** CorrectionClassifier (4-6h, zero LLM cost, immediate value)
   - **Cut:** OutcomeDistiller (defer to Sprint 18). The distiller needs accumulated data anyway, and the correction classifier alone provides meaningful learning signal.
   - **Cut:** 3 of 5 API endpoints (keep `/corrections` and `/corrections/stats`, defer distillation endpoints)

## Conditions for Approval

1. **Fix API mismatches before implementation:**
   - Add `list_outcomes_with_feedback()` to OutcomeDatabase (or use `get_outcomes()` with filtering)
   - Add `get_high_signal_outcomes()` to OutcomeDatabase
   - Use `OutcomeRecord.from_dict()` not `from_row()` in all code
   - Access PrincipleStore via `research_mgr._principle_store` or use public `distill_principles()` method

2. **Add principle quality gate:** Reject distilled principles shorter than 10 words or that match a blacklist of generic phrases ("user likes", "user wants good", "user prefers correct").

3. **Document the data readiness gate:** Before triggering the first distillation (manual or scheduled), run `SELECT COUNT(*) FROM outcomes WHERE feedback = 'positive' OR implicit_signal = 'long_gap'`. If < 10, defer distillation to next session.

4. **Update scheduler monitor count:** Change `"monitors": 6` to `"monitors": 8` in the log message.
