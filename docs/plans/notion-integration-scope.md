# Claude Code ↔ Notion Integration: Scope & Implementation Plan

**Author**: Claude (with Andrew)
**Date**: 2026-03-24
**Status**: Draft — awaiting Andrew's review
**Goal**: Claude Code maintains product documentation in Notion on every ship/handoff, and reads Andrew's working notes from a Notion "whiteboard" page to jumpstart planning — eliminating copy-paste from Apple Notes.

---

## 1. Current State

Hestia has ~203 markdown docs across 10 directories. Steward has ~6 docs and growing. Everything lives in git. There is no Notion integration today.

Documentation breaks down into these categories:

| Category | Directory | Count | Update Frequency | Structure |
|----------|-----------|-------|-------------------|-----------|
| API Contract | `docs/api-contract.md` | 1 | Every sprint (endpoint changes) | Single large file, 2,200+ lines |
| Decision Log (ADRs) | `docs/hestia-decision-log.md` | 1 (40+ ADRs) | Weekly | Single file, structured template per ADR |
| Sprint Plans | `docs/plans/` | ~75 | Multiple per sprint | Date-prefixed, scope/workstream/acceptance |
| Discoveries | `docs/discoveries/` | ~51 | Per research session | Free-form research, SWOT analysis |
| Audits | `docs/audits/` | ~13 | Per sprint cycle | Codebase health snapshots |
| Retrospectives | `docs/retrospectives/` | ~7 | Per session close | Standardized retro template |
| Architecture | `docs/architecture/` | 2 | Infrequent | Deep technical reference |
| Reference | `docs/reference/` | 8 | Infrequent | Quickstart guides, deployment |
| Superpowers | `docs/superpowers/` | 22 | Phase-based | Future specs and plans |
| Security | `docs/hestia-security-architecture.md` | 1 | Infrequent | Security posture |
| Archive | `docs/archive/` | 20 | Never (read-only) | Historical, preserved for context |
| **Steward** | `steward/docs/` | ~6 | Growing | Architecture, extraction plans |

---

## 2. What the Notion MCP Gives Us

The **official Notion MCP server** (v2.0.0, API version 2025-09-03) is available as a hosted connector in the MCP registry. It is **not currently connected** to Andrew's workspace.

### Available Tools (22 total)

**Read operations**: search, retrieve pages, retrieve blocks/children, retrieve data sources (databases), query data sources, list templates, retrieve comments, retrieve users.

**Write operations**: create pages, update pages, append page content, edit page content (Markdown-aware), create data sources, update data sources, move pages, duplicate pages, create comments.

### Key Constraints

| Constraint | Limit | Implication |
|------------|-------|-------------|
| Rate limit | 3 requests/second average | Bulk initial sync of 200+ docs needs throttling (~70 seconds minimum) |
| Payload size | 1,000 blocks / 500KB per request | Large docs (api-contract.md at 2,200 lines) need chunked uploads |
| Nesting depth | 2 levels of nested children per request | Complex nested structures need multiple sequential calls |
| Block children retrieval | Non-recursive | Must recursively fetch children of children for full page reads |
| No delete via MCP | Intentional limitation | Orphaned pages need manual cleanup or Notion API direct calls |
| Format | Notion block JSON, not raw markdown | Conversion layer needed (the MCP `edit` tool accepts markdown, but reads return block JSON) |

### Authentication

Requires a Notion internal integration token (`NOTION_TOKEN`). The integration must be explicitly connected to each page/database it needs to access in the Notion workspace.

---

## 3. Proposed Notion Workspace Structure

### Top-Level Layout

```
Hestia & Steward Knowledge Base (Notion workspace)
├── 📊 Documentation Hub (database)          ← Master index of all docs
│   ├── Properties: Title, Project, Category, Status, Last Synced, Git Path, Sprint
│   └── Views: By Project, By Category, Recently Updated, Stale Docs
│
├── 📋 ADR Registry (database)               ← One row per ADR, rich properties
│   ├── Properties: ADR Number, Title, Status, Date, Tags, Related ADRs
│   └── Views: Active, Deprecated, By Domain (inference, memory, security, etc.)
│
├── 🔌 API Reference (page tree)             ← Structured API docs
│   ├── Per-module sub-pages (Auth, Chat, Memory, Trading, etc.)
│   └── Each endpoint: method, path, request/response, errors
│
├── 🏃 Sprints (database)                    ← Sprint tracking mirror
│   ├── Properties: Sprint Name, Status, Start Date, End Date, Workstreams
│   └── Relations: → ADR Registry, → Documentation Hub
│
├── 🔍 Discoveries & Research (database)     ← Research outputs
│   ├── Properties: Topic, Date, Model Used, Validation Status
│   └── Full content as page body
│
├── 📝 Retrospectives (database)             ← Session retros
│   ├── Properties: Date, Session Duration, First-Pass Rate, Key Findings
│   └── Linked to Sprint
│
└── 🛡️ Steward (section)                    ← Steward-specific docs
    ├── Architecture
    ├── Extraction Plans
    └── Consumer Strategy
```

### Why Databases (Not Just Pages)

Notion databases unlock **filtering, sorting, relations, and rollups** — the key advantages over flat markdown files. For example: "Show me all ADRs related to trading that are still Active" or "Which sprint plans don't have a retrospective yet?" become one-click views.

The Documentation Hub database acts as a master index — every doc from git becomes a row with metadata properties, and the page body contains the full content. This gives you structured queryability on top of rich unstructured content.

---

## 4. Sync Architecture

### The Simple Model

The data flow is intentionally asymmetric — no complex bidirectional conflict resolution needed:

```
                    ANDREW'S BRAIN
                    ┌──────────────────────┐
                    │  Notion "Whiteboard"  │  ← Andrew dumps raw notes,
                    │  (Working Notes page) │    ideas, context here
                    └──────────┬───────────┘    (replaces Apple Notes
                               │                 copy-paste)
                          Claude READS
                               │
                               ▼
┌──────────────────────────────────────────────────────────┐
│                   Claude Code Session                     │
│                                                          │
│   Phase 1: Read whiteboard → understand context          │
│   Phase 2-3: Do the work (git is source of truth)        │
│   Phase 4 / /handoff: PUSH docs to Notion                │
│                                                          │
└──────────────────────────────────────────────────────────┘
                               │
                          Claude WRITES
                               │
                               ▼
                    ┌──────────────────────┐
                    │     Notion Docs       │  ← Maintained, structured,
                    │  (Knowledge Base)     │    browsable product docs
                    └──────────────────────┘
```

**Two distinct Notion surfaces:**

1. **Whiteboard (Andrew → Claude)** — A freeform Notion page where Andrew drops notes, requirements, meeting takeaways, feature ideas. Claude reads this at session start to get context without Andrew having to re-explain or paste from Apple Notes. Andrew writes here; Claude only reads.

2. **Knowledge Base (Claude → Andrew)** — Structured databases and pages that Claude maintains. Updated at Phase 4 / handoff. Git remains the source of truth; Notion is the polished, browsable mirror. Claude writes here; Andrew browses.

### Design Principles

1. **Git is always the source of truth.** Notion is a read-friendly mirror maintained by Claude, not a competing source of truth.
2. **No conflict resolution needed.** Andrew writes to the whiteboard; Claude writes to the knowledge base. These are separate surfaces with clear ownership.
3. **Sync is push-only (git → Notion).** Claude reads git docs, converts to Notion pages, and pushes on ship/handoff. No pulling Notion edits back into git.
4. **The whiteboard is ephemeral.** Claude reads it for context but doesn't archive it. Andrew can clear it between sessions or leave notes accumulating — doesn't matter.

### Sync Triggers

| Trigger | Direction | What Happens |
|---------|-----------|--------------|
| Session start | Notion → Claude (read-only) | Claude reads whiteboard page for context/notes |
| Phase 4 (Review) | Git → Notion | Push updated docs to knowledge base |
| `/handoff` skill | Git → Notion | Session close-out pushes all changed docs |
| Manual: `sync-notion.sh push` | Git → Notion | On-demand full push |

### Markdown → Notion Conversion

The Notion MCP's `edit` tool accepts markdown input, which simplifies pushes. For the git→Notion direction (the only write direction), the workflow is:

1. Read the markdown file from git
2. Parse frontmatter for metadata (properties in Notion databases)
3. Push content via MCP's markdown-aware edit tool
4. Store `notion_page_id` in git frontmatter for future updates (create vs. update)

No Notion→markdown conversion is needed since we're not pulling content back into git.

---

## 5. Implementation Phases

### Phase 0: Setup & Connect (2-3 hours)

- Create a Notion workspace (or use Andrew's existing one)
- Create a Notion internal integration at notion.so/profile/integrations
- Connect the Notion MCP in Cowork/Claude Code
- Verify basic read/write with a test page
- Store the integration token securely (Hestia Keychain or env var)
- Create the **Whiteboard** page — a freeform page Andrew can write to immediately

### Phase 1: Whiteboard + Knowledge Base Scaffold (6-8 hours)

**Goal**: Andrew can drop notes in Notion and Claude can read them. Knowledge base structure is ready to receive docs.

**Workstreams**:

1. **Whiteboard page setup** — Create a top-level "Working Notes" page with a simple structure:
   - Current Focus (what Andrew is thinking about)
   - Ideas & Requirements (raw feature ideas, user feedback, meeting notes)
   - Questions for Claude (things to research or decide next session)
   - Scratch Pad (anything else — links, screenshots, quick thoughts)

   Claude reads this page at session start using the Notion MCP `fetch` tool and incorporates the context into Phase 1 (Research).

2. **Knowledge base scaffolding** — Create databases in **both** workspaces:

   **Hestia workspace:**
   - Documentation Hub, ADR Registry, Sprints, Discoveries, Retrospectives, Archive
   - Whiteboard page (shared across both projects — or one per workspace)

   **Steward workspace:**
   - Documentation Hub, Architecture, Extraction Plans, Consumer Strategy
   - Whiteboard page

   No content yet — just the structure and properties.

3. **Session start hook** — Add whiteboard read to the session startup sequence:
   - Read `SESSION_HANDOFF.md` (existing)
   - Read Notion whiteboard via MCP (new)
   - Summarize any new notes Andrew added since last session

**Deliverable**: Andrew can open Notion on his phone/laptop, jot down "thinking about adding webhooks to the trading module" and the next Claude Code session picks it up automatically.

### Phase 2: Doc Push Pipeline — Git → Notion (8-10 hours)

**Goal**: All existing Hestia + Steward docs mirrored in Notion, updated on every ship/handoff.

**Workstreams**:

1. **Sync script (`scripts/sync-notion.sh`)** — Python script that:
   - Walks `docs/` directories
   - Parses markdown frontmatter for metadata (or infers from filename/path)
   - Creates or updates Notion pages via MCP
   - Handles the api-contract.md chunking (split by route module → sub-pages)
   - Handles the decision log splitting (one ADR per Notion database row)
   - Adds `notion_page_id` to git frontmatter after first sync
   - Respects 3 req/sec rate limit with backoff
   - Tracks `content_hash` to skip unchanged files (incremental sync)

2. **ADR decomposition** — The monolithic `hestia-decision-log.md` gets split into individual ADR entries in the Notion database. Each ADR becomes a row with: Number, Title, Date, Status, Context, Decision, Alternatives, Consequences as separate properties or page body sections.

3. **API contract decomposition** — The monolithic `api-contract.md` gets split into per-module sub-pages (Auth, Chat, Memory, Trading, etc.) for Notion readability.

4. **Initial bulk push** — Run the sync script to populate all ~200 docs into Notion. This is a one-time operation (~5-10 minutes with rate limiting).

**Deliverable**: Running `scripts/sync-notion.sh push` mirrors all docs to Notion. The knowledge base is populated and browsable.

### Phase 3: Workflow Integration (4-6 hours)

**Goal**: Doc pushes happen automatically at Phase 4 and handoff — no manual sync needed.

**Workstreams**:

1. **Phase 4 hook** — After `@hestia-reviewer` runs and docs are updated, automatically push changed docs to Notion.

2. **`/handoff` integration** — Add Notion push to the existing handoff skill's checklist. Session close-out syncs all changed docs.

3. **SPRINT.md → Sprints database** — Auto-update the Sprints database when SPRINT.md changes (sprint status, workstream completion, test counts).

4. **New doc auto-push** — When a new discovery, plan, or ADR is created during a session, it gets pushed to Notion at handoff (not mid-session, to avoid token overhead).

**Deliverable**: Zero-effort doc maintenance. Ship code → docs update in Notion automatically.

### Phase 4: Rich Features (Future — 4-8 hours)

- **Cross-linking**: Notion relations between ADRs, sprints, and discoveries
- **Rollup views**: "Sprint 27 — all related ADRs, plans, retros, and audit findings"
- **Steward consumer docs**: Public-facing Notion pages for Steward product documentation
- **Dashboards**: Notion dashboard showing doc freshness, coverage gaps, orphaned docs
- **Whiteboard templates**: Pre-structured templates for common note types (feature request, bug report, meeting debrief)

---

## 6. Key Trade-Offs & Risks

### Markdown → Notion Fidelity (One-Way Only)

Since we're only pushing git→Notion (never pulling back), fidelity loss is manageable. Markdown renders well in Notion via the MCP's edit tool. Some advanced markdown features (complex tables, nested code blocks) may need manual touch-up in Notion, but this is cosmetic and doesn't affect the source of truth in git.

### Rate Limiting at Scale

200+ docs × multiple blocks each = potentially thousands of API calls for a full sync. At 3 req/sec, a full re-sync could take 5-10 minutes. Mitigation: Incremental sync (only changed docs). Track `content_hash` to skip unchanged files. Typical handoff pushes will only touch 3-10 docs.

### Single Large Files

`api-contract.md` (2,200 lines) and `hestia-decision-log.md` (1,588 lines) exceed comfortable Notion page sizes. Mitigation: Decompose into sub-pages or database entries during sync. This is actually an improvement — these files are unwieldy in markdown too.

### Token/Cost Overhead

Each Notion MCP call during a Claude Code session costs API tokens. Mitigation: The whiteboard read is a single MCP call at session start (cheap). Doc pushes happen via a batch script at handoff, not as individual MCP calls mid-session. Estimated overhead: ~2-5 MCP calls per session (whiteboard read + push confirmation).

### Whiteboard Discipline

The value of the whiteboard depends on Andrew actually using it. If notes stay in Apple Notes or mental context, Claude doesn't benefit. Mitigation: Make it frictionless — Notion mobile app, quick-capture widget, or a bookmark. The whiteboard should feel easier than pasting into a Claude Code prompt.

---

## 7. Estimated Timeline

| Phase | Effort | Dependencies | Target |
|-------|--------|--------------|--------|
| Phase 0: Setup | 2-3 hours | Notion account, MCP connector | Day 1 |
| Phase 1: Whiteboard + scaffold | 6-8 hours | Phase 0 complete | Week 1 |
| Phase 2: Doc push pipeline | 8-10 hours | Phase 1 complete | Week 1-2 |
| Phase 3: Workflow integration | 4-6 hours | Phase 2 battle-tested | Week 2-3 |
| Phase 4: Rich features | 4-8 hours | Phase 3 stable | Month 2+ |

**Total estimated effort**: 24-35 hours across 3-4 weeks at ~12 hrs/week pace.

Phase 0 + Phase 1 can likely be done in a single focused session. The whiteboard becomes useful immediately — you can start dropping notes into Notion the same day.

---

## 8. Decisions (Resolved 2026-03-24)

| Question | Decision |
|----------|----------|
| Notion account | Existing account: `aroman1618@gmail.com` |
| Archive docs | **Yes — sync to Notion** for historical reference with agentic searching |
| ADR decomposition | **Split into individual files in git too** (not just Notion-side). One file per ADR. |
| Workspace separation | **Separate Notion workspaces** for Hestia and Steward, both under Andrew's `aroman1618` account |
| Access | Single user (Andrew only) — no multi-user permissions needed |
| Priority | **Parallel workstream** alongside trading module. No blocking dependencies. |

### ADR Split — Implementation Note

Splitting `hestia-decision-log.md` into individual ADR files is a git-side refactor that should happen in Phase 2 as prep for the Notion push. Proposed structure:

```
docs/decisions/
├── adr-001-qwen-primary-model.md
├── adr-002-governed-memory-persistence.md
├── ...
├── adr-042-agent-orchestrator.md
└── index.md              ← Table of all ADRs with links (replaces the monolith)
```

The monolithic `hestia-decision-log.md` moves to `docs/archive/` and `docs/decisions/index.md` becomes the new entry point. Each ADR file follows the existing template (Context/Decision/Alternatives/Consequences/Notes) with YAML frontmatter for Notion property mapping.

### Parallel Execution — Why It Works

The Notion integration has **zero overlap** with the trading module work:

- Different files: `scripts/sync-notion.sh`, Notion MCP config, `docs/decisions/` restructuring vs. `hestia/trading/`, strategy configs, backtest code
- Different infrastructure: Notion API vs. Coinbase/Alpaca APIs
- No shared database tables or API endpoints
- Phase 0-1 (whiteboard + scaffold) is entirely Notion-side work — no Hestia code changes at all

The only shared touchpoint is Phase 3's `/handoff` integration, which adds a hook call at the end of existing workflow. That's a 5-line addition and can be done safely alongside any other work.
