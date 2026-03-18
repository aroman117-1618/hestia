# Gemini Deep Research Prompt: Crypto Algo Trading Module

Copy everything below the line into Gemini Deep Research.

---

## Context

I'm building an autonomous algorithmic cryptocurrency trading module as part of a personal AI assistant (Python/FastAPI backend, Swift iOS/macOS frontend, running on Mac Mini M1). I have a development plan ready and want you to serve as a critical second opinion — find what I might be missing, challenge my assumptions, and surface real-world lessons from people who've built similar systems.

## My Current Plan (summarized)

**Capital:** $500–$2,000 starting, scaling over time
**Exchange:** Coinbase Advanced Trade API (spot only for MVP), with CCXT abstraction layer for adding Kraken/futures later
**Target Returns:** 25–50% annualized (moderate risk tolerance)
**Leverage:** Starting at 1x, data-driven Kelly criterion optimization after 3 months of live data
**Operation:** Fully autonomous on Mac Mini M1, 24/7

**Three strategies (Coinbase spot only):**
1. Grid Trading (45% allocation) — BTC/USDT, ETH/USDT, targeting ranging markets
2. Mean Reversion (25% allocation) — RSI-based entry/exit with hard stop-losses
3. Signal-Enhanced DCA (30% allocation) — Technical-trigger accumulation (RSI + MA confluence)

**Risk management:** 25% max single trade, 80% max deployed, 15% drawdown circuit breaker, 5% daily loss halt, exchange-native stop-losses as backup.

**AI enhancement (later phases):** LLM sentiment analysis (news/social), on-chain data (whale movements, exchange flows), ML parameter optimization with walk-forward analysis.

**Tech stack:** Python 3.12, FastAPI, CCXT + coinbase-advanced-py, VectorBT (backtesting), pandas-ta (indicators), SQLite (trade database), WebSocket for real-time data.

## What I Need From You

### 1. Strategy Critique & Alternatives

Research and evaluate:
- **Grid trading at this capital level** — what do real practitioners report? What grid spacing, range width, and pair selection actually work? What's the typical failure mode and how quickly does it fail in trending markets?
- **Are there better strategies I'm not considering?** Specifically research: Bollinger Band breakout strategies, VWAP-based strategies, order flow imbalance strategies, and triangular arbitrage within a single exchange. How do these compare to my chosen three at the $500–$2K level?
- **Mean reversion RSI thresholds** — the standard 30/70 oversold/overbought levels. Is there research showing different thresholds work better for crypto specifically? What about combining RSI with volume confirmation or Bollinger Band width?
- **Strategy correlation risk** — all three of my strategies are long-biased (can only profit when prices go up). How significant is this limitation at the $500–$2K level? What's the realistic impact of not being able to short?

### 2. Architecture & Implementation Deep Dive

Research:
- **Open-source crypto trading bot architectures** — specifically Freqtrade, Hummingbot, Jesse, and Zenbot. What architectural patterns do they use that a custom system should adopt? What mistakes did they make early that were painful to fix?
- **Order execution patterns** — limit vs market orders for each strategy type. What's the real slippage on Coinbase for small orders ($20–$100)? How do successful bots handle partial fills?
- **WebSocket reliability** — what's Coinbase's WebSocket uptime in practice? How do production bots handle disconnections, missed ticks, and stale data? What's the recommended reconnection strategy?
- **Backtesting pitfalls specific to crypto** — survivorship bias with delisted coins, exchange-specific data quirks, look-ahead bias in indicator calculation, and the "backtest looks great, live trading doesn't" gap. What's the typical performance degradation from backtest to live?
- **Database design for trading** — SQLite vs TimescaleDB vs InfluxDB for tick data. What are the query patterns that matter most? How do open-source bots handle data storage at scale?

### 3. Risk Management Reality Check

Research:
- **Circuit breaker design in practice** — what do real trading systems use? Are my thresholds (15% drawdown, 5% daily loss) appropriate for crypto's volatility? What do institutional crypto funds use?
- **Kelly criterion for crypto** — is half-Kelly actually optimal, or is there research suggesting a different fraction for highly volatile assets? What sample size is needed for a reliable Kelly estimate?
- **Black swan preparation** — what happens to grid bots during events like the May 2021 crash (-53% in 2 weeks), the FTX collapse (Nov 2022), or the March 2020 COVID crash (-50% in 2 days)? Would my circuit breakers have triggered in time?
- **Exchange risk** — Coinbase API outages during high volatility (when you need it most). How frequent are these? What's the mitigation strategy beyond "exchange-native stop-losses"?

### 4. AI/ML Enhancement Viability

Research:
- **Crypto sentiment analysis ROI** — is there rigorous academic or practitioner evidence that LLM sentiment analysis actually improves crypto trading returns? What's the signal-to-noise ratio? How quickly does sentiment alpha decay?
- **On-chain data as a trading signal** — whale movement tracking, exchange inflows/outflows. How actionable are these signals at the retail level? What's the typical lag between on-chain event and price move? Are there free data sources with sufficient granularity?
- **ML parameter optimization risks** — walk-forward analysis, Bayesian optimization for strategy parameters. What's the minimum amount of data needed to avoid overfitting? How do practitioners validate that optimization actually helps vs. just curve-fitting?
- **Local LLM viability** — can a 9B parameter model (Qwen 3.5) running on M1 16GB produce useful sentiment analysis, or is this a task that genuinely requires frontier models (GPT-4, Claude)?

### 5. Regulatory & Tax Considerations

Research:
- **US regulatory status** of automated crypto trading for personal use in 2025–2026
- **Tax implications** — wash sale rules for crypto, cost basis tracking for high-frequency grid trading (potentially hundreds of trades per month), recommended tax software for automated trading
- **Coinbase reporting** — what does Coinbase report to the IRS? How does this interact with automated trading?

### 6. Failure Mode Analysis

Research real cases of:
- **Small-account algo traders who failed** — what went wrong? Common patterns?
- **Grid bot disasters** — specific examples of grid bots losing significant capital and why
- **The "backtest millionaire" trap** — examples of strategies that backtested beautifully but failed live, and the specific reasons why
- **API/infrastructure failures** — real incidents where trading bot infrastructure failures caused losses

## Output Format

Please structure your response as:
1. **Executive Summary** — top 5 findings that should change or validate my plan
2. **Strategy Analysis** — detailed findings per strategy with specific data points
3. **Architecture Recommendations** — concrete changes to my tech stack or design
4. **Risk Management Findings** — validated or revised thresholds with evidence
5. **AI/ML Assessment** — honest viability assessment with evidence
6. **Regulatory & Tax Summary** — actionable items
7. **Failure Case Studies** — specific examples with lessons
8. **Recommended Changes to My Plan** — prioritized list of modifications

For each finding, include the source and how confident you are in the data quality. I want evidence, not opinions.
