# Discovery: Full UI/UX Wiring Roadmap

**Date:** 2026-03-03
**Author:** Claude (Discovery Agent)
**Classification:** Strategic Roadmap — Sprints 7-12
**Scope:** Profile/Settings, Research, Explorer, Chat, Command — all wired to production data

---

## Executive Summary

This discovery maps the complete path from Hestia's current state (126 backend endpoints, 66 macOS files, 1258 passing tests) to a fully wired, editable, persistent, real-time application across 5 modules. Based on 20+ clarifying questions with Andrew, I've produced sprint-by-sprint implementation plans, architectural decisions, and SWOT analysis for each module.

**Key decisions made during discovery:**
- MIND.md / BODY.md: Freeform markdown editor
- Agent profiles: V2 API only, Identity + Personality tabs
- Settings: Accordion layout (Profile, Agents, Resources, Field Guide)
- Graph view: Hybrid knowledge + activity data
- Explorer: Full Finder integration + Universal inbox (Apple Mail + Gmail first)
- Chat: CLI-style input, rich output, floating avatar swap, background sessions in Orders
- Command: Week calendar, contextual metrics, health sub-dashboard, Orders with Recurring/Scheduled
- Data: Local cache + server sync pattern
- Design: Orange accent globally (matching sidebar selection state)

---

## Architecture Overview

### Data Flow Pattern (All Modules)

```
┌────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  macOS UI  │────▶│ Local Cache   │────▶│  FastAPI      │────▶│ SQLite /     │
│  (SwiftUI) │◀────│ (UserDefaults │◀────│  (Port 8443)  │◀────│ ChromaDB     │
│            │     │  + in-memory) │     │  JWT Auth      │     │ + Keychain   │
└────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

**Cache Strategy:** Local cache for read-heavy views (settings, profiles, resource lists). Writes always go to server first; cache updates on 200 response. Cache invalidation via ETag/Last-Modified headers (already supported in Sprint 6's Cache-Control work). Offline: read from cache, queue writes for retry.

### Design System Update: Orange Accent

Global replacement of system blue accent with Hestia orange across all interactive elements:
- Selected sidebar items (already orange)
- Tab toggles, buttons, segmented controls
- Focus rings, selection highlights
- Progress indicators, activity spinners
- Applies to MacColors.swift tokens: `accentPrimary`, `selectionBackground`, `interactiveHighlight`

---

## Sprint 7: Profile & Settings Restructure

### Scope
Rebuild the Settings view as a 4-section accordion (Profile, Agents, Resources, Field Guide). Wire all sections to production backend APIs. Make everything editable and persistent.

### 7.1 Settings Architecture (Accordion Layout)

```
┌─────────────────────────────────────────────┐
│  ⚙️  Settings                                │
│                                               │
│  ▼ Profile                                    │
│  ┌─────────────────────────────────────────┐ │
│  │ [Photo]  Andrew Lonati                   │ │
│  │          Edit Name / Description          │ │
│  │                                           │ │
│  │  📄 MIND.md    [Edit]                     │ │
│  │  📄 BODY.md    [Edit]                     │ │
│  │                                           │ │
│  │  Push Notifications  [Toggle]             │ │
│  │  Default Mode        [Tia ▾]              │ │
│  │  Auto-Lock           [5 min ▾]            │ │
│  └─────────────────────────────────────────┘ │
│                                               │
│  ▶ Agents                                     │
│  ▶ Resources (LLMs, Integrations, Devices)    │
│  ▶ Field Guide                                │
└─────────────────────────────────────────────┘
```

### 7.2 User Profile Section

**Backend endpoints (all exist):**
- `GET /v1/user/profile` → name, description, photo_url
- `PATCH /v1/user/profile` → update name, description
- `POST /v1/user/photo` → upload photo (multipart)
- `GET /v1/user/photo` → retrieve photo
- `DELETE /v1/user/photo` → remove photo
- `GET /v1/user/settings` → push notifications, default mode, auto-lock
- `PATCH /v1/user/settings` → update settings
- `GET /v1/user-profile/files/{file_name}` → read MIND.md, BODY.md
- `PUT /v1/user-profile/files/{file_name}` → write MIND.md, BODY.md

**New macOS components:**
| Component | Purpose | API Wired To |
|-----------|---------|-------------|
| `MacProfileView` | Main profile section in accordion | `/v1/user/profile`, `/v1/user/settings` |
| `ProfilePhotoEditor` | Photo picker + crop circle + preview + upload | `/v1/user/photo` |
| `MarkdownEditorView` | Freeform markdown editor with syntax highlighting | `/v1/user-profile/files/{name}` |
| `MacUserSettingsViewModel` | Manages profile + settings state, local cache | All user endpoints |

**Photo edit flow:**
1. Tap current photo → Sheet presents: "Choose from Library" / "Take Photo"
2. Image picker → Crop overlay (circle mask, pinch-to-zoom)
3. Preview with "Cancel" / "Save"
4. On save: `POST /v1/user/photo` with compressed JPEG
5. On success: Update cache + UI, animate transition

**Markdown editor (MIND.md / BODY.md):**
- Full-width text editor with monospace font
- Live markdown preview toggle (edit ↔ preview)
- Auto-save on blur/close (debounced 2s) via `PUT /v1/user-profile/files/{name}`
- Undo/redo support
- Syntax highlighting for headers, lists, bold, code blocks

### 7.3 Agent Profiles Section

**Backend endpoints (V2 only — V1 becomes legacy):**
- `GET /v2/agents` → list all agents
- `GET /v2/agents/{name}` → get agent config
- `GET /v2/agents/{name}/files/IDENTITY.md` → name, emoji, vibe, colors, temperature
- `PUT /v2/agents/{name}/files/IDENTITY.md` → update identity
- `GET /v2/agents/{name}/files/ANIMA.md` → personality, instructions
- `PUT /v2/agents/{name}/files/ANIMA.md` → update personality

**New macOS components:**
| Component | Purpose |
|-----------|---------|
| `MacAgentsView` | Grid of 3 agent cards in accordion section |
| `AgentCardView` | Photo + name + emoji + vibe summary |
| `AgentDetailSheet` | Two-tab editor: Identity / Personality |
| `AgentIdentityEditor` | Name, emoji picker, vibe text, color pickers, temperature slider |
| `AgentPersonalityEditor` | Markdown editor for ANIMA.md (instructions, focus areas) |
| `MacAgentsViewModel` | V2 API integration, local cache |

**New macOS service extension:**
- `APIClient+AgentsV2.swift` — wraps all V2 agent endpoints

**Agent card layout:**
```
┌──────────────────────┐
│  [Photo]   Tia       │
│            🌊         │
│  "Sardonic daily ops" │
│                       │
│  [Identity] [Persona] │
└──────────────────────┘
```

### 7.4 Resources Section (Consolidation)

**Replaces:** Existing Cloud Settings view + Integrations view + separate Resources tab

**Sub-sections within Resources accordion:**
1. **LLMs** — Cloud providers (Anthropic, OpenAI, Google), model selection, state toggle
   - Wired to: `/v1/cloud/providers/*` (7 endpoints)
2. **Integrations** — Calendar, Reminders, Notes, Mail, HealthKit status
   - Wired to: `/v1/tools` (dynamic discovery)
3. **Devices** — Registered devices, revoke/unrevoke
   - Wired to: `/v1/user/devices`, `/v1/user/devices/{id}/revoke`
4. **MCPs** — Future MCP server connections (placeholder for now)

**Existing macOS views to migrate/refactor:**
- `MacCloudSettingsView` → becomes LLMs sub-section
- `MacIntegrationsView` → becomes Integrations sub-section
- `ResourcesView` (6 files) → consolidated into sub-sections

### 7.5 Field Guide Section

**Migrates from:** Dedicated Wiki tab → Settings accordion section

**Existing macOS views to relocate:**
- `MacWikiView` — article list with type filters
- `MacWikiArticleListView` — filtered article grid
- `MacWikiArticleDetailView` — full article reader
- `MacWikiDiagramView` — Mermaid diagram renderer

**Navigation:** Full navigation stack preserved inside the accordion section. Expanding "Field Guide" shows the article list; tapping an article pushes to detail view within the section.

**Backend:** `/v1/wiki/*` (6 endpoints) — all exist and are wired via `APIClient+Wiki.swift`

### Sprint 7 Effort Estimate

| Task | Backend | macOS | Tests | Days |
|------|---------|-------|-------|------|
| Settings accordion shell | — | New view | — | 1 |
| Profile section + photo editor | — | 3 new views | 5 | 2 |
| MIND.md / BODY.md markdown editor | — | 1 reusable view | 3 | 2 |
| Agent profiles (V2 wiring) | — | 4 new views + VM | 8 | 3 |
| Resources consolidation | — | Refactor 6→3 views | 5 | 2 |
| Field Guide migration | — | Move 4 views | 2 | 1 |
| Orange accent global update | — | MacColors + all views | — | 1 |
| Cache layer for settings | — | UserDefaults wrapper | 3 | 1 |
| **Total** | **0 new endpoints** | **~12 new/refactored views** | **~26 tests** | **~13 days** |

---

## Sprint 8: Research & Graph View

### Scope
Wire the Neural Net graph to real hybrid data (knowledge + activity), fix Explorer loading, and establish the research view as a genuine intelligence dashboard.

### 8.1 Graph View: Hybrid Knowledge + Activity

**Current state:** 3D SceneKit visualization with demo data (NeuralNetView in macOS).

**Target state:** Real-time graph where:
- **Knowledge nodes** = Memory chunks (topics, entities, decisions) from ChromaDB
- **Activity nodes** = Tools used, integrations triggered, orders executed
- **Edges** = Co-occurrence (same session), semantic similarity, causal chains

**New backend endpoints needed:**

```
GET /v1/research/graph
  ?node_types=knowledge,activity  (filter)
  &depth=2                         (hop distance from center)
  &limit=200                       (max nodes)
  &center_topic=health             (optional focus)

Response:
{
  "nodes": [
    {"id": "...", "type": "knowledge|activity", "label": "Budget Review",
     "category": "finance", "weight": 0.85, "last_active": "2026-03-01",
     "metadata": {"chunk_type": "decision", "source": "conversation"}},
    {"id": "...", "type": "activity", "label": "Calendar Check",
     "category": "tool", "weight": 0.6, "frequency": 45,
     "metadata": {"tool_name": "apple_calendar_today"}}
  ],
  "edges": [
    {"source": "...", "target": "...", "type": "co_occurrence|similarity|causal",
     "weight": 0.7, "count": 12}
  ],
  "clusters": [
    {"id": "health", "label": "Health & Fitness", "node_ids": [...], "color": "#..."}
  ]
}
```

**New backend module: `hestia/research/`**

```
hestia/research/
├── __init__.py
├── models.py          # GraphNode, GraphEdge, GraphCluster, GraphResponse
├── graph_builder.py   # Queries memory + tools + orders, builds graph
├── manager.py         # ResearchManager (singleton pattern)
└── database.py        # Optional: cache computed graphs in SQLite
```

**Graph data pipeline:**
1. Query ChromaDB for top-N memory chunks (knowledge nodes)
2. Query tool execution logs for tool usage frequency (activity nodes)
3. Query order execution history for order nodes
4. Compute edges: co-occurrence from session IDs, semantic similarity from embeddings, causal from temporal sequence
5. Run community detection (Louvain or label propagation) for clusters
6. Cache result with TTL (5 min) — graph doesn't need real-time updates

**macOS components:**
| Component | Purpose |
|-----------|---------|
| `MacResearchView` | Container for graph + controls |
| `NeuralNetGraphView` | Refactored SceneKit view consuming real `GraphResponse` |
| `GraphControlPanel` | Filters (node types, depth, focus topic), layout toggles |
| `NodeDetailPopover` | Tap a node → see details, related memories, actions |
| `MacResearchViewModel` | Fetches graph data, manages filters, caching |

**New macOS service:**
- `APIClient+Research.swift` — wraps `/v1/research/graph`

### 8.2 Explorer Fix (Not Loading)

**Diagnosis needed:** The Explorer view exists (`MacExplorerView`, `MacExplorerResourcesView`) and the backend has 6 endpoints. The "not loading" issue is likely one of:
1. Missing `APIClient+Explorer.swift` service extension (need to verify)
2. ViewModel not calling the right endpoint
3. Backend ExplorerManager not initialized (check server startup)

**Action:** Phase 1 Research — run `@hestia-explorer` to trace the exact failure, then fix.

### Sprint 8 Effort Estimate

| Task | Backend | macOS | Tests | Days |
|------|---------|-------|-------|------|
| Research module (graph_builder, models, manager) | New module | — | 15 | 3 |
| `/v1/research/graph` endpoint | New route | — | 5 | 1 |
| NeuralNet refactor (real data) | — | Refactor 1 view | 3 | 2 |
| Graph controls + node detail | — | 2 new views | 3 | 1 |
| Explorer loading fix | Debug | Debug | 2 | 1 |
| APIClient+Research.swift | — | New service | 2 | 1 |
| **Total** | **~1 new module, 1 new route** | **~4 views** | **~30 tests** | **~9 days** |

---

## Sprint 9: Explorer — Files & Inbox

### Scope
Build the full Explorer with two modes: Files (Finder integration + Notes) and Inbox (Email + Reminders + Notifications). Full CRUD. Orange selected-tab accent.

### 9.1 Files Tab (Finder Integration)

**Architecture: macOS File System Access**

The Mac Mini runs the backend with full filesystem access. The approach:

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────┐
│  macOS Explorer  │────▶│  /v1/explorer/    │────▶│  Python      │
│  Files View      │◀────│  files/*          │◀────│  os/pathlib  │
│                  │     │  (New endpoints)   │     │  + Apple CLI │
└─────────────────┘     └──────────────────┘     └──────────────┘
```

**New backend endpoints:**

```
GET    /v1/explorer/files
  ?path=/Users/andrew/Documents    (directory to list)
  ?show_hidden=false               (respect user's hide preferences)
  ?sort_by=name|date|size|type
  Response: { files: [FileEntry], path: str, parent_path: str }

GET    /v1/explorer/files/content
  ?path=/Users/andrew/file.md      (file to read)
  Response: { content: str, mime_type: str, size: int, modified: datetime }

POST   /v1/explorer/files
  { path: str, name: str, content: str, type: "file"|"directory" }
  → Create file or directory

PUT    /v1/explorer/files
  { path: str, content: str }
  → Update file content

DELETE /v1/explorer/files
  { path: str }
  → Delete file (move to Trash, not permanent)

POST   /v1/explorer/files/move
  { source: str, destination: str }
  → Move/rename file

GET    /v1/explorer/files/hidden-paths
  Response: { paths: [str] }
  → User's hidden folder list

PUT    /v1/explorer/files/hidden-paths
  { paths: [str] }
  → Update hidden folder list
```

**Security considerations:**
- Path traversal protection (validate all paths are under allowed roots)
- Configurable root directories (user picks which folders are visible)
- Dangerous paths blacklisted (`/System`, `/Library`, `~/.ssh`, etc.)
- Delete = move to macOS Trash (recoverable), not `rm`
- File size limits for content reads (e.g., 10MB max for text preview)

**Notes integration:**
- Already exists via Apple CLI tools (`hestia-cli-tools/`)
- Endpoint: `GET /v1/explorer/resources?type=note`
- CRUD via existing tool execution pipeline

**macOS components:**
| Component | Purpose |
|-----------|---------|
| `ExplorerFilesView` | File browser with breadcrumb nav, list/grid toggle |
| `FileRowView` | Icon + name + size + date for each file |
| `FilePreviewSheet` | Quick Look-style preview for common file types |
| `FileEditorView` | In-app text editor for markdown, txt, code files |
| `HiddenPathsSheet` | Configure which folders to hide from default view |

### 9.2 Inbox Tab (Unified Email + Reminders + Notifications)

**Architecture:**

```
Phase 1: Apple Mail (existing CLI) + Gmail (new OAuth2 module)
Phase 2: Outlook (future sprint)
```

**New backend module: `hestia/email/`**

```
hestia/email/
├── __init__.py
├── models.py          # EmailMessage, EmailAccount, EmailThread, Attachment
├── providers/
│   ├── __init__.py
│   ├── base.py        # BaseEmailProvider ABC
│   ├── apple_mail.py  # Wraps existing Apple CLI mail tool
│   └── gmail.py       # Google Gmail API (OAuth2)
├── manager.py         # EmailManager (aggregates all providers)
├── database.py        # SQLite cache for emails (offline support)
└── oauth.py           # OAuth2 flow helper (Gmail, future Outlook)
```

**New backend endpoints:**

```
GET    /v1/inbox/messages
  ?provider=all|apple_mail|gmail
  ?folder=inbox|sent|drafts|trash
  ?unread_only=true
  ?limit=50&offset=0
  Response: { messages: [EmailMessage], total: int, unread_count: int }

GET    /v1/inbox/messages/{message_id}
  Response: { message: EmailMessage, thread: [EmailMessage], attachments: [Attachment] }

POST   /v1/inbox/messages
  { to: [str], subject: str, body: str, provider: str, reply_to: str? }
  → Send email

PUT    /v1/inbox/messages/{message_id}
  { read: bool?, starred: bool?, folder: str? }
  → Update message state (mark read, star, move)

DELETE /v1/inbox/messages/{message_id}
  → Move to trash

GET    /v1/inbox/accounts
  Response: { accounts: [EmailAccount] }
  → List configured email accounts

POST   /v1/inbox/accounts/gmail/authorize
  Response: { auth_url: str }
  → Initiate Gmail OAuth2 flow

POST   /v1/inbox/accounts/gmail/callback
  { code: str }
  → Complete OAuth2 flow, store refresh token in Keychain
```

**Gmail OAuth2 flow:**
1. Backend generates auth URL → macOS opens in browser
2. User authorizes → Google redirects to localhost callback
3. Backend exchanges code for tokens → stores refresh token in Keychain
4. Subsequent requests use refresh token for access tokens

**Reminders integration:**
- Already exists via Apple CLI tools
- `GET /v1/explorer/resources?type=reminder`
- CRUD via tool execution pipeline
- Show in Inbox with due dates, completion status

**Notifications:**
- Aggregate from: Hestia's own notification history (`GET /v1/proactive/notifications`)
- Push notification history from iOS/macOS
- System notifications from proactive briefings

**macOS components:**
| Component | Purpose |
|-----------|---------|
| `ExplorerInboxView` | Unified inbox: email + reminders + notifications |
| `InboxMessageRow` | Sender/subject/preview/date for each item |
| `InboxMessageDetail` | Full email/reminder view with actions |
| `InboxComposeSheet` | New email composer with account picker |
| `GmailAuthSheet` | OAuth2 authorization flow UI |
| `InboxFilterBar` | Provider filter, unread toggle, search |

### 9.3 Tab Design (Orange Accent)

```
┌───────────────────────────────────────┐
│  Explorer                              │
│                                        │
│  ┌─────────────┐ ┌─────────────┐      │
│  │   📁 Files   │ │   📥 Inbox   │      │
│  │  [SELECTED]  │ │             │      │
│  │  ▔▔▔▔▔▔▔▔▔  │ │             │      │
│  │  Orange bg   │ │  Default bg │      │
│  └─────────────┘ └─────────────┘      │
│                                        │
│  Selected = Hestia orange (#FF6B35)    │
│  Matches sidebar selection state       │
└───────────────────────────────────────┘
```

### Sprint 9 Effort Estimate

| Task | Backend | macOS | Tests | Days |
|------|---------|-------|-------|------|
| File system endpoints (7 new) | New routes | — | 20 | 3 |
| File browser UI | — | 5 new views | 5 | 3 |
| Email module + Gmail OAuth2 | New module | — | 15 | 4 |
| Inbox UI (messages, compose) | — | 5 new views | 5 | 3 |
| Gmail auth flow (macOS) | — | 1 sheet | 3 | 1 |
| Tab redesign (orange accent) | — | Style updates | — | 0.5 |
| **Total** | **~2 new modules, ~15 endpoints** | **~11 views** | **~48 tests** | **~14.5 days** |

---

## Sprint 10: Chat Redesign

### Scope
CLI-style input, rich output, floating avatar swap, remove add-session button, background sessions → Orders integration.

### 10.1 CLI-Style Input Box

**Design spec:**

```
┌─────────────────────────────────────────────────────┐
│  ┌─────────────────────────────────────────────────┐│
│  │ $ ▌                                              ││
│  │                                                  ││
│  │  (monospace · dark bg · cursor blink)            ││
│  └─────────────────────────────────────────────────┘│
│  [⌘+Enter to send]  [Shift+Enter for newline]       │
└─────────────────────────────────────────────────────┘
```

**Input features (Claude Code-inspired):**
- Monospace font (SF Mono or Menlo)
- Dark background (#1E1E1E) with light text
- `$` or `>` prompt character (configurable per agent: `$` for Olly, `~` for Tia, `?` for Mira)
- Multi-line support with Shift+Enter
- Command completion (type `/` for slash commands)
- Up-arrow for message history recall
- Syntax highlighting for code blocks in input

**Output features (rich formatting):**
- Full markdown rendering (headers, lists, tables, code blocks)
- Syntax-highlighted code with copy button
- Collapsible sections for long outputs
- Inline tool-call cards (shows what Hestia did)
- Mermaid diagram rendering
- LaTeX math rendering (if needed)

### 10.2 Floating Avatar Header

```
┌─────────────────────────────────────────────┐
│           ┌──────┐                          │
│           │ [Tia]│  ← Active speaker        │
│           │ 🌊   │     (scales up,          │
│           └──────┘      glow ring)          │
│                                              │
│  ← swaps with animation when speaker changes │
│                                              │
│  [Andrew]: Can you check my calendar?        │
│                                              │
│  [Tia]: Here's your schedule for today...    │
│                                              │
└─────────────────────────────────────────────┘
```

**Animation:**
- Avatar swap: cross-dissolve + scale (300ms ease-in-out)
- Active indicator: pulsing orange ring around active speaker
- Agent → User swap on message send
- User → Agent swap on response start

### 10.3 Background Sessions → Orders

**Concept:** When user taps "Move to Background" on an active chat session, it becomes a Scheduled order item with status `working`.

**Order status flow:**
```
drafted → scheduled → working → completed
                   ↗
           (user triggers from chat)
```

**Backend changes:**
- Extend `OrderStatusEnum` to include `WORKING`
- New endpoint or extension: `POST /v1/orders/from-session`
  - Takes session_id, creates an order with the current conversation context
  - Hestia continues processing in the background task system

**UI flow:**
1. User in chat, conversation taking a while
2. Taps "↗ Move to Background" button (replaces the removed "add session" button)
3. Chat clears to fresh session
4. Background session appears in Command → Orders → Scheduled with `working` status
5. When complete: status → `completed`, notification to user
6. User can tap the completed order to see results, reference the full conversation

**macOS components:**
| Component | Purpose |
|-----------|---------|
| `ChatInputView` (refactored) | CLI-style input with monospace, prompt char, history |
| `ChatOutputRenderer` | Rich markdown/code/card rendering for responses |
| `FloatingAvatarView` | Animated avatar header with swap transitions |
| `BackgroundSessionButton` | "Move to Background" action in chat toolbar |
| `OrderSessionCard` | Order card variant showing background session status |

### 10.4 Removed: "Add Session" Button

Simply removed from the chat toolbar. New session creation happens implicitly when moving current to background, or via a keyboard shortcut (⌘N).

### Sprint 10 Effort Estimate

| Task | Backend | macOS | Tests | Days |
|------|---------|-------|-------|------|
| CLI input component | — | 1 new view (complex) | 3 | 2 |
| Rich output renderer | — | 1 new view (complex) | 3 | 2 |
| Floating avatar with animation | — | 1 new view | 2 | 1 |
| Background session → Order flow | Extend orders | 2 views | 8 | 3 |
| Remove add-session, add keyboard shortcuts | — | Refactor | 1 | 0.5 |
| Session history recall (up-arrow) | — | Input enhancement | 2 | 1 |
| **Total** | **~2 endpoint changes** | **~5 views** | **~19 tests** | **~9.5 days** |

---

## Sprint 11: Command Center Redesign

### Scope
Compact summary bubbles, week calendar, contextual metrics, Orders redesign (Recurring/Scheduled with wizard), health as sub-dashboard.

### 11.1 Layout Restructure

```
┌────────────────────────────────────────────────────────────────┐
│  Command                                                        │
│                                                                  │
│  ┌────────────────────────────────────────┐  ┌──────────────┐  │
│  │          WEEK CALENDAR                  │  │  METRICS     │  │
│  │  Mon  Tue  Wed  Thu  Fri  Sat  Sun     │  │              │  │
│  │  ═══  ═══  ═══  ═══  ═══  ═══  ═══    │  │  Sleep: 7.2h │  │
│  │  9am  ·    ·    Team ·    ·    ·       │  │  Recovery:85%│  │
│  │  Sync ·    ·    Mtg  ·    ·    ·       │  │  Time: 4/6hr │  │
│  │  10am ·    ·    ·    ·    ·    ·       │  │              │  │
│  │  ...  ·    ·    ·    ·    ·    ·       │  │  ─── or ───  │  │
│  └────────────────────────────────────────┘  │              │  │
│                                               │  Errors: 0   │  │
│  ┌──────────────────┐  ┌─────────────────┐  │  Latency:45ms│  │
│  │ 📬 3 Unread      │  │  Active Orders   │  │  Learning:+2 │  │
│  │ 📅 2 Events      │  │  ────────────    │  └──────────────┘  │
│  │ ⏰ 1 Reminder    │  │  Daily Brief ●   │                    │
│  │ 🔔 0 Alerts      │  │  Git Sync    ●   │                    │
│  └──────────────────┘  │  [+ New Order]   │                    │
│                         └─────────────────┘                    │
│  ─── sticky: Health Dashboard ──────────────────────────────── │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  [See Sprint 12]                                          │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

### 11.2 Week Calendar

**Backend:** Uses existing Apple Calendar CLI tool via Explorer resources.

**New endpoint (convenience):**
```
GET /v1/command/calendar-week
  ?week_offset=0  (0=this week, -1=last week, 1=next week)
  Response: {
    week_start: date,
    days: [{ date: str, events: [CalendarEvent] }],
    total_events: int
  }
```

**macOS component:** `WeekCalendarView` — 7-column grid with hour rows, event blocks color-coded by calendar.

### 11.3 Contextual Metrics (Auto-Switch)

**Default view: Personal** (Sleep, Recovery, Time/Busyness)
- Sleep: From HealthKit data (`GET /v1/health_data/summary`)
- Recovery: From Whoop API (new) or HealthKit HRV proxy
- Time: Calendar density calculation (hours booked / hours available)

**Auto-switches to System** when anomalies detected:
- Errors: Count of failed orders, tasks, or API errors in last 24h
- Latency: Average response time from `/v1/health` components
- Learning: New memory chunks committed, patterns detected (from proactive module)

**Switch trigger logic (backend):**
```python
if error_count_24h > 0 or avg_latency_ms > 500:
    return SystemMetrics(errors, latency, learning)
else:
    return PersonalMetrics(sleep, recovery, busyness)
```

**New endpoint:**
```
GET /v1/command/metrics
  Response: {
    mode: "personal"|"system",
    personal: { sleep_hours, recovery_pct, busyness_pct },
    system: { error_count, avg_latency_ms, learning_count },
    reason: "high_errors"|"default_personal"|...
  }
```

### 11.4 Orders Redesign

**Two sections:**
1. **Recurring** — Orders with frequency (daily, weekly, monthly, custom). Tagged with 🔄
2. **Scheduled** — One-time orders + background sessions. Statuses: `drafted` → `scheduled` → `working` → `completed`

**Multi-step creation wizard (sheet/modal):**

```
Step 1: Draft the Prompt
┌─────────────────────────────────────┐
│  What should Hestia do?             │
│  ┌─────────────────────────────────┐│
│  │ Summarize my unread emails and  ││
│  │ flag anything from investors... ││
│  └─────────────────────────────────┘│
│  [Cancel]              [Next →]     │
└─────────────────────────────────────┘

Step 2: Connect Resources
┌─────────────────────────────────────┐
│  What does Hestia need access to?   │
│                                      │
│  ☑ Email (Apple Mail)               │
│  ☑ Calendar                         │
│  ☐ Reminders                        │
│  ☐ Notes                            │
│  ☐ Files                            │
│  ☐ GitHub                           │
│  ☐ Firecrawl (Web)                  │
│                                      │
│  [← Back]              [Next →]     │
└─────────────────────────────────────┘

Step 3: Set Schedule
┌─────────────────────────────────────┐
│  When should this run?               │
│                                      │
│  ○ Once (pick date/time)            │
│  ● Recurring                         │
│    Frequency: [Daily ▾]             │
│    Time: [07:00 AM]                 │
│    Days: [Mon-Fri]                  │
│                                      │
│  [← Back]           [Create Order]  │
└─────────────────────────────────────┘
```

**Backend:** All order CRUD already exists (`/v1/orders/*`). The wizard is purely frontend — it constructs an `OrderCreateRequest` from the 3 steps.

### Sprint 11 Effort Estimate

| Task | Backend | macOS | Tests | Days |
|------|---------|-------|-------|------|
| Command layout restructure | — | Refactor main view | 3 | 2 |
| Week calendar view + endpoint | 1 new endpoint | 1 new view | 5 | 2 |
| Contextual metrics + endpoint | 1 new endpoint | 1 new view | 5 | 2 |
| Compact notification bubbles | — | Refactor existing | 2 | 1 |
| Orders redesign (Recurring/Scheduled) | — | 2 refactored views | 5 | 2 |
| Order creation wizard (3-step) | — | 1 new sheet (complex) | 5 | 2 |
| **Total** | **~2 new endpoints** | **~5 views** | **~25 tests** | **~11 days** |

---

## Sprint 12: Health Dashboard & Whoop Integration

### Scope
Health as sub-dashboard in Command. Sleep/Nutrition/Fitness visualizations. Whoop API integration. Labs + prescriptions (manual + Health Records). AI analysis card in daily briefing.

### 12.1 Health Sub-Dashboard

Accessed by scrolling down in Command or tapping a "Health" sticky section header.

```
┌──────────────────────────────────────────────────────────────┐
│  Health Dashboard                                             │
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │    SLEEP      │  │   FITNESS    │  │   NUTRITION      │   │
│  │              │  │              │  │                  │   │
│  │  ████████░░  │  │  Strain: 14  │  │   [Coming Soon]  │   │
│  │  7.2h / 8h   │  │  Exercise:   │  │                  │   │
│  │              │  │  45 min      │  │   Log Food  [+]  │   │
│  │  Deep: 1.5h  │  │  Avg HR: 72  │  │                  │   │
│  │  REM: 2.1h   │  │  Peak HR:165 │  │                  │   │
│  │  Light: 3.6h │  │              │  │                  │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  📋 Analysis                                              │ │
│  │                                                            │ │
│  │  Labs: Last drawn 2026-02-15                              │ │
│  │  • Vitamin D: 32 ng/mL (normal)  • TSH: 2.1 (normal)    │ │
│  │  [View All Labs →]                                        │ │
│  │                                                            │ │
│  │  Active Prescriptions: 3                                  │ │
│  │  • Lisinopril 10mg daily  • Vitamin D3 5000IU...         │ │
│  │  [View All →]                                             │ │
│  │                                                            │ │
│  │  🤖 Copilot Insights:                                     │ │
│  │  "Your deep sleep has improved 12% this week, likely      │ │
│  │  correlating with your reduced screen time after 9pm.     │ │
│  │  Consider maintaining this habit. Your Vitamin D is       │ │
│  │  borderline - recheck in 60 days."                        │ │
│  └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### 12.2 Whoop API Integration

**Research finding:** Whoop exports to Apple Health: blood oxygen, heart rate, respiratory rate, resting heart rate, sleep records, workouts. But it does **NOT** export: Strain scores, Recovery scores, 5-stage sleep breakdown (only awake/asleep), HRV (unit mismatch: RMSSD vs SDNN), disturbances, activity zones.

**Verdict: Direct Whoop API integration IS worth it.** Strain, Recovery, and granular sleep stages are Whoop's core value proposition and none of it comes through HealthKit.

**New backend module: `hestia/whoop/`**

```
hestia/whoop/
├── __init__.py
├── models.py          # WhoopSleep, WhoopRecovery, WhoopStrain, WhoopWorkout
├── client.py          # Whoop API client (OAuth2, REST)
├── manager.py         # WhoopManager (sync, cache, aggregate)
├── database.py        # SQLite storage for Whoop data
└── oauth.py           # Whoop OAuth2 flow (similar to Gmail pattern)
```

**Whoop API endpoints to consume:**
- `GET /v1/cycle` — daily strain, recovery scores
- `GET /v1/recovery` — recovery score, HRV (RMSSD), resting HR, SpO2
- `GET /v1/sleep` — 5-stage sleep (awake, light, REM, deep, disturbances)
- `GET /v1/workout` — individual workout strain, HR zones, duration

**New Hestia endpoints:**
```
POST   /v1/whoop/authorize        → Initiate OAuth2 flow
POST   /v1/whoop/callback         → Complete OAuth2, store tokens
POST   /v1/whoop/sync             → Pull latest data from Whoop API
GET    /v1/whoop/recovery          → Latest recovery score + trends
GET    /v1/whoop/strain            → Latest strain + daily trend
GET    /v1/whoop/sleep             → Detailed 5-stage sleep breakdown
GET    /v1/whoop/status            → Connection status, last sync time
```

### 12.3 Labs & Prescriptions

**New backend module: `hestia/health/clinical/`**

```
hestia/health/clinical/
├── __init__.py
├── models.py          # LabResult, Prescription, ClinicalRecord
├── manager.py         # ClinicalManager
├── database.py        # SQLite for labs/prescriptions
├── pdf_parser.py      # Extract lab values from uploaded PDFs (regex + LLM)
└── fhir_client.py     # Apple Health Records FHIR integration (future)
```

**New endpoints:**
```
POST   /v1/health_data/labs              → Upload lab PDF or manual entry
GET    /v1/health_data/labs              → List lab results
GET    /v1/health_data/labs/{lab_id}     → Get specific lab detail
POST   /v1/health_data/prescriptions     → Add prescription (manual)
GET    /v1/health_data/prescriptions     → List active prescriptions
PUT    /v1/health_data/prescriptions/{id} → Update prescription
DELETE /v1/health_data/prescriptions/{id} → Discontinue prescription
```

### 12.4 AI Health Analysis (Daily Briefing Integration)

**Extension to existing `BriefingGenerator`:**

Add a new `BriefingSection` type: `HEALTH_ANALYSIS`. During daily briefing generation:
1. Fetch latest HealthKit summary + Whoop recovery/strain
2. Fetch recent lab results + active prescriptions
3. Generate LLM analysis via cloud provider:
   - Trend observations (sleep improving, HR elevated, etc.)
   - Correlation detection (exercise → sleep quality, stress → HRV)
   - Action items (recheck labs, adjust medication timing, etc.)
4. Include in briefing response

**No new endpoint needed** — analysis rides on existing `GET /v1/proactive/briefing`.

### Sprint 12 Effort Estimate

| Task | Backend | macOS | Tests | Days |
|------|---------|-------|-------|------|
| Health sub-dashboard layout | — | 3 new views | 3 | 2 |
| Sleep/Fitness visualization charts | — | 2 chart views | 3 | 2 |
| Whoop module (client, OAuth2, sync) | New module | — | 15 | 4 |
| Whoop UI integration | — | 1 auth sheet + data views | 3 | 1 |
| Clinical module (labs, prescriptions) | New module | — | 12 | 3 |
| Labs/Prescriptions UI | — | 3 views | 5 | 2 |
| Health analysis in briefing | Extend briefing | — | 5 | 1 |
| PDF lab parser (regex + LLM) | New component | — | 5 | 2 |
| **Total** | **~2 new modules, ~10 endpoints** | **~9 views** | **~51 tests** | **~17 days** |

---

## SWOT Analysis

### Sprint 7 (Profile & Settings)

| | Positive | Negative |
|---|---|---|
| **Internal** | **S:** All backend endpoints already exist. Zero new backend work. Accordion pattern is native SwiftUI. V2 agent API is clean and well-tested. | **W:** Consolidating Resources means removing/refactoring 6 existing views. Risk of breaking existing macOS Cloud/Integrations functionality during migration. |
| **External** | **O:** Clean settings structure becomes the foundation for all future config (Whoop auth, Gmail auth, etc. all live here). Markdown editor is reusable (MIND.md, BODY.md, ANIMA.md, order prompts). | **T:** Field Guide inside Settings may feel buried. Users who relied on dedicated Wiki tab might be confused by the move. |

### Sprint 8 (Research & Graph)

| | Positive | Negative |
|---|---|---|
| **Internal** | **S:** ChromaDB already has embeddings for semantic similarity. Tool execution logs exist. Memory chunks have rich metadata for node construction. | **W:** Graph computation could be expensive (querying ChromaDB + building adjacency matrix). Community detection algorithms add Python dependencies. 3D SceneKit rendering on Mac Mini may have performance limits. |
| **External** | **O:** Graph view is a unique differentiator — no consumer AI assistant has a knowledge/activity graph. Creates foundation for the Neural Net Learning Cycle (previous research). | **T:** If graph data is sparse (few memories, limited tool usage), the visualization looks empty and underwhelming. Need minimum data thresholds. |

### Sprint 9 (Explorer)

| | Positive | Negative |
|---|---|---|
| **Internal** | **S:** Apple CLI tools for Notes/Reminders/Mail already exist. File system access is unrestricted on Mac Mini. Gmail OAuth2 is well-documented. | **W:** Highest new-code sprint (~15 endpoints, 11 views, 48 tests). Full Finder integration has security surface area (path traversal, permission issues). Gmail OAuth2 requires Google Cloud Console setup. |
| **External** | **O:** Universal inbox is a killer feature — managing email from Hestia with AI context is powerful. File browsing makes Hestia feel like a real OS companion, not just a chat bot. | **T:** Email CRUD is high-stakes — accidental deletes, wrong replies. Gmail API has rate limits and quota restrictions. Apple Mail CLI may not support all operations reliably. |

### Sprint 10 (Chat)

| | Positive | Negative |
|---|---|---|
| **Internal** | **S:** Chat is the most-used view — investment here has highest impact. CLI aesthetic matches Hestia's developer-oriented personality. Background sessions leverage existing task infrastructure. | **W:** Rich markdown rendering in SwiftUI is non-trivial (need WebView or custom AttributedString pipeline). CLI input expectations (history, completion) add complexity. Avatar animations need careful performance tuning. |
| **External** | **O:** CLI-style input differentiates from every consumer AI chat (all use rounded bubbles). Background sessions solve the "I'm waiting for Hestia" problem that kills flow. | **T:** Users expect Claude Code-level input quality — hard bar to clear in native SwiftUI. Rich output rendering may have edge cases with complex markdown/LaTeX. |

### Sprint 11 (Command)

| | Positive | Negative |
|---|---|---|
| **Internal** | **S:** Most data sources already exist (calendar via CLI, health via HealthKit, orders via existing API). Week calendar is a standard SwiftUI component. Order wizard is purely frontend. | **W:** Contextual auto-switching metrics requires careful threshold tuning (too sensitive = annoying flips; too conservative = misses problems). Dense layout needs responsive design work. |
| **External** | **O:** Command Center becomes the "at-a-glance brain" of Hestia. Order creation wizard dramatically lowers the barrier to creating scheduled intelligence. | **T:** Information density could overwhelm. Need clear visual hierarchy. Calendar data depends on Apple Calendar access (TCC permissions). |

### Sprint 12 (Health & Whoop)

| | Positive | Negative |
|---|---|---|
| **Internal** | **S:** HealthKit integration already complete (28 metrics). Whoop API is well-documented REST. LLM analysis can run on existing cloud providers. Briefing generator already has section-based architecture. | **W:** Largest sprint by effort (17 days). Whoop OAuth2 + Gmail OAuth2 means two external auth flows to maintain. PDF lab parsing is inherently messy (varied formats). Clinical data has regulatory sensitivity. |
| **External** | **O:** Health copilot with real lab data + prescriptions + wearable data is genuinely novel. No consumer AI does this. Whoop's proprietary Strain/Recovery data is a genuine value-add over HealthKit-only. | **T:** Whoop API access requires developer application and may have rate limits. Lab data interpretation by AI carries liability risk (needs strong disclaimers). Apple Health Records FHIR access requires user to have participating healthcare provider. |

---

## Risk Register

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Gmail OAuth2 token refresh fails silently | High (inbox stops working) | Medium | Implement token health check in `/v1/inbox/accounts`, alert on failure |
| Whoop API changes/deprecation | Medium (Strain/Recovery data lost) | Low | Abstract behind `BaseWearableProvider` interface, fallback to HealthKit |
| Full Finder access security vulnerability | Critical (data exposure) | Low | Whitelist roots, blacklist system paths, path traversal validation, sandbox testing |
| Mac Mini M1 performance under load (graph computation + email sync + Whoop sync) | High (latency spikes) | Medium | TTL caches on all computed data, async background sync, request queuing |
| Rich markdown rendering bugs in SwiftUI | Medium (broken chat display) | High | Use WKWebView fallback for complex content, progressive enhancement |
| Clinical data liability | High (health advice risk) | Medium | Strong disclaimers on all AI health analysis, "not medical advice" banners |

---

## Neural Net Learning Cycle Integration

The [Neural Net Learning Cycle Research](neural-net-learning-cycle-research.md) proposed a 3-phase evolution from command-driven to anticipatory intelligence. Here's how those phases weave into the UI/UX sprints:

### Phase A: Reflection Engine → Sprints 8 + 10

The Reflection Engine (OutcomeTracker + ReflectionAgent + PrincipleStore) has natural integration points with work already planned:

**Sprint 8 (Research & Graph):** The Graph View's hybrid knowledge + activity dataset IS the foundation for the Principle Store. Memory chunks + tool usage patterns + co-occurrence edges are exactly what the Reflection Engine needs to distill principles. The `hestia/research/graph_builder.py` module should be designed to also serve as the data source for principle distillation.

**Sprint 10 (Chat Redesign):** The OutcomeTracker needs to hook into the chat response cycle. With background sessions moving to Orders, we now have structured outcome signals: Did the background session complete successfully? Did Andrew review the output? Did he edit it? The `working → completed` status flow in Orders provides natural outcome checkpoints.

**Proposed additions to Sprints 8 + 10:**
- Sprint 8: Add `PrincipleStore` as a new ChromaDB collection alongside the graph module. Add `POST /v1/research/principles` endpoint for distillation triggers.
- Sprint 10: Add `OutcomeTracker` middleware to the chat endpoint. Log implicit signals (response edits, follow-up corrections, time-to-next-message). ~3 additional days total.

### Phase B: Metacognitive Dual-Cycle → Sprint 11

The Command Center redesign is the perfect home for metacognitive monitoring:

**Sprint 11 (Command):** The contextual auto-switching metrics (Errors/Latency/Learning ↔ Sleep/Recovery/Time) are literally the MetaMonitor's output. The "Learning" metric in the system view should display real data from the Reflection Engine — principles distilled, prediction accuracy, confidence calibration scores.

**Proposed additions to Sprint 11:**
- `MetaMonitor` as a background async manager that watches interaction logs for confusion loops, excessive back-and-forth, and declining acceptance rates.
- `ConfidenceCalibrator` that feeds into the contextual metrics card. "Learning: +2" becomes meaningful — it means 2 new principles were validated this week.
- `KnowledgeGapDetector` output feeds into the daily briefing: "Areas where I'm uncertain: your weekend project selection, your email triage priorities." ~4 additional days.

### Phase C: Active Inference → Sprint 13+ (Future)

The Active Inference Engine (hierarchical generative world model, prediction engine, curiosity drive) is the most ambitious phase and should come AFTER all UI/UX wiring is complete. It needs:
- The Reflection Engine generating validated principles (from Phase A)
- The MetaMonitor tracking prediction accuracy (from Phase B)
- The Health Dashboard providing rich personal state data (from Sprint 12)
- The Universal Inbox providing behavioral signals about communication patterns (from Sprint 9)

**Sprint 13 (proposed): Active Inference Foundation**
- `GenerativeWorldModel` with 3 hierarchical layers (abstract/routine/situational)
- `PredictionEngine` that generates pre-interaction predictions logged and scored
- `SurpriseDetector` replacing heuristic thresholds with free-energy formalism
- `CuriosityDrive` generating exploratory questions ranked by expected information gain

**Sprint 14 (proposed): Anticipatory Execution**
- `AnticipationExecutor` that queues proactive actions based on high-confidence predictions
- Integration with Orders system — auto-generated draft orders that Andrew approves
- The three operating regimes (anticipatory / curious / observant) become visible in the Command Center metrics

### Revised Sprint Map with Learning Cycle

```
Sprint 7:  Profile & Settings               ← Foundation (settings for all future config)
Sprint 8:  Research & Graph + PrincipleStore ← Learning Cycle Phase A (part 1)
Sprint 9:  Explorer (Files + Inbox)          ← Data breadth (behavioral signals)
Sprint 10: Chat Redesign + OutcomeTracker    ← Learning Cycle Phase A (part 2)
Sprint 11: Command + MetaMonitor             ← Learning Cycle Phase B
Sprint 12: Health & Whoop                    ← Personal state data for world model
Sprint 13: Active Inference Foundation       ← Learning Cycle Phase C (part 1)
Sprint 14: Anticipatory Execution            ← Learning Cycle Phase C (part 2)
```

This sequencing means the learning cycle isn't a separate workstream — it's woven into the fabric of every sprint. Each UI sprint generates the data and infrastructure the learning cycle needs, and each learning cycle phase makes the next UI sprint's features smarter.

---

## Sprint Sequencing Summary

| Sprint | Focus | New Backend | New macOS Views | New Tests | Est. Days |
|--------|-------|-------------|-----------------|-----------|-----------|
| **7** | Profile & Settings | 0 endpoints | ~12 views | ~26 | ~13 |
| **8** | Research & Graph + PrincipleStore | ~1 module, 2 routes | ~4 views | ~35 | ~11 |
| **9** | Explorer (Files + Inbox) | ~2 modules, ~15 endpoints | ~11 views | ~48 | ~14.5 |
| **10** | Chat Redesign + OutcomeTracker | ~3 endpoint changes | ~5 views | ~24 | ~11 |
| **11** | Command + MetaMonitor | ~3 endpoints + 1 bg manager | ~6 views | ~32 | ~15 |
| **12** | Health & Whoop | ~2 modules, ~10 endpoints | ~9 views | ~51 | ~17 |
| **13** | Active Inference Foundation | ~1 module, ~4 endpoints | ~2 views | ~25 | ~12 |
| **14** | Anticipatory Execution | ~3 endpoints | ~3 views | ~20 | ~10 |
| **TOTAL** | | **~7 new modules, ~40 endpoints** | **~52 views** | **~261 tests** | **~103.5 days** |

**At ~6 hours/week:** Sprints 7-12 (UI/UX wiring) = ~81.5 days ≈ **7 calendar months**. Sprints 13-14 (Learning Cycle completion) add ~22 days ≈ **2 more months**. Full roadmap: ~9 calendar months.

**Recommended pace:** 2-week sprint cycles with demo/review between each. Ship Sprint 7 first (highest user-facing impact, zero backend work needed). Learning Cycle phases are additive — each sprint works standalone even if Phases B/C are deferred.

---

## Sources

- [Whoop Apple Health Integration — What Syncs and What Doesn't](https://support.whoop.com/s/article/Apple-Health-Integration?language=en_US)
- [Whoop Syncs Health Data to Apple Health](https://tryterra.co/blog/whoop-syncs-health-data-to-apple-health-ee298d328f41)
- [What You Can (and Can't) Do With Apple HealthKit Data](https://www.themomentum.ai/blog/what-you-can-and-cant-do-with-apple-healthkit-data)
