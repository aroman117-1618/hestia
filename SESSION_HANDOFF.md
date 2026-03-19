# Session Handoff — 2026-03-19 (Session 7: Sprint 27 Go-Live Safety Hardening)

## Mission
Audit the Sprint 27 Go-Live plan with cross-model validation (Claude + Gemini), fix critical safety issues, lock trading dependencies, write integration tests, and deploy to Mac Mini for paper soak.

## Completed

### Cross-Model Audit (Claude Opus 4.6 + Gemini 2.5 Pro)
- 10-phase /second-opinion audit of the Go-Live plan
- Gemini issued REJECT (institutional-grade concerns), Claude issued APPROVE WITH CONDITIONS
- Reconciled: safety fixes are non-negotiable, WebSocket/shadow mode deferred to capital gates
- Capital scaling intent documented ($250 start → $10K+ based on performance)
- Output: `docs/plans/sprint-27-golive-second-opinion-2026-03-19.md`

### Safety Hardening (4 commits)
1. **Atomic trade recording** (`9658ab5`)
   - `hestia/trading/manager.py`: `record_trade()` wraps trade + tax lot writes in `BEGIN IMMEDIATE` / `COMMIT` with `ROLLBACK` on failure
   - `hestia/trading/database.py`: `_no_commit` variants for `record_trade`, `create_tax_lot`, `update_tax_lot`
   - FK-aware write order: trade first (parent), tax lot second (child)
   - Pre-existing bug fixed: `OrderType` string→enum conversion in Trade constructor

2. **Active reconciliation** (`9658ab5`)
   - `hestia/trading/position_tracker.py`: divergence now triggers kill switch callback + CRITICAL event via event bus
   - `hestia/trading/bot_runner.py`: wires `kill_switch_callback=risk_manager.activate_kill_switch` to PositionTracker

3. **Orchestrator idempotency** (`9658ab5`)
   - `hestia/trading/orchestrator.py`: failed bot resume → status set to STOPPED (no phantom RUNNING bots)

4. **Dead circuit breaker cleanup** (`9658ab5`)
   - `hestia/trading/risk.py`: VOLATILITY/CONNECTIVITY/SINGLE_TRADE disabled by default via `_IMPLEMENTED_BREAKERS` set

5. **Reviewer critical fixes** (`f8ef1f3`)
   - `hestia/trading/database.py`: `TradingDatabase.connect()` overrides BaseDatabase to pass `isolation_level=None`, preventing `OperationalError: cannot start a transaction within a transaction`
   - `hestia/trading/manager.py`: `_estimate_portfolio_value()` moved outside `BEGIN IMMEDIATE` lock (no exchange I/O while holding exclusive DB write lock)

### Dependencies (`f01265f`)
- `pandas`, `ta`, `coinbase-advanced-py`, `aiohttp` added to `requirements.in`
- `vectorbt` commented out (requires Python 3.10+, Mac Mini runs 3.9) — only needed for backtesting, not BotRunner
- Lockfile recompiled

### Integration Tests (16 new, 2515 total backend)
- `tests/test_trading_golive.py`: 29 tests total (was 13)
- Atomic trade recording: buy atomicity, sell lot consumption, rollback on error
- Active reconciliation: matching=no halt, divergence=kill switch, untracked=kill switch
- Circuit breaker cascade: drawdown blocks, daily loss cooldown, kill switch overrides, disabled vs armed
- Risk state persistence: kill switch survives restart, breaker state persists, PnL tracking round-trip
- Error recovery: backoff constants, crash detection callback

### Deployment
- All 4 commits pushed to GitHub (pre-push hook: tests + macOS build passed)
- Deployed to Mac Mini (`hestia-3.local`)
- Server running with `caffeinate -d` (prevents sleep during paper soak)
- Trading endpoints responding, macOS app already connecting

## In Progress
- **Paper soak not yet started** — server deployed, needs Andrew to enable trading via macOS app or CLI

## Decisions Made
- **Capital gates for scaling**: $250 → $1K (2-week clean + staleness checks), $1K → $2.5K (CoinGecko + shadow mode + WebSocket), $2.5K → $5K+ (strategy diversification + multi-exchange)
- **REST polling sufficient for Go-Live**: WebSocket deferred to Sprint 28 (capital gate 2). Grid on 1h candles doesn't need sub-second fills.
- **vectorbt deferred**: Mac Mini Python 3.9 incompatible. Backtesting works locally but not on deploy target. Will resolve with M5 Ultra upgrade (Python 3.12).
- **isolation_level=None on TradingDatabase only**: Other databases keep Python's default implicit transactions. Only trading needs explicit transaction control.

## Test Status
- 2515 backend passing, 0 failing, 0 skipped (Ollama integration tests excluded)
- 135 CLI tests (separate venv)
- 2650 total

## Uncommitted Changes
**Staged but not committed (from concurrent config cleanup session):**
- `.claude/agents/hestia-explorer.md`, `.claude/agents/hestia-reviewer.md` — agent definition updates
- `.claude/settings.json` — settings changes
- `.claude/skills/*.md` — skill file updates + retrospective archived
- `scripts/archive/` — old scripts moved to archive
- `docs/metrics/dev-loop-metrics.md`, `docs/plans/claude-config-audit-and-improvement-plan.md` — new docs
- `CLAUDE.md` — test count update (2515 backend, was 2499)

**Action**: These are safe to commit as a separate "chore: config cleanup" commit. The CLAUDE.md test count update should be committed regardless.

## Known Issues / Landmines
- **Mac Mini Python 3.9**: vectorbt won't install. Backtesting endpoint will fail if called on Mac Mini. Local dev (Python 3.9 too, but vectorbt happens to be installed). Long-term fix: M5 Ultra with Python 3.12.
- **Pre-push ChromaDB hang**: 240s timeout works but fragile. Root fix: ChromaDB cleanup fixture.
- **Concurrent session stash on Mac Mini**: `git stash list` may show old stashes from parallel sessions.
- **Paper mode only**: `trading.yaml` defaults to `mode: paper`. Switch to `coinbase` ONLY after 72h clean soak + all capital gate prerequisites met.
- **No macOS app auto-update**: Must manually `xcodegen generate && xcodebuild` after git pull on MacBook.
- **Reviewer warnings not yet addressed**: standalone `_consume_tax_lots` wrapper is a footgun (commits pending writes), kill_switch_callback type could accept async accidentally, event_bus import from routes layer couples orchestrator to API. Non-blocking.

## Process Learnings
- **@hestia-reviewer caught 2 critical bugs** that would have caused production failures: `isolation_level` conflict and DB lock contention during exchange I/O. Always run reviewer on financial code.
- **Gemini's REJECT was useful even where wrong**: WebSocket and shadow mode concerns were over-scoped for $250 but become relevant at $10K+. The capital gate framework emerged from reconciling both perspectives.
- **FK constraint ordering caught by integration tests, not unit tests**: The atomic transaction initially wrote tax lot before trade, violating `tax_lots.trade_id REFERENCES trades(id)`. Unit tests with mocked DBs would never catch this.
- **aiosqlite thread safety**: Can't directly access `_conn` from main thread. Need to either use `_execute()` or override `connect()` with `isolation_level` kwarg.
- **First-pass success**: 6/8 tasks completed on first try. Rework caused by: FK constraint ordering (1 rework), aiosqlite thread safety for isolation_level (2 attempts).

## Next Step
**Start the paper soak:**

1. Open Hestia macOS app on MacBook → Trading tab → toggle "Enable Trading"
   - OR via CLI: `hestia` → "enable trading"
   - OR via API: `POST /v1/trading/bots` then `POST /v1/trading/bots/{id}/start`

2. Verify in Decision Feed that candle polling starts (15-min intervals)

3. Monitor for 72h:
   - Decision Feed in macOS app shows signal generation
   - Discord alerts fire on risk events (if webhook configured)
   - No ERROR state transitions
   - `curl -sk https://hestia-3.local:8443/v1/trading/risk/status` shows kill switch inactive

4. After 72h clean soak → next session:
   - Review trade history: `GET /v1/trading/trades`
   - Check tax lots: `GET /v1/trading/tax/lots`
   - Verify reconciliation clean: no kill switch triggers in logs
   - If clean: flip `trading.yaml: mode → coinbase`, start with $25 (10%)
   - Capital gate checklist: `docs/plans/sprint-27-golive-second-opinion-2026-03-19.md`
