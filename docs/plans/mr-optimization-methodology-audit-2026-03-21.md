# Methodology Audit: Mean Reversion Optimization Results

**Date:** 2026-03-21
**Models:** Claude Opus 4.6 (internal) + Gemini 2.5 Pro (external)
**Type:** Data verification + methodology audit
**Verdict:** PROCEED WITH CORRECTIONS — results are real but methodology has biases that inflate returns

## Verified Data

All 15 claimed return figures independently re-computed and match exactly (0% deviation). The numbers are not hallucinated. The question is whether the METHODOLOGY that produced them is sound.

## Gemini's Methodology Audit — 6 Concerns

### Concern 1: Close-price entry bias
**Gemini says: CRITICAL — look-ahead bias, entire source of profit**
**Claude's assessment: PARTIALLY VALID — less severe than stated**

The engine uses `lookback_shift=1`, meaning the strategy sees data up to candle `i-1` and executes at candle `i`'s close. This is NOT classic look-ahead (the strategy can't see the execution candle's data). However, executing at `CLOSE[i]` instead of `OPEN[i]` introduces a modest favorable bias for mean reversion (the reversion may have already started by close).

**Action required:** Re-run backtests with `OPEN[i]` execution price. If results drop >50%, Gemini is right and the edge is fragile. If <30% degradation, the edge is real.

### Concern 2: Walk-forward failure (3/4 assets)
**Gemini says: CRITICAL — strong evidence of overfitting**
**Claude's assessment: VALID**

Walk-forward win rates of 33-44% below 50% means optimized params don't generalize across sub-periods. DOGE passing both periods is notable but insufficient to claim robustness. The per-asset "optimal" RSI parameters may be curve-fit.

**Action required:** Test with UNIFORM parameters (e.g., RSI-3 25/75 for all assets) to see if a less-optimized but more robust config still produces positive returns.

### Concern 3: RSI-3 regime dependency
**Gemini says: REAL — fragile microstructure edge**
**Claude's assessment: VALID CONCERN but unverifiable with available data**

RSI-3 captures 3-hour mean reversion cycles. This may be structural to crypto markets (24/7, retail-dominated) or temporary. We can't test this with 2 years of data. The mitigation is capital gates — start small, scale only if live results match backtests.

### Concern 4: No stop-loss = unbounded risk
**Gemini says: REAL — strategy relies on "all drawdowns are temporary"**
**Claude's assessment: VALID but existing 8-layer risk manager mitigates**

The 15% drawdown circuit breaker, 5% daily loss limit, and kill switch provide portfolio-level protection even without per-trade stops. The backtest correctly shows that per-trade stops hurt returns, but the risk manager catches catastrophic scenarios that per-trade stops were designed for.

### Concern 5: BTC 25-trade sample size
**Gemini says: REAL — statistically insignificant**
**Claude's assessment: VALID**

25 trades is too few for reliable statistics. The 80% win rate and Sharpe 1.59 should be disregarded as unreliable. BTC's wider bands (15/85) produce very few signals — this config should be deprioritized in favor of the tighter bands (ETH 20/80, SOL 25/70) that generate 65-190 trades.

### Concern 6: Maker vs taker fees
**Gemini says: REAL — strategy is a taker, not maker**
**Claude's assessment: PARTIALLY VALID**

Coinbase Post-Only limit orders guarantee maker fees (0.4%). The strategy CAN use Post-Only orders. However, Post-Only orders can be rejected if they'd cross the spread, and the backtest doesn't model rejection/re-submission latency. Realistic fee estimate is 0.4-0.5%, not 0.6%.

**Action required:** Re-run with 0.5% fee to see impact.

## Additional Biases (from Gemini)

### Asset selection bias
**VALID.** Excluding AVAX after seeing it's unprofitable is hindsight. A fair test would pre-select the asset universe before optimization.

### Parameter optimization bias
**VALID but mitigated.** The per-asset parameter search IS a form of curve-fitting. The walk-forward failure confirms this. However, the parameters have reasonable financial intuition (faster RSI for crypto, tighter bands for mean-reverting assets) — they're not arbitrary.

## Reconciliation

| Concern | Gemini | Claude | Impact |
|---------|--------|--------|--------|
| Close-price entry | CRITICAL | Moderate | Re-test with OPEN price |
| Walk-forward failure | CRITICAL (overfit) | Valid | Test uniform params |
| RSI-3 fragility | Real | Valid but unverifiable | Start small, capital gates |
| No stop-loss | Unbounded risk | Mitigated by risk manager | Accept for now |
| BTC 25 trades | Statistically insignificant | Valid | Deprioritize BTC wide bands |
| Maker vs taker | 50% cost increase | 25% cost increase | Re-test at 0.5% |
| Asset selection bias | Valid | Valid | Pre-select universe |

## Gemini's Estimate: 70-90% Degradation
## Claude's Estimate: 30-50% Degradation

The truth depends on the close-vs-open test. If Concern 1 is as bad as Gemini says, returns collapse. If it's moderate (as I suspect given the lookback_shift already prevents same-candle look-ahead), the strategy retains an edge.

## Required Next Steps Before Deployment

1. **Re-run backtests with OPEN[i] execution price** — this is the single most important test
2. **Re-run with 0.5% fee** — realistic maker fee with rejection overhead
3. **Test uniform RSI-3 25/75 across all assets** — proves robustness vs overfitting
4. **If still positive after corrections:** deploy with $25 live for 30-day validation
5. **If negative after corrections:** the edge was a methodology artifact, not a real market inefficiency
