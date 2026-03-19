# Second Opinion: Sprint 28 — Alpaca + Stocks Expansion
**Date:** 2026-03-19
**Models:** Claude Opus 4.6 (internal) + Gemini 2.5 Pro (external) + @hestia-critic (adversarial)
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary

Sprint 28 expands Hestia's trading module from crypto-only (Coinbase) to multi-asset (Coinbase + Alpaca) across two sub-sprints: S28A (~15h, crypto strategy expansion + backtests) and S28B (~20h, AlpacaAdapter read-only + market hours + multi-exchange orchestrator). Full equity orders and PDT enforcement deferred to S29A. Discovery: `docs/discoveries/sprint-28-alpaca-stocks-expansion-2026-03-19.md`.

**Updated context:** Margin account, $100K available in Fidelity, scaling goal = thousands/month passive income, regular hours first, Alpaca account pending approval.

## Scale Assessment

| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|----------------|-------------------|
| Single user | Yes | None — personal investment platform | N/A |
| Family (2-5) | Partially | Separate brokerage accounts needed. Risk manager needs per-user isolation. | Medium |
| Community | No | Regulatory implications of managing others' money | N/A — not the goal |

## Front-Line Engineering

- **Feasibility:** Strong. Adapter pattern is proven. `alpaca-py` SDK is Pydantic-based, maps 1:1 to `AbstractExchangeAdapter` ABC.
- **Effort realism:** S28A (~15h) accurate. S28B (~20h) accurate — AlpacaAdapter (8h) + market hours (4h) + orchestrator refactor (5h) + product info (3h).
- **Hidden prerequisites:** `alpaca-py` in `pyproject.toml`, Alpaca API keys in Keychain (pending account approval), orchestrator refactor before S28B bots.
- **Testing gaps:** No mention of integration tests against Alpaca paper environment. No equity backtesting framework mentioned (Gemini finding).

## Architecture Review

- **Fit:** Excellent. Follows adapter pattern, uses existing models, extends config cleanly.
- **Data model:** Already prepared — `asset_class`, `settlement_date` columns exist on Trade, Bot, TaxLot. No new migrations.
- **Multi-exchange routing:** Per-bot exchange assignment recommended (Bot model gets `exchange` field, orchestrator holds `Dict[str, AbstractExchangeAdapter]`).
- **Integration risk:** Low — AlpacaAdapter is a new file, orchestrator changes are additive.

## Product Review

- **User value:** Highest-value item on the roadmap. $100K available capital × algo trading = direct path to passive income goal.
- **Scope:** Right-sized. S28A + S28B is ~35h. S29A (live orders) correctly deferred.
- **Opportunity cost:** Minimal — Sprint 27 is in soak, quick wins are done.

## UX Review

No new UI needed for S28. Existing dashboard supports multi-bot display with `asset_class` filtering. Optional: asset class filter chip on dashboard.

## Infrastructure Review

- **Deployment impact:** Server restart (new package). Standard.
- **New dependency:** `alpaca-py` (Apache-2.0, actively maintained, no conflicts).
- **Rollback strategy:** Clean git revert — all changes are additive.
- **Resource impact:** Negligible. Market hours gating actually reduces polling load vs 24/7 crypto.

## Executive Verdicts

- **CISO:** Acceptable — Keychain credentials, no withdrawal API, kill switch. Standard security patterns.
- **CTO:** Acceptable — clean adapter pattern, well-designed multi-exchange routing, no technical debt.
- **CPO:** Acceptable — highest-value roadmap item. Direct path to stated financial goals.
- **CFO:** Acceptable — ~35h build cost. Even 0.5%/month on $50K = $250/month passive income. High ROI.
- **Legal:** Acceptable — personal trading on regulated US brokerage (FINRA member). Tax lot tracking exists.

## Key Principles Score

| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 5 | Keychain creds, no withdrawal API, PDT two-layer defense, kill switch |
| Empathy | 5 | Directly serves Andrew's financial goals — not infrastructure for its own sake |
| Simplicity | 4 | Adapter pattern is clean. Market hours add essential complexity. |
| Joy | 5 | Personal investment platform milestone — crypto + stocks under one roof |

## Final Critiques

### Counter-Plan: "Use Fidelity's Robo-Advisor"
Andrew already has $100K in Fidelity. Their robo-advisor offers automated investing, DCA, and tax-loss harvesting with zero engineering effort. **Credible for pure returns** — but misses personalization, cross-asset intelligence, and the build-it-yourself value proposition. Hestia's edge is automation + signal-enhanced timing + cross-asset portfolio intelligence (future).

### Future Regret Analysis
- **3 months:** Signal DCA may not beat simple monthly SPY purchases. Frame as "disciplined automation" not "beating the market."
- **6 months:** If $100K moved and a drawdown hits, regret is real and financial. Graduated ramp is critical.
- **12 months:** Multi-exchange infrastructure enables Sprint 29-30 (AI sentiment, regime detection). If those deliver, S28 compounds. If not, still a functional DCA tool.

### Stress Tests
1. **Most likely failure:** Paper trading fills don't match live behavior (100% fill assumption). **Mitigation:** 2-week paper soak minimum, start live at $25.
2. **Critical assumption:** "Alpaca API is stable for automated trading." **Validation:** 800+ star SDK, active maintenance, but monitor status page.
3. **Half-time cut list:** Keep S28B only (AlpacaAdapter + market hours + orchestrator = 17h). Cut S28A entirely (crypto strategies can wait). **S28B is the true priority.**

## Cross-Model Validation (Gemini 2.5 Pro)

### Gemini's Independent Assessment
Gemini rated the plan **APPROVE WITH CONDITIONS**. Praised the phased rollout (read-only → full orders) as "the single most important feature of this plan." Agreed S28B should be prioritized over S28A. Flagged several risks not in the internal audit.

### Where Both Models Agree
- S28B (Alpaca integration) is the priority over S28A (crypto strategies)
- Read-only first → full orders later is the correct phasing
- Margin account is the right choice for algo trading at scale
- PDT enforcement correctly deferred to S29A
- The $100K capital context means the graduated ramp must be rigorous
- Paper trading fills are unrealistically optimistic — live will be worse
- Custom build is justified by personalization + cross-asset intelligence goals

### Where Models Diverge

| Topic | Claude | Gemini | Resolution |
|-------|--------|--------|------------|
| S28B effort estimate | 20h (accurate) | "Seems optimistic" — flags unseen glue code | **Split the difference.** 20-25h is realistic. Error handling and data validation are real but bounded work. |
| Cloud deployment | Not discussed | Recommends moving trading to cloud VPS to eliminate Mac Mini SPOF | **Defer.** Mac Mini with Tailscale remote access is sufficient for single-user. Cloud adds complexity and cost. Revisit if capital exceeds $25K. |
| Capital gates | Manual judgment with graduated ramp | Must be automated state machine — "manual judgment is susceptible to emotion" | **Gemini is right.** Formalize as performance-gated system: Sharpe > 1.0, MaxDD < 15%, positive net profit over 30+ days before tier-up. Implement in S29A alongside PDT. |

### Novel Insights from Gemini

1. **Corporate actions (splits, dividends, mergers):** Not mentioned in the discovery or internal audit. A stock split would break price-based algorithms and corrupt position tracking. Alpaca provides corporate action data — the adapter must handle it. **Add to S28B scope.**

2. **Automated capital gates:** The graduated ramp should be a code-enforced state machine, not manual. Performance criteria (Sharpe ratio, max drawdown, win rate) must be met over a statistically significant period (30-60 days, 50+ trades) before scaling capital. **Add to S29A scope.**

3. **Alerting for critical failures:** Before live trading, the system needs out-of-band notifications (push to iOS) on critical events: order failures, API disconnects, large position swings. **Existing notification infrastructure can handle this — wire it in S29A.**

### Reconciliation

Both models converge strongly on APPROVE WITH CONDITIONS. The plan is well-designed, follows proven patterns, and serves a clear financial goal. The main differences are around operational maturity (Gemini wants more guardrails before live capital) and scope (Gemini flags corporate actions as a gap). Both are valid additions.

## @hestia-critic: Adversarial Strategic Critique

The critic challenged the plan's sequencing and surfaced one architectural gap missed by all other reviewers.

### Novel Findings

1. **`get_candles()` is NOT in the ABC.** `AbstractExchangeAdapter` has 11 methods (connect, disconnect, place_order, cancel_order, get_order, get_open_orders, get_balances, get_ticker, get_order_book + 3 properties). There is no `get_candles()`. The BotRunner fetches candles through a Coinbase-specific data feed path, not through the adapter. Adding Alpaca means either building a parallel data path or extending the ABC with `get_candles()`. **This is structural work not accounted for in the plan.** Add 3-4h to S28B estimate.

2. **Two unproven strategies enter production simultaneously.** Bollinger Breakout and Signal DCA are both new in S28A. Neither has live trading history. Running them alongside a Coinbase deployment still in its first weeks of real capital creates a system with zero validated strategies when Alpaca integration begins.

3. **Signal DCA "never sells" creates an orphaned position.** The strategy is accumulation-only — it bypasses sell logic entirely. The risk manager's drawdown circuit breakers are designed for active trading. A pure-accumulation strategy creates a position that the reconciliation loop must track indefinitely with no exit trigger.

4. **$100K migration creates motivated reasoning pressure.** Building Alpaca infrastructure creates an implicit commitment that makes it psychologically harder to answer "not yet" when evaluating whether to move Fidelity capital.

### Critic's Counter-Plan: "Coinbase Confidence Sprint"

The critic argues Sprint 28 should not exist in its current form. Instead:
- Run real capital on Coinbase for 30+ days with documented P&L
- Backtest Bollinger and Signal DCA exhaustively on 2yr BTC data
- Gate: "Proceed to Alpaca only if Coinbase live Sharpe > 0.8 over 90 days"

### Assessment of Critic's Position

The `get_candles()` gap is a **valid architectural finding** — add it to S28B scope. The sequencing concern is **partially valid** — but the S28B read-only constraint already addresses it. No equity orders are placed until S29A, which is gated on paper soak results. The 90-day Coinbase gate is too conservative given that (a) the Alpaca account approval takes days, (b) S28B read-only has zero financial risk, and (c) the infrastructure work is valuable regardless of crypto performance.

**Adopted from critic:** Add `get_candles()` to `AbstractExchangeAdapter` ABC as part of S28B. Add 3-4h to estimate.
**Not adopted:** 90-day Coinbase gate before any Alpaca work. Read-only integration has no financial risk and the infrastructure is needed regardless.

---

## Conditions for Approval

**APPROVE WITH CONDITIONS:**

1. **Resequence: S28B before S28A.** The Alpaca integration is the critical path. If time is limited, S28A (crypto strategies) can be deferred. This is a sequencing change, not a scope cut.

2. **Add corporate actions handling to S28B.** The AlpacaAdapter must handle stock splits and dividend notifications from the outset. Ignoring this creates accounting errors that compound over time.

3. **Formalize capital gates for S29A.** The graduated ramp must be automated:
   - Paper → $25: manual (sanity check)
   - $25 → $1K: Sharpe > 0.5, MaxDD < 20%, 30 days minimum
   - $1K → $5K: Sharpe > 1.0, MaxDD < 15%, 60 days minimum
   - $5K → $25K+: Sharpe > 1.0, MaxDD < 10%, positive net profit, 90 days minimum

4. **Wire trading alerts before live orders (S29A).** Push notifications to iOS on: order fill errors, API disconnects, circuit breaker triggers, PDT warning (2/3 day trades used).

5. **Equity backtesting before paper soak.** Run Signal DCA against 1-year SPY historical data before starting Alpaca paper soak. Validates strategy logic independent of paper fill assumptions.

6. **Add `get_candles()` to `AbstractExchangeAdapter` ABC** (@hestia-critic finding). The current ABC has no candle-fetching method — the BotRunner uses a Coinbase-specific data path. Extend the ABC so all adapters provide candles through a unified interface. Add ~3-4h to S28B.

7. **Revised S28B estimate: ~24h** (was 20h). Additional scope: corporate actions handling (+2h) and `get_candles()` ABC extension (+3h), offset by reusing existing patterns.

---

*Report generated by /second-opinion — Claude Opus 4.6 (internal audit, 9 phases) + Gemini 2.5 Pro (cross-model validation) + @hestia-critic (adversarial strategic critique, codebase-grounded)*
