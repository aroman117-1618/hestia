# Session Handoff — 2026-03-27 (Trading Bot Diagnosis & Fix)

## Mission
Investigate why the 4 live trading bots on Mac Mini haven't executed a single trade since going live on March 22. Diagnose root cause, fix all issues, restore service.

## Completed
- **Root cause identified**: 3 distinct bugs blocking all trading activity
- **Fix 1 — Credentials** (`~/.hestia/coinbase-credentials` on Mac Mini): File was overwritten on March 23 at 10:14 AM with invalid content, causing 401 Unauthorized on every API call. Re-saved from 1Password.
- **Fix 2 — USDC-USD reconciliation** (`hestia/trading/position_tracker.py`): Reconciliation tried to price `USDC-USD` (invalid Coinbase product_id) for any non-dust USDC balance. Fixed: skip all stablecoins unconditionally in untracked-position check.
- **Fix 3 — list_orders status** (`hestia/trading/exchange/coinbase.py`): `order_status=["OPEN", "PENDING"]` rejected by Coinbase API. Fixed: `["OPEN"]` only.
- **Deployed to Mac Mini**, restarted bot service, verified 2 successful tick cycles
- All 140 trading tests pass, 2976 total backend tests pass
- Commit: `7d192f0`

## In Progress
- Nothing — all fixes deployed and verified

## Decisions Made
- Stablecoins (USDC/USDT/DAI/BUSD) are unconditionally skipped in reconciliation — they're not positions we track and have no valid X-USD product_id on Coinbase
- Strategy threshold tuning deferred — bots are correctly returning HOLD signals based on current RSI thresholds. SOL-USD had RSI 20.8 but was blocked by volume filter (0.24x < 1.0x). Thresholds may need widening to generate trades in calm markets, but that's a tuning decision for a separate session.

## Test Status
- 2976 passing, 0 failing, 0 skipped (backend)
- 135 CLI tests (not run this session — no CLI changes)

## Uncommitted Changes
- `CLAUDE.md` — test count update (2976 from 2980)

## Known Issues / Landmines
- **Mac Mini Python 3.9**: The venv on Mac Mini uses Python 3.9.6 (system CommandLineTools), not 3.12. This is S27.5 WS3 work. The bots function on 3.9 but it's a drift risk.
- **Stdout log empty**: Bot service writes to `hestia.log` (structured JSON) but `trading-bots.log` (launchd stdout) is empty. Not critical but makes `tail` debugging harder.
- **Coinbase outage**: Coinbase API was temporarily down during our restart. The bots recovered automatically on the next tick. If you see a gap in tick logs around 15:04-15:17 UTC on March 27, that's the outage.
- **Strategy thresholds are tight**: BTC RSI threshold is 15/85, ETH is 20/80. In calm markets, these may never trigger. Current RSI values (28-46) are all in "neutral zone". Consider widening to 30/70 range if no trades after 1-2 more weeks.
- **Position state not persisted** (`_last_entry`): Known issue #31 — if bot service restarts mid-position, it loses entry price tracking.
- **Credential file mystery**: Who/what overwrote the credentials on March 23 at 10:14 AM? Unknown. Could have been a deploy script, macOS app, or manual action. Worth investigating to prevent recurrence.

## Process Learnings

### Config Gaps
- **No alerting on persistent errors**: The bots produced 401 errors for 5 days with no notification. A hook or health check that alerts on >N consecutive errors in `trading-bots.error.log` would have caught this on day 1.
- **Credential validation on deploy**: `deploy-to-mini.sh` should verify credential file exists and isn't empty after deploy. A simple `wc -l` check would suffice.

### First-Pass Success
- 3/3 fixes identified and resolved correctly on first analysis
- Top blocker: needing to SSH into Mac Mini for every diagnostic — no remote monitoring dashboard
- The Coinbase outage coinciding with our restart was bad luck, not a process failure

### Agent Orchestration
- Used @hestia-explorer (haiku) for initial architecture trace — effective, saved significant context
- Used @hestia-tester for test validation — clean run, good delegation
- Missed opportunity: could have run the Mac Mini SSH diagnostics in parallel rather than sequentially

### Proposals (ranked by frequency x severity / effort)
1. **SCRIPT**: Add `scripts/trading-health-check.sh` — SSH to Mini, check bot PID, last error, last tick time. Run as daily cron or manual check. (Impact: would have caught this in <24h)
2. **HOOK**: Add a post-deploy hook that validates credential files exist on Mac Mini after `deploy-to-mini.sh` runs. (Impact: prevents silent credential wipes)
3. **CLAUDE.MD**: Document the credential file format (`~/.hestia/coinbase-credentials`: line 1 = API key name, line 2 = EC private key) — currently undocumented. (Impact: faster recovery next time)

## Next Step
1. Commit the CLAUDE.md test count update
2. Monitor bot logs over the next few days: `ssh andrewroman117@hestia-3.local "grep 'Signal:' /Users/andrewroman117/hestia/logs/hestia.log | tail -20"`
3. If zero BUY/SELL signals after 1 week of healthy ticks, open a strategy tuning session to widen RSI thresholds
4. S27.5 WS3 (Python 3.12 upgrade on Mac Mini) remains TODO — prerequisite for Sentinel Layer 0 deployment
