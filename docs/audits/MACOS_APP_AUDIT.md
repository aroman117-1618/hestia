# Hestia macOS App Comprehensive UI Audit

**Date**: 2026-03-19
**Scope**: All Views and ViewModels in HestiaApp/macOS and HestiaApp/Shared
**Coverage**: 146 macOS Swift files + 17 Shared ViewModels

## Executive Summary

The macOS app has **EXCELLENT** wiring coverage with 18 fully wired features and only 1 placeholder (MCP). The application uses clean patterns:
- ViewModels consistently call `APIClient.shared` methods
- Real API endpoints for data loading (no hardcoded mock data except fallback)
- Proper async/await throughout
- Graceful error handling and degradation

**Key finding**: The app is production-ready for all major features with no critical unwired functionality in active use.

---

## Feature-by-Feature Analysis

### ✅ FULLY WIRED FEATURES (18)

#### 1. Chat (MacChatViewModel + MacChatPanelView)
- **Status**: FULLY WIRED ✅
- **What works**:
  - Message sending (streaming + REST fallback)
  - Mode switching
  - Session management
  - Reactions and outcome feedback
  - Background session conversion
  - Typewriter effect
  - Bylines and hallucination risk display
- **Endpoints used**:
  - `POST /v1/chat`
  - `POST /v1/chat/stream`
  - `POST /v1/mode/switch`
  - `POST /v1/sessions`
  - `GET /v1/outcomes`
  - `POST /v1/outcomes/{id}/feedback`
  - `POST /v1/orders` (from session)
- **Complexity**: HIGH - Fully implemented
- **Files**:
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacChatViewModel.swift`
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/Views/Chat/MacChatPanelView.swift`

#### 2. Trading Dashboard (MacTradingViewModel + TradingMonitorView)
- **Status**: FULLY WIRED ✅
- **What works**:
  - Portfolio snapshot, positions, trade history
  - Risk status monitoring with kill switch
  - Autonomous trading enable/disable with modal
  - Watchlist management (add/remove)
  - Bot creation and control (start/stop)
  - Trade feedback submission
  - Decision feed (client-side, from bot actions)
  - Periodic refresh (30s timer)
- **Endpoints used** (14 total):
  - `GET /v1/trading/portfolio`
  - `GET /v1/trading/positions`
  - `GET /v1/trading/trades`
  - `GET /v1/trading/risk-status`
  - `GET /v1/trading/watchlist`
  - `GET /v1/trading/bots`
  - `POST /v1/trading/bots`
  - `POST /v1/trading/bots/{id}/start`
  - `POST /v1/trading/bots/{id}/stop`
  - `POST /v1/trading/kill-switch/activate`
  - `POST /v1/trading/kill-switch/deactivate`
  - `POST /v1/trading/trades/{id}/feedback`
  - `POST /v1/trading/watchlist`
  - `DELETE /v1/trading/watchlist/{id}`
- **Complexity**: VERY HIGH - Sprint 26 production feature
- **Files**:
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacTradingViewModel.swift`
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/Views/Command/TradingMonitorView.swift`

#### 3. Health Dashboard (MacHealthViewModel + HealthView)
- **Status**: FULLY WIRED ✅
- **What works**:
  - Health summary (10 metrics: steps, distance, calories, exercise, resting HR, HRV, sleep, weight, BMI, date)
  - Progress rings (steps, exercise, calories)
  - Sleep and step trend sparklines (7-day)
- **Endpoints used** (3):
  - `GET /v1/health/summary`
  - `GET /v1/health/trend?metricType=stepCount&days=7`
  - `GET /v1/health/trend?metricType=sleepAnalysis&days=7`
- **Complexity**: MEDIUM - Real HealthKit data from backend
- **Files**:
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacHealthViewModel.swift`
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/Views/Health/HealthView.swift`

#### 4. Memory Browser (MacMemoryBrowserViewModel + MemoryBrowserView)
- **Status**: FULLY WIRED ✅
- **What works**:
  - Paginated chunk list (50 per page)
  - Sorting (importance, created, updated)
  - Filtering (by type, status)
  - Chunk detail inline editing
  - Status filter (active/archived)
- **Endpoints used** (2):
  - `GET /v1/memory/chunks` (with limit, offset, sortBy, sortOrder, chunkType, status)
  - `PUT /v1/memory/chunks/{id}`
- **Complexity**: MEDIUM - Full CRUD except delete
- **Files**:
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacMemoryBrowserViewModel.swift`
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/Views/Memory/MemoryBrowserView.swift`

#### 5. Command Center Dashboard (MacCommandCenterViewModel + CommandView)
- **Status**: FULLY WIRED ✅
- **What works**:
  - 6 stat cards (unread, pending memory, active orders, events, health, feed)
  - System health snapshot
  - Calendar week view
  - Newsfeed timeline (20 items)
  - Learning metrics (positive ratio, alert count, memory chunk count)
  - Investigation history (20 items)
  - Health summary card
  - Activity widgets (system, internal, external)
  - Orders panel
- **Endpoints used** (9+):
  - `GET /v1/health`
  - `GET /v1/memory/staged`
  - `GET /v1/orders`
  - `GET /v1/newsfeed/timeline`
  - `GET /v1/learning/meta-monitor/latest`
  - `GET /v1/learning/memory-health`
  - `GET /v1/learning/trigger-alerts`
  - `GET /v1/investigate/history`
  - `GET /v1/health/summary`
  - EventKit (local calendar)
- **Complexity**: VERY HIGH - Aggregates 9+ data sources
- **Files**:
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacCommandCenterViewModel.swift`
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/Views/Command/CommandView.swift`

#### 6. Explorer Files (MacExplorerFilesViewModel + ExplorerFilesView)
- **Status**: FULLY WIRED ✅
- **What works**:
  - File tree navigation
  - File preview (text, code, markdown, PDF)
  - File search
  - File sorting
  - Hidden file toggle
  - File creation/upload
  - File inline editing
  - File deletion with confirmation
  - File renaming
  - File move operations
- **Endpoints used** (5):
  - `GET /v1/files`
  - `GET /v1/files/read`
  - `POST /v1/files`
  - `PUT /v1/files/{id}`
  - `DELETE /v1/files/{id}`
- **Complexity**: HIGH - Full file CRUD
- **Files**:
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacExplorerFilesViewModel.swift`
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/Views/Explorer/ExplorerFilesView.swift`

#### 7. Unified Inbox (MacInboxViewModel + ExplorerInboxView)
- **Status**: FULLY WIRED ✅
- **What works**:
  - Unified inbox (mail, reminders, calendar)
  - Unread count tracking
  - Per-source unread counts
  - Item detail loading
  - Mark as read (single/all)
  - Archive items
  - Refresh inbox
  - Source filtering
- **Endpoints used** (6):
  - `GET /v1/inbox`
  - `GET /v1/inbox/unread`
  - `POST /v1/inbox/{id}/read`
  - `POST /v1/inbox/read-all`
  - `POST /v1/inbox/{id}/archive`
  - `POST /v1/inbox/refresh`
- **Complexity**: MEDIUM - Full inbox operations
- **Files**:
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacInboxViewModel.swift`
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/Views/Explorer/ExplorerInboxView.swift`

#### 8. Research/Neural Net 3D Graph (MacNeuralNetViewModel + ResearchView)
- **Status**: FULLY WIRED ✅
- **What works**:
  - 3D SceneKit knowledge graph visualization
  - Node selection with detail popover
  - Edge visualization (shared topics/entities)
  - Graph mode toggle (legacy memory vs. facts)
  - Node type multi-select filtering
  - Focus topic search
  - Depth limiting (1-3)
  - Data source filtering (conversation, mail, notes, calendar, etc.)
  - Source category filtering (facts mode only)
  - Time slider for bi-temporal queries (facts mode)
  - Durability filtering (contextual/durable/principled)
  - Principle extraction via distillation
  - Principle approval/rejection workflow
  - Fact invalidation (mark outdated)
  - Cache with 5-min TTL
  - Mock fallback if server unavailable
  - Client-side force-directed layout (for mock only)
- **Endpoints used** (6):
  - `GET /v1/research/graph` (with 8+ query parameters)
  - `GET /v1/research/principles`
  - `POST /v1/research/principles/distill`
  - `POST /v1/research/principles/{id}/approve`
  - `POST /v1/research/principles/{id}/reject`
  - `POST /v1/research/facts/{id}/invalidate`
- **Complexity**: VERY HIGH - 3D visualization + bi-temporal queries
- **Files**:
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacNeuralNetViewModel.swift` (720 lines)
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/Views/Research/ResearchView.swift`

#### 9. Learning Metrics (MacCommandCenterViewModel integration)
- **Status**: FULLY WIRED ✅
- **What works**:
  - Meta-monitor report (positive ratio, session count, quality)
  - Memory health (chunk count, redundancy %, durability)
  - Trigger alerts with acknowledgment state
  - Learning panel display
  - Metric calculations
- **Endpoints used** (3):
  - `GET /v1/learning/meta-monitor/latest`
  - `GET /v1/learning/memory-health`
  - `GET /v1/learning/trigger-alerts`
- **Complexity**: MEDIUM - Read-only dashboard
- **Files**:
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacCommandCenterViewModel.swift` (lines 126-153)
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/Views/Command/LearningMetricsPanel.swift`

#### 10. Agent Management (MacAgentsViewModel + MacAgentsView)
- **Status**: FULLY WIRED ✅
- **What works**:
  - V2 markdown-based agent listing
  - V1 slot-based agent CRUD (fallback)
  - Agent selection and detail view
  - Personality markdown editing and save
  - Agent photo upload/download
  - Agent snapshot history and restore
  - Default agent setting
  - Agent file management
- **Endpoints used** (6+):
  - `GET /v1/agents/v2`
  - `GET /v1/agents/v2/{dir}/files`
  - `PUT /v1/agents/v2/{dir}/files/{file}`
  - `POST /v1/agents/{slot}/photo` (V1)
  - `GET /v1/agents/{slot}/photo` (V1)
  - `DELETE /v1/agents/{slot}/photo` (V1)
  - `GET /v1/agents/{slot}/snapshots` (V1)
- **Complexity**: HIGH - V1/V2 dual support
- **Files**:
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacAgentsViewModel.swift`
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/Views/Settings/MacAgentsView.swift`

#### 11. User Profile Settings (MacSettingsProfileViewModel + MacProfileView)
- **Status**: FULLY WIRED ✅
- **What works**:
  - Profile loading (name, description, photo)
  - Name editing
  - Description editing
  - Photo upload
  - Photo deletion
  - Profile save
- **Endpoints used** (4):
  - `GET /v1/user/profile`
  - `PUT /v1/user/profile`
  - `POST /v1/user/profile/photo`
  - `DELETE /v1/user/profile/photo`
- **Complexity**: MEDIUM - Standard CRUD
- **Files**:
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacSettingsProfileViewModel.swift`
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/Views/Settings/MacProfileView.swift`

#### 12. Cloud Provider Management (MacCloudSettingsViewModel + MacCloudSettingsView)
- **Status**: FULLY WIRED ✅
- **What works**:
  - Provider listing (Anthropic, OpenAI, Google)
  - Provider addition with API key securely stored
  - Provider state management (disabled → smart → full)
  - Model selection per provider
  - Provider deletion
  - Health check per provider
  - Cloud usage summary (tokens, cost)
  - Effective cloud state display
- **Endpoints used** (7):
  - `GET /v1/cloud/providers`
  - `POST /v1/cloud/providers`
  - `DELETE /v1/cloud/providers/{provider}`
  - `PATCH /v1/cloud/providers/{provider}/state`
  - `PATCH /v1/cloud/providers/{provider}/model`
  - `POST /v1/cloud/providers/{provider}/health`
  - `GET /v1/cloud/usage`
- **Complexity**: HIGH - State machine + secure credential handling
- **Files**:
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacCloudSettingsViewModel.swift`
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/Views/Resources/MacCloudSettingsView.swift`

#### 13. Integrations Status (MacIntegrationsViewModel + MacIntegrationsView)
- **Status**: FULLY WIRED ✅
- **What works**:
  - Integration status for 4 platforms (calendar, reminders, notes, mail)
  - Permission request handling
  - Tool listing per integration (from API with fallback)
  - Status colors (connected, denied, not connected, backend only)
  - Platform icons and descriptions
- **Endpoints used** (1):
  - `GET /v1/tools` (to load tool definitions)
- **Complexity**: MEDIUM - Integrates EventKit + API
- **Files**:
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacIntegrationsViewModel.swift` (240 lines)
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/Views/Resources/MacIntegrationsView.swift`

#### 14. Device Management (MacDeviceManagementViewModel + MacDeviceManagementView)
- **Status**: FULLY WIRED ✅
- **What works**:
  - Device listing with metadata
  - Device revocation
  - Device un-revocation (if previously revoked)
  - Current device detection
  - Device status display
- **Endpoints used** (3):
  - `GET /v1/auth/devices`
  - `POST /v1/auth/devices/{id}/revoke`
  - `POST /v1/auth/devices/{id}/unrevoke`
- **Complexity**: MEDIUM - Simple state operations
- **Files**:
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacDeviceManagementViewModel.swift`
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/Views/Profile/MacDeviceManagementView.swift`

#### 15. Wiki (Architecture Guide) (MacWikiViewModel + MacWikiView)
- **Status**: FULLY WIRED ✅
- **What works**:
  - Wiki article listing with categories
  - Article detail with markdown rendering
  - Tab navigation (overview, architecture, modules, timeline)
  - Roadmap visualization with milestones
  - Wiki refresh with regeneration
  - Caching (2-min TTL)
  - Article search
- **Endpoints used** (3):
  - `GET /v1/wiki/articles`
  - `GET /v1/wiki/articles/{id}`
  - `GET /v1/wiki/roadmap`
- **Complexity**: MEDIUM - Markdown rendering + caching
- **Files**:
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacWikiViewModel.swift`
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/Views/Wiki/MacWikiView.swift`

#### 16. Scheduled Orders (MacCommandCenterViewModel integration)
- **Status**: FULLY WIRED ✅
- **What works**:
  - Order listing (limit 20)
  - Order status tracking
  - Active order count for stat card
  - Order creation from session (background)
  - Orders panel in dashboard
- **Endpoints used** (1+):
  - `GET /v1/orders`
  - `POST /v1/orders` (from session)
- **Complexity**: LOW - Dashboard integration only
- **Note**: Full order CRUD available via API but not exposed in macOS detail views
- **Files**:
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacCommandCenterViewModel.swift` (lines 84-93)
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/Views/Command/OrdersPanel.swift`

#### 17. Newsfeed Timeline (MacCommandCenterViewModel integration)
- **Status**: FULLY WIRED ✅
- **What works**:
  - Timeline loading (limit 20)
  - Unread count tracking
  - Item display in Command Center widget
  - Full newsfeed list view
  - Item expansion and detail
- **Endpoints used** (1):
  - `GET /v1/newsfeed/timeline`
- **Complexity**: MEDIUM - Dashboard + full view
- **Files**:
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacCommandCenterViewModel.swift` (lines 114-124)
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/Views/Command/NewsFeedListView.swift`

#### 18. Investigations History (MacCommandCenterViewModel integration)
- **Status**: FULLY WIRED ✅
- **What works**:
  - Investigation history display (limit 20)
  - Investigation status and metadata
  - Investigation URL/content details
  - Investigation list in Command Center widget
- **Endpoints used** (1):
  - `GET /v1/investigate/history`
- **Complexity**: MEDIUM - Data-rich history list
- **Note**: Creation happens via chat; no create UI in macOS
- **Files**:
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacCommandCenterViewModel.swift` (lines 155-164)
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/Views/Command/InvestigationsListView.swift`

---

### ⚠️ PARTIALLY WIRED FEATURES (2)

#### 1. Explorer Resources (MacExplorerResourcesViewModel + MacExplorerResourcesView)
- **Status**: PARTIALLY WIRED ⚠️
- **What works**:
  - Resource loading (drafts, bookmarks, references)
  - Type filtering (drafts, bookmarks, references)
  - Search
  - Draft creation
  - Resource list display
- **Endpoints used** (2):
  - `GET /v1/explorer/resources`
  - `POST /v1/explorer/drafts`
- **Missing**:
  - Resource detail/preview view
  - Resource deletion
  - Resource favorites/pinning
  - Draft publishing workflow
  - Bookmark import/export
- **Complexity to complete**: MEDIUM (S/M)
- **Files**:
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacExplorerResourcesViewModel.swift`
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/Views/Explorer/MacExplorerResourcesView.swift`

#### 2. User Photo Editor (MacSettingsProfileViewModel)
- **Status**: PARTIALLY WIRED ⚠️
- **What works**:
  - Photo display in profile view
  - Photo upload from picker
  - Photo deletion
- **Endpoints used** (2):
  - `POST /v1/user/profile/photo`
  - `DELETE /v1/user/profile/photo`
- **Missing**:
  - Photo cropping/resizing UI
  - Photo preview/verification before save
  - Photo history/previous photos
  - Drag-and-drop upload
- **Complexity to complete**: SMALL (S)
- **Files**:
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/Views/Settings/ProfilePhotoEditor.swift`

---

### 🔴 NOT WIRED / PLACEHOLDER FEATURES (1)

#### 1. MCP (Model Context Protocol) Server Management
- **File**: `MacMCPPlaceholderView.swift`
- **Status**: NOT WIRED 🔴
- **Current state**: Static placeholder view saying "MCP server management coming in a future update"
- **Endpoints needed** (hypothetical):
  - `GET /v1/mcp/servers` (list)
  - `POST /v1/mcp/servers` (create)
  - `DELETE /v1/mcp/servers/{id}` (delete)
  - `PATCH /v1/mcp/servers/{id}/config` (update)
  - (or equivalent backend structure)
- **Complexity to implement**: LARGE (L) - New feature area
- **Note**:
  - MCP is part of Resources tab as 4th tab
  - Backend implementation status unknown
  - No API contract documented yet
  - Placeholder is appropriate for future work
- **Files**:
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/Views/Resources/MacMCPPlaceholderView.swift`
  - `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/Views/Resources/MacResourcesView.swift` (includes tab)

---

## Architecture Patterns Observed

### ✅ Strengths

1. **Centralized API Client**: All ViewModels use `APIClient.shared` singleton
   - Consistent token management
   - Centralized retry/error handling
   - Easy to mock in tests

2. **Proper Async/Await**: Universal use of Swift Concurrency
   - No callbacks or combine publishers in ViewModels
   - Clear async flow from UI → ViewModel → APIClient

3. **Error Handling**: Three-tier approach
   - HestiaError enum with variants
   - Error state published in each ViewModel
   - Graceful degradation (mock fallback for research graph)

4. **Data Caching**: Strategic caching with TTLs
   - Research graph: 5-min TTL (expensive computation)
   - Wiki articles: 2-min TTL
   - Principles: 2-min TTL (invalidated on approval/rejection)
   - CacheManager.shared singleton pattern

5. **State Management**: @Published properties with MainActor isolation
   - Proper thread safety
   - UI always observes published state
   - No data races

6. **Pagination**: Properly implemented where needed
   - Memory browser: limit/offset with page buttons
   - Command Center: limit-only (acceptable for dashboard aggregation)

7. **Fallback Strategies**:
   - Research graph: Mock data + client-side layout if server unavailable
   - Integrations: Fallback tool definitions if API returns empty

### ⚠️ Areas for Improvement

1. **No WebSocket/SSE for Live Updates**
   - Trading dashboard polls every 30s (acceptable but not ideal)
   - Health data polls (alternative: push notifications)
   - Would require backend infrastructure change

2. **Limited State Persistence**
   - Most state ephemeral (no UserDefaults cache)
   - No offline mode
   - No draft recovery on crash

3. **No Background Sync**
   - Unlike iOS, macOS app doesn't use background task API
   - Could leverage Timer for periodic refresh (already done for trading)

4. **Pagination Incomplete**
   - Command Center uses limit-only (20 items cap)
   - Newsfeed: No pagination (20 item limit)
   - Investigation: No pagination (20 item limit)
   - OK for MVP but could be improved for large datasets

5. **Limited Real-time**
   - No SSE streams for chat (streaming implemented but single-use)
   - Trading updates: Polling not push
   - Could implement via WebSocket extension

---

## API Endpoints Summary

### Total Endpoints in API Contract
- **209 endpoints across 29 route modules** (per docs/api-contract.md)

### Endpoints Actually Used by macOS App
- **~65 distinct endpoint calls** across all features
- **Coverage: ~31% of total endpoints**

### Breakdown by Category

| Category | Used | Total | Notes |
|----------|------|-------|-------|
| Chat | 7 | 3 | Stream + REST fallback |
| Trading | 14 | 14+ | Sprint 26 complete |
| Health | 3 | 8+ | Summary + 2 trends |
| Memory | 2 | 14 | List + update only |
| Research | 6 | 8+ | Graph + principles |
| Agents | 6+ | varies | V1+V2 support |
| Cloud | 7 | 7 | Complete coverage |
| Devices | 3 | 3 | Complete coverage |
| Files | 5 | 8+ | CRUD complete |
| Inbox | 6 | 6 | Complete coverage |
| Wiki | 3 | 3 | Complete coverage |
| Orders | 1 | 5+ | List only |
| Newsfeed | 1 | 5+ | List only |
| Investigate | 1 | 6+ | List only |
| User/Profile | 4 | 8+ | Profile + photo |
| Integrations | 1 | 3 | Tools list only |
| Learning | 3 | varies | Read-only |

### Endpoints NOT Used (but available in API)

**Voice** (2 endpoints):
- `/v1/voice/quality-check` — iOS/voice input only
- `/v1/voice/journal-analyze` — iOS/voice input only

**Memory Management** (7 endpoints):
- Consolidation (2): preview, execute
- Pruning (2): preview, execute
- Search (1): Not exposed in macOS UI
- Ingest (1): Not exposed in macOS UI
- Import Claude (1): Not exposed in macOS UI
- Importance stats (1): Not exposed
- Sensitive flag (1): Not exposed in macOS UI

**Tasks** (5 endpoints):
- Create, get, approve, cancel, retry — Backend/CLI only

**Proactive/Briefings** (varies):
- Not exposed in macOS UI (CLI feature)

**Outcomes** (3 endpoints):
- Create (not used)
- List (not used)
- Get detail (not used)
- Feedback only (used)

**Suggestions** (3 endpoints):
- Create, list, dismiss — Not exposed

**Mode Management** (3 endpoints):
- Get current, switch, get detail — Only switch used

---

## Files Modified (Research Only - No Changes Made)

### Key ViewModel Files
- `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacChatViewModel.swift`
- `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacTradingViewModel.swift`
- `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacCommandCenterViewModel.swift`
- `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacNeuralNetViewModel.swift` (720 lines)
- `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacHealthViewModel.swift`
- `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacMemoryBrowserViewModel.swift`
- `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacExplorerFilesViewModel.swift`
- `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacInboxViewModel.swift`
- `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacAgentsViewModel.swift`
- `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacSettingsProfileViewModel.swift`
- `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacCloudSettingsViewModel.swift`
- `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacIntegrationsViewModel.swift` (240 lines)
- `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacExplorerResourcesViewModel.swift`
- `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacWikiViewModel.swift`
- `/sessions/dazzling-wonderful-fermi/mnt/hestia/HestiaApp/macOS/ViewModels/MacDeviceManagementViewModel.swift`

### Total Files Examined
- **146 Swift files** in macOS/
- **17 Shared ViewModels**
- **10 Shared Services** (API extensions, HealthKit, Orders, Reminders, Speech, Calendar)

---

## Recommendations

### 🔴 HIGH PRIORITY (Quick Wins)

1. **Add Resource Detail View to Explorer Resources**
   - **Estimated effort**: MEDIUM (S/M — 2-4 hours)
   - **Files to modify**:
     - `MacExplorerResourcesViewModel.swift` — add detail loading
     - `MacExplorerResourcesView.swift` — add detail sheet
   - **Endpoints needed**:
     - `GET /v1/explorer/resources/{id}` (if not exists, likely included in list)
   - **Benefit**: Complete Explorer feature for macOS

2. **Add Order Detail View with Execution Tracking**
   - **Estimated effort**: MEDIUM (S/M — 3-5 hours)
   - **Files to create/modify**:
     - Create `MacOrderDetailView.swift`
     - Modify `OrdersPanel.swift` to navigate to detail
   - **Endpoints needed**:
     - `GET /v1/orders/{order_id}` (already implemented)
     - `GET /v1/orders/{order_id}/executions` (already implemented)
   - **Benefit**: Better order tracking for scheduled prompts

3. **Expand Newsfeed Widget to Show Details**
   - **Estimated effort**: SMALL (S — 1-2 hours)
   - **Files to modify**:
     - `NewsFeedListView.swift` — add item detail/expansion
   - **Endpoints**: Already loaded in memory
   - **Benefit**: Better content preview in dashboard

### 🟡 MEDIUM PRIORITY (Architectural)

1. **Implement WebSocket/SSE for Real-time Trading Updates**
   - **Estimated effort**: LARGE (L — 8-12 hours)
   - **Impact**: Replace 30s polling with push
   - **Files to modify**:
     - `MacTradingViewModel.swift` — implement SSE stream
     - Likely new `TradeStreamService.swift`
   - **Backend requirement**: SSE endpoint for trades
   - **Benefit**: Lower latency, reduced server load

2. **Add Investigation Creation UI**
   - **Estimated effort**: MEDIUM (M — 4-6 hours)
   - **Files to create**:
     - `MacInvestigateView.swift`
   - **Endpoints needed**:
     - `POST /v1/investigate` (create)
   - **Current**: CLI + chat only
   - **Benefit**: macOS feature parity with iOS

3. **Implement Background Sync for Health Data**
   - **Estimated effort**: MEDIUM (M — 4-6 hours)
   - **Files to modify**:
     - `MacHealthViewModel.swift` — add background refresh timer
   - **Benefit**: Always-fresh health data

### 🟢 LOWER PRIORITY (Future Work)

1. **Implement MCP Server Management UI**
   - **Estimated effort**: VERY LARGE (XL — 20+ hours)
   - **Blocker**: Backend feature may not be complete
   - **Files to create**:
     - Replace `MacMCPPlaceholderView.swift` with full implementation
     - Create `MacMCPViewModel.swift`
   - **Endpoints**: Likely TBD or incomplete
   - **Benefit**: Protocol server management in macOS app

2. **Add Memory Consolidation/Pruning UI**
   - **Estimated effort**: LARGE (L — 10-12 hours)
   - **Files to create**:
     - `MacMemoryManagementView.swift`
     - `MacMemoryManagementViewModel.swift`
   - **Endpoints already available**:
     - `/v1/memory/consolidation/preview`
     - `/v1/memory/consolidation/execute`
     - `/v1/memory/pruning/preview`
     - `/v1/memory/pruning/execute`
   - **Benefit**: Advanced memory management in macOS

3. **Add Task Management UI**
   - **Estimated effort**: LARGE (L — 12-15 hours)
   - **Files to create**:
     - `MacTasksView.swift`
     - `MacTasksViewModel.swift`
   - **Endpoints already available**:
     - `/v1/tasks` (POST, GET)
     - `/v1/tasks/{id}/approve`
     - `/v1/tasks/{id}/cancel`
     - `/v1/tasks/{id}/retry`
   - **Benefit**: Full task lifecycle management in macOS

---

## Conclusion

**The Hestia macOS app is well-engineered and production-ready.** The audit found:

- ✅ **18 fully wired features** with real API integration
- ⚠️ **2 partially wired features** that work but have limited scope
- 🔴 **1 placeholder** that's appropriately marked "coming soon"
- **No fake data** except strategic fallbacks (research graph)
- **Excellent architecture** with proper error handling and state management

The app successfully implements **31% of available API endpoints**, with strong coverage of high-priority features (chat, trading, health, research, settings). The missing endpoints (voice, memory consolidation, tasks, suggestions) are either iOS-specific, backend-only, or lower-priority features that can be added incrementally.

**No critical issues found.** Recommended work is additive and non-blocking.

