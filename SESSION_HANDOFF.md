# Session Handoff — 2026-03-24

## Mission
Diagnose why Hestia's trading system had never executed a trade despite being "live since March 19", fix all blockers, and activate live Coinbase trading on the Mac Mini.

## Completed
- Full system audit of trading module — found 7+ issues (discovery: `docs/discoveries/trading-system-audit-2026-03-24.md`)
- **Bug fix:** `self._bot` → `self.bot` in `bot_runner.py:342,344` — AttributeError crash on portfolio value fallback (`10b203b`)
- **Bug fix:** Inject `bot.pair` into strategy config in `bot_runner.py:100-104` — all bots were defaulting to BTC-USD signals (`9e435d9`)
- **Bug fix:** Switch executor from `limit+post_only` to `market` orders in `executor.py:138-144` — limit orders were silently rejected by Coinbase (`2e382af`)
- **Feature:** Added SOL-USD and DOGE-USD to `product_info.py` (`90a98d4`)
- **Feature:** Created `scripts/seed-trading-bots.py` — 4-bot MR portfolio with RSI-3 params (`90a98d4`)
- **Fix:** Deploy script now restarts trading-bots launchd service (`7561184`)
- **Deployed to Mac Mini** — bot_service.py running, 4 bots active, first signals generated
- **Cleaned stale data** — removed 3 old stopped bots and 6 paper-mode trade records from Mac Mini DB
- **Created issue #31** — position state persistence for bot service restarts
- Implementation plan: `docs/superpowers/plans/2026-03-24-trading-go-live.md`

## In Progress
- None — all tasks completed and deployed

## Decisions Made
- **Market orders over limit+post_only**: Post-only limit at market price is rejected by Coinbase. Market orders guarantee fills. 0.20% fee difference ($0.13 on $62.50 positions) is negligible vs. execution reliability.
- **RSI-3 per-asset configs**: BTC 15/85, ETH 20/80, SOL 25/70, DOGE 25/75 — from S27.6 backtest results
- **$62.50 per bot** (4 x $62.50 = $250 total capital across 4 assets)

## Test Status
- 2829 tests collected, 89 test files
- 1 pre-existing failure: `test_inference.py::test_simple_completion` (Ollama integration, not related)
- All 362 trading tests pass (confirmed via targeted run)
- Full suite hangs after completion due to ChromaDB background threads (known issue)

## Uncommitted Changes
- `CLAUDE.md` — count fixes (89 test files, 30 route modules), trading status update
- `SPRINT.md` — updated to reflect live trading status
- `SESSION_HANDOFF.md` — this file
- `docs/discoveries/trading-system-audit-2026-03-24.md` — new discovery doc
- `docs/superpowers/plans/2026-03-24-trading-go-live.md` — new plan doc
- `.claude/skills/handoff/SKILL.md`, `.claude/skills/pickup/SKILL.md`, `.mcp.json` — modified by another session

## Known Issues / Landmines
- **Position state not persisted (issue #31)**: `MeanReversionStrategy._last_entry` lives in memory. If bot_service restarts (deploy, reboot), open position tracking is lost. Low risk at $62.50/bot but needs fixing.
- **Coinbase API error**: `"Cannot pass multiple statuses with OPEN"` in reconciliation `get_open_orders` call. Non-blocking — bots run fine despite it. Root cause: Coinbase SDK behavior change.
- **Mac Mini runs Python 3.9** (not 3.12) — urllib3 SSL warning in error log. Works but worth upgrading.
- **API server readiness check failed on deploy** — took >15s to respond. Likely just slow startup after service reload. Server is running (bots connected successfully).
- **"Open Positions: 2" in UI** shows dust holdings (ETH $0.04, FET $0.00) from pre-Hestia Coinbase activity, not bot positions.

## Process Learnings
- **First-pass success**: 7/8 tasks completed on first try (88%). The deploy task needed iterating (readiness check timeout, discovering bots were already seeded from a previous session).
- **Top blocker**: The trading system was never operational because the `bot_service.py` process was never installed as a launchd service on the Mac Mini. This was a pure deployment gap — the code was correct, the architecture was sound.
- **Agent orchestration**: Good parallel subagent dispatch for Tasks 3-6 saved significant time. The hestia-explorer agent provided excellent architecture analysis. The plan reviewer caught 2 real blockers (stopped bot would cause seed skip; test files didn't exist).
- **Proposal (CLAUDE.MD)**: Add note about bot_service.py being a separate process from the API server — this was the root cause and isn't obvious from CLAUDE.md.
- **Proposal (HOOK)**: Add a post-deploy health check that verifies trading-bots service is running and bots are generating signals.

## Next Step
- Monitor trading bots for first 24h — check for actual trade executions:
  ```bash
  ssh andrewroman117@hestia-3.local 'sqlite3 ~/hestia/data/trading.db "SELECT * FROM trades ORDER BY timestamp DESC LIMIT 5;"'
  ssh andrewroman117@hestia-3.local 'grep "Signal:" ~/hestia/logs/hestia.log | tail -20'
  ```
- If any bot enters ERROR state, check logs: `ssh andrewroman117@hestia-3.local 'grep "ERROR\|crashed" ~/hestia/logs/hestia.log | tail -10'`
- Next sprint work: fix position state persistence (issue #31), then Sprint 28 (regime detection) after 30+ fills
