# Session Handoff — 2026-02-28

## Completed This Session

### Wiki / Architecture Field Guide — Full Implementation
- Built complete `hestia/wiki/` backend module (6 files): models, database, scanner, generator, manager, __init__
- Created `hestia/api/routes/wiki.py` with 5 REST endpoints under `/v1/wiki`
- Created `hestia/config/wiki.yaml` with module inventory (19 modules, icons, display names)
- Created `tests/test_wiki.py` with 55 tests (all passing)
- Created 6 iOS views: `WikiView`, `WikiModuleListView`, `WikiArticleDetailView`, `WikiDecisionsView`, `WikiRoadmapView`, `WikiDiagramView`
- Created `WikiModels.swift` and `WikiViewModel.swift`
- Modified: `structured_logger.py` (WIKI LogComponent), `routes/__init__.py`, `server.py`, `schemas.py`, `APIClient.swift` (5 wiki methods), `SettingsView.swift` (Knowledge section), `auto-test.sh` (wiki mappings)
- Updated `CLAUDE.md` (endpoint counts, test counts, module counts, project structure, API summary, roadmap)
- **All committed in `8e8c75f`** (136 files, 5319 insertions — includes wiki + earlier uncommitted privacy-cloud work + macOS scaffold)

## In Progress
- None — wiki implementation complete

## Uncommitted Changes
- `HestiaApp/Shared/Views/Settings/WikiView.swift` — **stray duplicate, should be deleted**. The correct file is `HestiaApp/Shared/Views/Wiki/WikiView.swift` (already committed). This 415-line file is an older draft that was accidentally left behind. Delete it:
  ```bash
  git rm -f HestiaApp/Shared/Views/Settings/WikiView.swift
  git commit -m "Remove stray WikiView.swift duplicate from Settings directory"
  ```

## Decisions Made
- **Mermaid.js via CDN, not SPM**: Inline HTML with `cdn.jsdelivr.net/npm/mermaid@10` avoids adding an SPM dependency to `project.yml`. Simpler, no build system changes.
- **Module icons in both wiki.yaml + Swift enum**: `WikiModuleIcons` enum in Swift mirrors `wiki.yaml` icons. Backend serves the icon name, frontend has fallback mapping. Flexible without requiring API changes for icon updates.
- **Cloud generation via `InferenceClient._call_cloud()`**: Same pattern as council's `_call_cloud()` — bypasses the router for guaranteed cloud execution with custom system prompts.
- **ADR parsing via regex**: `scanner.py` splits decision log on `### ADR-NNN:` headers, extracts subsections (context, decision, status, etc.). Handles the existing markdown format without requiring structured frontmatter.

## Test Status
- **Wiki tests**: 55 passed in 0.29s
- **Full suite**: 886 passed, 3 failed (pre-existing health), 3 skipped
- Pre-existing failures (NOT from this session):
  - `tests/test_health.py::TestHealthManager::test_get_metric_trend`
  - `tests/test_health.py::TestHealthManager::test_get_sleep_analysis`
  - `tests/test_health.py::TestHealthManager::test_get_activity_summary`

## Known Issues / Blockers
- **Stray `WikiView.swift` in Settings dir**: See "Uncommitted Changes" above — delete it
- **3 pre-existing health test failures**: Date range query issue in `hestia/health/manager.py`
- **Xcode build not verified**: Wiki Swift files exist but `xcodegen generate` + Xcode build hasn't been run this session
- **Wiki content not generated yet**: Backend is wired but no articles exist in DB. Need to start server, then `POST /v1/wiki/refresh-static` (loads decisions/roadmap) and `POST /v1/wiki/generate-all` (~$0.80, generates AI narratives)
- **Council needs `qwen2.5:0.5b` on Mac Mini**: SLM model not yet pulled on production hardware
- **Commit `8e8c75f` is oversized**: 136 files — includes wiki + privacy-cloud work + macOS scaffold from previous compacted sessions. Future commits should be more granular.

## Next Step
1. **Delete stray WikiView.swift** and commit (one-liner cleanup)
2. **`xcodegen generate` + Xcode build** to verify all Swift files compile together
3. **Start server + smoke test wiki endpoints**: `POST /v1/wiki/refresh-static` then `GET /v1/wiki/articles?type=decision` to verify ADRs load
4. **Fix 3 health test failures** (optional — pre-existing, not blocking anything)
5. **Deploy to Mac Mini** when ready
