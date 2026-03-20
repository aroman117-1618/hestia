# macOS App Wiring Sprints — Comprehensive Plan (Rev 3)

**Created:** 2026-03-19
**Revised:** 2026-03-19 (Rev 3 — Andrew's design decisions incorporated)
**Scope:** Wire all remaining stub/placeholder/non-interactive UI in the macOS app
**Audit basis:** File-by-file review of 146 macOS Swift files, 17 ViewModels, 218 backend endpoints, Shared/ cross-reference, and live screenshot validation
**Methodology:** `docs/discoveries/ui-wiring-audit-methodology-2026-03-19.md`

## Design Decisions (Confirmed by Andrew)

### Progress Rings — Internal / External / System Activity Scores
The 3 hero progress rings map to the 3 Command Center tabs, giving a pulse-check of each domain:

**Ring 1: Internal** — "How busy is your day?"
- Composite of: calendar event count today, health metrics sync status, pending memory reviews
- Data sources: `EventKit` (local), `GET /v1/health_data/summary`, `GET /v1/memory/pending-reviews`
- Display: percentage of "day fullness" (e.g., 8 events = high, 0 = low), or a normalized activity score
- Label: "Internal" / subtitle: "Your Day"

**Ring 2: External** — "How much activity across external feeds?"
- Composite of: positive trades (win rate from `GET /v1/trading/summary`), news alerts (`GET /v1/newsfeed/unread-count`), investigations run (`GET /v1/investigate/history` count)
- Weights: Trade win rate (40%), news activity normalized (30%), investigation completion rate (30%)
- Label: "External" / subtitle: "World Activity"

**Ring 3: System** — "How healthy is the system?"
- Composite of: successful order execution rate (`GET /v1/orders` success/total), pending principles assessed against approval rate (`GET /v1/research/principles`), minimal system alerts (inverse of `GET /v1/learning/alerts` unacknowledged count)
- Weights: Order success rate (40%), principle approval ratio (30%), alert health (30% — higher = fewer unacked alerts)
- Label: "System" / subtitle: "Hestia Health"

**Viability assessment:** All data sources exist on the backend. The composite scoring needs a lightweight normalization function in the ViewModel (no new endpoints required). Main design question: should the rings show absolute percentages or relative-to-baseline? Recommend starting with absolute (simpler) and tuning later.

### "View Reports" → External > Investigations Tab
- Clicking "View Reports" navigates to the External activity tab, Investigations sub-tab
- This is where Hestia's responses/assessments appear when Andrew sends content via iPhone/macOS shortcuts
- Content types: web articles, TikTok videos, Instagram posts, screenshots
- The investigation detail view becomes the primary "report" view

### Health → Internal Activity Tab (Not Standalone)
- Health was merged into Command Center under Internal > Health Summary (Sprint 25.5)
- No separate Health sidebar tab — wiring goes to InternalActivityView's health section
- This is where HealthKit data (steps, resting HR, sleep) should display

### Voice → Chat UI Only (macOS)
- Voice recording wiring targets MacMessageInputBar in the chat panel
- No standalone voice view needed
- iOS voice will be a separate future effort

---

## Deep Audit Findings

### Audit 1: Hardcoded Values (16 findings)

**HIGH severity (user-visible fake data):**

| File | Line | Hardcoded | Should Be |
|------|------|-----------|-----------|
| HeroSection.swift | 40 | `"Last updated 2 min ago"` | `RelativeDateTimeFormatter` from last sync time |
| HeroSection.swift | 56 | `"Stonehurst is running smoothly. 12 updates..."` | `currentMode.displayName` + `pendingMemoryCount` |
| HeroSection.swift | 130-132 | Progress rings: 99.2%, 87%, 18% | systemHealth uptime, metaMonitor positiveRatio, memoryHealth improvement |
| HeroSection.swift | 141 | `"All systems operational"` (always green) | `systemHealth.status` — red when server down |
| OrdersPanel.swift | 79 | `"Started 45 min ago"` / `"Finished yesterday"` | `RelativeDateTimeFormatter(order.createdAt)` |
| OrdersPanel.swift | 93 | `geo.size.width * 0.64` (fake progress) | `geo.size.width * order.progressPercentage` |

**MEDIUM severity (color tokens):**

| File | Line | Literal | Should Be |
|------|------|---------|-----------|
| HeroSection.swift | 132 | `Color(hex: "00D7FF")` | `MacColors.cyanAccent` (new) |
| BiologicalAgeCard.swift | 94 | `Color(hex: "00FFB2")` | `MacColors.healthLime` (new) |
| BiologicalAgeCard.swift | 141 | `Color(hex: "FF6467")` | `MacColors.calorieRed` (new) |
| HealthMetricsRow.swift | 36, 93, 121 | `Color(hex: "FF6467")`, `Color(hex: "8B5CF6")` | `MacColors.heartRed`, `MacColors.sleepPurple` (new) |
| MarkdownEditorView.swift | 33, 81 | `Color(hex: "1E1E1E")`, `Color(hex: "1A1A1A")` | `MacColors.editorBackground` (new) |
| CalendarWeekStrip.swift | 117 | `Color(hex: "026DFF")` | `MacColors.blueAccent` (new) |

### Audit 2: Shared Components — Built But Not Wired

**Components that exist in `Shared/` and are MORE complete than macOS equivalents:**

| Shared Component | What It Has | macOS Status |
|-----------------|-------------|--------------|
| **OrdersWidget.swift** | Full `OrderInlineForm` (name, prompt, time, frequency, resources, validation), `OrderRow` with status/toggle/delete, `ResourceChip` grid | macOS `OrdersPanel.swift` is read-only display, no creation |
| **MemoryWidget.swift** | Memory review with approve/reject workflow, confidence scoring | macOS has no memory review UI at all |
| **AlertsWidget.swift** | Alert timeline with expandable details, status colors | macOS has alerts in LearningMetricsPanel but no drill-down |
| **BriefingCard.swift** | Daily briefing with collapsible summary | macOS Command Center has no briefing |
| **VoiceRecordingOverlay.swift** | Voice input with waveform, timer, cancel/send | macOS mic button is stub |
| **ModeIndicator.swift** | Agent mode badge (SOLO/ARTEMIS/APOLLO) | macOS doesn't show which agent is active |
| **FilterBar.swift** | Newsfeed filter chips with unread counts | macOS newsfeed has no type filtering |
| **ProactiveSettingsView.swift** | Interruption policy, briefing cadence | Not in macOS Settings |
| **WikiDecisionsView.swift** | ADR browser | macOS Wiki missing decisions section |
| **WikiModuleListView.swift** | Module index navigation | macOS Wiki has no module browser |
| **AgentCustomizationView.swift** | Full agent instruction editor with capabilities | macOS `AgentDetailSheet` is simpler |
| **IntegrationDetailView.swift** | Integration credential entry + status detail | macOS has no integration detail sheet |

### Audit 3: Error Handling & Offline Behavior (Critical)

**The macOS app has NO server connectivity awareness:**

1. **`NetworkMonitor.swift` exists** (fully functional NWPathMonitor) — used by iOS, **not instantiated in macOS**
2. **All 8 data load methods** in `MacCommandCenterViewModel` catch errors silently — only `#if DEBUG print()`, never set `errorMessage`
3. **`errorMessage` property exists** (line 19) but is **never set anywhere** in the ViewModel
4. **`isLoading` completes even if all requests fail** — no way to distinguish "loaded empty" from "failed to load"
5. **`GlobalErrorBanner.swift` exists** but is **not used in CommandView or WorkspaceRootView**
6. **APIClient maps errors** to user-friendly messages (`HestiaError.serverUnreachable: "Can't reach Hestia server"`) but they're swallowed

**Result:** Server goes down → App shows "All systems operational" with empty panels → User has zero indication anything is wrong.

### Audit 4: Backend Endpoints — Available But Unused

**130 of 218 endpoints (59%) are not called by macOS.** Key gaps:

| Category | Unused Endpoints | What They Enable |
|----------|-----------------|------------------|
| **Memory CRUD** | GET /chunks, PUT /chunks/{id}, PATCH /{id}/sensitive | Browse, edit, flag memory |
| **Memory Maintenance** | POST /consolidation/execute, POST /pruning/execute | One-click consolidation, prune stale |
| **Knowledge Graph** | GET /entities, /facts, /episodes, /principles + 15 more | Full entity/fact browser, principle approval |
| **Orders CRUD** | GET /{id}, POST /{id}/execute, DELETE /{id} | View detail, manual trigger, delete |
| **Proactive** | GET /briefing, GET /patterns, POST /analyze | Daily briefing, pattern detection |
| **Newsfeed Ops** | POST /{id}/read, POST /{id}/dismiss + filtered GET | Mark read, dismiss, filter by type |
| **Inbox Detail** | GET /{id}, POST /{id}/archive, POST /{id}/read | Item detail, archive, mark read |
| **Tasks** | GET /{id}, POST /{id}/approve/cancel/retry | Background task management |
| **Investigations** | GET /{id}, POST /compare | Detail view, comparison |

---

## Revised Sprint Structure

### Sprint 31: Server Awareness + Command Center (Est. 12-14h)

**Theme:** Make the dashboard truthful — real data, real status, working buttons.

| WS | Task | Files | Effort |
|----|------|-------|--------|
| **WS1** | **Wire NetworkMonitor to macOS** — Instantiate in `HestiaApp.swift` or `WorkspaceRootView`, inject via `@EnvironmentObject`. Show `OfflineBanner` at top of CommandView when `!isConnected` | `WorkspaceRootView.swift`, `CommandView.swift`, existing `NetworkMonitor.swift` | 1.5h |
| **WS2** | **Fix error handling in all ViewModels** — Set `errorMessage` on catch instead of silent swallow. Show error in relevant view (banner or inline). Add retry button. Pattern: `catch { errorMessage = error.localizedDescription }` | All 17 macOS ViewModels | 2h |
| **WS3** | **Wire Hero progress rings** — Replace hardcoded 99.2%/87%/18% with Internal/External/System activity scores. **Internal ring:** composite of today's calendar count (EventKit), health sync status, pending memory count. **External ring:** composite of trading win rate, newsfeed unread count, investigation completion count. **System ring:** composite of order success rate, principle approval ratio, inverse unacked alert count. Add `computeRingScores()` to ViewModel with lightweight normalization. Bind status badge to `systemHealth.status`. Bind "Last updated" to actual sync timestamp. Bind "X updates" to `pendingMemoryCount` | `HeroSection.swift`, `MacCommandCenterViewModel.swift` | 3h |
| **WS4** | **Wire Hero buttons** — "New Order" opens sheet containing adapted `OrderInlineForm` from `Shared/Views/CommandCenter/Widgets/OrdersWidget.swift` (restyle with MacColors tokens). Wire save to `POST /v1/orders`. **"View Reports" navigates to External > Investigations tab** (switch to External activity + select Investigations sub-tab) | `HeroSection.swift`, adapt `OrderInlineForm`, `CommandView.swift` tab navigation | 3h |
| **WS5** | **Fix OrdersPanel** — Replace hardcoded timestamps with `RelativeDateTimeFormatter`. Replace 64% progress with actual order progress. Wire "View all" to System Activity tab. Make cards tappable → detail sheet with execute/pause/delete buttons using `GET/POST/DELETE /v1/orders/{id}` | `OrdersPanel.swift`, new `OrderDetailSheet.swift` | 2h |
| **WS6** | **Consolidate color tokens** — Add 7 new tokens to MacColors (`cyanAccent`, `healthLime`, `calorieRed`, `heartRed`, `sleepPurple`, `editorBackground`, `blueAccent`). Replace all `Color(hex:)` in View files | `DesignSystem/MacColors.swift`, ~6 View files | 1.5h |

**Acceptance:** Hero shows real metrics from server. Status badge turns red when server is down. Offline banner visible. All buttons do something. No hardcoded fake data.

---

### Sprint 32: Interactivity + Navigation (Est. 10-12h)

**Theme:** Every list item tappable, every screen reachable, detail views for everything.

| WS | Task | Files | Effort |
|----|------|-------|--------|
| **WS1** | **Make Newsfeed interactive** — Wrap rows in `Button`. `onTapGesture` opens `NewsfeedDetailSheet` (title, body, source, timestamp). Swipe to mark read → `POST /v1/newsfeed/{id}/read`. Add "Mark all read" in header. Add filter chips (from Shared `FilterBar` pattern) | `NewsFeedListView.swift`, new `NewsfeedDetailSheet.swift`, `MacCommandCenterViewModel.swift` | 3h |
| **WS2** | **Make Investigations interactive** — Wrap cards in `Button`. Open `InvestigationDetailSheet` with full analysis, key points, source URL, "Open Source" button. Fetch via `GET /v1/investigate/{id}` | `InvestigationsListView.swift`, new `InvestigationDetailSheet.swift` | 2h |
| **WS3** | **Make Calendar events tappable** — `onTapGesture` on day columns shows popover with that day's events. Include "Open in Calendar" button. Events already loaded from EventKit | `CalendarWeekStrip.swift` | 1h |
| **WS4** | **Add Trading sidebar tab** — Add `.trading` case to workspace navigation. Route to full `TradingMonitorView`. Keep embedded version in Command Center as compact summary | `IconSidebar.swift`, `WorkspaceRootView.swift` | 1.5h |
| **WS5** | **Stat cards as navigation** — Make each stat card tappable: Unread → External > News tab, Memory → Memory Browser screen, Orders → System Activity tab, Events → Internal tab (scroll to calendar), Health → Internal tab (scroll to health), Feed → External Activity tab | `StatCardsRow.swift` | 1.5h |
| **WS6** | **Add Agent Mode indicator** — Show current agent mode (HESTIA/ARTEMIS/APOLLO) in sidebar or hero, using ModeIndicator pattern from Shared. Fetch from server or derive from last chat response | `IconSidebar.swift` or `HeroSection.swift` | 1h |
| **WS7** | **Add Briefing card to Command Center** — Port `BriefingCard` from Shared. Fetch daily briefing from `GET /v1/proactive/briefing`. Show collapsed by default, expandable | `CommandView.swift`, adapt `BriefingCard` | 2h |

**Acceptance:** Every item in Command Center is interactive. Detail sheets dismiss cleanly and refresh parent data. User can reach every feature from sidebar + stat cards.

---

### Sprint 33: Memory & Knowledge Graph Wiring (Est. 10-12h)

**Theme:** Unlock the 34 research/memory endpoints currently invisible to the user.

| WS | Task | Files | Effort |
|----|------|-------|--------|
| **WS1** | **Memory Browser — edit/delete chunks** — Add swipe-to-delete with `DELETE /v1/memory/chunks/{id}`. Add edit sheet with `PUT /v1/memory/chunks/{id}`. Add "Flag sensitive" toggle with `PATCH /v1/memory/chunks/{id}/sensitive` | `MemoryBrowserView.swift`, `MemoryChunkRow.swift`, `MacMemoryBrowserViewModel.swift` | 3h |
| **WS2** | **Memory maintenance panel** — Add "Consolidation" button: preview → confirm → execute (`POST /v1/memory/consolidation/preview` then `/execute`). Add "Prune stale" button: preview → confirm → execute. Show before/after stats | New `MemoryMaintenanceSheet.swift` | 3h |
| **WS3** | **Knowledge Graph entity browser** — Add entity list sidebar to Research tab. Search entities via `GET /v1/research/entities/search`. Click entity → show facts, episodes, related entities | `ResearchView.swift`, new `EntityBrowserPanel.swift` | 3h |
| **WS4** | **Principles editor** — Show principles list from `GET /v1/research/principles`. Allow approve/reject via `POST /v1/research/principles/{id}/approve`. Show principle source and confidence | `ResearchView.swift` (principles tab already exists) | 2h |
| **WS5** | **Fact timeline** — Add temporal fact browser: `GET /v1/research/facts/timeline`. Show facts changing over time. Allow time-travel queries via `GET /v1/research/facts/at-time` | New `FactTimelinePanel.swift` | 2h |

**Acceptance:** User can browse, edit, and delete memories. Can run consolidation and pruning. Can explore entities, facts, and principles in the knowledge graph.

---

### Sprint 34: Voice (Chat UI) & Task Management (Est. 12-14h)

**Theme:** Voice input via chat panel mic button + background task visibility. Voice is macOS chat UI only (iOS voice is a separate future effort).

| WS | Task | Files | Effort |
|----|------|-------|--------|
| **WS1** | **Audio capture** — Implement `AVAudioRecorder` in new `AudioRecorderManager.swift`. Request mic permission. Record to temp `.m4a`. Wire to existing mic button state in `MacMessageInputBar` | `MacMessageInputBar.swift`, new `AudioRecorderManager.swift` | 3h |
| **WS2** | **Transcription** — Integrate `SFSpeechRecognizer` for on-device transcription. Show real-time transcript. Fallback to Whisper via Ollama if available | New `TranscriptionService.swift` | 4h |
| **WS3** | **Send transcript** — On stop, insert transcript into input bar. User can edit before sending. Auto-send option. Wire voice quality analysis to `POST /v1/voice/quality-check` | `MacMessageInputBar.swift`, `MacChatViewModel.swift` | 2h |
| **WS4** | **Background task management** — Add "Tasks" section to System Activity showing background tasks. Approve/cancel/retry via `POST /v1/tasks/{id}/approve|cancel|retry`. Show task progress and approval requests | `SystemActivityView.swift`, new `TaskManagerPanel.swift` | 2h |
| **WS5** | **Inbox detail actions** — Add right-click context menu to inbox items: archive, mark read, open source. Wire to `POST /v1/inbox/{id}/archive`, `/read` | `ExplorerInboxView.swift`, `InboxDetailSheet.swift` | 1.5h |

**Acceptance:** Voice recording captures real audio, transcribes, and sends as chat message. Background tasks visible and manageable. Inbox items have full context actions.

---

### Sprint 35: Polish & Consistency (Est. 8-10h)

**Theme:** Professional error handling, loading states, and missing Settings pages.

| WS | Task | Files | Effort |
|----|------|-------|--------|
| **WS1** | **Loading skeletons everywhere** — Add `SkeletonLoader` to: Hero section, stat cards, all activity tabs, memory browser, research graph. Use `.redacted(reason: .placeholder)` where appropriate | Various Views | 2h |
| **WS2** | **Empty states with actions** — Every empty list gets actionable empty state: "No investigations yet — use /investigate in chat", "No orders — create one ↗", etc. | Various Views | 1.5h |
| **WS3** | **Proactive Settings page** — Port `ProactiveSettingsView` from Shared. Wire interruption policy, briefing cadence, reminder preferences to backend | New `MacProactiveSettingsView.swift` | 2h |
| **WS4** | **Integration detail sheets** — Port `IntegrationDetailView` from Shared. Show integration credentials, connection status, last sync. Wire to backend | `MacIntegrationsView.swift`, new detail sheet | 1.5h |
| **WS5** | **Wiki — decisions + module browser** — Add ADR browser tab and module index navigation to Wiki. Wire to `GET /v1/wiki/articles` with category filters | `MacWikiView.swift`, `MacWikiSidebarView.swift` | 2h |
| **WS6** | **Dark mode audit** — Test all screens in both modes. Fix any hardcoded colors missed in Sprint 31 WS6 | Various | 1h |

**Acceptance:** No empty screens without context. Settings complete. Loading/error states on every data-fetching view. Dark mode clean.

---

## Effort Summary

| Sprint | Hours | Theme |
|--------|-------|-------|
| Sprint 31 | 12-14h | Server awareness + Command Center truthfulness |
| Sprint 32 | 10-12h | Interactivity + navigation |
| Sprint 33 | 10-12h | Memory + Knowledge Graph unlock |
| Sprint 34 | 12-14h | Voice + chat + tasks |
| Sprint 35 | 8-10h | Polish + settings + consistency |
| **Total** | **52-62h** | **~5-6 weeks at 12h/week** |

## Priority Order

**Sprint 31 first** — Most impactful. Dashboard stops lying, buttons work, server status visible.
**Sprint 32 second** — Unlocks navigation, makes every list interactive.
**Sprint 33 third** — Massive feature unlock (34 hidden endpoints), differentiating value.
**Sprint 34 fourth** — Voice is a big UX win but can defer. Task management fills a gap.
**Sprint 35 last** — Polish pass. Should run after everything else is wired.

## Key Decisions (RESOLVED — Andrew 2026-03-19)

1. **Progress rings** → ✅ Internal / External / System activity composite scores. Each ring maps to one of the three Command Center tabs. See "Design Decisions" section above for full data source breakdown.

2. **"View Reports"** → ✅ Navigates to External > Investigations tab. This is where Hestia's assessments from iPhone/macOS shortcut submissions (articles, videos, screenshots) appear.

3. **Health tab** → ✅ Stays merged into Command Center under Internal > Health Summary. No standalone sidebar tab. Wiring targets `InternalActivityView`.

4. **Voice** → ✅ Chat UI only on macOS (mic button in `MacMessageInputBar`). iOS voice is a separate future effort.

## Out of Scope
- iOS app wiring (separate effort)
- New backend endpoints (we wire to what exists)
- MCP Server Management (backend doesn't exist yet)
- Mobile-only features (QR scanner, lock screen, push registration)
