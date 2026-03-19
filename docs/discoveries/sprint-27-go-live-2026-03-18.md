# Discovery Report: Sprint 27 — Go-Live (Bot Runner + Paper Soak + Capital Deploy)

**Date:** 2026-03-18
**Confidence:** High
**Decision:** Build the Bot Runner engine, wire market data, validate with 72h paper soak, then deploy $25 of real capital.

## Context

Sprints 21-26 built every component of the trading pipeline — strategies, risk management, execution, backtesting, Coinbase adapter, dashboard, alerts. But nothing *runs*. `start_bot()` changes a database row and nothing else. Sprint 27 assembles the car from the parts.

## What Exists (fully tested, reviewed, committed)

| Component | Status | File |
|-----------|--------|------|
| Grid + Mean Reversion strategies | 42 tests | `strategies/grid.py`, `strategies/mean_reversion.py` |
| 8-layer risk management | Persisted to DB | `risk.py` (kill switch survives restart) |
| TradeExecutor pipeline | Signal→Risk→Price→Exchange | `executor.py` |
| Coinbase REST (async, non-blocking) | `run_in_executor` wrapped | `exchange/coinbase.py` |
| Coinbase WebSocket (drafted) | Callbacks, sequence tracking | `exchange/coinbase_ws.py` |
| Paper adapter | Realistic slippage + fees | `exchange/paper.py` |
| PositionTracker | Async with lock, reconciliation loop | `position_tracker.py` |
| Dashboard (SSE + REST) | 23 endpoints, macOS UI wired | `routes/trading.py` |
| Confidence scoring | Composite 4-factor metric | `scoring.py` |
| Alerts | Discord + push, rate-limited | `alerts.py` |
| Tax lot tracking | HIFO/FIFO from day one | `database.py` |

## What's Missing

| Gap | Description | Effort |
|-----|-------------|--------|
| **BotRunner** | Async loop: poll candles → compute indicators → strategy.analyze() → executor.execute_signal() | 3h |
| **BotOrchestrator** | Manages BotRunner lifecycle: spawn on start, cancel on stop, resume on server restart | 2h |
| **Market data polling** | Fetch OHLCV candles from Coinbase REST on interval (1h candles, 15min poll) | 1h |
| **WebSocket wiring** | Connect CoinbaseWebSocketFeed, register callbacks, feed into MarketDataFeed | 2h |
| **Event publishing** | TradeExecutor + RiskManager publish to TradingEventBus on trade/alert/kill switch | 1h |
| **Daily summary generation** | Scheduled job at UTC midnight to aggregate trades → daily_summaries table | 1h |
| **Reconciliation loop startup** | Call PositionTracker.start_reconciliation_loop() in orchestrator | 30min |
| **Paper soak test** | 72h paper trading with real Coinbase prices, monitor dashboard | Time |
| **Security review** | Verify API key scoping, no withdrawal permissions, error handling | 1h |
| **Capital deployment** | Switch config from paper→coinbase, start with $25 (10% of $250) | 30min |

**Total code: ~12h. Total elapsed with soak: ~4 days.**

## Architecture: Bot Runner

```
Server startup
  └→ BotOrchestrator.resume_running_bots()
       └→ For each bot with status=RUNNING:
            └→ asyncio.create_task(BotRunner(bot).run())

BotRunner.run() loop:
  1. Fetch 200 candles (Coinbase REST, 1h granularity)
  2. Add technical indicators (RSI, SMA, EMA, Bollinger, ATR, ADX)
  3. Call strategy.analyze(df, portfolio_value) → Signal
  4. If signal.is_actionable:
     a. TradeExecutor.execute_signal(signal, portfolio_value)
     b. TradingManager.record_trade(trade_data + decision_trail + confidence_score)
     c. EventBus.publish(trade event)
     d. TradingAlerter.send_trade_alert()
  5. Sleep 15 minutes (for 1h candle strategy)
  6. Repeat until bot.status != RUNNING

POST /v1/trading/bots/{id}/start
  └→ manager.start_bot(id) → sets status=RUNNING
  └→ orchestrator.start_runner(bot) → spawns BotRunner task

POST /v1/trading/bots/{id}/stop
  └→ manager.stop_bot(id) → sets status=STOPPED
  └→ orchestrator.stop_runner(bot_id) → cancels BotRunner task
```

## 6 Workstreams

### WS1: BotRunner (~3h)
New file: `hestia/trading/bot_runner.py`

Core async loop. One runner per bot. Fetches candles, generates signals, executes trades. Handles errors gracefully (log + sleep + retry). Publishes events to SSE bus. Records trades with decision trail + confidence score.

### WS2: BotOrchestrator (~2h)
New file: `hestia/trading/orchestrator.py`

Manages BotRunner lifecycle. Spawns runners on bot start. Cancels on stop. Resumes all RUNNING bots on server startup. Integrates with server.py lifespan. Tracks active tasks in a dict[bot_id → asyncio.Task].

### WS3: Market Data + Indicators (~1h)
Modify: `hestia/trading/data/feed.py`, `hestia/trading/exchange/coinbase.py`

Add `get_candles()` method to CoinbaseAdapter (REST endpoint for OHLCV). Wire into MarketDataFeed. Compute indicators via existing `add_all_indicators()`.

### WS4: WebSocket Integration (~2h)
Modify: `hestia/trading/exchange/coinbase_ws.py`, `hestia/trading/bot_runner.py`

Connect WebSocket for real-time price updates between candle polls. Register callbacks: on_ticker → update latest price, on_fill → record fill + update position. on_candle → update MarketDataFeed. Graceful fallback if WebSocket disconnects (use REST polling).

### WS5: Event Publishing + Daily Summary (~2h)
Modify: `hestia/trading/executor.py`, `hestia/trading/risk.py`, `hestia/trading/manager.py`

Wire event bus publishing into executor (trade events), risk manager (alert events), manager (kill switch events). Add daily summary generation method + schedule via LearningScheduler or standalone timer.

### WS6: Security Review + Paper Soak + Capital Deploy (~2h code + 72h soak)
- Verify Coinbase API key scoping (trade-only, no withdrawal)
- Run paper mode for 72h with real Coinbase prices
- Monitor dashboard: trades executing, risk working, kill switch functional
- Validate on Mac Mini (production server)
- Switch config: `mode: paper` → `mode: coinbase`
- Start with $25 (10% of $250 account)
- Ramp: $25 → $60 → $125 → $250 over 4 weeks

## Risk Assessment

### Safety Layers (all implemented)
1. API key scoped to trade-only (no withdrawal) ✅
2. Position limits (25% single trade, 80% deployed) ✅
3. Quarter-Kelly sizing ✅
4. Drawdown circuit breaker (15%) ✅
5. Daily loss limit (5%) ✅
6. Latency circuit breaker (2000ms) ✅
7. Price divergence check (2%) ✅
8. 60-sec reconciliation loop ✅
9. Kill switch (persisted, dashboard toggle) ✅
10. Rate-limited alerts (Discord + push) ✅

### What Could Go Wrong
1. **Strategy generates bad signals** → Mitigated by risk layers 2-7. Worst case: 5% daily loss before breaker fires.
2. **Coinbase API changes** → Mitigated by SDK abstraction. Monitor for deprecation warnings.
3. **Server crash during open position** → On restart, reconciliation detects discrepancy, kill switch state survives.
4. **Price feed glitch** → Layer 7 (price divergence) catches single-source glitches.
5. **Bug in BotRunner loop** → try/except around entire loop body, log + sleep + retry. Kill switch as manual override.

### Maximum Loss Scenario
- Starting capital: $25
- Worst case: 5% daily loss limit → $1.25/day before circuit breaker fires
- If all breakers fail simultaneously (near-impossible): $25 total loss
- No withdrawal risk (API key scoped)
