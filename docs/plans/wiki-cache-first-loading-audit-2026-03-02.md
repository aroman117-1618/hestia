# Plan Audit: Wiki Cache-First Loading + Roadmap Rename
**Date:** 2026-03-02
**Verdict:** APPROVE

## Plan Summary

Add stale-while-revalidate disk caching to the macOS Field Guide (Wiki) so cached articles display instantly on view appear, with silent background refresh. Also rename 3 occurrences of "Development Timeline" to "Roadmap". Touches 5 files (1 new, 4 modified), all macOS-only Swift.

## Scale Assessment

| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|----------------|-------------------|
| Single user | Yes | None | N/A |
| Family (2-5) | Yes | Cache is device-local, not shared — each device caches independently | Negligible — per-device cache is correct behavior |
| Community | Yes | Same — local cache per device is the right design at any scale | N/A |

**Assessment:** The plan is inherently device-scoped (disk cache per device). This is architecturally correct at every scale level — there's no shared state to worry about. The backend already handles multi-device via JWT auth; the cache layer sits entirely below that.

## Front-Line Engineering Review

### Feasibility: Straightforward ✅

All prerequisites exist:
- `WikiArticle`, `WikiRoadmapResponse` are already `Codable` (confirmed in `WikiModels.swift`)
- APIClient already uses `.convertToSnakeCase` / `.convertFromSnakeCase` (matching encoder/decoder)
- `.task` modifier in `MacWikiView` provides the right async entry point
- `FileManager` cache directory APIs are well-established on macOS 15.0+

### Complexity: Low (~1-2 hours implementation)

- New `WikiCacheService.swift`: ~80 lines (6 methods, all trivial file I/O)
- `MacWikiViewModel.swift` changes: ~30 lines changed (rewrite `loadArticles()`, add 2 properties)
- 3 string renames: 1 line each

### Hidden Prerequisites: None

No database migrations, no backend changes, no config changes, no new dependencies.

### Testing Strategy

- **Manual testing covers it**: Kill server → launch app → verify cached data appears. Start server → verify silent refresh. First launch → verify error state. These are UI-level behaviors that are hard to unit test meaningfully without mocking FileManager.
- **Build verification**: `xcodebuild -scheme HestiaWorkspace` confirms compilation.
- **No backend tests needed** — this is purely client-side.

### Staff Engineer Pushback: Why Not URLCache?

Sprint 6 just added `Cache-Control` headers to backend responses. `URLSession`'s built-in `URLCache` could theoretically handle stale-while-revalidate for free — no custom service, no manual file I/O. **Why reinvent?**

**Response:** `URLCache` is opaque. You can't show "Updated 5 min ago" (no access to cache write timestamps). You can't do "show stale immediately, then silently replace" in a controlled way — `URLSession` either returns cached or network, not both sequentially. The custom approach gives explicit control over the two-phase load. The tradeoff is ~80 lines of simple code vs. losing UI control. Acceptable.

### Staff Engineer Pushback: Generate/Refresh → loadArticles Failure

After `generateAll()` succeeds, it calls `loadArticles()` to refresh the list. If that network fetch fails, the ViewModel falls back to cache — which still has the *pre-generation* articles. The user sees stale content and thinks generation failed.

**Response:** This is an edge case (server up for generate, then down for the immediate follow-up fetch) but worth noting. Mitigation: `generateAll()` could save the fresh articles to cache directly from its response, but `WikiGenerateAllResponse` doesn't return full articles (just status strings). The real fix would be a backend change. For now, the user can hit retry. **Low risk, noted for future.**

### Staff Engineer Pushback: Synchronous Cache Reads on Main Actor

The plan's API shows `loadCachedArticles() -> [WikiArticle]?` as a synchronous call, but it's invoked from the `@MainActor` ViewModel. That's file I/O on the main thread.

**Response:** The cache files are <100KB. `FileManager` reads at this size complete in <1ms on SSD. This is well within the 16ms frame budget. Making the reads `async` would add complexity for no perceptible gain. Acceptable, but the implementer should be aware of the tradeoff.

### Developer Experience: Clean ✅

The plan follows the existing codebase patterns well. `WikiCacheService` mirrors the singleton pattern used everywhere (`APIClient.shared`, `PersistenceController.shared`). The ViewModel changes are localized to `loadArticles()` — no API signature changes, no protocol changes.

## Architecture Review

### Fit: Good ✅

- File-based cache in `~/Library/Caches/Hestia/` is the macOS-standard location for this pattern
- Singleton service is consistent with `APIClient.shared`, `PersistenceController.shared`
- The plan correctly avoids Core Data (which exists in Shared/ for iOS) — a file-based JSON cache is simpler and more appropriate for read-heavy, write-rare wiki data

### Data Model: No Changes Required ✅

All types are already `Codable`. No new types needed beyond the small `CacheMeta` struct (2 optional dates). The cache files are derivative — they can be deleted at any time without data loss.

### Integration Risk: Minimal ✅

Only `MacWikiViewModel` is modified. No changes to `WikiCacheService` ← `APIClient` relationship (they're independent). The sidebar/detail pane views consume `@Published` properties that don't change shape — just timing.

### Concern: `WikiArticleListResponse` vs `[WikiArticle]`

The plan says to cache `[WikiArticle]` but the API returns `WikiArticleListResponse` (which wraps `articles: [WikiArticle]` + `count: Int`). Caching just the array is correct — the wrapper `count` field adds no value in cache.

### Concern: JSON Key Strategy Mismatch

The plan specifies `.convertToSnakeCase` for the cache encoder. This is fine for round-tripping (encode snake → decode snake), but it means the cache files on disk will have snake_case keys. This is consistent with how APIClient encodes request bodies, so it's internally consistent. No issue.

## Product Review

### User Value: High ✅

This directly solves the "server down → blank Field Guide" problem. For a personal assistant app, the server being temporarily unavailable is a normal scenario (Mac Mini rebooting, Hestia server restarting after deploy, network hiccup). Having the last-known content available instantly is the expected behavior.

### Edge Cases: Well-Handled ✅

- **First launch, no cache, no server**: Error state with retry button (existing behavior preserved)
- **First launch, no cache, server available**: Normal loading → cache populated for next time
- **Cache present, server down**: Cached data shown silently (the primary improvement)
- **Cache present, server up**: Cached data shown instantly, then silently refreshed
- **Stale cache with server changes**: Next successful refresh overwrites cache (correctness guaranteed)

### Multi-Device: Correct ✅

Each macOS device maintains its own cache. iOS doesn't have the Wiki view yet (macOS-only feature), so no platform divergence concern.

### Scope: Right-Sized ✅

This is a small, focused improvement with high UX impact. The "Roadmap" rename is a trivial piggyback that's been needed since the last restructure. No scope creep.

### Opportunity Cost: Negligible

1-2 hours of work. Not displacing anything meaningful.

### PM Pushback: "Updated X ago" — Freshness or Misleading?

"Updated 5 min ago" tells the user when the *cache* was written, not when the *content* last changed on the server. If the server was down for 2 days, it shows "Updated 2 days ago" — does that communicate "articles may be stale" or "the system checked 2 days ago and confirmed everything is current"? Ambiguous.

**Response:** For a single-user personal project this is low risk — Andrew understands what it means. If this were multi-user, the label should say "Last synced" instead of "Updated" to clarify. Minor wording choice, not a blocker.

### PM Pushback: Should This Be a Generic Cache Service?

If wiki caching works, Explorer, Newsfeed, and Health will want the same pattern. Should we build `DiskCacheService<T: Codable>` now?

**Response:** No — YAGNI. Build wiki-specific now. If a second consumer appears, *then* extract the generic. The API surface (`load/save + meta`) is simple enough that extraction later is cheap. Building the abstraction first risks over-engineering for hypothetical consumers.

## UX Review

### Design System Compliance: Good ✅

- "Updated X ago" footer uses `MacColors.textFaint` and size 10 — consistent with existing pill/badge patterns
- No new colors, fonts, or spacing values introduced

### Interaction Model: Clean ✅

- **Instant data → silent refresh** is the best possible UX pattern for cached content
- Error banner only shows when there's no cached fallback — progressive disclosure of failure
- `TimelineView(.periodic(every: 60))` for the timestamp is the right approach (auto-refreshes the relative time string without manual timer management)

### Platform Divergences: N/A

iOS doesn't have Wiki view. macOS-only change.

### Empty States: Preserved ✅

The plan explicitly preserves the existing error state + retry button when no cache is available. The "No articles yet" empty state is unaffected.

### Minor Suggestion

The "Updated X ago" text could show "Loading..." on first launch (no cache, fetching), but this is already handled by `isLoading` spinner logic. No change needed.

## Infrastructure Review

### Deployment Impact: None ✅

- No server changes
- No database migration
- No config changes
- Client-only update (next Xcode build)

### New Dependencies: None ✅

All APIs used (`FileManager`, `JSONEncoder`, `RelativeDateTimeFormatter`) are Foundation framework built-ins.

### Monitoring: N/A

Client-side change. Cache failures are intentionally silent (best-effort). If caching breaks, the app simply falls back to network-only behavior — degraded but functional.

### Rollback Strategy: Trivial ✅

Revert the 5 files. Cache files on disk are harmless artifacts (in `~/Library/Caches/`, which macOS can purge automatically).

### Resource Impact: Negligible ✅

- Wiki articles: ~50KB JSON (20 articles × ~2.5KB each)
- Roadmap: ~5KB JSON
- Cache meta: ~100 bytes
- Total disk: <100KB. No memory impact (read on demand, not held in memory by the cache service)

## Executive Verdicts

### CISO: Acceptable ✅
No new attack surface. Cache files contain the same public wiki content the user already sees in the UI. No credentials, no PII, no tokens. Files written to standard `~/Library/Caches/` with `.atomic` writes (no corruption risk). Reads wrapped in `try?` (no crash risk from malformed cache).

### CTO: Acceptable ✅
Clean implementation that follows established patterns. File-based cache is simpler than Core Data for this use case (read-heavy, write-rare, no relationships, no queries). The singleton `WikiCacheService` is consistent with existing service patterns. `Task.detached` for file I/O keeps the main actor responsive. No technical debt introduced.

### CPO: Acceptable ✅
High UX value for minimal effort. Solves the real "blank screen when server is down" problem. The "Updated X ago" footer adds useful context without cluttering the UI. The "Roadmap" rename cleans up naming inconsistency from the last sprint. Right priority, right scope.

## Final Critiques

### 1. Most Likely Failure: Cache Deserialization After Model Change

If `WikiArticle` gains a new non-optional field in a future update, the cached JSON will fail to decode (missing key). The plan handles this correctly — `loadCachedArticles()` returns `nil` on decode failure (wrapped in `try?`), which falls through to network fetch. **Mitigation is built-in.**

For extra safety, consider making new fields optional with defaults, but this is a general Codable best practice, not a plan-specific concern.

### 2. Critical Assumption: `try?` Silence is Acceptable

The plan assumes all cache failures should be silent. This is correct for a best-effort cache — but if `FileManager` starts failing for permissions reasons (sandbox change, disk full), the user gets no feedback. **Validation:** This is the standard pattern for `~/Library/Caches/` — macOS manages this directory and can purge it at will. Apps are expected to handle missing/corrupt cache gracefully. The assumption holds.

### 3. Half-Time Cut List

If only 50% of the plan could ship:
1. **Keep:** Cache-first loading for articles (the core value)
2. **Keep:** "Roadmap" rename (3 trivial string changes)
3. **Cut:** Roadmap caching (roadmap is secondary content, rarely viewed)
4. **Cut:** "Updated X ago" footer (nice-to-have polish)

This confirms the plan's priorities are correctly ordered — the cache mechanism is the real value, everything else is polish.

## Conditions for Approval

None. Plan is approved as-is. All assumptions validated, architecture is sound, scope is right-sized.
