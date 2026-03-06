# Sprint 11.5 Execution Plan — 2026-03-05
*File retained as `sprint-12-plan-audit-2026-03-05.md` for git history continuity. Discovery filed as Sprint 12; renumbered to 11.5 during audit.*

**Discovery:** `docs/discoveries/sprint-12-cli-macos-polish-2026-03-05.md`
**Audit Methodology:** 5-panel parallel review (Architecture, Security, Risk, Testing, Code)
**Verdict:** **GO** — All blockers and mitigations resolved inline within execution phases

---

## Executive Summary

Sprint 12 is an **inserted sprint** that addresses a critical infrastructure gap discovered during planning: Hestia has Apple integration access (Mail, Calendar, Reminders, Notes) via 20+ tools and the InboxManager, but none of this data flows into the memory system. The `ChunkMetadata.source` field exists but is never populated — all memory is conversation-only.

This sprint bridges that gap, wires the Research graph to real multi-source data, fixes two longstanding UI bugs (black block, principles loading), polishes the CLI with agent theming and fire emoji animation, and adds macOS agent customization.

Five independent review panels (Architecture, Security, Risk, Testing, Code) validated the plan and identified 6 critical blockers + 5 security mitigations. Rather than treating these as separate pre-work, they are integrated directly into the execution phases below — each task includes its own security hardening and test coverage as a single atomic unit.

---

## Roadmap Placement

### Problem: Sprint Number Collision

The master roadmap (`docs/plans/sprint-7-14-master-roadmap.md`) defines **Sprint 12 as "Health Dashboard & Whoop"**. Our current Sprint 12 is entirely different scope. Meanwhile, Sprint 11A (Model Swap) was already an insertion not in the original roadmap.

### Resolution: Renumber as Sprint 11.5

This sprint becomes **Sprint 11.5** — an infrastructure and polish sprint inserted between Sprint 11A (Model Swap) and the deferred Sprint 11B (Command Center + MetaMonitor). This preserves the master roadmap numbering for Sprints 12-14.

**Rationale:**
1. The multi-source memory ingestion is the **missing link** in the Learning Cycle threading between Sprint 9B (Inbox) and Sprint 8 (Research & Graph). The master roadmap's dependency chain shows `9B → 12 (Health/Whoop)`, but it should also show `9B → memory pipeline → 8 (graph enrichment)`. Sprint 11.5 fills that gap.
2. Sprint 11B (Command Center + MetaMonitor) depends on OutcomeTracker data accumulating over time. Inserting 11.5 gives OutcomeTracker more time to collect meaningful signals before Decision Gate 2.
3. The CLI and macOS polish work in 11.5B improves developer experience for all subsequent sprints.

### Updated Learning Cycle Threading

```
Sprint 7:   Profile & Settings               ← Foundation
Sprint 8:   Research & Graph + PrincipleStore ← Learning Cycle Phase A (part 1)
Sprint 9A:  Explorer: Files                   ← Data breadth (file signals)
Sprint 9B:  Explorer: Inbox                   ← Data breadth (email signals)
Sprint 10:  Chat Redesign + OutcomeTracker    ← Learning Cycle Phase A (part 2)
Sprint 11A: Model Swap + Coding Specialist    ← Dual model (qwen3.5:9b + qwen2.5-coder:7b)
Sprint 11.5A: Memory Pipeline + Research Wire ← INSERTED: Multi-source ingestion fills 9B→8 gap
Sprint 11.5B: CLI + Agent Polish              ← INSERTED: UX polish before 11B complexity
Sprint 11B: Command Center + MetaMonitor      ← Learning Cycle Phase B (deferred, more data now)
Sprint 12:  Health Dashboard & Whoop          ← Personal state data (master roadmap preserved)
Sprint 13:  Active Inference Foundation        ← Learning Cycle Phase C (part 1)
Sprint 14:  Anticipatory Execution            ← Learning Cycle Phase C (part 2)
```

### Updated Dependency Chain

```
Sprint 9B (Inbox read-only)
    └── Sprint 11.5A (Inbox → Memory pipeline) ← NEW
        └── Sprint 8 enrichment (graph now has multi-source data)
        └── Sprint 11B (MetaMonitor benefits from richer memory)
            └── Sprint 13-14 (Active Inference has full data landscape)
```

### Decision Gate Impact

**Gate 2 (after Sprint 10):** "Is OutcomeTracker collecting meaningful signals?" — Sprint 11.5 gives 2-3 more weeks of data collection before Gate 2 is evaluated for Sprint 11B go/no-go. This is a benefit, not a delay.

**Gate 3 (after Sprint 12):** Unchanged. Health Dashboard & Whoop remain Sprint 12 in the master roadmap.

---

## Execution Phases

### Phase A: Memory Pipeline Infrastructure (Sprint 11.5A — ~14h)

Every task in this phase includes its security mitigations and tests as integral parts, not afterthoughts. Tasks are sequenced by dependency — each builds on the previous.

#### Task A1: MemorySource Enum + Source Parameter Wiring
**Scope:** Create the type-safe foundation that all subsequent tasks depend on.
**Est:** 2h

**Implementation:**
1. Add `MemorySource(str, Enum)` to `hestia/memory/models.py`:
   - Values: `CONVERSATION`, `MAIL`, `CALENDAR`, `REMINDERS`, `NOTES`, `HEALTH`
   - String values lowercase for DB storage: `"conversation"`, `"mail"`, etc.
2. Add `source: Optional[MemorySource] = None` to `MemoryQuery` dataclass
3. Add `source: Optional[str] = MemorySource.CONVERSATION` param to `MemoryManager.store()` and `store_exchange()`
4. Pass `source` through to `MemoryDatabase.store_chunk()`
5. Set `source=MemorySource.CONVERSATION` in `RequestHandler.handle()` when storing exchanges
6. Add `WHERE source = ?` clause to `MemoryDatabase.query_chunks()` (when `MemoryQuery.source` is set)
7. **Migration:** Add `UPDATE chunks SET source = 'conversation' WHERE source IS NULL` to handle existing data

**Tests (8):**
- Store chunk with source="mail" → verify source persisted
- Store chunk with default → source="conversation"
- Query filtered by source → correct results only
- Query without source filter → all sources returned (backward compat)
- MemorySource enum all values valid
- Invalid source rejected with ValueError
- Migration: existing chunks get source="conversation"
- No breaking changes to `/v1/chat` or `/v1/memory/search`

**Resolves:** CB-1 (missing source param), CB-2 (missing source filtering), CB-6 (missing enum)

---

#### Task A2: Source Deduplication + Ingestion Tracking
**Scope:** Prevent duplicate memory chunks when daily ingestion re-processes the same items. Track ingestion batches for rollback capability.
**Est:** 2.5h

**Implementation:**
1. Add `source_dedup` table to `MemoryDatabase`:
   ```sql
   CREATE TABLE IF NOT EXISTS source_dedup (
       source TEXT NOT NULL,
       source_id TEXT NOT NULL,
       chunk_id TEXT NOT NULL,
       ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       batch_id TEXT,
       UNIQUE(source, source_id)
   );
   ```
2. Add `external_id: Optional[str]` to `ChunkMetadata`
3. Add `check_duplicate(source, source_id) → bool` method to `MemoryDatabase`
4. Add `source_ingestion_log` table:
   ```sql
   CREATE TABLE IF NOT EXISTS source_ingestion_log (
       batch_id TEXT PRIMARY KEY,
       source TEXT NOT NULL,
       started_at TIMESTAMP,
       completed_at TIMESTAMP,
       items_processed INTEGER DEFAULT 0,
       items_stored INTEGER DEFAULT 0,
       items_skipped INTEGER DEFAULT 0,
       status TEXT DEFAULT 'running'
   );
   ```
5. Add `rollback_batch(batch_id)` method — deletes all chunks with matching batch_id from both SQLite and ChromaDB

**Tests (8):**
- Store same external_id twice → only one chunk exists
- Different content same external_id → skip (not update)
- Bulk: 100 items, 20 duplicates → 80 stored
- Ingestion log tracks batch progress
- Rollback: delete all chunks from specific batch
- Rollback: ChromaDB entries also removed
- Partial batch failure → successful items persisted
- Concurrent dedup checks → no race condition (UNIQUE constraint handles)

**Resolves:** CB-3 (no dedup mechanism), R-009 (no rollback strategy)

---

#### Task A3: InboxMemoryBridge + Email Preprocessing
**Scope:** Bridge class that mediates between InboxManager (read) and MemoryManager (write) with full email body preprocessing, encryption, and prompt injection sanitization. This is the core of the ingestion pipeline.
**Est:** 5h

**Architecture (ARCH-1):**
```
InboxManager (read-only) → InboxMemoryBridge (transform + dedup + encrypt + sanitize) → MemoryManager (write)
```
InboxManager never writes to memory. The bridge is a separate class in `hestia/inbox/bridge.py`.

**Implementation:**
1. New file: `hestia/inbox/bridge.py` → `InboxMemoryBridge` class
2. Constructor takes `InboxManager`, `MemoryManager`, `CredentialManager` (for Fernet)
3. Core method: `async def ingest(source_types: List[MemorySource], batch_size: int = 50) → IngestionResult`
4. **Email body preprocessing pipeline:**
   - Strip HTML tags (BeautifulSoup or html2text)
   - Remove email signatures (regex: `--\s*\n`, `Sent from my iPhone`, common patterns)
   - Collapse quoted thread text (lines starting with `>`)
   - Extract structured metadata: sender, recipients, subject, date, thread_id, message_id
   - **Chunking:** If body > 2000 chars, split on paragraph boundaries. All chunks share `thread_id` tag
5. **Prompt injection sanitization (SEC-2):**
   - Strip control characters and zero-width Unicode
   - Prefix each stored chunk: `[INGESTED EMAIL — {sender} — {date}]:`
   - Add content boundary in prompt template: `--- BEGIN INGESTED CONTENT ---` / `--- END INGESTED CONTENT ---`
   - Configurable blocklist of suspicious patterns (optional, log-only initially)
6. **Encryption at rest (SEC-1):**
   - Encrypt email body content with Fernet before storing in ChromaDB metadata
   - Use `CredentialManager.encrypt(body)` → store encrypted bytes
   - On retrieval: `CredentialManager.decrypt(encrypted)` → plaintext
   - SQLite stores encrypted content column; ChromaDB document field stores encrypted
   - Tags/metadata remain unencrypted (needed for filtering)
7. **Privilege separation (SEC-4):**
   - InboxManager only provides `get_items()` — never gains write access
   - Bridge creates ChunkMetadata, calls dedup check, encrypts, then calls MemoryManager.store()
   - Clear separation: InboxManager interface unchanged from Sprint 9B
8. **Batch processing (ARCH-2):**
   - Process items in batches of 50
   - Each batch is a transaction unit — log to `source_ingestion_log`
   - If batch fails, log error, skip to next batch
   - Resume from last successful batch on retry
9. **Source mapping:**
   - Mail items → `MemorySource.MAIL`, ChunkType.FACT
   - Calendar events → `MemorySource.CALENDAR`, ChunkType.FACT
   - Reminders → `MemorySource.REMINDERS`, ChunkType.FACT
   - Notes → `MemorySource.NOTES`, ChunkType.INSIGHT
10. **Rolling window:** Only ingest items from last 30 days. Temporal decay handles older items.
11. **Per-source caps:** Max 500 chunks per source type. Oldest chunks pruned when cap exceeded.

**Tests (20):**
- Bridge transforms mail item → correct ChunkMetadata
- Bridge transforms calendar item → correct ChunkMetadata
- Bridge transforms reminder → correct ChunkMetadata
- Bridge transforms note → correct ChunkMetadata
- Email HTML stripped cleanly
- Email signatures removed (3 patterns tested)
- Quoted thread text collapsed
- Body >2000 chars → multiple chunks with shared thread_id
- Fernet encryption applied to stored content
- Encrypted content decrypted correctly on retrieval
- Tags/metadata remain unencrypted and searchable
- Prompt injection patterns sanitized (5 patterns)
- Content prefix "[INGESTED EMAIL]" applied
- Dedup: existing item skipped
- Dedup: new item stored
- Batch of 50 processes correctly
- Partial batch failure → others succeed
- Ingestion log records batch stats
- Empty inbox → graceful empty result
- Per-source cap enforced (501st item triggers prune)

**Resolves:** CB-5 (missing export method), SEC-1 (encryption), SEC-2 (prompt injection), SEC-4 (privilege separation), ARCH-1 (bridge pattern), ARCH-2 (transactions), R-003 (email noise)

---

#### Task A4: Daily Ingestion Background Task
**Scope:** Scheduled task via Orders/APScheduler that triggers the InboxMemoryBridge daily.
**Est:** 1.5h

**Implementation:**
1. New order type: `SYSTEM_INGESTION` in `hestia/orders/`
2. APScheduler CronTrigger: `hour=3, minute=0` (3 AM daily — off-peak)
3. Task body: instantiate InboxMemoryBridge → call `ingest(all_sources)` → log result
4. On first server start: auto-create the scheduled order if it doesn't exist
5. Manual trigger: `POST /v1/orders/{id}/execute` for on-demand ingestion
6. Exponential backoff on failure (1h, 2h, 4h retries)
7. **User-scoped (SEC fix):** Ingestion runs per-user using the authenticated user's device token

**Tests (6):**
- Scheduled order created on first server start
- Manual trigger executes ingestion
- Failure → retry with backoff
- Concurrent triggers → only one runs (lock)
- Ingestion result logged to order execution history
- User scope: different users get different ingestion runs

**Resolves:** R-008 (task reliability)

---

#### Task A5: DataSource Filter Wiring + Graph Truncation
**Scope:** Wire the decorative DataSource filters in the Research graph UI to real backend source filtering. Truncate graph node content for security.
**Est:** 2.5h

**Implementation:**
1. `hestia/research/graph_builder.py`: Add `sources: Optional[List[MemorySource]]` param to `build_graph()`. Pass to `MemoryManager.search()` as source filter.
2. `hestia/api/routes/research.py`: Add `sources` query param to `GET /v1/research/graph`. Accept comma-separated list: `?sources=conversation,mail`
3. **Graph content truncation (SEC-3):** Truncate `node.content` to 200 chars in API response. Full content via `/v1/memory/search` only.
4. `ResearchView.swift` (macOS): Wire `DataSource` toggle state to `sources` API query param. When user toggles "Email" on/off → re-fetch graph with updated sources filter.
5. Validate: empty sources list → empty graph (not error). Invalid source → 400 with message.
6. `MemorySource` → `DataSource` mapping enum in Swift: CONVERSATION→chat, MAIL→email, CALENDAR→calendar, REMINDERS→reminders, NOTES→notes, HEALTH→health

**Tests (10):**
- Graph endpoint accepts sources param
- sources=["conversation"] → only chat nodes
- sources=["mail"] → only email nodes
- sources=["mail","conversation"] → both types
- No sources param → all sources (backward compat)
- Empty sources → empty graph (not error)
- Invalid source → 400 error
- Node content truncated to ≤200 chars in response
- Graph build with 1000+ nodes <5s
- DataSource enum maps 1:1 to MemorySource enum

**Resolves:** SEC-3 (graph leakage), R-002 (search quality — source filtering gives user control)

---

#### Task A6: Fix Graph Black Block
**Scope:** Fix the opaque black block obscuring the 3D SceneKit graph view.
**Est:** 1h

**Diagnostic plan (3 hypotheses, test each):**
1. `ambientBackground` ZStack has opaque fill → add `.allowsHitTesting(false)` and ensure SceneKit view is above it
2. `MacSceneKitGraphView` NSView backing layer not transparent → set `sceneView.layer?.isOpaque = false`, `sceneView.backgroundColor = .clear`
3. Dark mode color bleed from tooltip `Color(red: 17/255, green: 11/255, blue: 3/255)`

**Fix sequence:** Comment out `ambientBackground` first to isolate. If that fixes it, adjust z-ordering. If not, check NSView opacity. Test on both dev machine and Mac Mini.

**Tests (2):**
- Graph renders without opaque overlay (visual verification)
- Ambient background doesn't intercept touch/click events

**Resolves:** R-005 (environment-dependent fix — test on both machines)

---

#### Task A7: Fix Principles Loading + Daily Auto-Distillation
**Scope:** Make the Principles tab actually load and populate. Add daily auto-distillation so principles accumulate without manual intervention.
**Est:** 2.5h

**Implementation:**
1. **PrincipleStore async safety (CB-4):** Add `asyncio.Lock()` guard to `initialize()`. Ensure ChromaDB collection exists before any operation.
2. **Auto-distill on first visit:** When Principles tab loads and list is empty, auto-trigger `POST /v1/research/principles/distill` if memory has >10 chunks. Show loading spinner with "Analyzing your conversations..." message.
3. **Daily auto-distill:** Add scheduled order (same pattern as A4): daily at 4 AM, runs `PrincipleStore.distill()` on recent memory (last 7 days).
4. **Error state:** If distillation fails, show actionable error with retry button instead of empty state.
5. **Status labels:** Display principle status (Pending Review / Approved / Rejected) with color coding.
6. **Graph integration:** Approved principles appear as `principle` node type in graph. Edges connect to source memory chunks.
7. **Source awareness:** When distilling from multi-source memory, principles cite their sources: "Based on email from [sender] on [date]" or "From conversation on [date]".

**Tests (12):**
- PrincipleStore.initialize() is async-safe (concurrent calls don't race)
- Auto-distill triggers when memory >10 chunks
- Auto-distill skipped when memory ≤10 chunks
- Auto-distill produces ≥1 principle from test data
- Approve → status updated in ChromaDB
- Reject → status updated, excluded from graph
- Edit → content updated, status preserved
- Approved principle appears as graph node
- Daily scheduled order created
- Empty memory → graceful empty list (no error)
- ChromaDB unavailable → graceful degradation with error message
- Concurrent distill requests → no duplicate principles

**Resolves:** CB-4 (async safety), R-011 (first-visit latency)

---

#### Task A8: Profile Layout + File Templates
**Scope:** Make Profile/Settings sections span full window width. Add scaffold templates for MIND.md and BODY.md.
**Est:** 2h

**Implementation:**
1. Remove `maxWidth` constraint from accordion content area in `MacSettingsView.swift`
2. Profile file grid: switch to `LazyVGrid(columns: [GridItem(.adaptive(minimum: 150))])`
3. Markdown editor: fill available width with 24px horizontal padding
4. Agent cards: adaptive grid columns
5. **Profile file templates:** When MIND.md or BODY.md doesn't exist, pre-populate with structured scaffold:
   - MIND.md: `# Standards & Values\n\n## Communication Preferences\n...\n## Decision-Making Style\n...\n## Non-Negotiables\n...`
   - BODY.md: `# Health & Wellness\n\n## Medications\n...\n## Supplements\n...\n## Exercise Routine\n...\n## Sleep Schedule\n...`
6. Add tooltips on `ProfileFileChip` explaining each file's purpose
7. Change agent section icon from zap/database to `person.3.fill`

**Tests (4):**
- Profile grid adapts to window width (wide → more columns)
- Template generated for empty MIND.md
- Template generated for empty BODY.md
- Agent icon updated to person.3.fill

---

#### Phase A Integration Test Suite
**Scope:** Backward compatibility and performance regression tests that span all Phase A tasks.
**Est:** 2h

**Tests (12):**
- Existing conversations load without source → defaults to "conversation"
- Memory search without source filter → same results as before
- Graph without source filter → same output as before
- Existing principles still load after changes
- API responses include source field where applicable
- Health check passes after all changes
- Full existing test suite (1611+) still passes
- Memory search with 5000 chunks <500ms
- Graph build with 1000 nodes <5s
- Daily ingestion of 200 items <60s
- Concurrent ingestion + chat query → no deadlock
- Temporal decay batch processing: 5000 chunks <10s

---

### Phase A Totals

| Task | Est | Tests |
|------|-----|-------|
| A1: MemorySource + source wiring | 2h | 8 |
| A2: Dedup + ingestion tracking | 2.5h | 8 |
| A3: InboxMemoryBridge + preprocessing | 5h | 20 |
| A4: Daily ingestion task | 1.5h | 6 |
| A5: DataSource filters + graph truncation | 2.5h | 10 |
| A6: Fix graph black block | 1h | 2 |
| A7: Principles loading + auto-distill | 2.5h | 12 |
| A8: Profile layout + templates | 2h | 4 |
| Integration + performance tests | 2h | 12 |
| **Phase A Total** | **21h** | **82** |

---

### Phase B: CLI + Agent Polish (Sprint 11.5B — ~15h)

#### Task B1: CLI Agent-Colored Prompts
**Scope:** Fetch agent identity from V2 API, apply gradient color to CLI prompt and response headers.
**Est:** 2.5h

**Implementation:**
1. `hestia-cli/hestia_cli/models.py`: Add `AgentTheme` dataclass (name, color_hex, gradient_secondary)
2. `hestia-cli/hestia_cli/client.py`: Fetch `/v2/agents` on connect → extract active agent identity → cache `AgentTheme`
3. `hestia-cli/hestia_cli/renderer.py`: New `set_agent_theme(theme: AgentTheme)` method → uses Rich `Color.parse(hex)` for hex → ANSI
4. Prompt: `[@tia] >` rendered in agent's gradient_color_1 (Tia=#FF9500, Olly=#2D8B73, Mira=#1C3A5F)
5. Response header: `\nTia:` (in agent color) before first token
6. Sub-byline enhancement: add agent name to existing `tokens · duration · model` display
7. **Escape sanitization (SEC-5):** All tool output passed through `rich.markup.escape()` before rendering. Audit existing `_render_tool_*` methods for coverage.

**Tests (10):**
- Agent color hex parsed for all 3 agents
- Color applied to prompt string
- Color applied to response header
- Sub-byline includes agent name
- Agent theme cached after first fetch
- API unavailable → fall back to yellow (existing default)
- HESTIA_NO_COLOR → no color applied
- Rich escape() applied to tool output (SEC-5)
- Custom agent name renders correctly
- Custom agent color renders correctly

**Resolves:** SEC-5 (escape injection), R-007 (color conversion)

---

#### Task B2: Fire Emoji Thinking Animation + Spinner Verbs
**Scope:** Replace dim gray `⟳ Generating...` with a fire emoji that color-cycles and personality-driven rotating verbs.
**Est:** 3.5h

**Implementation:**
1. `hestia-cli/hestia_cli/models.py`: Add verb constants:
   - `COMMON_VERBS` (32 entries — cognitive, Jarvis classics, hearth metaphors)
   - `TIA_VERBS` (32 — sardonic, warm, Friday personality)
   - `OLLY_VERBS` (32 — technical, dev-focused, Jarvis engineering)
   - `MIRA_VERBS` (32 — philosophical, Socratic, reflective)
   - `FIRE_FRAMES` list (4 Rich-formatted fire emoji with color cycling)
2. `hestia-cli/hestia_cli/renderer.py`: New `ThinkingAnimation` class:
   - `async start(agent_name: str)` → spawns asyncio task
   - Fire emoji color-cycles at 200ms (Rich live display, single line rewrite)
   - Verb rotates every 2s (random selection from common + agent-specific pool)
   - Display: `🔥 Chewing on this...`
   - `stop()` → cancels task, clears line
   - **Race condition guard (R-006):** `asyncio.Lock` ensures stop() completes before token rendering begins. Token event checks `_animation_active` flag before writing.
3. ASCII fallback for terminals without emoji support: detect with `HESTIA_NO_EMOJI` env var or terminal capability check. Use `◠◡○◉●◎` sequence.
4. In `render_event()`: inference stage → `animation.start()`. First token event → `animation.stop()`. Done event also calls stop as safety net.

**Tests (14):**
- Fire frames cycle through 4 colors
- Animation stops cleanly on first token
- Verb selection includes common + agent-specific
- Tia verbs used when Tia active
- Olly verbs used when Olly active
- Mira verbs used when Mira active
- ThinkingAnimation.start() creates task
- ThinkingAnimation.stop() cancels + clears
- No animation leak: stop always called before done
- Race condition: token during animation → clean transition
- ASCII fallback when HESTIA_NO_EMOJI set
- HESTIA_NO_COLOR disables color on fire frames
- Empty verb list → falls back to common
- Long verb text truncated to terminal width

**Resolves:** R-006 (race conditions)

---

#### Task B3: Default Agent Per Model Tier
**Scope:** When user doesn't explicitly select an agent with `@tia`/`@olly`/`@mira`, automatically assign one based on the model tier being used.
**Est:** 2h

**Implementation:**
1. `hestia/inference/router.py`: Add `default_agent: Optional[str]` to `ModelConfig` dataclass
2. Configure defaults in `config/inference.yaml`:
   - PRIMARY (Qwen 3.5 9B) → `tia`
   - CODING (Qwen 2.5 Coder 7B) → `olly`
   - COMPLEX (future) → `mira`
   - CLOUD → `None` (preserve user selection)
3. `hestia/orchestration/handler.py`: After `ModelRouter.route()`, if no explicit mode override (no `@agent` prefix), apply `routing_decision.tier.default_agent`
4. Agent's system prompt and temperature override applied when default agent activates
5. Agent preferences editable in macOS app → V2 API persists → CLI picks up on next start

**Tests (10):**
- No explicit mode + PRIMARY → Tia's prompt applied
- No explicit mode + CODING → Olly's prompt applied
- No explicit mode + COMPLEX → Mira's prompt applied
- No explicit mode + CLOUD → user's last selection preserved
- Explicit @tia overrides regardless of tier
- Explicit @olly overrides regardless of tier
- Temperature override applied from agent config
- default_agent field stored in ModelConfig
- Config YAML parsed correctly
- Agent change mid-session updates prompt

---

#### Task B4: macOS Agent Customization GUI
**Scope:** Expand MacAgentsView from read-only display to full editing: name, photo, gradient colors, per-file .md editor.
**Est:** 3h

**Implementation:**
1. **Quick Edit Panel:** Inline editing for name, gradient_color_1/2, temperature slider
2. **Photo picker:** Use `PhotosPicker` → upload via `PUT /v2/agents/{slot}/photo`
3. **Advanced Tab:** Per-file `.md` editor (IDENTITY, ANIMA, AGENT, USER) using existing `MarkdownEditor` component
4. **Preview:** Read-only assembled system prompt (call `GET /v2/agents/{slot}?assembled=true`)
5. **Snapshot history:** List snapshots from `GET /v2/agents/{slot}/snapshots` with restore button
6. **Color sync:** When gradient colors change, save via `PUT /v2/agents/{slot}` → CLI picks up new colors on next start

**Tests (6):**
- Agent name editable and saved
- Gradient colors editable and saved
- Photo upload works
- .md file editing works per-file
- Snapshot restore works
- Changes sync to CLI (verified via API)

---

#### Task B5: Device Setup Wizard
**Scope:** 3-step wizard for onboarding new devices: iOS (QR), Mac (instructions), CLI (copy-paste command).
**Est:** 2h

**Implementation:**
1. New `MacDeviceSetupWizard.swift`: sheet/modal with 3 steps
2. Step 1: Select device type (Phone/Tablet | Mac | Terminal/CLI) with SF Symbols
3. Step 2a (Phone): Generate QR via `CIFilter.qrCodeGenerator` encoding invite token from `POST /v1/auth/invite`
4. Step 2b (Mac): Download instructions + invite token display
5. Step 2c (CLI): Copy-ready command: `pip install hestia-cli && hestia auth login --server https://hestia-3.local:8443 --invite <TOKEN>`
6. Step 3: Confirmation — poll `/v1/user/devices` until new device appears

**Tests (4):**
- QR code generated from invite token
- CLI command includes correct server URL
- Device list updates after registration
- Wizard dismisses on completion

---

#### Phase B Integration Test Suite
**Scope:** CLI-specific integration and backward compatibility.
**Est:** 2h

**Tests (10):**
- CLI without agent theme → falls back to yellow
- CLI connects to server with all Phase A changes → no errors
- Agent preferences fetched on CLI startup
- Model tier switch → agent switches automatically
- 200ms fire frame rate maintained (timing)
- 2s verb rotation maintained (timing)
- Unicode verbs render correctly
- Bulk dedup check: 500 items <2s
- CLI memory footprint during animation <50MB
- Full CLI test suite (66+) still passes

---

### Phase B Totals

| Task | Est | Tests |
|------|-----|-------|
| B1: Agent-colored prompts | 2.5h | 10 |
| B2: Fire emoji animation + verbs | 3.5h | 14 |
| B3: Default agent per model tier | 2h | 10 |
| B4: macOS agent customization GUI | 3h | 6 |
| B5: Device setup wizard | 2h | 4 |
| Integration tests | 2h | 10 |
| **Phase B Total** | **15h** | **54** |

---

## Grand Totals

| Phase | Effort | New Tests | Sessions (~6h) |
|-------|--------|-----------|-----------------|
| Phase A: Memory Pipeline + Research | 21h | 82 | 3.5 |
| Phase B: CLI + Agent Polish | 15h | 54 | 2.5 |
| **Sprint 11.5 Total** | **36h** | **136** | **6** |

**Projected test suite:** 1611 existing + 136 new = **1747 tests**

---

## Risk Register (Consolidated)

| ID | Risk | Severity | Mitigation (built into tasks) |
|----|------|----------|-------------------------------|
| R-001 | Estimation accuracy | Addressed | Tasks individually estimated with subtask detail. Total 36h (realistic). |
| R-002 | Search quality degradation | High | Source-weighted search + per-source caps (500) + user-controlled DataSource filters (A5) |
| R-003 | Email noise | High | Full preprocessing pipeline: HTML strip, signature removal, thread collapse (A3) |
| R-004 | Test coverage | Addressed | 136 new tests across 8 categories (embedded in each task) |
| R-005 | Black block environment-dependent | Medium | Test on both dev + Mac Mini. 2D fallback ready (A6) |
| R-006 | Animation race conditions | Medium | asyncio.Lock guard + _animation_active flag (B2) |
| R-007 | Color hex → ANSI lossy | Medium | Rich Color.parse() handles hex natively. All 3 colors tested (B1) |
| R-008 | Background task reliability | Medium | Exponential backoff + manual trigger fallback + ingestion log (A4) |
| R-009 | No rollback for bad ingestion | Addressed | batch_id tracking + rollback_batch() method (A2) |
| R-010 | ChromaDB memory pressure | Low | Batch processing (50), per-source caps (500), RSS monitoring (A3) |
| R-011 | Principles first-visit latency | Medium | Async distill + loading spinner + daily background distill (A7) |

---

## Acceptance Criteria

Sprint 11.5 is complete when:

1. **Memory pipeline live:** Daily ingestion runs at 3 AM, processes Mail/Calendar/Reminders/Notes into memory with source tags, encryption, and dedup
2. **Research graph multi-source:** DataSource filters work — toggling Email/Notes/Calendar shows/hides relevant nodes
3. **Principles auto-populate:** Principles tab loads with distilled insights. Approve/reject workflow functional
4. **Graph visible:** No black block obscuring the 3D view
5. **CLI themed:** Agent-colored prompts, fire emoji animation with personality verbs, model sub-byline
6. **Agents editable:** macOS GUI supports full agent customization (name, photo, colors, .md files)
7. **Device wizard works:** QR code for iOS, CLI command for terminal — new device appears in list
8. **All tests pass:** 1747+ tests (1611 existing + 136 new), zero regressions
9. **Security hardened:** Email bodies encrypted at rest, prompt injection sanitized, graph content truncated, CLI escape sequences sanitized

---

## Architecture Review Responses

| Finding | Severity | Response |
|---------|----------|----------|
| ARCH-1: InboxMemoryBridge | WARN → Resolved | Built as core of Task A3. InboxManager stays read-only. |
| ARCH-2: Transaction boundaries | WARN → Resolved | Batch processing with ingestion log in Task A2/A3. |
| ARCH-3: ChromaDB volume | WARN → Mitigated | Per-source caps (500), temporal decay, monitoring. Review at Gate 2. |
| ARCH-4: Agent sync pull-only | INFO → Accepted | Pull-based sufficient for now. WebSocket push tracked as future. |

## Security Review Responses

| Finding | Severity | Response |
|---------|----------|----------|
| SEC-1: Email encryption | CRITICAL → Resolved | Fernet encryption in Task A3. |
| SEC-2: Prompt injection | HIGH → Resolved | Sanitization + content boundaries in Task A3. |
| SEC-3: Graph data leakage | HIGH → Resolved | 200-char truncation in Task A5. |
| SEC-4: Privilege separation | HIGH → Resolved | InboxMemoryBridge pattern in Task A3. |
| SEC-5: Escape injection | MEDIUM → Resolved | Rich escape() audit in Task B1. |

---

## Sprint 12C: Deferred / Future

| # | Task | Est | Notes |
|---|------|-----|-------|
| C1 | Reasoning/thinking stream (model-dependent) | 4h | Requires Qwen thinking block support or cloud model |
| C2 | Field Guide diagram responsive scaling | 1h | Low priority — GeometryReader already handles most cases |
| C3 | Source-weighted search scoring | 2h | conversation=1.0x, apple=0.7x — implement if search quality degrades |
| C4 | Agent sync via WebSocket push | 3h | Real-time sync when agent prefs change — implement if pull-based feels laggy |
