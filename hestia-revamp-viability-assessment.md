# Hestia Revamp Viability Assessment

**Date:** February 22, 2026
**Scope:** Unified workspace interface, deep file system integration, Obsidian/Cursor-inspired UI, .md-based agent management

---

## Executive Summary

What you're describing isn't an enhancement to the current Hestia — it's a platform pivot. The current Hestia is a **mobile-first chat assistant** (iOS SwiftUI + FastAPI backend). What you're proposing is a **desktop AI workspace** with panels, tabs, file trees, and IDE-level context management. That's a fundamentally different product category.

**The honest assessment:** The backend (FastAPI, memory, inference, tools) is largely reusable. The iOS app is not — you'd be building a new frontend from scratch. The .md-based agent config system is a better paradigm than what exists today, but it replaces (not extends) the current agent architecture.

**Viability: Yes, but with eyes open about scope.** This is a 3-6 month rebuild of the frontend and agent layer, not a feature sprint.

---

## What You're Actually Asking For

Let me restate the proposal in concrete terms, because the gap between current state and target state matters:

### Current Hestia
- iOS chat app with mode switching (@tia/@mira/@olly)
- Single conversation pane with gradient backgrounds
- Settings screens for cloud providers, integrations, health
- 3 fixed agent slots stored in SQLite
- Apple ecosystem tools via CLI wrappers (Calendar, Reminders, Notes, Mail read-only)
- Memory as semantic search over conversation chunks

### Proposed Hestia
- Desktop workspace with multi-panel layout (Obsidian-style sidebars + Cursor-style chat)
- Tabs for Chat/Tasks, Calendar, Mail & iMessage, Notes/Research
- Deep file system integration (browse, tag, reference files in context)
- Context injection via tab selection, text highlighting, file tagging (@-mentions)
- 10+ .md config files per agent defining personality, rules, tools, memory, heartbeat
- Agent self-maintenance (agents read/write their own config)

These are **different products**. The question isn't "can we add these features?" — it's "what do we keep, what do we rebuild, and on what platform?"

---

## Platform Decision: The Fork in the Road

This is the single biggest decision, and everything else flows from it.

### Option A: Native macOS App (Swift/AppKit or SwiftUI)

**Pros:**
- Reuses your Swift knowledge and existing DesignSystem tokens
- Native macOS file system access (no sandbox fighting)
- Direct EventKit, HealthKit, Contacts, Messages framework access
- Best performance for panels, split views, drag-and-drop
- Can share models/services with existing iOS app

**Cons:**
- SwiftUI on macOS is weaker than on iOS for complex layouts (split views, sidebars, custom panels)
- AppKit is powerful but verbose — steeper learning curve
- No cross-platform story (locks you into Apple)
- Building an Obsidian-quality panel system in Swift is significant effort

**Effort:** 4-6 months for the frontend alone

### Option B: Electron/Tauri (TypeScript + React/Svelte)

**Pros:**
- Obsidian and Cursor are both Electron apps — you'd be building in the same paradigm
- Rich ecosystem for panels, tabs, file trees, split views (VS Code extensions, Monaco editor)
- Cross-platform by default
- Faster UI iteration (hot reload, CSS flexibility)
- Markdown rendering is trivial (it's the web)

**Cons:**
- Abandons Swift investment entirely for the frontend
- Apple ecosystem integration requires a bridge layer (Node → Python backend → CLI tools)
- Memory overhead (Electron is hungry)
- Two languages/runtimes to maintain (TS frontend + Python backend)

**Effort:** 3-5 months (faster UI iteration, but bridge layer adds complexity)

### Option C: Enhanced iOS + Companion macOS Menu Bar App

**Pros:**
- Preserves existing iOS app investment
- Mac menu bar app handles file system integration
- Incremental — doesn't require a full rewrite
- iOS app gets panel improvements (iPadOS split view)

**Cons:**
- iOS will never feel like Obsidian/Cursor — the paradigm doesn't fit mobile
- Split attention between two apps
- File system integration on iOS is fundamentally limited
- Doesn't deliver the unified workspace vision

**Effort:** 2-3 months, but delivers a compromised version

### Recommendation

If you're serious about the Obsidian/Cursor vision: **Option A (native macOS)** or **Option B (Electron/Tauri)**. Option C won't get you there.

The choice between A and B depends on whether you value Apple-native integration (Option A) or UI flexibility and speed of iteration (Option B). Given your existing Swift investment and the deep Apple ecosystem integration (Calendar, Reminders, Notes, Mail, HealthKit), **Option A is probably the right call** — but expect SwiftUI panel management to be the hardest part.

---

## Component-by-Component Viability

### 1. Unified Interface with Tabs (Chat/Tasks, Calendar, Mail & iMessage, Notes/Research)

**Current state:** Separate views in iOS app (ChatView, CommandCenterView, SettingsView with IntegrationsView).

**Gap:** These are currently isolated screens with no cross-referencing. The proposal wants them as persistent tabs in a workspace where context flows between them.

**Viability: HIGH, but requires new frontend.**

The backend already has endpoints for all of these:
- Chat: `/v1/chat`, `/v1/sessions`
- Tasks: `/v1/tasks` (6 endpoints, full CRUD + approval)
- Calendar: Apple CLI tools + CalendarService
- Mail: Apple CLI tools (read-only currently)
- Notes: Apple CLI tools
- iMessage: Not currently integrated (new capability needed)

**What's needed:**
- macOS app with tab-based navigation (NSTabView or custom)
- Sidebar panel system (file tree on left, context/tools on right)
- Cross-tab context awareness (selecting a calendar event should be referenceable from chat)
- iMessage integration via Messages.framework or AppleScript bridge
- Mail write capability (currently read-only)

**iMessage is the riskiest piece.** Apple heavily restricts programmatic iMessage access. AppleScript can read Messages.app, but sending requires accessibility permissions and is fragile. There's no official API.

### 2. Deep File System Integration

**Current state:** Minimal. SandboxConfig allows access to `~/Documents`, `~/Desktop`, iCloud Drive. No file browsing, searching, or tagging tools exposed.

**Viability: HIGH on macOS, LOW on iOS.**

On macOS, this is straightforward:
- File tree browser (NSOutlineView or SwiftUI List with FileManager)
- File search (Spotlight/NSMetadataQuery for fast indexed search)
- File tagging (macOS extended attributes — `xattr` supports custom tags natively)
- File content preview (Quick Look integration)
- Drag-and-drop files into chat context

**What's needed:**
- New `filesystem/` backend module with tools: read, write, search, list, tag
- macOS frontend file browser component
- Context injection pipeline (selected file → added to chat context → sent with next message)
- Sandbox expansion (or no sandbox on macOS, since it's your own machine)

### 3. Obsidian/Cursor-Inspired UI

**Obsidian patterns to adopt:**
- Left sidebar: file tree + navigation
- Right sidebar: context panels (memory search results, related conversations, tool status)
- Main area: active tab content (chat, calendar, notes, etc.)
- Graph view: memory chunk relationships (you already have NeuralNetViewModel doing 3D graph visualization — this could be adapted)
- Backlinks: "which prior conversations reference this topic?" — memory search already supports this via tag-based queries

**Cursor patterns to adopt:**
- @-mention system: `@file:budget.xlsx`, `@calendar:tomorrow`, `@memory:project-hestia`
- Tab/selection context: highlighted text or active tab automatically included in chat context
- Plan mode: show what the agent intends to do before executing (task approval flow already exists)
- .rules file: persistent agent configuration (maps directly to your .md config proposal)

**Viability: MEDIUM-HIGH.** The interaction patterns are well-understood. The challenge is building the panel system and context pipeline in Swift, which is doable but labor-intensive.

### 4. Context Injection (Tab Selection, Highlighting, File Tagging)

**Current state:** No context injection mechanism. Chat messages are standalone text.

**This is the most architecturally significant change.** It requires:

1. **Context model:** A new data structure representing "what the user is looking at right now"
   ```
   ChatContext:
     - active_tab: "calendar" | "notes" | "chat" | ...
     - selected_text: Optional[str]
     - tagged_files: List[FilePath]
     - tagged_memories: List[MemoryChunkID]
     - referenced_events: List[CalendarEventID]
     - referenced_messages: List[iMessageID]
   ```

2. **Context pipeline:** Before sending a chat message, the app bundles the ChatContext and sends it alongside the message to `/v1/chat`

3. **Backend context handling:** PromptBuilder needs to incorporate context items into the system prompt or user message (similar to how Cursor injects @-referenced files)

4. **Smart chunking:** Large files need to be chunked intelligently (not dumped wholesale into context). The memory system's existing chunking logic could be adapted.

**Viability: HIGH.** This is well-understood engineering. The backend's PromptBuilder already constructs prompts from multiple sources (memory, mode instructions, user preferences). Adding a context injection layer is a natural extension.

**New API contract:**
```json
POST /v1/chat
{
  "message": "What should I prioritize today?",
  "context": {
    "active_tab": "calendar",
    "tagged_files": ["/Documents/Q1-goals.md"],
    "selected_text": "Review budget by Friday",
    "referenced_events": ["evt-abc123"]
  }
}
```

---

## Agent Management System (.md Config Files)

This is the most interesting part of the proposal and the biggest philosophical shift.

### Current Agent System
- 3 fixed slots (Tia/Mira/Olly)
- Stored in SQLite via AgentProfile model
- Fields: name, instructions (5000 char limit), gradient colors, photo
- Snapshots for rollback
- Mode switching via @-mention in chat

### Proposed Agent System
Ten .md files per agent, each serving a distinct purpose:

| File | Purpose | Maps to Current... |
|------|---------|-------------------|
| AGENT.md | Operating rules, priorities, quality bar | `instructions` field (partial) |
| ANIMA.md | Personality, voice, values, behavioral constraints | `instructions` field (partial) |
| USER.md | User preferences, timezone, communication style | UserProfile + UserSettings |
| IDENTITY.md | Name, emoji, avatar, vibe | AgentProfile name + colors + photo |
| TOOLS.md | Machine-local notes: paths, SSH hosts, environment | SandboxConfig + execution.yaml |
| HEARTBEAT.md | Recurring checklist evaluated every 30 min | Orders system (scheduled prompts) |
| BOOT.md | Startup ritual on restart | Server initialization in server.py |
| MEMORY.md | Curated long-term memory, agent-maintained | Memory system (ChromaDB + SQLite) |
| BOOTSTRAP.md | One-time onboarding interview, deleted after | No equivalent |
| memory/YYYY-MM-DD.md | Daily working notes, auto-created | No equivalent (sessions exist but different) |

### Viability Assessment

**The paradigm is sound.** This is essentially what Claude Code does with CLAUDE.md, and what Cursor does with .cursorrules. File-based agent config is more transparent, version-controllable, and user-editable than database records.

**However, there are important design tensions:**

**1. File-based vs. Database-backed**

Current agents live in SQLite. The .md approach puts config in the file system. You need to decide: are .md files the source of truth, or are they a view into the database?

- **File-as-truth** (Obsidian model): Agent reads .md files directly. User edits them in any text editor. Simple, transparent, git-friendly. But: no validation, no schema migration, no atomic updates.
- **DB-as-truth with .md sync** (hybrid): Database remains authoritative. .md files are generated/synced. Editing .md triggers DB update. More robust but more complex.

**Recommendation:** File-as-truth for config files (AGENT.md, ANIMA.md, IDENTITY.md, TOOLS.md, USER.md) and DB-as-truth for runtime data (MEMORY.md, daily notes, heartbeat state). The config files change rarely and benefit from human editability. The runtime data changes constantly and needs query performance.

**2. Agent Self-Maintenance**

MEMORY.md says "agent-maintained" and daily notes are "auto-created." This means the agent needs write access to its own config directory. Currently, the backend has no mechanism for the inference layer to write files.

**What's needed:**
- New tool: `write_agent_file(agent_slot, filename, content)`
- Permission model: agents can write to their own directory, not others'
- Lifecycle hooks: on_boot (reads BOOT.md), on_heartbeat (evaluates HEARTBEAT.md every 30 min), on_session_end (updates MEMORY.md)

**3. HEARTBEAT.md — The Most Novel Piece**

A recurring checklist evaluated every 30 minutes is essentially a cron job that triggers inference. This maps nicely to the existing Orders system (APScheduler + scheduled prompts), but with a twist: the checklist is in a .md file, not a database record.

**Implementation path:**
- Orders system creates a recurring job per agent
- Job reads HEARTBEAT.md, passes it to inference as a prompt
- Agent evaluates checklist, takes actions (or reports status)
- Results written to daily notes

**4. BOOTSTRAP.md — Onboarding Flow**

A one-time interview that configures the agent, then deletes itself. This is a guided setup wizard driven by a markdown template.

**Implementation:** Backend reads BOOTSTRAP.md, uses it as a system prompt for a special "onboarding" session. User answers questions. Responses populate USER.md, ANIMA.md, etc. BOOTSTRAP.md is deleted.

### Effort Estimate for Agent System

- File-based config loading: 1-2 weeks
- Agent self-maintenance (write tools, lifecycle hooks): 2-3 weeks
- Heartbeat system (30-min cron + inference): 1 week (builds on Orders)
- Bootstrap onboarding flow: 1 week
- Migration from current 3-slot system: 1 week
- **Total: 6-8 weeks**

---

## Gap Analysis Summary

| Capability | Current State | Target State | Gap Size |
|-----------|--------------|-------------|----------|
| Platform | iOS only | macOS workspace (+ iOS) | **LARGE** — new app |
| Layout | Single-pane chat | Multi-panel workspace | **LARGE** — new frontend |
| File system | Minimal sandbox access | Deep browsing/tagging/search | **MEDIUM** — new module |
| Agent config | 3 SQLite slots | 10 .md files per agent | **MEDIUM** — new paradigm |
| Context injection | None | Tab/selection/file/@ tagging | **MEDIUM** — new pipeline |
| Calendar/Tasks | CLI tools + API | Integrated tab with cross-ref | **SMALL** — frontend work |
| Mail | Read-only CLI | Read/write integrated tab | **SMALL-MEDIUM** — add write |
| iMessage | Not integrated | Integrated tab | **MEDIUM** — Apple restrictions |
| Notes/Research | CLI tools | Obsidian-style linked notes | **MEDIUM-LARGE** — new UX |
| Memory graph | 3D NeuralNet viz | Obsidian-style backlinks | **SMALL** — adapt existing |
| Agent self-maintenance | Not possible | Write own config + daily notes | **MEDIUM** — new tools |
| Heartbeat | Orders system exists | 30-min .md-driven cron | **SMALL** — extend Orders |

---

## What You Keep (Backend Reuse)

The good news: **~80% of the Python backend transfers directly.**

- Inference layer (local + cloud routing, council) — unchanged
- Memory system (ChromaDB + SQLite + temporal decay) — extended, not replaced
- Tool execution (registry, sandbox, gating) — add new tools, keep framework
- API server (FastAPI, JWT auth, middleware) — add new endpoints
- Apple ecosystem tools — keep CLI wrappers, add iMessage + Mail write
- Security (Keychain, Fernet, biometric) — unchanged
- Health data (HealthKit sync, coaching) — unchanged
- Orders/scheduling — extend for heartbeat
- Agent profiles — migrate from DB to file-based, keep snapshot logic

**What you rebuild:**
- Entire frontend (new macOS app, or rethought iOS app)
- Agent configuration layer (file-based loading, validation, lifecycle hooks)
- Context injection pipeline (new concept entirely)
- Chat API contract (add context parameter)

---

## Recommended Phasing

### Phase 1: Foundation (4-6 weeks)
- Decide platform (macOS native vs Electron)
- Build basic workspace shell (tabs, left sidebar, right sidebar, main content area)
- Port chat functionality to new frontend
- Implement file-based agent config loading (AGENT.md, ANIMA.md, IDENTITY.md)

### Phase 2: Context & Files (4-6 weeks)
- Deep file system integration (browser, search, tagging)
- Context injection pipeline (@-mentions, tab selection, file tagging)
- Updated chat API contract with context parameter
- PromptBuilder context incorporation

### Phase 3: Integrated Tabs (4-6 weeks)
- Calendar tab (EventKit direct access on macOS)
- Notes/Research tab (local markdown files with linking)
- Mail tab (read + write)
- iMessage tab (AppleScript bridge, with known limitations)
- Tasks tab (existing backend, new frontend)

### Phase 4: Agent Intelligence (3-4 weeks)
- Agent self-maintenance tools (write config, daily notes)
- HEARTBEAT.md evaluation loop
- BOOT.md startup rituals
- BOOTSTRAP.md onboarding flow
- MEMORY.md agent-curated long-term memory
- USER.md and TOOLS.md population

### Phase 5: Polish & Migration (2-3 weeks)
- Migrate existing Tia/Mira/Olly configs to .md format
- Memory graph visualization (adapt NeuralNet view)
- Backlinks / related conversations panel
- iOS app updates (if maintaining mobile client)

**Total: 17-25 weeks (4-6 months)**

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| iMessage integration blocked by Apple | High | Medium | Fall back to read-only via AppleScript; note limitation |
| SwiftUI panel system insufficient for Obsidian-level UX | Medium | High | Use AppKit for window management, SwiftUI for content |
| Scope creep (each tab becomes its own app) | High | High | MVP each tab — read-only first, then add write capabilities |
| Agent self-maintenance produces garbage | Medium | Medium | Validation layer on .md writes; human review gate |
| 6 hours/week insufficient for this scope | High | High | Prioritize ruthlessly; Phase 1 is the gatekeeper |

---

## Bottom Line

**Is this viable?** Yes. The backend is solid and ~80% reusable. The agent .md system is a better paradigm than what exists. The Obsidian/Cursor interaction patterns are well-understood and implementable.

**Is this a small project?** No. This is a 4-6 month platform rebuild of the frontend and agent layer. The backend changes are incremental, but you're building a new app.

**Should you do it?** That depends on whether the current iOS chat interface is limiting what Hestia can be for you. If you find yourself wanting to reference files, see your calendar alongside chat, and give agents richer configuration — then yes, this is the right evolution. If the mobile chat is working fine for daily use, consider a more targeted enhancement (add file tools, add @-mentions to existing chat, migrate to .md agent config) without the full workspace rebuild.

**The .md agent config system is worth doing regardless of the UI decision.** It's a better paradigm, it's independently valuable, and it can be implemented on the current backend in 6-8 weeks without touching the frontend.
