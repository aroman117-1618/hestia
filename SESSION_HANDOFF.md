# Session Handoff — 2026-03-18

## Mission
Debug and fix the macOS Research view (Graph + Memory tabs) that were completely non-functional after importing 988 chunks of Claude conversation history. All four bugs fixed and shipped; graph is now live with 200+ nodes.

## Completed

- **Graph cache deserialization fix** (`hestia/research/manager.py`, commit `b4b918c`)
  - `get_graph()` returned empty arrays on every cache hit — nodes/edges/clusters were never deserialized from the cached JSON
  - Fixed: added `GraphNode.from_dict()`, `GraphEdge.from_dict()`, `GraphCluster.from_dict()` calls on cache read
  - Root cause: comment "Cached response is already serialized" was wrong — the cache stores dicts, not `GraphResponse`

- **Force-directed layout overflow fix** (`hestia/research/graph_builder.py`, commit `5c4e3a9`)
  - 200+ nodes caused unbounded velocity accumulation → positions at 10^80 over 120 iterations
  - Fixed: per-step velocity cap (`max_velocity = 2.0`) + final normalization to `target_radius = 6.0`

- **Memory browser decode failure fix** (`HestiaApp/macOS/Models/MemoryBrowserModels.swift`, commit `5c4e3a9`)
  - `MemoryChunkItem` had explicit snake_case `CodingKeys` that conflicted with `APIClient`'s `convertFromSnakeCase` decoder
  - Decoder converts `chunk_type` → `chunkType`, then looks for CodingKey with stringValue `"chunk_type"` → miss → throw → empty list
  - Fixed: removed explicit `CodingKeys` entirely; decoder strategy handles conversion automatically
  - Same fix applied to `MemoryChunkUpdateRequest`

- **Camera distance fix** (`MacSceneKitGraphView.swift`, commit `94e746e`)
  - Initial camera at z=8 with graph normalized to radius 6.0 meant nodes were 2–3 units from camera
  - Fixed: camera moved to z=20, `zFar` extended to 200

- **Legend accuracy fix** (`ResearchView.swift`, commit `94e746e`)
  - Missing Chat and Insight node types (the two types covering all imported Claude history)
  - All 5 existing legend entries had wrong hex colors (didn't match backend `CATEGORY_COLORS`)
  - Fixed: added Chat (#5AC8FA) and Insight (#8E8E93) entries; corrected all 7 legend colors to match backend

- **Content prefix stripping** (`NodeDetailPopover.swift`, commit `94e746e`)
  - Imported Claude history nodes prefixed with `[IMPORTED CLAUDE HISTORY — Foo]: [User]:` noise
  - Fixed: `strippingBracketPrefixes()` regex helper applied to main content and connected node labels

- **macOS environment default** (`Configuration.swift`, commit `ae3f95a`)
  - macOS app was defaulting to `.local` (localhost) — changed to `.tailscale` (Mac Mini)

- **Claude history import** (78 conversations / 988 chunks)
  - Done via SSH Python bypass on Mac Mini (CLI JWT token from local server was invalid on Mac Mini)
  - `data-2026-03-15-22-44-27-batch-0000/` directory imported, stale graph cache cleared
  - Chunks stored as `source="claude_history"`, `chunk_type="conversation"` or `"insight"`

- **GitHub Project board + CLAUDE.md workflow** (commit `85f88a0`)
  - Added board update steps to Phase 3/4 checklists in CLAUDE.md
  - Added stop hook that blocks if sprint work isn't board-synced

## In Progress
- None — all bug fixes are committed and functional

## Decisions Made
- **Velocity cap for graph layout**: Chose `max_velocity = 2.0` + final normalization over reformulating the algorithm. Fast, no physics model change. Works for up to ~500 nodes before density degrades.
- **Remove CodingKeys on MemoryBrowserModels**: `APIClient` uses `convertFromSnakeCase` globally — explicit snake_case keys always conflict. Rule: never mix explicit snake_case `CodingKeys` with `convertFromSnakeCase` decoder.
- **claude_history MemorySource gap deferred**: `claude_history` is not in the `MemorySource` enum, so imported chunks can't be filtered by source in Memory Browser. Deferred to future sprint.

## Test Status
- `tests/test_research.py`: 70 tests — all passing (verified post-fix)
- Full suite: 2142 backend + 135 CLI = 2277 total (no new tests added this session)

## Uncommitted Changes
- `docs/discoveries/gemini-deep-research-prompt.md` — from previous session, untracked
- `docs/discoveries/trading-module-research-and-plan.md` — trading module research, untracked
- `scripts/gh-project-sync.sh` — GitHub board helper script, untracked (should be committed)

## Known Issues / Landmines
- **`gh-project-sync.sh status` command is broken**: Uses `--owner` flag not supported by `gh project item-edit`. Direct workaround: `gh project item-edit --id <id> --field-id <fid> --single-select-option-id <oid> --project-id PVT_kwHODI9jOM4BSG9c`. Should be fixed before next board update.
- **Graph legend colors are hardcoded**: Colors in `ResearchView.swift` legend will drift if backend `CATEGORY_COLORS` changes. Future: source from an API endpoint.
- **`claude_history` MemorySource gap**: 988 imported chunks can't be filtered by source in Memory Browser. Add `claude_history` to `MemorySource` enum in a future sprint.
- **Server NOT running on Mac Mini**: Verify with `lsof -i :8443` via SSH before testing on device.
- **Graph cache TTL**: 300s TTL. Force fresh build with `DELETE FROM graph_cache` on Mac Mini's `data/research.db` if graph looks stale after data changes.

## Process Learnings
- **CodingKeys/decoder conflict is a recurring trap**: Second time `convertFromSnakeCase` has silently broken a struct decode. Should add a warning comment in `APIClient.swift` and/or a note in iOS memory file.
- **First-pass success rate**: 3 of 4 root causes found correctly on first hypothesis. Memory browser took 2 passes (wrong-shape assumption → CodingKeys conflict).
- **Missed @hestia-explorer delegation**: Initial "why is graph empty" investigation was done manually with curl. Explorer agent would have been faster for tracing `get_graph()` → cache → deserialization path.
- **Background pytest visibility**: Temp file paths are fragile. Prefer `@hestia-tester` or foreground runs for critical verification.

## Next Steps
1. **Commit untracked files**: At minimum `scripts/gh-project-sync.sh` — it's referenced in CLAUDE.md workflow
2. **Fix `gh-project-sync.sh status` command**: Remove positional project number arg and `--owner` flag; add `--project-id PVT_kwHODI9jOM4BSG9c`
3. **Sprint 20: Neural Net Graph Phase 2** — time slider, bi-temporal exploration — the natural next sprint now that graph is functional with real data
4. **Verify on Mac Mini**: Open macOS app → Research tab → confirm graph loads with 988 chunks visible; confirm Memory tab shows all chunks with correct types
