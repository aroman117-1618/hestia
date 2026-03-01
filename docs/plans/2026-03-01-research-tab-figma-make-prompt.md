# Research Tab — Figma Make Prompt

> Generated 2026-03-01. Copy everything below the line into Figma Make.

---

## Prompt

Design a **"Research" tab** for a macOS desktop application called **Hestia** — a personal AI assistant with a dark, warm-amber design language. This tab has two modes: **GraphView** and **DataExplorer**, toggled via a segmented control at the top. Design both modes as separate frames within the same page.

The app uses a fixed 68px icon sidebar on the left (already exists — do not design it). The Research tab content fills the remaining workspace (~1200px wide, ~800px tall). An optional 520px chat panel can slide in from the right (do not design it either). Focus only on the main content area.

---

### Global Design System

**Color Palette (dark mode only):**
- Window background: `#0D0802` (very dark warm brown)
- Panel/card background: `#110B03`
- Sidebar background: `#0A0603`
- Primary accent: `#E0A050` (warm amber — buttons, active states, links)
- Bright accent: `#FFB900` (highlights, active indicators)
- Dark accent: `#FF8904` (depth, hover states)
- Card border: `rgba(254, 154, 0, 0.08)` — very subtle amber tint, 1px stroke
- Strong border: `rgba(254, 154, 0, 0.15)` — for focused/active elements
- Divider: `rgba(182, 165, 145, 0.15)`
- Active tab background: `rgba(238, 203, 160, 0.15)`
- Search input background: `rgba(235, 223, 209, 0.08)`
- Primary text: `#E4DFD7` (warm off-white)
- Secondary text: `rgba(235, 223, 209, 0.5)` (50% opacity)
- Faint text: `rgba(235, 223, 209, 0.3)`
- Placeholder text: `rgba(235, 223, 209, 0.4)`
- Status green: `#00D492`
- Status red: `#FF6467`
- Status gold: `#FEE685`

**Typography:**
- Font family: SF Pro (system font)
- Page title: 18pt regular
- Section title: 16pt medium
- Card title: 15pt medium
- Body: 14pt regular
- Label: 13pt regular
- Label medium: 13pt medium
- Small: 12pt regular
- Caption: 11pt regular
- Metadata: 10pt regular
- Monospace: SF Mono 13pt (for data values)

**Spacing:**
- xs: 4px, sm: 8px, md: 12px, lg: 16px, xl: 20px, xxl: 24px, xxxl: 32px
- Container padding: 20px
- Panel corner radius: 16px
- Tab corner radius: 10px
- Search bar corner radius: 8px

**Iconography:** SF Symbols (Apple's system icon set). Use outlined variants.

---

### Top Bar (shared by both modes)

Full width of content area. Height ~46px. Background: transparent (inherits window background).

**Left section:**
- Page title: "Research" in 18pt, primary text color
- Subtle atom/molecule icon to the left of the title (SF Symbol: `atom`)

**Center section:**
- Segmented control with two options: **"Graph"** (SF Symbol: `circle.grid.cross`) and **"Explorer"** (SF Symbol: `tablecells`)
- Active segment: amber accent text + `rgba(238, 203, 160, 0.15)` background fill, 10px radius
- Inactive segment: secondary text color, no fill
- Segments are pill-shaped, 13pt medium text, 8px horizontal / 6px vertical padding

**Right section:**
- Lookback duration selector: segmented control with options `7d` `30d` `90d`
- Same styling as mode picker but smaller (12pt, tighter padding)

---

### Frame 1: GraphView Mode

This is the primary visualization — an interactive 2D force-directed knowledge graph inspired by Obsidian.md's graph view. It visualizes the user's personal data (chat history, emails, notes, calendar events, reminders, health metrics) as an interconnected network.

#### Filter Bar (below top bar)

Horizontal row of toggleable pill buttons for data sources:
- **Chat** (icon: `bubble.left.fill`, color: `#E0A050` amber)
- **Email** (icon: `envelope.fill`, color: `#4A9EFF` blue)
- **Notes** (icon: `note.text`, color: `#00D492` green)
- **Calendar** (icon: `calendar`, color: `#B06AFF` purple)
- **Reminders** (icon: `checklist`, color: `#FF6467` red)
- **Health** (icon: `heart.fill`, color: `#2CC295` teal)

Each pill: icon + label, 12px horizontal / 4px vertical padding, 8px radius. Active: filled with source color at 20% opacity, text in source color. Inactive: transparent, secondary text. All active by default.

To the right of the pills: a search field (magnifying glass icon, placeholder "Search tags, topics, people...", 240px wide, `rgba(235, 223, 209, 0.08)` background, 8px radius).

#### Graph Canvas (main area, ~70% of content width)

Dark background (`#0D0802`), fills available space. This is the centerpiece.

**Nodes:**
- Circles scattered across the canvas in a force-directed layout (clusters of related nodes, with connecting lines)
- Each node is colored by its source type (same colors as filter pills above)
- Node sizes vary: larger nodes = more recent + more frequently referenced data points. Range from 6px to 24px diameter.
- Nodes have a subtle glow/bloom effect — a soft radial shadow in the node's color at 15% opacity, radius 2x the node size
- Small label text (10pt, secondary text color) appears below larger nodes showing the title/name
- Hovered node: grows 1.3x with a brighter glow, shows a tooltip card floating nearby

**Edges (connections):**
- Thin lines (1px) connecting nodes that share tags, topics, or entities
- Color: `rgba(235, 223, 209, 0.06)` (very faint, almost invisible until you focus)
- Edges connected to a hovered/selected node brighten to `rgba(235, 223, 209, 0.25)`
- Some clusters of densely connected nodes should be visible — these represent topic groups

**Show approximately 60-80 nodes with natural clustering.** Include:
- A dense cluster of ~15 amber (chat) nodes in the center-left
- A cluster of ~8 purple (calendar) nodes upper-right
- Scattered blue (email) and green (notes) nodes
- A few teal (health) nodes loosely connected to the main graph
- Some red (reminder) nodes near the calendar cluster
- 2-3 isolated nodes floating at the edges (low-connection data)

**Tooltip Card (shown on hover):**
- Small floating card (200px wide), appears near the hovered node
- Panel background with card border, 12px radius, 12px padding
- Title (14pt medium, primary text), source icon + source label (12pt, source color)
- Timestamp (11pt, faint text): e.g., "2 days ago"
- Tag pills: 2-3 small rounded tags (10pt, `rgba(238, 203, 160, 0.15)` background)

**Design a state where one node is selected (clicked):**
- Selected node has a bright ring (2px stroke in node's source color at 80% opacity)
- All edges connected to the selected node are highlighted
- Connected nodes brighten slightly, unconnected nodes dim to 30% opacity
- The detail sidebar slides in from the right

#### Detail Sidebar (right side, ~30% width, appears on node selection)

Slides in from the right when a node is selected. 300px wide. Panel background with left card border.

**Header:**
- Source icon + type label (e.g., "Chat Message") in source color, 13pt medium
- Timestamp: "March 1, 2026 at 2:34 PM" in 11pt faint text
- Close button (×) top-right, faint text, brightens on hover

**Content Section:**
- Title: 15pt medium, primary text (e.g., the subject line, note title, or first line of chat)
- Body preview: 13pt regular, secondary text, 4-5 lines max, fades out with gradient if truncated
- Tags row: horizontal scroll of tag pills (topics, entities, people) — 11pt, `rgba(238, 203, 160, 0.1)` background, amber text, 6px radius
- Clicking a tag highlights all nodes with that tag in the graph

**Related Nodes Section:**
- Section header: "Connected" in 13pt medium, secondary text
- List of 4-5 related data points, each row:
  - Source icon (colored) + Title (13pt, primary text) + Timestamp (11pt, faint)
  - Relevance indicator: thin horizontal bar, amber fill proportional to relevance score
  - Clicking a related node selects it in the graph

**Actions:**
- Two buttons at the bottom, full-width, stacked:
  - **"Investigate in Explorer"** — amber accent fill, dark text, 13pt medium, 10px radius, arrow-right icon
  - **"Open Source"** — transparent with amber border, amber text, 13pt medium, 10px radius, external link icon

#### Legend (bottom-left corner, floating overlay)

Small semi-transparent card (`rgba(17, 11, 3, 0.85)` background), 12px radius, 12px padding.
- 6 rows: colored dot (8px) + source label (11pt, secondary text)
- One row per source type with their colors
- Below: "Node size = recency × frequency" in 10pt faint italic

---

### Frame 2: DataExplorer Mode

A comprehensive data table showing every interaction and data point across all sources as a unified chronological timeline. Think: personal activity log meets Datadog metrics explorer.

#### Filter Bar (same position as GraphView's filter bar)

Same source filter pills as GraphView (Chat, Email, Notes, Calendar, Reminders, Health).

Additional controls on the right:
- Sort dropdown: "Newest First" (default), with chevron. 13pt, secondary text.
- Density toggle: two small icons — list view (default, tighter rows) vs. comfortable view (more spacing)

#### Data Table (main content area)

Full-width table with the following columns:

**Column Headers (sticky top row):**
- Background: `rgba(17, 11, 3, 0.9)` (semi-opaque dark)
- Text: 11pt medium, faint text color, uppercase letter-spacing 0.5px
- Bottom border: divider color
- Columns: `☐` (checkbox, 32px) | `TIMESTAMP` (140px) | `SOURCE` (100px) | `TYPE` (100px) | `TITLE / SUMMARY` (flex, fills remaining) | `TAGS` (180px) | `⋯` (actions, 48px)

**Table Rows:**
- Alternating row backgrounds: transparent and `rgba(235, 223, 209, 0.02)` (barely visible zebra striping)
- Row height: 44px (list mode) or 56px (comfortable mode)
- Row hover: `rgba(238, 203, 160, 0.06)` background
- Row selected (checked): `rgba(238, 203, 160, 0.1)` background with left border accent (3px amber)
- Bottom border per row: divider color

**Cell content styling:**
- Checkbox: custom styled, amber accent when checked, 16px square, 4px radius
- Timestamp: 12pt monospace (SF Mono), faint text. Format: "Mar 1, 2:34p" (compact)
- Source: Colored icon (16px, source color) + label (12pt, secondary text)
- Type: 12pt, secondary text (e.g., "Message", "Event", "Metric", "Note Edit", "Flagged Email")
- Title/Summary: 13pt regular, primary text. Single line, truncated with ellipsis. Expandable on click.
- Tags: 2-3 small pills (10pt, `rgba(238, 203, 160, 0.08)` background, secondary text), "+N" overflow if more
- Actions: `⋯` icon (three dots), secondary text, reveals dropdown on click

**Show ~15-20 sample rows with realistic data, mixing all source types.** Example rows:
1. Chat message about "API security review" (amber icon)
2. Calendar event "Team standup" (purple icon)
3. Health metric "Heart rate: 72 bpm" (teal icon)
4. Email flagged "Q1 Budget Proposal" (blue icon)
5. Note edited "Project Architecture Notes" (green icon)
6. Reminder completed "Review pull request" (red icon)
7. Chat message about "Memory search optimization" (amber icon)
8. Health metric "Steps: 8,432" (teal icon)

**Expanded Row State (show one row expanded):**
- Row expands downward to reveal full content (up to 6 lines of body text)
- 13pt regular, secondary text
- Subtle indentation (20px left padding)
- Collapse icon (chevron up) replaces the expand icon

#### Selection Actions Bar (appears when rows are checked)

Sticky bar that slides up from the bottom of the table area when 1+ rows are selected. Full width, 56px tall.

- Background: `#110B03` with strong border on top
- Left: "**3 items selected**" — 13pt medium, primary text
- Center-right: three action buttons, horizontal:
  - **"Investigate"** — amber fill, dark text (`#040301`), 13pt medium, 10px radius, icon: `magnifyingglass.circle.fill`. This launches AI sub-agent analysis.
  - **"Visualize"** — transparent with amber border, amber text, 13pt medium, 10px radius, icon: `chart.line.uptrend.xyaxis`. This generates AI visualizations.
  - **"Clear"** — text-only button, secondary text, 13pt, icon: `xmark.circle`

#### Reports Section (below the table)

Collapsible section. Default: collapsed. Toggle: "Reports" header with chevron, 16pt medium section title.

**When expanded:**

Two sub-tabs (same pill style as source filters):
- **"AI Analyses"** — saved outputs from Investigate and Visualize actions
- **"Periodic Summaries"** — auto-generated daily/weekly/monthly rollups

**Report Cards (grid layout, 2-3 columns):**
Each card: 280px wide, panel background, card border, 16px radius, 16px padding.

- **Thumbnail area** (top, 100% width, 120px height): placeholder visualization or chart preview. Use a subtle gradient fill as placeholder (`rgba(224, 160, 50, 0.05)` to transparent).
- **Title**: 14pt medium, primary text (e.g., "Health Trends: Feb 2026" or "Security Research Analysis")
- **Metadata row**: icon for type (chart icon for Visualize, magnifying glass for Investigate, calendar icon for Periodic) + date generated (11pt, faint text)
- **Source badge**: small pill showing data sources used (e.g., "Health + Chat", 10pt)
- **Actions on hover**: "Re-run", "Export", "Delete" — tiny text buttons, faint text, appear on card hover

Show 4-5 sample report cards. Mix of:
- "Weekly Activity Summary — Feb 24-Mar 1" (periodic)
- "Sleep vs Productivity Correlation" (AI visualization)
- "Project Architecture Decision Analysis" (AI investigation)
- "Monthly Health Trends — February 2026" (periodic)
- "Email Response Time Patterns" (AI visualization)

---

### Additional Design Notes

1. **Transitions:** Design both modes on the same canvas size. The mode picker swaps between them. Include a subtle crossfade indication.

2. **Empty states are not needed** — design the populated, active state for both views.

3. **The aesthetic is warm, dark, and premium** — like a luxury instrument panel. Amber is the dominant accent color. Avoid cool grays or stark whites. Everything should feel warm and slightly golden-tinted.

4. **Depth is created through opacity, not shadows.** Use layered semi-transparent backgrounds rather than drop shadows. The card borders (1px, very low opacity amber) provide structure.

5. **The graph should feel alive** — imagine the nodes have subtle animation. Use slight randomness in node positions to suggest organic clustering, not a rigid grid.

6. **Information density is high but organized** — this is a power-user tool. Don't oversimplify. Show lots of data, but with clear visual hierarchy (primary text for important, secondary/faint for supporting).

7. **This sits alongside 5 other tabs** in the same app: Command (home), Explorer (files), Resources (LLMs/integrations), Health (biometrics), Wiki (architecture docs). The Research tab should feel cohesive with these siblings.
