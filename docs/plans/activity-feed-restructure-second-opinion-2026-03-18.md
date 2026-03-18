# Second Opinion: Sprint 25.5 — Activity Feed Restructure
**Date:** 2026-03-18
**Models:** Claude Opus 4.6 (internal) — Gemini unavailable (CLI registry bug)
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary

The macOS Command Center's bottom section (currently: learning metrics, calendar, orders, activity feed) is restructured into a 3-tab segmented control (System / Internal / External). System shows workflows and alerts, Internal shows health/tasks/calendar, External has a nested sub-toggle for Trading/News/Investigations. Six new Swift files, two modified.

---

## Phase 2: Scale Assessment

| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|----------------|-------------------|
| Single user | Yes | None | N/A |
| Family (2-5) | Yes | ViewModels hardcode single-user API calls — no user_id param | Low — add user param |
| Community | Partially | ViewModel aggregator pattern doesn't scale to multi-tenant dashboards | Medium |

**No scale blockers.** This is purely a frontend view restructure — the backend endpoints already support user_id scoping via JWT.

## Phase 3: Front-Line Engineering Review

- **Feasibility:** Fully feasible. All data sources already exist. The tab pattern is proven (Research view).
- **Complexity:** Moderate (~6-8h implementation). The Trading placeholder is the most complex piece due to component count.
- **Hidden prerequisites:**
  1. **`APIClient+Investigate.swift` must be created** — no macOS API client for `/v1/investigate/history`
  2. **NewsfeedTimeline uses iOS tokens** (`Spacing.lg`, `CornerRadius.card`) — cannot embed directly in macOS
  3. **Health summary API method exists** (`getHealthSummary()` in `APIClient+Health.swift`) — no blocker
- **Testing strategy:** Visual testing only (no unit tests for SwiftUI views in this project). Build verification via xcodebuild.
- **Developer experience:** Good. Clear pattern to follow (Research view), existing ViewModel provides most data.

## Phase 4: Backend Engineering Lead Review

- **Architecture fit:** Good. No backend changes needed. All endpoints exist.
- **API design:** N/A — no new endpoints.
- **Data model:** N/A — frontend only.
- **Integration points:** `MacCommandCenterViewModel` grows from 6 to 8 parallel data loads. Acceptable but approaching the limit.
- **Dependency risk:** None. No new packages.

**Recommendation:** Consider splitting the ViewModel at 10+ data sources. For now, 8 is manageable.

## Phase 5: Product Management Review

- **User value:** HIGH. The current flat activity feed mixes system noise with user-relevant content. Categorization makes the dashboard genuinely useful.
- **Edge cases:**
  - Empty states for each tab (no orders, no health data, no investigations) — **must be designed**
  - First-time user sees mostly empty tabs — **not a great first impression**
  - Trading tab is 100% placeholder — **must have a clear "coming soon" treatment**
- **Multi-device:** macOS only. iOS unaffected. No platform divergence concern.
- **Opportunity cost:** Minimal. This is prerequisite for Sprint 26 (Trading Dashboard).
- **Scope:** Right-sized. The Trading placeholder adds ~30% effort for future-proofing.

## Phase 6: Design/UX Review

### CRITICAL FINDING: NewsfeedTimeline Cannot Be Directly Embedded

The existing `NewsfeedTimeline` (Shared/) uses iOS design tokens:
- `Spacing.lg`, `Spacing.md`, `Spacing.xs`, `Spacing.xl` (iOS `Spacing` enum, NOT `MacSpacing`)
- `CornerRadius.card`, `CornerRadius.small` (iOS `CornerRadius`, NOT `MacCornerRadius`)
- `.foregroundColor(.white.opacity(...))` (hardcoded, not `MacColors`)

**Resolution options:**
1. **Create a macOS NewsfeedTimeline wrapper** that reimplements the list using MacColors/MacSpacing — cleanest
2. **Create a macOS-specific NewsfeedListView** in `macOS/Views/Command/` that uses the same `NewsfeedViewModel` but macOS tokens — recommended
3. **Modify the Shared view to use conditional compilation** (`#if os(macOS)`) — messy, avoid

**Recommendation:** Option 2. Build a `NewsFeedListView.swift` in macOS/Views/Command/ that wraps `NewsfeedViewModel` with macOS tokens. The Shared version stays for iOS.

### 3-Level Navigation Depth Concern

The External tab creates: `Command Center > External tab > Trading|News|Investigations sub-toggle`

This is **borderline but acceptable** given:
- The Research view already has 2 levels (Research > Graph|Principles|Memory) and works fine
- The sub-toggle is visually distinct (nested within the External tab's content area, not another toolbar)
- There are only 3 sub-options, all semantically related (external data sources)

**However:** Consider whether the sub-toggle should be a **segmented control** (like the top-level tabs) or a **filter bar** (like Research view's data source pills). A filter bar is visually lighter and reads as "filtering within this view" rather than "navigating to a sub-page."

### Design System Compliance Checklist

| Token | Available? | Notes |
|-------|-----------|-------|
| `MacColors.activeTabBackground` | Yes | Used in existing ActivityFeed filter tabs |
| `MacColors.searchInputBackground` | Yes | Used in OrdersPanel, StatCard |
| `MacColors.cardGradient` | Yes | Standard card background |
| `MacColors.cardBorder` | Yes | Standard card stroke |
| `MacColors.panelBackground` | Yes | Panel container bg |
| `MacColors.amberAccent` | Yes | Selected tab indicator |
| `MacCornerRadius.panel` | Yes | 16pt card radius |
| `MacCornerRadius.tab` | Yes | 10pt tab button radius |
| `MacTypography.sectionTitle` | Yes | Section headers |
| `.buttonStyle(.hestia)` | Yes | Standard button style |
| `.hoverCursor(.pointingHand)` | Yes | Custom modifier, exists in codebase |

All required tokens exist. No new tokens needed.

### Empty States Required

Each section needs an empty state treatment:
- System > Orders: "No active orders" (already exists in `OrdersPanel`)
- System > Memory Activity: "No memory health data"
- System > Alerts: "No active alerts" (positive state — green checkmark)
- Internal > Health: "Health data unavailable" (HealthKit not connected)
- Internal > Tasks: "No tasks due today"
- Internal > Events: "No upcoming events"
- External > Trading: "Trading module loading..." with Sprint 26 ETA
- External > News: "No news items" (existing `NewsfeedTimeline` empty state)
- External > Investigations: "No investigations yet — use /investigate in chat"

### Accessibility

Must include:
- `accessibilityLabel` on all tab buttons
- `.accessibilityAddTraits(.isSelected)` on active tab
- Keyboard shortcut hints in labels (following Research view pattern)

## Phase 7: Infrastructure/SRE Review

- **Deployment impact:** None. macOS-only frontend change. No server restart needed.
- **New dependencies:** None.
- **Monitoring:** N/A — client-side only.
- **Rollback strategy:** Git revert. Clean.
- **Resource implications:** None. No new API calls beyond the 2 added to the ViewModel (investigations + health summary).

## Phase 8: Executive Verdicts

### CISO: ACCEPTABLE
No new data exposure, no new communication paths, no credential handling. The Trading kill switch button is disabled/placeholder — no risk of accidental activation.

### CTO: ACCEPTABLE WITH NOTE
The ViewModel aggregator pattern (8 parallel loads) is approaching complexity limits. After Sprint 26 adds more Trading data, consider splitting into `SystemActivityViewModel`, `InternalActivityViewModel`, `ExternalActivityViewModel`. Not a blocker for S25.5.

### CPO: ACCEPTABLE
This is the right structural change to support the Trading Dashboard (S26). Categorization improves dashboard usability. The News Feed moving from always-visible to External > News is a minor discoverability regression — mitigate with an "unread count" badge on the External tab.

## Phase 9: Sustained Devil's Advocate

### 9.1 The Counter-Plan

**Alternative: Keep flat layout, add filter tabs on top**

Instead of restructuring into 3 views, keep the current scrollable layout but add a filter bar at the top (like the existing ActivityFeed's "All Updates / Orders / Memory / Tasks / Health / System" pills). Add "Trading", "News", "Investigations" pills. The dashboard stays one scrollable page — sections show/hide based on selected filter.

**Why it's better:**
- Zero navigation depth — everything is one scroll away
- No "buried" content — users can filter to what they want
- Simpler implementation — enhance existing `ActivityFeed`, don't replace it
- Better for sparse data — when tabs are mostly empty, a filtered flat list feels less hollow

**Why it's worse:**
- The Trading Monitor needs significant screen real estate (~600-800px) — it can't be a card in a feed
- Mixing "system alerts" with "trade feed" in the same scrollable list creates cognitive overload
- The filter approach doesn't scale well to 9+ categories

**Verdict:** The counter-plan works for everything EXCEPT the Trading Monitor, which genuinely needs its own dedicated space. **The tabbed approach is correct** given the Trading module's incoming scope.

### 9.2 Future Regret Analysis

- **3 months:** The Trading placeholder will look embarrassingly empty until S26 ships. Consider hiding the Trading sub-tab entirely until S26 is ready (feature flag).
- **6 months:** The ViewModel aggregator will be unwieldy if each tab keeps adding data sources. Plan the ViewModel split now, execute when it hits 10+ sources.
- **12 months:** The 3-tab structure should survive through Sprint 30 (Go-Live). System/Internal/External is a durable categorization.

### 9.3 The Uncomfortable Questions

- **"Do we actually need this?"** — Yes. The flat activity feed doesn't work for a dashboard that now has 8+ data source types. This is needed.
- **"Are we building this because it's valuable, or because it's interesting?"** — Valuable. This is a prerequisite for S26.
- **"What's the cost of doing nothing?"** — The Trading Monitor would have to be bolted onto the flat feed, creating a worse UX.

### 9.4 Final Stress Tests

1. **Most likely failure:** The NewsfeedTimeline embedding breaks because of iOS token mismatch. **Mitigation:** Build a macOS-specific news list view (already flagged above).

2. **Critical assumption:** That the Trading view's component structure (satisfaction scores, decision trails, expandable rows) will match what S26 actually needs. **Validation:** Review the Figma mockup before building — if the Trading view design isn't finalized, build only the section headers + empty states, not the detailed component slots.

3. **Half-time cut list:** Cut the full Trading component structure → replace with a simple "Coming in Sprint 26" placeholder card. Cut InvestigationsListView → replace with a "View investigations in chat" link. This halves the new file count from 6 to 4.

---

## Cross-Model Validation (Gemini 2.5 Pro)

**Status:** Unavailable — Gemini CLI has a ProjectRegistry crash (`TypeError: Cannot read properties of undefined`). Internal audit (Phases 1-9) stands alone.

---

## Conditions for Approval

1. **MUST: Create macOS-specific NewsFeedListView** — Do NOT embed the Shared `NewsfeedTimeline` directly. Build a macOS version using `MacColors`/`MacSpacing` that wraps the existing `NewsfeedViewModel`.

2. **MUST: Create `APIClient+Investigate.swift`** for macOS with `getInvestigationHistory()` method before building `InvestigationsListView`.

3. **MUST: Add unread count badge on External tab** to mitigate news discoverability regression.

4. **MUST: Design empty states for all 9 sections** before implementing. Empty dashboards destroy first impressions.

5. **SHOULD: Use filter-pill style for External sub-toggle** (not a second segmented control) to visually differentiate the nesting level from the top-level tabs.

6. **SHOULD: Consider hiding Trading sub-tab** behind a feature flag until S26 ships real data. An empty placeholder for months is worse than no tab.

7. **SHOULD: Keep full Trading component structure in plan** (satisfaction scores, decision trails, expandable rows) — this is the right call for S26 velocity. But build them with mock data that exercises the layout, not just empty states.

8. **NICE-TO-HAVE: Plan the ViewModel split** (into per-tab VMs) as a follow-up task. Not needed for S25.5, but should be on the roadmap before S26 adds more data sources.
