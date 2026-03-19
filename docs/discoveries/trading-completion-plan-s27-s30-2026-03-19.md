# Discovery Report: Trading Module Completion Plan (Sprints 27-30)
**Date:** 2026-03-19
**Confidence:** High
**Decision:** Complete S27 post-soak validation + $25 ramp as planned. Resequence S28-30 with Optuna replacing scikit-optimize, CryptoQuant/Dune replacing Glassnode free tier, and CryptoPanic sentiment treated as supplementary signal only.

## Hypothesis
Sprints 27-30 as originally planned (Go-Live, Portfolio Expansion, AI Sentiment, On-Chain + ML) remain the right sequence and scope for taking Hestia's trading module from paper soak to profitable autonomous operation at $250-$10K+ capital on Coinbase, with multi-exchange expansion via CCXT.

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** 8-layer risk pipeline battle-tested, atomic transactions, kill switch with exchange reconciliation, 33 go-live tests passing, paper soak running clean, `StrategyType` enum already has all 4 strategies, `AbstractExchangeAdapter` ABC designed for CCXT expansion, `BaseStrategy` interface clean and extensible | **Weaknesses:** Only 2/4 strategies wired in `_create_strategy()` factory, no partial fill handling yet, dead circuit breakers (VOLATILITY/CONNECTIVITY) disabled not removed, Python 3.9 on Mac Mini blocks vectorbt, single exchange only, WebSocket deferred (REST polling OK for 1h candles but limits expansion to faster strategies) |
| **External** | **Opportunities:** Optuna is actively maintained and superior to scikit-optimize for Bayesian optimization, CCXT Kraken integration is mature, CryptoQuant/Dune offer free on-chain data, Bollinger breakout diversifies regime exposure (profits when grid fails), post-halving BTC market is favorable for trend-capture strategies | **Threats:** scikit-optimize is effectively dead (archived Feb 2024), Glassnode free tier has NO API access (display-only), CryptoPanic sentiment has no validated predictive power, Coinbase fees (0.40% maker / 0.60% taker) require >1.2% round-trip profit to break even at <$10K volume, walk-forward meta-overfitting risk |

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | S27 post-soak validation + $25 live ramp, Bollinger breakout strategy (regime diversification), Optuna adoption (replace dead scikit-optimize), partial fill handling | Dead circuit breaker cleanup (minor tech debt), dependency lockfile audit |
| **Low Priority** | CCXT Kraken (diversification at $2.5K+ gate), CryptoQuant on-chain signals (regime detection), walk-forward validation enhancement | Glassnode integration (free tier useless, paid overkill), CryptoPanic as primary signal (unvalidated accuracy), wash sale monitoring (not required for crypto) |

## Argue (Best Case)

**The plan is fundamentally sound and the architecture supports it:**

1. **S27 is 95% done.** Paper soak is live, safety hardening complete, capital gates documented. The remaining work (post-soak validation, $25 ramp, minor hardening) is mechanical, not architectural.

2. **S28 strategies have natural mathematical synergy.** Grid profits in range-bound markets, mean reversion profits from overextensions, Bollinger breakout profits from trends, signal DCA accumulates during corrections. The four strategies together cover all market regimes.

3. **CCXT integration is straightforward.** The `AbstractExchangeAdapter` ABC was designed for this from Sprint 21. Kraken via CCXT is a well-trodden path. The effort is adapter implementation + config, not architecture rework.

4. **Optuna is a strict upgrade.** More features (pruning, distributed optimization, visualization), actively maintained, larger community. The migration is localized to the optimizer module planned for S30.

5. **Capital gates provide natural checkpoints.** $250 -> $1K (2-week clean run) -> $2.5K (secondary feed + shadow mode) creates a progressive confidence ladder. Each gate is a natural review point where strategy performance is validated on real capital.

6. **At 25-50% annual returns on eventual $10K deployment, the module generates $2.5K-$5K/year** — meaningful passive income that compounds.

## Refute (Devil's Advocate)

**Several assumptions deserve scrutiny:**

1. **Fee drag is brutal at small capital.** At $250, a single BTC trade at maker rate costs $1.00 in fees. With Quarter-Kelly sizing ($62.50 max position), fees eat 1.6% per round trip. Strategy must reliably capture >1.6% moves to be profitable. BTC's 1h ATR often hovers around 0.5-1.0% — many signals will be fee-negative.

2. **Four strategies on $250 is over-diversification.** The original allocation plan ($87.50 grid / $62.50 DCA / $50 mean reversion / $50 Bollinger) means each strategy operates with $50-87 capital. A single BTC trade at $87K uses most of a strategy's allocation. This is effectively single-position-per-strategy, which defeats the purpose of grid trading (needs multiple open levels).

3. **Grid trading is impractical at $87.50.** With 10 grid levels and $87.50 capital, each level holds $8.75. At $87K BTC, that's 0.0001 BTC per level — below Coinbase's minimum order size for many pairs. Grid strategy may be non-functional at this capital level.

4. **AI Sentiment (S29) has no validated edge.** CryptoPanic labels achieved "70-85% accuracy on clear positive or negative sentiment" according to providers, but no independent study validates predictive power on price. LLM regime filters add cloud API cost ($50-200/month) that may exceed trading profits at $250-$2.5K capital.

5. **On-Chain data (S30) is premature.** Glassnode free tier is useless (no API). CryptoQuant/Dune free tiers provide data but require significant engineering to extract actionable signals. The alpha from on-chain is measured in hours (6-12h lag), which is fine for daily strategies but adds complexity for uncertain benefit.

6. **Walk-forward optimization (S30) risks meta-overfitting.** Optimizing window sizes, fitness functions, and parameter ranges until results look good defeats the purpose. With only weeks of live data by S30, the sample size is too small for meaningful optimization.

## Third-Party Evidence

### Contradictions to Original Plan

1. **scikit-optimize is dead.** The plan specified scikit-optimize for Bayesian optimization. The library was archived in February 2024 and is no longer maintained. Optuna (v4.7.0, January 2026) is the clear replacement.

2. **Glassnode free tier has no API access.** The plan assumed "free data from Glassnode." Reality: free tier is web dashboard only, no API. Professional plan ($40+/month) required for API access. Alternatives: CryptoQuant (free API for exchange flows), Dune Analytics (free SQL queries), LookIntoBitcoin (free macro indicators).

3. **Grid trading minimum capital is higher than allocated.** At $87.50 per the allocation plan, grid trading is likely below minimum order thresholds for BTC-USD on Coinbase.

### Alternative Approaches Found

- **Concentrate capital instead of diversifying.** Run 1-2 strategies with full capital ($125-250 each) rather than 4 strategies with $50-87 each. Add strategies as capital grows through gates.
- **Use Kraken Pro for lower fees.** Kraken's fee schedule may be more favorable for small capital algorithmic trading (0.16% maker / 0.26% taker at lowest tier).
- **Arkham Intelligence** for free entity/whale tracking instead of paid Glassnode.

## Gemini Web-Grounded Validation
**Model:** Gemini 2.5 Pro (thinking + google_web_search)

### Confirmed Findings
- scikit-optimize archived February 2024, Optuna is the industry standard replacement
- CCXT Kraken integration is mature and stable for automated trading
- Coinbase fee structure (0.40%/0.60%) creates high breakeven threshold at <$10K volume
- Walk-forward optimization is the correct approach but meta-overfitting is a documented risk

### Contradicted Findings
- **Glassnode free tier has NO API access** — original plan assumed free API data; this is incorrect. Free tier is display-only web dashboard.
- **CryptoPanic sentiment has no validated predictive power** — Gemini found no studies or production reports confirming price prediction accuracy of CryptoPanic labels.

### New Evidence
- **Kraken rate limiting uses a counter-based recharge system** — different cost per action type, canceling recently-placed orders costs more points (anti-spam). Must implement in CCXT adapter.
- **CryptoQuant** offers free API tier with exchange inflow/outflow data — viable Glassnode alternative for the specific signals we need.
- **Dune Analytics** provides free SQL-based blockchain queries — flexible but requires more engineering effort than a REST API.
- **Bollinger Band performance is regime-dependent** — no recent (2024-2026) BTC-specific backtests found. Must generate our own with recent data.
- **Post-only orders are critical** — at $250 capital, the 0.20% fee difference between maker and taker is $0.50 per trade, which compounds significantly.

### Sources
- [Glassnode Pricing](https://glassnode.com/pricing)
- [Kraken API Rate Limits](https://docs.kraken.com/rest/#section/Rate-Limits)
- [CryptoPanic API](https://cryptopanic.com/developers/api/)
- [Coinbase Trading Fees](https://www.coinbase.com/fees)
- [CCXT Library](https://github.com/ccxt/ccxt)
- [Optuna](https://optuna.org/)
- [Bollinger Bands Regime Study (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5775962)
- [scikit-optimize status](https://github.com/holgern/scikit-optimize/issues/6)

## Philosophical Layer

### Ethical Check
Trading with personal capital on a transparent exchange with no leverage is ethically clean. No clients' money at risk. The system is designed with institutional-grade safety (kill switch, circuit breakers, atomic transactions) despite personal use — this is responsible engineering.

### First Principles Challenge
**Why four strategies at $250?** Strip away the plan and start from fundamentals: $250 on Coinbase with 0.40% maker fees means each strategy needs to capture moves >0.80% per trade to be profitable after one-way fees. With Quarter-Kelly sizing and 4-strategy allocation, each strategy has ~$62.50. At BTC's current price, this is approximately 0.00072 BTC per position — likely below minimum order thresholds for grid trading.

**First-principles answer:** Start with 1-2 strategies at full capital concentration. Add strategies as capital grows through gates. Grid trading becomes viable at ~$1K+ (10 levels x $100 = meaningful positions). Bollinger breakout and mean reversion work at any capital level since they take single positions.

### Moonshot Challenge (Full Feasibility)
**What's the moonshot?** Self-optimizing multi-exchange arbitrage across Coinbase, Kraken, and Binance with LLM-driven regime detection and real-time on-chain whale tracking.

- **Technical viability:** Partially feasible. CCXT provides multi-exchange abstraction. LLM regime detection is possible via Hestia's existing cloud inference. Real-time on-chain requires paid APIs ($100+/month). Cross-exchange arbitrage requires funded accounts on multiple exchanges with fast settlement.
- **Effort estimate:** 80-120 hours beyond current plan scope.
- **Risk:** Over-engineering. Arbitrage opportunities at retail scale are typically <0.1% and disappearing. Latency on Mac Mini M1 (residential internet) vs. co-located HFT means we lose arbitrage races.
- **MVP scope:** Not worth building separately. Better to evolve through S28-30 naturally.
- **Verdict:** SHELVE. The capital-efficient path is single-exchange multi-strategy with gradual expansion. Arbitrage needs $50K+ and co-location to be viable.

### Key Principles Score

| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 5 | 8-layer risk, kill switch, atomic transactions, Keychain credentials, no-withdrawal API keys |
| Empathy | 4 | Serves Andrew's goal of passive income; needs better alerting/monitoring UX for confidence |
| Simplicity | 3 | 4-strategy architecture is elegant but over-diversified at $250. Should start simpler. |
| Joy | 5 | Autonomous money-making bot on personal hardware — this is peak engineer joy |

## Recommendation — REVISED (Personal Investment Platform Pivot)

**Date of revision:** 2026-03-19
**Strategic pivot:** Andrew wants a **personal investment platform**, not just a crypto trading bot. Alpaca for stocks (zero commission, algo-friendly API, built-in paper trading). Coinbase stays primary for crypto. Kraken deprioritized to optional backlog.

**Confidence: High.** The existing architecture (AbstractExchangeAdapter, BaseStrategy, BotRunner, risk pipeline) is ~60% reusable for equities. The pivot front-loads higher-value work (stocks) over speculative crypto features.

### Sprint 27: Go-Live — Crypto (remaining ~3h)
1. Complete 72h paper soak validation (expected ~2026-03-22)
2. Review trade history + tax lots, confirm no kill switch triggers
3. Add product metadata fetch + order size validation (prevents 400 errors on live)
4. Flip to live with $25 (10% ramp) on mean reversion only
5. Minor hardening: partial fill handling, dependency lockfile, dead breaker cleanup
6. After 1 week clean at $25: ramp to $250 on mean reversion

### Sprint 28: Alpaca + Stock Trading + Strategy Wiring (~22h) — NEW SCOPE
**Key change: Alpaca for stocks replaces Kraken. Higher value, broader investment platform.**

Phase 28A — Alpaca Foundation (~12h):
- `AlpacaAdapter` extending `AbstractExchangeAdapter` (REST + WebSocket via `alpaca-py` SDK)
- Paper trading mode (same API, different base URL — mirrors our existing paper/live toggle)
- Market hours scheduler: pre-market (4am-9:30am), regular (9:30am-4pm), after-hours (4pm-8pm), closed
- PDT rule enforcement in `RiskManager` (3 day trades per 5 rolling business days if account <$25K)
- T+1 settlement awareness in `PositionTracker` (unsettled cash tracking)
- Alpaca API keys in Keychain, `trading.yaml` multi-exchange section with `alpaca:` config block
- Stock-specific data model: `AssetClass` enum (CRYPTO, US_EQUITY), shared `Trade` model with asset_class field
- 40+ tests targeting Alpaca adapter, market hours, PDT rule, settlement

Phase 28B — Strategy Wiring + Stock Strategies (~10h):
- Wire Bollinger breakout into `_create_strategy()` factory (code exists in `strategies/`, just not connected)
- Wire signal DCA strategy (same gap — enum exists, strategy exists, factory doesn't route to it)
- Crypto capital allocation: mean reversion 50% + Bollinger 30% + signal DCA 20% (grid deferred to $1K+)
- Stock strategies: momentum (SMA crossover) + swing trading (RSI + volume) — adapt existing indicator layer
- Backtest all strategies on 90d data (crypto via Coinbase, stocks via Alpaca historical)
- Unified portfolio view API: `GET /v1/trading/portfolio` returns positions across both Coinbase + Alpaca

### Sprint 29: Multi-Asset Intelligence (~16h) — REVISED
**Key change: Regime detection spans both markets. Sentiment is supplementary only.**

Phase 29A — Regime Detection + Tax (~10h):
- LLM regime filter via cloud inference: classify market regime per asset class (trending/ranging/volatile)
- Regime filter gates strategy activation (e.g., disable Bollinger in ranging equity market)
- Wash sale rule enforcement for equities (31-day window, substantially identical securities)
- Tax-loss harvesting detector: flag positions with unrealized losses >$X for manual review
- Unified tax report: crypto (HIFO, no wash sale) + equity (FIFO, wash sale enforced) — 1099-B + 1099-DA
- CoinGecko secondary price feed for crypto (capital gate 2 prerequisite)

Phase 29B — Supplementary Signals (~6h):
- CryptoPanic API as confidence modifier on crypto signals only (not primary, not for stocks)
- Alpha decay measurement: track signal-to-fill latency, correlate with P&L across both asset classes
- A/B framework: sentiment-modified vs. raw signals in shadow mode
- Capital gate: sentiment module only activates at $1K+ crypto capital

### Sprint 30: Optimization + On-Chain (~18h) — REVISED
**Key change: Optuna replaces dead scikit-optimize. CryptoQuant/Dune replaces Glassnode. Optimization spans both asset classes.**

Phase 30A — Optimization Engine (~10h):
- Optuna Bayesian optimizer for strategy parameter tuning (both crypto + stock strategies)
- Walk-forward validation: 30d train / 7d validate rolling windows
- ML guardrails: parameter bounds, minimum 90d data before optimization, out-of-sample degradation alert
- Anti-meta-overfitting: fix window sizes (30d/7d), single fitness function (Sharpe), no WFO process tuning
- Per-asset-class optimization (stock and crypto parameters tuned independently)

Phase 30B — On-Chain Signals (~8h):
- CryptoQuant free API: exchange inflow/outflow for BTC (crypto-only enhancement)
- Dune Analytics SQL queries: whale accumulation indicators
- Point-in-time data ingestion (when data was available, not when event occurred)
- On-chain signal as regime overlay for crypto strategies (accumulation/distribution phase)

### Capital Deployment Timeline
| Gate | Capital | Asset Class | Prerequisites | Estimated Date |
|------|---------|-------------|--------------|----------------|
| Crypto soak complete | $25 crypto | Crypto | 72h clean paper soak | ~2026-03-22 |
| Crypto ramp 1 | $250 crypto | Crypto | 1 week clean at $25 | ~2026-03-29 |
| Stock paper soak | $0 (paper) | Equity | Alpaca adapter complete (S28A) | ~2026-04-05 |
| Stock live | $500 equity | Equity | 1 week clean paper + PDT-safe strategies | ~2026-04-12 |
| Crypto ramp 2 | $1K crypto | Crypto | 2-week clean + staleness checks | ~2026-04-12 |
| Multi-asset ramp | $2.5K total | Both | CoinGecko feed + unified portfolio view | ~2026-04-26 |
| Scale | $5K+ total | Both | Optimization + on-chain (S30) | ~2026-05-10 |

### Total Effort: ~59h across S27-30
At 12h/week hands-on + Claude Code acceleration: ~5 weeks (S27 done Mar 22, S28 mid-April, S29 late April, S30 mid-May).

### Architecture Impact

**New/Modified Files:**
- `hestia/trading/exchange/alpaca.py` — AlpacaAdapter (new)
- `hestia/trading/exchange/alpaca_ws.py` — Alpaca WebSocket feed (new)
- `hestia/trading/market_hours.py` — Market hours scheduler (new)
- `hestia/trading/models.py` — AssetClass enum, asset_class fields on Trade/Bot/TaxLot
- `hestia/trading/risk.py` — PDT rule, wash sale detection
- `hestia/trading/tax.py` — Multi-regime tax tracking (new, extracted from database.py)
- `hestia/trading/bot_runner.py` — Market hours awareness (skip ticks when market closed)
- `hestia/trading/strategies/momentum.py` — SMA crossover for equities (new)
- `hestia/trading/strategies/swing.py` — RSI + volume swing strategy (new)
- `hestia/config/trading.yaml` — `alpaca:` section, `asset_classes:` config
- `tests/test_trading_alpaca.py` — Alpaca adapter + market hours + PDT tests (new)

**Dependencies:**
- `alpaca-py` (official SDK, replaces need for raw REST)
- Verify Python 3.9 compatibility on Mac Mini

**Database migrations:**
- `asset_class TEXT DEFAULT 'crypto'` on bots, trades, tax_lots tables
- `wash_sale_disallowed REAL` on tax_lots (equity only)
- `settlement_date TEXT` on trades (equity only)
- `day_trade_count INTEGER` tracking table (PDT enforcement)

## Final Critiques (Updated for Platform Pivot)

### Skeptic: "Why won't this work?"
**Challenge:** Adding stocks doubles the surface area. Market hours, settlement, PDT, wash sales — each is a regulatory landmine. One bug in wash sale tracking could create tax liability.

**Response:** Valid. This is why S29 explicitly includes wash sale enforcement and unified tax reporting. The risk is manageable because: (1) Alpaca handles order routing and compliance on their end, (2) we start with paper trading on stocks (zero financial risk while validating), (3) PDT rule is enforced in our risk manager as a hard gate. The tax module is the highest-risk component — it deserves extra test coverage and possibly a CPA review before tax season.

### Pragmatist: "Is the effort worth it?"
**Challenge:** 59 hours for a platform managing $250 crypto + $500 stocks. ROI is still negative in year one.

**Response:** The investment platform framing changes the calculus. This isn't a crypto experiment — it's infrastructure for managing Andrew's entire investment portfolio autonomously. At $10K+ across stocks and crypto (achievable by Q3 2026), even conservative 15-20% returns on equities + 25-50% on crypto = $2K-$5K/year. Plus tax-loss harvesting alone can save $500-1K/year at that capital level. The platform scales to $50K+ without architecture changes.

### Long-Term Thinker: "What happens in 6 months?"
**Challenge:** Two asset classes, two exchanges, four+ strategies, tax tracking across regimes — maintenance burden grows.

**Response:** The manager pattern + shared abstractions keep complexity bounded. BotRunner doesn't care if it's trading stocks or crypto — it polls candles, runs strategy, executes signals. The asset-class-specific logic is isolated in adapters and tax modules. The M5 Ultra upgrade (summer 2026) provides headroom for heavier optimization workloads. Capital gates ensure we only add complexity when the portfolio justifies it.

## Open Questions (Updated)

1. **Coinbase BTC-USD minimum order: ~$8.70** (0.0001 BTC at $87K) — RESOLVED. Grid deferred to $1K+.
2. **Alpaca Python 3.9 compatibility** — `alpaca-py` requires Python 3.8+. Should work on Mac Mini. Verify before S28.
3. **Optuna Python 3.9 compatibility** — Must verify before S30.
4. **Paper soak results** — 72h window ends ~2026-03-22. Strategy decisions depend on clean results.
5. **Kraken account** — DEPRIORITIZED. Andrew is signing up but deployment deferred to optional backlog ($5K+ gate).
6. **CPA review of tax module** — Recommended before first tax season with live trades. Wash sale + HIFO interaction needs professional validation.
7. **Alpaca account setup** — Andrew needs to create and fund an Alpaca account before S28A. Paper trading available immediately after signup (no funding required).
8. **Stock strategy selection** — Momentum (SMA crossover) and swing (RSI) are conservative starting points. May want to research sector rotation or dividend capture strategies for long-term holdings.
