# Session Handoff — 2026-03-28 (macOS App Refresh)

## Mission
Redesign the macOS app to match the refreshed iOS app — streamline navigation from 5 tabs to 3, redesign the Command tab with hero + sub-tabs, add chat panel detach-to-window, port the iOS wavelength particle animation to macOS.

## Completed
- **Brainstormed and designed** macOS refresh with Andrew via visual companion (10 mockup iterations)
  - Spec: `docs/superpowers/specs/2026-03-27-macos-refresh-design.md`
- **Second opinion audit** — 10-phase internal + Gemini cross-validation, APPROVE WITH CONDITIONS
  - Report: `docs/plans/macos-refresh-second-opinion-2026-03-27.md`
- **Implementation plan** — 7 tasks, subagent-driven development
  - Plan: `docs/superpowers/plans/2026-03-28-macos-refresh.md`
- **Task 1: Strip WorkspaceView enum** — removed .explorer/.orders, deleted 16 Explorer files, updated 6 files (`d9060ed`)
- **Task 2: Redesign Hero Section** — avatar + wavelength left, stats right (`f1ce740`)
- **Task 3: Sub-tab ViewModels** — InternalTab (EventKit), NewsfeedTab (trading), SystemAlertsTab (`4575145`)
- **Task 4: Sub-tab Views** — InternalTabView, NewsfeedTabView, SystemAlertsTabView, TradingStatusView, PLLookbackToggle (`c3f2437`)
- **Task 5: Rewire CommandView** — sub-tab architecture with lazy rendering (`97ade0c`)
- **Task 6: Chat panel detach** — double-click sidebar toggle, NSWindow, re-dock on close (`eb1b749`)
- **Task 7: Cleanup** — removed 12 dead Command view files (`2656d6b`)
- **QA fixes** — removed old chat toggle overlay, Memory icon, wavelength animation (`33edad0`)
- **Ported iOS wavelength** — CGContext renderer to macOS at 30fps, transparent bg (`e3eb7f3`, `1406d0f`)
- **Hero polish** — removed card styling, wavelength scaling, layout rearrange (`f6fe84e` → `a75b884`)
- **Shipped mac-v1.12.0** (build 61) — pushed + tagged (`563c4b8`)

## In Progress
- None — all code merged, tagged, and pushed

## Decisions Made
- Sidebar: 3 tabs (Command, Memory, Settings) + chat toggle. Avatar replaces logo at top.
- Explorer removed entirely (git history preserves). Orders absorbed into Command/Newsfeed.
- Chat detach uses fresh ViewModel per window (pragmatic — messages come from API)
- Wavelength on macOS uses CGContext renderer at 30fps (ported from iOS simulator fallback)
- Hero has no card background — contents sit on pure black, matching iOS pattern
- Memory tab untouched. Settings/Onboarding deferred.

## Test Status
- 2976 backend passing, 0 failing
- macOS build: clean. iOS build: clean.

## Uncommitted Changes
- `hestia/data/` — runtime data directory (gitignored), no action needed

## Known Issues / Landmines
- **Sentinel API**: SystemAlertsTabViewModel calls `/sentinel/status` — Layer 0 not deployed on Mac Mini yet. Wrapped in try/catch.
- **P&L lookback toggle**: Client-side only — backend doesn't support period filtering yet.
- **Chat detach double-click**: `onTapGesture(count: 2)` must come before `onTapGesture(count: 1)` in modifier chain.
- **iOS wavelength background**: macOS renderer uses transparent bg, iOS uses opaque near-black. Don't unify without checking iOS chat view.
- **Wavelength waveScale**: Currently 0.25 — may need tuning if window size changes significantly.

## Process Learnings
- **First-pass success**: 7/7 tasks completed by subagents. QA added ~8 polish fixes.
- **Top time sink**: Wavelength rendering (6 commits) — iOS particle system designed for full-screen, not 80pt hero.
- **Subagent-driven dev worked well**: Fresh context per task, build validation as quality gate.
- **Visual companion high-value**: 10 mockup iterations saved rework. Standard for all UI work.

## Next Steps
1. **Monitor GitHub Actions** — verify mac-v1.12.0 builds, signs, notarizes via Sparkle
2. **Deploy Sentinel Layer 0 on Mac Mini** (~30 min manual) — still pending from previous session
3. **iOS refresh remaining** — WS0 (TestFlight) and WS1 (voice modes) per `docs/superpowers/plans/2026-03-24-ios-refresh.md`
4. **Settings/Onboarding redesign** — deferred, on the Notion whiteboard
