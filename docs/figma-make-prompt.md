# Figma Make Prompt — Hestia Workspace (macOS Desktop App)

---

## App Overview

Design a macOS desktop application called **"Hestia Workspace"** — a locally-hosted personal AI assistant workspace. Think Vivaldi Browser's panel/tab modularity meets a dark-mode IDE meets an executive dashboard. The app is a multi-panel workspace where the user manages their digital life (calendar, mail, notes, files, health data) alongside a persistent AI chat companion.

**Window size:** 1400×900pt default, 1000×600pt minimum. Full-screen capable.

**Platform:** macOS native. Use macOS window chrome (traffic lights top-left), transparent titlebar with hidden title text. No tab bar or toolbar — the layout IS the navigation.

---

## Color System (Dark Mode Only — No Light Mode)

### Background & Surfaces
- **Window background:** Near-black (`#0D0D0F`)
- **Sidebar background:** `#141418` (slightly lighter than window)
- **Panel/card surfaces:** `rgba(255, 255, 255, 0.05)` to `rgba(255, 255, 255, 0.10)` — layered glassmorphism
- **Hover states:** `rgba(255, 255, 255, 0.08)`
- **Selected/active states:** `rgba(255, 255, 255, 0.15)`
- **Dividers/borders:** `rgba(255, 255, 255, 0.06)`

### Agent Mode Accent Gradients (The app changes accent color based on active AI persona)
- **Tia (Default — daily ops):** Warm orange/brown gradient: `#E0A050` → `#A54B17` → `#8B3A0F`
- **Mira (Learning):** Electric blue gradient: `#090F26` → `#026DFF` → `#00D7FF`
- **Olly (Projects):** Forest green gradient: `#03624C` → `#187403` → `#2CC295`

The active agent's gradient subtly tints the chat panel header and certain accent elements (selected sidebar items, active tab indicators, send button). Default to **Tia (orange/brown)** for the mockup.

### Semantic Colors
- **Healthy/Success:** `#34C759`
- **Warning:** `#FFCC00`
- **Error/Destructive:** `#FF3B30`
- **Cloud providers:** Anthropic `#D4A574`, OpenAI `#10A37F`, Google `#4285F4`

### Text
- **Primary text:** `#FFFFFF` (100% white)
- **Secondary text:** `rgba(255, 255, 255, 0.70)`
- **Tertiary/disabled:** `rgba(255, 255, 255, 0.40)`
- **Timestamps/metadata:** `rgba(255, 255, 255, 0.50)`

---

## Typography

- **Brand font (greetings, hero text):** Volkhov Bold, 28-32pt, white
- **UI font:** SF Pro (system). Use SF Pro Display for larger sizes, SF Pro Text for body.
  - Section headers: 13pt Semibold, uppercased, `rgba(255,255,255,0.5)` — letter-spacing 0.5pt
  - Tree item labels: 14pt Regular
  - Card titles: 16pt Semibold
  - Body text: 14-15pt Regular (desktop-optimized, slightly smaller than iOS 17pt)
  - Chat messages: 15pt Regular
  - Metadata/timestamps: 12pt Regular
  - Input fields: 15pt Regular
- **Monospace (code, scripts, logs):** SF Mono or Menlo, 13pt

---

## Spacing & Sizing

- **Spacing scale:** 4 / 8 / 12 / 16 / 24 / 32 / 48pt
- **Corner radius:** Cards/panels: 12pt. Buttons: 8pt. Pills/badges: 16pt. Sidebar items: 6pt.
- **Sidebar width:** 240-320pt (resizable, collapsible via Cmd+B)
- **Chat panel width:** 320-480pt (resizable, collapsible via Cmd+\)
- **Settings ribbon height:** 48pt fixed at bottom of sidebar
- **Icon size in sidebar:** 16pt (SF Symbols style)
- **Tree indentation:** 16pt per level

---

## Layout — Three Zones

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ● ● ●  (traffic lights)                              Hestia Workspace      │
├────────────────┬─────────────────────────────────┬───────────────────────────┤
│                │                                 │                           │
│   EXPLORER     │        WORKBENCH                │      CHAT PANEL           │
│   (Top-Left)   │        (Center)                 │      (Right)              │
│                │                                 │                           │
│  Sidebar tabs: │  Tabbed document area           │  Agent header + mode      │
│  • Newsfeed    │  (like browser/IDE tabs)         │  Message history          │
│  • Calendar    │                                 │  Context-aware input      │
│  • Health      │  Opens: PDFs, images,           │                           │
│  • File Tree   │  markdown, RTF, scripts,        │  Collapsible (Cmd+\)      │
│                │  docs, CSV/Excel                │                           │
│                │                                 │                           │
│                │  Supports split panes            │                           │
│                │  (horizontal + vertical)         │                           │
│                │                                 │                           │
├────────────────┤                                 │                           │
│  SETTINGS      │                                 │                           │
│  (Bottom-Left  │                                 │                           │
│   Ribbon)      │                                 │                           │
└────────────────┴─────────────────────────────────┴───────────────────────────┘
```

---

## Zone 1: Explorer Sidebar (Top-Left, 240-320pt wide)

The Explorer is a **Vivaldi-style vertical tab stack** — a column of collapsible sections, each functioning as a mini-panel. Only one section is expanded at a time (accordion behavior), with the others collapsed to a single header row showing icon + label.

### Section 1: Newsfeed (`newspaper` SF Symbol)
An alert/spotlight feed with two subsections:

- **Hyperfocused Alerts:** Curated topic-tracking cards (e.g., "Sabrina Pasterski," "Mac Studio Ultra," custom keywords). Each alert is a compact card: source icon + headline + timestamp + relevance badge. Cards stack vertically, most recent first.
- **Tia Spotlight:** AI-generated daily briefing summary — 3-5 bullet points of what matters today, with subtle gradient accent border (Tia orange).

### Section 2: Calendar Timeline (`calendar` SF Symbol)
A compact day/week timeline view (not a full calendar grid — think a vertical timeline ribbon).

Three interleaved item types, distinguished by left-edge color coding:
- **Orders** (agent-scheduled tasks): Orange accent dot
- **Tasks** (user todos): Blue accent dot
- **Events** (calendar events): Green accent dot

Each item: time/range on left, title + brief detail on right. Tapping an event could open management in the Workbench via the agent. Day/week toggle at section header.

### Section 3: Health (`heart.fill` SF Symbol)
A compact health dashboard inspired by ClyHealth (reference: https://dribbble.com/shots/26128793-Health-Dashboard-ClyHealth).

Two sub-views:
- **Graph View:** Mini sparkline charts for key metrics (steps, heart rate, sleep, activity). Dark cards with colored accent lines per metric type. Compact — show 3-4 metrics in the sidebar width.
- **Data Explorer:** A structured tree/table showing Metrics, Logs, and Traces. Collapsible categories, numerical values right-aligned, trend arrows (↑↓→) with green/red/neutral coloring.

### Section 4: File Tree (`folder.fill` SF Symbol)
A rich, customizable data tree (references: https://dribbble.com/shots/25521744-Data-tree-with-light-and-dark-themes and https://dribbble.com/shots/25410692-Customizable-data-tree-with-contextual-insights).

**Root-level folders:**
- Mailboxes (envelope icon)
- Notes (note.text icon)
- Files (doc icon)
- Tasks (checklist icon)

**Tree design:**
- Each node has: **SF Symbol icon** (contextual to file type) + **label** + optional **custom color dot** for user-defined categorization
- Indentation: 16pt per nesting level, with subtle vertical guide lines (`rgba(255,255,255,0.06)`)
- Expand/collapse chevrons on folders
- **Contextual metadata badges** on tree items:
  - 🟠 "Recent dialogue" — items recently referenced in chat (orange dot)
  - 🔵 "Open plan" — items linked to an active project/order (blue dot)
  - 🚩 "Flagged" — user-flagged items (red flag icon)
- Hover shows a tooltip with last-modified date + size
- Double-click opens item in Workbench center panel
- Drag-and-drop onto Chat panel to attach as context

---

## Zone 2: Settings Ribbon (Bottom-Left, fixed 48pt tall strip below Explorer)

A horizontal strip of icon buttons at the bottom of the sidebar — think VS Code's bottom-left gear area but expanded. Compact icon row with tooltips on hover.

**Items (left to right):**
- **User Profile** (`person.circle` icon) — avatar thumbnail, opens profile sheet
- **Agent Profiles** (`brain` icon) — manage Tia/Mira/Olly + custom agents
- **Resources** (`square.grid.2x2` icon) — opens a popover/sheet listing connected integrations:
  1. Firecrawl (web scraping)
  2. Playwright (browser automation)
  3. Calendar (EventKit)
  4. Reminders
  5. Shortcuts
  6. GitHub
  7. Fidelity (financial)
  8. Email
  9. Notes

  Each resource shows: icon + name + connection status dot (green=connected, gray=disconnected)
- **Field Guide** (`book` icon) — opens the Wiki/Architecture knowledge base
- **Sync indicator** (`arrow.triangle.2.circlepath` icon) — shows iCloud sync status (syncs user profile + agent configs across devices)

On hover, each icon subtly highlights. Active/open item gets the agent accent color underline.

---

## Zone 3: Workbench (Center, flexible width — takes all remaining space)

A **tabbed document area** like a browser or IDE. Tabs across the top, content below.

### Tab Bar
- Horizontal tab row at the top of the Workbench area
- Each tab: favicon/type icon + document title + close (×) button
- Active tab: slightly brighter background (`rgba(255,255,255,0.10)`), white text
- Inactive tabs: `rgba(255,255,255,0.05)` background, dimmed text
- "+" button at end of tab row to open new blank tab
- Tabs are reorderable via drag
- Overflow: horizontal scroll with fade indicators

### Content Area
Supports these document types with appropriate viewers:
- **PDFs & Images:** Preview with zoom/pan
- **Markdown ↔ RTF:** Editable with live preview toggle (rendered markdown on left, source on right — or single-pane toggle)
- **Scripts:** Syntax-highlighted code editor (monospace font, line numbers, dark theme)
- **Docs:** Rich text display
- **CSV/Excel:** Table view with sortable columns, alternating row shading (`rgba(255,255,255,0.03)`)

### Split Panes
The content area supports splitting horizontally or vertically (like VS Code split editor). Show a subtle divider line between panes. Each split pane has its own tab bar.

### Empty State
When no documents are open, show a centered placeholder:
- Volkhov Bold 24pt: "What are we working on?"
- Below: subtle grid of recent files (4-6 items) as clickable cards
- Below that: keyboard shortcut hints in `rgba(255,255,255,0.3)` text

---

## Zone 4: Chat Panel (Right, 320-480pt wide, collapsible)

A persistent AI conversation panel — not a tab, always available alongside whatever the user is working on.

### Chat Header (top of panel)
- Agent avatar: circular, 40pt, with subtle gradient border matching active mode (Tia orange by default)
- Agent name + mode label: "Tia" / "Mira" / "Olly" with mode subtitle ("Daily Ops" / "Learning" / "Projects")
- Mode switcher: dropdown or segmented control to switch personas
- Subtle gradient wash across the header background matching the active agent's colors

### Message Area
- Bottom-anchored message list (newest at bottom, like iMessage)
- **User messages:** Right-aligned bubbles, `rgba(255,255,255,0.15)` background, 12pt corner radius
- **Assistant messages:** Left-aligned bubbles, `rgba(255,255,255,0.08)` background, 12pt corner radius
- Timestamps below each message cluster: 12pt, `rgba(255,255,255,0.5)`
- Tool execution states: "Working on that..." with a subtle spinning indicator, replacing raw JSON
- Context attachments: When the user drags a file/item into chat, show a compact attachment chip above the input (file icon + name + × to remove)

### Input Area (bottom of panel)
- Text input field: `rgba(255,255,255,0.10)` background, 12pt corner radius, 40pt height (expands with multiline)
- Placeholder: "Message Tia..." (changes with active agent)
- Send button: circular, 32pt, agent accent color when input has text, dimmed when empty
- Above input: subtle context indicator showing what the chat "sees" (e.g., "Viewing: Q4-report.pdf" in tiny `rgba(255,255,255,0.4)` text)

---

## Design Principles

1. **Dark-only, glassmorphism-lite:** Layers of semi-transparent white surfaces over a near-black base. No harsh borders — use opacity differences to create depth.
2. **Information-dense but breathable:** This is a power-user tool. Show lots of data, but use consistent spacing and subtle dividers to prevent overwhelm.
3. **Agent personality through color:** The active AI persona (Tia/Mira/Olly) subtly shifts accent colors across the UI — chat header gradient, selected sidebar items, active tab indicator, send button. It should feel alive.
4. **Vivaldi-inspired modularity:** Panels resize, collapse, and rearrange. The sidebar accordion, resizable splits, and collapsible chat panel give the user control over their workspace density.
5. **Native macOS feel:** Respect platform conventions — traffic light buttons, system font (SF Pro), keyboard shortcuts, native scroll physics. Don't fight the platform.
6. **No visual clutter:** Minimal iconography. SF Symbols only. No emoji in the UI chrome. Clean lines, generous negative space within information-dense areas.

---

## Screens to Generate

### Screen 1: Full Workspace — Default State
Show the complete 3-zone layout with:
- Explorer sidebar open with the **Calendar Timeline** section expanded (showing a mix of orders, tasks, and events for today)
- File Tree section collapsed (visible as header row)
- Workbench with 3 tabs open, active tab showing a **Markdown document** in rendered view
- Chat panel open with a short conversation (3-4 messages) with Tia, showing the orange accent theme
- Settings ribbon visible at bottom-left

### Screen 2: Health + Data Explorer Focus
- Explorer sidebar with **Health** section expanded, showing mini sparkline charts and the data explorer tree
- Workbench showing a **CSV/table view** (health metrics export)
- Chat panel showing a health-related conversation ("Here's your sleep trend this week...")

### Screen 3: File Tree + Multi-Document Workbench
- Explorer sidebar with **File Tree** expanded, showing Mailboxes/Notes/Files hierarchy with contextual badges (recent dialogue dots, flags)
- Workbench with **split panes** — PDF on left, Markdown editor on right
- Chat panel collapsed (just a thin vertical strip with expand arrow)

### Screen 4: Newsfeed + Empty Workbench
- Explorer sidebar with **Newsfeed** expanded, showing Hyperfocused Alerts cards and Tia Spotlight briefing
- Workbench in **empty state** (centered "What are we working on?" with recent file cards)
- Chat panel open, conversation just starting

---

## Reference Links (for visual inspiration — view directly on Dribbble)
- Health dashboard aesthetic: https://dribbble.com/shots/26128793-Health-Dashboard-ClyHealth
- Data tree (light/dark): https://dribbble.com/shots/25521744-Data-tree-with-light-and-dark-themes
- Customizable data tree with context: https://dribbble.com/shots/25410692-Customizable-data-tree-with-contextual-insights
- General vibe: Vivaldi Browser panel system + VS Code sidebar + Obsidian dark theme
