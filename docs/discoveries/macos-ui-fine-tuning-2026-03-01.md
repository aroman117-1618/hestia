# Discovery Report: macOS UI Fine-Tuning

**Date:** 2026-03-01
**Confidence:** High
**Decision:** Implement in 3 sprints: (1) Navigator restructure + Explorer persistence, (2) Chat tab redesign, (3) Research view. App icon is a design-only deliverable that can happen in parallel at any time.

## Hypothesis

Five macOS UI refinements are proposed:
1. **Navigator restructure** -- reorder sidebar icons, make Home/Profile sticky (top/bottom), let middle icons be reorderable
2. **App icon** -- change from the current bolt/zap to a hearth/fireplace motif aligned with "Hestia" identity
3. **Research view** -- new tab implementing the Figma Make prompt (force-directed knowledge graph + DataExplorer table)
4. **Explorer persistent file tree** -- remember the selected folder across app launches
5. **Chat tab redesign** -- single agent per session, multi-session tabs (browser-like), agent profile photos in tabs

---

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Solid architecture to build on. `WorkspaceView` enum + `IconSidebar` + `WorkspaceRootView` switch are clean and modular. Agent avatar images already exist in both targets. `MacChatViewModel` already has `startNewConversation()`. Sessions DB table has all necessary columns. NeuralNetView provides a reference implementation for SceneKit graph rendering. Research view has a complete Figma Make prompt spec. | **Weaknesses:** No `GET /v1/sessions` list endpoint exists. No security-scoped bookmark infrastructure for persistent folder access. Chat panel is a single `MacChatPanelView` with one `MacChatViewModel` instance -- no concept of multiple parallel sessions. The Research view is the most complex single feature ever proposed for Hestia (2D force graph + data table + report cards + filter system). Icon reordering requires persistent storage + drag-and-drop infrastructure that does not exist. |
| **External** | **Opportunities:** Security-scoped bookmarks are well-documented (SwiftLee, AppCoda, Apple Forums). SpriteKit `ForceDirectedScene` library exists for the graph view. SwiftUI's `SpriteView` makes embedding straightforward. The Research view would be a flagship differentiator. Browser-tab chat UX is expected in modern AI assistants (ChatGPT, Claude). | **Threats:** Security-scoped bookmark bugs reported in macOS 26 (r.162781619). Force-directed graph libraries are unmaintained (last commits 2018-2020). Research view complexity could consume 2+ full sessions and introduce significant new surface area. Custom drag-and-drop for icon reordering on macOS is notoriously finicky. |

---

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | Chat tab redesign (multi-session tabs + agent photos). Explorer persistent file tree. | Navigator icon reorder (middle section). |
| **Low Priority** | Research view (flagship feature, but high effort). | App icon change (cosmetic, no functional impact). |

### Rationale

- **Chat tab redesign** is high-impact because it fundamentally changes how users interact with the app. Currently, switching agents wipes the conversation. Multi-session tabs preserve context across agent conversations -- this is table stakes for an AI assistant.
- **Explorer persistence** is high-impact because the current experience is broken: every time you relaunch, you lose your folder selection. This is a paper-cut that degrades the daily workflow.
- **Navigator reorder** is high-priority (users notice it) but low-impact (the current order works fine). The sticky home/profile is a quick win; draggable middle icons is nice-to-have.
- **Research view** is the highest-effort item on the list (~20+ new files, new backend endpoints, force graph physics engine). It's genuinely impressive but not blocking any current workflow.
- **App icon** is pure cosmetic. Important for brand identity but zero functional impact.

---

## Argue (Best Case)

### 1. Navigator Restructure
- The current icon order (house, map, server, heart, book) is arbitrary. Reordering to (house, explorer, health, wiki, resources, research) with home pinned top and profile pinned bottom matches desktop conventions (VS Code, Slack, Discord all pin home/settings).
- Sticky home/profile requires ~20 lines of code change in `IconSidebar.swift`. The current architecture already separates top icons from bottom icons with a `Spacer()`.
- Adding a new `WorkspaceView.research` case is trivial -- add the enum case, add the sidebar icon, add the view switch. The enum/switch pattern makes this O(1) complexity.

### 2. App Icon
- "Hestia" literally means "hearth." The current bolt/zap icon has no brand connection. A hearth icon creates instant recognition.
- macOS already has the full icon set infrastructure (10 sizes from 16x16 to 512x512@2x, Contents.json). Swapping PNGs is a file operation, not a code change.
- Figma has an [official macOS App Icon Template](https://www.figma.com/community/file/1040708197994685442/official-macos-app-icon-template) for correct sizing/padding.

### 3. Research View
- The Figma Make prompt (`docs/plans/2026-03-01-research-tab-figma-make-prompt.md`) is the most detailed design spec in the project -- 280 lines of precise specification.
- The GraphView mode would be the most visually impressive feature in the app. An Obsidian-style knowledge graph showing chat history, emails, notes, calendar events, and health data as interconnected nodes is a genuine differentiator.
- The DataExplorer mode is essentially a unified activity log -- something no other personal AI assistant offers.
- The existing `NeuralNetView` proves SceneKit graph rendering works in this codebase. The Research graph is a 2D evolution (simpler in some ways than the 3D neural net).

### 4. Explorer Persistent File Tree
- Security-scoped bookmarks are the Apple-blessed solution. The pattern is well-documented: `url.bookmarkData(options: .withSecurityScope)` on save, `URL(resolvingBookmarkData:)` on restore.
- Required entitlement (`com.apple.security.files.bookmarks.app-scope`) is a one-line addition.
- UserDefaults is sufficient for storing the bookmark data (single folder path per user).
- The current `NSOpenPanel` flow in `selectRootFolder()` already returns the URL needed to create the bookmark.

### 5. Chat Tab Redesign
- The backend already supports multiple concurrent sessions. The `sessions` DB table tracks id, mode, timestamps. The `RequestHandler._conversations` dict can hold multiple sessions simultaneously.
- Agent profile images already exist in both targets (hestia-profile, artemis-profile, apollo-profile). The `HestiaMode.avatarImage` property is ready.
- The current `agentTabBar` already renders per-agent tabs with avatars. The redesign is an evolution, not a rewrite.
- The `startNewConversation()` method already exists on `MacChatViewModel`. The `+` button in the current tab bar is wired but does nothing.

---

## Refute (Devil's Advocate)

### 1. Navigator Restructure
- **Icon reordering is cosmetically nice but functionally unnecessary.** Users have keyboard shortcuts (Cmd+1-6). Reordering icons means also reordering keyboard shortcuts, which breaks muscle memory.
- **Customizable middle icons** via drag-and-drop is disproportionate effort. It requires: persistent storage for order, drag-and-drop gesture handling, animation for reordering, a reset-to-default mechanism. This is 100+ lines of new code for a feature exactly zero users have requested.
- **Counter-argument:** Implement sticky home/profile (easy) but skip customizable middle icons. The reorder is a "someday" feature.

### 2. App Icon
- **The icon must be generated externally.** Claude Code cannot create bitmap images. Andrew needs to either commission art, use an AI image generator, or design it in Figma/Illustrator.
- **10 sizes are required** (16, 32, 128, 256, 512 at 1x and 2x). The icon must look good at 16x16 -- a detailed hearth/fireplace will be unrecognizable at that size.
- **The current bolt icon is fine.** It's recognizable and reads well at small sizes. A hearth icon risks being too detailed for the smallest sizes or too abstract to convey meaning.
- **Counter-argument:** The icon change is a design task, not an engineering task. It can happen whenever Andrew has or commissions the artwork.

### 3. Research View
- **This is a massive feature.** Conservative estimate: 15-25 new Swift files, 2-4 new backend endpoints (query memory chunks by type, list all data sources, aggregate timeline), and a force-directed graph physics engine.
- **The force graph is the hardest part.** The existing `ForceDirectedScene` and `SpriteKit-Force-Directed` libraries are unmaintained (2018-2020). The Hestia `NeuralNetView` uses SceneKit with a custom force simulation -- adapting that to 2D with 60-80 nodes is possible but nontrivial.
- **Data availability is a problem.** The spec calls for "emails, notes, calendar events, reminders, health data" as node sources. Currently, the backend only stores chat history and memory chunks. Email/notes/calendar/reminders are tool-call results that are ephemeral, not persisted as searchable data. The Research view would need a new data aggregation layer.
- **The DataExplorer table requires a unified timeline API** that doesn't exist. Building this touches memory, health, and Apple integration modules.
- **Counter-argument:** The Research view should be the LAST thing implemented, after all foundational improvements are in place. It's the capstone feature, not a quick win.

### 4. Explorer Persistent File Tree
- **Stale bookmarks are a real risk.** If the user moves or deletes the folder, the bookmark becomes stale. The code needs graceful fallback (detect stale -> show "Select Folder" again).
- **Security-scoped bookmark bugs** have been reported on macOS 26 (the current target). A `/.nofollow/` path bug affected bookmark resolution. This is reportedly fixed in 26.2, but it's a risk for early adopters.
- **The current app is NOT sandboxed** (no App Store distribution). If the app has full disk access, security-scoped bookmarks may be unnecessary -- a simple UserDefaults URL string might suffice.
- **Counter-argument:** Check whether the app is sandboxed. If not, this is a 10-line change (save URL string to UserDefaults, restore on launch). If sandboxed, the bookmark approach is needed.

### 5. Chat Tab Redesign
- **"Single agent per session" is a breaking change** to the current UX model. Currently, users can switch agents mid-conversation (the `switchMode()` method). The proposed design pins one agent per tab. This is a philosophical decision, not just a UI change.
- **There's no `GET /v1/sessions` list endpoint.** Building multi-tab chat requires: (a) a new backend list-sessions endpoint, (b) a `list_recent_sessions()` database method, (c) client-side session persistence, and (d) UI for session history browsing.
- **Performance concern:** Each session tab would need its own `MacChatViewModel` instance with its own message array. With 5+ open sessions, memory usage could be significant if messages aren't lazy-loaded.
- **Session restoration on app relaunch** is complex. Currently, session state is ephemeral (in-memory only). Restoring tabs after relaunch requires persisting the list of open session IDs and re-fetching their histories.
- **Counter-argument:** Start simple. Phase 1: multiple tabs that each create a new session. Phase 2: session persistence across app launches. Phase 3: session history browsing. Don't try to build the full browser-tab experience in one sprint.

---

## Third-Party Evidence

### Comparable Implementations

1. **ChatGPT Desktop (macOS):** Uses a sidebar for conversation history, not browser-style tabs. Each conversation is a separate item in a list. Agent switching (GPT-4, GPT-4o) happens within a conversation, not per-conversation.

2. **Claude Desktop (macOS):** Similar to ChatGPT -- sidebar-based conversation list. No tab metaphor.

3. **Arc Browser:** Pioneered the vertical sidebar + tabbed workspace model on macOS. Spaces (workspaces) are persistent. This is the closest analog to what Hestia proposes, but Arc was built by a team of 30+ engineers.

4. **VS Code / Cursor:** Uses an icon sidebar (Activity Bar) with pinned top/bottom items. The middle icons are NOT reorderable by default (extensions add icons in a fixed order). This validates the "sticky home/profile, fixed middle" approach.

5. **Obsidian:** The graph view that inspired the Research tab. Obsidian renders their graph with Canvas 2D (HTML), not SpriteKit/SceneKit. The graph is performant with 1000+ nodes because it uses WebGL acceleration.

### Alternative Approaches

- **For the Research graph:** Consider using a `WKWebView` with D3.js or vis.js instead of native SpriteKit. This would give access to the mature force-directed graph ecosystem (D3's force simulation is battle-tested with millions of users). The tradeoff is breaking the native-only principle.
- **For the chat tabs:** Consider Apple's new TabView improvements in SwiftUI (WWDC 25) or the [darrarski/swiftui-tabs-view](https://github.com/darrarski/swiftui-tabs-view) library for a customizable tab bar that fits the dark theme.
- **For icon reordering:** Skip it entirely and use a fixed, well-chosen order. No major macOS app (VS Code, Slack, Discord, Figma) lets users reorder sidebar icons.

---

## Recommendation

### Implementation Order (3 Sprints)

**Sprint A: Foundation (Navigator + Explorer Persistence)**
Effort: ~3-4 hours
1. Restructure IconSidebar: pin Home top, Profile bottom, fixed middle order (Explorer, Health, Wiki, Resources, Research placeholder)
2. Add `WorkspaceView.research` enum case (placeholder view)
3. Update keyboard shortcuts to match new order
4. Implement Explorer folder persistence via UserDefaults (check sandbox status first; use security-scoped bookmarks only if sandboxed)
5. Update `MacExplorerViewModel` to restore last-used folder on init

**Sprint B: Chat Tab Redesign**
Effort: ~6-8 hours
1. Backend: Add `GET /v1/sessions` list endpoint + `list_recent_sessions()` DB method
2. Backend: Add `title` column to sessions table (auto-generated from first user message)
3. Create `ChatSession` model: sessionId, mode, messages, title, lastActivity
4. Create `ChatTabManager` (observable): manages array of `ChatSession`, active session index
5. Redesign `MacChatPanelView` tab bar: each tab shows agent avatar photo + session title (truncated)
6. Wire `+` button to create new session (picks current agent)
7. Wire tab close (X button) to end session
8. Each tab maintains its own message history independently

**Sprint C: Research View**
Effort: ~12-16 hours (largest single feature)
1. Create `ResearchView` with mode picker (Graph / Explorer)
2. Implement `ResearchGraphView` using SpriteKit 2D force-directed layout
3. Implement `ResearchDataExplorerView` as a unified data table
4. Backend: New endpoint to query memory chunks with source-type filtering
5. Connect filter pills to source-type queries
6. Implement node selection -> detail sidebar
7. Wire "Investigate in Explorer" action to switch tabs

**Parallel: App Icon**
Effort: ~1 hour (code) + design time
1. Andrew creates or commissions hearth/fireplace artwork
2. Generate 10 required sizes using the [macOS App Icon Template](https://www.figma.com/community/file/1040708197994685442/official-macos-app-icon-template)
3. Replace PNGs in `macOS/Assets.xcassets/AppIcon.appiconset/`
4. Update the sidebar logo in `IconSidebar.swift` to use the new icon image instead of `bolt.fill`

### What to Skip

- **Customizable/draggable middle icons.** No major macOS app does this. Use a fixed, well-chosen order. Revisit only if user feedback demands it.
- **Full session restoration across app relaunches** (Sprint B scope). Start with in-memory tabs that reset on relaunch. Add persistence later.
- **Reports section** in DataExplorer (Research view). The Figma spec includes AI-generated report cards -- this is a v2 feature that requires significant backend infrastructure.

### Confidence: High

The architecture is clean and modular. Each change builds on well-understood patterns. The main risk is the Research view's scope -- but by scheduling it last, we ensure the foundational improvements (navigation, persistence, chat) ship regardless.

### What Would Change This Recommendation

- If the app IS sandboxed: Explorer persistence requires security-scoped bookmarks (more complex, +1 hour)
- If Andrew prioritizes the Research view: it should still come after Sprint B, since the graph visualization depends on having robust session/memory data
- If time is severely constrained: do Sprint A only (highest ROI per hour invested)

---

## Final Critiques

### The Skeptic: "Why won't this work?"
**Challenge:** The Research view force-directed graph is the biggest risk. SpriteKit force-directed libraries are abandoned. You'll end up writing custom physics.
**Response:** Fair concern. The existing `NeuralNetView` already has a custom force simulation in SceneKit. Porting that to 2D SpriteKit is simpler than building from scratch. And SpriteKit's built-in physics body system (SKPhysicsBody) provides repulsion/attraction without a library. Worst case, we use a `WKWebView` with D3.js -- it's a known escape hatch.

### The Pragmatist: "Is the effort worth it?"
**Challenge:** Sprint C (Research view) is 12-16 hours for a feature that aggregates data the backend doesn't fully have yet. Is this the best use of 3 sessions?
**Response:** No, Sprint C should be deferred until the data aggregation layer exists. Sprints A and B are high-ROI (7-12 hours total) and deliver immediate UX improvements. Sprint C is the "someday" sprint -- do it when the backend can actually supply email, calendar, and notes data as structured timeline entries.

### The Long-Term Thinker: "What happens in 6 months?"
**Challenge:** The chat tab redesign assumes one agent per session. But what if users want multi-agent conversations? Or cross-session search?
**Response:** The `ChatSession` model should be designed with extensibility in mind. Include a `mode` field per session but don't enforce it at the UI level yet. A future enhancement could allow agent switching within a tab (like the current behavior) while still maintaining separate tab sessions. Cross-session search is a backend feature (`GET /v1/sessions/search`) that can be added without touching the tab UI.

---

## Open Questions

1. **Is the macOS app sandboxed?** This determines the complexity of Explorer folder persistence (UserDefaults string vs. security-scoped bookmark).
2. **Should the chat redesign enforce "one agent per session" or allow agent switching within a session?** The current UX allows mid-conversation switching. Removing this could frustrate power users.
3. **Does Andrew have a hearth/fireplace icon design?** The app icon change is blocked on artwork, not code.
4. **What data sources should the Research view aggregate?** The Figma spec lists 6 sources (Chat, Email, Notes, Calendar, Reminders, Health). Currently, only Chat and Health data are persisted. Email/Notes/Calendar/Reminders are ephemeral tool-call results.
5. **Should the sidebar logo also change to match the new app icon?** Currently it's a `bolt.fill` SF Symbol on an orange gradient. A hearth icon would need a custom image asset, not an SF Symbol.
6. **What keyboard shortcut for Research?** If Research is added as a 7th icon, it would be Cmd+7. But the current Cmd+\ (toggle chat) uses the backslash key. No conflict, but worth confirming the shortcut assignment.

---

## Sources

- [Security-scoped bookmarks for URL access - SwiftLee](https://www.avanderlee.com/swift/security-scoped-bookmarks-for-url-access/)
- [Persist Access to User Folders - SwiftyLion](https://swiftylion.com/articles/persist-and-retrieve-user-folders-access)
- [Deploying Mac Apps: Remember User Intent for Folders - AppCoda](https://www.appcoda.com/mac-apps-user-intent/)
- [Official macOS App Icon Template - Figma](https://www.figma.com/community/file/1040708197994685442/official-macos-app-icon-template)
- [ForceDirectedScene - GitHub](https://github.com/knightcode/ForceDirectedScene)
- [SpriteKit-Force-Directed - GitHub](https://github.com/joenot443/Spritekit-Force-Directed)
- [SwiftUI Tabs View - GitHub](https://github.com/darrarski/swiftui-tabs-view)
- [Building a Native macOS Browser with SwiftUI](https://www.blog.brightcoding.dev/2025/12/06/building-a-native-macos-browser-with-swiftui-the-complete-developer-guide-to-creating-the-next-generation-web-experience/)
- [Glassifying Tabs in SwiftUI (WWDC 25)](https://swiftwithmajid.com/2025/06/24/glassifying-tabs-in-swiftui/)
- [Apple Developer Forums - Security-scoped URL Clarification](https://developer.apple.com/forums/thread/798402)
- [Hestia Symbols - Symbol Sage](https://symbolsage.com/hestia-hearth-greek-goddess/)
- [Hestia Symbols Explained - Spells8](https://spells8.com/lessons/hestias-symbols-explained-fire-hearth-peace/)
