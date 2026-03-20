# Session Handoff — 2026-03-20

## Mission
Massive UI wiring + infrastructure session: make the macOS dashboard truthful (Sprint 31), add offline caching, fix settings bugs, and decouple trading bots for enterprise-grade server reliability.

## Completed (5 major features, 4 releases)

### Sprint 31: Dashboard Truthfulness (v1.1.0) — `ceb27b7`
- Progress rings: real data (calendar / unread / server health) replacing 99.2%/87%/18%
- Status badge: 3-state (green/amber/red) based on actual server state
- Error handling: `failedSections` tracking + `ErrorState` banner integration
- Hero buttons: "New Order" → sheet, "View Reports" → External tab
- OrdersPanel: real timestamps, time-based progress bar
- NetworkMonitor: OfflineBanner wired to WorkspaceRootView
- Color tokens: 7 new MacColors, all Color(hex:) in Views replaced
- New endpoint: `GET /v1/trading/summary`
- New files: `NewOrderSheet.swift`, `LoadableState.swift`, `OfflineBanner.swift`

### Settings Fixes (included in v1.1.0)
- Agent Personality tab: wired `loadPersonality()` (was never called)
- Apple sync: `AppleIdentityProvider.swift` (Contacts "Me" card + NSFullUserName fallback)
- Feedback button: opens GitHub Issues with pre-filled data
- Roadmap removed from Field Guide sidebar

### Offline Resilience / Caching (v1.1.1) — `d6edd51`
- CacheManager: `getStale()`, `CacheTTL` constants, backward-compatible decoding
- CacheFetcher: shared SWR helper with `@Sendable` closures
- 10 ViewModels cached (was 3): CommandCenter, Trading, Cloud, Devices, Inbox, Health, Integrations
- OfflineBanner: 2-state (amber cached / red unreachable), auto-refresh on reconnect

### Server HA (pushed for CI/CD) — `1ea4e93`
- Bot decoupling: `bot_service.py` standalone process, `bot_commands` table IPC
- Watchdog: 60s interval, 2 strikes (was 5 min / 3 strikes)
- Monitoring: Healthchecks.io + ntfy.sh wired into watchdog
- macOS hardening script: `scripts/harden-macos.sh`

### Sparkle Hotfix (v1.1.2) — sandbox removed — `67c5b87`
- App sandbox broke Sparkle auto-update installer
- Removed sandbox entitlement; Contacts/Calendar entitlements kept
- Calendar permission may re-prompt (known tradeoff until proper Sparkle XPC sandbox support added)

## In Progress
- **Mac Mini setup**: Andrew is SSH'd in. Needs: `cd ~/hestia && git pull && sudo bash scripts/harden-macos.sh`, then load the 2 new launchd plists
- **Healthchecks.io**: Account not yet created. Set `HESTIA_HC_PING_URL` env var after signup
- **ntfy.sh topic**: Set `HESTIA_NTFY_TOPIC` env var (e.g., `hestia-alerts`)

## Decisions Made
- Progress rings: simple (1 source/ring), not 9-source composite — defer complexity
- CacheManager stays UserDefaults — ~850KB fits, disk migration deferred
- WikiCacheService NOT consolidated — working code, don't touch
- Gunicorn REJECTED — fork safety + bot duplication risk. Single Uvicorn + bot decoupling instead
- App sandbox REVERTED — breaks Sparkle. Needs XPC installer service for proper sandbox (future task)
- Voice (Sprint 34) DEFERRED — SpeechAnalyzer iOS 26+ only, macOS 15 can't use it

## Test Status
- 346 trading tests passing (post-decoupling)
- macOS + iOS builds: passing
- Full suite not re-run — trading subset validated

## Known Issues / Landmines
- **Calendar permission**: Will re-prompt on launch (sandbox removed). Persists after first grant on non-sandboxed.
- **Trading bots on Mac Mini**: NOT running until `com.hestia.trading-bots.plist` loaded. Paper soak interrupted.
- **Sandbox + Sparkle**: Future task — add XPC installer service for proper sandboxed auto-update
- **3 untracked files**: `.superpowers/`, `MACOS_APP_AUDIT.md`, `MACOS_AUDIT_REPORT.md` — pre-existing artifacts, not from this session

## Discovery Reports (saved)
- `docs/discoveries/server-high-availability-2026-03-20.md`
- `docs/discoveries/offline-resilience-caching-strategy-2026-03-20.md`

## Second Opinions (saved)
- `docs/plans/macos-wiring-sprints-second-opinion-2026-03-19.md`
- `docs/plans/offline-resilience-caching-second-opinion-2026-03-20.md`
- `docs/plans/server-ha-second-opinion-2026-03-20.md`

## Next Steps
1. Finish Mac Mini setup (hardening + launchd plists)
2. Verify paper soak bots resume via bot service
3. Create Healthchecks.io account + configure env vars
4. Continue macOS wiring: Sprint 32 items (newsfeed interactivity, investigation detail sheets, stat card navigation)
5. Future: Sparkle XPC sandbox support, blue/green deploys, PostgreSQL evaluation
