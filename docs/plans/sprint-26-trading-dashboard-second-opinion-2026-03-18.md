# Second Opinion: Sprint 26 — Trading Dashboard
**Date:** 2026-03-18
**Models:** Claude Opus 4.6 (internal) + Gemini 2.5 Pro (external)
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary
Sprint 26 adds a fully wired trading monitoring dashboard to Hestia. 6 workstreams (~20h): decision trail persistence, satisfaction scoring, SSE streaming endpoint, watchlist CRUD, macOS Trading tab wiring, and Discord/push alerting. Builds on Sprints 21-25 (241 tests, 12 endpoints, full execution pipeline).

## Scale Assessment
| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|----------------|-------------------|
| Single user | Yes | None | — |
| Family (2-5) | Mostly | SSE stream per user needs user-scoped event bus; watchlist/trades already user_id scoped | Low (~4h) |
| Community | No | Event bus doesn't scale past ~20 concurrent SSE connections; SQLite contention | High (~40h, needs Redis pub/sub + PostgreSQL) |

## Front-Line Engineering
- **Feasibility:** High — every component extends an existing pattern (SSE from chat, ViewModel from other macOS views, notifications from Sprint 20C)
- **Hidden prerequisites:**
  - `trades` table needs `ALTER TABLE ADD COLUMN decision_trail TEXT, satisfaction_score REAL` — migration required
  - New `watchlist` table creation
  - `risk_state` table already added in today's review fixes — no additional migration needed
  - **REST endpoints for positions/portfolio** — Gemini correctly identified these are missing and the SSE plan depends on them
- **Testing gaps:** SSE long-lived connections are hard to unit test. Need integration test with `httpx.AsyncClient` + `text/event-stream` parsing. Event bus cleanup on disconnect needs explicit test coverage.
- **Effort realism:** 20h is realistic. WS5 (macOS wiring, 6h) is the riskiest estimate — SwiftUI SSE parsing + reconnection logic adds complexity beyond simple REST calls.

## Architecture Review
- **Fit:** Follows Hestia's patterns — new ViewModel, new endpoints on existing router, manager pattern, YAML config
- **Data model:** Decision trail as JSON blob is acceptable for v1. Gemini recommends a hybrid (JSON + normalized table). **Resolution: JSON blob for Sprint 26, normalize in Sprint 29 when ML optimization needs analytical queries.**
- **Integration risk:** Low — trading module is self-contained. SSE endpoint follows proven chat streaming pattern. Event bus is new but isolated.
- **API design:** Consistent with existing patterns. New endpoints: `GET /v1/trading/stream` (SSE), `GET /v1/trading/trades/{id}/trail`, `GET /v1/trading/positions` (NEW — from Gemini), `GET /v1/trading/portfolio` (NEW — from Gemini), watchlist CRUD (4 endpoints)

## Product Review
- **User value:** High — monitoring is essential before go-live (Sprint 30). Can't deploy real money without a dashboard.
- **Scope:** Right-sized for ~20h. WS4 (watchlist) is the weakest value-add pre-go-live but is only 2h.
- **Opportunity cost:** Not building Sprint 27 (portfolio strategies) or Sprint 30 (go-live). Dashboard is the correct next step — can't validate strategies without observability.

## UX Review
- **Design system:** TradingMonitorView already uses MacColors, MacSpacing, CollapsibleSection. Consistent.
- **Interaction model:** Portfolio snapshot → positions → trades (expandable trail) → risk → kill switch. Clear hierarchy.
- **Empty states:** Already handled in placeholder (emptyListState helper with icon + message + detail). Good.
- **Platform:** macOS only for Sprint 26. iOS deferred. No divergence to manage.
- **Location:** Trading lives in Command Center → External tab (Activity Feed restructure from concurrent session). Not a new sidebar icon. This is correct — trading is one of several external data sources, not a top-level navigation concern during paper trading.

## Infrastructure Review
- **Deployment impact:** ALTER TABLE migration for `decision_trail` + `satisfaction_score` columns. New `watchlist` table. Server restart required.
- **New dependencies:** None. Discord webhook uses stdlib `aiohttp` (or existing `httpx`). No new packages.
- **Monitoring:** SSE connection count should be logged. Event bus queue depth should be observable. Risk state persistence (already implemented) provides restart recovery.
- **Rollback:** Clean — new columns are additive (NULL default), new table can be dropped, SSE endpoint can be removed from router.
- **Resource impact:** SSE adds one long-lived connection per client. asyncio.Queue is lightweight (100 events max). Negligible on M1 16GB.

## Executive Verdicts
- **CISO:** Acceptable — Discord webhook URL must not be in version control. Use Keychain from day one (not config file). SSE endpoint must require JWT auth (`Depends(get_device_token)`). Kill switch endpoint already has auth.
- **CTO:** Acceptable with conditions — Add REST endpoints for positions and portfolio (Gemini's point is correct). SSE should deliver deltas, not be the sole state source. JSON blob for decision trails is acceptable for v1 with documented migration path.
- **CPO:** Acceptable — Dashboard is the mandatory prerequisite for go-live. Satisfaction scoring adds learning signal for strategy tuning. Watchlist is low-value but low-cost.

## Final Critiques

### Most Likely Failure
**SSE subscriber leak.** If the `finally` block doesn't properly unsubscribe from the event bus on client disconnect, queues accumulate in memory. Over time (hours/days of trading), this silently consumes RAM.
- **Mitigation:** Explicit `try/finally` with queue removal. Periodic sweep that removes stale queues (no `get()` in 60s). Log subscriber count on each connect/disconnect.

### Critical Assumption
**`TradingMonitorView.swift` mock data structure matches backend models.** The placeholder uses mock values (`hestiaScore: 0.82`, side enums, pair format). If the actual API response schema differs, WS5 (6h) could balloon.
- **Validation:** Compare `TradingMonitorView` mock data shapes against `BotResponse`, `TradeResponse`, `RiskStatusResponse` Pydantic schemas before starting WS5.

### Half-Time Cut List (10h budget)
1. **Keep:** WS1 (decision trail, 3h) + WS3 (SSE, 4h) + WS5 (macOS wiring, 6h → reduce to 3h with REST-only, no SSE in ViewModel)
2. **Cut:** WS2 (satisfaction scoring), WS4 (watchlist), WS6 (Discord alerts)
3. **This reveals:** The core value is observability (see trades, see risk, kill switch). Scoring and alerting are enhancements.

---

## Cross-Model Validation (Gemini 2.5 Pro)

### Gemini's Independent Assessment
**Verdict: APPROVE WITH CONDITIONS**

Gemini assessed the plan as "strong but with several high-impact architectural risks." Key strengths: pragmatic decomposition, good architectural foresight (decision trails + scoring), resource-appropriate choices (SSE over WS, SQLite). Key weaknesses: state management brittleness, short-sighted data schema, superficial initial metrics.

### Where Both Models Agree
- SSE over WebSocket is the right choice for server-to-client trading updates
- Decision trail persistence is high-value and the TradeExecutor audit dict is ready to persist
- TradingMonitorView placeholder is well-structured and reduces UI implementation risk
- Discord webhook should fail-silent and be fully optional
- macOS-first, iOS-deferred is the correct platform strategy
- SSE subscriber cleanup in `finally` block is critical for stability

### Where Models Diverge

| Topic | Claude | Gemini | Resolution |
|-------|--------|--------|------------|
| Decision trail schema | JSON blob in trades table (simple, adequate for v1) | Hybrid: JSON blob + normalized `trade_decision_logs` table | **Claude wins for Sprint 26.** Normalized table is premature — no analytics use case exists yet. Revisit in Sprint 29 when ML optimization needs cross-trade queries. |
| Satisfaction score naming | "Satisfaction score" with retrospective adjustment | Rename to "ConfidenceScore", add separate "OutcomeScore" | **Gemini is right.** Pre-execution confidence ≠ satisfaction. Rename to `confidence_score`. Add `outcome_score` (P&L-based) to daily summary. |
| REST endpoints for positions | Not in original plan (SSE snapshots serve this) | Mandatory `GET /positions` and `GET /portfolio` before SSE | **Gemini is right.** Client needs REST for initial state load, SSE for deltas. Adding 2 endpoints is ~1h and makes the architecture resilient to disconnects. |
| SQLite WAL mode | Not flagged (already on TradingDatabase) | Flagged as critical — needs WAL for concurrent access | **Already resolved.** TradingDatabase enables WAL mode in `connect()` (line 36-38). Gemini missed this existing implementation. |
| Discord webhook storage | Config file initially, Keychain for go-live | Keychain from day one | **Gemini is right.** Config files get committed. Use Keychain from the start — it's the established pattern for all other API keys. |

### Novel Insights from Gemini
1. **No event persistence.** The event bus is ephemeral — events are lost when the server restarts. Persisting events would enable replay debugging and "as-if" backtesting. **Assessment:** Valid but low priority for Sprint 26. Add event logging to the daily summary instead.
2. **Client backpressure gap.** The bounded queue drops oldest events on overflow, but the client has no signal that events were dropped. A slow UI could miss a `kill_switch` event. **Assessment:** Valid concern. Mitigation: critical events (kill_switch, risk_alert) should bypass the bounded queue — use a separate priority channel or direct push notification.
3. **Maximum Adverse Excursion (MAE) for outcome scoring.** Measures how much a trade went against you before becoming profitable. Better than raw P&L for evaluating trade quality. **Assessment:** Excellent suggestion. Include MAE in the outcome score formula for Sprint 27.

### Reconciliation
Both models agree the plan is sound and well-scoped. The key actionable difference is Gemini's insistence on REST endpoints for state (`/positions`, `/portfolio`) — this is correct and adds ~1h of work for significant resilience improvement. The naming correction (confidence_score vs satisfaction_score) is also valid and costs nothing to implement correctly from the start. The normalized decision trail table is premature for Sprint 26 but should be on the Sprint 29 roadmap.

---

## Conditions for Approval

1. **Add REST endpoints for positions and portfolio** — `GET /v1/trading/positions` and `GET /v1/trading/portfolio` (~1h). Client loads state via REST, then subscribes to SSE for deltas.
2. **Rename satisfaction_score to confidence_score** — pre-execution composite metric. Reserve "satisfaction" or "outcome" for the retrospective P&L-based score (Sprint 27).
3. **SSE subscriber cleanup** — explicit `try/finally` with queue removal, periodic stale queue sweep, subscriber count logging.
4. **Critical events bypass bounded queue** — `kill_switch` and `risk_alert` events must be delivered even if the queue is full. Use a separate unbounded priority channel or fall back to push notification.
5. **Discord webhook in Keychain** — not config file. Follow established credential pattern from day one.
6. **Decision trail migration path documented** — JSON blob is acceptable for v1, but document the normalized table design for Sprint 29 ML optimization.

---

## Updated Workstream Estimates (incorporating conditions)

| WS | Scope | Hours | Changes from Original |
|----|-------|-------|-----------------------|
| WS1 | Decision trail persistence + REST positions/portfolio endpoints | 4h | +1h for 2 new REST endpoints |
| WS2 | Confidence scoring (renamed) | 2h | Naming change only |
| WS3 | SSE streaming with priority channel for critical events | 4.5h | +0.5h for priority bypass |
| WS4 | Watchlist CRUD | 2h | Unchanged |
| WS5 | macOS Trading tab wiring (REST-first, SSE for deltas) | 6h | Architecture improvement, same effort |
| WS6 | Alert system (Keychain webhook, push notifications) | 3h | Keychain instead of config file |
| **Total** | | **21.5h** | +1.5h from original 20h |
