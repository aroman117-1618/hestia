# Discovery Report: Command Center Deep Wiring Audit
**Date:** 2026-03-20
**Confidence:** High
**Decision:** Three categories of bugs — data contract mismatches (health), data source contamination (newsfeed), and calendar permission gating — each with clear, isolated fixes.

## Hypothesis
The macOS Command Center dashboard connects to the server and decodes SystemHealth, but multiple panels show incorrect, empty, or misrouted data across all three tabs.

---

## Panel-by-Panel Audit

### Tab: Internal

#### 1. Health Summary — BROKEN (Shows dashes for Steps/HR/Sleep)

**Root Cause: Data contract mismatch (two layers deep)**

The backend `GET /v1/health_data/summary` returns nested dicts per category:
```json
{
  "activity": {
    "stepCount": {"value": 1234, "samples": 5}
  },
  "heart": {
    "restingHeartRate": {"avg": 65.0, "min": 58.0, "max": 72.0, "samples": 24}
  },
  "sleep": {
    "total_minutes": 420.0,
    "total_hours": 7.0,
    "stages": {"deep": 90.0}
  }
}
```

The Swift model `MacHealthSummaryResponse` declares categories as `[String: AnyCodableValue]`, but `AnyCodableValue` only handles scalar types (String, Int, Double, Bool, null). It **cannot decode nested objects** like `{"value": 1234, "samples": 5}`. This causes the entire `MacHealthSummaryResponse` decode to throw, so `healthSummary` is `nil`.

Even if the decode somehow succeeded (e.g., if the backend returned flat values), the Swift code uses **wrong key names**:
- `formattedSteps()` looks up `"steps"` — backend key is `"stepCount"`
- `formattedHeartRate()` looks up `"resting_heart_rate"` — backend key is `"restingHeartRate"`
- `formattedSleep()` looks up `"sleep_hours"` — backend key is `"total_hours"`

**Fix required (two parts):**
1. Either flatten the backend response so category values are scalar (e.g., `"stepCount": 1234`) OR extend `AnyCodableValue` to handle nested dicts (add a `.dict([String: AnyCodableValue])` case). Flattening the backend is simpler and more correct.
2. Fix the key names in the Swift helper functions to match the backend's actual keys.

**Files:**
- Backend: `/hestia/health/database.py` lines 224-330 (response structure)
- Backend schema: `/hestia/api/schemas/health_data.py` (HealthSummaryResponse)
- Swift model: `/HestiaApp/macOS/Models/HealthDataModels.swift` (AnyCodableValue, MacHealthSummaryResponse)
- Swift view: `/HestiaApp/macOS/Views/Command/InternalActivityView.swift` lines 159-179 (key lookups)

#### 2. Calendar — BROKEN (Shows "No upcoming events")

**Root Cause: EventKit permission gating + possible all-day filter**

The code (`loadCalendarEvents()` in `MacCommandCenterViewModel.swift` line 117-133) does:
1. Checks `EKEventStore.authorizationStatus(for: .event)` — requires `.fullAccess` or `.authorized`
2. If not authorized, calls `requestCalendarAccess()` which prompts — but if the app was previously denied, macOS won't re-prompt
3. Filters out `isAllDay` events (`filter { !$0.isAllDay }`)
4. Queries from start of current week to end of current week

**Possible failure modes:**
- Permission was granted via System Settings but the app was not restarted — EventKit may cache the old auth status
- If all events are all-day events, the filter removes everything
- The week range calculation starts from the beginning of the current ISO week — if today is at the end of the week, "upcoming" events may already be past

**Diagnosis needed:** Check `EKEventStore.authorizationStatus(for: .event)` at runtime. If it returns `.denied` or `.notDetermined`, that's the issue. If `.fullAccess`, then the all-day filter or date range is excluding real events.

**Files:**
- `/HestiaApp/macOS/ViewModels/MacCommandCenterViewModel.swift` lines 117-133

### Tab: External

#### 3. Newsfeed / News — BROKEN (Only shows "Daily health summary" entries)

**Root Cause: Newsfeed aggregation sources + no filtering by type**

The newsfeed aggregator (`/hestia/newsfeed/manager.py` `_aggregate_all()`) runs four aggregators:
1. `_aggregate_order_executions()` — requires recent order executions (last 48h)
2. `_aggregate_memory_reviews()` — requires pending memory reviews
3. `_aggregate_task_updates()` — requires non-terminal tasks
4. `_aggregate_health_insights()` — always creates a "Daily health summary" entry if any health data exists

**Why only health shows:** If there are no recent order executions, no pending memory reviews, and no active tasks, only the health insight gets created. The health aggregator always generates at least one item because `get_daily_summary()` returns a dict even with empty categories (it returns `{"date": "...", "activity": {}, "heart": {}, ...}` which is truthy).

**This is NOT a data leak** — health insights are a legitimate newsfeed source. The issue is that the newsfeed is correctly aggregating from all sources, but the other sources have no data to contribute.

However, there IS a UX problem: health data appearing in External > News gives the impression of a data leak because health logically belongs in Internal. The newsfeed is a cross-cutting timeline by design, but the user expects the News sub-tab to show "external" news, not internal health summaries.

**Fix options:**
1. Filter out `health_insight` items from the News sub-tab (add `?source=orders,tasks,system` or exclude health)
2. Move health insights to the Internal tab's own activity list
3. Add source filtering to the newsfeed API call

**Files:**
- `/hestia/newsfeed/manager.py` lines 279-307 (`_aggregate_health_insights`)
- `/HestiaApp/macOS/Views/Command/NewsFeedListView.swift` (shows all items unfiltered)
- `/HestiaApp/macOS/Services/APIClient+Newsfeed.swift` (calls `/newsfeed/timeline` with no type/source filter)

#### 4. Trading — WIRED CORRECTLY (Shows live data or empty states)

The `TradingMonitorView` has its own `MacTradingViewModel` that loads portfolio, positions, trades, bots, watchlist, and risk status independently. Each section shows appropriate empty states when no data exists ("No active positions", "No trades yet", etc.).

**Status:** Working as designed. Empty states are correct if trading hasn't been activated yet.

**Files:**
- `/HestiaApp/macOS/Views/Command/TradingMonitorView.swift`
- `/HestiaApp/macOS/ViewModels/MacTradingViewModel.swift`

#### 5. Investigations — WIRED CORRECTLY (Shows history or empty state)

The `InvestigationsListView` receives `viewModel.investigations` from the main ViewModel, which calls `/investigate/history`. Shows "No investigations yet" if empty.

**Status:** Working as designed. Empty state is correct if no `/investigate` commands have been run.

**Data contract match confirmed:** Swift `Investigation` struct fields match backend response (using `.convertFromSnakeCase` decoder).

**Files:**
- `/HestiaApp/macOS/Views/Command/InvestigationsListView.swift`
- `/HestiaApp/Shared/Models/InvestigationModels.swift`

### Tab: System

#### 6. Active Workflows (Orders) — WIRED CORRECTLY

Calls `APIClient.shared.listOrders(limit: 20)`. Shows order cards with status badges, recurrence info, next execution time. "New Order" button has `// TODO: Open order creation form` — empty closure.

**Status:** Working if orders exist. The "New Order" button in the orders section (line 88-89 of SystemActivityView) has an empty TODO closure, but the HeroSection's "New Order" button DOES work (opens `NewOrderSheet`).

**Bug:** The "New Order" button inside the Active Workflows section does nothing.

**Files:**
- `/HestiaApp/macOS/Views/Command/SystemActivityView.swift` lines 88-89

#### 7. Memory Activity — WIRED CORRECTLY

Displays `memoryChunkCount`, `redundancyEstimatePct`, and `positiveRatioPercent` from learning metrics endpoints. Shows "No memory health data" if both `memoryHealth` and `metaMonitorReport` are nil.

**Status:** Working if learning data exists. Will show zeros/empty state for fresh installs.

**Data contract match confirmed:** `LearningModels.swift` has explicit `CodingKeys` mapping snake_case to camelCase. Backend returns `{"data": {...}}` wrapper, Swift models use `MetaMonitorReportResponse.data`, `MemoryHealthResponse.data`, `TriggerAlertsResponse.data`.

#### 8. System Alerts — WIRED CORRECTLY

Displays unacknowledged trigger alerts from `/learning/alerts`. Shows "No active alerts — all systems nominal" when empty.

**Status:** Working as designed.

### Hero Section (Top)

#### 9. Progress Rings — PARTIALLY BROKEN

- **Internal ring:** Shows `todayEventCount` — will show 0 if calendar is broken (see issue #2)
- **External ring:** Shows `unreadCount` — will show 0 if newsfeed has no unread items
- **System ring:** Shows server reachability — WORKING (shows "OK" green)

#### 10. Status Badge — WORKING
Shows "All systems operational" / "N services degraded" / "Server unreachable" based on `failedSections`.

#### 11. StatCardsRow — NOT RENDERED
`StatCardsRow` exists but is NOT used in `CommandView.swift`. The layout only includes `HeroSection` + `ActivityFeedView`. The stat cards (Unread, Memory, Orders, Events, Health, Feed) are defined but never displayed.

**Files:**
- `/HestiaApp/macOS/Views/Command/StatCardsRow.swift` (orphaned)

#### 12. LearningMetricsPanel — NOT RENDERED
`LearningMetricsPanel` exists but is NOT used in any view. The learning metrics are already shown in SystemActivityView's Memory Activity section.

**Files:**
- `/HestiaApp/macOS/Views/Command/LearningMetricsPanel.swift` (orphaned — functionality duplicated in SystemActivityView)

---

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | Health Summary decode failure (shows dashes/unavailable), Calendar "No events" despite data existing | "New Order" button in orders section has empty closure |
| **Low Priority** | Newsfeed shows health data in External tab (UX confusion) | StatCardsRow/LearningMetricsPanel orphaned files |

---

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Architecture is clean (ViewModel -> APIClient -> Backend). Graceful degradation with `failedSections` tracking. Cache layer (`CacheFetcher`) prevents hard failures. Trading, Orders, Memory, Alerts all correctly wired. | **Weaknesses:** Health data contract is fundamentally broken (nested dict vs scalar). Calendar permission flow has no retry/diagnostic. Two orphaned view files (StatCardsRow, LearningMetricsPanel). |
| **External** | **Opportunities:** Newsfeed could become very powerful with source filtering. Health panel could show rich data (avg/min/max HR, sleep stages). | **Threats:** Users see empty/dashes and assume the whole system is broken. Health data in newsfeed creates "data leak" perception. |

---

## Fix Plan (Ordered by Priority)

### Fix 1: Health Summary (Critical)

**Option A — Flatten backend response (Recommended):**
Modify `health/database.py` `get_daily_summary()` to return flat values:
```python
# Instead of: "stepCount": {"value": 1234, "samples": 5}
# Return:     "steps": 1234
```
This is cleaner because the dashboard doesn't need samples/min/max — just the headline number.

**Option B — Extend AnyCodableValue:**
Add a `.dictionary([String: AnyCodableValue])` case. More complex, keeps backend unchanged.

Either way, fix the Swift key names (`steps`, `resting_heart_rate`, `sleep_hours`) to match whatever the backend sends.

### Fix 2: Calendar

Add diagnostic logging to `loadCalendarEvents()`:
```swift
let status = EKEventStore.authorizationStatus(for: .event)
print("[Calendar] Auth status: \(status.rawValue)")
```
If permission is granted, check whether removing the `!$0.isAllDay` filter shows events. Consider broadening the date range from "this week" to "next 7 days from now".

### Fix 3: Newsfeed Source Filtering

Change the `getNewsfeedTimeline` call to exclude health insights:
```swift
func getNewsfeedTimeline(limit: Int = 50, excludeSource: String? = nil) async throws -> NewsfeedTimelineResponse {
    var path = "/newsfeed/timeline?limit=\(limit)"
    // The backend already supports ?source= filtering
    return try await get(path)
}
```
Or filter client-side in `NewsFeedListView` to hide `health_insight` items.

### Fix 4: Empty Closure

Wire the "New Order" button in SystemActivityView to `showNewOrderSheet` (same as the HeroSection button).

---

## Open Questions

1. **Calendar:** What is the actual `EKEventStore.authorizationStatus` at runtime? Need to add a debug log or test on device.
2. **Health data on dev Mac:** Is there any HealthKit data in `data/health.db`? If the DB is empty (no iOS sync has happened from this Mac), the summary will return empty categories regardless of the key fix.
3. **Newsfeed refresh:** Has `/newsfeed/refresh` ever been called? The cache may not have been populated yet. The aggregation only runs on explicit refresh or on first timeline fetch.
4. **StatCardsRow/LearningMetricsPanel:** Were these intentionally removed from the layout, or were they lost in a refactor? They contain useful data that could be shown.
