# Discovery Report: Sprint 28 — Alpaca + Stocks Expansion

**Date:** 2026-03-19
**Confidence:** High
**Decision:** Proceed with Sprint 28 as two sub-sprints (S28A crypto strategies + S28B Alpaca read-only), with revised equity strategy choices and PDT-first risk architecture.

## Hypothesis

Expanding Hestia's trading module from crypto-only (Coinbase) to multi-asset (Coinbase + Alpaca) is the right next step after Go-Live, using the existing adapter pattern, and the scoped work (AlpacaAdapter, market hours, PDT compliance, stock strategies, backtests) is feasible in 2 sub-sprints.

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Clean `AbstractExchangeAdapter` ABC with 11 abstract methods — AlpacaAdapter slots in directly. `AssetClass` enum already in models.py. `asset_class` + `settlement_date` columns already on Trade/Bot/TaxLot. Zero-commission stocks via Alpaca eliminate the fee-efficiency concerns that drove Post-Only defaults for crypto. Fractional shares ($1 minimum) work perfectly at $500 scale. | **Weaknesses:** Orchestrator currently holds a single `_exchange` adapter — needs multi-exchange routing. `product_info.py` is hardcoded to crypto pairs. Bot pair naming convention ("BTC-USD") differs from Alpaca stock symbols ("AAPL"). Bollinger breakout strategy was designed for crypto volatility — backtests show it underperforms buy-and-hold on equity indices. |
| **External** | **Opportunities:** Alpaca has built-in Calendar/Clock APIs for market hours (no third-party dependency). Paper trading environment mirrors live with same API. `alpaca-py` SDK is mature, Pydantic-based, actively maintained. Cash account bypasses PDT entirely (unlimited day trades, T+2 settlement constraint). Swing trading strategies are naturally PDT-safe and well-suited to small accounts. | **Threats:** PDT violation = account freeze (Alpaca rejects orders that would trigger 4th day trade with HTTP 403). T+1/T+2 settlement constrains capital recycling in cash accounts. Paper trading uses simplified fill model (100% fill assumption, IEX-only data for unfunded accounts). Alpaca paper latency significantly higher than live (100ms-seconds vs milliseconds). |

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | PDT enforcement in risk manager (account freeze prevention). Market hours scheduler (prevent orders outside trading hours). AlpacaAdapter with Keychain credentials. Multi-exchange routing in orchestrator. | Product info catalog for equity pairs. Settlement date tracking on trades. |
| **Low Priority** | Equity-optimized Bollinger params (14-period RSI, 30/70 thresholds for stocks). CoinGecko secondary feed for equities. | Alpaca WebSocket streaming (REST polling sufficient at low frequency). Options support (future). |

## Argue (Best Case)

**The expansion is well-timed and architecturally clean:**

1. **Adapter pattern is ready.** `AbstractExchangeAdapter` has exactly the interface Alpaca needs — `place_order`, `get_balances`, `get_ticker`, etc. The `alpaca-py` SDK maps 1:1 to these methods. Implementation effort is similar to `CoinbaseAdapter` (~400 lines).

2. **Zero-commission removes fee optimization complexity.** Unlike crypto where Post-Only maker orders save 0.20%/trade, Alpaca charges $0 commission on stocks. This means market orders are viable, strategies don't need fee-aware execution, and the entire Post-Only/maker infrastructure can be bypassed for equities.

3. **Fractional shares enable small-capital strategies.** At $500 starting capital, fractional shares let you trade any stock (even $500+ AAPL) with as little as $1 per position. This makes diversified multi-position strategies viable at micro scale.

4. **Built-in paper trading is API-identical.** Same SDK, same methods, just `paper=True` on the client constructor. No separate adapter needed — the existing PaperAdapter pattern works, or you can use Alpaca's native paper environment directly.

5. **DCA + swing strategies are naturally PDT-safe.** Signal-Enhanced DCA (buy-only, 24h interval gate) never generates same-day round-trips. Swing trading (multi-day holds) by definition avoids day trades. These two strategies alone provide meaningful equity exposure without PDT risk.

6. **Diversification reduces portfolio correlation.** Currently 100% crypto exposure. Adding equities provides genuine diversification — stock and crypto correlation varies (0.3-0.7 historically), reducing portfolio drawdown risk.

## Refute (Devil's Advocate)

**Several risks deserve serious attention:**

1. **PDT is a landmine, not a guardrail.** Alpaca pre-rejects orders (HTTP 403) that would trigger PDT, but your algo needs to track `daytrade_count` proactively. A bug in day-trade counting could brick the account for a business day. At $500 in a margin account, you get exactly 3 day trades per 5-day window — one off-by-one error and you're frozen.

2. **T+2 settlement in cash accounts creates a capital trap.** The PDT-free alternative (cash account) means $500 in capital can only cycle every 2 business days. In practice, you can make ~2-3 trades per week with full capital. This fundamentally limits strategy throughput and makes many algo approaches unviable.

3. **Bollinger breakout is wrong for equities.** Backtesting data from QuantifiedStrategies shows Bollinger breakout underperforms buy-and-hold on stock indices. The strategy was designed for crypto's higher volatility and 24/7 markets. Equities are more mean-reverting, with structural features (market hours, earnings, ex-dividend dates) that invalidate crypto-tuned parameters.

4. **Paper trading fills are unrealistically optimistic.** Alpaca's paper engine assumes 100% fill at limit price with no queue position modeling. This inflates backtest results, especially for strategies that depend on limit order execution. Live performance will be worse.

5. **Market hours introduce scheduling complexity.** Crypto runs 24/7. Stocks trade 9:30 AM - 4:00 PM ET with pre-market (4:00-9:30 AM) and after-hours (4:00-8:00 PM), plus holidays and half-days. The bot runner's poll loop needs time-awareness — polling during market close wastes resources, and stale candle data during off-hours can generate false signals.

6. **Orchestrator is single-exchange.** The current `BotOrchestrator.__init__` takes one `exchange: AbstractExchangeAdapter`. Multi-asset requires routing bots to different exchanges based on `asset_class`. This is a structural change, not a parameter change.

## Third-Party Evidence

**Alpaca SDK is production-grade.** GitHub shows active maintenance, 800+ stars on alpaca-py, regular releases. The SDK uses Pydantic models for type safety, which aligns well with Hestia's patterns. Known gotcha: async event loop conflicts in Jupyter (irrelevant for Hestia's async FastAPI context).

**PDT tracking is API-accessible.** The `account.daytrade_count` field provides the rolling 5-day count. Combined with Alpaca's server-side rejection, this creates a two-layer defense: client-side gate in risk manager + server-side enforcement.

**Swing trading outperforms day trading for small accounts.** Multiple studies and community consensus: with <$25K and PDT constraints, multi-day holds targeting 2-5% moves are the most practical approach. This maps directly to existing Mean Reversion and DCA strategies with adjusted hold periods.

**Cash vs Margin account tradeoff is real.** Margin account = PDT applies but instant buying power. Cash account = no PDT but T+2 wait. For an algo with $500, margin + PDT tracking is likely better than cash + T+2 delays. Decision point for Andrew.

## Gemini Web-Grounded Validation

**Model:** Gemini 2.5 Pro (thinking + google_web_search)

### Confirmed Findings

- **alpaca-py is mature and production-ready.** Actively maintained, Pydantic-based, full feature support for equities/crypto/options. Correct choice over deprecated `alpaca-trade-api-python`.
- **PDT enforcement is server-side.** Alpaca rejects orders that would trigger PDT (HTTP 403). The `daytrade_count` field on the account object enables client-side tracking.
- **Paper trading has significant limitations.** 100% fill assumption, IEX-only data (not SIP) for unfunded accounts, higher latency (100ms to seconds vs milliseconds live). Not reliable for latency-sensitive strategies.

### Contradicted Findings

- **T+2 settlement, not T+1 for equities.** Web search initially suggested T+1 but Gemini confirmed equities are T+2 (options are T+1). This is worse than assumed for cash account strategies.
- **PDT protection counts pending orders.** Initial assumption was only filled round-trips. Gemini confirmed Alpaca's PDT protection considers pending orders that *would* create a day trade if filled. This means the algo must check before submitting, not just before filling.

### New Evidence

- **Instant buying power exists for margin accounts.** Alpaca margin accounts get immediate access to sale proceeds without waiting for settlement. This significantly reduces the T+2 impact *if* using a margin account (but brings PDT back into play).
- **Cash account bypasses PDT entirely.** Unlimited day trades in a cash account, constrained only by settled funds. This is a viable alternative for strategies with low trade frequency.
- **Swing trading + options spreads are the recommended PDT-constrained strategies.** Multi-day holds and defined-risk spreads (future capability) are the community-validated approaches.

### Sources

- [Alpaca Paper Trading Docs](https://alpaca.markets/docs/trading/paper-trading/)
- [Alpaca PDT Protection](https://alpaca.markets/support/pattern-day-trading-protection)
- [Alpaca PDT Rule Explanation](https://alpaca.markets/support/what-is-the-pattern-day-trading-pdt-rule)
- [Alpaca Calendar API](https://alpaca.markets/sdks/python/api_reference/trading/calendar.html)
- [Alpaca Clock API](https://alpaca.markets/sdks/python/api_reference/trading/clock.html)
- [Alpaca Commission Fees](https://alpaca.markets/support/commission-clearing-fees)
- [Alpaca Fractional Trading](https://docs.alpaca.markets/docs/fractional-trading)
- [alpaca-py GitHub](https://github.com/alpacahq/alpaca-py)
- [Bollinger Bands Backtesting — QuantifiedStrategies](https://www.quantifiedstrategies.com/bollinger-bands-trading-strategy/)

## Philosophical Layer

### Ethical Check
Building a personal investment platform that automates disciplined strategies (DCA, swing trading) is productive and ethical. Automated discipline removes emotional trading errors. The PDT safeguards protect against account freezes. No concerns.

### First Principles

**Why Alpaca specifically?** It is the only US brokerage offering zero-commission, full API access with fractional shares, built-in paper trading, and no account minimum. The alternatives (Interactive Brokers, TD Ameritrade/Schwab) either charge commissions on API trades, have higher minimum requirements, or have more restrictive API access. Alpaca is the correct choice for this use case.

**Why multi-asset now?** Sprint 27 paper soak is running. The crypto strategies are validated. Adding equities while the architecture is fresh and well-understood is more efficient than revisiting it later. The adapter pattern was designed for exactly this expansion.

### Moonshot: Unified Portfolio Intelligence

**What if Hestia could optimize across both asset classes simultaneously?** Not just running separate crypto and equity strategies, but a portfolio-level optimizer that:
- Shifts capital between crypto and equities based on regime detection (risk-on vs risk-off)
- Performs tax-loss harvesting across asset classes (sell losing crypto to offset equity gains)
- Correlates crypto sentiment with equity sector rotation (BTC as risk barometer)

**Technical viability:** Feasible with existing infrastructure. Portfolio-level view already planned. Correlation monitoring already in the design. Tax lot tracker already supports multi-asset.
**Effort:** 15-20h beyond Sprint 28-29 scope.
**Verdict:** SHELVE for now. Requires live data from both asset classes first. Revisit after 30 days of dual-asset operation. The foundation built in S28 enables this naturally.

## Key Principles Score

| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 5 | PDT enforcement + Keychain credentials + kill switch. No withdrawal API access. |
| Empathy | 4 | Genuinely serves Andrew's investment goals. Small-capital constraints thoughtfully handled. |
| Simplicity | 4 | Adapter pattern makes this clean. Market hours add complexity but it's essential complexity. |
| Joy | 5 | Expanding from crypto to stocks is a real milestone — personal investment platform. |

## Recommendation

**Proceed with Sprint 28 as scoped in SPRINT.md (S28A + S28B), with these specific modifications:**

### 1. Account Type Decision Required (Andrew)
**Margin account** (recommended): PDT applies (3 day trades / 5 days), but instant buying power. Best for algo trading.
**Cash account**: No PDT, but T+2 settlement locks capital. Best for pure DCA/swing.

### 2. Strategy Adjustments for Equities
- **Do NOT use Bollinger Breakout on equities.** Backtests show it underperforms buy-and-hold on stock indices. Keep it crypto-only.
- **Signal DCA is ideal for equities.** Buy-only, interval-gated, naturally PDT-safe. Use equity RSI defaults (14-period, 30/70 thresholds).
- **Mean Reversion needs equity tuning.** Use standard RSI-14 with 30/70 thresholds for stocks (not crypto's 7-9/20-80). Stocks are more mean-reverting than crypto.
- **New: Swing strategy consideration.** Multi-day hold targeting 2-5% moves. Can be implemented as a Mean Reversion variant with `min_hold_days > 1`.

### 3. PDT Enforcement (Critical Path)
- Add `PDTTracker` class to risk manager that checks `account.daytrade_count` before every equity order
- Gate: if `daytrade_count >= 3` and account is margin, block all equity day trades
- Log PDT state on every trade cycle for audit trail
- This is Layer 0 of risk for equities — before position limits, before Kelly sizing

### 4. Multi-Exchange Orchestrator
- `BotOrchestrator` needs an exchange registry: `Dict[str, AbstractExchangeAdapter]` keyed by exchange name
- Bot's `asset_class` determines which adapter to use
- Risk manager instances may need to be per-exchange (different circuit breaker thresholds for stocks vs crypto)

### 5. Market Hours Scheduler
- Use Alpaca's Calendar + Clock APIs (not hardcoded schedules)
- Bot runner checks `clock.is_open` before polling candles
- Pre-market/after-hours trading: disabled initially (regular hours only)
- Holiday handling: Calendar API provides full schedule through 2029

### 6. S28A vs S28B Sequencing (confirmed correct)
- **S28A:** Wire Bollinger + DCA for crypto, backtest 90d, CSV export. Crypto-only, no Alpaca dependency.
- **S28B:** AlpacaAdapter (read-only first), market hours scheduler, simulated stock signals. No live equity orders yet.
- **S29A:** AlpacaAdapter (full orders), PDT enforcement, Alpaca paper soak.

**Confidence: High.** The adapter pattern is proven, Alpaca SDK is mature, and the two-sub-sprint approach de-risks the expansion. The main risk is PDT implementation correctness, which is mitigated by Alpaca's server-side rejection as a safety net.

## Final Critiques

### Skeptic: "Why not just buy index funds?"
**Response:** Valid for pure returns. But the value proposition is (a) learning algo trading infrastructure, (b) building toward portfolio-level intelligence, and (c) tax-loss harvesting across asset classes. The DCA strategy effectively IS systematic index buying, just with signal-enhanced timing. At $500, the learning value exceeds the return value.

### Pragmatist: "Is the effort worth it for $500?"
**Response:** Yes, because $500 is the starting capital, not the ceiling. Andrew has $1K-$25K+ available based on performance (per trading-capital-intent.md). The infrastructure built now scales to meaningful capital. Additionally, S28B is read-only — minimal risk, maximum learning.

### Long-Term: "What happens in 6 months?"
**Response:** In 6 months, Hestia has a unified view across crypto + equities with validated strategies on both. If performance justifies it, capital scales to $5K+ and the PDT constraint may resolve (approaching $25K). The moonshot (cross-asset portfolio optimization) becomes feasible. If performance disappoints, the architecture still serves as a disciplined DCA tool across both asset classes — which beats emotional manual trading.

## Open Questions

1. **Account type:** Margin (PDT + instant buying power) or Cash (no PDT + T+2)? Recommend margin.
2. **Starting equity pairs:** AAPL, SPY, QQQ? Or sector-specific? Recommend starting with SPY (broad market, high liquidity, low spread).
3. **Equity capital allocation:** $500 stated in SPRINT.md. Confirm this is separate from the $250 crypto allocation.
4. **Pre-market/after-hours:** Enable extended hours trading or regular hours only? Recommend regular hours only initially.
5. **Alpaca API key creation:** Need to set up Alpaca account + generate API keys before S28B can begin. Paper keys are free and instant.
