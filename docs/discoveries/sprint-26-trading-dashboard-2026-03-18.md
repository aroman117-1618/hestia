# Discovery Report: Sprint 26 — Trading Dashboard

**Date:** 2026-03-18
**Confidence:** High
**Decision:** Build Sprint 26 as 6 workstreams: SSE streaming endpoint, decision trail storage, satisfaction scoring, watchlist, macOS Trading tab wiring, and Discord/push alerting. Target ~20h across 1-2 sessions.

## Hypothesis

Sprint 26 should deliver a fully wired monitoring dashboard for the Hestia trading module, replacing the placeholder `TradingMonitorView.swift` with live data from the backend. The sprint should add SSE streaming for real-time trade/P&L updates, decision trail audit logging, trade satisfaction scoring, a watchlist, and Discord webhook alerting — all surfaced in the macOS app (and iOS later).

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Solid foundation (241 tests, 12 endpoints, full execution pipeline with audit trail already in `TradeExecutor`). Existing SSE pattern proven in chat streaming (`/v1/chat/stream`). macOS placeholder `TradingMonitorView.swift` already has the visual structure (portfolio snapshot, trade rows, decision trail expansion, satisfaction gauge, risk card, kill switch). Notification module (Sprint 20C) provides push + macOS local notification infrastructure. | **Weaknesses:** No SSE endpoint exists yet for trading. No `decision_trail` table — audit data only lives transiently in `execute_signal()` return dict. No satisfaction scoring logic. No watchlist storage. TradingMonitorView is 100% static mock data. No ViewModel for trading (unlike every other macOS view). |
| **External** | **Opportunities:** Discord webhooks are trivial (~20 lines, HTTP POST). SSE for trading is well-established pattern. Trade quality scoring (multi-factor confidence) is emerging best practice in crypto bot space. Decision trail visualization is a differentiator vs. black-box bots. | **Threats:** SSE connections on mobile can be dropped by iOS backgrounding — need reconnection logic. Discord rate limits (30 msg/min per webhook). Over-alerting causes alert fatigue (classic problem). SSE memory pressure if many events queue during disconnection. |

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | SSE streaming endpoint (`/v1/trading/stream`), Decision trail persistence (new DB table + TradeExecutor integration), macOS TradingMonitorView wiring to live API data + ViewModel | Watchlist CRUD (simple but lower value until live trading) |
| **Low Priority** | Satisfaction scoring (composite quality metric per trade), Discord webhook alerts | iOS Trading tab (deferred — macOS first, iOS can wait for Sprint 30 polish) |

## Argue (Best Case)

**Why this sprint is well-positioned:**

1. **TradeExecutor already produces full audit trails.** Every `execute_signal()` call returns a dict with `pipeline_steps` (risk validation result, price validation result, exchange execution result). The decision trail UI in the placeholder already visualizes exactly this structure (Signal → Strategy → Risk Check → Market → Hestia). Persisting this to SQLite is a straightforward `INSERT`.

2. **SSE pattern is proven.** The chat streaming endpoint (`/v1/chat/stream`) demonstrates the exact `StreamingResponse` + `async def event_generator()` + `text/event-stream` pattern. Trading SSE is simpler — no complex handler pipeline, just periodic state snapshots + event-driven trade notifications.

3. **macOS placeholder is remarkably complete.** `TradingMonitorView.swift` already has:
   - Portfolio snapshot card (total value, 24h P&L, open positions)
   - Trade rows with expandable decision trail
   - Satisfaction gauge (circular progress indicator)
   - Risk status card with traffic light + metrics
   - Kill switch button
   - `CollapsibleSection` pattern for Active Positions and Watchlist
   - The mock data structure mirrors the backend models exactly

4. **Notification infrastructure exists.** Sprint 20C built `NotificationManager` with macOS osascript notifications, APNs push, rate limiting, and routing. Discord webhooks are a simple extension — just an HTTP POST to a webhook URL.

5. **The 12 existing endpoints cover most data needs.** Bot CRUD, trade history, tax lots, daily summaries, risk status, kill switch, backtest — the ViewModel just needs to call these REST endpoints and pipe the data to SwiftUI.

## Refute (Devil's Advocate)

**Why this could go wrong:**

1. **SSE complexity may be underestimated.** Trading SSE is different from chat SSE:
   - Chat SSE has a natural lifecycle (request → stream → done). Trading SSE is long-lived — potentially hours/days.
   - Need heartbeat pings to detect dropped connections.
   - Need client-side reconnection with state catch-up (what happened while disconnected?).
   - Memory pressure: if the client disconnects but the async generator keeps running, events queue in memory.
   - **Mitigation:** Use a pub/sub pattern (asyncio.Queue per connection) with bounded buffer. Send periodic heartbeat events. Client reconnects with `Last-Event-ID` for gap recovery.

2. **Decision trail storage could bloat the database.** Every trade generates a full pipeline trace (signal, risk result, price check, exchange result). At 5-50 trades/day, that's 150-1500 trail entries/month. Each entry could be 1-2KB of JSON.
   - **Mitigation:** Store as JSON blob in the existing `trades` table (add `decision_trail TEXT` column). Prune trails older than 90 days. This is ~150KB/month max — negligible.

3. **Satisfaction scoring is conceptually ambiguous.** What does "82% satisfaction" mean for a trade? The placeholder shows `hestiaScore: 0.82` but doesn't define the formula. Possible approaches:
   - **Post-hoc outcome scoring:** P&L result vs. expected value (but this requires hindsight)
   - **Pre-execution confidence scoring:** Signal confidence * risk approval strength * price validation score (available at execution time)
   - **Hybrid:** Initial confidence at execution + retrospective P&L outcome
   - **Mitigation:** Use pre-execution composite confidence score as the initial "Hestia Score". Add retrospective P&L-based adjustment in daily summary. This gives immediate feedback at trade time + learning signal later.

4. **Watchlist adds scope but unclear value pre-go-live.** Watchlist is primarily useful when you're deciding which pairs to add bots on. During paper trading with fixed BTC-USD/ETH-USD pairs, a watchlist adds complexity without clear utility.
   - **Mitigation:** Implement watchlist as a thin CRUD layer (database + 3 endpoints) but keep UI minimal. It's a 2-hour add that becomes useful when expanding to more pairs (Sprint 27+).

5. **Discord webhook is a new external dependency.** Needs a webhook URL stored somewhere, error handling for Discord downtime, and rate limiting.
   - **Mitigation:** Store webhook URL in `trading.yaml` config. Use existing `hestia.notifications` router pattern. Add try/except with silent fallback — alerts are informational, not critical path.

## Third-Party Evidence

### SSE for Trading Dashboards

FastAPI's official documentation now includes a dedicated [SSE tutorial](https://fastapi.tiangolo.com/tutorial/server-sent-events/) recommending `StreamingResponse` with `text/event-stream` media type and `Cache-Control: no-cache`. The `sse-starlette` library provides `EventSourceResponse` with built-in ping/keepalive, but Hestia's existing raw `StreamingResponse` approach works fine and avoids the dependency.

For long-lived SSE connections (trading dashboard vs. chat), the key pattern difference is:
- **Chat SSE:** Generator runs handler pipeline, yields tokens, terminates with `done` event.
- **Trading SSE:** Generator subscribes to an event bus, yields events indefinitely, terminates on client disconnect.

The recommended pattern is an `asyncio.Queue` per subscriber with bounded size and a background task that publishes events to all active queues.

### Trade Quality Scoring in Production

Modern crypto bots (3Commas, Darkbot) use multi-factor scoring:
- **Signal quality:** Strategy confidence (0-1)
- **Risk compliance:** How much of the allowed position size was used (Quarter-Kelly efficiency)
- **Execution quality:** Slippage vs. expected (maker vs. taker, actual fill vs. signal price)
- **Timing quality:** Was volume confirmation present? Was trend filter aligned?

Composite formula: `score = 0.3 * signal_confidence + 0.25 * risk_efficiency + 0.25 * execution_quality + 0.2 * timing_alignment`

### Discord Webhook Pattern

Standard Python implementation is ~20 lines using `aiohttp.ClientSession.post()` with a JSON payload. Rate limit: 30 messages/min per webhook URL. Best practice: batch alerts (group 3+ events in 60s into one message) — mirrors Hestia's existing notification consolidation pattern.

### Audit Trail Compliance

MiFID II/FCA require algorithmic trading audit trails with microsecond timestamps. While Hestia isn't regulated, implementing from day one prevents retrofitting. Key requirement: every decision point that affected order flow must be logged with the data it used. The `TradeExecutor.execute_signal()` audit dict already satisfies this — it just needs persistence.

## Recommendation

### Architecture: 6 Workstreams

**WS1: Decision Trail Persistence (~3h)**
- Add `decision_trail TEXT` column to `trades` table (JSON blob)
- Modify `TradeExecutor.execute_signal()` to return trail as part of trade recording
- Add `TradingManager.record_trade()` integration to persist trail alongside trade
- Add `GET /v1/trading/trades/{id}/trail` endpoint for per-trade trail retrieval
- Trail is already structured: `{signal, portfolio_value, pipeline_steps: [{step, result}], result, reason, fill}`

**WS2: Satisfaction Scoring (~2h)**
- Define `SatisfactionScorer` class with composite formula:
  ```
  score = 0.30 * signal_confidence
        + 0.25 * risk_efficiency    (adjusted_qty / requested_qty)
        + 0.25 * execution_quality  (1 - abs(slippage_pct))
        + 0.20 * timing_alignment   (volume_confirmed * trend_aligned)
  ```
- Compute at execution time, store as `satisfaction_score REAL` in trades table
- Retrospective adjustment: daily summary recalculates score with actual outcome
- Add `satisfaction_score` to `TradeResponse` schema

**WS3: SSE Streaming Endpoint (~4h)**
- New endpoint: `GET /v1/trading/stream` (SSE, long-lived)
- Event types:
  - `heartbeat` — every 15s, keeps connection alive
  - `trade` — new trade executed (includes decision trail + satisfaction score)
  - `position_update` — position changed (price tick or fill)
  - `risk_alert` — circuit breaker triggered/cleared
  - `portfolio_snapshot` — periodic full state (every 30s)
  - `kill_switch` — kill switch activated/deactivated
- Implementation: `TradingEventBus` class with `asyncio.Queue` per subscriber
  - Bounded queue (max 100 events) — drops oldest on overflow
  - `TradeExecutor`, `RiskManager`, `PositionTracker` publish events to bus
  - SSE generator subscribes, yields events, unsubscribes on disconnect
- Reconnection: `Last-Event-ID` header for gap recovery (events are sequentially numbered)

**WS4: Watchlist (~2h)**
- New table: `watchlist` (id, pair, notes, price_alerts JSON, added_at, user_id)
- 4 endpoints: `GET/POST /v1/trading/watchlist`, `PUT/DELETE /v1/trading/watchlist/{id}`
- Minimal UI initially — list of pairs with current price (from exchange adapter)
- Price alert integration with notification system (optional, can defer)

**WS5: macOS Trading Tab Wiring (~6h)**
- New `MacTradingViewModel` (ObservableObject):
  - Fetches bots, trades, risk status, daily summaries via REST
  - Subscribes to SSE stream for real-time updates
  - Kill switch toggle
  - Watchlist CRUD
- Wire `TradingMonitorView.swift` to live data:
  - Portfolio snapshot: total value from `PositionTracker` aggregate, 24h P&L from daily summary
  - Active positions: from position tracker API
  - Recent trades: from `GET /v1/trading/trades?limit=20` with decision trail expansion
  - Satisfaction gauge: display `satisfaction_score` from trade data
  - Risk status: from `GET /v1/trading/risk/status`
  - Kill switch: POST to `/v1/trading/kill-switch`
  - Watchlist: CRUD operations
- SSE integration in ViewModel:
  - `URLSession` with `text/event-stream` parsing
  - Auto-reconnect with exponential backoff
  - Update `@Published` properties on each event
- The view stays in Command Center (no new sidebar icon needed) — Trading is a panel within the Internal or System activity feed, or a dedicated tab in ActivityFeedView

**WS6: Alert System (~3h)**
- Discord webhook: `DiscordAlerter` class in `hestia/trading/alerts.py`
  - Webhook URL from `trading.yaml` (or Keychain for security)
  - Formatted embeds: trade execution, circuit breaker trigger, daily summary, kill switch
  - Rate limiting: max 1 msg/min per event type, batch consolidation (3+ in 60s)
- Push notification integration: use existing `NotificationManager.bump()`
  - Circuit breaker triggers → High priority bump
  - Daily summary → Low priority scheduled bump
  - Kill switch events → Critical priority (bypass quiet hours)

### What NOT to Build in Sprint 26

- **iOS Trading tab:** Defer to Sprint 30 polish. macOS-first approach mirrors the pattern from Sprints 1-5.
- **Equity curve chart:** Requires SwiftUI Charts framework integration. Schedule for Sprint 30.
- **Strategy-level P&L attribution:** Already in DailySummary model. UI visualization can wait.
- **Backtest UI in Trading tab:** The backtest endpoint exists. A nice backtest viewer is Sprint 30 territory.

### Estimated Effort

| WS | Scope | Hours |
|----|-------|-------|
| WS1 | Decision trail persistence | 3h |
| WS2 | Satisfaction scoring | 2h |
| WS3 | SSE streaming endpoint | 4h |
| WS4 | Watchlist CRUD | 2h |
| WS5 | macOS Trading tab wiring | 6h |
| WS6 | Alert system (Discord + push) | 3h |
| **Total** | | **20h** |

### Confidence Level: High

The foundation is solid. Every component either extends an existing pattern (SSE from chat, notifications from Sprint 20C, ViewModel pattern from other macOS views) or persists data that's already being computed (decision trail from TradeExecutor, risk status from RiskManager). No new architectural patterns are needed.

### What Would Change This Recommendation

- **If live trading is imminent (< 1 week):** Prioritize WS1/WS3/WS5/WS6 (the monitoring essentials), defer WS2/WS4.
- **If iOS is required simultaneously:** Add ~8h for iOS ViewModel + View (doubles UI scope).
- **If WebSocket is preferred over SSE:** SSE is simpler and sufficient for server-to-client updates. The client never pushes trade data. Stick with SSE unless bidirectional communication is needed (e.g., real-time order placement from the dashboard).

## Final Critiques

- **Skeptic:** "Why add SSE complexity when REST polling every 5s would work fine?"
  **Response:** At 5-50 trades/day, most 5s polls return no changes. SSE eliminates wasted requests and provides instant feedback when trades execute. The pattern is already proven in chat streaming. The incremental complexity is ~100 lines of event bus code. REST polling would actually be MORE code (timer management, diff detection, stale state handling).

- **Pragmatist:** "Is the satisfaction scoring worth 2 hours? It's a vanity metric."
  **Response:** It's not vanity — it's a feedback signal for strategy tuning. A trade with high signal confidence but poor execution quality (high slippage) reveals a liquidity problem. A trade with low signal confidence but good P&L outcome reveals the strategy is working despite uncertainty. This data feeds Sprint 29's ML optimization. The 2h cost is minimal for the learning signal it provides.

- **Long-Term Thinker:** "What happens when there are 10,000+ trades and the decision trail table grows?"
  **Response:** Decision trails are stored as JSON in the trades table, not a separate table. At 50 trades/day * 2KB/trail = 100KB/day = 36MB/year. SQLite handles this trivially. Add a 90-day auto-prune for trail data if needed (the trade itself persists forever for tax purposes, but the reasoning trace can be compressed or pruned).

## Open Questions

1. **Where should Trading live in the macOS sidebar?** Options: (a) New sidebar icon (requires adding to `WorkspaceView` enum), (b) Tab within Command Center's ActivityFeedView, (c) Dedicated section in System or Internal activity. Recommendation: **(a) New sidebar icon** — trading is a top-level concern, not subordinate to Command Center.

2. **Discord webhook URL storage:** Config file (`trading.yaml`) vs. Keychain? Keychain is more secure but requires manual setup. Config file is simpler for dev/paper trading. Recommendation: Config file initially, migrate to Keychain before go-live (Sprint 30).

3. **SSE reconnection strategy:** Should the client request a full state snapshot on reconnect, or replay missed events via `Last-Event-ID`? Recommendation: Full snapshot on reconnect (simpler, more reliable) + `Last-Event-ID` for gap recovery within a session.

4. **User feedback on trades (thumbs up/down):** The placeholder shows thumb icons. Should Sprint 26 implement this? It feeds into satisfaction scoring and strategy tuning. Recommendation: Yes, add a simple `POST /v1/trading/trades/{id}/feedback` endpoint (body: `{rating: "positive"|"negative"|"neutral", note: "..."}`) — 1h add, high learning value.

---

Sources:
- [FastAPI SSE Tutorial](https://fastapi.tiangolo.com/tutorial/server-sent-events/)
- [SSE with FastAPI — Medium](https://mahdijafaridev.medium.com/implementing-server-sent-events-sse-with-fastapi-real-time-updates-made-simple-6492f8bfc154)
- [Trading Audit Trails & Regulatory Compliance](https://medium.com/@veritaschain/why-your-algorithmic-trading-logs-might-not-survive-a-regulatory-audit-1582bfd1445d)
- [Crypto Trading Bot Metrics — SSA Group](https://www.ssa.group/blog/how-to-identify-a-perfect-crypto-trading-bot-key-metrics-explained/)
- [AI Trading Bot Performance Analysis — 3Commas](https://3commas.io/blog/ai-trading-bot-performance-analysis)
- [Trading Bot Checklist 2026 — Darkbot](https://darkbot.io/blog/trading-bot-checklist-2026-essential-criteria-for-crypto-success)
- [TradingView Webhook Bot (Discord)](https://github.com/fabston/TradingView-Webhook-Bot)
- [Audit Trails as Product Feature — Graph + Rules](https://partenit.io/audit-trails-as-a-product-feature-why-graph-rules-win-enterprise-deals/)
- [SwiftUI Charts Dashboard Tutorial](https://medium.com/data-science-collective/how-to-build-a-beautiful-data-dashboard-app-on-ios-using-swiftui-charts-1019a362fa5c)
