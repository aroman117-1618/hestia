# Offline Resilience & Caching — Implementation Plan

**Created:** 2026-03-20
**Discovery basis:** `docs/discoveries/offline-resilience-caching-strategy-2026-03-20.md`
**Scope:** Make the macOS app show last-known data when the server is unreachable
**Estimated effort:** 8-12 hours across 3 phases

## Problem Statement

When the Hestia server is unreachable (crash, reboot, Tailscale disconnect, deploy restart), the macOS app shows empty panels with zero indication of previous state. 13 of 17 ViewModels have no caching. The user sees a dead dashboard instead of stale-but-useful data.

**Goal:** Every data-driven panel shows last-known data within 100ms of app launch, with a clear "cached / last updated X ago" indicator when the server is down.

---

## Current State

### What Already Works
- **3 ViewModels** use `CacheManager` (UserDefaults-backed, TTL): `MacAgentsViewModel`, `MacNeuralNetViewModel`, `MacSettingsProfileViewModel`
- **WikiViewModel** uses `WikiCacheService` (disk-backed JSON): loads cached articles instantly, fetches fresh in background
- **NetworkMonitor** exists in HestiaShared and is now wired to macOS (`OfflineBanner` from Sprint 31)
- **Backend ETag** support exists in `hestia/api/etag.py` but only covers 2 of 29 route modules

### What's Broken
- **CacheManager uses UserDefaults** — degrades above ~1MB total (entire plist loaded at launch)
- **13 ViewModels have zero caching**: CommandCenter, Trading, Inbox, Health, Explorer (files, resources), Memory Browser, Cloud Settings, Integrations, Device Management, Chat
- **WikiCacheService is siloed** — its disk-backed JSON pattern isn't reusable by other ViewModels
- **NetworkMonitor isn't used for data loading** — API calls fire regardless of connectivity
- **No "stale data" indicator** — user can't tell if displayed data is fresh or cached

---

## Phase 1: CacheManager Upgrade (2-3h)

**Goal:** Replace the UserDefaults backend with disk-backed JSON. Keep the same API surface so existing consumers (3 ViewModels) work without changes.

### WS1.1: Disk Storage Backend (1.5h)

Replace `CacheManager` internals:

```
Before: UserDefaults.set(data, forKey:)
After:  FileManager.write(data, to: ~/Library/Caches/Hestia/{key}.json)
```

**File:** `HestiaApp/macOS/Services/CacheManager.swift`

Changes:
- Storage: `~/Library/Caches/Hestia/` directory (same as WikiCacheService)
- One JSON file per cache key: `{cacheDir}/{key}.json`
- Each file contains `CacheEntry { data: Data, expiresAt: Date, cachedAt: Date }`
- Thread safety: `DispatchQueue(label: "com.hestia.cache", qos: .utility)` for all I/O
- Async read method: `func getAsync<T>(_ type: T.Type, forKey key: String) async -> T?`
- Keep synchronous `get()` for backward compatibility (existing 3 VMs use it)

New methods:
- `func getStale<T>(_ type: T.Type, forKey key: String) -> T?` — returns data even if expired (for offline fallback)
- `func cachedAt(forKey key: String) -> Date?` — when was this key last cached (for "updated X ago" display)
- `func totalCacheSize() -> Int` — sum of all cached files in bytes (debugging)

### WS1.2: TTL Matrix (0.5h)

Define per-data-type TTLs in `CacheKey`:

| Data Type | TTL | Rationale |
|-----------|-----|-----------|
| Trading summary/positions | 30s | Near-real-time, stale quickly |
| System health | 60s | Server status changes fast |
| Calendar events | 5 min | EventKit data, changes infrequently during a session |
| Newsfeed, investigations | 5 min | Content updates periodically |
| Orders | 2 min | User may create/modify orders |
| Memory chunks, learning metrics | 5 min | Background processes, not real-time |
| Wiki articles | 1 hour | Generated content, very stable |
| User profile, agents | 10 min | User-initiated changes only |
| Cloud providers, integrations | 10 min | Configuration, rarely changes |

Add TTL constants to `CacheKey`:

```swift
enum CacheKey {
    // ... existing keys ...

    // TTLs (seconds)
    static let ttlRealtime: TimeInterval = 30
    static let ttlFrequent: TimeInterval = 120
    static let ttlStandard: TimeInterval = 300
    static let ttlStable: TimeInterval = 600
    static let ttlLongLived: TimeInterval = 3600
}
```

### WS1.3: Consolidate WikiCacheService (0.5h)

Migrate `WikiCacheService` to use `CacheManager` internally:

- `saveArticles()` → `CacheManager.shared.cache(articles, forKey: .wikiArticles, ttl: CacheKey.ttlLongLived)`
- `loadCachedArticles()` → `CacheManager.shared.getStale([WikiArticle].self, forKey: .wikiArticles)`
- `saveRoadmap()` → `CacheManager.shared.cache(roadmap, forKey: .wikiRoadmap, ttl: CacheKey.ttlLongLived)`
- Keep `WikiCacheService` as a thin facade (preserves existing VM call sites) but delegate to `CacheManager`
- Delete the `ioQueue`, `encoder`, `decoder`, `ensureDirectory()` from WikiCacheService (CacheManager owns these)
- Add new CacheKeys: `wikiArticles`, `wikiRoadmap`

**Acceptance:** Existing 3 ViewModels still work. WikiViewModel still works. `~/Library/Caches/Hestia/` directory contains JSON files instead of UserDefaults plist bloat.

---

## Phase 2: ViewModel Cache Integration (4-5h)

**Goal:** Add stale-while-revalidate pattern to all 13 uncached ViewModels.

### Standard Pattern

Every ViewModel follows the same 10-line template:

```swift
func loadSomething() async {
    // 1. Show cached data immediately (skip spinner if cache hit)
    if let cached: MyType = CacheManager.shared.getStale(forKey: .myKey) {
        self.data = cached
    }
    let hadCache = self.data != nil
    if !hadCache { isLoading = true }

    // 2. Fetch fresh from server
    do {
        let fresh = try await APIClient.shared.getData()
        self.data = fresh
        CacheManager.shared.cache(fresh, forKey: .myKey, ttl: CacheKey.ttlStandard)
    } catch {
        if !hadCache {
            failedSections.insert("something")
        }
        // If cache exists, silently use stale data
    }
    if !hadCache { isLoading = false }
}
```

### WS2.1: MacCommandCenterViewModel (1.5h) — HIGHEST PRIORITY

This VM has 9 data loaders plus the new trading summary. Each gets the cache pattern.

New CacheKeys needed:
```swift
static let systemHealth = "system_health"
static let pendingMemories = "pending_memories"
static let orders = "orders"
static let newsfeed = "newsfeed"
static let metaMonitorReport = "meta_monitor_report"
static let memoryHealth = "memory_health"
static let triggerAlerts = "trigger_alerts"
static let investigations = "investigations"
static let healthSummary = "health_summary"
static let tradingSummary = "trading_summary"
```

Special considerations:
- `loadCalendarEvents()` uses EventKit (local), not API — no caching needed (already local)
- `loadHealth()` is the canary — if it fails AND no cache exists, show the error banner
- `loadLearningMetrics()` has 3 sequential calls — each gets its own cache key
- Loading spinner only shows on first ever load (no cache). Subsequent loads are silent refresh.

Also add `lastUpdated` per-section tracking so the UI can show "Health: 3 min ago, Orders: 1 min ago" granularity (optional, nice-to-have).

### WS2.2: MacTradingViewModel (1h)

6 API calls: portfolio, positions, bots, trades, risk status, watchlist.

New CacheKeys:
```swift
static let tradingPortfolio = "trading_portfolio"
static let tradingPositions = "trading_positions"
static let tradingBots = "trading_bots"
static let tradingTrades = "trading_trades"
static let tradingRiskStatus = "trading_risk_status"
static let tradingWatchlist = "trading_watchlist"
```

TTL: `ttlRealtime` (30s) for portfolio/positions, `ttlFrequent` (2 min) for trades/bots.

### WS2.3: Remaining ViewModels (1.5h)

Mechanical application of the pattern to:

| ViewModel | Cache Keys | TTL | Notes |
|-----------|-----------|-----|-------|
| `MacInboxViewModel` | inbox_items | standard | |
| `MacHealthViewModel` | health_metrics | standard | |
| `MacExplorerFilesViewModel` | (skip) | — | File browser is always live |
| `MacExplorerResourcesViewModel` | explorer_resources | standard | |
| `MacMemoryBrowserViewModel` | memory_chunks | standard | Already has pagination — cache first page only |
| `MacCloudSettingsViewModel` | cloud_providers | stable | |
| `MacIntegrationsViewModel` | integrations_status | stable | |
| `MacDeviceManagementViewModel` | registered_devices | stable | |
| `MacChatViewModel` | (skip) | — | Chat is real-time, caching makes no sense |
| `MacWikiViewModel` | (already done via WikiCacheService consolidation) | — | |

**Skipped:** `MacExplorerFilesViewModel` (file browser should always be live), `MacChatViewModel` (real-time streaming).

### WS2.4: Cache Invalidation After Mutations (0.5h)

Ensure every write/mutation operation invalidates the relevant cache:

| Mutation | Invalidate Key |
|----------|---------------|
| Create order (NewOrderSheet) | `orders` |
| Agent save (AgentDetailSheet) | `agentsList` (already done) |
| Profile save | `userProfile` (already done) |
| Cloud provider add/remove | `cloudProviders` |
| Memory delete/edit | `memoryChunks` |
| Newsfeed mark read/dismiss | `newsfeed` |

Most of these are already done in the 3 cached ViewModels. The new ones need explicit `CacheManager.shared.invalidate(forKey:)` calls after successful mutations.

**Acceptance:** App launches and immediately shows last-known data for all panels. Fresh data replaces cached data silently in the background. Server going down mid-session shows stale data instead of empty panels.

---

## Phase 3: NetworkMonitor Integration (1.5-2h)

**Goal:** Skip API calls when offline, show "cached data" indicator, auto-refresh on reconnect.

### WS3.1: Smart Data Loading (0.5h)

Add a helper to `CacheManager`:

```swift
/// Load data with network awareness. If offline, return cached only.
func loadWithFallback<T: Codable>(
    key: String,
    ttl: TimeInterval,
    isOnline: Bool,
    fetch: () async throws -> T
) async -> T? {
    // Always try cache first
    let cached: T? = getStale(forKey: key)

    // If offline, return cache (even if expired)
    guard isOnline else { return cached }

    // If online, try fresh fetch
    do {
        let fresh = try fetch()
        cache(fresh, forKey: key, ttl: ttl)
        return fresh
    } catch {
        return cached // Server error — fall back to cache
    }
}
```

ViewModels pass `isOnline: networkMonitor.isConnected` into this helper.

### WS3.2: "Showing Cached Data" Indicator (0.5h)

Update `OfflineBanner` (from Sprint 31) to show two states:

1. **No connection + no cache:** "Server unreachable — check your connection" (red, current behavior)
2. **No connection + has cache:** "Offline — showing cached data from [time]" (amber, less alarming)

Also add a subtle per-section "cached" badge: a small clock icon next to section headers when the displayed data is stale (came from `getStale()` rather than a fresh fetch). Use `CacheManager.cachedAt(forKey:)` to compute the timestamp.

### WS3.3: Auto-Refresh on Reconnect (0.5h)

When `NetworkMonitor.isConnected` transitions from `false` to `true`:

1. Post a notification: `.hestiaServerReconnected`
2. `CommandView` listens for this and calls `viewModel.loadAllData()` to refresh everything
3. Other visible ViewModels (Trading, Explorer) listen similarly
4. This avoids a full-app refresh — only the currently visible screen refreshes

### WS3.4: Loading State Refinement (0.5h)

Refine `isLoading` semantics:
- `isLoading = true` only on first-ever load (cold start, no cache)
- Background refreshes don't show spinners
- A subtle "refreshing..." indicator (e.g., small spinning arrow near "Last updated") shows during background fetches
- `failedSections` only populated when no cache fallback exists

**Acceptance:** Server goes down → app continues showing last-known data with amber "Offline" banner. Server comes back → data refreshes automatically. No spinners on cache-warm launches.

---

## Effort Summary

| Phase | Hours | Theme |
|-------|-------|-------|
| Phase 1: CacheManager Upgrade | 2-3h | Disk storage, TTL matrix, WikiCacheService consolidation |
| Phase 2: ViewModel Integration | 4-5h | 11 ViewModels + cache invalidation |
| Phase 3: NetworkMonitor Integration | 1.5-2h | Offline awareness, stale indicator, auto-reconnect |
| **Total** | **7.5-10h** | |

## Priority Order

**Phase 1 first** — the storage upgrade unblocks everything else. Without disk-backed storage, caching 13 ViewModels into UserDefaults would degrade the app.

**Phase 2 second, starting with CommandCenter** — this is the most visible panel and validates the pattern for all other VMs.

**Phase 3 third** — the polish layer that makes offline mode feel intentional rather than broken.

## Out of Scope

- Backend ETag expansion (separate backend sprint)
- Offline write queue (actions require the AI server)
- SwiftData/Core Data migration (over-engineered for single-user)
- Cross-device cache sync (not applicable)
- Cache encryption (data is user's own, sandboxed)

## Key Decisions Needed

1. **Stale data indicator style:** Subtle clock icon per section? Or just the global "Offline" banner? (Recommend: global banner only — per-section timestamps add clutter)
2. **Cache warm-up on app launch:** Should we proactively fetch all data on launch even for screens the user hasn't visited? (Recommend: No — lazy load on first visit, then cache)
3. **Cache purge policy:** Manual "Clear Cache" button in Settings, or automatic OS-managed? (Recommend: OS-managed — `~/Library/Caches/` is purgeable, plus a debug-only clear button)
