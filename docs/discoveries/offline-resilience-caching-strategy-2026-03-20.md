# Discovery Report: Offline Resilience & Caching Strategy for macOS App

**Date:** 2026-03-20
**Confidence:** High
**Decision:** Extend the existing CacheManager pattern to all ViewModels with disk-backed JSON storage, add stale-while-revalidate semantics, and expand backend ETag support. No new frameworks needed.

## Hypothesis

The Hestia macOS app needs a stale-while-revalidate caching architecture so it always shows last-known data when the server is unreachable. The question is whether to use lightweight per-ViewModel caching (extending current patterns), a shared CacheManager with disk persistence, or an enterprise offline store (Core Data/SwiftData).

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** WikiCacheService already proves the disk-cache pattern works. CacheManager exists with TTL support. NetworkMonitor exists but is unused. ETag infrastructure exists on backend. 3 ViewModels already use cache-first pattern. | **Weaknesses:** 13 of 17 ViewModels have zero caching. CacheManager uses UserDefaults (bad for large payloads). No ETag handling on client side. No integration between NetworkMonitor and data loading. WikiCacheService is siloed (not reusable). |
| **External** | **Opportunities:** ETag support on only 2/29 route modules — cheap to expand. Single-user app = no cache coherence complexity. Local server = predictable latency model. JSON-on-disk is trivially debuggable. | **Threats:** UserDefaults degrades above ~1MB total cached data. SwiftData/Core Data adds migration complexity for no queryability benefit. Over-engineering caching for a single-user local app wastes sprint time. |

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | Migrate CacheManager from UserDefaults to disk-backed JSON. Add stale-while-revalidate to Command Center VM (9 concurrent calls, most visible panel). Add cache-first to Trading VM (real-time data, but last-known is better than empty). | Add CacheKey entries for remaining ViewModels (mechanical). Clean up WikiCacheService to use shared CacheManager. |
| **Low Priority** | Expand backend ETag to high-churn endpoints (health, trading, newsfeed). Add URLCache integration for automatic HTTP-level caching. | SwiftData offline store. Full sync engine. Per-field cache invalidation. |

## Argue (Best Case)

**The "Enhanced CacheManager" approach wins because:**

1. **Pattern already proven.** WikiCacheService (disk JSON) and CacheManager (TTL) both work in production. The 3 ViewModels using CacheManager (Agents, NeuralNet, SettingsProfile) demonstrate the stale-while-revalidate pattern correctly: load cached data first, show it immediately, fetch fresh in background, update cache on success.

2. **Minimal blast radius.** Migrating CacheManager's storage backend from UserDefaults to disk JSON is a single-file change. Adding cache-first loading to each ViewModel is a mechanical ~10-line pattern per VM.

3. **No new dependencies.** SwiftQuery/Sqwery libraries add dependency risk for a pattern that's already hand-rolled in 4 places. The existing code is simple and works.

4. **Fits the architecture.** This is a single-user app talking to a local server. The cache is purely a UX optimization, not a data consistency system. TTL-based expiry with stale-while-revalidate is the right level of sophistication.

5. **Memory safe.** 90 API responses averaging 5-50KB each = 0.5-5MB total disk cache. Even fully loaded in memory, this is negligible on 16GB. The disk-backed approach means only active ViewModels hold data in RAM.

## Refute (Devil's Advocate)

**Why this might not be enough:**

1. **Cache invalidation is the actual hard problem.** TTL-based caching means stale data is shown for up to N seconds after a mutation. Example: user creates a new order, switches to Command Center, sees the old order count for 5 minutes. Fix: add explicit `CacheManager.invalidate(forKey:)` calls after mutations (already done in MacAgentsViewModel).

2. **Disk I/O on main thread risk.** WikiCacheService uses `ioQueue.sync` for reads, which blocks the calling thread. If CacheManager does the same, initial app launch could stutter when loading 17 cached datasets. Fix: async disk reads or memory-map files.

3. **No offline write queue.** If the server is down and the user tries to take an action (approve memory, create order), it will fail with an error. This approach only caches reads, not writes. For Hestia this is acceptable — actions require the AI server.

4. **ETag expansion is backend work.** Adding ETag to all 29 route modules is ~2 hours of backend work. Without it, the client does full fetches every time, wasting bandwidth on unchanged data. But the server is local, so bandwidth is effectively free.

5. **No partial failure resilience in Command Center.** Currently, if 3 of 9 API calls fail, those sections show empty. With caching, they'd show stale data, but the `failedSections` tracking would be misleading (section has data but it's stale, not fresh).

## Third-Party Evidence

**SwiftUI SWR patterns (2025-2026):** The standard approach in production SwiftUI apps is hand-rolled actor-based repositories or simple cache-first patterns — exactly what Hestia already does in MacAgentsViewModel. Libraries like SwiftQuery exist but are young and add dependency weight for marginal benefit over the existing pattern.

**UserDefaults limits:** Confirmed problematic above ~1MB total. The entire plist is loaded into memory at app launch. For 90 cached API responses, this is a non-starter. Disk-backed JSON (FileManager) or URLCache are the correct alternatives.

**URLCache + self-signed certs:** Works but requires careful configuration. The existing CertificatePinningDelegate would need to be verified compatible with URLCache's caching policy. URLCache defaults to ~4MB memory / ~20MB disk — would need custom sizing. However, URLCache is opaque and harder to debug than explicit JSON files.

**Memory impact:** 90 cached responses at 5-50KB average = negligible memory impact on 16GB. Disk-backed cache with lazy loading is the correct approach.

## Gemini Web-Grounded Validation

**Model:** Gemini 2.5 Pro (thinking + google_web_search)

### Confirmed Findings
- UserDefaults is unsuitable for caching multiple API responses (confirmed: ~1MB practical limit, entire plist loaded at launch)
- Hand-rolled stale-while-revalidate is the standard approach in production SwiftUI apps (confirmed: SwiftQuery/Sqwery exist but are not widely adopted)
- URLCache with ETag works well but requires custom configuration with self-signed certs (confirmed: must set explicit cache size, verify delegate compatibility)
- Memory pressure from caching ~90 JSON responses is negligible on 16GB Apple Silicon (confirmed: 5-50MB disk cache has minimal RAM impact)

### Contradicted Findings
- None material. Gemini aligned with the internal analysis on all key points.

### New Evidence
- SwiftQuery (https://github.com/Kajatin/SwiftQuery) and Sqwery (https://github.com/laptou/sqwery) are available as TanStack Query-inspired libraries for Swift, but adoption is limited
- URLCache default limits are smaller than expected (~4MB memory, ~20MB disk) and would need explicit sizing for 90 endpoints
- Server-side `Cache-Control: stale-while-revalidate` headers would enable automatic SWR in URLSession with zero client code changes (worth investigating for backend)

### Sources
- SwiftQuery: https://github.com/Kajatin/SwiftQuery
- Sqwery: https://github.com/laptou/sqwery

## Philosophical Layer

**Ethical check:** Clean pass. Caching API responses for offline display is standard practice with no privacy or security implications. Cached data is the user's own data, stored locally.

**First principles:** The fundamental need is "show something useful when the server is down." The simplest solution is: save every successful API response to disk, load from disk before fetching from network. Everything else is optimization on top of that.

**Moonshot:** A full local-first architecture where SwiftData is the source of truth and the server syncs to it. The UI never talks to the network directly — only to the local database. **Verdict: SHELVE.** This is the right architecture for a multi-device collaborative app, but Hestia is single-user with a local server. The complexity-to-benefit ratio is wrong. Revisit if Hestia ever supports multiple clients writing to the same server.

## Key Principles Score

| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 5 | Cache lives in ~/Library/Caches/Hestia/, sandboxed, purgeable by OS. No secrets cached. |
| Empathy | 5 | Empty panels when server is down is the #1 UX gap. Stale data is dramatically better than nothing. |
| Simplicity | 5 | Extends existing proven patterns. No new dependencies. Mechanical ViewModel changes. |
| Joy | 4 | Satisfying to build. Result is immediately visible in app behavior. Loses a point because 17 ViewModels is repetitive. |

## Recommendation

**Confidence: High.** Implement a 3-phase approach:

### Phase 1: CacheManager Upgrade (2-3 hours)
Migrate CacheManager from UserDefaults to disk-backed JSON in `~/Library/Caches/Hestia/`. Keep the same API surface (`cache()`, `get()`, `invalidate()`). Add:
- Async disk reads to avoid blocking main thread
- Configurable TTL per cache key (not just global 5 minutes)
- `getStale()` method that returns expired data (for offline fallback)
- Consolidate WikiCacheService into CacheManager (eliminate the one-off)

### Phase 2: ViewModel Cache Integration (3-4 hours)
Add cache-first pattern to all 13 uncached ViewModels. Standard pattern:
```swift
func loadData() async {
    // 1. Show cached data immediately (no spinner)
    if let cached = CacheManager.shared.get(MyType.self, forKey: .myKey) {
        self.data = cached
    }
    let hadCachedData = self.data != nil
    if !hadCachedData { isLoading = true }

    // 2. Fetch fresh from server
    do {
        let fresh = try await APIClient.shared.getMyData()
        self.data = fresh
        CacheManager.shared.cache(fresh, forKey: .myKey)
    } catch {
        if !hadCachedData { errorMessage = "Could not load data" }
        // If we have cached data, silently swallow the error
    }
    isLoading = false
}
```

Priority order for Phase 2:
1. **MacCommandCenterViewModel** (highest visibility, 9 sections)
2. **MacTradingViewModel** (6 API calls, active use)
3. **MacInboxViewModel, MacHealthViewModel** (daily use)
4. **MacExplorerResourcesViewModel, MacMemoryBrowserViewModel** (moderate use)
5. **Remaining ViewModels** (lower frequency)

### Phase 3: NetworkMonitor Integration (1-2 hours)
Wire NetworkMonitor into the data loading path:
- When `isConnected == false`, skip API calls entirely (serve from cache only)
- Show a subtle "Offline — showing cached data" banner
- When connectivity restores, trigger a background refresh of visible ViewModels

### Optional Phase 4: Backend ETag Expansion (2-3 hours, separate sprint)
Expand ETag support from 2 to all 29 route modules. Add `If-None-Match` header support in APIClient. This saves bandwidth and server processing but is an optimization, not a correctness fix.

**Total estimate: 6-9 hours across Phases 1-3.**

**What would change this recommendation:**
- If the app needed to support offline writes (queue mutations) — would need a sync engine
- If the app ran on multiple devices simultaneously — would need conflict resolution
- If API responses exceeded ~50MB total — would need eviction policies
- None of these apply to Hestia today.

## Final Critiques

- **Skeptic:** "Won't stale data confuse the user?" Response: Stale data with a 'last updated 5 min ago' timestamp is dramatically better than empty panels. The WikiViewModel already does this and it works well. Users understand cached data.

- **Pragmatist:** "Is 6-9 hours worth it for a local server that's usually online?" Response: Yes. Tailscale disconnects happen (VPN restarts, Mac Mini reboots, server crashes during development). Every time this happens, the app becomes useless. The fix is proportional to the pain.

- **Long-Term Thinker:** "What happens when we add 20 more endpoints?" Response: The pattern is mechanical and scales linearly. Each new ViewModel gets the same 10-line cache-first block. CacheKeys enum grows but that's just bookkeeping. If it becomes burdensome, consider a protocol extension or property wrapper that automates the pattern.

## Open Questions

1. **Cache TTL per data type:** Trading data should have a 30-second TTL (real-time), wiki articles can have 1-hour TTL, user profile can have 10-minute TTL. Need to define the TTL matrix before implementing.
2. **Cache size limits:** Should there be a max total cache size? Probably not needed — 90 endpoints at 50KB average is 4.5MB. But worth adding a `purgeIfNeeded()` safety valve.
3. **Stale data indicator:** Should the UI show "cached" vs "live" data? A subtle timestamp like WikiViewModel's `lastUpdatedText` is probably sufficient. Full "offline mode" banner only when NetworkMonitor reports disconnected.
4. **Migration path for existing CacheManager users:** The 3 ViewModels using UserDefaults-backed CacheManager need their cached data migrated or just invalidated on first launch after the upgrade. Invalidation is simpler and acceptable (one-time cold start).
