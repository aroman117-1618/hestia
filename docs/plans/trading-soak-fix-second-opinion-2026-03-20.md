# Second Opinion: Trading Soak Fix + Monitoring

**Date:** 2026-03-20
**Models:** Claude Opus 4.6 (internal) + Gemini 2.5 Pro (external)
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary

Fix the non-functional Sprint 27 paper soak (zero trades in 24+ hours due to PaperAdapter having no market data source) and add monitoring to prevent future silent failures. The core fix adds a dependency-injected market data callable to PaperAdapter wired to Coinbase's public API. Monitoring adds ntfy.sh push alerts and health checks.

## Scale Assessment

| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|----------------|-------------------|
| Single user | Yes | None | N/A |
| Family (2-5) | Yes | ntfy topic is global — need per-user topics | Low |
| Community | Needs work | Single exchange adapter instance shared | Medium |

No scale concerns for a bug fix plan.

## Front-Line Engineering

- **Feasibility:** High confidence. CoinbaseAdapter already uses the exact same DataLoader path. Proven code being wired to a new consumer.
- **Hidden prerequisites:** (1) Validate Coinbase SDK works on Mac Mini before deploying. (2) ntfy.sh topic needs creation.
- **Testing gaps:** Spec says 2h but doesn't specify test scenarios. Need: PaperAdapter with/without market_data_source, candle-to-signal integration test.

## Architecture Review

- **Fit:** Clean DI pattern — consistent with Hestia's constructor injection style.
- **Data model:** No schema changes. Trading DB untouched.
- **Integration risk:** Low — only PaperAdapter and TradingManager.initialize() change. BotRunner, strategies, risk manager all untouched.
- **Concern (CTO):** The spec's `get_ticker()` change fetches a full day of 1h candles just to extract the last close price. Should cache the last DataFrame from `get_candles()` and extract price from it.

## Product Review

- **User value:** Direct and critical — unblocks the entire trading roadmap (Sprints 27-30).
- **Scope:** Right-sized for the core fix. Monitoring layer could be phased.
- **Opportunity cost:** ~9h that could go toward Sprint 28 prep. But Sprint 27 Go-Live is the critical path — correct priority.

## UX Review

Skipped — no UI changes.

## Infrastructure Review

- **Deployment:** rsync Python files + restart bot service. Server doesn't need restart (trading is separate launchd service).
- **Rollback:** Remove `market_data_source` param → PaperAdapter falls back to `return None`. Clean rollback.
- **Resource impact:** Negligible on M1.
- **Concern:** Two monitoring launchd services (watchdog + health monitor) could create alert storms on the same failure.

## Executive Verdicts

- **CISO:** Acceptable — no new credentials, public API only, ntfy.sh is push-only
- **CTO:** Approve with conditions — fix get_ticker() inefficiency, consider phasing monitoring
- **CPO:** Acceptable — directly unblocks critical path, monitoring justified by 400-restart incident
- **CFO:** Acceptable — 9h justified by unblocking 60h+ of downstream trading work
- **Legal:** Acceptable — public API compliant with Coinbase terms, paper trading has no regulatory triggers

## Key Principles Score

| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 5 | No new attack surface, public API only |
| Empathy | 5 | Directly unblocks Andrew's top priority |
| Simplicity | 3 | Composite adapter adds a layer; monitoring adds shell scripts + launchd. Gemini recommends simplifying. |
| Joy | 4 | Seeing real signals and trades from the soak will validate weeks of work |

## Final Critiques

1. **Most likely failure:** Coinbase SDK returns empty candles on Mac Mini for environment-specific reasons (SSL, SDK version). **Mitigation:** Run DataLoader test script on Mac Mini before deploying.
2. **Critical assumption:** `coinbase-advanced-py` behaves identically on Mac Mini as dev Mac. **Validation:** `python3 -c "from hestia.trading.backtest.data_loader import DataLoader; import asyncio; dl = DataLoader(); df = asyncio.run(dl.fetch_from_coinbase('BTC-USD', '1h')); print(f'{len(df)} candles')"` on Mac Mini.
3. **Half-time cut list (~4.5h):** Keep PaperAdapter fix + TradingManager wiring (~2h) + ntfy.sh on watchdog (~15min) + tests (~1.5h). Cut: health monitor shell script, /check-soak skill, watchdog cooldown.

## Cross-Model Validation (Gemini 2.5 Pro)

### Gemini's Independent Assessment

Gemini confirms the core fix is architecturally sound and the DI pattern is the correct approach. It rates the composite paper mode as "far more valuable" than testing with synthetic data. However, it flags the 7:2 ratio of monitoring-to-fix effort as disproportionate and recommends significant simplification.

### Where Both Models Agree

- The DI callable pattern for `market_data_source` is correct and clean
- Composite paper mode (real data + paper fills) is better than switching to live trading
- The core fix is ~2h; monitoring is the bulk of the estimate
- `get_ticker()` fetching a full day of candles for spot price is wasteful and should be fixed
- The Coinbase SDK must be validated on Mac Mini before deploying
- ntfy.sh is a reasonable choice for push notifications

### Where Models Diverge

| Topic | Claude | Gemini | Resolution |
|-------|--------|--------|------------|
| Health monitor implementation | Shell script + launchd job | Python asyncio task inside bot_service | **Gemini is right.** Internal task has direct access to bot state, no new launchd config, no shell scripts. System watchdog covers process death. |
| Alert consolidation | Both watchdog and health monitor send ntfy | Only watchdog sends ntfy; health monitor logs to file/endpoint | **Gemini is right.** Prevents alert storms and simplifies reasoning about what each layer does. |
| Recovery plan | Not addressed | Non-negotiable — must document how to safely pause the bot on alert | **Gemini is right.** We have kill switch and circuit breakers, but no documented "I got an alert at 3 AM, what do I do?" procedure. |
| Data pipeline health | Not checked | Verify last candle timestamp is fresh, not just that signals exist | **Gemini is right.** A stale-data check is more reliable than "signals were generated." |

### Novel Insights from Gemini

1. **Recovery procedure is mandatory** for an autonomous financial system. The existing kill switch and circuit breakers exist but there's no documented quick-response playbook.
2. **Move health checks inside bot_service** as an asyncio task — eliminates an entire shell script, launchd plist, and configuration surface. The system watchdog handles process-level failures; the internal monitor handles logic-level failures.
3. **Data freshness check** — verify the timestamp of the last received candle, not just that signals are being generated. A bot could be "generating signals" from stale data.
4. **Configuration validation** — a typo in a launchd plist or YAML alerts section could silently disable monitoring. Internal Python checks are type-safe.

### Reconciliation

Both models agree the core fix is sound and should ship immediately. The divergence is on monitoring architecture. Gemini's proposal to internalize health checks as a Python asyncio task inside bot_service is simpler, more maintainable, and eliminates operational complexity. The two-layer model (system watchdog for process health, internal task for logic health) is cleaner than two external monitoring scripts.

## Conditions for Approval

1. **Ship the core fix first** — PaperAdapter market_data_source + TradingManager wiring. Get candles flowing and the soak producing signals before adding monitoring.

2. **Validate on Mac Mini before deploying** — run the DataLoader test script directly on Mac Mini. If it returns 0 candles, debug before proceeding.

3. **Fix `get_ticker()` inefficiency** — cache the last candle DataFrame from `get_candles()` and extract the closing price. Don't fetch a full day of candles for a spot price.

4. **Simplify monitoring per Gemini's recommendation:**
   - Watchdog: just add `HESTIA_NTFY_TOPIC` env var to launchd plist (15 min)
   - Health checks: asyncio task inside bot_service, not a separate shell script
   - Expose trading health via `/v1/trading/health` endpoint (already partially exists)
   - Only watchdog sends ntfy.sh alerts (process-level). Health checks log to file.

5. **Document a recovery playbook** — what to do when you get an alert:
   - Check: `ssh hestia-3.local "curl -sk https://localhost:8443/v1/trading/bots"`
   - Pause: `ssh hestia-3.local "launchctl stop com.hestia.trading-bots"`
   - Kill switch: already exists in risk manager
   - Resume: `ssh hestia-3.local "launchctl start com.hestia.trading-bots"`

6. **Add data freshness check** to the internal health monitor — verify last candle timestamp is < 30 min old.

## Revised Effort Estimate

| Component | Hours |
|-----------|-------|
| PaperAdapter market data delegation + get_ticker fix | 1.5 |
| TradingManager wiring | 0.5 |
| Internal health monitor (asyncio task in bot_service) | 2 |
| ntfy.sh on watchdog (env var + plist update) | 0.5 |
| Recovery playbook doc | 0.5 |
| Mac Mini validation + deploy + bot restart | 1 |
| Tests | 1.5 |
| **Total** | **~7.5h** |

Savings of ~1.5h by eliminating the shell script health monitor and /check-soak skill, replacing with a simpler internal asyncio task.
