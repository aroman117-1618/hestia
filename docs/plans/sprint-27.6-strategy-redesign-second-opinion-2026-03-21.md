# Second Opinion: Sprint 27.6 Strategy Redesign

**Date:** 2026-03-21
**Models:** Claude Opus 4.6 (internal) + Gemini 2.5 Pro (external)
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary

Fix the broken strategy foundation discovered by S27.5 backtesting. All 4 strategies lose money across 5 crypto assets over 1 year. The plan proposes: fix Signal DCA bug, add profit targets to Mean Reversion, redesign Bollinger as a fade strategy, add a new trend-following strategy, and shelve Grid. ~14h estimated.

## Evidence Base (Empirical — Not Theoretical)

| Strategy | 5-Asset Avg | BTC | ETH | Walk-Forward |
|----------|:---:|:---:|:---:|:---:|
| Mean Reversion (best config) | +1.6% | -2.5% | +56.0% | FAIL |
| Signal DCA | -0.2% | -1.0% | 0 trades | BUG |
| Bollinger Breakout | -30.2% | -19.0% | +2.0% | FAIL |
| Grid ($5K) | -90.7% | -90.7% | -98.1% | FAIL |

Buy-and-hold baseline: BTC -16.4%, ETH +9.0%, SOL -29.6%, DOGE -43.9%, AVAX -49.5%

## Front-Line Engineering

- **Feasibility:** High for DCA bug fix and Grid shelving. Medium for Mean Reversion (stateful strategy) and trend-following (new strategy). Medium-high for Bollinger redesign.
- **Hidden prerequisite:** The backtest engine generates signals per-candle without preserving strategy state. Adding profit targets and trailing stops requires either: (a) modifying the engine to pass state, or (b) strategies tracking their own position state internally. Option (b) is simpler but less testable.
- **Testing gaps:** Walk-forward validation failed even for the best Mean Reversion config. This means either the methodology is too strict OR the parameters are genuinely overfit. Gemini says trust the walk-forward — it's detecting real overfitting.

## Architecture Review

- **Fit:** New trend-following strategy follows `BaseStrategy` ABC cleanly. New `StrategyType.TREND_FOLLOWING` enum.
- **Data model:** No schema changes needed.
- **Integration risk:** Low — strategies are plugged into the existing BotRunner pipeline.

## Product Review

- **User value:** Maximum — prevents deploying strategies that lose money.
- **Scope:** Gemini recommends narrowing to 2 strategies (trend + mean reversion) rather than fixing all 4. This is a significant scope change.
- **Opportunity cost:** Every hour on strategy fixes delays S28-S30. But S28-S30 on broken strategies would waste far more time.

## Infrastructure Review

- **Deployment:** Strategy changes don't require server restart during development.
- **Rollback:** Clean — each strategy is independent.
- **Resource impact:** None.

## Executive Verdicts

- **CISO:** Acceptable — no security changes
- **CTO:** Approve with conditions — adopt Dual Momentum over SMA crossover (Gemini recommendation)
- **CPO:** Approve with conditions — concentrate capital on 1-2 assets until $1K+ (Gemini recommendation)
- **CFO:** Acceptable — 14-40h to fix a $0 foundation vs building 61h on losing strategies
- **Legal:** Acceptable — no regulatory impact

## Key Principles Score

| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 5 | No change |
| Empathy | 5 | Prevents capital loss from deploying broken strategies |
| Simplicity | 4 | Fewer strategies (2-3) is simpler than fixing all 4 |
| Joy | 4 | Finding real edges is deeply satisfying |

## Final Critiques

1. **Most likely failure:** Optimized Mean Reversion parameters are curve-fit to 2025-2026 data and fail in different market conditions. **Mitigation:** Use Dual Momentum (fewer parameters, longer lookback, less curve-fit-prone) and validate across multiple market periods.

2. **Critical assumption:** That fixing strategy logic (profit targets, exits) will turn negative-EV strategies into positive-EV. It's equally possible that the strategies simply don't have an edge, and no parameter tuning will create one. **Validation:** If walk-forward STILL fails after fixes, the strategy approach itself needs rethinking.

3. **Half-time cut list (~7h):** Keep: DCA bug fix (2h) + Dual Momentum trend strategy (4h) + shelve Grid (1h). Cut: Bollinger redesign (fix only if time permits after validating the two core strategies).

## Cross-Model Validation (Gemini 2.5 Pro)

### Gemini's Independent Assessment

Gemini provides expert quant guidance with specific, actionable recommendations:

**Verdict: APPROVE WITH CONDITIONS**

### Where Both Models Agree

- Signal DCA bug is a code issue, not a strategy issue — fix it first
- Grid should be shelved (structural flaw, not parameter issue)
- Mean Reversion walk-forward failure IS genuine overfitting (trust the validation)
- Trend-following is the critical missing piece
- Cash/long-only is sufficient for bear protection (no need for short selling)
- 14h estimate is too aggressive
- Capital should be concentrated on fewer assets until $1K+

### Where Models Diverge

| Topic | Claude | Gemini | Resolution |
|-------|--------|--------|------------|
| **Trend approach** | 50/200 SMA crossover + ADX | **Dual Momentum** (Antonacci) — absolute + relative momentum | **Gemini is right.** Dual Momentum has decades of academic validation, fewer parameters (less curve-fitting), and built-in regime filtering (absolute momentum takes you to cash in downtrends). Adopt this. |
| **Bollinger redesign** | Fade strategy (buy lower band, sell upper band) | Not addressed directly — recommends focusing on 2 core strategies | **Gemini is right.** Focus on getting 2 strategies working (trend + mean reversion) before fixing a third. Bollinger fade is nice-to-have, not must-have. |
| **Timeline** | 14h | 30-40h | **Gemini is closer to right.** Budget 20-25h realistically — the DCA bug may be quick, but Dual Momentum implementation + validation across multiple assets + walk-forward needs proper time. |
| **Walk-forward methodology** | Possibly too strict (30d/7d windows) | **Trust the results** — 30d train is likely too SHORT for hourly data. Recommends 90-180d training windows. | **Gemini is right.** Longer training windows produce more robust parameters. Adjust walk-forward to 90d train / 30d test. |
| **Number of strategies** | Fix all 4 | **Start with 2** — one trend + one mean reversion | **Gemini is right.** Quality over quantity. Two well-validated strategies beat four mediocre ones. |

### Novel Insights from Gemini

1. **Dual Momentum (Antonacci)** — the single most important recommendation. Uses absolute momentum (is the asset going up?) + relative momentum (which asset is going up the most?). Has decades of out-of-sample validation across stocks, bonds, and commodities. Fewer parameters than SMA crossover = less curve-fitting. Built-in bear market protection (absolute momentum takes you to cash when returns are negative). This should replace the proposed SMA crossover approach.

2. **Capital concentration is non-negotiable** — at $50/asset with 0.8% round-trip fees, no active strategy can generate net positive returns. This is a mathematical constraint, not a strategy issue. Concentrate all capital ($250) on 1-2 assets until reaching $1K+.

3. **Simple regime filter first** — instead of the complex HMM planned for S28, use BTC > 200-day SMA as a binary market barometer. Above = risk-on (enable all strategies). Below = risk-off (enable only mean reversion or go to cash). This can be implemented in hours, not a full sprint.

4. **Fixed fractional position sizing** — risk no more than 1-2% of equity per trade. This is separate from Kelly sizing and is non-negotiable for long-term survival. Current strategies risk 5-15% per trade which is too aggressive at $250.

5. **Lower frequency = lower fees** — switch from hourly to daily signals. Fewer trades = less fee drag. A daily-timeframe Dual Momentum strategy would trade ~12 times per year, making fees negligible even at $250.

### Reconciliation

Both models agree the foundation is broken and must be fixed before expanding scope. The key upgrade from Gemini is the **Dual Momentum** recommendation, which is a materially better trend-following approach than SMA crossover — more robust, fewer parameters, decades of evidence, and built-in regime filtering.

The revised S27.6 should focus on **two strategies done well** rather than four done adequately:
1. **Dual Momentum** (trend/regime) — long when absolute momentum positive, cash when negative, rotate to strongest performer
2. **Mean Reversion** (RSI-based) — with profit targets and tighter stops, for ranging markets

Signal DCA should be fixed (it's a bug) but deprioritized as a core strategy. Bollinger redesign deferred. Grid shelved.

## Conditions for Approval

### Must-Have

1. **Replace SMA crossover with Dual Momentum** — use 6-12 month lookback for absolute momentum, 3-6 month for relative momentum. Fewer parameters, less curve-fitting, proven across asset classes.

2. **Concentrate capital on 1-2 assets** — all $250 on BTC or ETH until capital reaches $1K+. This is a mathematical requirement given fee structure.

3. **Fix Signal DCA bug** — it's a code bug, not a strategy issue. Fix it even if DCA becomes a secondary strategy.

4. **Adjust walk-forward to 90d train / 30d test** — current 30d/7d is too short for hourly data and may be rejecting valid parameters.

5. **Shelve Grid** — confirmed by both models.

### Should-Have

6. **Switch to daily timeframe for Dual Momentum** — reduces fee impact from 0.8% per trade on 100+ annual trades to 0.8% on ~12 trades. This alone could flip a losing strategy positive.

7. **Add fixed fractional sizing (1-2% risk per trade)** — separate from Kelly, this is a hard cap on per-trade risk.

8. **Implement simple regime filter** — BTC > 200-day SMA = risk-on. Below = risk-off/cash. Gets 80% of S28's regime detection value in 2 hours.

9. **Budget 20-25h** — not 14h. Dual Momentum is simpler than SMA crossover but still needs proper implementation, multi-asset backtesting, and walk-forward validation.

### Deferred

10. Bollinger fade redesign — revisit after Dual Momentum + Mean Reversion are validated
11. Multi-asset diversification (5+ assets) — revisit at $1K+ capital
12. Complex regime detection (HMM) — the simple 200-SMA filter handles most of this

## Critical Additions from @hestia-critic

### Finding 1: Backtest Engine Cannot Validate Profit Targets
`_simulate_trades()` processes signals at candle close prices ONLY. No intra-candle high/low checks. If a profit target is hit during a candle, the engine misses it. **Any backtest of profit targets or trailing stops will be systematically wrong.** The engine needs intra-candle exit simulation BEFORE stateful exit strategies can be tested.

### Finding 2: Walk-Forward Position-State Contamination
`walk_forward()` combines train+test data and runs the full strategy, then slices equity at `train_size`. Open positions from training contaminate test returns. This is look-ahead bias on position state — may explain inconsistent walk-forward results.

### Finding 3: Best Mean Reversion Used NO Volume Filter
The +56% ETH result used `volume_confirmation=1.0` (effectively disabled). Adding more filters (profit targets, trailing stops) runs counter to the empirical evidence. Fewer filters = better results on this data.

### Finding 4: Signal DCA Root Cause Confirmed
`signal_dca.py:82` uses `datetime.now(timezone.utc)` (wall-clock time) instead of candle timestamp. In backtesting, elapsed time between candles is ~0 seconds, permanently blocking the interval gate after the first buy. Fix: pass candle timestamp to `analyze()`.

## FINAL Revised S27.6 Workstreams (All 3 Reviewers Synthesized)

### Phase 1: Fix the Foundation (BEFORE strategy work)

| WS | Scope | Hours | Why |
|----|-------|:---:|---|
| WS1 | Fix Signal DCA wall-clock bug — pass candle timestamp to analyze() | 0.5h | Code bug, confirmed root cause |
| WS2 | Fix walk-forward position-state contamination — reset at test boundary | 2h | Invalidates ALL walk-forward results |
| WS3 | Add intra-candle exit simulation to backtest engine (high/low checks) | 3h | BLOCKER for profit targets and trailing stops |

### Phase 2: Validate What Works

| WS | Scope | Hours | Why |
|----|-------|:---:|---|
| WS4 | Systematic Mean Reversion sweep with FIXED engine (RSI 5/7/9 × oversold 15/20/25 × volume on/off, 5 assets, 90d/30d walk-forward) | 2h | Find params with real edge, not overfit |
| WS5 | Implement Dual Momentum strategy (Antonacci) — daily timeframe, absolute + relative momentum | 5h | Gemini's top recommendation, decades of evidence |

### Phase 3: Configure & Validate

| WS | Scope | Hours | Why |
|----|-------|:---:|---|
| WS6 | Shelve Grid + update config | 1h | Confirmed non-viable by all reviewers |
| WS7 | Full re-backtest all strategies (90d/30d walk-forward, 5 assets) | 2h | Validate with fixed engine |
| **Total** | | **~15.5h** | |

### Deferred (to S27.7 or S28)
- Mean Reversion profit targets + trailing stops (requires WS3 complete)
- Bollinger fade redesign
- Simple regime filter (Dual Momentum provides built-in regime filtering)
- Fixed fractional position sizing
