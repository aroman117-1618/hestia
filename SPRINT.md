# Current Sprint: Wire Frontend to Backend

**Started:** 2026-02-28
**Target:** 5 sequential sprints (~10 sessions)
**Plan:** `.claude/plans/nifty-exploring-rain.md`
**Audit:** `docs/plans/wire-frontend-backend-audit-2026-02-28.md`

## Sprint 1: DevOps & Deployment

### 1A. Backend Invite Endpoints
- **Phase:** Done
- **Key files:** `hestia/api/routes/auth.py` (invite, register-with-invite, re-invite), `hestia/api/middleware/auth.py` (invite tokens), `hestia/api/schemas.py` (invite models)
- **Notes:** 4 new endpoints, nonce-based one-time invites, rate limiting (5/hour), recovery via re-invite. 28 tests passing.

### 1B. iOS/macOS Onboarding Flow
- **Phase:** Done
- **Key files:** `HestiaApp/Shared/Views/Auth/OnboardingView.swift`, `QRScannerView.swift`, `PermissionsOnboardingView.swift`, `HestiaApp/macOS/Views/Auth/MacOnboardingView.swift`
- **Notes:** iOS: QR scanner + multi-step flow. macOS: paste JSON payload. Both build clean with Swift 6 strict concurrency. HestiaShared SPM updated with invite models + `registerWithInvite()`.

### 1C. Permissions Harmony
- **Phase:** Done
- **Key files:** `HestiaApp/Shared/Views/Auth/PermissionsOnboardingView.swift`, `HestiaApp/Shared/App/ContentView.swift`
- **Notes:** Apple HIG-compliant guided flow: Calendar → Reminders → Health → Notifications → Biometric. One at a time, Skip option, grant summary. Integrated between auth and main app in ContentView.

### macOS App (Hestia)
- **Phase:** Done
- **Discovery:** Figma designs analyzed (command, explore, health screens)
- **Key files:** `HestiaApp/macOS/` (35 Swift files), `HestiaApp/project.yml`
- **Notes:** Renamed from HestiaWorkspace to Hestia. 3 views (Command, Explorer, Health) + chat panel + icon sidebar. UX polish complete: keyboard shortcuts (⌘1/2/3/\), sidebar hover effects, responsive layout (stat card grid, flexible chat panel), resizable chat divider with grabber, app icon matching iOS. Both schemes build clean.

### 1D. Tests
- **Phase:** Done
- **Key files:** `tests/test_auth_invite.py`
- **Notes:** 28 tests for invite generation, expiry, nonce consumption, register-with-invite, re-invite, rate limiting, device listing. All passing.

## Sprint 2: Explorer — Both Platforms (~3 sessions)

### 2A. Backend Explorer Module
- **Phase:** Done
- **Key files:** `hestia/explorer/models.py`, `database.py`, `manager.py`
- **Notes:** Manager pattern with ExplorerResource model, SQLite drafts + TTL cache, asyncio.gather() aggregation from Apple clients (mail, notes, reminders). LogComponent.EXPLORER added. auto-test.sh mapping added.

### 2B. Backend Explorer API
- **Phase:** Done
- **Key files:** `hestia/api/routes/explorer.py`
- **Notes:** 6 endpoints: GET resources (filterable/searchable/paginated), GET resource/{id}, GET resource/{id}/content, POST/PATCH/DELETE drafts. Registered in routes/__init__.py and server.py lifespan.

### 2C. iOS Explorer View
- **Phase:** Done
- **Key files:** `HestiaShared/.../Models/ExplorerModels.swift`, `HestiaApp/Shared/ViewModels/ExplorerViewModel.swift`, `HestiaApp/Shared/Views/Explorer/ExplorerView.swift`, `ExplorerResourceRow.swift`
- **Notes:** Section filter chips (All/Drafts/Inbox/Tasks/Notes/Files), search bar, resource list with pull-to-refresh, swipe-to-delete drafts, new draft alert. Explorer tab added to ContentView (3rd tab). Both iOS + macOS builds clean.

### 2D. macOS Explorer Enhancement
- **Phase:** Deferred (half-time cut)
- **Notes:** Existing macOS Explorer uses local FileManager. API-backed enhancement deferred per plan audit CPO-H1.

### 2E. APIClient Extensions + Tests
- **Phase:** Done
- **Key files:** `HestiaShared/.../Networking/APIClient.swift` (6 Explorer methods), `tests/test_explorer.py`
- **Notes:** 6 APIClient methods (getExplorerResources, getExplorerResource, getExplorerContent, createDraft, updateDraft, deleteDraft). 41 backend tests passing — models, database CRUD, caching, TTL, manager aggregation, filtering, search, pagination, ID formats.

## Sprint 3: Command Center / Newsfeed (~2 sessions)

### 3A. Backend Newsfeed Module
- **Phase:** Done
- **Key files:** `hestia/newsfeed/models.py`, `database.py`, `manager.py`
- **Notes:** Materialized cache with 30s TTL. Aggregates from orders, memory, tasks, health sources via `asyncio.gather(return_exceptions=True)`. Per-user read/dismiss state (composite PK: item_id + user_id) for multi-device continuity. 30-day retention cleanup. LogComponent.NEWSFEED added. auto-test.sh mapping added.

### 3B. Backend Newsfeed API
- **Phase:** Done
- **Key files:** `hestia/api/routes/newsfeed.py`
- **Notes:** 5 endpoints: GET timeline (filterable by type/source, paginated), GET unread-count (by type), POST mark-read, POST dismiss, POST refresh (rate-limited 1/10s per device). All use `Depends(get_device_token)`.

### 3C. iOS Command Center Rewrite
- **Phase:** Done
- **Key files:** `HestiaApp/Shared/Models/NewsfeedModels.swift`, `BriefingModels.swift`, `ViewModels/NewsfeedViewModel.swift`, `Views/CommandCenter/BriefingCard.swift`, `FilterBar.swift`, `NewsfeedTimeline.swift`, `NewsfeedItemRow.swift`, `CommandCenterView.swift`
- **Notes:** CommandCenterView rewritten: Header > BriefingCard > FilterBar > NewsfeedTimeline > NeuralNetView. Old tab layout (Orders/Alerts/Memory) replaced. BriefingCard is persistent above timeline (not a feed item). Empty state for zero items. Swipe-to-dismiss, auto-mark-read on appear, pull-to-refresh.

### 3D. macOS Command View Update
- **Phase:** Done
- **Key files:** `HestiaApp/macOS/Models/NewsfeedModels.swift`, `macOS/Services/APIClient+Newsfeed.swift`, `MacCommandCenterViewModel.swift`, `StatCardsRow.swift`, `ActivityFeed.swift`, `CommandView.swift`
- **Notes:** macOS target sources separately from iOS — duplicate models created. StatCardsRow wired to real viewModel data (replaced hardcoded mocks). ActivityFeed renders actual newsfeed items with filtering and search.

### 3E. APIClient + Tests
- **Phase:** Done
- **Key files:** `HestiaApp/Shared/Services/APIClient+Newsfeed.swift`, `tests/test_newsfeed.py`
- **Notes:** 6 APIClient extension methods (timeline, unread-count, mark-read, dismiss, refresh, briefing). 42 backend tests: models (8), database (13), manager (13), routes (8). Also added `list_recent_executions()` bulk method to OrderManager [T1]. All 1085 tests pass.

## Sprint 4: Settings Wiring + Health Dashboard (~2 sessions)

### 4A. Dynamic Tool Discovery
- **Phase:** Done
- **Key files:** `Shared/Models/ToolModels.swift`, `Shared/Services/APIClient+Tools.swift`, `Shared/ViewModels/IntegrationsViewModel.swift`
- **Notes:** Replaced hardcoded `toolsFor()` (23 tools, 5 categories) with `GET /v1/tools` API call. API-first with hardcoded fallback. Category mapping: backend `tool.category` → `IntegrationType`.

### 4B. Device Management UI
- **Phase:** Done
- **Key files:** `Shared/Models/DeviceModels.swift`, `Shared/Services/APIClient+Devices.swift`, `Shared/ViewModels/DeviceManagementViewModel.swift`, `Shared/Views/Settings/DeviceManagementView.swift`, `macOS/Views/Profile/MacDeviceManagementView.swift`
- **Notes:** Wired `GET /v1/user/devices`, `POST .../revoke`, `POST .../unrevoke`. iOS via Settings > Security > Manage Devices. macOS via Profile sidebar. Confirmation alert on revoke. Cannot revoke own device. Revoked devices show Restore button.

### 4C. macOS Health View Redesign
- **Phase:** Done
- **Key files:** `macOS/Models/HealthDataModels.swift`, `macOS/Services/APIClient+Health.swift`, `macOS/ViewModels/MacHealthViewModel.swift`, `macOS/Views/Health/*.swift` (5 files)
- **Notes:** Replaced fake biomarker data (telomere, methylation, CRP) with real HealthKit data from `/v1/health_data/summary` and `/v1/health_data/trend/{type}`. ActivityCard (steps/exercise/calories), Heart/Sleep/Body metric cards, CoachingCard. Empty state for no synced data. Reused GaugeArc, SparklineChart, GradientProgressBar. ADR-036.

### 4D. Proactive Intelligence Settings
- **Phase:** Done
- **Key files:** `Shared/Models/ProactiveModels.swift`, `Shared/Services/APIClient+Proactive.swift`, `Shared/ViewModels/ProactiveSettingsViewModel.swift`, `Shared/Views/Settings/ProactiveSettingsView.swift`
- **Notes:** Wired policy/patterns endpoints. Settings sections: Interruption Policy (picker), Daily Briefing (toggle + time), Quiet Hours (toggle + start/end), Pattern Detection (toggle + count), Weather (toggle + location). Added to iOS Settings as "Intelligence" section.

## Sprint 5: Audit Remediation + macOS Frontend Wiring (~2 sessions)

### 5A. Fix Proactive Auth Bug (CRITICAL)
- **Phase:** Done
- **Key files:** `hestia/api/routes/proactive.py`
- **Notes:** All 6 `Depends(verify_device_token)` → `Depends(get_device_token)`. `verify_device_token` is a validation utility (takes `str`), not a FastAPI dependency — FastAPI resolved its param as query string instead of reading `X-Hestia-Device-Token` header.

### 5B. Standardize Auth Dependency Naming
- **Phase:** Done
- **Key files:** `hestia/api/middleware/auth.py`, 9 route files (user, user_profile, orders, agents, agents_v2, wiki, explorer, auth, health_data)
- **Notes:** Removed `get_current_device` alias. ~67 mechanical substitutions across 10 files. `get_device_token` is now the single canonical auth dependency.

### 5C. macOS Navigation Infrastructure
- **Phase:** Done
- **Key files:** `macOS/State/WorkspaceState.swift`, `macOS/Views/Chrome/IconSidebar.swift`, `macOS/Views/WorkspaceRootView.swift`, `macOS/AppDelegate.swift`
- **Notes:** Added `.wiki` + `.resources` to WorkspaceView enum. IconSidebar navIcon() calls. Cmd+5 (Field Guide) + Cmd+6 (Resources) keyboard shortcuts. Removed dead `inactiveIcon()` code.

### 5D. macOS Wiki (Field Guide) Tab
- **Phase:** Done
- **Key files:** `macOS/Models/WikiModels.swift`, `macOS/Services/APIClient+Wiki.swift`, `macOS/ViewModels/MacWikiViewModel.swift`, `macOS/Views/Wiki/*.swift` (4 files)
- **Notes:** 2-pane layout (sidebar + detail). Sidebar: vertical tab buttons (Overview/Modules/Decisions/Roadmap/Diagrams) with article counts + scrollable article list. Detail: toolbar (refresh/generate-all), article content, status badges, generate button for pending articles. Reuses WikiArticle models from HestiaShared.

### 5E. macOS Explorer Resources Mode
- **Phase:** Done
- **Key files:** `macOS/ViewModels/MacExplorerResourcesViewModel.swift`, `macOS/Views/Explorer/MacExplorerResourcesView.swift`, `macOS/Views/Explorer/ExplorerView.swift`
- **Notes:** Segmented control (Files/Resources) added to existing ExplorerView. Files mode = existing filesystem browser. Resources mode = backend `/v1/explorer/` API (matching iOS). Filter bar, search, draft CRUD.

### 5F. macOS Resources Tab (LLMs/Integrations/MCPs)
- **Phase:** Done
- **Key files:** `macOS/ViewModels/MacCloudSettingsViewModel.swift`, `MacIntegrationsViewModel.swift`, `macOS/Views/Resources/*.swift` (6 files)
- **Notes:** 3-tab container. LLMs: 2-column provider list + detail (model selector, health check, state toggle, add/remove). Integrations: expandable cards with status badges, permission requests, tool lists. MCPs: placeholder. macOS IntegrationsViewModel avoids UIKit (uses EventKit directly, excludes HealthKit).

### 5G. Docs + Validation
- **Phase:** Done
- **Notes:** CLAUDE.md updated (sprint status, project structure, macOS app description — 66 files, 6 views). Both targets build clean. 1083 tests passing, 3 skipped.

---

## Previous Sprint: Claude Code Config Refresh (COMPLETE)

All topics done: Direct API config, Figma MCP, macOS app (Hestia), Skills redesign, Cheat sheet.
Deferred: CI/CD pipeline, Fireproof (server reliability).
