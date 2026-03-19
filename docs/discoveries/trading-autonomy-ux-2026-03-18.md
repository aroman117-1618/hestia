# Discovery Report: Trading Autonomy UX

**Date:** 2026-03-18
**Confidence:** High
**Decision:** Trading should be controlled primarily through chat tools with a minimal visual dashboard for at-a-glance status. Natural language is the primary control plane; UI is the monitoring plane.

## Hypothesis

Trading autonomy can be fully controlled through Hestia's existing chat + tool infrastructure (chat tools, proactive briefings, bump notifications) without requiring a dedicated trading dashboard, making it the most natural and lowest-friction interface for a single-user system.

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Proven chat tool pattern (20 Apple + 5 Health + Investigation tools already work this way). Council intent classification handles tool routing. Proactive briefing system already aggregates calendar/health/tasks -- trading is another data source. Notification relay (bumps) already handles alerts with routing logic. Single-user system means no multi-tenant complexity. BotOrchestrator + RiskManager + kill switch already exist as backend primitives. | **Weaknesses:** `TOOL_TRIGGER_KEYWORDS` needs trading keywords added. No trading tools exist yet -- must be built from scratch. Kill switch via chat has higher latency than a dedicated button (~200ms tool call vs instant tap). Current briefing generator has no trading data source. Council SLM (qwen2.5:0.5b) may need fine-tuning to classify trading intents correctly. |
| **External** | **Opportunities:** Industry trend toward conversational trading (Nansen AI, PionexGPT, MiDash all moving this direction). Chat-first UX eliminates need for complex trading dashboards -- saves 2-3 sprints of iOS/macOS UI work. Natural language enables complex compound commands ("pause all grid bots and show me why the drawdown breaker triggered"). Proactive briefing integration creates the "Jarvis trading desk" experience. | **Threats:** Ambiguous natural language commands near real money (e.g., "stop everything" -- kill switch or just pause bots?). Latency-sensitive operations (kill switch) need a fast path that bypasses full LLM pipeline. Chat tool errors near money are higher-stakes than calendar tool errors. Over-reliance on chat means no visual monitoring when you're not actively chatting. |

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | **Chat tools for trading control** (8-10 tools covering bot CRUD, risk status, kill switch, portfolio overview). **Briefing integration** (trading P&L section in daily briefing). **Bump notifications for alerts** (circuit breaker triggers, daily P&L summary, kill switch events). **TOOL_TRIGGER_KEYWORDS expansion** (add trading vocabulary). | **Kill switch confirmation UX** (double-confirm for deactivate, instant for activate). **Trading keyword additions to council** (ensure intent classification routes correctly). |
| **Low Priority** | **Minimal dashboard view** (portfolio value + active bots + risk status -- read-only, no controls). **SSE streaming to dashboard** (already built in trading routes, just needs UI consumer). | **Full trading dashboard with charts** (defer to Sprint 28+). **Voice-first trading commands** (nice-to-have, not needed for single-user). |

## Argue (Best Case)

**1. The pattern already works.** Hestia has 25+ chat tools across Apple, Health, and Investigation domains. The tool registration pattern (`models.py` + `tools.py` + `register_X_tools()`) is battle-tested. Adding trading tools follows the exact same pattern. Zero architectural risk.

**2. Natural language is strictly more expressive than UI for trading control.** Consider:
- "Start a new grid bot on ETH-USD with $200 and 10% grid spacing" -- one sentence vs. 5+ form fields
- "Pause all bots until tomorrow morning" -- one sentence vs. navigating to each bot and setting timers
- "What's my P&L this week by strategy?" -- one sentence vs. building a filtered dashboard view
- "Why did the drawdown breaker trigger?" -- one sentence vs. navigating to risk status and interpreting raw numbers

**3. Proactive briefing integration is a natural fit.** The `BriefingGenerator.generate()` already gathers data from 5 sources in parallel via `asyncio.gather()`. Adding `_get_trading_data()` as a 6th source is trivial:
```python
# In briefing.py generate():
trading_task = self._get_trading_data()  # Daily P&L, active bots, risk status
```
This creates the "morning trading desk briefing" experience with zero additional UI.

**4. Bump notifications handle the alert use case perfectly.** Circuit breaker triggers, kill switch activations, and daily P&L summaries map directly to the existing `NotificationManager.create_bump()` API. The 5-check routing chain (rate limit, cooldown, quiet hours, Focus mode, idle detection) already handles all the edge cases.

**5. Industry is moving this direction.** Nansen AI (built on Claude), PionexGPT, MiDash, ChainGPT, and Interactive Brokers' IBOT all use conversational interfaces for trading. The trend is clear: chat-first with optional visual dashboards, not dashboard-first with optional chat.

**6. Massive development savings.** A full trading dashboard (Sprint 26 original scope) requires: iOS TradingView, macOS TradingView, SSE consumer, chart library integration, state management, real-time updates. That's 15-20h of UI work. Chat tools + briefing integration is 6-8h. Savings: 50-60%.

## Refute (Devil's Advocate)

**1. Kill switch latency is a real concern.** The chat pipeline: user types "kill switch" -> council classifies intent (~100ms) -> tool call detected -> tool executed (~50ms) -> response rendered. Total: ~300-500ms. A dedicated UI button: tap -> API call (~50ms). The 250-450ms difference matters during a flash crash.

**Mitigation:** Register "kill switch" as a hardcoded fast-path in the council coordinator (like the `TOOL_TRIGGER_KEYWORDS` bypass), and also expose a single red button in the minimal dashboard. Both paths call the same `manager.activate_kill_switch()`.

**2. No ambient monitoring.** When you're not actively chatting with Hestia, you have zero visibility into trading activity. A dashboard provides passive monitoring -- you can glance at it.

**Mitigation:** This is what bump notifications solve. Circuit breaker triggers, unusual P&L, and daily summaries push to you proactively. You don't need to be watching. Additionally, the minimal dashboard (portfolio value + active bots + risk LED) provides the ambient glance.

**3. Ambiguous commands near real money.** "Stop trading" -- does that mean kill switch (emergency halt, cancel all orders) or pause bots (orderly shutdown, keep positions)? "Sell everything" -- sell all positions or liquidate the entire portfolio including cash?

**Mitigation:** Trading tools must implement a confirmation tier system:
- **Instant (no confirmation):** Read-only queries (portfolio, P&L, risk status)
- **Soft confirm:** Bot start/stop, strategy changes (Hestia confirms intent before executing)
- **Hard confirm:** Kill switch deactivation, capital allocation changes, position liquidation (explicit "yes" required)

This is analogous to the existing `requires_approval` field on `Tool` and the CommGate pattern.

**4. Complex queries may exceed local LLM capability.** "Compare my grid bot performance to mean reversion over the last 30 days, normalized for market conditions" -- this requires data aggregation, calculation, and narrative synthesis that qwen3.5:9b may not handle well.

**Mitigation:** Route complex trading analysis to Artemis (deepseek-r1:14b via agent orchestrator) or cloud. The `AgentRouter` already handles this via confidence gating.

**5. Discovery problem.** New users won't know what trading tools are available. A dashboard has visual affordances; chat has none.

**Mitigation:** Single-user system. Andrew knows the tools. Additionally, `/tools` command already lists available tools, and the briefing can include "You have 3 active bots. Say 'trading status' for details."

## Third-Party Evidence

**Interactive Brokers IBOT:** Production NLP trading interface serving millions of retail traders. Supports order placement, portfolio queries, and market data via natural language. Validates the chat-first approach at scale.

**Nansen AI:** Built on Claude/Anthropic, launched 2025. Chat interface for on-chain analysis with trading execution planned. Raised $75M. Validates the AI-assistant-as-trading-interface thesis.

**PionexGPT:** Natural language strategy creation. Users describe strategies in plain English, system generates and deploys bots. Validates that even strategy configuration (not just queries) works via NLP.

**ChainGPT Trading Assistant:** AI-powered trading recommendations via chat. Validates the advisory + execution model.

**Common failure pattern across all:** Every platform that went chat-only eventually added a minimal visual dashboard for ambient monitoring. The sweet spot is chat as primary control + minimal visual status.

## Recommendation

**Implement a 3-layer trading UX architecture:**

### Layer 1: Chat Tools (Primary Control Plane) -- Sprint 26A

Register 8-10 trading tools following the existing `health/tools.py` pattern:

| Tool | Category | Confirmation |
|------|----------|-------------|
| `trading_status` | Read | None |
| `trading_portfolio` | Read | None |
| `trading_bot_list` | Read | None |
| `trading_bot_create` | Write | Soft (confirm params before creating) |
| `trading_bot_start` | Write | Soft |
| `trading_bot_stop` | Write | Soft |
| `trading_kill_switch` | Critical | None for activate, Hard for deactivate |
| `trading_risk_status` | Read | None |
| `trading_daily_summary` | Read | None |
| `trading_watchlist` | Read/Write | None for read, Soft for add |

Add trading keywords to `TOOL_TRIGGER_KEYWORDS`:
```python
# Trading
"trading", "trade", "bot", "bots", "portfolio", "kill", "switch",
"grid", "strategy", "position", "crypto", "bitcoin", "eth",
```

### Layer 2: Proactive Integration (Push Monitoring) -- Sprint 26B

**Briefing integration:**
- Add `_get_trading_data()` to `BriefingGenerator` (daily P&L, active bot count, risk status, overnight events)
- New `BriefingSection` type: `"trading"` with structured data for UI rendering

**Bump notifications:**
- Circuit breaker triggered -> immediate bump (high priority)
- Kill switch activated -> immediate bump (critical priority)
- Daily P&L summary -> scheduled bump (normal priority, end of trading day)
- Unusual activity detected -> bump (medium priority)

### Layer 3: Minimal Dashboard (Ambient Monitoring) -- Sprint 26C

A single-screen read-only view in Command Center (not a new tab):
- Portfolio value + daily P&L (one line)
- Active bots with status LEDs (green/yellow/red)
- Risk status summary (all-clear or breaker name)
- Kill switch toggle (the ONE visual control -- instant, no chat pipeline)

This is 20-30 lines of SwiftUI, not a full trading view. It consumes the existing `/v1/trading/portfolio` and `/v1/trading/risk/status` endpoints.

### Implementation Order

1. **Sprint 26A (4h):** Trading chat tools + TOOL_TRIGGER_KEYWORDS + council integration
2. **Sprint 26B (3h):** Briefing trading section + bump notification triggers
3. **Sprint 26C (2h):** Minimal dashboard card in Command Center

**Total: ~9h vs. original Sprint 26 estimate of 15-20h for full dashboard.**

### What Would Change This Recommendation

- **Multi-user system:** If Hestia ever serves more than Andrew, a full dashboard becomes necessary for user onboarding and discovery
- **High-frequency trading:** If strategies move to sub-second execution, chat latency is unacceptable for any control action
- **Regulatory requirements:** If reporting/audit needs grow, a dedicated trading view with export capabilities would be needed
- **Andrew says "I want charts":** Personal preference overrides architectural arguments. The SSE streaming infrastructure already exists.

## Final Critiques

### Skeptic: "Why won't this work?"

**Challenge:** "Chat tools add latency to every trading action. In a market crash, 500ms matters. You're optimizing for elegance over safety."

**Response:** The kill switch is the only latency-sensitive action, and it gets a dedicated UI button (Layer 3). Every other trading action (create bot, start bot, check P&L) is not time-sensitive -- bots execute autonomously. You're not manually trading through chat; you're managing autonomous agents. The agents trade in milliseconds regardless of how you configure them.

### Pragmatist: "Is the effort worth it?"

**Challenge:** "You're building 3 layers when a simple dashboard would be one thing done well."

**Response:** Layer 1 (chat tools) is 4h and follows an existing pattern with zero architectural novelty. Layer 2 (briefing) is 3h and adds one data source to an existing system. Layer 3 (minimal dashboard) is 2h of SwiftUI. Total: 9h. A full dashboard is 15-20h. The 3-layer approach costs less AND delivers a better UX because it integrates trading into the existing Hestia experience rather than creating an isolated silo. Trading isn't a separate app -- it's another capability of your AI assistant.

### Long-Term Thinker: "What happens in 6 months?"

**Challenge:** "Chat tools are fine now. But as strategies multiply (Sprint 27-29) and you add ML signals (Sprint 29), the number of things you want to monitor grows. Won't you eventually need a real dashboard?"

**Response:** Yes, probably. The architecture explicitly accommodates this. The SSE streaming endpoint already exists (`/v1/trading/stream`). The minimal dashboard card (Layer 3) can grow into a full tab when the complexity justifies it. But building the full tab now, before strategies are live, means building UI for features that don't exist yet. Start minimal, grow as needed. The chat tools and briefing integration will remain valuable even if a full dashboard is added later -- they're complementary, not competing.

## Open Questions

1. **Kill switch voice activation:** Should "Hestia, kill switch" via voice (Sprint 2 voice pipeline) bypass the normal tool chain entirely? Probably yes, but needs design.
2. **Trading tool trust tier:** Should CLI users (hestia-cli) have access to trading tools? The tool trust tier system (Sprint CLI-3) already supports per-device permissions. Trading tools should probably require `execute` tier.
3. **Backtest results in chat:** Should `trading_run_backtest` be a chat tool? Backtests take 5-30 seconds -- may need async execution with bump notification on completion rather than blocking the chat.
4. **Strategy parameter tuning via chat:** "Make my grid bot more aggressive" is natural language but requires mapping to concrete config changes. Worth a dedicated tool or better handled by Hestia interpreting and suggesting specific changes?

---

*Research conducted using codebase analysis and external market research. External sources: Nansen AI, PionexGPT, MiDash, Interactive Brokers IBOT, ChainGPT, industry analysis from CoinBureau, Devexperts, and Digiqt.*
