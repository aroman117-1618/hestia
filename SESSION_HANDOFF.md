# Session Handoff — 2026-03-05

## Mission
Implement Sprint 12: Apple Metadata Cache — FTS5-backed local cache for Apple ecosystem entities (Notes, Calendar, Reminders) with fuzzy resolution via rapidfuzz, enabling reliable single-call tool execution for small local models.

## Completed
- **Sprint 12A: Core module** (`bbf2a30`): `hestia/apple_cache/` — database (FTS5 schema + sync tracking), resolver (two-phase: FTS5 candidates + rapidfuzz scoring), manager (TTL-based sync, lazy Apple client init, write-through hooks), models (CachedEntity, EntitySource, ResolvedMatch). 45 tests.
- **Sprint 12B: Tool integration** (`a94e00d`): 3 new tools (`find_note`, `read_note`, `find_event`), 5 modified tools (`get_note`, `search_notes`, `list_reminders`, `create_note/event/reminder`). Write-through cache updates. 6 new tests. Total Apple tools: 20.
- **Server lifecycle wiring**: apple_cache_manager added to Phase 2 parallel init, sequential retry, readiness check, and shutdown (#20).
- **LogComponent.APPLE_CACHE** added to structured logging enum.
- **rapidfuzz>=3.0.0** added to requirements.in/requirements.txt.
- **CLAUDE.md updated**: Test counts (1683), project structure (apple_cache/), architecture notes, LogComponent list.

## In Progress
- Nothing code-related — all implementation committed.
- SPRINT.md needs phase marker updates for Sprint 12 (blocked by parallel session's uncommitted changes to SPRINT.md).

## Decisions Made
- **Two-phase resolution**: FTS5 narrows candidates (<1ms) then rapidfuzz `token_set_ratio` scores them. Handles word reordering ("grocery list" matches "List - Grocery").
- **TTL sync intervals**: Notes 6h, Calendar 2h, Reminders 4h. Calendar is most time-sensitive.
- **Write-through caching**: Create/update/delete tools immediately update cache, avoiding stale reads.
- **Lazy Apple client init**: Clients imported and instantiated on first use to avoid circular imports.
- **`read_note(query)` as killer feature**: One call does fuzzy resolve + fetch content. Previously required 4+ tool calls that 7B models couldn't chain reliably.

## Test Status
- 1683 total (1611 backend + 72 CLI), 1680 passing, 3 skipped
- All apple_cache tests (51) passing, all apple tests (30/33, 3 skipped integration) passing

## Uncommitted Changes
- `CLAUDE.md` — our updates (test counts, structure, architecture notes). Ready to commit.
- **Parallel session's changes (DO NOT COMMIT)**: `SPRINT.md`, `docs/plans/*`, `hestia/memory/*`, `tests/test_memory.py`, `hestia/inbox/bridge.py`, `tests/test_inbox_bridge.py`

## Known Issues / Landmines
- **Parallel session active**: Another Claude session has uncommitted changes to memory module, inbox bridge, SPRINT.md. Don't stage those files.
- **rapidfuzz is a new dependency**: Must `pip install -r requirements.txt` after pulling on Mac Mini.
- **Apple cache sync requires running Apple clients**: Tests mock these, but on Mac Mini, AppleScript/EventKit must work.
- **Pre-existing test failure**: `TestInferenceClientIntegration::test_simple_completion` requires running Ollama. Marked `@pytest.mark.integration` but shows up in some test runs.
- **pytest hangs after completion**: Known ChromaDB background thread issue. Tests pass but process doesn't exit cleanly.

## Next Step
1. Commit `CLAUDE.md` (only our file — avoid parallel session's changes)
2. Update SPRINT.md when parallel session's changes are resolved
3. **Sprint 12C: API endpoints** — add `/v1/apple-cache/status`, `/v1/apple-cache/sync`, `/v1/apple-cache/resolve` for iOS UI
4. **Sprint 12D: Proactive sync** — background task that runs cache sync on server startup and periodically
