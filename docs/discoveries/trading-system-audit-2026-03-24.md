# Discovery Report: Hestia Trading Module — Full System Audit
**Date:** 2026-03-24
**Confidence:** High
**Decision:** The trading system has **at least 7 blockers** preventing autonomous execution. The bot service process is not running, no bots exist in the database, there is a code bug that would crash the runner, and the execution pipeline would silently reject orders via limit-order mechanics. All are fixable in a focused session.

## Hypothesis
The trading system was declared "live paper soak" on 2026-03-19, but has never executed a single trade. The question: what specific failures prevent autonomous trading, and what is the complete fix list?

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Architecture is sound — 8-layer risk pipeline, clean separation (strategies, executor, risk, exchange), event bus for streaming, command queue for IPC, tax lot tracking. Code quality is high. | **Weaknesses:** Multiple silent failure points — no bots created, bot service not running, `self._bot` AttributeError, limit orders on paper adapter won't fill, no bot creation automation, no observability/alerting for "nothing happening". |
| **External** | **Opportunities:** All infrastructure exists — just needs wiring. Coinbase adapter is production-ready. 4-asset Mean Reversion strategy is backtested. Config is correct (`mode: live`). | **Threats:** Coinbase API key scoping (must be "Consumer Default Spot" portfolio). Keychain access from launchd context may fail silently. No monitoring for bot health = could run for weeks without executing. |

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | P1: Bot service not running (launchd not installed) | P6: Missing product_info for SOL/DOGE (falls back safely) |
| | P2: No bots exist in database (need creation script) | P7: PriceValidator secondary feed not configured (skips validation) |
| | P3: `self._bot` AttributeError in bot_runner.py (crash) | |
| | P4: Limit orders on live Coinbase won't auto-fill at market (post_only=True) | |
| **Low Priority** | P5: Deploy script doesn't manage trading-bots service | P8: Paper adapter hardcoded prices (BTC=65000, ETH=3500) stale |
| | | P9: No health dashboard for "are bots actually running?" |

## Detailed Findings — The 7+ Blockers

### BLOCKER 1: Bot Service Process Not Running
**Severity: CRITICAL — Nothing executes without this**

The entire trading loop runs in `hestia.trading.bot_service` — a **separate process** from the API server. The server explicitly skips orchestrator startup (line 390-393 of `server.py`). The launchd plist exists at `scripts/launchd/com.hestia.trading-bots.plist` but:

1. It has never been installed to `~/Library/LaunchAgents/` on the Mac Mini
2. The deploy script (`deploy-to-mini.sh`) only manages `com.hestia.server.plist` — it does NOT install or restart the trading-bots service
3. The plist references `/Users/andrewroman117/hestia/.venv/bin/python` — must verify this path exists on Mac Mini

**Fix:**
```bash
# On Mac Mini:
cp scripts/launchd/com.hestia.trading-bots.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.hestia.trading-bots.plist
# Also: add to deploy-to-mini.sh to restart on deploy
```

### BLOCKER 2: No Bots Exist in the Database
**Severity: CRITICAL — Even if service runs, nothing to trade**

The trading config (`trading.yaml`) specifies the 4-asset Mean Reversion portfolio (BTC, ETH, SOL, DOGE with custom RSI parameters), but these are just **config comments**. No bot creation script or seed data exists. The `bot_commands` table polling in `bot_service.py` will find nothing to resume because there are zero bots with `status=RUNNING`.

**Fix:** Create a bot seeding script or API calls to create the 4 bots:
```python
# For each: POST /v1/trading/bots with:
# BTC-USD: mean_reversion, rsi_period=3, rsi_oversold=15, rsi_overbought=85, capital=62.50
# ETH-USD: mean_reversion, rsi_period=3, rsi_oversold=20, rsi_overbought=80, capital=62.50
# SOL-USD: mean_reversion, rsi_period=3, rsi_oversold=25, rsi_overbought=70, capital=62.50
# DOGE-USD: mean_reversion, rsi_period=3, rsi_oversold=25, rsi_overbought=75, capital=62.50
# Then: POST /v1/trading/bots/{id}/start for each
```

### BLOCKER 3: `self._bot` AttributeError in BotRunner
**Severity: CRITICAL — Runner will crash on first tick**

File: `hestia/trading/bot_runner.py`, lines 342-344:
```python
return total if total > 0 else self._bot.capital_allocated
    except Exception:
        return self._bot.capital_allocated
```

The attribute is `self.bot` (no underscore), not `self._bot`. This will raise `AttributeError` when `_get_portfolio_value()` falls through to the fallback — which happens whenever exchange balances return empty or the balance calculation yields 0. On the very first tick with a new paper adapter (only USD balance, no crypto positions), `total` could be 0 for all non-USD currencies, so `total` = just the USD balance, which should be > 0... but if the paper adapter's `get_balances()` has any issue, this crashes.

More critically: the `except Exception` on line 343 will catch the `AttributeError` from line 342 and **also crash** on line 344 with the same `AttributeError`. This means:
- If `get_balances()` throws → `_get_portfolio_value()` returns `AttributeError` → tick crashes → after 3 crashes, bot enters ERROR state.

**Fix:** Change `self._bot` to `self.bot` on both lines (342 and 344).

### BLOCKER 4: Limit Orders + Post-Only on Paper Adapter
**Severity: HIGH — Orders will never fill**

The `TradeExecutor.execute_signal()` hardcodes `order_type="limit"` and `post_only=True` (line 138-145). The `PaperAdapter.place_order()` treats limit orders with maker fees (line 107-108), which is fine. However, in paper mode, orders fill immediately (no order book matching). This actually works — paper adapter auto-fills everything. **This blocker applies only in LIVE mode.**

Wait — re-reading the config: `mode: "live"`. The manager initialization at line 82-115 shows: if mode is NOT "paper", it creates a `CoinbaseAdapter`. So in the current config, the system will try to use Coinbase live, not paper.

For live Coinbase with `post_only=True` limit orders: the order is placed at `signal.price` (the current market price). A post-only limit buy at the current price will be **immediately rejected** by Coinbase because it would be a taker order (crossing the spread). The order needs to be placed below the best ask to be a valid maker order.

**Fix options:**
1. Set `mode: "paper"` to continue paper soak with real market data
2. Or: change order type to "market" for initial testing
3. Or: implement smart limit pricing (place below ask for buys, above bid for sells)

### BLOCKER 5: RSI Period Mismatch
**Severity: MEDIUM — Strategy config doesn't match backtest results**

The YAML config says `rsi_period: 7` as default. The YAML comments reference "RSI-3" for all assets:
```
# ETH-USD: RSI-3 20/80 (+33.9% combined)
# BTC-USD: RSI-3 15/85 (+18.3% combined)
```

But `rsi_period: 3` is NOT the default in `trading.yaml` — it's `rsi_period: 7`. The per-bot config override would need to explicitly set `rsi_period: 3` when creating each bot. This is part of Blocker 2 — the bot creation must pass the correct per-asset RSI parameters.

**Fix:** Include `rsi_period: 3` in each bot's config dict when creating them.

### BLOCKER 6: Deploy Script Doesn't Manage Trading Service
**Severity: MEDIUM — Service won't restart on code deploys**

`scripts/deploy-to-mini.sh` only restarts `com.hestia.server.plist`. After a code deploy, the trading bot service will keep running stale code until manually restarted or the Mac Mini reboots.

**Fix:** Add trading-bots service restart to `deploy-to-mini.sh`:
```bash
if [[ -f ~/Library/LaunchAgents/com.hestia.trading-bots.plist ]]; then
    launchctl unload ~/Library/LaunchAgents/com.hestia.trading-bots.plist 2>/dev/null || true
    sleep 1
    launchctl load ~/Library/LaunchAgents/com.hestia.trading-bots.plist
fi
```

### NON-BLOCKER 7: PriceValidator Has No Secondary Feed
**Severity: LOW — Validation is skipped gracefully**

`PriceValidator` has no CoinGecko integration yet (comment says "Sprint 25"). When no secondary price exists, validation returns `valid: True` with a warning. Orders pass through. This is acceptable for paper soak but should be addressed before real capital.

### NON-BLOCKER 8: Missing Product Info for SOL/DOGE
**Severity: LOW — Falls back to BTC-USD defaults safely**

`product_info.py` only has entries for BTC-USD and ETH-USD. SOL-USD and DOGE-USD get BTC-USD defaults (`base_min_size: 0.0001`). For DOGE at ~$0.15, this means $0.000015 minimum order — effectively no minimum. For SOL at ~$130, it's $0.013 minimum. Both are fine for the $25/trade size (10% of $250).

However, Coinbase has actual minimums that may differ. SOL minimum on Coinbase is typically 0.01 SOL (~$1.30). BTC default of 0.0001 is too small. This could cause order rejections on live Coinbase.

**Fix:** Add SOL-USD and DOGE-USD to `_PRODUCT_DEFAULTS` with correct Coinbase minimums.

## Argue (Best Case)
- Architecture is genuinely solid: strategy -> executor -> risk pipeline is well-designed
- All 8 risk layers are implemented and tested
- Mean Reversion strategy has been backtested with corrected methodology
- Paper adapter with real market data source (Coinbase public API) is production-grade
- Event bus + SSE streaming for real-time monitoring exists
- Tax lot tracking is built from day one
- The fixes are all straightforward — no architectural changes needed

## Refute (Devil's Advocate)
- "Live since March 19" was aspirational, not actual — the system was never operational
- Paper soak with zero trades for 5 days means zero validation of the execution pipeline
- The `self._bot` bug suggests the runner has **never been tested end-to-end in production conditions**
- Limit + post_only orders at market price is a fundamental execution design flaw
- No monitoring for "nothing happening" means failures are invisible
- The bot service + API server + command queue architecture adds complexity for IPC that could be simplified (in-process orchestrator would be simpler)
- RSI-3 was backtested but RSI-7 is the default — config mismatch could produce different results

## Gemini Web-Grounded Validation
Skipped — this is an internal system audit, not a technology evaluation. All findings are from direct codebase analysis.

## Philosophical Layer
- **Ethical check:** Trading automation with proper risk controls is fine. The kill switch, circuit breakers, and position limits are appropriate safeguards.
- **First principles:** The separate bot service process is the right architecture for reliability (server restarts don't kill trading loops). The command queue IPC is clean. The issue is purely operational — nothing was deployed.
- **Moonshot:** N/A — this is a bug fix session, not a feature discovery.

## Key Principles Score
| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 5 | 8-layer risk, kill switch, Keychain credentials, no secrets in config |
| Empathy | 2 | User thinks trading is running — it's not. No "nothing is happening" alert. |
| Simplicity | 3 | Architecture is sound but the operational gap (no bots, no service) makes it feel complex |
| Joy | 2 | 5 days of "paper soak" with zero trades is frustrating |

## Recommendation
**Confidence: HIGH**

Execute the following checklist in order:

### Phase A: Code Fixes (do first, then deploy)
- [ ] Fix `self._bot` -> `self.bot` in `bot_runner.py` lines 342, 344
- [ ] Add SOL-USD and DOGE-USD to `product_info.py` `_PRODUCT_DEFAULTS`
- [ ] Decide: keep `mode: "paper"` for initial paper soak, or switch to market orders for live

### Phase B: Bot Seeding (after deploy)
- [ ] Create seed script or curl commands to create 4 Mean Reversion bots via API
- [ ] Each bot needs: `rsi_period: 3`, asset-specific RSI thresholds, `$62.50` capital, `pair` set correctly
- [ ] Start each bot via `POST /v1/trading/bots/{id}/start`

### Phase C: Service Deployment (on Mac Mini)
- [ ] Install trading-bots launchd plist: `cp scripts/launchd/com.hestia.trading-bots.plist ~/Library/LaunchAgents/`
- [ ] Verify Python path in plist matches Mac Mini: `/Users/andrewroman117/hestia/.venv/bin/python`
- [ ] Verify Coinbase credentials exist at `~/.hestia/coinbase-credentials` (file-based, not Keychain — launchd can't access Keychain)
- [ ] Load service: `launchctl load ~/Library/LaunchAgents/com.hestia.trading-bots.plist`
- [ ] Check logs: `tail -f ~/hestia/logs/trading-bots.log`

### Phase D: Deploy Script Update
- [ ] Add trading-bots service restart to `deploy-to-mini.sh`

### Phase E: Verification
- [ ] Check `GET /v1/trading/bots` — all 4 should show `status: running`
- [ ] Check `GET /v1/trading/trades` — should start showing trades within 15 min (poll interval)
- [ ] Check logs for "BotRunner started" and "Signal:" messages
- [ ] Verify SSE stream shows decision events: `GET /v1/trading/stream`

## Final Critiques
- **Skeptic:** "What if the bot service crashes on startup due to an import or config error?" — Valid. The launchd plist has `KeepAlive: SuccessfulExit: false` which will restart on crashes, plus `ThrottleInterval: 10` to prevent rapid restart loops. But you should test locally first: `python -m hestia.trading.bot_service` and verify it starts cleanly.
- **Pragmatist:** "Is the separate process architecture worth the IPC complexity?" — For now, yes. The API server has a complex shutdown sequence and Uvicorn recycling. Keeping bots in a separate process means server restarts don't interrupt trading loops. The command queue IPC is simple (SQLite polling). Revisit if this becomes a maintenance burden.
- **Long-Term Thinker:** "What happens when you scale to 10+ bots?" — The `BotOrchestrator` runs each bot as an `asyncio.Task` in the same event loop. This scales to dozens of bots on M1. The 15-minute poll interval means very low CPU usage. The real limit is the Coinbase API rate limit (10 req/s). With 4 bots each making ~3 API calls per tick, at 15-min intervals, this is well within limits.

## Open Questions
1. **Paper or live first?** Config says `mode: "live"` but no trades have ever executed. Recommend switching to `mode: "paper"` first to validate the full pipeline, then switch to live after 30+ paper fills confirm the system works end-to-end.
2. **Coinbase credentials on Mac Mini**: Are they stored in `~/.hestia/coinbase-credentials`? The `CoinbaseAdapter.connect()` tries file-based creds first, then Keychain fallback. Launchd context may not have Keychain access.
3. **RSI-3 vs RSI-7**: The backtested configs use RSI-3 but the YAML default is RSI-7. The per-bot config must explicitly override this.
4. **Limit order execution**: Post-only limit orders at market price will be rejected by Coinbase. Need to either use market orders or implement smart limit pricing (offset from best bid/ask).
