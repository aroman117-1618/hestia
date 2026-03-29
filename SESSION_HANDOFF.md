# Session Handoff — 2026-03-28 (Command Center Restructure)

## Mission
Restructure the macOS Command Center from 3 legacy tabs (Internal, Newsfeed, System Alerts) to 3 purpose-driven tabs (Dashboard, Activity, Orders) with a new card-based dashboard design, unified activity feed with detail panels, and workflow canvas as the default Orders view.

## Completed

### Command Center Tab Restructure (v1.13.0 → v1.15.0)
- **Tab enum + routing**: Renamed `CommandSubTab` from `.internal/.newsfeed/.systemAlerts` to `.dashboard/.activity/.orders` (`WorkspaceState.swift`, `CommandView.swift`)
- **DashboardTabView** (`macOS/Views/Command/DashboardTabView.swift`): 4 health stat cards, 2-week calendar (EventKit), tasks/reminders (EventKit), trading card with lookback toggle + kill switch
- **DashboardTabViewModel** (`macOS/ViewModels/DashboardTabViewModel.swift`): Aggregates health API, EventKit calendar/reminders, trading API. Includes `requestReminderAccess()` fix
- **ActivityTabView** (`macOS/Views/Command/ActivityTabView.swift`): Feed list with filter pills (All/Orders/Alerts/System), selected state highlighting
- **ActivityTabViewModel** (`macOS/ViewModels/ActivityTabViewModel.swift`): CacheFetcher-based feed loading, filter logic, detail panel state, send-to-chat via NotificationCenter
- **ActivityDetailPanelView** (`macOS/Views/Command/ActivityDetailPanelView.swift`): Slide-over panel (420px) with per-type content: order execution timeline, alert detail, self-dev suggestion, system event. All types include "Send to Chat" button
- **OrdersTabView** (`macOS/Views/Command/OrdersTabView.swift`): Wraps existing workflow views with `showCanvas = true` default
- **Canvas bridge fix** (`WorkflowCanvas/src/WorkflowApp.tsx`): Fixed handler-chain race — `window.loadWorkflow` set directly in `useEffect`
- **Canvas emoji cleanup**: All 6 React node types replaced emoji icons with inline SVGs
- **Deleted 7 old files**: InternalTabView/ViewModel, NewsfeedTabView/ViewModel, SystemAlertsTabView/ViewModel, PLLookbackToggle
- **Send to Chat**: `hestiaSendToChat` notification + `MacChatPanelView` receiver
- **Newsfeed backend**: Added `TRADING` + `SENTINEL` sources/aggregators to `hestia/newsfeed/manager.py`
- **Dashboard fixes**: Reminders permission, removed fake health deltas, trading P&L delta fixed, lookback wired to API, layout fixes
- **Browser mockup**: `docs/mockups/command-center-v2.html` — interactive reference

### Key Commits
- `5f15939` feat(macOS): restructure Command Center tabs (v1.13.0)
- `954a2fa` fix(canvas): bypass handler chain race (v1.13.2)
- `9ecd1f2` fix(dashboard+activity): wire missing data sources (v1.14.0)
- `fb2690f` fix(dashboard): layout fixes

## In Progress
- **Health stat cards**: Code compiles but may need clean build (Shift+Cmd+K → Cmd+B) to appear
- **Newsfeed aggregators**: Added to code but Mac Mini server needs restart to pick up changes

## Decisions Made
- Tab structure: Dashboard/Activity/Orders — grouped by user intent (glance/review/build)
- Send to Chat: NotificationCenter pattern (`hestiaSendToChat` with context in userInfo)
- Canvas bridge: Bypass handler-chain, set `window.loadWorkflow` directly in useEffect
- Newsfeed: Pull-based 30s TTL aggregation into SQLite

## Test Status
- 42 newsfeed tests passing (verified)
- macOS build: PASS, iOS build: PASS
- Full suite running at handoff

## Uncommitted Changes
None — all committed and pushed to `main`

## Known Issues / Landmines
1. **Orders tab empty** — Mac Mini DB has zero workflows. "Evening Research" lost during migration. Recreate via + button
2. **Health cards stale cache** — clean build may be needed (Shift+Cmd+K)
3. **Research canvas decode error** — `keyNotFound "connectionCount"` in entity response. Unrelated to our work
4. **Concurrent ChatMode refactor** — session overlapped with `feat/notion-style-chat-hero-redesign`. MainSplitViewController fixed to use `chatMode` enum
5. **Trading lookback** — API param sent but backend ignores it. Needs backend update
6. **Per-bot P&L** — shows "—" placeholder. Backend `TradingBotResponse` needs `pnl` field
7. **Research canvas latent bug** — uses same `bridge.onLoadWorkflow` handler-chain we fixed in workflow canvas. May fail under same race condition

## Process Learnings
- **First-pass success**: 7/10 tasks (70%). Rework from canvas race condition (3 iterations), ChatMode conflict, stale build cache
- **Top blocker**: WKWebView sandbox noise masked real canvas bug. Debug overlay (nodes:0) was the diagnostic that cracked it
- **HOOK proposal**: Auto-run xcodegen when Swift files added/deleted
- **AGENT miss**: Should dispatch @hestia-build-validator after file creation, not just edits

## Next Steps

### Immediate
1. Clean build: Shift+Cmd+K → Cmd+B — verify all 3 Dashboard rows render
2. Deploy backend: `./scripts/deploy-to-mini.sh` — trading + sentinel aggregators need server restart
3. Recreate "Evening Research" workflow via + button in Orders sidebar
4. Verify Activity feed populates with trading fills after deploy

### Polish Sprint
5. Health trend deltas (wire `getHealthTrend()` API)
6. Per-bot P&L (add `pnl` to `TradingBotResponse`)
7. Backend lookback filtering on `/trading/summary`
8. Activity feed mark-read/dismiss API wiring
9. Order execution detail enrichment in newsfeed metadata
