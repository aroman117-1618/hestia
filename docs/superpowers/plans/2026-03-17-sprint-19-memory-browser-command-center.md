# Sprint 19: Memory Browser + Command Center Learning Metrics

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a macOS Memory Browser for paginated inspection of memory chunks sorted by importance, and add learning metrics (correction stats, distillation history, MetaMonitor positive ratio, trigger alerts) to the Command Center dashboard.

**Architecture:** The Memory Browser is a new macOS view accessible from the sidebar (or as a tab within an existing view). It requires a new backend endpoint for paginated chunk listing with sort/filter, plus a new macOS ViewModel and View. The Command Center additions wire existing `/v1/learning/*` endpoints to new stat cards and a small metrics panel in `CommandView.swift`.

**Tech Stack:** Swift/SwiftUI (macOS), Python 3.9, FastAPI, SQLite, pytest

**Python version:** 3.9 — use `Optional[X]` not `X | None`, use `Tuple[X, ...]` not `tuple[X, ...]`, use `List[X]` not `list[X]`.

### Audit Resolutions (pre-identified during research)

1. **No paginated chunk list endpoint exists:** The memory API has `/v1/memory/search` (semantic search) and `/v1/memory/staged` (pending review only). Neither returns all chunks sorted by importance with pagination. Must add `GET /v1/memory/chunks` with `sort_by`, `chunk_type`, `limit`, `offset` params.
2. **MemoryDatabase has no list-all-chunks method:** Only `get_chunk(id)` exists. Must add `list_chunks(limit, offset, sort_by, chunk_type_filter, status_filter)` to `hestia/memory/database.py`.
3. **Importance score is stored in `metadata.confidence`:** Sprint 16 repurposed the `confidence` field as importance score. The SQL column is `metadata_confidence` in the chunks table. Sorting by importance means `ORDER BY metadata_confidence DESC`.
4. **Learning routes missing auth dependency:** The current `learning.py` routes take `user_id` as a query param but don't use `Depends(get_device_token)`. Sprint 17 may fix this, but if not, Sprint 19 must add auth to be consistent.
5. **Command Center layout:** `CommandView.swift` uses `ScrollView > VStack` with `HeroSection`, `StatCardsRow`, calendar/orders HStack, and `ActivityFeed`. Learning metrics should go between `StatCardsRow` and the calendar/orders section — a new `LearningMetricsPanel` component.
6. **macOS sidebar navigation:** The Memory Browser needs a sidebar entry. Check `AppState` or sidebar enum for where to add it. May need a new case in the navigation enum.

---

## File Map

### Backend (Python)
| File | Change |
|------|--------|
| `hestia/memory/database.py` | Add `list_chunks()` method with pagination, sort, filter |
| `hestia/api/routes/memory.py` | Add `GET /v1/memory/chunks` endpoint |
| `hestia/api/schemas/__init__.py` | Add `MemoryChunkListResponse` schema (or inline) |
| `hestia/api/routes/learning.py` | Add `Depends(get_device_token)` to all routes (if Sprint 17 hasn't) |
| `tests/test_memory_browser.py` | Tests for list_chunks pagination, sorting, filtering |

### macOS Frontend (Swift) — Memory Browser
| File | Change | New? |
|------|--------|------|
| `HestiaApp/macOS/ViewModels/MacMemoryBrowserViewModel.swift` | ViewModel for paginated memory list | NEW |
| `HestiaApp/macOS/Views/Memory/MemoryBrowserView.swift` | Main memory browser view | NEW |
| `HestiaApp/macOS/Views/Memory/MemoryChunkRow.swift` | Row component for chunk list | NEW |
| `HestiaApp/macOS/Services/APIClient+Memory.swift` | API client extension for memory endpoints | NEW |
| `HestiaApp/macOS/Models/MemoryBrowserModels.swift` | Response types for chunk list | NEW |

### macOS Frontend (Swift) — Command Center Learning Metrics
| File | Change | New? |
|------|--------|------|
| `HestiaApp/macOS/ViewModels/MacCommandCenterViewModel.swift` | Add learning metrics loading | EDIT |
| `HestiaApp/macOS/Views/Command/LearningMetricsPanel.swift` | Learning metrics card panel | NEW |
| `HestiaApp/macOS/Views/Command/CommandView.swift` | Insert `LearningMetricsPanel` | EDIT |
| `HestiaApp/macOS/Services/APIClient+Learning.swift` | API client extension for learning endpoints | NEW |
| `HestiaApp/macOS/Models/LearningModels.swift` | Response types for learning data | NEW |

### Navigation
| File | Change |
|------|--------|
| Sidebar/navigation enum (location TBD) | Add Memory Browser sidebar entry |
| `HestiaApp/macOS/project.yml` | Add new files to macOS target |

---

## Chunked Tasks

### Task 1: Backend — Paginated Chunk List Endpoint (1 hour)

**Goal:** Add `GET /v1/memory/chunks` that returns memory chunks with pagination, sorting, and filtering.

- [ ] **Step 1:** In `hestia/memory/database.py`, add `list_chunks()` method:
  ```python
  async def list_chunks(
      self,
      limit: int = 50,
      offset: int = 0,
      sort_by: str = "importance",  # "importance", "created", "updated"
      sort_order: str = "desc",
      chunk_type: Optional[str] = None,
      status: Optional[str] = None,
      source: Optional[str] = None,
  ) -> Tuple[List[ConversationChunk], int]:
      """List chunks with pagination and filtering.

      Returns (chunks, total_count) tuple.
      """
      where_clauses = []
      params = []

      if chunk_type:
          where_clauses.append("chunk_type = ?")
          params.append(chunk_type)
      if status:
          where_clauses.append("status = ?")
          params.append(status)
      if source:
          where_clauses.append("metadata_source = ?")
          params.append(source)

      where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

      sort_column = {
          "importance": "metadata_confidence",
          "created": "timestamp",
          "updated": "updated_at",
      }.get(sort_by, "metadata_confidence")

      order = "DESC" if sort_order == "desc" else "ASC"

      # Count
      count_cursor = await self._connection.execute(
          f"SELECT COUNT(*) FROM chunks WHERE {where_sql}", params
      )
      total = (await count_cursor.fetchone())[0]

      # Fetch page
      cursor = await self._connection.execute(
          f"SELECT * FROM chunks WHERE {where_sql} ORDER BY {sort_column} {order} LIMIT ? OFFSET ?",
          params + [limit, offset],
      )
      rows = await cursor.fetchall()
      chunks = [self._row_to_chunk(row) for row in rows]

      return chunks, total
  ```

- [ ] **Step 2:** In `hestia/api/routes/memory.py`, add the endpoint:
  ```python
  @router.get("/chunks")
  async def list_memory_chunks(
      limit: int = Query(default=50, ge=1, le=200),
      offset: int = Query(default=0, ge=0),
      sort_by: str = Query(default="importance", description="importance, created, or updated"),
      sort_order: str = Query(default="desc", description="asc or desc"),
      chunk_type: Optional[str] = Query(default=None),
      status: Optional[str] = Query(default=None, description="active, archived, superseded"),
      source: Optional[str] = Query(default=None, description="conversation, mail, calendar, etc."),
      device_id: str = Depends(get_device_token),
  ):
  ```
  Response shape:
  ```json
  {
      "chunks": [
          {
              "id": "...",
              "content": "...",
              "chunk_type": "preference",
              "importance": 0.85,
              "status": "active",
              "source": "conversation",
              "topics": ["python", "hestia"],
              "entities": ["andrew"],
              "created_at": "2026-03-15T...",
              "updated_at": "2026-03-15T..."
          }
      ],
      "total": 342,
      "limit": 50,
      "offset": 0
  }
  ```

- [ ] **Step 3:** Verify `_row_to_chunk()` exists in `MemoryDatabase` and handles all columns. If the method is named differently, adapt accordingly.

- [ ] **Step 4:** Write tests in `tests/test_memory_browser.py`:
  - Test default sort (importance desc)
  - Test pagination (offset/limit)
  - Test chunk_type filter
  - Test status filter
  - Test empty results

### Task 2: macOS — Memory Browser ViewModel (45 min)

**Goal:** Build the ViewModel that fetches and manages paginated memory chunks.

- [ ] **Step 1:** Create `HestiaApp/macOS/Services/APIClient+Memory.swift`:
  ```swift
  extension APIClient {
      func listMemoryChunks(
          limit: Int = 50,
          offset: Int = 0,
          sortBy: String = "importance",
          sortOrder: String = "desc",
          chunkType: String? = nil,
          status: String? = nil,
          source: String? = nil
      ) async throws -> MemoryChunkListResponse {
          var path = "../v1/memory/chunks?limit=\(limit)&offset=\(offset)&sort_by=\(sortBy)&sort_order=\(sortOrder)"
          if let ct = chunkType { path += "&chunk_type=\(ct)" }
          if let s = status { path += "&status=\(s)" }
          if let src = source { path += "&source=\(src)" }
          return try await get(path)
      }
  }
  ```

- [ ] **Step 2:** Create `HestiaApp/macOS/Models/MemoryBrowserModels.swift`:
  ```swift
  struct MemoryChunkListResponse: Codable {
      let chunks: [MemoryChunkItem]
      let total: Int
      let limit: Int
      let offset: Int
  }

  struct MemoryChunkItem: Codable, Identifiable {
      let id: String
      let content: String
      let chunkType: String
      let importance: Double
      let status: String
      let source: String?
      let topics: [String]
      let entities: [String]
      let createdAt: String
      let updatedAt: String?
  }
  ```

- [ ] **Step 3:** Create `HestiaApp/macOS/ViewModels/MacMemoryBrowserViewModel.swift`:
  ```swift
  @MainActor
  class MacMemoryBrowserViewModel: ObservableObject {
      @Published var chunks: [MemoryChunkItem] = []
      @Published var totalCount: Int = 0
      @Published var isLoading: Bool = false
      @Published var currentPage: Int = 0
      @Published var sortBy: String = "importance"  // "importance", "created", "updated"
      @Published var sortOrder: String = "desc"
      @Published var chunkTypeFilter: String? = nil
      @Published var statusFilter: String? = nil     // "active", "archived"
      @Published var sourceFilter: String? = nil
      @Published var searchText: String = ""

      let pageSize: Int = 50

      var totalPages: Int { max(1, (totalCount + pageSize - 1) / pageSize) }
      var hasNextPage: Bool { currentPage < totalPages - 1 }
      var hasPreviousPage: Bool { currentPage > 0 }

      func loadChunks() async { ... }
      func nextPage() async { ... }
      func previousPage() async { ... }
      func applyFilters() async { ... }
  }
  ```

- [ ] **Step 4:** Implement `loadChunks()`:
  ```swift
  func loadChunks() async {
      isLoading = true
      defer { isLoading = false }
      do {
          let response = try await APIClient.shared.listMemoryChunks(
              limit: pageSize,
              offset: currentPage * pageSize,
              sortBy: sortBy,
              sortOrder: sortOrder,
              chunkType: chunkTypeFilter,
              status: statusFilter,
              source: sourceFilter
          )
          chunks = response.chunks
          totalCount = response.total
      } catch {
          #if DEBUG
          print("[MacMemoryBrowserVM] Load failed: \(error)")
          #endif
      }
  }
  ```

### Task 3: macOS — Memory Browser View (1.5 hours)

**Goal:** Build the Memory Browser UI — a paginated list with type badges, importance bars, and filter controls.

- [ ] **Step 1:** Create `HestiaApp/macOS/Views/Memory/MemoryBrowserView.swift`:
  ```swift
  struct MemoryBrowserView: View {
      @StateObject private var viewModel = MacMemoryBrowserViewModel()

      var body: some View {
          VStack(spacing: 0) {
              headerBar
              filterBar
              chunkList
              paginationBar
          }
          .background(MacColors.windowBackground)
          .task { await viewModel.loadChunks() }
      }
  }
  ```

- [ ] **Step 2:** Build the header bar with title "Memory Browser" and sort picker:
  - Sort by: Importance / Created / Updated (segmented picker or Menu)
  - Sort order: toggle button (asc/desc arrow)

- [ ] **Step 3:** Build the filter bar with horizontal pills:
  - Chunk type: All / Preference / Fact / Decision / Action / Research / System
  - Status: Active / Archived / All
  - Source: Chat / Email / Notes / Calendar / Reminders / Health (reuse `DataSource` enum style)

- [ ] **Step 4:** Create `HestiaApp/macOS/Views/Memory/MemoryChunkRow.swift` — each row shows:
  - **Left:** Type badge (colored pill with chunk type icon + label)
  - **Center:** Content preview (2 lines, truncated), topics as small tag pills below
  - **Right column:** Importance bar (horizontal, colored by score: green >0.7, amber 0.4-0.7, red <0.4), percentage label, relative timestamp

  ```swift
  struct MemoryChunkRow: View {
      let chunk: MemoryChunkItem

      private var importanceColor: Color {
          if chunk.importance > 0.7 { return MacColors.healthGreen }
          if chunk.importance > 0.4 { return MacColors.amberAccent }
          return MacColors.healthRed
      }

      var body: some View {
          HStack(spacing: MacSpacing.md) {
              // Type badge
              chunkTypeBadge
              // Content
              VStack(alignment: .leading, spacing: MacSpacing.xs) {
                  Text(chunk.content)
                      .font(.system(size: 12))
                      .foregroundStyle(MacColors.textPrimary)
                      .lineLimit(2)
                  topicPills
              }
              .frame(maxWidth: .infinity, alignment: .leading)
              // Importance
              importanceIndicator
          }
          .padding(MacSpacing.md)
          .background(MacColors.cardGradient)
          .overlay(RoundedRectangle(cornerRadius: MacCornerRadius.panel).strokeBorder(MacColors.cardBorder, lineWidth: 1))
          .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
      }
  }
  ```

- [ ] **Step 5:** Build the pagination bar at the bottom:
  - "Page X of Y" label
  - Previous / Next buttons (disabled at bounds)
  - Total count label: "342 chunks"

- [ ] **Step 6:** Add archive/restore actions (stretch goal — can be deferred):
  - Swipe action or context menu on each row
  - Archive: `PATCH /v1/memory/{id}/sensitive` (repurpose, or add new status endpoint)
  - This may require a new `POST /v1/memory/{chunk_id}/archive` endpoint

### Task 4: macOS — Sidebar Navigation Entry (30 min)

**Goal:** Add Memory Browser to the macOS sidebar so users can navigate to it.

- [ ] **Step 1:** Find the sidebar navigation enum/state. Search for the existing sidebar cases (Command, Explorer, Health, Profile, Wiki, Resources, Research/Chat).

- [ ] **Step 2:** Add a `.memory` case to the navigation enum with icon `brain` and label "Memory".

- [ ] **Step 3:** In the sidebar view, add the Memory entry (position: after Research, before Profile or at a logical spot).

- [ ] **Step 4:** In the main content router (the `switch` that shows `CommandView`, `ResearchView`, etc.), add:
  ```swift
  case .memory:
      MemoryBrowserView()
  ```

- [ ] **Step 5:** Add all new files to `project.yml` under the macOS target sources.

### Task 5: macOS — Learning Metrics Models + API Client (30 min)

**Goal:** Create Swift models and API client for the `/v1/learning/*` endpoints.

- [ ] **Step 1:** Create `HestiaApp/macOS/Models/LearningModels.swift`:
  ```swift
  struct MetaMonitorReportResponse: Codable {
      let data: MetaMonitorReport?
  }

  struct MetaMonitorReport: Codable {
      let id: String
      let userId: String
      let timestamp: String
      let status: String
      let totalOutcomes: Int
      let positiveRatio: Double?
      let confusionSessions: [String]
      let avgLatencyMs: Double?
      let latencyTrend: String?
      let sampleSizeSufficient: Bool
  }

  struct MemoryHealthResponse: Codable {
      let data: MemoryHealthSnapshot?
  }

  struct MemoryHealthSnapshot: Codable {
      let id: String
      let userId: String
      let timestamp: String
      let chunkCount: Int
      let chunkCountBySource: [String: Int]
      let redundancyEstimatePct: Double
      let entityCount: Int
      let factCount: Int
      let staleEntityCount: Int
      let contradictionCount: Int
      let communityCount: Int
  }

  struct TriggerAlertsResponse: Codable {
      let data: [TriggerAlert]
  }

  struct TriggerAlert: Codable, Identifiable {
      let id: String
      let userId: String
      let triggerName: String
      let currentValue: Double
      let thresholdValue: Double
      let direction: String
      let message: String
      let timestamp: String
      let acknowledged: Bool
  }
  ```

- [ ] **Step 2:** Create `HestiaApp/macOS/Services/APIClient+Learning.swift`:
  ```swift
  extension APIClient {
      func getLatestMetaMonitorReport(userId: String = "default") async throws -> MetaMonitorReportResponse {
          return try await get("../v1/learning/report?user_id=\(userId)")
      }

      func getMemoryHealth(userId: String = "default") async throws -> MemoryHealthResponse {
          return try await get("../v1/learning/memory-health?user_id=\(userId)")
      }

      func getTriggerAlerts(userId: String = "default") async throws -> TriggerAlertsResponse {
          return try await get("../v1/learning/alerts?user_id=\(userId)")
      }

      func acknowledgeAlert(alertId: String, userId: String = "default") async throws -> [String: String] {
          return try await post("../v1/learning/alerts/\(alertId)/acknowledge?user_id=\(userId)", body: EmptyBody())
      }
  }
  ```

### Task 6: macOS — Command Center Learning Metrics Panel (1 hour)

**Goal:** Add a learning metrics panel to the Command Center showing MetaMonitor positive ratio, memory health stats, and trigger alert badges.

- [ ] **Step 1:** In `MacCommandCenterViewModel.swift`, add learning state:
  ```swift
  @Published var metaMonitorReport: MetaMonitorReport?
  @Published var memoryHealth: MemoryHealthSnapshot?
  @Published var triggerAlerts: [TriggerAlert] = []
  ```

- [ ] **Step 2:** Add loading methods:
  ```swift
  private func loadLearningMetrics() async {
      do {
          let reportResponse = try await APIClient.shared.getLatestMetaMonitorReport()
          metaMonitorReport = reportResponse.data
      } catch {
          #if DEBUG
          print("[MacCommandCenterVM] MetaMonitor load failed: \(error)")
          #endif
      }

      do {
          let healthResponse = try await APIClient.shared.getMemoryHealth()
          memoryHealth = healthResponse.data
      } catch {
          #if DEBUG
          print("[MacCommandCenterVM] Memory health load failed: \(error)")
          #endif
      }

      do {
          let alertsResponse = try await APIClient.shared.getTriggerAlerts()
          triggerAlerts = alertsResponse.data
      } catch {
          #if DEBUG
          print("[MacCommandCenterVM] Alerts load failed: \(error)")
          #endif
      }
  }
  ```

- [ ] **Step 3:** Add `loadLearningMetrics()` to the `loadAllData()` gather:
  ```swift
  async let learningTask: () = loadLearningMetrics()
  _ = await (healthTask, memoryTask, ordersTask, calendarTask, newsfeedTask, learningTask)
  ```

- [ ] **Step 4:** Add derived properties:
  ```swift
  var positiveRatioPercent: Int {
      guard let ratio = metaMonitorReport?.positiveRatio else { return 0 }
      return Int(ratio * 100)
  }
  var unacknowledgedAlertCount: Int { triggerAlerts.filter { !$0.acknowledged }.count }
  var memoryChunkCount: Int { memoryHealth?.chunkCount ?? 0 }
  var memoryRedundancyPct: Double { memoryHealth?.redundancyEstimatePct ?? 0.0 }
  ```

- [ ] **Step 5:** Create `HestiaApp/macOS/Views/Command/LearningMetricsPanel.swift`:
  ```swift
  struct LearningMetricsPanel: View {
      @ObservedObject var viewModel: MacCommandCenterViewModel

      var body: some View {
          VStack(alignment: .leading, spacing: MacSpacing.md) {
              // Section header
              HStack {
                  Image(systemName: "chart.line.uptrend.xyaxis")
                      .foregroundStyle(MacColors.amberAccent)
                  Text("Learning Metrics")
                      .font(.system(size: 13, weight: .semibold))
                      .foregroundStyle(MacColors.textPrimary)
                  Spacer()
                  if viewModel.unacknowledgedAlertCount > 0 {
                      alertBadge
                  }
              }

              // Metrics grid: 2x2
              LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: MacSpacing.md) {
                  metricCard(
                      icon: "face.smiling",
                      label: "Positive Ratio",
                      value: "\(viewModel.positiveRatioPercent)%",
                      color: viewModel.positiveRatioPercent > 70 ? MacColors.healthGreen : MacColors.amberAccent
                  )
                  metricCard(
                      icon: "brain",
                      label: "Memory Chunks",
                      value: "\(viewModel.memoryChunkCount)",
                      color: MacColors.textSecondary
                  )
                  metricCard(
                      icon: "doc.on.doc",
                      label: "Redundancy",
                      value: String(format: "%.1f%%", viewModel.memoryRedundancyPct),
                      color: viewModel.memoryRedundancyPct > 20 ? MacColors.healthRed : MacColors.healthGreen
                  )
                  metricCard(
                      icon: "bolt.trianglebadge.exclamationmark",
                      label: "Alerts",
                      value: "\(viewModel.unacknowledgedAlertCount)",
                      color: viewModel.unacknowledgedAlertCount > 0 ? MacColors.healthRed : MacColors.healthGreen
                  )
              }
          }
          .padding(MacSpacing.lg)
          .background(MacColors.cardGradient)
          .overlay(RoundedRectangle(cornerRadius: MacCornerRadius.panel).strokeBorder(MacColors.cardBorder, lineWidth: 1))
          .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
      }
  }
  ```

- [ ] **Step 6:** Build the individual `metricCard()` helper (icon, label, value, colored accent bar).

- [ ] **Step 7:** Build the `alertBadge` — red circle with count, tappable to show alert list popover.

- [ ] **Step 8:** In `CommandView.swift`, insert `LearningMetricsPanel` between `StatCardsRow` and the calendar/orders section:
  ```swift
  StatCardsRow(viewModel: viewModel)

  // Learning metrics
  LearningMetricsPanel(viewModel: viewModel)

  // Calendar + Orders
  if layoutMode.isCompact { ... }
  ```

### Task 7: Tests + Verification (30 min)

- [ ] **Step 1:** Run backend tests: `python -m pytest tests/ -v --timeout=30`
- [ ] **Step 2:** Run new memory browser tests: `python -m pytest tests/test_memory_browser.py -v`
- [ ] **Step 3:** Build macOS target: `xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS'`
- [ ] **Step 4:** Build iOS target: `xcodebuild -scheme HestiaApp -destination 'platform=iOS Simulator,name=iPhone 16'`
- [ ] **Step 5:** Manual smoke test:
  - Navigate to Memory Browser via sidebar — verify chunks load sorted by importance
  - Test pagination (next/prev page)
  - Test filters (chunk type, status)
  - Open Command Center — verify Learning Metrics panel appears
  - Verify positive ratio gauge shows data (or graceful "No data" if no reports yet)
  - Verify trigger alert badge shows count (or hidden if zero)

---

## Estimated Effort

| Task | Time |
|------|------|
| Task 1: Backend paginated chunk list | 1 hour |
| Task 2: Memory Browser ViewModel | 45 min |
| Task 3: Memory Browser View | 1.5 hours |
| Task 4: Sidebar navigation | 30 min |
| Task 5: Learning models + API client | 30 min |
| Task 6: Command Center learning panel | 1 hour |
| Task 7: Tests + verification | 30 min |
| **Total** | **~6 hours** |

## Risk Assessment

- **Medium risk:** `_row_to_chunk()` in `MemoryDatabase` may not exist as a public method — the database may use a different deserialization pattern. Must verify the actual column names and row-to-model conversion before implementing `list_chunks()`.
- **Low risk:** Learning endpoints may return `null` data if no MetaMonitor/MemoryHealth reports have been generated yet. All UI must handle the `nil` case gracefully (show "No data yet" instead of crashing).
- **Low risk:** The `user_id=default` pattern in learning routes may not match the actual user ID used elsewhere. If Sprint 17 changes this to auth-based, update the API client accordingly.
- **Medium risk:** Adding a sidebar entry requires understanding the exact navigation pattern. If the sidebar uses an enum, it's straightforward. If it uses a more complex routing system, may need more investigation.
