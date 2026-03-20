# Session Handoff — 2026-03-20 (Extended)

## Mission
Massive session: Sprint 31 dashboard truthfulness, offline caching, server HA (bot decoupling + watchdog + monitoring), settings fixes, and Command Center wiring audit. Culminated in a critical debugging session fixing SystemHealth JSON decode failures that caused "Can't reach server" despite 200 OK responses.

## Completed

### Sprint 31: Dashboard Truthfulness (v1.1.0) — `ceb27b7`
- Real progress rings (calendar/unread/health), 3-state status badge, error handling, hero buttons wired, OrdersPanel real timestamps, NetworkMonitor + OfflineBanner, 7 color tokens, `GET /v1/trading/summary` endpoint

### Settings Fixes (in v1.1.0)
- Agent Personality tab wired, Apple "Me" card sync, Feedback → GitHub Issues, Roadmap removed from Field Guide

### Offline Caching (v1.1.1) — `d6edd51`
- CacheManager enhanced (getStale, TTL constants), CacheFetcher SWR helper, 10 ViewModels cached, OfflineBanner 2-state + auto-reconnect

### Server HA — `1ea4e93`
- Bot decoupled to standalone `bot_service.py` + `bot_commands` table IPC
- Watchdog: 60s/2-strikes (was 5min/3), Healthchecks.io + ntfy.sh monitoring
- macOS hardening script, 3 launchd plists (server, watchdog, trading-bots)
- **Deployed to Mac Mini** — all services running and verified

### Sparkle Hotfix (v1.1.2) — `67c5b87`
- Removed app-sandbox (broke Sparkle installer)

### SystemHealth Decode Bugfixes — `992a596`, `4ee385a`
- InferenceHealth null booleans → custom init(from:) with fallback
- **ROOT CAUSE: `convertFromSnakeCase` + explicit CodingKeys with snake_case raw values = double-conversion failure.** Removed all redundant CodingKeys from SystemHealth models.

### Command Center Wiring Audit Fixes — `ae2d48f`
- Health Summary: AnyCodableValue handles nested dicts, fixed key names (stepCount, restingHeartRate, total_hours)
- Calendar: broadened to "next 7 days from today", removed all-day filter, added diagnostic logging
- Newsfeed: filtered health insights out of External News tab
- New Order button in System tab: wired to open NewOrderSheet

## Uncommitted Changes
- `.github/workflows/*.yml` + `requirements.txt` — pre-existing from parallel session, NOT from this session
- Untracked: `.superpowers/`, audit artifacts, mockups — pre-existing

## Decisions Made
- **convertFromSnakeCase is global**: NEVER use explicit CodingKeys with snake_case raw values when decoder uses convertFromSnakeCase. Document in CLAUDE.md.
- **Bot decoupling via command table**: SQLite-based IPC, bot service polls every 1s
- **Gunicorn rejected**: Fork safety + bot duplication risk. Single Uvicorn + bot service instead.
- **App sandbox reverted**: Breaks Sparkle. Needs XPC installer service (future task).
- **Caching stays on UserDefaults**: ~850KB total fits. Disk migration deferred.

## Known Issues / Landmines
- **Calendar may still show empty** if EventKit permission wasn't properly re-granted after sandbox removal. Check Xcode console for `[Calendar] Auth status:` line.
- **Health Summary shows dashes** if no HealthKit data exists on Mac Mini (no iOS sync). The decode fix is correct, but there may simply be no data.
- **Workflow files modified** (`.github/workflows/`) — from parallel session, don't commit without checking.
- **Sparkle auto-update**: v1.1.2 fixes the sandbox issue but user must manually update past v1.1.0/v1.1.1 (those versions can't auto-update due to sandbox).
- **Trading bots on Mac Mini**: Now running via `com.hestia.trading-bots` launchd service. Paper soak should be resumed.
- **Orphaned files**: `StatCardsRow.swift` and `LearningMetricsPanel.swift` exist but aren't rendered. Could be deleted or re-integrated.

## Process Learnings

### Critical Bug Pattern: Silent Decode Failures
The CacheFetcher pattern catches ALL errors and returns `.empty` — making it impossible to distinguish "server unreachable" from "server returned data but decode failed." The `[DEBUG]` temporary logging was the only way to see the actual error. **Proposal**: Add a `.decodeFailed` case to `CacheFetcher.Source` that preserves the error, or log decode errors even in release builds.

### convertFromSnakeCase Gotcha
This wasted ~30 min across 2 fix attempts. The APIClient decoder uses `convertFromSnakeCase` globally, which means explicit CodingKeys with snake_case raw values double-convert and fail silently. **Must document in CLAUDE.md.**

### First-Pass Success
- Session total: ~12/16 tasks first-pass (75%)
- Rework causes: CodingKeys double-conversion (2x), Swift 6 Sendable (2x), `body` variable collision (1x), Sparkle sandbox (1x)
- Top blocker: Silent error swallowing in CacheFetcher

## Next Steps
1. **Push latest commits** (`ae2d48f` — Command Center fixes not yet pushed)
2. **Verify on device**: Clean build in Xcode, check calendar shows events, health summary shows data if available
3. **Ship v1.1.3** if everything looks good
4. **Continue Sprint 32**: Newsfeed interactivity (tap → detail sheet), investigation detail sheets, stat card navigation
5. **Future**: Sparkle XPC sandbox support, blue/green deploys, PostgreSQL evaluation
