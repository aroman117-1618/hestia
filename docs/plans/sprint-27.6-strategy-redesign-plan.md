# Sprint 27.6: Strategy Redesign — Fix Broken Foundation

**Date:** 2026-03-21
**Status:** PLAN (pending second opinion)
**Blocking:** All downstream sprints (S28-S30). Cannot build regime detection, portfolio optimization, or Alpaca integration on strategies that lose money.

---

## Problem Statement

### What We Found

Sprint 27.5 WS1 ran comprehensive backtests — 696 parameter combinations across 4 strategies, tested against 5 crypto assets (BTC, ETH, SOL, DOGE, AVAX) over 1 year of hourly data (8,755 candles per asset). The results are unambiguous:

**Three of four strategies are non-viable. The fourth has a code bug that prevents it from trading at all.**

| Strategy | Combos Tested | Assets Tested | Best Avg Return | Walk-Forward | Verdict |
|----------|:---:|:---:|:---:|:---:|---|
| Mean Reversion | 400 × 5 | BTC/ETH/SOL/DOGE/AVAX | +1.6% avg (+56% ETH) | FAIL | MARGINAL — works on some assets, loses on others |
| Signal DCA | 216 × 5 | BTC/ETH/SOL/DOGE/AVAX | -0.2% | FAIL | **CODE BUG** — 0 trades across ALL 1,080 test runs |
| Bollinger Breakout | 64 × 5 | BTC/ETH/SOL/DOGE/AVAX | -30.2% avg | FAIL | BROKEN — loses money on every asset except ETH (+2%) |
| Grid Trading | 16 × 5 | BTC/ETH/SOL/DOGE/AVAX | -90.7% avg | FAIL | CATASTROPHIC — destroys capital on all assets |

### Market Context (Past 12 Months)

The crypto market was broadly bearish during the test period, which is ESSENTIAL context:

| Asset | Buy & Hold Return | Character |
|-------|:---:|---|
| ETH-USD | +9.0% | Only positive — moderate uptrend |
| BTC-USD | -16.4% | Bearish with rallies |
| SOL-USD | -29.6% | Sharp decline |
| DOGE-USD | -43.9% | Deep bear |
| AVAX-USD | -49.5% | Deep bear |

A viable trading system MUST perform in bear markets — that's when protection matters most. The current strategies have no bear-market capability: no shorting, no cash rotation, no trend filtering.

### Root Cause Analysis

**1. Signal DCA: Code Bug (0 trades)**
The `analyze()` method in `signal_dca.py` generates 0 trades across ALL parameter combinations on ALL assets. This is not a tuning problem — the entry logic has a structural bug. Either the conditions are never simultaneously met (RSI below threshold AND price below MA AND interval elapsed), or there's a short-circuit that prevents signal generation.

**2. Mean Reversion: No Exit Logic**
Mean Reversion has a 48-59% win rate but the average loss exceeds the average win ($1.10 loss vs $0.64 win on BTC). The strategy has a 3% hard stop-loss but NO profit target. Winning trades are held until they reverse back through the entry zone — giving back profits. On ETH specifically (the one bullish asset), the strategy returned +56% because the uptrend bailed out long positions. On bearish assets, positions hit the stop-loss consistently.

**3. Bollinger Breakout: Buys Fakeouts**
The strategy buys when price breaks above the upper Bollinger Band with volume confirmation. In a bear market, these "breakouts" are mostly fakeouts — price spikes above the band, triggers a buy, then reverses. 32% win rate across assets confirms this. The strategy also has no exit logic — it buys breakouts but doesn't define when to sell.

**4. Grid Trading: Structural Flaw**
Grid trading profits from oscillation in a tight range. The past year had large trending moves (BTC from ~$84K to ~$71K, SOL from ~$178 to ~$125). The grid buys every dip during a downtrend, accumulating losing positions at progressively lower prices while the 0.4% fee per trade bleeds capital. At $250 or even $5K, the individual trade sizes are too small for the fee to be recoverable. The strategy loses 90%+ across all assets and capital levels tested.

**5. Missing: Trend-Following Capability**
ALL four strategies are mean-reversion or accumulation biased (buy dips, sell rallies). NONE can profit from sustained trends. In a year where 4/5 assets trended down 16-50%, the portfolio had zero downside protection. A simple trend-following strategy (go long above 200-SMA, go to cash below) would have protected capital on all declining assets.

### Why This Matters for the Broader Vision

Andrew's goal is an autonomous portfolio manager that trades crypto today and stocks/ETFs tomorrow via Alpaca. The strategy suite must work across:

- **Bull markets** (accumulation, trend-following)
- **Bear markets** (shorting where possible, cash rotation, defensive positioning)
- **Ranging markets** (mean reversion, grid where viable)
- **Multiple asset classes** (crypto volatility ≠ equity volatility — parameters must adapt)
- **Multiple timeframes** (day trading, swing trading, position trading)

The current suite covers only one regime (ranging) and has zero bear-market protection. Building regime detection (S28), Alpaca (S29), and portfolio optimization (S30) on this foundation would amplify losses, not generate alpha.

---

## Goal

**Fix the strategy foundation so at least 2 strategies show positive expected value across multiple assets and market regimes, validated by walk-forward testing.**

Success criteria:
1. At least 2 strategies with positive average return across 5 crypto assets
2. At least 1 strategy with Sharpe > 0.5 on walk-forward validation
3. Signal DCA bug fixed and producing trades
4. A trend-following strategy added to complement mean-reversion
5. Grid either fixed or formally shelved with documented rationale
6. All results reproducible via backtest scripts

---

## Proposed Changes

### WS1: Fix Signal DCA Bug (~2h)

**Problem:** 0 trades across 1,080 test runs (216 params × 5 assets).

**Investigation needed:**
- Read `hestia/trading/strategies/signal_dca.py` `analyze()` method
- Trace why conditions are never simultaneously true
- Likely cause: the interval gate (`buy_interval_hours`) tracks state between calls, but the backtest engine creates a fresh strategy instance per run — so state resets every candle. OR the MA calculation requires more history than the backtest provides at early candles.

**Fix approach:** Debug the condition chain, add logging, fix the root cause. Re-run backtests on all 5 assets to confirm trades are generated.

### WS2: Add Profit Targets to Mean Reversion (~3h)

**Problem:** Win rate is positive (48-59%) but avg loss > avg win (no profit-taking).

**Proposed changes to `mean_reversion.py`:**
- Add configurable `take_profit_pct` parameter (default: 2.5%)
- When in a position, generate SELL signal if unrealized profit exceeds take_profit_pct
- Tighten stop-loss from 3% to 2% (reduce avg loss)
- Add trailing stop option: once profit > 1.5%, trail at 1% below high water mark
- Track position state between analyze() calls (entry price, high water mark)

**Risk:** Adding state to strategy makes backtesting harder (need to persist state across candles). The backtest engine currently creates signals independently per candle — may need modification to support stateful strategies.

**Backtest target:** Improve Mean Reversion avg return from +1.6% to >5% across 5 assets, with walk-forward consistency.

### WS3: Redesign Bollinger as a Fade Strategy (~3h)

**Problem:** Breakout buying loses 30% avg because most breakouts are fakeouts in the tested period.

**Proposed redesign:**
- **Bollinger Band Fade** — instead of buying breakouts, SELL (or close long) when price reaches upper band, BUY when price reaches lower band. This is effectively mean reversion using Bollinger Bands as the signal.
- Add entry conditions: only buy at lower band if RSI < 40 (confirmation of oversold). Only sell at upper band if RSI > 60.
- Add profit target: close position when price returns to middle band (SMA).
- Keep volume confirmation but make it less restrictive (1.25x instead of 1.5x).

**Alternative approach:** Convert Bollinger to a volatility squeeze detector. When Bollinger width is at a 20-period low (squeeze), prepare for a big move. Take direction from trend (SMA slope). This is more sophisticated but requires less redesign.

**Backtest target:** Positive average return across 5 assets.

### WS4: Add Momentum/Trend-Following Strategy (~4h)

**Problem:** No strategy can profit from sustained trends. ALL current strategies are mean-reversion biased.

**Proposed new strategy: `TrendFollowingStrategy`**

This is the critical missing piece. The strategy suite is 100% contrarian (buy dips, sell rips). In a bear market, this is suicide. A trend-following strategy provides:
- Long positions during uptrends (capture bull runs)
- Cash/neutral during downtrends (protect capital)
- Regime diversification against the mean-reversion strategies

**Entry logic:**
- **BUY:** Price closes above 50-period SMA AND 50-SMA > 200-SMA (golden cross confirmed) AND ADX > 20 (trending, not choppy)
- **SELL/EXIT:** Price closes below 50-period SMA OR 50-SMA < 200-SMA (death cross)

**Position sizing:** 15% of portfolio per trade (larger than mean reversion's 10% because trend trades have higher expected value but lower frequency).

**Confidence scoring:**
- ADX strength (higher ADX = stronger trend = higher confidence)
- Distance above/below SMA (further = more committed trend)
- Volume confirmation (1.25x average)

**Backtesting expectation:** In a year where BTC dropped 16% and ETH rose 9%, a trend follower should:
- Capture most of ETH's 9% uptrend
- Avoid most of BTC/SOL/DOGE/AVAX's declines by exiting when trend turns bearish
- Expected positive return on 3-4 of 5 assets

**Implementation:**
- New file: `hestia/trading/strategies/trend_following.py`
- New `StrategyType.TREND_FOLLOWING` enum value
- Backtest across all 5 assets with walk-forward validation

### WS5: Shelve Grid Trading (~1h)

**Problem:** -90.7% average return across all assets at $5K capital. Structural flaw, not parameter issue.

**Action:**
- Remove Grid from the active strategy allocation in `trading.yaml`
- Add `GRID_DEPRECATED` or `GRID_SHELVED` comment explaining why
- Document in decision log: Grid trading requires a tight ranging market AND capital large enough to overcome fee drag. Neither condition was met in the past year. Revisit only when: (a) regime detection can identify ranging periods, and (b) capital exceeds $10K.
- Keep the code (don't delete) — it may work under regime-detected ranging conditions in S28.

### WS6: Re-run Full Backtest Suite (~1h)

After WS1-WS5, re-run the multi-asset optimization:
- All fixed/new strategies against BTC, ETH, SOL, DOGE, AVAX
- Walk-forward validation on the top configs
- Compare against buy-and-hold baseline
- Document results in `data/backtest-results-s27.6.json`

**Go/No-Go decision:** If at least 2 strategies show positive average return across 5 assets with walk-forward consistency, proceed to S28 (regime detection). If not, reassess the strategy approach entirely.

---

## Estimated Effort

| Workstream | Hours | Risk |
|-----------|:---:|---|
| WS1: Fix Signal DCA bug | 2h | Low — likely a simple logic bug |
| WS2: Mean Reversion profit targets | 3h | Medium — stateful strategy adds complexity |
| WS3: Bollinger fade redesign | 3h | Medium — fundamental behavior change |
| WS4: Trend-following strategy | 4h | Medium — new strategy but well-known approach |
| WS5: Shelve Grid | 1h | Low — config + documentation |
| WS6: Full backtest re-run | 1h | Low — scripts already exist |
| **Total** | **~14h** | |

---

## Broader Market Considerations

### For Crypto (Current)
- Crypto markets are 24/7, highly volatile, and regime-dependent
- The past year was broadly bearish — strategies MUST work in bear markets, not just bull
- Mean reversion works best on large-cap coins with mean-reverting microstructure (ETH > BTC > SOL > DOGE)
- Trend following is essential for bear protection — crypto drawdowns of 50%+ are common

### For Stocks/ETFs (S29 via Alpaca)
- Equity markets have different characteristics: market hours, lower volatility, stronger mean reversion
- RSI parameters that work for crypto (7-period, 20/80) will NOT work for equities (14-period, 30/70)
- Trend following (SMA crossover) has decades of evidence working on equity indices
- DCA is the most proven equity accumulation strategy — fixing the bug matters for S29
- PDT rule (3 day trades / 5 days under $25K) means strategies must be swing-oriented, not intraday

### Strategy-Market Fit Matrix (Target State)

| Strategy | Crypto Bull | Crypto Bear | Crypto Range | Equity Bull | Equity Bear | Equity Range |
|----------|:---:|:---:|:---:|:---:|:---:|:---:|
| Mean Reversion | ✅ | ⚠️ (with stops) | ✅ | ✅ | ⚠️ | ✅ |
| Trend Following | ✅ | ✅ (cash) | ❌ (whipsaw) | ✅ | ✅ (cash) | ❌ |
| Signal DCA | ✅ (accumulate) | ✅ (buy cheap) | ✅ | ✅ | ✅ | ✅ |
| Bollinger Fade | ⚠️ | ⚠️ | ✅ | ⚠️ | ⚠️ | ✅ |
| Grid | ❌ | ❌ | ✅ (if capital >$10K) | N/A | N/A | ⚠️ |

**The fixed suite (Mean Reversion + Trend Following + Signal DCA + Bollinger Fade) covers all 6 regime-market combinations.** This is the foundation that regime detection (S28) will route capital through.

---

## Questions for Second Opinion

1. **Is the trend-following approach (50/200 SMA crossover + ADX) the right choice, or should we use a different method?** Alternatives: Donchian channel breakout, dual momentum (absolute + relative), or simple price > 200-SMA binary.

2. **For the Bollinger redesign: fade (mean reversion at bands) vs. squeeze detector (volatility expansion) — which has better expected value across diverse assets?**

3. **At $250 starting capital across 5 assets = $50/asset — is this enough for any strategy to overcome fees? Should we concentrate on fewer assets initially?**

4. **The walk-forward validation failed even for Mean Reversion's best config (+7.7% on BTC). Is this because the walk-forward methodology is too strict (30d train / 7d test), or does it genuinely indicate no reliable edge?**

5. **For the broader vision (crypto + stocks + ETFs): should we design the trend-following strategy with equity parameters from the start (14-period SMA, longer timeframes), or optimize separately for crypto and equities?**

6. **Is adding a single trend-following strategy sufficient for bear-market protection, or do we need dedicated short-selling or inverse-ETF capability?**
