# Hestia Workspace — Development Plan

**Version:** 2.0 (Workspace Revamp)
**Created:** 2026-02-22
**Status:** PROPOSED — Pending Andrew's approval
**Approach:** Quality over speed, phased delivery, each phase independently usable

---

## Vision

Transform Hestia from a mobile chat assistant into a multi-platform AI workspace. The macOS desktop app is the flagship: a three-panel layout (sidebar → canvas → chat) inspired by Obsidian and Cursor, with deep file system integration, N-agent management via .md config files, and context-aware chat that sees what you're working on.

iPad and iPhone adapt the same architecture to their form factors. The existing FastAPI backend remains the intelligence layer, extended with new capabilities.

---

## Confirmed Design Decisions

| Decision | Choice | ADR |
|----------|--------|-----|
| Platform | macOS primary + iPad + iPhone | ADR-024 |
| macOS frontend | AppKit shell (NSSplitViewController) + SwiftUI content panels | ADR-025 |
| iOS frontend | SwiftUI adaptive layout (iPad 2-panel, iPhone chat-first) | ADR-025 |
| Layout | Left sidebar (tabs + folder tree) → Center canvas (tabs + split panes) → Right chat (collapsible) | ADR-026 |
| Chat role | Persistent companion panel, collapsible via shortcut. Not a tab. | ADR-026 |
| Agent model | N agents, user-created. Tia/Mira/Olly as defaults. iCloud-synced. | ADR-027 |
| Agent config | 10 .md files per agent in `~/Library/Mobile Documents/` | ADR-027 |
| Config editing | Hybrid: in-app GUI + chat-driven + direct file editing | ADR-027 |
| File system | Full management: browse, create, move, rename, delete, tag | ADR-028 |
| Notes | Apple Notes integrated + file system folder tree, RTF, multi-file, custom panels | ADR-029 |
| Calendar | Full EventKit integration as canvas tab | ADR-029 |
| Mail | Read + write | ADR-029 |
| iMessage | Read-only acceptable, full CRUD ideal | ADR-029 |
| Health | Dedicated tab + proactive context in chat/briefings. Backend already complete. | ADR-029 |
| Context injection | @ mentions + drag-and-drop + active panel soft-context | ADR-030 |
| Heartbeat | General-purpose 30-min agent checklist (inbox, tasks, system, custom) | ADR-031 |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        macOS App (AppKit + SwiftUI)                     │
│  ┌───────────┐  ┌──────────────────────────┐  ┌──────────────────────┐ │
│  │  LEFT      │  │   CENTER CANVAS           │  │  RIGHT CHAT         │ │
│  │  SIDEBAR   │  │                           │  │  (collapsible)      │ │
│  │            │  │  ┌─────┬─────┬─────┐      │  │                     │ │
│  │  Tab Nav:  │  │  │Tab 1│Tab 2│Tab 3│      │  │  Agent: Tia         │ │
│  │  Calendar  │  │  ├─────┴─────┴─────┤      │  │                     │ │
│  │  Mail      │  │  │                 │      │  │  Context-aware      │ │
│  │  Notes     │  │  │  Active content │      │  │  conversation       │ │
│  │  Files     │  │  │  (split-able)   │      │  │                     │ │
│  │  Health    │  │  │                 │      │  │  Sees active canvas │ │
│  │  Agents    │  │  │                 │      │  │  + @mentions        │ │
│  │            │  │  └─────────────────┘      │  │  + drag-drop        │ │
│  │  ────────  │  │                           │  │                     │ │
│  │  Folder    │  │  Supports:                │  │  Cmd+\ to toggle    │ │
│  │  tree for  │  │  - Tabs across top        │  │                     │ │
│  │  active    │  │  - Horizontal/vert split  │  │                     │ │
│  │  tab       │  │  - Multiple items open    │  │                     │ │
│  └───────────┘  └──────────────────────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                     HTTPS (port 8443) + JWT Auth
                                    │
┌─────────────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (existing, extended)                  │
│                                                                         │
│  Existing (reuse as-is):          New/Extended:                         │
│  ├─ Inference (local + cloud)     ├─ Agent config loader (.md files)   │
│  ├─ Memory (ChromaDB + SQLite)    ├─ Context injection pipeline        │
│  ├─ Council (4-role dual-path)    ├─ File system tools (extended)      │
│  ├─ Tool execution + sandbox      ├─ iMessage reader                   │
│  ├─ Apple tools (20)              ├─ Mail write capability             │
│  ├─ Health (28 metrics, 5 tools)  ├─ Heartbeat scheduler              │
│  ├─ Security (Keychain, JWT)      ├─ Agent self-maintenance tools     │
│  ├─ Orders / scheduling           ├─ Chat context API contract        │
│  └─ Proactive / briefings         └─ Bootstrap onboarding flow        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                        iCloud Sync (agent configs)
                                    │
┌─────────────────────────────────────────────────────────────────────────┐
│  iOS App (SwiftUI adaptive)                                             │
│  ├─ iPad landscape: 2-panel (sidebar + canvas), chat slides from right │
│  ├─ iPad portrait: single panel + tab bar, sidebar as slide-over       │
│  └─ iPhone: chat-first, full-screen modals for calendar/notes/files    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 0: Foundation & Agent Config System

**Goal:** Build the .md agent config system on the backend and establish the macOS project skeleton. No functional UI yet — this is infrastructure.

**Duration estimate:** 3-4 sessions (~18-24 hours)

### 0.1 — Agent Config File System

**What:** Replace the 3-slot SQLite agent model with N-agent .md file directories in iCloud.

**Directory structure:**
```
~/Library/Mobile Documents/com~hestia~agents/
├── tia/
│   ├── AGENT.md          # Operating rules, priorities, safety, quality bar
│   ├── ANIMA.md          # Personality, voice, values, behavioral constraints
│   ├── USER.md           # User preferences, timezone, communication style
│   ├── IDENTITY.md       # Name, emoji, vibe, avatar path, gradient colors
│   ├── TOOLS.md          # Machine-local notes: paths, SSH hosts, environment
│   ├── HEARTBEAT.md      # Recurring 30-min checklist
│   ├── BOOT.md           # Startup ritual
│   ├── MEMORY.md         # Curated long-term memory (agent-maintained)
│   ├── BOOTSTRAP.md      # One-time onboarding (deleted after setup)
│   └── memory/
│       └── 2026-02-22.md # Daily working notes (auto-created)
├── mira/
│   └── ... (same structure)
├── olly/
│   └── ... (same structure)
└── .hestia-agents.yaml   # Registry: agent list, default agent, sync metadata
```

**Backend changes:**
- New module: `hestia/agents/config_loader.py` — reads .md files, validates structure, caches in memory with file-watcher for hot reload
- New module: `hestia/agents/config_writer.py` — agent self-maintenance writes (MEMORY.md, daily notes)
- Migrate `AgentProfile` model to read from .md files (IDENTITY.md fields map to name, gradient colors, photo)
- PromptBuilder updated: system prompt assembled from AGENT.md + ANIMA.md + USER.md instead of `instructions` field
- New API endpoints:
  - `GET /v1/agents` — list all agents (reads directory listing)
  - `GET /v1/agents/{name}/config/{file}` — read a specific .md file
  - `PUT /v1/agents/{name}/config/{file}` — update a .md file (GUI/chat editing)
  - `POST /v1/agents` — create new agent (scaffold directory with templates)
  - `DELETE /v1/agents/{name}` — archive agent (move to `.archived/`)
- Migration script: export current Tia/Mira/Olly from SQLite → .md file directories

**Deliverables:**
- [ ] Agent config directory structure created for Tia/Mira/Olly
- [ ] ConfigLoader reads and validates all 10 .md files
- [ ] ConfigWriter handles MEMORY.md and daily notes
- [ ] PromptBuilder assembles prompts from .md files
- [ ] API endpoints for agent CRUD and config file access
- [ ] Migration from SQLite agent profiles
- [ ] File watcher for hot-reload on config changes
- [ ] Tests for all new modules

### 0.2 — macOS Project Skeleton

**What:** Create the Xcode project for the macOS desktop app with the three-panel layout shell.

**Setup:**
- New Xcode project: `HestiaWorkspace` (macOS target, AppKit + SwiftUI)
- Shared Swift package: `HestiaShared` — models, services, API client extracted from iOS app for reuse across both targets
- xcodegen config (`HestiaWorkspace/project.yml`)
- Deployment target: macOS 15.0+ (Sequoia)

**AppKit shell:**
- `MainWindowController` (NSWindowController) — manages the three-panel window
- `MainSplitViewController` (NSSplitViewController) — left sidebar, center canvas, right chat
- Panel minimum/maximum widths, divider positions persisted in UserDefaults
- `Cmd+\` keyboard shortcut to toggle right chat panel
- `Cmd+B` keyboard shortcut to toggle left sidebar

**SwiftUI hosting:**
- Each panel hosts a SwiftUI view via `NSHostingView`
- Left sidebar: `SidebarView` (placeholder tabs + file tree)
- Center canvas: `CanvasView` (placeholder tab bar + content area)
- Right chat: `ChatPanelView` (placeholder chat interface)

**Shared infrastructure:**
- Extract from iOS app into `HestiaShared`:
  - `APIClient` + `CertificatePinning` + `NetworkMonitor`
  - All API models (`APIModels`, `AgentProfile`, `HealthModels`, etc.)
  - `DesignSystem` (Colors, Typography, Spacing — adapted for macOS)
  - `AuthService` (JWT auth, Touch ID on Mac instead of Face ID)

**Deliverables:**
- [ ] macOS Xcode project with xcodegen config
- [ ] Three-panel AppKit shell with resizable dividers
- [ ] Keyboard shortcuts for panel toggling
- [ ] SwiftUI placeholder views hosted in each panel
- [ ] HestiaShared package extracted from iOS app
- [ ] API client connecting to backend on port 8443
- [ ] Build and run on macOS with placeholder UI

### 0.3 — Context Injection Pipeline (Backend)

**What:** Extend the chat API to accept and process contextual information from the workspace.

**New chat API contract:**
```json
POST /v1/chat
{
  "message": "What should I prioritize today?",
  "agent": "tia",
  "context": {
    "active_tab": "calendar",
    "selected_text": "Review budget by Friday",
    "attached_files": [
      {"path": "/Documents/Q1-goals.md", "content_preview": "...first 500 chars..."}
    ],
    "referenced_items": [
      {"type": "calendar_event", "id": "evt-abc123", "summary": "Team sync at 9am"},
      {"type": "note", "id": "note-xyz", "title": "Project Hestia TODO"}
    ],
    "panel_context": {
      "visible_panels": ["calendar", "notes"],
      "calendar_date_range": "2026-02-22 to 2026-02-22"
    }
  }
}
```

**Backend changes:**
- New model: `ChatContext` (Pydantic) in `schemas.py`
- `PromptBuilder.build_context_block()` — formats context items into a system prompt section
- Smart chunking: files > 2000 chars get summarized or truncated with "[...truncated, ask to see more]"
- Context items included after agent personality but before conversation history
- Token budget: context gets max 30% of available context window

**Deliverables:**
- [ ] ChatContext model with validation
- [ ] PromptBuilder context block assembly
- [ ] Smart chunking for large files
- [ ] Token budget enforcement
- [ ] Updated API contract documentation
- [ ] Tests for context injection pipeline

---

## Phase 1: Chat + Calendar + Notes (macOS MVP)

**Goal:** First usable macOS workspace. Chat in the right panel talks to your agent. Calendar and Notes tabs work in the canvas. @ mentions inject context.

**Duration estimate:** 5-7 sessions (~30-42 hours)

### 1.1 — Chat Panel (Right Side)

**What:** Port the chat experience to the macOS right panel with context awareness.

**Components:**
- `ChatPanelView` (SwiftUI): message list, input bar, agent indicator
- `ChatPanelViewModel`: manages conversation state, sends messages with context
- Input bar features:
  - Text input with `Cmd+Enter` to send
  - `@` trigger: opens autocomplete popover (files, calendar events, notes, agents)
  - Drag-and-drop target: files/items dropped onto input attach as context
  - Agent switcher: click agent name/avatar to switch
- Message rendering:
  - Markdown rendering for agent responses (AttributedString or WKWebView)
  - Code blocks with syntax highlighting
  - Tool call results displayed inline
  - Typing indicator (Lottie animation, reuse from iOS)
- Context indicator: small chips above input showing attached context items (removable)

**Deliverables:**
- [ ] Chat panel with message list and input
- [ ] @ mention autocomplete popover
- [ ] Drag-and-drop context attachment
- [ ] Agent switching
- [ ] Markdown rendering in messages
- [ ] Context chips display
- [ ] Cmd+Enter send, Cmd+\ toggle panel

### 1.2 — Calendar Tab (Canvas)

**What:** Calendar view in the center canvas, integrated with EventKit on macOS.

**Left sidebar (when Calendar tab active):**
- Mini month calendar (date picker)
- Calendar list (toggle visibility per calendar, color-coded)
- Quick-create event button

**Center canvas:**
- Day view (default): hourly timeline with event blocks
- Week view: 7-column grid
- Month view: traditional calendar grid
- Event detail: click event → detail panel (or split pane)
- EventKit integration: `EKEventStore` on macOS for read/write (same API as iOS)

**Context integration:**
- Selected event(s) appear as context chips in chat input
- Drag event from calendar → drop into chat = attach as context
- Agent can reference calendar when answering ("You have a meeting at 2pm")

**Deliverables:**
- [ ] Calendar tab in left sidebar navigation
- [ ] Day/week/month views in canvas
- [ ] EventKit read/write on macOS
- [ ] Event selection → context chip in chat
- [ ] Drag event to chat for context injection
- [ ] Calendar folder tree in left sidebar (calendar list + date picker)

### 1.3 — Notes Tab (Canvas)

**What:** Apple Notes integration + file system folder tree for note browsing and editing.

**Left sidebar (when Notes tab active):**
- Folder tree showing:
  - Apple Notes folders (via existing CLI tool / AppleScript bridge)
  - Local file system folders (user-configured root directories)
- Search bar for full-text note search
- Sort options (date modified, name, manual)

**Center canvas:**
- Note viewer/editor with RTF support
- Multiple notes open as tabs across the top of canvas
- Split pane: two notes side-by-side for comparison
- Apple Notes: read/display via AppleScript extraction. Editing opens in Notes.app (Apple doesn't expose a write API for rich content)
- Local files (.md, .txt, .rtf): direct editing in canvas with save-on-blur

**Context integration:**
- Selected note text → context chip in chat
- Highlight text in a note → right-click "Ask Hestia about this" → text injected as context
- Drag note from folder tree → chat input = attach as context

**Deliverables:**
- [ ] Notes tab in left sidebar navigation
- [ ] Apple Notes folder tree via AppleScript bridge
- [ ] Local file folder tree (configurable root directories)
- [ ] RTF note viewer in canvas
- [ ] Markdown editor for local .md files
- [ ] Tab system for multiple open notes
- [ ] Split pane for side-by-side notes
- [ ] Text selection → context injection
- [ ] Search across Apple Notes + local files

### 1.4 — @ Mention System

**What:** Unified context reference system across the workspace.

**Trigger:** Typing `@` in the chat input opens an autocomplete popover.

**Namespaces:**
- `@file:` — browse/search files. Autocompletes from recent files + search.
- `@cal:` — reference calendar events. Autocompletes from today's events + search.
- `@note:` — reference notes. Autocompletes from recent notes + search.
- `@agent:` — switch agent or reference agent config. Autocompletes from agent list.
- `@memory:` — reference memory chunks. Autocompletes from recent + search.
- `@health:` — reference health data. Autocompletes from recent metrics.

**Popover behavior:**
- Fuzzy search as you type after the namespace prefix
- Up/down arrow to navigate, Enter to select, Escape to dismiss
- Selected item appears as a styled chip in the input bar
- Multiple @ references per message supported

**Backend processing:**
- @ references resolved to full content before sending to inference
- Files: content loaded and chunked (smart truncation for large files)
- Calendar events: event details (title, time, location, notes) serialized
- Notes: note content loaded and chunked
- Memory: chunk content retrieved from ChromaDB

**Deliverables:**
- [ ] @ trigger detection in chat input
- [ ] Autocomplete popover with namespace filtering
- [ ] Fuzzy search within each namespace
- [ ] Chip rendering for selected references
- [ ] Backend resolution of @ references to content
- [ ] Support for multiple @ references per message

---

## Phase 2: File System + Mail + Agent GUI

**Goal:** Full file management, mail integration, and in-app agent configuration editing. The workspace becomes a daily driver.

**Duration estimate:** 5-7 sessions (~30-42 hours)

### 2.1 — File System Tab (Canvas)

**What:** Full file management in the workspace. Browse, preview, create, move, rename, delete, tag.

**Left sidebar (when Files tab active):**
- Folder tree with expandable directories
- Configurable root directories (add/remove via settings)
- Default roots: `~/Documents`, `~/Desktop`, iCloud Drive
- Drag-and-drop reordering of root directories
- File search (Spotlight-backed via NSMetadataQuery)

**Center canvas:**
- File browser: icon view or list view (toggle)
- File preview: Quick Look integration (PDF, images, documents, code)
- File operations: right-click context menu (rename, move, copy, delete, tag)
- Create new: file, folder, markdown note
- Multi-select for batch operations
- Tags: macOS native file tags (colored dots) + custom Hestia tags stored in xattr

**Context integration:**
- Select file(s) → context chips in chat
- Drag file from browser → chat input
- "What's in this file?" works via @ mention or drag-and-drop
- Agent can suggest file operations ("You have 3 duplicates in Downloads")

**Backend extensions:**
- Extend existing iCloud file tools: `read_file`, `write_file`, `list_directory`, `search_files`
- New tools: `move_file`, `rename_file`, `delete_file`, `tag_file`, `get_file_metadata`
- Spotlight search integration via new endpoint
- File content indexing for semantic search (optional, stretch)

**Deliverables:**
- [ ] Files tab in left sidebar navigation
- [ ] Folder tree with configurable roots
- [ ] File browser (icon + list views)
- [ ] Quick Look file preview
- [ ] File operations (rename, move, copy, delete)
- [ ] macOS native tags + custom Hestia tags
- [ ] Spotlight-backed file search
- [ ] Drag-and-drop to chat for context
- [ ] New backend file management tools

### 2.2 — Mail Tab (Canvas)

**What:** Read and compose email within the workspace.

**Left sidebar (when Mail tab active):**
- Mailbox list (Inbox, Sent, Drafts, Trash, custom folders)
- Account switcher (if multiple mail accounts)
- Unread count badges

**Center canvas:**
- Message list: sender, subject, date, preview snippet
- Message detail: full email rendered (HTML email via WKWebView)
- Compose: new email / reply / forward with rich text
- Split pane: message list on left, detail on right

**Implementation approach:**
- Read: existing Mail CLI tool (AppleScript) for message listing and content
- Write: AppleScript `tell application "Mail" to make new outgoing message` — can set recipients, subject, body, then either send or open in Mail.app for review
- Alternative: direct IMAP/SMTP if AppleScript proves too limited (requires mail credentials → Keychain integration)

**Context integration:**
- Selected email → context chip in chat
- "Summarize this email thread" via @ mention
- Agent can draft replies based on email content + your communication style (from USER.md)

**Deliverables:**
- [ ] Mail tab in left sidebar navigation
- [ ] Mailbox folder tree
- [ ] Message list with search
- [ ] Email detail viewer (HTML rendering)
- [ ] Compose / reply / forward
- [ ] Email → context injection in chat
- [ ] Backend mail write capability (AppleScript or IMAP)

### 2.3 — Agent Management GUI

**What:** In-app interface for viewing and editing agent .md configs. The visual face of the agent system.

**Left sidebar (when Agents tab active):**
- Agent list: avatar, name, status indicator (active/idle)
- "Create New Agent" button
- Agent search (for when you have many)

**Center canvas — Agent Detail View:**
- Header: avatar (editable), name, emoji, gradient preview
- Tab bar for config files:
  - **Identity** (IDENTITY.md) — name, emoji, vibe, avatar, gradient colors. Form fields.
  - **Personality** (ANIMA.md) — rich text editor for personality description
  - **Rules** (AGENT.md) — rich text editor for operating rules
  - **Tools** (TOOLS.md) — key-value editor for machine-local config
  - **User** (USER.md) — form fields for preferences, timezone, communication style
  - **Heartbeat** (HEARTBEAT.md) — checklist editor (add/remove/reorder items)
  - **Boot** (BOOT.md) — text editor for startup ritual
  - **Memory** (MEMORY.md) — read-only viewer (agent-maintained), with "Clear" button
  - **Daily Notes** (memory/*.md) — date-picker + read-only viewer
- Save button: writes changes to .md files
- "Talk to configure" button: opens chat with agent, changes go through chat-driven editing

**Chat-driven editing:**
- User says: "Be more direct and less verbose"
- Agent updates its own ANIMA.md via `write_agent_file` tool
- Change reflected in GUI immediately (file watcher)

**Deliverables:**
- [ ] Agents tab in left sidebar navigation
- [ ] Agent list with create/delete
- [ ] Agent detail view with config file tabs
- [ ] Form-based editing for Identity, User, Tools, Heartbeat
- [ ] Rich text editing for Personality, Rules, Boot
- [ ] Read-only viewers for Memory and Daily Notes
- [ ] Chat-driven config editing (agent self-modification)
- [ ] File watcher → GUI refresh on external changes
- [ ] New agent creation with template scaffolding
- [ ] Agent deletion (archive to `.archived/`)

---

## Phase 3: Health Tab + Heartbeat + iMessage + iOS Adaptation

**Goal:** Complete the tab lineup, activate the heartbeat system, and bring the workspace to iPad and iPhone.

**Duration estimate:** 5-7 sessions (~30-42 hours)

### 3.1 — Health Tab (Canvas)

**What:** Health data visualization and coaching in the workspace. Backend already complete — this is purely frontend.

**Left sidebar (when Health tab active):**
- Metric categories: Activity, Heart, Body, Nutrition, Vitals, Sleep, Mindfulness
- Date range selector
- Coaching preferences shortcut

**Center canvas:**
- Dashboard: summary cards for key metrics (steps, sleep, heart rate, weight)
- Trend charts: line/bar charts for any metric over time (7d, 30d, 90d, 1yr)
- Coaching: personalized recommendations based on trends + agent's coaching preferences
- Comparison view: split pane to compare two metrics or time periods

**Implementation:**
- All data from existing `/v1/health_data/*` endpoints
- Charts: Swift Charts framework (macOS 14+) or custom SwiftUI charting
- Coaching text from existing health chat tools

**Context integration:**
- Health metric → context chip in chat ("My sleep has been bad this week, what should I adjust?")
- Agent proactively references health in briefings (already built on backend)

**Deliverables:**
- [ ] Health tab in left sidebar
- [ ] Dashboard with summary cards
- [ ] Trend charts for all metric categories
- [ ] Coaching recommendations view
- [ ] Health data → context injection in chat

### 3.2 — Heartbeat System

**What:** Activate the 30-minute recurring agent checklist from HEARTBEAT.md.

**Backend:**
- New module: `hestia/agents/heartbeat.py`
- Extends Orders system (APScheduler): creates a recurring job per agent
- Job lifecycle:
  1. Read agent's HEARTBEAT.md
  2. Parse checklist items (markdown checkboxes)
  3. For each item, evaluate: run relevant tool, check condition, or invoke inference
  4. Compile results into a heartbeat report
  5. Write summary to agent's daily notes (`memory/YYYY-MM-DD.md`)
  6. If any item triggers an alert (urgent email, missed deadline, server down), push notification

**Checklist item types:**
- `[inbox]` — check for new emails/iMessages since last heartbeat
- `[tasks]` — review open tasks, flag overdue
- `[calendar]` — upcoming events in next 2 hours
- `[system]` — server health, disk space, Ollama status
- `[custom]` — user-defined prompt evaluated by inference
- `[health]` — health metric check (e.g., "remind me to move if steps < 500 for 2 hours")

**macOS UI:**
- Menu bar indicator: green dot (all clear) / yellow (items need attention) / red (urgent)
- Click menu bar → dropdown showing last heartbeat summary
- Notification Center integration for alerts

**Deliverables:**
- [ ] Heartbeat scheduler (extends Orders/APScheduler)
- [ ] HEARTBEAT.md parser for checklist items
- [ ] Built-in checklist evaluators (inbox, tasks, calendar, system, health)
- [ ] Custom checklist items via inference
- [ ] Daily notes writer
- [ ] Push notification on alerts
- [ ] macOS menu bar indicator
- [ ] Heartbeat history viewer in Agent detail view

### 3.3 — iMessage Integration

**What:** Read iMessages within the workspace. Send if Apple allows it.

**Implementation approach:**
- Read: SQLite database at `~/Library/Messages/chat.db` (macOS stores iMessage history here). Query with `sqlite3`. Requires Full Disk Access permission.
- Alternative read: AppleScript `tell application "Messages"` — more limited but no special permissions
- Send: AppleScript `tell application "Messages" to send "text" to buddy "phone"` — works but requires accessibility permissions and is fragile across macOS versions
- Fallback for send: open Messages.app with pre-filled content via `imessage://` URL scheme

**Left sidebar (when iMessage tab active, under Mail or as sub-tab):**
- Conversation list (recent contacts)
- Search across messages

**Center canvas:**
- Conversation view: message bubbles (incoming/outgoing)
- Contact info header
- Read-only by default; send button if permissions allow

**Deliverables:**
- [ ] iMessage reader (chat.db or AppleScript)
- [ ] Conversation list in sidebar
- [ ] Message detail view in canvas
- [ ] Message search
- [ ] Send capability (best-effort, with fallback to URL scheme)
- [ ] iMessage content → context injection in chat

### 3.4 — iOS Adaptation

**What:** Bring the workspace to iPad and iPhone using the shared HestiaShared package.

**iPad (landscape):**
- `UISplitViewController` behavior: sidebar (collapsible to icons) + canvas
- Chat panel: slides in from right edge (sheet presentation or custom)
- Canvas: single item at a time (no split panes — screen too small)
- @ mentions work in chat input
- Drag-and-drop between sidebar and chat

**iPad (portrait):**
- Tab bar at bottom (Calendar, Mail, Notes, Files, Health, Chat)
- Full-screen content area
- Sidebar as slide-over sheet (swipe from left edge)
- Chat as slide-over sheet (swipe from right edge)

**iPhone:**
- Tab bar at bottom (same tabs)
- Full-screen views for each tab
- Chat is one of the tabs (not a companion panel — no room)
- @ mentions in chat input (autocomplete popover adapts to keyboard)
- Long-press items in other tabs → "Send to Chat" action

**Shared code (HestiaShared):**
- ViewModels: identical across platforms (ChatPanelViewModel, CalendarViewModel, etc.)
- API client: identical
- Models: identical
- DesignSystem: adapted tokens (macOS uses slightly different sizing)

**Platform-specific:**
- macOS: AppKit shell, keyboard shortcuts, menu bar heartbeat indicator
- iPad: UISplitViewController, slide-over panels, pencil support for notes
- iPhone: UITabBarController, full-screen navigation, compact layouts

**Deliverables:**
- [ ] iPad landscape layout (split view + chat slide-over)
- [ ] iPad portrait layout (tab bar + slide-over sheets)
- [ ] iPhone layout (tab bar + full-screen views)
- [ ] HestiaShared package consumed by both macOS and iOS targets
- [ ] @ mentions working on all form factors
- [ ] Platform-adaptive DesignSystem tokens

---

## Phase 4: Agent Intelligence + Boot/Bootstrap + Polish

**Goal:** Activate agent self-maintenance, boot rituals, onboarding, and workspace-wide polish.

**Duration estimate:** 4-5 sessions (~24-30 hours)

### 4.1 — Agent Self-Maintenance

**What:** Agents can read and write their own config files during conversation.

**New tools registered in ToolRegistry:**
- `read_agent_config(file)` — reads any .md file from the active agent's config directory
- `write_agent_config(file, content)` — writes to MEMORY.md or daily notes (restricted files)
- `append_daily_note(content)` — appends to today's `memory/YYYY-MM-DD.md`
- `update_personality(changes)` — modifies ANIMA.md (requires user confirmation)
- `update_rules(changes)` — modifies AGENT.md (requires user confirmation)

**Permission model:**
- Auto-approved: MEMORY.md, daily notes (agent's working memory)
- Requires confirmation: ANIMA.md, AGENT.md, USER.md, IDENTITY.md (personality/identity changes)
- Read-only from agent: HEARTBEAT.md, BOOT.md, TOOLS.md (user-controlled)

**Use cases:**
- "Remember that I prefer morning meetings" → agent writes to MEMORY.md
- "Be more concise" → agent updates ANIMA.md (with confirmation)
- End of conversation → agent summarizes key takeaways in daily notes

**Deliverables:**
- [ ] Agent config read/write tools in ToolRegistry
- [ ] Permission model (auto-approve vs. confirmation)
- [ ] Daily notes auto-creation and appending
- [ ] MEMORY.md curation (agent summarizes and maintains)
- [ ] User confirmation flow for personality/identity changes
- [ ] Tests for all self-maintenance tools

### 4.2 — Boot & Bootstrap

**What:** Agent startup rituals and one-time onboarding.

**BOOT.md — Startup Ritual:**
- Evaluated when the backend starts (or when an agent is first activated in a session)
- Contains a sequence of instructions the agent executes:
  - Check unread messages/emails
  - Review today's calendar
  - Read yesterday's daily notes for continuity
  - Run heartbeat checklist once
  - Compose a morning brief
- Results written to daily notes and optionally surfaced as a notification

**BOOTSTRAP.md — Onboarding:**
- Present only for newly created agents
- Contains an interview script:
  - "What should I call you?"
  - "What's your timezone?"
  - "How formal should I be?"
  - "What are your priorities right now?"
- Responses populate USER.md, ANIMA.md, and IDENTITY.md
- BOOTSTRAP.md deleted after completion, replaced with a note in MEMORY.md

**Deliverables:**
- [ ] Boot ritual evaluator (reads BOOT.md, executes steps)
- [ ] Boot results → daily notes + optional notification
- [ ] Bootstrap onboarding interview flow
- [ ] Response population into config files
- [ ] Bootstrap deletion after completion
- [ ] Tests for boot and bootstrap flows

### 4.3 — Workspace Polish

**What:** Cross-cutting quality improvements across the workspace.

**Items:**
- Keyboard shortcut system:
  - `Cmd+1..6` switch sidebar tabs
  - `Cmd+\` toggle chat panel
  - `Cmd+B` toggle sidebar
  - `Cmd+N` new item (context-sensitive: new note, new event, new file)
  - `Cmd+K` command palette (Spotlight-style, searches across all content)
  - `Cmd+Shift+F` global search
- Command palette: unified search across files, notes, calendar events, messages, memory, agents
- Drag-and-drop polish: visual feedback (highlight drop targets, preview cards)
- Preferences window:
  - General: default agent, startup behavior, appearance (light/dark/system)
  - Connections: backend URL, Tailscale, certificate management
  - File roots: configure which directories appear in Files tab
  - Keyboard shortcuts: customizable bindings
- Window state persistence: panel sizes, active tab, open files restored on relaunch
- Spotlight/Alfred integration: "hestia" trigger opens workspace or sends quick query

**Deliverables:**
- [ ] Full keyboard shortcut system
- [ ] Command palette with cross-content search
- [ ] Drag-and-drop visual polish
- [ ] Preferences window
- [ ] Window state persistence
- [ ] Menu bar integration (heartbeat + quick actions)

---

## Phase 5: Soft-Context + Proactive Intelligence + Stretch Goals

**Goal:** The workspace becomes anticipatory. Agents understand what you're looking at and offer help before you ask.

**Duration estimate:** 3-4 sessions (~18-24 hours)

### 5.1 — Active Panel Soft-Context

**What:** The agent automatically sees what's visible in your canvas panels and uses it as background context.

**How it works:**
- Every 5 seconds (debounced), the workspace snapshots what's visible:
  - Calendar: currently visible date range + events
  - Notes: active note title + first 200 chars
  - Files: selected file name + type + size
  - Mail: active email subject + sender
  - Health: active metric + current value
- This snapshot is sent as `panel_context` in every chat message
- Agent weighs soft-context lower than explicit @ mentions but higher than memory search
- Privacy toggle: user can disable soft-context per tab or globally

**Deliverables:**
- [ ] Panel context snapshot system (debounced)
- [ ] Soft-context included in chat API calls
- [ ] PromptBuilder soft-context weighting
- [ ] Per-tab privacy toggle
- [ ] Visual indicator when soft-context is active

### 5.2 — Proactive Agent Suggestions

**What:** Agents surface suggestions based on context without being asked.

**Triggers:**
- You open a calendar event → agent offers to pull up related notes/files
- You read an email → agent offers to draft a reply
- You browse files → agent notices duplicates or suggests organization
- Heartbeat finds something → notification with suggested action
- Daily notes pattern detection → "You've mentioned budget 3 days in a row, want to block time for it?"

**UI:**
- Suggestion chips appear at the top of the chat panel (dismissible)
- Click a chip → expands into a chat message with the suggestion
- Agent learns from dismissed suggestions (writes to MEMORY.md: "Andrew dismissed budget suggestion")

**Deliverables:**
- [ ] Proactive suggestion engine (extends existing ProactiveManager)
- [ ] Suggestion chips in chat panel
- [ ] Dismissal tracking in agent memory
- [ ] Configurable suggestion categories (toggle per type)

### 5.3 — Stretch Goals (Future Phases)

Items deferred beyond the core plan. Tracked here for future consideration:

- **Voice input in chat panel**: microphone button, speech-to-text via macOS Dictation or Whisper
- **Reminders tab**: full Reminders.app integration (currently tools-only)
- **Contacts integration**: reference people by name in @ mentions, auto-link to emails/messages
- **Graph view**: Obsidian-style visualization of memory chunks + note links + conversation threads
- **Multi-window**: detach tabs into separate windows (e.g., calendar on second monitor)
- **Shortcuts.app integration**: Hestia actions available as Shortcuts for automation
- **Plugin system**: user-installable plugins for new tabs/tools (long-term)
- **Collaboration**: share agent configs or workspace layouts (very long-term)

---

## Testing Strategy

Each phase follows the existing Hestia testing discipline:

**Backend:**
- Unit tests for every new module (ConfigLoader, ConfigWriter, Heartbeat, Context pipeline)
- Integration tests for new API endpoints
- Migration tests (SQLite agent → .md files)
- Target: maintain 784+ passing, add ~150-200 new tests across all phases

**macOS App:**
- XCTest for ViewModels (unit tests)
- UI tests for critical flows (panel toggling, @ mentions, drag-and-drop)
- Preview verification for all SwiftUI views

**iOS App:**
- Existing test suite maintained
- New tests for adaptive layouts (iPad/iPhone)
- Shared ViewModel tests run on both targets

**Cross-platform:**
- API contract tests: ensure macOS and iOS apps send identical request formats
- iCloud sync tests: verify agent config changes propagate between devices

---

## Migration Path

**From current Hestia to Workspace:**

1. Backend changes are additive — existing iOS app continues to work throughout
2. Agent config migration: script exports SQLite → .md files. Old API endpoints preserved with deprecation warnings. New endpoints added alongside.
3. iOS app updated incrementally: HestiaShared extraction doesn't change behavior, just code organization
4. macOS app developed in parallel — no disruption to current iOS usage
5. Cutover: once macOS app is functional (Phase 1 complete), it becomes primary. iOS app transitions to companion role.

**No big bang.** At every point, the current system works. New capabilities are additive.

---

## Estimated Total Effort

| Phase | Sessions | Hours | Delivers |
|-------|----------|-------|----------|
| 0: Foundation | 3-4 | 18-24 | Agent .md system, macOS skeleton, context pipeline |
| 1: Chat + Calendar + Notes | 5-7 | 30-42 | Usable macOS MVP |
| 2: Files + Mail + Agent GUI | 5-7 | 30-42 | Daily-driver workspace |
| 3: Health + Heartbeat + iMessage + iOS | 5-7 | 30-42 | Complete tab lineup + mobile |
| 4: Intelligence + Boot + Polish | 4-5 | 24-30 | Self-maintaining agents, keyboard-driven UX |
| 5: Soft-Context + Proactive | 3-4 | 18-24 | Anticipatory workspace |
| **Total** | **25-34** | **150-204** | **Full Hestia Workspace** |

At ~6 hours/week: **25-34 weeks (6-8 months)**. Quality over speed — each phase is usable on its own.
