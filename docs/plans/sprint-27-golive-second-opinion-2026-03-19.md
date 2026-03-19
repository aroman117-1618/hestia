# Second Opinion: Sprint 27 Go-Live Session Plan

**Date:** 2026-03-19
**Models:** Claude Opus 4.6 (internal, 9 phases) + Gemini 2.5 Pro (external cross-validation)
**Verdict:** APPROVE WITH CONDITIONS

## Capital Context

$250 is the **starting allocation**, not the ceiling. Andrew has $1K-$25K+ available to deploy based on performance. This shifts the risk calculus: what's acceptable at $250 becomes unacceptable at $10K. The system must be built to institutional-grade safety standards from day one, with a gradual capital deployment ladder gated on clean performance windows.

## Plan Summary

Take Hestia's autonomous crypto trading module from "code complete" (Sprints 21-26) to "paper soak running, then live with real money on Coinbase." The plan covers dependency lockdown, integration testing, paper soak launch, operational prep, and handoff. Target: Grid Trading + Mean Reversion on BTC-USD with $250 starting capital (scaling to $10K+), Quarter-Kelly sizing, 8-layer risk pipeline.

---

## Scale Assessment

| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|----------------|-------------------|
| Single user (Andrew) | Yes | N/A | N/A |
| Family (2-5) | No | Single exchange account, shared capital, no per-user bot isolation | Medium |
| Community | No | Regulatory (managing others' funds requires licensing) | Prohibitive |

**Assessment**: Single-user is the correct scope. No scale debt being created — trading is inherently personal.

---

## Front-Line Engineering Review

- **Feasibility:** YES — code is built, this is validation + hardening
- **Hidden prerequisites:**
  1. Python 3.9 venv vs 3.12 target — trading deps may behave differently
  2. Mac Mini sleep/wake — BotRunner needs `caffeinate` or wake-on-LAN for 72h soak
  3. Coinbase public API rate limits (10 req/sec) — multiple bots could hit limits
- **Complexity underestimate:** Plan says 1.5h for integration tests, but CRITICAL findings (atomic transactions, reconciliation) need *fixes* first, then tests. Realistically 3-4h for fix + test.
- **Testing gaps in the plan:**
  - Flash crash scenario (BTC -20% in 5 min)
  - Concurrent bot signal conflict (two bots buy simultaneously)
  - Server restart mid-trade

---

## Architecture Review

- **Fit:** Excellent. Manager pattern, singleton factory, clean separation
- **Data model CRITICAL issue:** Trade + tax lot writes are NOT atomic. In a financial system, this is unacceptable.
- **Integration risk:** Low — trading module is well-isolated (own DB, own exchange, own event bus)
- **Dependency risk:** 4 unlocked Python packages. Fresh deploy fails.

---

## Product Review

- **User value:** HIGH — direct revenue generation ($60-125/year at 25-50% annual)
- **Opportunity cost:** Not building macOS auto-update or Visual Workflow Orchestrator. Acceptable — trading generates revenue.
- **Edge cases:**
  - Coinbase scheduled maintenance (~monthly)
  - Coinbase fraud detection on automated patterns
  - API key rotation (90-day expiry?)

---

## UX Review

- **Trading tab:** Adequate — enable/disable toggle, Decision Feed, first-run confirmation
- **Gap:** No "pause" state (stop signals but keep positions). Not blocking for Go-Live.

---

## Infrastructure Review

- **Deployment impact:** Config change only (`trading.yaml: mode → coinbase`), server restart
- **Rollback:** Kill switch → cancel orders → flip config → restart. Clean.
- **Resource impact:** Minimal on M1 (one async task + burst pandas computation). Acceptable.
- **Missing:** No DB backup strategy for trading database. Power loss could corrupt.
- **Missing:** No `caffeinate` for 72h soak — Mac Mini may sleep.

---

## Executive Verdicts

- **CISO:** APPROVE WITH CONDITIONS — Fix atomic transaction gap and reconciliation-triggers-kill-switch before live trading. API key scoping (no withdrawal) is correct.
- **CTO:** APPROVE WITH CONDITIONS — Lock dependencies, fix dead circuit breakers, add idempotency to Manager↔Orchestrator sequence. REST polling is fine for 1h candle strategies.
- **CPO:** APPROVE — Revenue-generating, risk capped at $250, paper soak is the right approach.

---

## Final Critiques

1. **Most likely failure:** Coinbase public API rate limiting during paper soak. DataLoader fetches up to 30 chunks per poll, multiple bots would exceed 10 req/sec. **Mitigation:** Rate-limit candle fetches with backoff.

2. **Critical assumption:** "Grid + Mean Reversion will generate signals within 72h on BTC-USD." At current volatility, Grid should trigger. Mean Reversion (RSI-7 hitting 20/80) may not. **Validation:** Check historical 72h BTC windows.

3. **Half-time cut list:** If only 1.5h available: (1) Atomic transaction fix, (2) Dependency lockfile. Cut: integration tests, ADR, monitoring setup. **This reveals true priorities: safety fixes > deps > tests > docs.**

---

## Cross-Model Validation (Gemini 2.5 Pro)

### Gemini's Independent Assessment

Gemini issued a **REJECT** verdict. Key arguments:

1. **"Don't paper-soak a system with known critical flaws"** — Paper soak is for finding unknown edge cases, not watching known bugs play out. Fix first, then soak.
2. **"Grid Trading is incompatible with 15-min REST polling"** — Claims Grid needs sub-second fill detection to re-place orders.
3. **"Active reconciliation, not passive"** — Divergence should trigger kill switch, not just log a warning.
4. **"Shadow mode before live"** — Run the full pipeline with read-only exchange access before committing capital.
5. **"Implement all dead circuit breakers"** — VOLATILITY/CONNECTIVITY/SINGLE_TRADE should work, not just exist.

### Gemini's Novel Insights (not in internal audit)

| Finding | Assessment |
|---------|-----------|
| **Resource contention** — Ollama inference could starve BotRunner of CPU | Valid. Easy to mitigate: trading polls run in 100ms bursts every 15 min, unlikely to collide with inference. But worth monitoring. |
| **Clock drift** — System clock vs exchange time could cause wrong candle fetch | Valid but minor. macOS runs NTP by default. Worth adding a timestamp sanity check on fetched candles. |
| **SQLite corruption on power loss** — WAL mode helps but isn't invincible | Valid. Should add a daily DB backup to the operational checklist. |
| **Config integrity** — Dev config could accidentally trigger live trades | Valid. Could add a startup assertion: `if mode == "live": assert keychain_has_key(...)`. |
| **Cancel-Only mode** — During exchange maintenance, cancel existing orders but don't place new ones | Good idea. Could be a BotRunner state (MAINTENANCE). Defer to post-Go-Live. |

### Where Both Models Agree

- **Atomic transaction fix is CRITICAL** — Both agree this must be fixed before live trading
- **Reconciliation should trigger kill switch** — Passive warning is inadequate for a financial system
- **Dead circuit breakers should be cleaned up** — Either implement or remove
- **Dependencies must be locked** — Deploy blocker
- **REST polling is technically functional** for the current strategies (though Gemini argues it's insufficient for Grid)

### Where Models Diverge

| Topic | Claude's View | Gemini's View | Resolution |
|-------|--------------|---------------|------------|
| **WebSocket for Grid Trading** | Defer — REST polling + 60s reconciliation is adequate for 1h candle Grid strategy | CRITICAL — Grid is "non-functional" without sub-second fills | **Claude is right for $250 launch.** Grid on 1h candles doesn't need sub-second fills. But Gemini's concern becomes valid at scale: at $10K with 25% position, a 15-min fill detection delay costs ~$375 in potential slippage. **WebSocket should be wired before scaling past $2.5K (Sprint 28).** |
| **Shadow mode before live** | Skip — paper soak + config flip is sufficient for $250 | Required — read-only exchange → paper execution as intermediate step | **Gemini is right in spirit.** Shadow mode should be implemented before scaling past $2.5K. For $250 launch, paper soak + gradual capital deployment is sufficient. |
| **Soak duration** | 72h paper soak | 1 week shadow + 72h full paper (9+ days) | **Compromise: 72h paper soak for $250 launch. Before each capital gate ($1K, $2.5K, $5K, $10K), require a clean 2-week run at the current level.** |
| **Overall verdict** | APPROVE WITH CONDITIONS | REJECT | **See synthesis below** |

### Synthesis

Gemini's REJECT is principled and, given Andrew's capital scaling intent ($10K-$25K+), more justified than it initially appeared. The critical safety findings (atomic transactions, active reconciliation) are non-negotiable. Gemini's scope escalation (WebSocket, shadow mode, secondary price feeds) — initially dismissed as over-engineering for $250 — becomes load-bearing infrastructure as capital scales.

**The right approach**: Fix all CRITICAL safety issues now (atomic transactions, active reconciliation, dependency lockfile). Launch paper soak at $250. But build in **capital deployment gates** that require specific hardening milestones before scaling:

| Capital Gate | Prerequisite |
|-------------|-------------|
| $250 → $1K | 2-week clean run, all MUST DO items complete |
| $1K → $2.5K | Secondary price feed (CoinGecko), shadow mode validation |
| $2.5K → $5K | WebSocket integration, partial fill handling |
| $5K → $10K+ | Full strategy diversification (3+ strategies), multi-exchange capability |

---

## Conditions for Approval

The original plan is **APPROVED WITH CONDITIONS**. The following must be added:

### MUST DO (before paper soak — blocking)

1. **Atomic trade recording** — Wrap `create_tax_lot()` + `record_trade()` in a single SQLite transaction. If either fails, both roll back. (~30 min)

2. **Active reconciliation** — When `position_tracker.reconcile()` detects divergence above threshold, trigger kill switch (not just log). Add CRITICAL alert via event bus + Discord. (~30 min)

3. **Lock dependencies** — Add `pandas`, `ta`, `coinbase-advanced-py`, `aiohttp`, `vectorbt` to `requirements.in` and recompile. (~15 min)

4. **Manager↔Orchestrator idempotency** — On server startup, `resume_running_bots()` should verify each RUNNING bot has an active runner. If not, either restart the runner or set bot status to STOPPED. (~20 min)

### SHOULD DO (before live trading — not blocking paper soak)

5. **Dead circuit breaker cleanup** — Remove VOLATILITY/CONNECTIVITY/SINGLE_TRADE from config if unused, or implement them. Dead code in a safety system is a liability. (~30 min)

6. **Price validation staleness** — Add timestamp to secondary prices, reject if > 5 min stale. Even without CoinGecko, validate that the primary price isn't stale (last candle timestamp > 2h ago = stale). (~20 min)

7. **Partial fill handling** — Map Coinbase order states (pending/partial/filled/canceled) to BotRunner state transitions. At minimum, log partial fills and update position proportionally. (~45 min)

8. **Mac Mini soak prep** — Run `caffeinate -d` during soak test. Add daily DB backup to cron. (~10 min)

### REQUIRED BEFORE $1K (Sprint 28 — Capital Gate 1)

9. Price validation staleness check (timestamp on prices, reject if > 5 min stale)
10. Partial fill state machine (pending/partial/filled/canceled/rejected)
11. Daily DB backup to iCloud or external storage

### REQUIRED BEFORE $2.5K (Sprint 28-29 — Capital Gate 2)

12. CoinGecko secondary price feed (hard-fail if unavailable)
13. Shadow mode deployment (live signals → paper execution)
14. WebSocket integration into BotRunner (fill detection + candle streaming)

### CAN DEFER (Sprint 29-30 — Capital Gate 3+)

15. Cancel-Only maintenance mode
16. Pause state in macOS UI
17. Multi-exchange (CCXT/Kraken)
18. AI sentiment overlay

---

## Revised Session Plan

Given the conditions above, the session plan should be restructured:

### Phase 1: Safety Fixes (~1.5h)
1. Atomic trade recording (transaction wrapper)
2. Active reconciliation (divergence → kill switch)
3. Manager↔Orchestrator idempotency
4. Dead circuit breaker cleanup

### Phase 2: Dependencies (~15 min)
5. Lock all trading deps in requirements.in
6. Recompile lockfile
7. Verify imports

### Phase 3: Integration Tests (~1.5h)
8. Full trading tick (signal → risk → execute → record → event)
9. Circuit breaker cascade (drawdown → kill switch)
10. Error recovery (3 crashes → ERROR state)
11. Atomic transaction rollback (DB crash mid-trade)
12. Active reconciliation trigger (divergence → kill switch)

### Phase 4: Paper Soak Launch (~30 min)
13. Start server on Mac Mini with paper mode
14. `caffeinate -d` for uninterrupted soak
15. Create Grid bot (BTC-USD, $250)
16. Enable via chat tool or API
17. Verify Decision Feed + reconciliation loop
18. Set up Discord alert monitoring

### Phase 5: Review & Handoff (~30 min)
19. @hestia-reviewer on all changed files
20. Update SPRINT.md (S27 → IN PROGRESS)
21. Session handoff with soak monitoring checklist
22. ADR for Go-Live architecture decisions

**Total: ~4h** (vs original 3h — the safety fixes add ~1h but are non-negotiable)

---

## Post-Soak Go-Live Checklist (next session, after 72h clean soak)

- [ ] All paper trades recorded with correct tax lots
- [ ] No reconciliation divergences detected
- [ ] Decision Feed shows consistent signal generation
- [ ] No ERROR state transitions (all recoveries clean)
- [ ] Kill switch tested manually (activate → verify halt → deactivate)
- [ ] Verify Coinbase API keys in Keychain on Mac Mini
- [ ] Verify API key scope: "Consumer Default Spot" (no withdrawal)
- [ ] Flip `trading.yaml: mode → coinbase`
- [ ] Deploy to Mac Mini
- [ ] Start with $25 (10%) for first 48h
- [ ] Escalate to $125 (50%) after 48h clean
- [ ] Full $250 after 1 week clean
- [ ] Monitor Discord alerts daily for 2 weeks
- [ ] **Capital Gate 1 ($1K):** 2-week clean run at $250 + staleness checks + partial fills + DB backups
- [ ] **Capital Gate 2 ($2.5K):** CoinGecko feed + shadow mode validation + WebSocket wiring
- [ ] **Capital Gate 3 ($5K+):** Strategy diversification + multi-exchange capability
