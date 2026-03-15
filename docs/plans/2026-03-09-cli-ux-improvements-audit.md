# Plan Audit: CLI UX Improvements Sprint

**Date:** 2026-03-09
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary

Eight improvements across 4 tiers to transform the Hestia CLI from a functional chat wrapper into a coding-first power tool. Fixes two broken paths (raw JSON tool calls, 4-minute response times), adds missing feedback (tool execution visibility, initial text suppression), introduces differentiation features (insight callouts, model/routing visibility), and polishes the command interface (interactive `/config`, `/tools` browser, command palette).

---

## Scale Assessment

| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|----------------|-------------------|
| Single user | Yes | None — all changes are client-side or single-device server | N/A |
| Family (2-5) | Yes | Insight callouts are user-agnostic (no personalization). Cloud routing preferences are server-global not per-device. | Low — add device_id scoping to routing preferences |
| Community | Partial | Slash command registry is in-process (not extensible at runtime). Config is local YAML (no server-synced preferences). | Medium — would need server-side config sync |

**Assessment:** The plan is appropriately scoped for single-user. No decisions here would create expensive migration pain at family scale. The cloud routing preference being server-global is a minor concern — if Andrew's phone triggers `enabled_smart` but the CLI wants `enabled_full` for coding, they'd conflict. Consider device-scoped routing preference in the future (not now).

---

## Front-Line Engineering Review

### Feasibility

All 8 items are buildable as described. The hardest is #4 (initial text suppression) because the streaming architecture yields tokens before tool detection — there is **no mechanism to unsend tokens**. This requires a design decision (see Architecture section).

### Hidden Prerequisites

| Item | Prerequisite | Status |
|------|-------------|--------|
| #2 (Cloud routing) | `chat_stream()` needs `force_tier` parameter | Missing — ~10 lines to add |
| #7 (Insight callouts) | New `INSIGHT` event type in WebSocket protocol | Missing — needs backend + CLI |
| #8 (Command palette) | `prompt_toolkit` completion framework | Available — `NestedCompleter` exists |
| #1 (JSON detection) | `_looks_like_tool_call()` needs `"name":` substring check | Missing — 1 line fix |

### Complexity Estimates

| Item | Estimated LOC | Risk | Notes |
|------|--------------|------|-------|
| #1 JSON detection | 5–10 | Low | Add `"name":` check to `_looks_like_tool_call()` |
| #2 Cloud routing | 30–40 | Medium | `force_tier` on `chat_stream()` + synthesis routing logic |
| #3 Tool feedback | 15–20 | Low | Renderer enhancement — new status line |
| #4 Text suppression | 40–60 | **High** | Architectural decision required (see below) |
| #5 Model visibility | 20–30 | Low | Enhance `done` event rendering |
| #6 Tool execution insight | 20–30 | Low | Enhance `tool_result` rendering |
| #7 Insight callouts | 60–80 | Medium | New event type + backend emission + renderer |
| #8 Command palette | 80–120 | Medium | Completer, interactive config, `/tools` command |

### Testing Strategy

- #1: Extend `TestTextPatternToolDetection` with JSON format variants
- #2: Mock `chat_stream` with `force_tier`, verify routing decision
- #3–#6: Renderer tests with `StringIO` capture (existing pattern)
- #7: New `TestInsightRendering` class + backend emission tests
- #8: Command handler tests (existing pattern) + completer tests

### Testing Gaps

- **Live display behavior**: Currently untested. The progressive markdown Live display can't be easily captured in StringIO tests. Risk: visual glitches in production that tests don't catch.
- **WebSocket protocol compatibility**: Adding `INSIGHT` event type means older CLI versions will silently drop it (safe) but won't benefit. No versioning concern.

---

## Architecture Review

### Critical Decision: Token Suppression (#4)

The streaming pipeline yields tokens **before** tool detection. This is by design (streaming UX requires immediate token emission). Four approaches exist:

| Approach | UX Quality | Complexity | Risk |
|----------|-----------|------------|------|
| **A: Buffer all tokens** until tool detection | No streaming feel | Low | Kills UX for ALL messages |
| **B: Client-side `clear` event** | Clean suppression | Medium | Protocol change, requires CLI to support cursor manipulation |
| **C: Visual separator** | "Explanation → Answer" flow | Low | Initial text visible but contextualized |
| **D: Token window** (buffer last 200 chars) | Partial suppression | High | Adds latency, complex edge cases |

**Recommendation: Approach C (visual separator).** Rationale:
- The initial text ("I'll read your note...") is actually *useful context* — it shows the user what the model decided to do
- A separator (`───── ⚙️ read_note("hestia") ─────`) clearly delineates "model reasoning" from "actual answer"
- Zero protocol changes, zero streaming latency impact
- Aligns with Claude Code's behavior (shows tool calls, then results)

**Rejected alternatives:**
- Approach A destroys streaming UX for the 80% of messages that don't involve tools
- Approach B requires WebSocket protocol changes and terminal cursor manipulation (ANSI escape sequences that may not work in all terminals)
- Approach D has nasty edge cases (what if the tool call spans the buffer boundary?)

### Data Model

No new database tables or migrations. All changes are:
- In-memory event handling (CLI renderer)
- Backend event emission (handler.py)
- Config YAML structure (additive — new keys with defaults)

### Integration Points

| Change | Files Touched | Breaking Risk |
|--------|--------------|---------------|
| #1 JSON detection | `handler.py` | None — additive regex |
| #2 Cloud routing | `client.py`, `handler.py` | None — optional parameter |
| #3 Tool feedback | `renderer.py` | None — new render path |
| #4 Visual separator | `renderer.py` | None — additive |
| #5 Model visibility | `renderer.py` | None — enhanced existing |
| #6 Tool insight | `renderer.py` | None — enhanced existing |
| #7 Insight callouts | `handler.py`, `models.py`, `renderer.py` | Low — new event type |
| #8 Command palette | `commands.py`, `repl.py`, `config.py` | Low — additive |

### API Consistency

No new API endpoints. The `INSIGHT` event is a WebSocket protocol addition (backward compatible — unknown events are silently dropped by existing clients).

---

## Product Review

### User Value Assessment

| Item | Value | Justification |
|------|-------|---------------|
| #1 JSON detection | **Critical** | Broken UX — user sees garbage text |
| #2 Cloud routing | **Critical** | 4-min response time makes CLI unusable for coding |
| #3 Tool feedback | **High** | Eliminates confusion during tool execution |
| #4 Visual separator | **Medium** | Polish — makes tool flow legible |
| #5 Model visibility | **High** | Transparency — essential for trust and debugging |
| #6 Tool insight | **Medium** | Nice-to-have — compounds with #7 |
| #7 Insight callouts | **High** | Core differentiator — maps to 70% teach-as-we-build |
| #8 Command palette | **High** | Coding-first UX standard — discoverability + control |

### Edge Cases

| Scenario | Handling |
|----------|---------|
| Cloud provider not configured | Fall back to local silently (existing behavior) |
| Cloud API key expired | Existing error handling surfaces warning |
| Model outputs tool call in unknown format | Existing fallback: show text as-is (degraded but not broken) |
| Empty tool result | Show insight: "Tool returned no data" |
| `/tools` when server disconnected | Show cached tool list or "Connect first" message |
| `/config` with malformed YAML | **GAP** — currently crashes on next load. Add validation on save. |

### Scope Assessment

**Right-sized as a single sprint.** Individual items are 5–120 LOC each. Total estimated: ~300–400 LOC across 6–8 files. Dependencies between items (e.g., #3 and #6 share renderer code, #2 and #5 share routing visibility) make them more efficient to implement together.

### Opportunity Cost

Building this instead of: Sprint 8 (Research & Graph), iOS improvements, or new backend features. **Justified** — a broken CLI blocks the coding-first workflow that Andrew will use daily. Backend features matter less if the primary interface is unusable.

---

## UX Review

### CLI Design Language

The existing CLI uses:
- Rich Console for rendering (Markdown, Panels, Text)
- Agent-specific colors (Tia amber, Olly teal, Mira navy)
- `⟳` spinner for status, `🔥` fire for thinking animation
- Dim text for metadata, bold for headers

**New elements should match:**
- Insight callouts: Use a bordered Panel with agent color accent
- Tool separator: Use Rule with emoji + tool name
- Model indicator: Dim text in metrics footer (consistent with current `done` rendering)
- Command palette: Use prompt_toolkit completion (consistent with existing REPL)

### Proposed Visual Language

**Tool execution separator** (#4):
```
Tia:
I'll read your note for you.

────── ⚙️ read_note("hestia") ──────

Here's my analysis of the CLI section...
```

**Insight callout** (#7):
```
┌─ 💡 Insight ──────────────────────────────┐
│ Routed to cloud (Anthropic) — local model  │
│ generating at 0.6 tok/s, below 8.0         │
│ threshold. Use /config to change routing.  │
└────────────────────────────────────────────┘
```

**Model indicator in metrics** (#5):
```
  tia · 145 tokens · 3.2s · claude-3-haiku (cloud) ☁️
  tia · 132 tokens · 241.3s · qwen2.5:7b (local) 💻
```

**Command palette** (#8):
```
[@tia] > /
  /help     — Show available commands
  /mode     — Switch agent (tia/mira/olly)
  /tools    — Browse available tools
  /config   — Configure CLI preferences
  /trust    — View/set tool trust tiers
  /memory   — Search Hestia memory
  /session  — Manage sessions
  /status   — Server health info
  /clear    — Clear screen
  /exit     — Exit CLI
```

### Accessibility

- All new visual elements use text, not just emoji (screen reader compatible)
- Color is never the sole differentiator (always paired with text or emoji)
- `HESTIA_NO_EMOJI` and `HESTIA_NO_COLOR` already supported — extend to new elements

---

## Infrastructure Review

### Deployment Impact

- **Backend changes** (#1, #2, #7): Requires server restart after deploy
- **CLI changes** (#3–#8): Requires CLI reinstall (`pip install -e .`)
- **No database migrations**: All changes are in-memory or config-file based
- **No new dependencies**: Uses existing Rich, prompt_toolkit, YAML libraries

### Rollback Strategy

- All changes are additive (no removals, no schema changes)
- Git revert of any commit cleanly rolls back
- Unknown event types are silently dropped by older clients
- Config additions have defaults (old config files work unchanged)

### Resource Impact

- Insight events add ~200 bytes per relevant request to WebSocket traffic — negligible
- `force_tier` on cloud routing shifts compute from Mac Mini to cloud API — reduces local resource pressure (positive)
- Command palette completion is in-memory, no external lookups — negligible

---

## Executive Verdicts

### CISO: ACCEPTABLE ✅

No new credential handling, no new data exposure paths. Cloud routing preference is server-side (already exists). Insight events contain operational data (model name, routing reason) — not sensitive. Tool result visibility shows data the user already has access to. Config file remains local-only with existing permissions.

**One note:** Ensure insight events don't leak prompt content or tool arguments in logs. The current `sanitize_for_log()` pattern must be applied to any new log entries.

### CTO: APPROVE WITH CONDITIONS ⚠️

Architecture is sound. The visual separator approach (#4) is the right call — protocol changes for token suppression would be over-engineering. The `force_tier` addition to `chat_stream()` is clean and backward-compatible.

**Conditions:**
1. **#2 Cloud routing: Define the "known-slow" heuristic precisely.** The plan says "route synthesis to cloud when local is known-slow" but doesn't specify the trigger. Use the existing hardware adaptation state — if `hardware_adapted == True` (model was swapped due to slow tok/s), route synthesis to cloud. Don't invent a new heuristic.
2. **#7 Insights: Keep the backend emission minimal.** The handler should yield `{"type": "insight", "content": "..."}` — the message text should be constructed in the handler, not the renderer. The renderer just formats/displays. Don't create an insight "framework" — start with 3-4 hardcoded insight points and iterate.
3. **#8 Config validation:** Add YAML parse validation when `/config` returns from the editor. If invalid, warn and don't apply.

### CPO: APPROVE ✅

Priority ordering is correct. The broken items (#1, #2) are table-stakes. The differentiators (#7 insights, #8 commands) are high-leverage for the 70% teach-as-we-build philosophy. The visual separator (#4) is the pragmatic choice over the technically "cleaner" token suppression.

**Recommendation:** Ship #1 and #2 first as a hotfix (they're blocking daily use), then #3–#8 as a feature sprint. This ensures the CLI is usable immediately while the polish lands.

---

## Final Critiques

### 1. Most Likely Failure: Insight callouts become noise

**Risk:** If every request emits 2-3 insights, users will learn to ignore them. Claude Code's insights work because they're rare and specific.

**Mitigation:** Gate insights behind a verbosity preference (`/config` → `insight_level: auto|verbose|quiet`). Default to `auto`: show insights only on first occurrence of a pattern (first cloud fallback, first tool execution, first cache hit). After the user has seen it once, suppress unless `verbose`.

### 2. Critical Assumption: Cloud API is reliably available

**Assumption:** Routing synthesis to cloud in `enabled_smart` mode will solve the 4-minute response time. If the Anthropic API is down, rate-limited, or the key expired, synthesis falls back to the same slow local model.

**Validation:** The existing cloud health check (`/v1/cloud/providers` health endpoint) already validates API key and connectivity. Add a pre-flight check in the synthesis path: if cloud health is unhealthy, skip the `force_tier=CLOUD` and use local with a longer timeout. Log a warning insight: "Cloud unavailable — using local model (expect slower responses)."

### 3. Half-Time Cut List

If we had half the time, cut in this order (last cut = highest priority):

| Cut Order | Item | Why Cut |
|-----------|------|---------|
| Cut first | #8 Command palette | Polish — existing commands work, just not discoverable |
| Cut second | #6 Tool execution insight | Nice-to-have — #3 already provides basic feedback |
| Cut third | #4 Visual separator | Cosmetic — initial text leak is annoying but not blocking |
| Keep | #7 Insight callouts | Core differentiator — defines the product |
| Keep | #5 Model visibility | Transparency — essential for trust |
| Keep | #3 Tool feedback | Missing — confusing without it |
| Keep | #2 Cloud routing | Broken — 4-min responses are unusable |
| Keep | #1 JSON detection | Broken — garbage output |

**This reveals the true priority stack:** #1 → #2 → #3 → #5 → #7 → #4 → #6 → #8

---

## Conditions for Approval

1. **Define "known-slow" heuristic:** Use `hardware_adapted` flag from inference client, not a new measurement
2. **Insight gating:** Implement `auto` verbosity by default — don't emit every insight on every request
3. **Config validation:** Add YAML parse check when `/config` editor closes
4. **Ship in two phases:** Hotfix (#1, #2) first, feature sprint (#3–#8) second
5. **Test coverage:** Every new renderer method gets a StringIO capture test. Insight emission gets a handler test.

---

## Recommended Implementation Order

### Phase A: Hotfix (ship immediately)
1. **#1** — Fix `_looks_like_tool_call()` to detect `"name":` format + strengthen Pattern D
2. **#2** — Add `force_tier` to `chat_stream()` + route synthesis to cloud when `hardware_adapted`

### Phase B: Feedback & Transparency
3. **#3** — Tool execution status line in renderer
4. **#5** — Model/routing indicator in metrics footer
5. **#4** — Visual separator between initial text and synthesis

### Phase C: Differentiation
6. **#7** — Insight callouts (new event type + renderer + 3-4 initial insight points)
7. **#6** — Tool execution insight (what tool, what data, why)

### Phase D: Polish
8. **#8** — Command palette (completer, interactive `/config`, `/tools` browser)
