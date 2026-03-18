# Hestia Trading Module: Research & Development Plan

**Date:** 2026-03-18
**Author:** Claude (Research) + Andrew (Direction)
**Status:** APPROVED — Ready for Sprint 21 Build
**Approved:** 2026-03-18

---

## Executive Summary

This document outlines the research findings and development plan for an autonomous algorithmic cryptocurrency trading module integrated into Hestia. The system will manage a $500–$2,000 fund using multiple strategies across Coinbase (primary) with expansion capability to additional exchanges. Target: 25–50% annualized returns with moderate risk tolerance, fully autonomous operation with human override.

**Scope:** Full trading module (multiple strategies, backtesting, risk management, monitoring) with AI-enhanced features (sentiment analysis, on-chain signals) added incrementally.

**Estimated effort:** 10 sprints (Sprints 21–30), building on Hestia's existing manager pattern.
**Workstream:** Trading Module (WS-TRADING)
**GitHub Projects Label:** `workstream:trading`
**Milestone:** Hestia v2.0 — Autonomous Trading

---

## Table of Contents

1. Research Findings
2. Architecture Design
3. Sprint Breakdown (21–30)
4. Risk Management Framework
5. Infrastructure & Deployment
6. Success Metrics & Evaluation
7. Decisions (Resolved)
8. Gemini Deep Research Review
9. Dependencies & Prerequisites

---

## 1. Research Findings

### 1.1 Market Reality Check

The Instagram post that inspired this project claimed $238K profit from $1,400 in 11 days (170x return). This is not achievable through legitimate algorithmic trading. For calibration:

- Renaissance Technologies (best hedge fund in history): ~66% annual returns
- Top quantitative crypto funds: 30–60% annually
- Retail algo traders with good systems: 15–25% annually
- Grid trading bots in favorable conditions: 15–40% annually

A 5–10x return in one year requires either extreme leverage (which historically destroys small accounts), a lucky concentrated altcoin bet (gambling, not trading), or fraud.

**Our target of 25–50% annually is ambitious but achievable** with disciplined multi-strategy execution and moderate risk tolerance. This would turn $2,000 into $2,500–$3,000 in year one, compounding to $6,250–$14,000 over 5 years.

### 1.2 Viable Strategies for $500–$2,000 Capital

#### Grid Trading (Primary — 35% allocation)
- Places buy/sell orders at **geometric** (percentage-based) intervals within a price range
- **Critical: Must use geometric spacing, not arithmetic.** Arithmetic grids lose fee efficiency as price rises; geometric maintains constant fee-to-profit ratio at every level (Gemini review finding)
- Grid width must be ≥ 2× ATR of chosen timeframe to prevent being "gapped" by volatility
- **Execution: Post-Only limit orders only** — maker fees are significantly lower than taker; at our capital level, the fee difference is 5–10% annually
- Backtested returns: 15–40% annually in favorable conditions
- Risk: Fails in strong trends; requires regime detection + "re-grid" mechanism
- Best pairs: BTC/USDT, ETH/USDT (highest liquidity, lowest slippage)

#### Mean Reversion (Secondary — 20% allocation)
- **Crypto-optimized RSI: 7–9 period lookback with 20/80 thresholds** (not standard 30/70 with 14-period — those are equity defaults that produce delayed signals in crypto)
- Entry requires volume confirmation: ≥ 1.5× 20-period average volume
- Trend filter: 50-period SMA direction or ADX > 25 to avoid "momentum trap" entries
- Backtested returns: 10–20% annually
- Risk: Catastrophic in breakout/momentum markets — "falling knife" entries without filters
- Requires hard stop-losses (non-negotiable)

#### Signal-Enhanced DCA (Accumulation — 25% allocation)
- Systematic accumulation triggered by RSI + MA confluence signals
- Outperforms lump-sum in 65% of backtested scenarios
- Returns: 20–50% in trending markets
- Lowest risk of all strategies; natural hedge against timing errors

#### Bollinger Band Breakout (Trend Capture — 20% allocation) ← NEW
- **Added based on Gemini review:** All other strategies are range-bound; this captures trending moves
- Enter when price closes outside 2σ Bollinger Band with high volume confirmation
- Provides critical **regime diversification** — profits exactly when grid trading fails
- Acts as natural counterweight to grid strategy's range-bound bias
- Risk: False breakouts in choppy markets; mitigated by volume filter + ATR confirmation

### 1.3 AI/ML Enhancement Opportunities

#### Sentiment Analysis (Phase 2)
- LLM-powered scanning of crypto Twitter, Reddit, news feeds
- 2–5% improvement over technical-only baseline
- Integration: Weight trade signals based on sentiment score
- Cost: $50–$200/month in LLM API calls (Hestia's cloud inference)
- Lag: Sentiment follows price by 1–2 hours; useful for medium-term signals, not scalping

#### On-Chain Data (Phase 2)
- Whale wallet accumulation, exchange inflows/outflows, active addresses
- Free data from Glassnode, Dune Analytics APIs
- Signal: Whale accumulation during corrections preceded 23% BTC rally in Jan 2026
- Lag: 6–12 hours between on-chain event and price move
- Best use: Regime detection (accumulation vs. distribution phase)

#### ML Strategy Optimization (Phase 3)
- Train models to optimize grid spacing, RSI thresholds, position sizing
- VectorBT + scikit-learn for parameter optimization
- Risk: Extreme overfitting potential; requires rigorous out-of-sample testing
- Timeline: After 3+ months of live trading data

### 1.4 Coinbase Advanced Trade API

- REST + WebSocket API, JWT authentication
- Order types: Market, Limit, Stop, Bracket, TWAP, Iceberg
- Rate limits: 30 req/sec private, 10 req/sec public
- Fees: 0.40% maker / 0.60% taker at <$10K monthly volume (use Post-Only orders to guarantee maker rate)
- **Critical: API keys must be scoped to "Consumer Default Spot" portfolio** — wrong portfolio scope causes silent 401 failures (Gemini finding)
- Official Python SDK: `coinbase-advanced-py`
- No explicit restrictions on automated trading
- API keys can be scoped to trade-only (no withdrawal) with IP allowlisting

### 1.5 Python Trading Ecosystem

| Component | Recommended | Rationale |
|-----------|-------------|-----------|
| Exchange API | CCXT + coinbase-advanced-py | CCXT for abstraction + multi-exchange; official SDK for Coinbase-specific features |
| Backtesting | VectorBT | Fastest (Numba JIT), tick-level resolution, Binance fill matching ±0.3% |
| Indicators | pandas-ta | 150+ indicators, Pandas-native, actively maintained |
| Data | CCXT historical + WebSocket real-time | Free, comprehensive, exchange-native |
| ML/AI | scikit-learn + Hestia's cloud inference | Strategy optimization + LLM sentiment |

---

## 2. Architecture Design

### 2.1 Module Structure (Hestia Pattern)

```
hestia/trading/
├── models.py              # Dataclasses: Trade, Order, Position, Strategy, BotConfig, PerformanceMetrics, TaxLot
├── database.py            # TradingDatabase (SQLite WAL mode): trades, orders, positions, signals, tax_lots
├── manager.py             # TradingManager singleton (async factory pattern)
├── strategies/
│   ├── base.py            # BaseStrategy ABC: analyze(), execute(), backtest()
│   ├── grid.py            # GridStrategy (GEOMETRIC spacing, Post-Only maker orders)
│   ├── mean_reversion.py  # MeanReversionStrategy (RSI-7/9, 20/80 thresholds, volume filter)
│   ├── dca_signal.py      # SignalDCAStrategy (RSI + MA confluence accumulation)
│   └── bollinger.py       # BollingerBreakoutStrategy (2σ breakout + volume, trend capture)
├── risk/
│   ├── manager.py         # RiskManager: validates every order, Quarter-Kelly sizing
│   ├── position_tracker.py # Real-time exposure + 60-sec exchange reconciliation
│   ├── circuit_breaker.py # Emergency stops: drawdown, daily loss, ATR, API latency
│   └── price_validator.py # Redundant price feed verification (anti-glitch)
├── exchange/
│   ├── base.py            # ExchangeAdapter ABC (unified interface, CCXT-ready)
│   ├── coinbase.py        # CoinbaseAdapter (REST + WebSocket, Post-Only default)
│   ├── paper.py           # PaperTradingAdapter (simulation with realistic slippage)
│   └── factory.py         # ExchangeFactory (mode → adapter)
├── data/
│   ├── feed.py            # MarketDataFeed (WebSocket + REST fallback + sequence checking)
│   ├── cache.py           # OHLCVCache (SQLite WAL time-series, point-in-time aware)
│   └── indicators.py      # Technical indicator layer (pandas-ta: RSI, SMA, BB, ATR, ADX)
├── tax/
│   ├── lot_tracker.py     # HIFO/FIFO cost-basis tracking per trade (1099-DA ready)
│   ├── reporter.py        # Tax report generation (annual summary, per-trade detail)
│   └── wash_monitor.py    # Wash sale detection (future-proofing for regulatory changes)
├── ai/
│   ├── sentiment.py       # LLM regime filter (cloud → local migration path)
│   ├── onchain.py         # On-chain data with point-in-time ingestion timestamps
│   └── optimizer.py       # Walk-forward parameter optimization (30d train / 7d validate)
├── backtest/
│   ├── engine.py          # VectorBT integration (slippage + maker/taker fee modeling)
│   ├── report.py          # Backtest report (Sharpe, Sortino, max DD, equity curve)
│   └── data_loader.py     # Historical OHLCV with point-in-time data integrity
└── config/
    └── trading.yaml       # Strategy params, risk limits, exchange config, tax settings
```

### 2.2 API Endpoints (~20 new endpoints)

```
POST   /v1/trading/bots                    # Create/configure trading bot
GET    /v1/trading/bots                    # List all bots
GET    /v1/trading/bots/{id}               # Bot details + performance
PUT    /v1/trading/bots/{id}               # Update bot config
DELETE /v1/trading/bots/{id}               # Stop and remove bot
POST   /v1/trading/bots/{id}/start         # Activate bot
POST   /v1/trading/bots/{id}/stop          # Pause bot
POST   /v1/trading/bots/{id}/paper         # Switch to paper trading mode
GET    /v1/trading/bots/{id}/trades        # Trade history
GET    /v1/trading/bots/{id}/performance   # P&L, Sharpe, drawdown, win rate
GET    /v1/trading/bots/{id}/signals       # Signal history with reasoning
POST   /v1/trading/backtest               # Run backtest on historical data
GET    /v1/trading/backtest/{id}          # Backtest results
GET    /v1/trading/portfolio              # Aggregate portfolio view
GET    /v1/trading/portfolio/allocation   # Current allocation across strategies
GET    /v1/trading/risk/status            # Risk manager state (limits, breakers)
PUT    /v1/trading/risk/config            # Update risk parameters
POST   /v1/trading/fund                   # Add/withdraw funds
GET    /v1/trading/fund/history           # Fund movement history
GET    /v1/trading/tax/summary            # Annual tax summary (1099-DA ready)
GET    /v1/trading/tax/lots               # Individual tax lot detail (HIFO/FIFO)
GET    /v1/trading/reconciliation/status  # Exchange ↔ local state sync status
POST   /v1/trading/reconciliation/force   # Force immediate reconciliation
GET    /v1/trading/daily-summary          # Daily recap (P&L, trades, risk, attribution)
SSE    /v1/trading/stream/{bot_id}        # Real-time trade + P&L stream
```

### 2.3 Data Flow

```
Market Data (WebSocket + sequence checking)
    ↓                                    ↗ Redundant Price Feed (CoinGecko)
OHLCV Cache (SQLite WAL time-series)  ←── Price Validator (anti-glitch cross-check)
    ↓
Technical Indicators (pandas-ta: RSI-7, BB, ATR, ADX, Volume)
    ↓                          ↓ (Phase 2)
Strategy Engine ←───── AI Regime Filter (sentiment, on-chain)
    ↓
Risk Manager (Quarter-Kelly sizing, position limits, circuit breakers, API latency check)
    ↓ (approved)
Order Executor (Post-Only maker orders default)
    ↓                              ↗ Exchange Reconciliation (60-sec sync loop)
Trade Audit Log + Tax Lot Tracker (every decision, every fill, cost basis)
    ↓
Performance Calculator (real-time: Sharpe, win rate, drawdown, P&L)
    ↓
SSE Stream → iOS/macOS Dashboard + Daily Summary + Discord Alerts
```

### 2.4 iOS/macOS Integration

New "Trading" tab in both apps:

- **Dashboard view**: Portfolio value, today's P&L, active bots, recent trades
- **Bot detail view**: Strategy parameters, performance chart, trade history
- **Risk view**: Current exposure, drawdown gauge, circuit breaker status
- **Backtest view**: Run backtests, compare strategies, visualize results
- **Fund management**: Add/withdraw, allocation adjustments

### 2.5 Safety Architecture

**Defense in depth — eight layers (expanded per Gemini review):**

1. **API Key Scoping**: Trade-only permissions, no withdrawal, IP allowlisted, scoped to "Consumer Default Spot" portfolio
2. **Position Limits**: Max 25% of fund in any single trade, max 80% total deployed
3. **Quarter-Kelly Sizing**: Conservative position sizing during parameter estimation phase (first 3 months)
4. **Drawdown Circuit Breaker**: Pause all trading if drawdown exceeds 15% from peak
5. **Daily Loss Limit**: Halt for 24h if daily loss exceeds 5% of fund
6. **API Latency Breaker**: Pause new orders if exchange API response > 2000ms (indicates exchange instability during volatility — exactly when losses are worst)
7. **Price Validation**: Cross-check prices against secondary feed before executing; reject if >2% divergence (prevents trading on data glitches)
8. **Emergency Kill Switch**: Manual override via API, iOS app, macOS app, or CLI — instantly closes all positions

**Exchange State Reconciliation**: Background task syncs local position state with actual exchange balances every 60 seconds. Catches phantom fills, missed orders, and state drift from API glitches.

**Credentials**: Exchange API keys stored in Hestia's existing Keychain + Fernet double encryption (CredentialManager). Never in config files, never in logs.

---

## 3. Sprint Breakdown

> **Note:** Sprint numbers 1–20 are already complete (see SPRINT.md / GitHub Projects).
> Trading module begins at Sprint 21 and runs through Sprint 30.
> Each sprint maps to a GitHub Projects issue with label `workstream:trading`.

---

### Sprint 21: Trading Foundation (Est. 1 session)
<!-- GH Projects: priority=P0, size=L, phase=Engine, depends=none -->
**Goal:** Core module structure, database (WAL mode), paper trading adapter, tax lot tracking

- [ ] Create `hestia/trading/` module structure (all directories)
- [ ] Implement `models.py` (Trade, Order, Position, BotConfig, PerformanceMetrics, **TaxLot**)
- [ ] Implement `database.py` (TradingDatabase — **SQLite WAL mode + MMIO enabled from day one**)
  - Tables: trades, orders, positions, signals, **tax_lots** (HIFO/FIFO cost-basis tracking)
  - Periodic VACUUM scheduled task
- [ ] Implement `manager.py` skeleton (TradingManager singleton)
- [ ] Implement `exchange/paper.py` (PaperTradingAdapter with **realistic slippage modeling**)
- [ ] Implement `exchange/base.py` (ExchangeAdapter ABC — **CCXT-compatible interface for future Kraken**)
- [ ] Implement `tax/lot_tracker.py` (HIFO/FIFO cost-basis per fill — **1099-DA compliance from day one**)
- [ ] Add `LogComponent.TRADING` to logging system
- [ ] Create `config/trading.yaml` with default parameters
- [ ] Basic API routes (CRUD for bots, start/stop)
- [ ] Tests: 45+ unit tests for models, database (WAL), paper adapter, tax lot tracker

### Sprint 22: Strategy Engine (Est. 1–2 sessions)
<!-- GH Projects: priority=P0, size=XL, phase=Engine, depends=S21 -->
**Goal:** Strategy abstraction + Grid Trading (geometric) + Mean Reversion (crypto-optimized)

- [ ] Implement `strategies/base.py` (BaseStrategy ABC with analyze/execute/backtest)
- [ ] Implement `data/feed.py` (MarketDataFeed — REST polling for MVP, WebSocket later)
- [ ] Implement `data/indicators.py` (pandas-ta wrapper: **RSI-7/9, SMA, EMA, Bollinger 2σ, ATR, ADX, Volume**)
- [ ] Implement `strategies/grid.py`:
  - **Geometric spacing** (percentage-based intervals, not fixed dollar)
  - Grid width ≥ 2× ATR of chosen timeframe
  - **Post-Only limit orders** as default execution mode
  - Re-grid mechanism when price exits range
- [ ] Implement `strategies/mean_reversion.py`:
  - **RSI-7 or RSI-9** lookback (not 14-period equity default)
  - **20/80 thresholds** (not 30/70)
  - **Volume confirmation**: entry requires ≥ 1.5× 20-period avg volume
  - **Trend filter**: 50-period SMA direction check to avoid momentum traps
- [ ] Strategy parameter validation (warn on likely-overfit configs: Sharpe > 3.0)
- [ ] Paper trading integration tests (run grid + mean reversion on historical data)
- [ ] Tests: 55+ tests for strategies, indicators, geometric grid math, data feed

### Sprint 23: Risk Management (Est. 1 session)
<!-- GH Projects: priority=P0, size=L, phase=Engine, depends=S22 -->
**Goal:** Position tracking, circuit breakers (8 triggers), safety controls, exchange reconciliation

- [ ] Implement `risk/position_tracker.py`:
  - Real-time exposure + unrealized P&L
  - **60-second exchange reconciliation loop** (sync local state with actual exchange balances)
- [ ] Implement `risk/circuit_breaker.py`:
  - Drawdown limit (15%), daily loss (5%), weekly loss (10%)
  - Volatility filter (ATR > 2× normal)
  - **API latency breaker** (pause if response > 2000ms)
  - **Price feed divergence** (halt if > 2% cross-feed discrepancy)
- [ ] Implement `risk/price_validator.py` (redundant price feed via CoinGecko API for cross-check)
- [ ] Implement `risk/manager.py` (RiskManager: validates every order, **Quarter-Kelly sizing default**)
- [ ] Emergency kill switch endpoint (API + iOS + macOS + CLI triggered)
- [ ] Risk status API endpoints
- [ ] Integration: Strategy → Risk Manager → Price Validator → Executor pipeline
- [ ] Tests: 40+ tests for risk scenarios (drawdown, latency, reconciliation, price divergence, kill switch)

### Sprint 24: Backtesting Engine (Est. 1–2 sessions)
<!-- GH Projects: priority=P0, size=XL, phase=Engine, depends=S22 (can parallel with S23) -->
**Goal:** Historical data fetching, VectorBT integration, anti-overfit validation

- [ ] Implement `backtest/data_loader.py` (fetch + cache OHLCV from Coinbase, **point-in-time aware**)
- [ ] Implement `backtest/engine.py`:
  - VectorBT wrapper with **maker/taker fee modeling** (not flat fee)
  - Realistic slippage model (0.1–0.5% based on order size / liquidity)
  - **Look-ahead bias prevention**: signals shifted back 1 candle
- [ ] Implement `backtest/report.py` (Sharpe, Sortino, max drawdown, win rate, equity curve)
  - **Overfit detection**: warn if Sharpe > 3.0 or win rate > 70% (likely curve-fit)
- [ ] Backtest API endpoints
- [ ] Run backtests on BTC/ETH for past 12 months with all strategies
- [ ] **Out-of-sample testing (70/30 train/test split) — mandatory before any strategy goes live**
- [ ] **Walk-forward validation**: 30-day train / 7-day test windows, shift forward
- [ ] Tests: 30+ tests for backtest engine, data loading, overfit detection, report generation

### Sprint 25: Coinbase Live Integration (Est. 1–2 sessions)
<!-- GH Projects: priority=P0, size=XL, phase=Exchange, depends=S23+S24 -->
**Goal:** Real exchange connectivity, WebSocket with sequence checking, live paper trading

- [ ] Implement `exchange/coinbase.py`:
  - REST: order placement (**Post-Only default**), account balances, order status
  - **Portfolio scoping**: explicit "Consumer Default Spot" in all requests
  - Partial fill handling (accumulate fills, update tax lots per fill)
- [ ] Implement WebSocket market data feed:
  - Real-time OHLCV, order book
  - **Sequence number checking** (detect missed messages during disconnects)
  - **Exponential backoff reconnection** (prevent IP ban from rapid reconnects)
- [ ] API key management (Keychain integration via CredentialManager, 90-day rotation reminder)
- [ ] Order lifecycle management (placed → partial → filled → settled)
- [ ] Live paper trading mode (real market data, virtual execution with realistic fill simulation)
- [ ] Connection health monitoring (heartbeat, reconnection logic, latency tracking for circuit breaker)
- [ ] Tests: 25+ integration tests (mocked exchange responses, reconnection scenarios)

### Sprint 26: Monitoring & Dashboard (Est. 1–2 sessions)
<!-- GH Projects: priority=P1, size=XL, phase=UI, depends=S25 -->
**Goal:** Performance tracking, audit logging, SSE streaming, iOS/macOS UI

- [ ] Implement trade audit logger (every decision with full reasoning trace)
- [ ] Performance calculator (real-time: Sharpe, win rate, drawdown, P&L)
- [ ] SSE endpoint for real-time trade/P&L streaming
- [ ] iOS Trading tab (Dashboard, Bot Detail, Risk, Fund Management)
- [ ] macOS Trading view (sidebar integration)
- [ ] Alert system (Discord/push notifications for circuit breakers, large trades)
- [ ] Tests: 20+ tests for performance calculations, SSE streaming

### Sprint 27: Bollinger Breakout + DCA + Portfolio Management (Est. 1–2 sessions)
<!-- GH Projects: priority=P1, size=XL, phase=Strategies, depends=S25 -->
**Goal:** Complete 4-strategy suite, multi-strategy orchestration, daily summary system

- [ ] Implement `strategies/bollinger.py`:
  - Enter on close outside 2σ Bollinger Band with ≥ 1.5× volume + ATR confirmation
  - Trend capture counterweight to grid strategy's range-bound bias
- [ ] Implement `strategies/dca_signal.py` (technical-trigger DCA with RSI/MA confluence)
- [ ] Multi-strategy portfolio manager:
  - Allocation: Grid 35%, Mean Rev 20%, DCA 25%, Bollinger 20%
  - Correlation monitoring (all strategies are long-biased; cash allocation critical in bear regimes)
- [ ] Strategy rotation logic (regime detection → strategy weighting via ATR + trend strength + ADX)
- [ ] Auto-rebalancing (drift threshold triggers reallocation)
- [ ] **Daily summary generator** (P&L, trades executed, risk status, strategy attribution)
- [ ] **Tax report endpoints** (`/v1/trading/tax/summary`, `/v1/trading/tax/lots`)
- [ ] Prepare CCXT abstraction for future Kraken/futures expansion
- [ ] Tests: 35+ tests for Bollinger strategy, DCA, portfolio management, rebalancing, daily summary

### Sprint 28: AI Sentiment as Regime Filter (Est. 1–2 sessions)
<!-- GH Projects: priority=P2, size=L, phase=AI, depends=S27 -->
**Goal:** LLM-powered macro regime classification (NOT primary signal — Gemini validated this approach)

- [ ] Implement `ai/sentiment.py`:
  - **Regime filter, not trade signal** — classify hourly news cycle as "High Risk" or "Normal"
  - High Risk → widen RSI thresholds (25/75 → 15/85), reduce grid exposure 50%
  - Architecture: cloud inference now (Anthropic/OpenAI), **local migration path** (quantized Qwen on M1)
- [ ] Data sources: CryptoPanic API (free tier), Reddit API
- [ ] LLM scoring via Hestia's existing cloud inference pipeline
- [ ] Sentiment history tracking + **correlation analysis** with actual price moves (validate alpha)
- [ ] **Alpha decay measurement**: track how quickly sentiment signals lose predictive value
- [ ] Tests: 20+ tests for sentiment pipeline, regime classification, signal integration

### Sprint 29: On-Chain Data + ML Optimization (Est. 1–2 sessions)
<!-- GH Projects: priority=P2, size=XL, phase=AI, depends=S28 -->
**Goal:** On-chain signals (with point-in-time integrity), walk-forward parameter optimization

- [ ] Implement `ai/onchain.py`:
  - Glassnode/Dune Analytics integration
  - **Point-in-time ingestion**: timestamp every data point at retrieval, NOT at event time
  - **Critical: On-chain data is frequently revised retroactively** — backtests using "current" historical data show phantom alpha. All on-chain signals are trend confirmation only, never primary
  - Whale movement tracking, exchange flow monitoring
- [ ] Regime detection model (accumulation vs. distribution based on on-chain + price action)
- [ ] Implement `ai/optimizer.py`:
  - **Walk-forward analysis** (30-day train / 7-day validate windows, shift forward)
  - Bayesian optimization for strategy parameters (scikit-optimize)
  - **Overfit guardrails**: reject parameter sets with Sharpe > 3.0, profit factor > 3.0, or win rate > 70%
  - Monthly re-tuning cycle (automated parameter refresh)
- [ ] Out-of-sample validation pipeline
- [ ] Tests: 25+ tests for on-chain data (PiT integrity), optimizer (overfit detection)

### Sprint 30: Hardening & Go-Live (Est. 1 session)
<!-- GH Projects: priority=P0, size=L, phase=Launch, depends=S27 (S28-29 optional for go-live) -->
**Goal:** Production readiness, live trading with real funds

- [ ] Security audit of all exchange interactions
- [ ] Failsafe testing (kill API, simulate crashes, test recovery)
- [ ] 72-hour live paper trading soak test
- [ ] Gradual capital deployment plan (10% → 25% → 50% → 100%)
- [ ] Monitoring dashboard hardening
- [ ] Documentation: trading module docs, strategy guides, risk parameters
- [ ] ADR for trading module architecture decisions

---

## 4. Risk Management Framework

### 4.1 Position Sizing

| Rule | Value | Rationale |
|------|-------|-----------|
| Max single trade | 25% of fund | Prevents concentrated losses |
| Max total deployed | 80% of fund | Always maintain 20% cash reserve |
| Per-trade risk (months 1–3) | **Quarter-Kelly** | Conservative while parameter estimates are unreliable (Gemini finding) |
| Per-trade risk (months 4+) | **Half-Kelly** | Upgrade after 3 months of live data validates win rate + avg win/loss |
| Max correlated exposure | 50% of fund | Prevents BTC crash from wiping all positions |

### 4.2 Circuit Breakers

| Trigger | Action | Reset |
|---------|--------|-------|
| Daily loss > 5% | Pause all trading 24h | Automatic after 24h |
| Weekly loss > 10% | Pause all trading 72h | Manual review required |
| Drawdown from peak > 15% | Emergency stop, close all positions | Manual restart only |
| Single trade loss > 3% | Skip next signal, reduce position size 50% | After 3 winning trades |
| Exchange connectivity lost > 5min | Pause new orders, maintain stops | Auto-resume on reconnect |
| Volatility (ATR) > 2x normal | Reduce all positions by 50% | When ATR normalizes |
| **API latency > 2000ms** | **Pause new orders (exchange instability)** | **Auto-resume when latency < 500ms for 60s** |
| **Price feed divergence > 2%** | **Halt strategy, flag for review** | **Manual restart after verification** |

### 4.3 Operational Safety

- API keys: Trade-only (no withdrawal), IP allowlisted, rotated every 90 days
- All API keys stored in macOS Keychain via CredentialManager (existing Hestia pattern)
- Every trade decision logged with full reasoning trace
- No code path can place an order without passing through RiskManager
- Emergency kill switch accessible via API, iOS app, macOS app, and CLI
- Exchange-native stop-losses as backup (set on exchange, not just in bot)

---

## 5. Infrastructure & Deployment

### 5.1 Recommended Setup

**Development & Initial Paper Trading:** Mac Mini M1 (existing Hestia hardware)
- Adequate for all strategies at retail scale
- 24/7 operation feasible (M1 power efficiency)
- Risk: ISP outage, power outage, macOS updates

**Production Trading (after validation):** Mac Mini + Cloud VPS failover
- Primary execution on Mac Mini (zero latency cost, existing infra)
- Cloud VPS (DigitalOcean/Linode, ~$20/month) as monitoring + failover
- Heartbeat ping: Mac Mini → VPS every 30s; VPS takes over if 3 pings missed
- Exchange-native stop-losses always set as ultimate safety net

### 5.2 Monitoring Stack

- Hestia's existing logging system (get_logger() + LogComponent.TRADING)
- Trade audit database (SQLite, same pattern as other modules)
- Push notifications via existing Hestia push token system
- Discord webhook for real-time alerts (circuit breakers, large trades, errors)
- Performance dashboard in iOS/macOS apps (SSE real-time updates)

---

## 6. Success Metrics & Evaluation

### 6.1 Paper Trading Phase (Sprints 21–26)

| Metric | Target | Fail Threshold |
|--------|--------|---------------|
| Sharpe Ratio | > 1.0 | < 0.5 |
| Max Drawdown | < 15% | > 25% |
| Win Rate | > 45% | < 35% |
| Profit Factor | > 1.3 | < 1.0 |
| Uptime | > 99% | < 95% |

### 6.2 Live Trading Phase (Sprint 30+)

| Metric | 3-Month Target | 12-Month Target |
|--------|---------------|-----------------|
| Net Return | > 5% | > 25% |
| Sharpe Ratio | > 0.8 | > 1.2 |
| Max Drawdown | < 12% | < 15% |
| Average Trade Duration | Strategy-dependent | Strategy-dependent |
| Trades per Day | 5–20 | 10–50 |

### 6.3 Go/No-Go Criteria

**Proceed to live trading if:**
- Paper trading Sharpe > 1.0 over 30 days
- Max drawdown < 15% during paper phase
- All circuit breakers tested and functional
- 72-hour soak test passed without intervention
- Risk manager blocked at least 1 trade that would have lost money

**Abort/redesign if:**
- Paper trading shows negative returns after 30 days
- Circuit breakers trigger more than 3x per week
- Strategy shows regime-dependent fragility (only works in one market type)

---

## 7. Decisions (Resolved 2026-03-18)

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Exchange scope | Coinbase only (MVP), Kraken expansion later | Build CCXT abstraction layer for easy expansion; Kraken adds value at $5K+ capital |
| 2 | Funding rate arb | Deferred to Kraken expansion sprint | Not viable at $500–$2K scale (~$50–150/year); replace with expanded DCA allocation |
| 3 | Capital deployment | Moderate: 1 month paper → gradual live | Balance validation time vs. opportunity cost |
| 4 | Notifications | Circuit breakers + large moves + daily summary | Avoid alert fatigue; daily recap for awareness |
| 5 | Leverage | Start 1x, data-driven Kelly criterion after 3 months live | Let actual win rate and loss data determine optimal leverage mathematically |
| 6 | AI inference budget | Hestia's existing cloud budget → fully local after hardware upgrade | Plan architecture for local model inference (Ollama) as primary, cloud as fallback |

### Revised Strategy Allocation (Coinbase Spot Only — v2, post-Gemini review)

| Strategy | Allocation | Expected Return | Regime | Notes |
|----------|-----------|-----------------|--------|-------|
| Grid Trading (geometric) | 35% | 15–40% | Ranging | Post-Only maker orders, 2× ATR width |
| Mean Reversion (crypto RSI) | 20% | 10–20% | Ranging | RSI-7/9, 20/80, volume + trend filter |
| Signal-Enhanced DCA | 25% | 20–50% | Bull | RSI + MA confluence accumulation |
| Bollinger Breakout | 20% | 15–35% | Trending | Captures moves grid misses; regime diversifier |

### Technical Decisions (Can Be Deferred)

- WebSocket library: `websockets` vs `aiohttp` for exchange connections
- Backtest data granularity: 1-minute vs 5-minute vs 1-hour candles
- Database: Extend existing SQLite or dedicated trading DB file
- Multi-exchange order routing strategy
- Strategy parameter serialization format

---

## 8. Gemini Deep Research Review (2026-03-18)

External adversarial review conducted via Gemini Deep Research. Key findings integrated throughout this document. Summary of changes made:

### Critical Changes (plan modified)

| # | Finding | Action Taken |
|---|---------|-------------|
| 1 | Arithmetic grid spacing loses fee efficiency as price rises | Switched to **geometric** (percentage-based) spacing |
| 2 | RSI 30/70 with 14-period is equity default; produces delayed crypto signals | Changed to **RSI-7/9 with 20/80 thresholds** + volume confirmation + trend filter |
| 3 | Taker fees destroy grid profitability at small capital | **Post-Only maker orders** as default execution mode |
| 4 | 1099-DA reporting mandatory from Jan 2025; no cost-basis = catastrophic tax bill | **Tax lot tracker (HIFO/FIFO) built into Sprint 21 database schema** |
| 5 | SQLite bottleneck during concurrent WebSocket events | **WAL mode + memory-mapped I/O** specified in Sprint 21 |
| 6 | On-chain data retroactively revised; backtests show phantom alpha | **Point-in-time ingestion timestamps** required for all external data |

### High-Impact Changes (plan enhanced)

| # | Finding | Action Taken |
|---|---------|-------------|
| 7 | All strategies are long-biased; no trend capture | Added **Bollinger Band Breakout** as 4th strategy (20% allocation) |
| 8 | Half-Kelly too aggressive with unreliable parameter estimates | **Quarter-Kelly** default for first 3 months, upgrade to Half-Kelly after validation |
| 9 | Local/exchange state drift causes phantom fills | **60-second exchange reconciliation loop** in position tracker |
| 10 | Exchange API degrades during volatility (when losses are worst) | **API latency circuit breaker** (pause if > 2000ms response) |
| 11 | Data glitches can trigger false panic sells | **Redundant price feed** (CoinGecko cross-check, halt if > 2% divergence) |

### Validated (no change needed)

- SQLite correct for MVP (with WAL optimization)
- 15% drawdown circuit breaker appropriate for normal conditions
- LLM sentiment as macro filter, not primary signal
- Local quantized model viable for sentiment classification
- Triangular arbitrage confirmed insolvent at retail fee tier

### Noted for Future (low priority)

- TimescaleDB migration if data volume exceeds SQLite WAL capacity
- Wash sale rules may extend to crypto in future legislation — wash_monitor.py placeholder included
- Freqtrade's "hyperopt" (Optuna) as alternative to scikit-optimize for parameter tuning

---

## 9. Dependencies & Prerequisites

### Before Sprint 21

- [ ] Coinbase API key created (trade-only, no withdrawal, IP-restricted, **scoped to Consumer Default Spot**)
- [ ] `pip install ccxt coinbase-advanced-py vectorbt pandas-ta scikit-optimize` in Hestia venv
- [ ] Andrew reviews and approves this plan
- [ ] Decide on cost-basis method: HIFO (recommended for tax minimization) or FIFO (simpler)
- [ ] Set up Discord webhook for trading alerts (or designate alternative notification channel)

### External Dependencies

| Dependency | Purpose | Cost | Risk |
|-----------|---------|------|------|
| Coinbase API | Primary exchange | Free (trading fees only) | API changes, rate limits |
| CCXT | Exchange abstraction | Free (MIT) | Coinbase adapter lag |
| VectorBT | Backtesting | Free (MIT) | Learning curve |
| pandas-ta | Indicators | Free (MIT) | Low risk |
| CryptoPanic API | News sentiment | Free tier available | Rate limits |
| Glassnode | On-chain data | Free tier available | Data lag |

---

## 10. GitHub Projects Integration

### Labels
- `workstream:trading` — all trading module issues
- `phase:engine` — Sprints 21–24 (core trading infrastructure)
- `phase:exchange` — Sprint 25 (live exchange connectivity)
- `phase:ui` — Sprint 26 (monitoring dashboard, iOS/macOS)
- `phase:strategies` — Sprint 27 (complete strategy suite)
- `phase:ai` — Sprints 28–29 (sentiment, on-chain, ML optimization)
- `phase:launch` — Sprint 30 (hardening, go-live)

### Milestone
**Hestia v2.0 — Autonomous Trading** (Sprints 21–30)

### Dependency Graph (for GitHub Projects board)

```
S21 Foundation ──→ S22 Strategy Engine ──→ S23 Risk Management ──┐
                         │                                        │
                         └──→ S24 Backtesting (parallel w/ S23) ──┤
                                                                   │
                                                                   ↓
                                            S25 Coinbase Live ──→ S26 Dashboard
                                                    │
                                                    ↓
                                            S27 Bollinger+DCA+Portfolio ──→ S30 Go-Live
                                                    │                         ↑
                                                    ↓                         │
                                            S28 AI Sentiment ──→ S29 On-Chain+ML
                                            (optional for go-live)
```

### Sprint → GitHub Issue Mapping

| Sprint | Issue Title | Size | Priority | Phase | Depends On |
|--------|------------|------|----------|-------|------------|
| S21 | Trading: Foundation — module structure, database, paper adapter, tax lots | L | P0 | Engine | — |
| S22 | Trading: Strategy Engine — geometric grid, crypto-optimized RSI | XL | P0 | Engine | S21 |
| S23 | Trading: Risk Management — 8 circuit breakers, reconciliation, Quarter-Kelly | L | P0 | Engine | S22 |
| S24 | Trading: Backtesting — VectorBT, anti-overfit, walk-forward validation | XL | P0 | Engine | S22 |
| S25 | Trading: Coinbase Live — WebSocket, Post-Only orders, sequence checking | XL | P0 | Exchange | S23, S24 |
| S26 | Trading: Dashboard — SSE streaming, iOS/macOS Trading tab, alerts | XL | P1 | UI | S25 |
| S27 | Trading: Portfolio — Bollinger breakout, DCA, regime rotation, daily summary | XL | P1 | Strategies | S25 |
| S28 | Trading: AI Sentiment — LLM regime filter, CryptoPanic, alpha decay tracking | L | P2 | AI | S27 |
| S29 | Trading: On-Chain + ML — Glassnode, walk-forward optimizer, overfit guardrails | XL | P2 | AI | S28 |
| S30 | Trading: Go-Live — security audit, soak test, gradual capital deployment | L | P0 | Launch | S27 |

### Critical Path (minimum to live trading)

**S21 → S22 → S23 → S25 → S27 → S30** (6 sprints, ~8 sessions)

S24 (backtesting) can run in parallel with S23. S26 (dashboard) and S28-29 (AI) are enhancements that can follow after go-live if you want to start paper trading faster.

---

## Appendix A: Honest Return Expectations

| Scenario | Annual Return | 2-Year Value ($2,000 start) | Probability |
|----------|--------------|----------------------------|------------|
| Conservative (grid + DCA, no leverage) | 15–20% | $2,645–$2,880 | 60% |
| Moderate (multi-strategy, selective signals) | 25–35% | $3,125–$3,645 | 30% |
| Aggressive (leverage + sentiment + momentum) | 40–60% | $3,920–$5,120 | 10% |
| Loss scenario (bad regime, strategy failure) | -15 to -30% | $1,400–$1,700 | 20% |

Note: These are independent probability estimates. The loss scenario can occur in any approach. Capital preservation via risk management is the primary objective; returns are secondary.

---

## Appendix B: Key Sources

- Coinbase Advanced Trade API Documentation (2026)
- CCXT Library (109+ exchanges, Python/JS/PHP)
- Freqtrade open-source trading bot (50K+ developers)
- VectorBT backtesting framework (Numba JIT, tick-level)
- Hummingbot enterprise architecture (Cython-based)
- Jesse trading framework (300+ indicators)
- Academic: "Enhancing Cryptocurrency Trading Strategies: A Deep Reinforcement Learning Approach" (IEEE, 2025)
- Academic: "LLMs and NLP Models in Cryptocurrency Sentiment Analysis" (MDPI, 2024)
- Glassnode on-chain analytics, Dune Analytics
- Bitcoin 2025 Sharpe ratio analysis (XBTO Research)
