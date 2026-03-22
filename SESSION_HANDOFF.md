# Session Handoff — 2026-03-21 (Trading Strategy Validation)

## Mission
Validate the trading module's strategy foundation through comprehensive backtesting, fix backtest engine bugs, optimize strategies, and deploy a 4-asset per-parameter portfolio on the Mac Mini.

## Completed

### S27.5: Backtest Validation
- **Initial backtests:** ALL 4 strategies lose money on BTC over 1yr. Grid -90%, Bollinger -30%, MR -3%, DCA 0 trades (bug). (`scripts/run-backtests.py`)
- **Multi-asset sweep:** 696 combos × 5 assets. Mean Reversion only viable strategy. (`scripts/optimize-multi-asset.py`)
- **Bull vs bear:** MR-fast-moderate +15.4% bull, +4.0% bear = +9.7% combined avg. Buy-and-hold was -15%. (`scripts/run-backtests-bull-market.py`, `a1ef95d`)

### S27.6: Engine Fixes + Strategy Redesign
- **Signal DCA bug:** wall-clock → candle timestamp for interval gate (`d152557`)
- **Walk-forward fix:** fresh capital per test window, no position contamination (`3e7d403`)
- **Intra-candle exits:** stop-loss/take-profit check high/low prices (`4ae6c13`)
- **Dual Momentum strategy:** new `DualMomentumStrategy` — has 0-trade bug, deferred (`f55004d`)
- **Grid shelved:** allocation 0% (`92aabdb`)

### Aggressive Optimization + Methodology Audit
- **Per-asset RSI-3:** 245 combos × 5 assets × 2 periods = +22.8% combined (`62a72c5`)
- **Independent verification:** 15/15 numbers match exactly (`fb4fe51`)
- **Gemini methodology audit:** close-price bias = ZERO. Fee impact = 9%. Uniform params = 99% degradation (overfitting confirmed). (`e9e236b`)
- **Corrected backtests:** OPEN price + 0.5% fee. Per-asset: **+20.9%**. Uniform: +0.2%. (`0a2ea8e`)

### Deployment
- **4 bots deployed on Mac Mini:** ETH ($85, RSI-3 20/80), BTC ($82.50, RSI-3 15/85), SOL ($50, RSI-3 25/70), DOGE ($32.50, RSI-3 25/75). All running. (`10137bc`)

### Key Commits (this session)
- `d152557` fix: Signal DCA wall-clock bug
- `3e7d403` fix: walk-forward position-state contamination
- `4ae6c13` feat: intra-candle exit simulation
- `f55004d` feat: Dual Momentum strategy
- `92aabdb` feat: shelve Grid, update allocation
- `62a72c5` feat: aggressive MR optimization (+22.8%)
- `fb4fe51` feat: independent verification (15/15 match)
- `0a2ea8e` feat: corrected backtests (+20.9% survives)
- `10137bc` feat: deploy 4-asset portfolio

## In Progress
- **4-asset paper soak** — started 02:29 UTC Mar 22. All HOLD (RSI neutral). Waiting for oversold/overbought.
- **Dual Momentum 0-trade bug** — deferred. Position state doesn't interact correctly with backtest engine.

## Decisions Made
- **Per-asset RSI-3 over uniform:** +20.9% vs +0.2%. Accept partial overfitting, validate with live capital gates.
- **No stop-losses:** ALL stop configs reduce returns (19-47%). Risk managed by 8-layer risk manager.
- **Shelve Grid, Bollinger, DCA, Dual Momentum:** Only MR shows reliable returns across both market regimes.
- **Sharpe-weighted allocation:** ETH 34%, BTC 33%, SOL 20%, DOGE 13%.

## Test Status
- 2779 total (2644 backend + 135 CLI), 87 test files, all passing

## Uncommitted Changes
- None from this session.

## Known Issues / Landmines
- **Per-asset params partially overfit** — walk-forward fails 3/4 assets. Live validation essential.
- **BTC RSI-3 15/85 = very few trades** (21-25/yr). Small sample, unreliable stats.
- **DOGE highest risk** — 54.7% max drawdown in bull period. Monitor closely.
- **Dual Momentum 0-trade bug** — exists as code, doesn't work in backtests.
- **Mac Mini macOS app → localhost** — reset: `defaults write com.andrewlonati.hestia-macos hestia_environment tailscale`
- **Alpaca API keys still 403** — S29 blocked.

## Process Learnings
- **First-pass success: 12/15 (80%)** — rework from zsh heredoc issues and backtest execution time
- **@hestia-critic was the MVP** — found backtest engine bugs that no one else caught
- **Gemini methodology audit was invaluable** — caught overfitting (valid) and false-alarmed on close-price bias
- **Backtest execution time is the bottleneck** — each sweep takes 10-20 min. Multiple sweeps = hours.

## Next Step
1. **Check soak tomorrow:** `ssh andrewroman117@hestia-3.local "grep trading ~/hestia/logs/hestia.log | tail -40"` — look for BUY/SELL across 4 assets
2. **If signals firing:** let run 72h through ~Mar 25
3. **If no signals after 48h:** widen bands (RSI thresholds less restrictive)
4. **Next session:** Fix Dual Momentum bug, iOS app audit, flip to live ($25) if soak validates
