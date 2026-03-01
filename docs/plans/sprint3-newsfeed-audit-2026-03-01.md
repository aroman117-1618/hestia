# Plan Audit: Sprint 3 — Command Center / Newsfeed
**Date:** 2026-03-01
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary

Build a unified newsfeed aggregation module (backend) + rewrite the iOS Command Center from a 3-tab layout to BriefingCard + FilterBar + NewsfeedTimeline. New tables are user-aware from day one (`user_id` column, defaulting to `"user-default"`), enabling cross-device read/dismiss state synchronization without migrating existing tables. Estimated 2 sessions (~12 hours).

## SWOT

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** All data sources already built and tested (orders, proactive, memory, health, tasks). Manager + route pattern battle-tested across 8 modules. User-aware design avoids future rewrite. Materialized cache prevents N+1 query storms. | **Weaknesses:** Order execution listing requires per-order iteration (no bulk cross-order query). TaskManager has no time-bound filter. BriefingGenerator is slow (2-5s with weather API + AppleScript). No offline/cache strategy on iOS for newsfeed items. |
| **External** | **Opportunities:** Newsfeed is the natural home for future push notification routing — item creation could trigger APNs. BriefingCard could eventually become a widget (iOS WidgetKit). Filter bar pattern reusable for Explorer. | **Threats:** AppleScript CLI calls may fail on Mac Mini without GUI session. Weather API dependency adds external failure point to aggregation. 30s cache TTL means stale data during rapid user actions (approve memory, then refresh timeline). |

---

## CISO Review
**Verdict:** Acceptable

- **Acceptable:**
  - Auth on all endpoints via `Depends(get_device_token)` — no new unauthenticated surfaces
  - `user_id` hardcoded to constant — no user enumeration vector until multi-user ships
  - Error handling follows `sanitize_for_log(e)` pattern
  - No new credential handling, external communication, or data export paths
  - Read/dismiss state is audit-logged with `acted_on_device_id`

- **Minor:**
  - C1: The `POST /v1/newsfeed/refresh` endpoint is a potential abuse vector (forces expensive aggregation). **Condition:** Add rate limiting (e.g., 1 refresh per 10 seconds per device).
  - C2: Item IDs in the format `orders:exec-abc123` expose internal source naming. Low risk but consider opaque IDs if multi-tenant later.

- **Recommendation:** Proceed. No new attack surface. Rate limit the refresh endpoint.

---

## CTO Review
**Verdict:** Approve with Conditions

- **Acceptable:**
  - Module follows established manager pattern exactly (models.py + database.py + manager.py)
  - `asyncio.gather(return_exceptions=True)` for resilient aggregation — proven pattern from BriefingGenerator and ExplorerManager
  - Materialized cache prevents polling-induced load
  - User-scoped state table with composite PK is clean schema design
  - 40-50 test target is appropriate

- **Critical:**
  - T1: **Order execution aggregation is O(active_orders)** — each active order requires a separate `list_executions()` call. With 20+ orders this could bottleneck. **Condition:** Add a bulk `list_recent_executions(since, limit)` method to OrderManager/Database that queries across all orders in one SQL statement. This is a small database.py change (single SQL query with JOIN) that eliminates the per-order iteration.
  - T2: **Auth dependency name mismatch** — Plan says `get_current_device` but primary function is `get_device_token`. `get_current_device` is a deprecated alias (line 315 of auth.py). **Condition:** Use `get_device_token` in new routes for consistency.
  - T3: **Cache staleness after user actions** — If user approves a memory review, the cached timeline still shows the old item for up to 30s. **Condition:** `mark_read()` and `mark_dismissed()` should invalidate the relevant cached item (update in-place in `newsfeed_items` table) rather than waiting for full re-aggregation. Memory approval happens via the existing `/v1/memory/approve` endpoint, not through newsfeed — so the newsfeed state and the source state can diverge. Accept this for MVP; document as known limitation.
  - T4: **No database cleanup/retention** — `newsfeed_items` table will grow unbounded. **Condition:** Add a `_cleanup_old_items()` method that deletes items older than 30 days, called during `_aggregate_all()`.

- **Recommendation:** Approve with T1 (bulk execution query) and T4 (retention cleanup) as build-time conditions. T2 is a naming fix. T3 is acceptable for MVP with documentation.

---

## CPO Review
**Verdict:** Acceptable

- **Acceptable:**
  - Transforms a tab-juggling dashboard into a unified timeline — clear UX upgrade
  - BriefingCard at top addresses the "morning glance" use case — high user value
  - Cross-device read state is a premium feel for a personal assistant
  - Preserves all existing functionality (orders CRUD, memory review, neural net)
  - macOS scope is appropriately minimal (wire real data into existing stat cards)

- **Minor:**
  - P1: **No empty state design specified** — What does the timeline show when there are zero items? First-time user experience matters. **Condition:** Design an empty state with a friendly message and suggestion to create an order or review the briefing.
  - P2: **Neural Net placement** — Moving it below the timeline may bury it. Consider whether it should become its own tab or be accessible via a toolbar button. Low priority — current placement is fine for MVP.
  - P3: **RSS dropped from original Sprint 3 scope** (SPRINT.md line 66 mentions "RSS via feedparser + APScheduler"). This is the right call for scope discipline, but should be explicitly noted as deferred.

- **Recommendation:** Proceed. Delivers clear user value. Empty state is the only gap to address at build time.

---

## Sequencing Issues

The two-session split is well-structured:
- **Session 1 (backend)** has zero iOS dependencies — can be fully tested via curl
- **Session 2 (iOS/macOS)** depends on Session 1 being complete and the server running

**Parallelization opportunity:** Within Session 1, the models + database can be built and tested before the manager (which depends on them). Route file depends on manager. Tests can be written alongside each layer.

**Critical path:** Manager aggregation logic is the riskiest piece — it has the most dependencies (5 source managers) and the most complex mock setup in tests. Build and test this before routes.

---

## Quality Gates

| Milestone | Gate |
|-----------|------|
| Models + Database | 18-20 tests pass (serialization + CRUD + state) |
| Manager | 30-35 tests pass (add aggregation + cache + resilience) |
| Routes | 40-50 tests pass (add endpoint contracts) |
| Full backend | `python -m pytest` all green, `curl` verification |
| iOS models + VM | Both schemes compile |
| iOS views | Both schemes compile, visual inspection in simulator |
| macOS updates | Both schemes compile |
| Final | Full test suite + both builds + manual timeline check |

Test strategy is solid: unit tests for models, integration tests for database, mock-based tests for manager, and HTTP-level tests for routes. No end-to-end test (server + real managers), which is acceptable given the mock coverage.

---

## Single Points of Failure

| SPOF | Impact | Mitigation |
|------|--------|------------|
| BriefingGenerator latency (2-5s) | iOS shows loading spinner, feels slow | BriefingCard loads independently from timeline (separate async call). Timeline renders immediately; briefing populates when ready. |
| One aggregator throws | Entire timeline empty | Already mitigated by `return_exceptions=True` — plan correctly handles this |
| SQLite file corruption (newsfeed.db) | Timeline unusable | Standard SQLite journal mode handles this. Worst case: delete file, re-aggregate on next request. |
| macOS build breaks | Blocks session completion | macOS changes are minimal (3 files). Build early, not last. |

---

## Final Critiques

1. **Most likely failure:** Order execution aggregation performance. With many orders, iterating per-order is slow. **Mitigation:** T1 condition — add bulk `list_recent_executions()` to OrderManager. If that's too invasive, cap at 10 most recent active orders during aggregation.

2. **Critical assumption:** That the existing proactive briefing endpoint works correctly when called from iOS. It's been built but **never called from any client**. If the response format has issues or the endpoint errors, the BriefingCard is dead on arrival. **Validation:** During Session 1, manually `curl` the briefing endpoint and verify the response parses correctly. Fix any issues before Session 2.

3. **Half-time cut list:** If we had one session instead of two:
   - **Keep:** Backend module + tests + iOS NewsfeedViewModel + NewsfeedTimeline (core value)
   - **Cut:** BriefingCard (use existing greeting), FilterBar (show all items), macOS updates (leave stat cards hardcoded), NeuralNet repositioning (leave in old position)
   - **Result:** Timeline works, just without the polish layers

---

## Conditions for Approval

| ID | Condition | Type | Owner |
|----|-----------|------|-------|
| T1 | Add bulk `list_recent_executions(since, limit)` to OrderManager to avoid per-order iteration | Build-time | Backend |
| T2 | Use `get_device_token` (not `get_current_device`) in all new routes | Build-time | Backend |
| T4 | Add 30-day retention cleanup to newsfeed database | Build-time | Backend |
| C1 | Rate limit `/v1/newsfeed/refresh` (1 per 10s per device) | Build-time | Backend |
| P1 | Design empty state for timeline (zero items) | Build-time | iOS |
| V1 | Manually verify `/v1/proactive/briefing` response before building BriefingCard | Validation | Session 1 |
