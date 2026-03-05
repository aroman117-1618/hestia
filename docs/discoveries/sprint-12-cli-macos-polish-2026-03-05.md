# Discovery Report: Sprint 12 — CLI Polish + macOS Profile/Settings + Research Wiring
**Date:** 2026-03-05
**Confidence:** High
**Decision:** Structure as three parallel workstreams (CLI UX, Profile/Settings, Research Deep Dive) across ~2 sprints, prioritizing data pipeline fixes (multi-source memory ingestion) and bug fixes before cosmetic polish.

## Hypothesis
Every piece of the Hestia UI/UX can be made live, editable, secured, and persistent — wired end-to-end from backend to frontend — while also upgrading the CLI experience to match the polish level of tools like Claude Code.

---

## Critical Finding: Multi-Source Memory Ingestion Gap

**Hestia has access to Apple Mail, Reminders, Notes, and Calendar** via 20+ Apple tools and the InboxManager. But **none of this data flows into the memory system**. The `ChunkMetadata.source` field exists in the data model but is never populated. All memory chunks are currently sourced exclusively from chat conversations.

This means:
- The Research graph only visualizes chat-derived knowledge
- DataSource filters (Chat/Email/Notes/Calendar/Reminders/Health) are decorative
- Hestia's "knowledge" of the user is limited to what's been discussed in chat
- Apple integration data is ephemeral — used once in a response, then lost

**This is the highest-impact finding of this discovery.** Fixing the memory pipeline to ingest from Apple sources would make the Research graph genuinely useful and the DataSource filters functional.

---

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Solid backend (154 endpoints, 1611 tests). Agent V2 `.md` config system is flexible. Profile markdown files (MIND/BODY/SPIRIT) already exist with topic-based loading. SceneKit 3D graph rendering works. Rich CLI rendering pipeline in place. `ChunkMetadata.source` field already defined in schema. | **Weaknesses:** Memory system is conversation-only — no ingestion from Apple integrations. DataSource filters are decorative. Principles requires manual distillation trigger. CLI has no agent-colored prompts or thinking animation. Graph "black block" likely from ambient background z-ordering. No device onboarding wizard. |
| **External** | **Opportunities:** Claude Code's spinner verbs pattern is directly applicable and proven at scale. Agent preferences set in macOS app can sync across all devices. Multi-source ingestion would transform Research from novelty to utility. Fire emoji animation would give Hestia distinctive brand identity. | **Threats:** Multi-source ingestion adds complexity to memory search (source-filtered queries). SceneKit deprecated direction from Apple (favor RealityKit long-term). Over-customization of agents could confuse users. |

---

## Priority × Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | **1.** Multi-source memory ingestion (Apple → Memory pipeline). **2.** Fix Research graph black block + principles loading. **3.** Wire DataSource filters to real source data. **4.** CLI agent-colored prompt + fire emoji thinking animation. **5.** Agent profile customization GUI (names, photos, focuses — synced to CLI). | **1.** CLI sub-byline (model, tokens, timing — already partially implemented in `_render_done`). **2.** Profile file grid responsive to window. |
| **Low Priority** | **1.** Default-agent-per-model routing. **2.** Device setup wizard (QR + CLI install). **3.** Reasoning/thinking stream from inference. | **1.** Field Guide diagram scaling (already works via GeometryReader). |

---

## Workstream A: CLI Polish

### A1. Agent-Optimized Modes & Default Agent Per Model

**Current state:** Three personas (Tia/Mira/Olly) with distinct system prompts. Two model tiers actively routed: PRIMARY (Qwen 3.5 9B) and CODING (Qwen 2.5 Coder 7B). Mode detection via `@tia`/`@mira`/`@olly` prefix in CLI.

**Design decision (per Andrew):** The user sets their preferred model and nickname (and color scheme) inside the macOS app. This syncs across all devices/accounts. The CLI prompt shows just `@olly` — the user knows which agent is active because they configured it.

**Proposal: Default Agent Per Model Tier**

| Model Tier | Default Agent | Rationale |
|-----------|---------------|-----------|
| PRIMARY (Qwen 3.5 9B) | **Tia** (Hestia) | General-purpose daily ops, 0.0 temperature |
| CODING (Qwen 2.5 Coder 7B) | **Olly** (Apollo) | Focused dev mode, technical precision, 0.0 temperature |
| COMPLEX (future) | **Mira** (Artemis) | Complex reasoning benefits from Socratic approach, 0.3 temperature |
| CLOUD | **Preserve user selection** | Cloud can handle any persona effectively |

**How it works:**
1. `ModelRouter.route()` already returns a `RoutingDecision` with `tier`
2. After routing, check if user explicitly set a mode (via `@tia` etc.)
3. If no explicit mode → apply tier's default agent
4. Agent's system prompt + temperature override the defaults
5. CLI prompt shows: `[@olly] >` (just the agent name, matching the agent's profile color from macOS app)

**Implementation:** Add `default_agent` field to `ModelConfig` dataclass. In `RequestHandler.handle()`, after routing decision, if no explicit mode override, apply `tier.default_agent`. ~30 lines across `router.py` and `handler.py`. Agent preferences (name, color, model assignment) editable in macOS app and synced via V2 API.

### A2. CLI Formatting & Agent Colors

**Current state:** Rich library renders tokens, status spinners, tool panels, and metrics. Colors: dim gray (status), yellow (mode), red (errors), cyan (links). The `_render_done` method already shows `tokens · duration · model` as a dim sub-byline. No agent-specific theming.

**Proposal: Agent-Colored CLI (ref Claude Code)**

| Component | Current | Proposed |
|-----------|---------|----------|
| Prompt | `[@tia] >` (yellow) | `[@tia] >` in Tia's gradient primary (#FF9500 orange) |
| Prompt (Mira) | `[@mira] >` (yellow) | `[@mira] >` in Mira's gradient primary (#1C3A5F navy) |
| Prompt (Olly) | `[@olly] >` (yellow) | `[@olly] >` in Olly's gradient primary (#2D8B73 teal) |
| Sub-byline | `tokens · duration · model` (dim) | Already exists — enhance with agent name |
| Response header | None | Agent name before first token (in agent color) |
| Markdown | Basic Rich Markdown | Enhanced: code blocks with syntax highlight, headers styled |

**Agent color source:** V2 agent `IDENTITY.md` → `gradient_color_1` field → convert hex to Rich ANSI. Already stored as hex strings. Fetched on CLI startup via `/v2/agents` endpoint, cached locally.

**Implementation:**
1. `renderer.py`: Add `set_agent_theme(name, hex_color)` method → converts hex to nearest Rich ANSI color
2. `repl.py`: Fetch active agent identity on connect → pass theme to renderer
3. `models.py`: Add `AgentTheme` dataclass (name, color_hex)
4. Prompt toolkit prompt formatted with agent color
5. Response header: `\nTia:` (in agent color) before first token

### A3. Thinking Animation (Fire Emoji + Spinner Verbs)

**Current state:** Status events show pipeline stages. `STAGE_LABELS` maps stages to labels like "Searching memory", "Generating". Display: `⟳ Generating...` in dim gray. No personality. No animation.

**Reference:** Claude Code uses ASCII spinner characters (·, ✻, ✽, ✶, ✳, ✢) cycling through a shimmer animation, paired with customizable "spinner verbs" that rotate during processing.

**Proposal: Hestia Fire Spinner + Personality Verbs**

**Fire Animation (replacing ⟳):**
Cycle through fire-themed Unicode characters to create a flickering flame effect:
```
🔥 (fire emoji — primary)

ASCII fallback sequence (for terminals without emoji):
Frame 1: ◠  (open arc)
Frame 2: ◡  (close arc)
Frame 3: ○  (circle)
Frame 4: ◉  (bullseye)
Frame 5: ●  (filled)
Frame 6: ◎  (double circle)
```

With Rich, we can also color-cycle between orange/amber/red to simulate flame flicker:
```python
FIRE_FRAMES = [
    "[bold #FF6B00]🔥[/]",  # orange
    "[bold #FF8C00]🔥[/]",  # dark orange
    "[bold #FFA500]🔥[/]",  # amber
    "[bold #FF4500]🔥[/]",  # red-orange
]
```
Cycle speed: ~200ms per frame (faster than verb rotation).

**Comprehensive Thinking Words List (Jarvis/Friday inspired):**

Common set (used by all agents, shuffled):
```python
COMMON_VERBS = [
    # Cognitive (Jarvis-tier: composed, intelligent)
    "Processing", "Analyzing", "Computing", "Evaluating",
    "Synthesizing", "Correlating", "Cross-referencing",
    "Deliberating", "Contemplating", "Reasoning",
    "Deducing", "Inferring", "Extrapolating",
    "Calibrating", "Resolving", "Formulating",
    "Distilling", "Parsing", "Mapping",

    # Jarvis/Friday Classics (dry, competent)
    "Running diagnostics", "Scanning databases",
    "Accessing records", "Compiling results",
    "Running the numbers", "Checking protocols",
    "Reviewing parameters", "Verifying data",
    "Querying archives", "Assembling brief",
    "Crunching variables", "Consulting the archives",
    "Triangulating", "Reconciling inputs",
    "Performing analysis", "Updating models",

    # Hestia-Specific (hearth/fire metaphor)
    "Tending the fire", "Stoking the embers",
    "Kindling a thought", "Warming up",
    "Simmering", "Slow-burning",
    "Gathering kindling", "Fanning the flames",
    "Forging a response", "Tempering",
    "Annealing", "Casting",
]
```

Agent-specific additions:

```python
TIA_VERBS = [
    # Sardonic/Warm (Friday personality — competent with wit)
    "Chewing on this", "Cooking something up",
    "Stirring the pot", "Brewing thoughts",
    "Herding neurons", "Wrangling context",
    "Juggling priorities", "Polishing the brief",
    "Rehearsing the punchline", "Composing a masterpiece",
    "Negotiating with entropy", "Summoning patience",
    "Rummaging through the archives", "Interrogating the data",
    "Having a word with the database", "Consulting my notes",
    "Reading the room", "Putting pieces together",
    "Making sense of this", "Working my magic",
    "Taking a closer look", "Putting on my thinking cap",
    "Channeling competence", "Tidying up the facts",
    "Doing the heavy lifting", "Fact-checking myself",
    "Running it through the gauntlet", "Sharpening the response",
    "Double-checking the math", "Drafting something good",
    "Earning my keep", "On it, boss",
]

OLLY_VERBS = [
    # Technical/Precise (dev-focused, Jarvis engineering mode)
    "Compiling insights", "Resolving dependencies",
    "Running inference", "Traversing the graph",
    "Optimizing output", "Indexing context",
    "Allocating attention", "Garbage collecting",
    "Refactoring thoughts", "Merging branches",
    "Rebasing understanding", "Linting the logic",
    "Profiling the problem", "Benchmarking options",
    "Debugging assumptions", "Stepping through",
    "Building from source", "Linking symbols",
    "Unwinding the stack", "Checking the diff",
    "Running unit tests", "Validating schema",
    "Spinning up instances", "Deploying thoughts",
    "Patching knowledge gaps", "Containerizing the answer",
    "Pipeline running", "Hotfixing my reasoning",
    "Grepping for answers", "Pushing to production",
    "Code reviewing my thoughts", "Stress-testing the logic",
]

MIRA_VERBS = [
    # Philosophical/Reflective (Socratic, deeper — Artemis wisdom)
    "Seeking the question behind the question",
    "Tracing the roots", "Exploring the landscape",
    "Mapping the territory", "Finding the pattern",
    "Following the thread", "Opening the aperture",
    "Zooming out", "Looking deeper",
    "Listening to what's unsaid",
    "Weighing perspectives", "Sitting with the question",
    "Turning it over", "Considering the angles",
    "Seeking first principles", "Unraveling layers",
    "Meditating on this", "Holding space",
    "Examining assumptions", "Challenging the obvious",
    "Searching for nuance", "Peeling back the surface",
    "Drawing from the well", "Consulting the oracle",
    "Walking the labyrinth", "Connecting constellations",
    "Sifting through wisdom", "Letting it crystallize",
    "Distilling the essence", "Finding the signal",
    "Illuminating blind spots", "Seeing what emerges",
]
```

**Display format:**
```
🔥 Chewing on this...     (verb rotates every 2s, fire flickers every 200ms)
```

**Implementation:**
1. `models.py`: Add `COMMON_VERBS`, `TIA_VERBS`, `OLLY_VERBS`, `MIRA_VERBS` constants
2. `renderer.py`: New `ThinkingAnimation` class:
   - `start(agent_name, agent_color)` → spawns asyncio task
   - Fire emoji color-cycles at 200ms
   - Verb rotates every 2s (random selection from common + agent-specific)
   - Renders: `🔥 {verb}...` on single overwritten line
   - `stop()` → clears line, cancels task
3. In `render_event()`: When status stage is `inference` → start animation. On first `token` event → stop animation.
4. Race condition guard: `_animation_task` checked before token rendering to prevent flicker.

### A4. Reasoning/Thinking Stream (Tier 2 — Future)

When Qwen 3.5 supports chain-of-thought streaming or when using cloud models with thinking blocks:
- Stream `<thinking>` blocks to CLI as collapsed/expandable sections
- Toggle with `--show-reasoning` flag or `/reasoning on` command
- Display in dim italic, indented under a `💭 Reasoning:` header

**Deferred** — requires model-level support. Track as Sprint 12C.

---

## Workstream B: macOS Profile/Settings

### B1. Full-Window Adaptive Layout

**Current state:** macOS settings use accordion pattern (Profile/Agents/Resources/Field Guide). Content has `maxWidth` constraints (~600-800px). Left sidebar in profile view: 200-320px.

**Problem:** Sections don't span full window width on wide displays.

**Fix:**
1. Remove `maxWidth` constraint from accordion content area in `MacSettingsView`
2. Add `GeometryReader` to each section for proportional layout
3. Profile file grid: switch from fixed 4-column to adaptive `GridItem(.adaptive(minimum: 150))`
4. Markdown editor: fill available width with generous padding
5. Agent cards: use `LazyVGrid` with adaptive columns

**Key files:**
- `macOS/Views/Settings/MacSettingsView.swift` → remove maxWidth on content
- `macOS/Views/Settings/MacProfileView.swift` → adaptive grid
- `macOS/Views/Profile/UserProfileView.swift` → flexible sidebar + content

### B2. User Profile Files — MIND.md & BODY.md

**Current state:** Backend already supports 8 markdown files: USER-IDENTITY, MIND, BODY, SPIRIT, VITALS, TOOLS, MEMORY, SETUP. Topic-based loading injects BODY.md for health queries, MIND.md always loaded. macOS UI shows these as `ProfileFileChip` grid with markdown editor.

**What's needed:**
- ✅ MIND.md exists (standards, morals, requirements) — already editable
- ✅ BODY.md exists (meds, supplements, routines beyond HealthKit) — already editable
- **Gap:** No onboarding prompt to populate these files on first use
- **Gap:** No structured template/scaffold when creating a new file
- **Gap:** Editor doesn't show what each file is for

**Proposal:**
1. Add placeholder text / template when file doesn't exist yet:
   - MIND.md: `# My Standards & Values\n\n## Communication Preferences\n...\n## Decision-Making Style\n...\n## Non-Negotiables\n...`
   - BODY.md: `# Health & Wellness\n\n## Medications\n...\n## Supplements\n...\n## Exercise Routine\n...\n## Sleep Schedule\n...`
2. Add tooltip/description on each `ProfileFileChip` explaining the file's purpose
3. Consider adding a "Getting Started" banner if <3 files have content

### B3. Agent Profile Customization GUI

**Current state:** iOS has `AgentProfileView` with full editing. macOS has `MacAgentsView` but it's primarily read-only display. V2 API supports full CRUD for agent configs + individual `.md` files.

**Design decision (per Andrew):** Users customize their 3 agent names, photos, and focuses in the macOS app. These preferences sync across devices — including to the CLI, where the agent's color and name appear in the prompt.

**Recommended GUI scope:**
1. **Quick Edit Panel:** Name, photo, gradient colors, temperature slider
2. **Advanced Tab:** Per-file `.md` editor (IDENTITY, ANIMA, AGENT, USER)
3. **Preview:** Read-only assembled system prompt
4. **History:** Snapshot browser for recovery

**Agent section icon change:** Zap/Database → `person.3.fill` (better represents agent personalities)

**Key implementation:** When agent preferences change in macOS, the V2 API persists them. CLI fetches on startup via `/v2/agents`. Color sync is automatic.

### B4. Device Setup Wizard

**Current state:** QR invite exists (`POST /v1/auth/invite`). Registration with invite works (`POST /v1/auth/register-with-invite`). No streamlined wizard flow.

**Proposal: "Setup New Device" — 3-step wizard**

Step 1: Select device type (Phone/Tablet | Mac | Terminal/CLI)

Step 2a (Phone): Generates QR code → new device scans → auto-registers
Step 2b (Mac): Download instructions + invite token
Step 2c (CLI): Copy-paste ready terminal command:
```bash
pip install hestia-cli && hestia auth login --server https://hestia-3.local:8443 --invite <TOKEN>
```

Step 3: Confirmation — new device appears in device list

**Implementation:**
- New `MacDeviceSetupWizard.swift` view
- QR generation: `CoreImage.CIFilter.qrCodeGenerator`
- Backend: existing endpoints sufficient

---

## Workstream C: Research Deep Dive

### C1. Graph Black Block

**Root cause analysis (3 hypotheses):**

1. **Ambient background z-ordering** (Most likely): `ambientBackground` is a ZStack with blurred orange circles. If it has an opaque fill or the circles are too dense, it could obscure the SceneKit view.

2. **SceneKit NSView opacity**: `MacSceneKitGraphView` may not have `isOpaque = false` set on its backing layer.

3. **Dark mode interaction**: The dark brown color `Color(red: 17/255, green: 11/255, blue: 3/255)` used in tooltips could bleed to parent.

**Fix plan:**
1. Set `sceneView.layer?.isOpaque = false` on the NSView
2. Ensure `ambientBackground` uses `.allowsHitTesting(false)`
3. Verify z-ordering: SceneKit view must be above ambient background in ZStack
4. Test with `ambientBackground` commented out to isolate

### C2. Principles — Review/Approve/Reject Workflow

**Per Andrew's clarification:** The Principles page is a review interface. Hestia flags insights from conversations, and the user approves, edits, or rejects them. Approved principles get correlated into the graph view.

**Current state:**
- `POST /v1/research/principles/distill` — LLM distills principles from recent memory
- `GET /v1/research/principles` — lists all principles
- `PUT /v1/research/principles/{id}/approve` — approves a principle
- `PUT /v1/research/principles/{id}/reject` — rejects a principle
- `PUT /v1/research/principles/{id}` — edits a principle

**Why it's not loading:**
1. **Distillation never triggered**: No auto-trigger. User must manually invoke.
2. **Empty state shows nothing**: No CTA, no explanation of what to do.
3. **ChromaDB collection may not exist** until first distillation.

**Fixes:**
1. Auto-trigger distillation on first visit to Principles tab (if memory has >10 chunks)
2. Show prominent "Analyze Conversations" CTA in empty state
3. Add clear status labels: Pending Review / Approved / Rejected
4. Approved principles should flow into graph as `principle` node type
5. Add loading indicator with error recovery
6. Consider periodic background distillation (hourly/daily) via Orders system

### C3. DataSource Filters — Keep & Wire to Multi-Source

**Per Andrew's clarification:** Hestia already has access to email, reminders, notes, and calendar. The DataSource filters should work with real data.

**Root cause:** The InboxManager aggregates Apple data for UI display, but **nothing flows into the memory system**. The `ChunkMetadata.source` field exists but is never populated.

**Architecture gap:**
```
Current:  Apple Apps → InboxManager → InboxDatabase (read-only cache) → UI
          Chat → MemoryManager → ChromaDB/SQLite → Graph

Missing:  Apple Apps → MemoryManager (with source tagging) → Graph
```

**Proposal: Multi-Source Memory Pipeline**

Phase 1 — Source Tagging (immediate):
- Set `metadata.source = "conversation"` on all chat-stored chunks
- Add `source` filter to `MemoryQuery` and `query_chunks()` SQL
- Wire DataSource filters in UI to pass source filter to graph endpoint

Phase 2 — Apple Ingestion (Sprint 12A priority):
- New `InboxManager.export_to_memory()` method
- Background task (via Orders/APScheduler) runs daily:
  - Pull recent emails → store as FACT chunks with `source="mail"`
  - Pull calendar events → store with `source="calendar"`
  - Pull reminders → store with `source="reminders"`
  - Pull notes → store with `source="notes"`
- Tag extraction: apply AutoTagger to ingested content
- Deduplication: hash-based check before storing

Phase 3 — Graph Integration:
- `graph_builder.py` already builds from memory — source-tagged chunks auto-appear
- DataSource filters map directly: Chat→conversation, Email→mail, Notes→notes, Calendar→calendar, Reminders→reminders, Health→health
- Keep Health filter → fed by HealthKit sync data

**Implementation files:**

| File | Change |
|------|--------|
| `hestia/memory/models.py` | Add `source` to `MemoryQuery` filter params |
| `hestia/memory/database.py` | Add source SQL filtering in `query_chunks()` |
| `hestia/memory/manager.py` | Accept + pass `source` param in `store()` and `store_exchange()` |
| `hestia/orchestration/handler.py` | Set `source="conversation"` when storing exchanges |
| `hestia/inbox/manager.py` | New `export_to_memory()` method |
| `hestia/research/graph_builder.py` | Accept `sources` filter param |
| `hestia/api/routes/research.py` | Accept `sources` query param on graph endpoint |
| `ResearchView.swift` | Wire DataSource filter toggles to `sources` API param |

### C4. Graph Data Validation

**Current datasets behind the graph:**

| Data Layer | Source | Status |
|-----------|--------|--------|
| Memory nodes | ChromaDB `hestia_memory` collection | ✅ Live — from chat interactions |
| Topic nodes | Aggregated from chunk tags (top 50) | ✅ Live — auto-extracted |
| Entity nodes | Aggregated from chunk tags (top 50) | ✅ Live — auto-extracted |
| Principle nodes | ChromaDB `hestia_principles` collection | ⚠️ Requires distillation trigger |
| Edges | Shared topics/entities between nodes | ✅ Computed server-side |
| 3D Layout | Force-directed (120 iterations) | ✅ Computed server-side |
| Clusters | Dominant topic grouping | ✅ Computed server-side |
| **Apple data** | **Mail/Calendar/Reminders/Notes** | **❌ Not ingested into memory** |

---

## Argue (Best Case)

**Why this plan succeeds:**
- Most changes are **wiring, not invention** — backends exist, frontends exist, they just need connection
- CLI formatting is purely additive (Rich library already imported, colors are trivial)
- The sub-byline already exists in `_render_done` — just needs agent name added
- Agent V2 `.md` system was *designed* for GUI editing — the API is already there
- Multi-source ingestion is architecturally clean — `source` field already exists in ChunkMetadata
- Claude Code's spinner verbs pattern is proven at scale and easily replicated
- The Jarvis/Friday personality reference gives clear creative direction
- All changes are backward-compatible — no breaking API changes

**Evidence:**
- Sprint 10 added chat redesign in one session (~6h)
- Sprint 8 built the entire Research module from scratch
- Claude Code has 635+ custom spinner verb configurations in the wild
- The `ChunkMetadata.source` field was designed for exactly this use case

## Refute (Devil's Advocate)

**Why this plan could fail:**
- **Multi-source ingestion is bigger than it looks**: Deduplication, rate limiting, storage growth, and search relevance all need attention. Ingesting every email into memory could flood the graph with noise.
- **Scope creep:** Three workstreams simultaneously is ambitious for ~6h/week
- **Thinking animation race conditions:** Cycling words during inference with asyncio timers has subtle bugs when tokens start arriving mid-cycle
- **Apple data volume:** If user has 10K emails, ingesting all of them into ChromaDB will be slow and may degrade search quality
- **SceneKit deprecation:** More investment in 3D rendering may be throwaway work

**Hidden costs:**
- CLI formatting changes need CLI test updates (66 tests)
- Agent color sync between macOS app and CLI requires API call on CLI startup
- Multi-source ingestion needs new tests (~30-40 across memory, inbox, graph)
- Background ingestion task needs monitoring/logging

**Mitigations:**
- Ingestion window: last 30 days of emails, rolling. Older emails decay via temporal decay.
- Full email bodies stored but chunked if >2000 chars (split into multiple memory chunks with same thread_id tag)
- Chunk type: use `FACT` for Apple data (lower priority in search than `CONVERSATION`)
- Background task: daily via Orders/APScheduler, not real-time
- Deduplication: hash(source + external_id) prevents re-ingesting same email/reminder
- Fire animation: 200ms frame rate is fast but Rich handles ANSI rewrites well

## Third-Party Evidence

**Claude Code's spinner verbs (validated at scale):**
- ASCII spinner characters: ·, ✻, ✽, ✶, ✳, ✢ (cycling through shimmer animation)
- Customizable via `~/.claude/settings.json` — users have created 635+ themed lists
- Community themes: Lord of the Rings, Star Wars, One Piece, military, philosophy
- Key insight: spinner verbs are a beloved feature that adds personality without complexity

**Similar CLI tools:**
- GitHub Copilot CLI: minimal formatting, fast response
- Cursor: rich IDE integration, no terminal personality
- Warp: terminal-native AI with streaming indicators

**Key learning:** The most successful CLI tools invest in *personality during wait states* (spinner verbs) and *clarity in responses* (formatted output). Claude Code proves users love customizable thinking indicators.

---

## Recommendation: Updated Sprint Plan

### Sprint 12A: Data Pipeline + Bugs (~10-12h)

| # | Task | Files | Est |
|---|------|-------|-----|
| 1 | **Multi-source memory ingestion** — source tagging, MemoryQuery filter, InboxManager.export_to_memory() | `memory/models.py`, `memory/database.py`, `memory/manager.py`, `handler.py`, `inbox/manager.py` | 4h |
| 2 | Wire DataSource filters to `sources` API param on graph endpoint | `research/graph_builder.py`, `routes/research.py`, `ResearchView.swift` | 2h |
| 3 | Fix graph black block (SceneKit opacity + ambient bg z-order) | `MacSceneKitGraphView.swift`, `ResearchView.swift` | 1h |
| 4 | Fix principles loading (auto-distill, error state, review workflow) | `ResearchPrinciplesView.swift`, `MacNeuralNetViewModel.swift` | 2h |
| 5 | Profile sections full-window adaptive layout | `MacSettingsView.swift`, `MacProfileView.swift` | 2h |
| 6 | Profile file templates + agent icon change | `MacProfileView.swift`, `MacSettingsView.swift` | 1h |

### Sprint 12B: CLI + Agent Polish (~10-12h)

| # | Task | Files | Est |
|---|------|-------|-----|
| 7 | CLI agent-colored prompts (synced from macOS agent prefs) | `renderer.py`, `repl.py`, `client.py` | 2h |
| 8 | CLI fire emoji thinking animation + spinner verbs (comprehensive list) | `renderer.py`, `models.py` | 3h |
| 9 | Default agent per model tier (configurable in macOS) | `router.py`, `handler.py`, `mode.py` | 2h |
| 10 | macOS agent customization GUI (full editing, color sync) | `MacAgentsView.swift` (expand) | 3h |
| 11 | Device setup wizard (QR + CLI command) | `MacDeviceSetupWizard.swift` (new) | 2h |

### Sprint 12C: Deferred / Future

| # | Task | Files | Est |
|---|------|-------|-----|
| 12 | Reasoning/thinking stream (when model supports it) | `ws_chat.py`, `handler.py`, `renderer.py` | 4h |
| 13 | Background daily ingestion via Orders/APScheduler | `orders/`, `inbox/manager.py` | 3h |
| 14 | Field Guide diagram responsive scaling | `MacWikiView.swift` | 1h |

**Total estimate:** ~22-26h across 3-4 sessions.

---

## Final Critiques

### Skeptic: "Why won't this work?"
**Challenge:** Multi-source ingestion is infrastructure work that could derail the UI polish sprint.
**Response:** The ingestion is surgically scoped: add `source` param to 3 existing methods, write one `export_to_memory()` method, add SQL filter. No schema changes — `source` field already exists. The graph builder already consumes whatever's in memory. Once tagged, Apple data flows through the existing pipeline automatically. This is ~4h of wiring, not a rewrite.

### Pragmatist: "Is the effort worth it?"
**Challenge:** The Research graph was built in Sprint 8 and Andrew barely uses it. Why invest more?
**Response:** *Because it's never had real data to show.* A graph populated only from chat is a novelty. A graph that visualizes patterns across emails, calendar, notes, health, and conversations is the intelligence layer that makes Hestia a genuine personal AI assistant. The DataSource filters were designed for exactly this — they just need the pipeline behind them. This is the difference between a demo and a product.

### Long-Term Thinker: "What happens in 6 months?"
**Challenge:** More data in memory means more storage, slower searches, and potential privacy concerns with email content in ChromaDB.
**Response:** Temporal decay already handles stale data (old chunks fade). Storage is bounded by ingestion limits (30 days, 500/source). ChromaDB handles 100K+ vectors fine on M1. Privacy: all data stays local (Mac Mini), no cloud sync. The bigger risk is *not* doing this — without multi-source data, the Research graph remains decorative and the principles system starves for input.

---

## Resolved Questions

1. ~~Figma reference~~ → Assess based on current build (skip Figma).
2. ~~Agent-per-model UX~~ → Just `@olly`. User sets preferred model/nickname/color in macOS app, syncs everywhere.
3. ~~Thinking words~~ → Common set + agent-specific additions. Comprehensive list above, Jarvis/Friday personality reference.
4. ~~Principles bootstrap~~ → Principles is a review page for Hestia-flagged insights. User approves/edits/rejects. Approved items go to graph. No seeding needed — auto-distill on first visit instead.
5. ~~DataSource vs NodeType~~ → Keep DataSource filters. Multi-source ingestion should already be working. Gap identified: InboxManager → Memory pipeline doesn't exist yet. Fix in Sprint 12A.
6. ~~Thinking icon~~ → Fire emoji (🔥) with color-cycling animation, paired with rotating spinner verbs. Claude Code animation style reference.

## All Questions Resolved

1. ~~Ingestion scope~~ → **Full email bodies and context**. Hestia should be able to evaluate the inbox, clean/organize it, and draft responses to essential threads. This means storing full body text, sender, recipients, subject, date, and thread ID.
2. ~~Ingestion frequency~~ → **Daily background task** for now. Adjust cadence as usage patterns emerge.
3. ~~Principle distillation~~ → **Daily via Orders/APScheduler**. Runs automatically alongside the Apple data ingestion task.

**All design decisions are locked. Ready to execute.**
