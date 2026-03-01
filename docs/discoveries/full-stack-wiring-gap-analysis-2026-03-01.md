# Discovery Report: Full-Stack Wiring Gap Analysis

**Date:** 2026-03-01
**Confidence:** High
**Decision:** Fix the MockHestiaClient defaults in 4 iOS ViewModels (30-minute fix, massive ROI), then prioritize the Command Center newsfeed rewrite (Sprint 3) as the highest-impact next sprint.

## Hypothesis

There are significant wiring gaps between Hestia's 109 backend endpoints, iOS app, and macOS app -- specifically views using mock/placeholder data, endpoints with no client consumers, and backend features with no UI at all.

---

## Executive Summary

The investigation revealed **5 critical categories of wiring gaps** across the stack:

1. **4 iOS ViewModels default to MockHestiaClient** -- the single biggest bug in the app
2. **macOS Health view is 100% hardcoded mock data** -- no API calls at all
3. **~30 backend endpoints have zero client consumers** across tasks, tools, proactive, agents_v2, user management
4. **macOS Explorer is local-filesystem-only** -- doesn't use the backend Explorer API
5. **MCPs tab is a placeholder** -- "Coming Soon" with no backend support

---

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Backend is comprehensive (109 endpoints, 19 route modules). iOS has good architecture (protocol-based, API client extensions). OrdersService has excellent backend-first-with-offline-fallback pattern. Explorer and Newsfeed recently wired end-to-end (Sprint 2/3 prep). macOS Command Center already calls real APIs for health, memory, orders, newsfeed. | **Weaknesses:** 4 critical ViewModels default to MockHestiaClient instead of APIClient.shared. macOS Health is entirely fake data. No tasks/tools UI exists anywhere. agents_v2 (10 endpoints) has zero client usage. User device management (3 endpoints) has no UI. Memory sensitivity endpoint unwired. |
| **External** | **Opportunities:** Newsfeed infrastructure already built (backend + API client extension + ViewModel) -- iOS Command Center rewrite is nearly ready. macOS Health could be wired to real HealthKit data synced through backend with minimal effort. Device management UI would enable multi-device experience. | **Threats:** MockHestiaClient defaults mean the iOS app silently returns canned data when APIClientProvider doesn't configure the ViewModel -- users see a "working" app that isn't actually working. The more features built on top of mock defaults, the harder the debt accumulates. |

---

## Gap Inventory

### Category 1: iOS ViewModels Defaulting to MockHestiaClient (CRITICAL BUG)

These ViewModels are instantiated with `MockHestiaClient()` as the default. Only `ChatView` calls `.configure(client:)` via the `APIClientProvider` environment object. The rest **silently use mock data in production**.

| ViewModel | Default | Real Client Injection? | Impact |
|-----------|---------|----------------------|--------|
| `ChatViewModel` | `MockHestiaClient()` | YES -- ChatView calls `.configure(client:)` | Working (but fragile pattern) |
| `SettingsViewModel` | `MockHestiaClient()` | **NO** | System health + pending memory count are FAKE |
| `CommandCenterViewModel` | `MockHestiaClient()` | **NO** | Pending memory count is FAKE (orders work via OrdersService separately) |
| `MemoryReviewViewModel` | `MockHestiaClient()` | **NO** | Memory review approve/reject goes to mock -- **data loss** |
| `NeuralNetViewModel` | `APIClient.shared` (correct) | N/A | Working correctly |
| `CloudSettingsViewModel` | `APIClient.shared` (correct) | N/A | Working correctly |
| `WikiViewModel` | `APIClient.shared` (correct) | N/A | Working correctly |
| `ExplorerViewModel` | `APIClient.shared` (correct) | N/A | Working correctly (iOS only) |
| `NewsfeedViewModel` | `APIClient.shared` (correct) | N/A | Working correctly |

**Fix:** Change 3 ViewModels to default to `APIClient.shared` instead of `MockHestiaClient()`. The `ChatViewModel` already has the `.configure()` pattern to handle the `APIClientProvider` environment, but `SettingsViewModel`, `CommandCenterViewModel`, and `MemoryReviewViewModel` should just use `APIClient.shared` directly like the newer ViewModels do.

Files:
- `/Users/andrewlonati/hestia/HestiaApp/Shared/ViewModels/SettingsViewModel.swift` (line 57)
- `/Users/andrewlonati/hestia/HestiaApp/Shared/ViewModels/CommandCenterViewModel.swift` (line 50)
- `/Users/andrewlonati/hestia/HestiaApp/Shared/ViewModels/MemoryReviewViewModel.swift` (line 32)
- `/Users/andrewlonati/hestia/HestiaApp/Shared/ViewModels/ChatViewModel.swift` (line 31)

### Category 2: macOS Views with Static/Mock Data

| View | Data Source | Backend Endpoint Available? | Gap |
|------|------------|---------------------------|-----|
| `MacHealthViewModel` | 100% hardcoded mock (biological age, telomere, CRP, etc.) | YES -- `/v1/health_data/summary`, `/v1/health_data/trend/{type}` | **Fully mocked** |
| `MacExplorerViewModel` | Local filesystem only (`NSOpenPanel` + `FileManager`) | YES -- `/v1/explorer/resources`, drafts CRUD | **Different paradigm** -- local files vs backend resources |
| `MacCommandCenterViewModel` | **Real API calls** (health, memory, orders, newsfeed, calendar) | YES | **Wired correctly** |
| `MacChatViewModel` | `APIClient.shared` (correct) | YES | **Wired correctly** |
| `MacUserProfileViewModel` | **Real API calls** to `/v1/user-profile/*` | YES | **Wired correctly** |

**Key finding:** The macOS Health view (`MacHealthViewModel`) is the worst offender -- it has hardcoded values like `biologicalAge: 47`, `telomereLength: 5.2`, `crpScore: 3.2` with a comment `// Future: fetch from /v1/health_data/summary`. The backend has 7 health_data endpoints ready to serve real data.

File: `/Users/andrewlonati/hestia/HestiaApp/macOS/ViewModels/MacHealthViewModel.swift`

### Category 3: Backend Endpoints with Zero Client Consumers

| Module | Endpoint | Method | Purpose | Client Calls |
|--------|----------|--------|---------|-------------|
| **Tasks** | `/v1/tasks` | POST | Create background task | **0** |
| **Tasks** | `/v1/tasks` | GET | List tasks | **0** |
| **Tasks** | `/v1/tasks/{id}` | GET | Get task detail | **0** |
| **Tasks** | `/v1/tasks/{id}/approve` | POST | Approve task | **0** |
| **Tasks** | `/v1/tasks/{id}/cancel` | POST | Cancel task | **0** |
| **Tasks** | `/v1/tasks/{id}/retry` | POST | Retry task | **0** |
| **Tools** | `/v1/tools` | GET | List available tools | **0** |
| **Tools** | `/v1/tools/{name}` | GET | Get tool details | **0** |
| **Tools** | `/v1/tools/{name}/schema` | GET | Get tool JSON schema | **0** |
| **Proactive** | `/v1/proactive/policy` | GET | Get interruption policy | **0** |
| **Proactive** | `/v1/proactive/policy` | POST | Update policy | **0** |
| **Proactive** | `/v1/proactive/patterns` | GET | List patterns | **0** |
| **Proactive** | `/v1/proactive/notifications` | GET | Notification history | **0** |
| **Proactive** | `/v1/proactive/notifications` | POST | Send notification | **0** |
| **Agents v2** | `/v2/agents` | GET | List agents (md-based) | **0** |
| **Agents v2** | `/v2/agents/{slot}` | GET | Get agent config | **0** |
| **Agents v2** | `/v2/agents/{slot}` | POST | Create agent | **0** |
| **Agents v2** | `/v2/agents/{slot}` | DELETE | Delete agent | **0** |
| **Agents v2** | `/v2/agents/{slot}/notes` | GET | Get agent notes | **0** |
| **Agents v2** | `/v2/agents/{slot}/notes` | PUT | Update notes | **0** |
| **Agents v2** | `/v2/agents/reload` | POST | Reload from .md files | **0** |
| **Agents v2** | `/v2/agents/diff` | GET | Show config diff | **0** |
| **Agents v2** | `/v2/agents/{slot}/export` | GET | Export agent | **0** |
| **Agents v2** | `/v2/agents/{slot}/import` | POST | Import agent | **0** |
| **User** | `/v1/user/devices` | GET | List devices | **0** |
| **User** | `/v1/user/devices/{id}/revoke` | POST | Revoke device | **0** |
| **User** | `/v1/user/devices/{id}/unrevoke` | POST | Unrevoke device | **0** |
| **Sessions** | `/v1/sessions/{id}` | DELETE | Delete session | **0** |
| **Memory** | `/v1/memory/{id}/sensitive` | PATCH | Set sensitivity | **0** |
| **Health Data** | `/v1/health_data/summary` | GET | Today's summary | **0** (comment only in macOS) |
| **Health Data** | `/v1/health_data/summary/{date}` | GET | Date summary | **0** |
| **Health Data** | `/v1/health_data/trend/{type}` | GET | Metric trend | **0** |
| **Health Data** | `/v1/health_data/sync/history` | GET | Sync history | **0** |
| **Auth** | `/v1/auth/invite` | POST | Generate invite | **0** (server-only) |
| **Auth** | `/v1/auth/re-invite` | POST | Regenerate invite | **0** (server-only) |
| **Auth** | `/v1/auth/refresh` | POST | Refresh token | **0** |

**Total: ~35 endpoints with zero client callers** (some auth endpoints are intentionally server-side-only).

### Category 4: iOS Placeholder / "Coming Soon" UI

| View | State | What's Missing |
|------|-------|---------------|
| `ResourcesView` MCPs tab | "Coming Soon" placeholder | No MCP backend module exists at all |
| `IntegrationsView` tool lists | Hardcoded tool definitions in ViewModel | Should fetch from `/v1/tools` endpoint |

### Category 5: Feature Parity Gaps (iOS has it, macOS doesn't)

| Feature | iOS | macOS |
|---------|-----|-------|
| Explorer (backend resources) | Full API integration via `ExplorerViewModel` | Local filesystem only (`NSOpenPanel`) |
| Health Coaching Preferences | Full UI + API wiring | No health settings UI |
| Wiki | Full tabbed UI + API wiring | No wiki view |
| Memory Review | MemoryWidget + MemoryReviewView | No memory review UI (shows count in Command Center) |
| Neural Net Graph | Full 3D SceneKit visualization | No equivalent |
| Agent Profile Management | Full CRUD + photos + snapshots | No agent management |
| Integrations (Calendar/Reminders/Notes/Mail settings) | Full permissions + config UI | No integrations settings |

---

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | Fix MockHestiaClient defaults (4 ViewModels) -- **30 min, fixes silent data loss**. Wire macOS Health to real API -- **2 hrs, replaces fake data**. | Wire tools endpoint to IntegrationsView -- **1 hr, dynamic tool lists** |
| **Low Priority** | Build Tasks UI (6 endpoints unwired) -- **4-6 hrs, enables task approval UX**. Build Device Management UI -- **3 hrs, multi-device story**. Wire agents_v2 to iOS -- **4 hrs, modern agent config**. | Wire memory sensitivity patch -- **30 min, edge case**. Wire session delete -- **15 min, cleanup only**. Wire auth refresh -- **30 min, token management** |

---

## Argue (Best Case)

The backend is remarkably complete at 109 endpoints. The iOS app has excellent architecture patterns (protocol-based clients, proper async/await, DesignSystem tokens). Sprint 2's Explorer and the newsfeed prep show the team can wire features end-to-end efficiently. The OrdersService demonstrates the gold standard pattern: backend-first with offline fallback via CoreData.

Fixing the MockHestiaClient defaults is a 30-minute change that immediately makes Settings, Command Center memory counts, and Memory Review all work with real data. This is the single highest-ROI fix possible.

The newsfeed infrastructure (backend module + API client extension + ViewModel + macOS integration) is already built and tested. Sprint 3's Command Center rewrite is the natural next step and would bring 20+ endpoints into active use.

## Refute (Devil's Advocate)

The MockHestiaClient default bug has been in production since the beginning -- it means:
- `SettingsViewModel.refresh()` shows mock system health data
- `MemoryReviewViewModel` approve/reject actions go to mock (approved memories are silently lost)
- `CommandCenterViewModel` shows mock pending memory count

This isn't a "future enhancement" -- it's a data integrity bug. Every memory approval through the iOS UI has been going to `/dev/null`.

The macOS Health view with hardcoded biological age, telomere length, and CRP scores could actively mislead a health-conscious user. Even if it's labeled as mock data, the values look real and specific.

The 35 unwired endpoints represent significant backend development effort (tests, documentation, security) that delivers zero user value until clients consume them.

## Third-Party Evidence

The pattern of ViewModels defaulting to mock clients instead of real ones is a known anti-pattern in SwiftUI apps. The correct approach (already used by newer ViewModels like `CloudSettingsViewModel`, `WikiViewModel`, `ExplorerViewModel`) is to default to `APIClient.shared` directly. The `MockHestiaClient` should only be used in SwiftUI previews and tests, never as a production default.

The macOS vs iOS feature parity gap is normal for a project at this stage -- macOS was added later. The strategy should be to wire the highest-value features first (Health data, Memory Review) rather than trying to achieve full parity.

---

## Recommendation

### Immediate (This Session -- 30 minutes)
1. **Fix MockHestiaClient defaults** in `SettingsViewModel`, `CommandCenterViewModel`, `MemoryReviewViewModel`, and `ChatViewModel` to use `APIClient.shared`
2. This is not a feature request -- it's a bug fix that prevents silent data loss

### Sprint 3: Command Center Newsfeed (Next Sprint -- 6 hours)
The newsfeed infrastructure is already built. The sprint should:
1. Rewrite iOS `CommandCenterView` to use `NewsfeedViewModel` (timeline + briefing card)
2. Wire iOS proactive briefing endpoint (`/v1/proactive/briefing` -- already in APIClient extension)
3. Add unread badge to Command Center tab
4. Polish macOS `ActivityFeed` (already partially wired)

### Sprint 4: Health Dashboard + Device Management (Future)
1. Wire macOS Health view to real `/v1/health_data/summary` and `/v1/health_data/trend` endpoints
2. Build iOS health dashboard view (not just the coaching preferences)
3. Build device management UI (`/v1/user/devices`, revoke/unrevoke)

### Backlog (Lower Priority)
- Tasks UI (6 backend endpoints, no UI anywhere)
- Tools browsing UI (3 endpoints)
- agents_v2 integration (10 endpoints, coexists with v1)
- Proactive policy/patterns/notifications UI (5 endpoints)
- MCP management (no backend exists yet)
- Memory sensitivity toggle
- macOS Explorer using backend resources API

**Confidence: High.** The MockHestiaClient fix is unambiguously correct. The Sprint 3 recommendation follows directly from the existing sprint plan and the infrastructure already in place.

---

## Final Critiques

### The Skeptic: "Why won't this work?"
**Challenge:** "Changing MockHestiaClient to APIClient.shared might break views that aren't authenticated yet."
**Response:** The views that use these ViewModels (SettingsView, CommandCenterView, MemoryReviewView) are only accessible after authentication. The `APIClientProvider` is already configured with a token before these views render. The newer ViewModels (`CloudSettingsViewModel`, `WikiViewModel`, etc.) already use `APIClient.shared` as default and work fine.

### The Pragmatist: "Is the effort worth it?"
**Challenge:** "35 unwired endpoints sounds bad. Should we invest in wiring all of them?"
**Response:** No. The 80/20 rule applies. The MockHestiaClient fix (30 min) and Sprint 3 Command Center (6 hrs) together bring ~25 endpoints into active use and fix the most critical data integrity bug. The remaining ~20 unwired endpoints are lower-priority features (tasks UI, tools browsing, agents_v2) that can wait.

### The Long-Term Thinker: "What happens in 6 months?"
**Challenge:** "Won't this tech debt compound?"
**Response:** The newer ViewModels (Sprint 2+) already follow the correct pattern of using `APIClient.shared`. The fix for the older ViewModels is a one-time migration. The real long-term risk is the 10 agents_v2 endpoints that duplicate agents_v1 -- at some point, one needs to be deprecated. But that's an architectural decision, not a wiring gap.

---

## Open Questions

1. **Is the `ChatViewModel` configure pattern worth keeping?** The newer ViewModels prove that direct `APIClient.shared` works. Should `ChatViewModel` be simplified to match?
2. **Should macOS Explorer switch from local-filesystem to backend API?** Current implementation is useful for local file browsing, but iOS Explorer uses the backend resource aggregation API. Different paradigms for different platforms may be intentional.
3. **When should agents_v2 replace agents_v1?** Ten endpoints with zero callers suggests the v2 system was built but never wired to any UI.
4. **Is MCP management planned for a future sprint?** The "Coming Soon" placeholder in ResourcesView has no backend support.

---

## Appendix: Complete Endpoint-to-Client Mapping

### Fully Wired (Both Client + Backend)
- `/v1/ping` -- health check (implicit)
- `/v1/health` -- `APIClient.getSystemHealth()` -> SettingsView (via mock!), MacCommandCenterVM
- `/v1/auth/register` -- `APIClient.registerDevice()`
- `/v1/auth/register-with-invite` -- `APIClient.registerWithInvite()`
- `/v1/chat` -- `APIClient.sendMessage()`
- `/v1/mode` -- `APIClient.getCurrentMode()`
- `/v1/mode/switch` -- `APIClient.switchMode()`
- `/v1/mode/available` -- (not explicitly called but available)
- `/v1/memory/staged` -- `APIClient.getPendingMemoryReviews()`
- `/v1/memory/approve/{id}` -- `APIClient.approveMemory()`
- `/v1/memory/reject/{id}` -- `APIClient.rejectMemory()`
- `/v1/memory/search` -- `APIClient.searchMemory()`
- `/v1/sessions` POST -- `APIClient.createSession()`
- `/v1/sessions/{id}/history` -- `APIClient.getSessionHistory()`
- `/v1/orders` POST -- `OrdersService` (via APIClient)
- `/v1/orders` GET -- `OrdersService.fetchOrders()`
- `/v1/orders/{id}` GET -- `OrdersService`
- `/v1/orders/{id}` PATCH -- `OrdersService.updateOrder()`
- `/v1/orders/{id}` DELETE -- `OrdersService.deleteOrder()`
- `/v1/orders/{id}/executions` GET -- `OrdersService.fetchRecentExecutions()`
- `/v1/orders/{id}/execute` POST -- `OrdersService.retryOrder()`
- `/v1/agents` GET -- `APIClient.listAgents()`
- `/v1/agents/{slot}` GET -- `APIClient.getAgent()`
- `/v1/agents/{slot}` PUT -- `APIClient.updateAgent()`
- `/v1/agents/{slot}` DELETE -- `APIClient.deleteAgent()`
- `/v1/agents/{slot}/photo` POST -- `APIClient.uploadAgentPhoto()`
- `/v1/agents/{slot}/photo` GET -- `APIClient.getAgentPhoto()`
- `/v1/agents/{slot}/photo` DELETE -- `APIClient.deleteAgentPhoto()`
- `/v1/agents/{slot}/snapshots` GET -- `APIClient.listAgentSnapshots()`
- `/v1/agents/{slot}/restore` POST -- `APIClient.restoreAgentSnapshot()`
- `/v1/agents/sync` POST -- (agent sync)
- `/v1/user/profile` GET -- `APIClient.getUserProfile()`
- `/v1/user/profile` PATCH -- `APIClient.updateUserProfile()`
- `/v1/user/photo` POST/GET/DELETE -- `APIClient.uploadUserPhoto()` etc.
- `/v1/user/settings` GET/PATCH -- `APIClient.getUserSettings()` etc.
- `/v1/user/push-token` POST/DELETE -- `APIClient.registerPushToken()` etc.
- `/v1/cloud/providers` GET/POST -- `APIClient.listCloudProviders()` etc.
- `/v1/cloud/providers/{name}` DELETE -- `APIClient.removeCloudProvider()`
- `/v1/cloud/providers/{name}/state` PATCH -- `APIClient.updateCloudProviderState()`
- `/v1/cloud/providers/{name}/model` PATCH -- `APIClient.updateCloudProviderModel()`
- `/v1/cloud/usage` GET -- `APIClient.getCloudUsage()`
- `/v1/cloud/providers/{name}/health` POST -- `APIClient.checkCloudProviderHealth()`
- `/v1/voice/quality-check` POST -- `APIClient.voiceQualityCheck()`
- `/v1/voice/journal-analyze` POST -- `APIClient.voiceJournalAnalyze()`
- `/v1/health_data/sync` POST -- `APIClient.syncHealthMetrics()`
- `/v1/health_data/coaching` GET/POST -- `APIClient.getCoachingPreferences()` etc.
- `/v1/wiki/articles` GET -- `APIClient.getWikiArticles()`
- `/v1/wiki/articles/{id}` GET -- `APIClient.getWikiArticle()`
- `/v1/wiki/generate` POST -- `APIClient.generateWikiArticle()`
- `/v1/wiki/generate-all` POST -- `APIClient.generateAllWikiArticles()`
- `/v1/wiki/refresh-static` POST -- `APIClient.refreshWikiStatic()`
- `/v1/user-profile/*` -- `MacUserProfileViewModel` (5 calls)
- `/v1/explorer/resources` GET -- `APIClient.getExplorerResources()` (iOS only)
- `/v1/explorer/resources/{id}` GET -- `APIClient` (in HestiaShared)
- `/v1/explorer/resources/{id}/content` GET -- `APIClient` (in HestiaShared)
- `/v1/explorer/drafts` POST/PATCH/DELETE -- `APIClient` (in HestiaShared, iOS only)
- `/v1/newsfeed/timeline` GET -- `APIClient+Newsfeed` extension
- `/v1/newsfeed/unread-count` GET -- `APIClient+Newsfeed`
- `/v1/newsfeed/items/{id}/read` POST -- `APIClient+Newsfeed`
- `/v1/newsfeed/items/{id}/dismiss` POST -- `APIClient+Newsfeed`
- `/v1/newsfeed/refresh` POST -- `APIClient+Newsfeed`
- `/v1/proactive/briefing` GET -- `APIClient+Newsfeed.getBriefing()`

### Zero Client Callers
(See Category 3 table above -- 35 endpoints)
