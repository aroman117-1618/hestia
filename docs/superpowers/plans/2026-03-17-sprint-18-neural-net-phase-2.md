# Sprint 18: Neural Net Graph Phase 2 — Time Slider, Importance Sizing, Filter Wiring

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the bi-temporal time slider for fact exploration, wire importance-weighted node sizing from Sprint 16 scores, connect the DataSource filter bar to the API `sources` param, and wire the center-entity BFS text field to the API `center_entity` param.

**Architecture:** All four features are primarily frontend wiring — the backend already supports `point_in_time`, `sources`, and `center_entity` query params on `GET /v1/research/graph`. The only backend change is returning `earliest_fact_date` in the graph response metadata so the frontend can bound the time slider. Phase 1 (commit `1e49101`) already landed graph mode selector, expanded node types/shapes, edge styling, and detail sections.

**Tech Stack:** Swift/SwiftUI (macOS + iOS), SceneKit, Python 3.9, FastAPI

**Discovery:** `docs/discoveries/neural-net-graph-view-evolution-2026-03-17.md`

**Python version:** 3.9 — use `Optional[X]` not `X | None`, use `Tuple[X, ...]` not `tuple[X, ...]`, use `List[X]` not `list[X]`.

### Audit Resolutions (pre-identified during research)

1. **Time slider bounding:** The backend `build_fact_graph()` does not currently return `earliest_fact_date` in metadata. Must add `MIN(valid_at)` query to `ResearchDatabase` and include in `GraphResponse.metadata`. Without this, the slider range is guesswork.
2. **DataSource filter bar state not propagated:** `ResearchView.activeFilters` is `@State` local to the view. The `MacNeuralNetViewModel.sourceFilter` property exists but `ResearchView` never writes to it. Must bind the filter bar toggle to the view model.
3. **Center entity param is entity name, not ID:** The backend `_filter_by_center_entity()` uses entity IDs, but the UI text field accepts names. The API route passes `center_entity` directly to `manager.get_fact_graph()`. Must handle name-to-ID resolution — either backend-side (search entities by name) or pass name and let graph builder do fuzzy match. Backend-side is cleaner.
4. **iOS time slider not in scope:** iOS `NeuralNetView` is a compact card — no room for a time slider. Phase 2 is macOS-only. iOS catch-up deferred to RealityKit migration era.
5. **Slider debounce needed:** Dragging the time slider should NOT fire API calls on every value change. Use `onEditingChanged` or `.debounce()` to batch calls.

---

## File Map

### Backend (Python)
| File | Change |
|------|--------|
| `hestia/research/graph_builder.py` | Add `earliest_fact_date` to fact graph metadata |
| `hestia/research/database.py` | Add `get_earliest_fact_date()` query |
| `hestia/research/manager.py` | Thread `earliest_fact_date` through `get_fact_graph()` |
| `hestia/api/routes/research.py` | Resolve `center_entity` name to ID before passing to manager |
| `tests/test_research_graph.py` | Tests for earliest_fact_date, center_entity name resolution |

### macOS Frontend (Swift)
| File | Change |
|------|--------|
| `HestiaApp/macOS/ViewModels/MacNeuralNetViewModel.swift` | Wire `earliestFactDate` from response metadata; debounced time slider reload |
| `HestiaApp/macOS/Views/Research/ResearchView.swift` | Bind `activeFilters` to view model `sourceFilter`; propagate on toggle |
| `HestiaApp/macOS/Views/Research/GraphControlPanel.swift` | Add debounced `onEditingChanged` to time slider; show loading indicator during time travel |
| `HestiaApp/macOS/Models/ResearchModels.swift` | Add `earliestFactDate` to `ResearchGraphResponse.metadata` parsing |

### iOS Frontend (Swift) — minimal
| File | Change |
|------|--------|
| `HestiaApp/Shared/ViewModels/NeuralNetViewModel.swift` | No changes (iOS stays as-is for Phase 2) |

---

## Chunked Tasks

### Task 1: Backend — Earliest Fact Date in Graph Metadata (30 min)

**Goal:** Return `earliest_fact_date` in fact graph response so the time slider knows its lower bound.

- [ ] **Step 1:** In `hestia/research/database.py`, add method `get_earliest_fact_date()`:
  ```python
  async def get_earliest_fact_date(self) -> Optional[datetime]:
      """Get the earliest valid_at date across all facts."""
      cursor = await self._connection.execute(
          "SELECT MIN(valid_at) FROM facts WHERE status = 'active'"
      )
      row = await cursor.fetchone()
      if row and row[0]:
          return datetime.fromisoformat(row[0])
      return None
  ```

- [ ] **Step 2:** In `hestia/research/graph_builder.py` `build_fact_graph()`, after loading entities/facts, call `db.get_earliest_fact_date()` and include in response metadata:
  ```python
  earliest = await db.get_earliest_fact_date()
  # ... in metadata dict:
  "earliest_fact_date": earliest.isoformat() if earliest else None,
  ```

- [ ] **Step 3:** In `hestia/research/manager.py` `get_fact_graph()`, ensure the metadata flows through unchanged (it already does via `response.to_dict()`).

- [ ] **Step 4:** Write test in `tests/test_research_graph.py`:
  - Mock DB with facts having known `valid_at` dates
  - Verify `earliest_fact_date` appears in response metadata
  - Verify it's `None` when no facts exist

### Task 2: Backend — Center Entity Name Resolution (30 min)

**Goal:** Allow the UI to pass an entity name (not ID) in `center_entity` param and have the backend resolve it.

- [ ] **Step 1:** In `hestia/api/routes/research.py`, before calling `manager.get_fact_graph()`, resolve the `center_entity` name to an ID:
  ```python
  resolved_entity_id = None
  if center_entity and mode == "facts":
      manager = await get_research_manager()
      if manager._database:
          cursor = await manager._database._connection.execute(
              "SELECT id FROM entities WHERE canonical_name LIKE ? LIMIT 1",
              (f"%{center_entity.lower()}%",),
          )
          row = await cursor.fetchone()
          if row:
              resolved_entity_id = row[0]
  ```
  Pass `resolved_entity_id` (or `None` if no match) to `manager.get_fact_graph(center_entity=resolved_entity_id)`.

- [ ] **Step 2:** Log a warning if `center_entity` was provided but no match found (helps debug in development).

- [ ] **Step 3:** Write test: search for entity by partial name, verify BFS graph is centered on it.

### Task 3: macOS — Wire DataSource Filter Bar to API (45 min)

**Goal:** Connect the existing `DataSource` filter pills in `ResearchView` to the `MacNeuralNetViewModel.sourceFilter` property, which is already sent to the API.

- [ ] **Step 1:** In `ResearchView.swift`, replace the local `activeFilters` state with a binding to the view model. Change:
  ```swift
  @State private var activeFilters: Set<DataSource> = Set(DataSource.allCases)
  ```
  to derive from `graphViewModel.sourceFilter`. The `sourceFilter` is currently a `String` — change the view model property to `Set<DataSource>` for cleaner binding:

- [ ] **Step 2:** In `MacNeuralNetViewModel.swift`, replace `sourceFilter: String` with:
  ```swift
  @Published var activeDataSources: Set<String> = Set(["chat", "email", "notes", "calendar", "reminders", "health"])
  ```
  In `loadGraph()`, convert to the comma-separated string:
  ```swift
  let sourcesParam: String? = activeDataSources.count == 6 ? nil : activeDataSources.sorted().joined(separator: ",")
  ```

- [ ] **Step 3:** In `ResearchView.filterPill()`, replace `activeFilters.contains(source)` with `graphViewModel.activeDataSources.contains(source.apiValue)` where `apiValue` maps `DataSource` enum cases to API strings:
  ```swift
  extension DataSource {
      var apiValue: String {
          switch self {
          case .chat: return "conversation"
          case .email: return "mail"
          case .notes: return "notes"
          case .calendar: return "calendar"
          case .reminders: return "reminders"
          case .health: return "health"
          }
      }
  }
  ```

- [ ] **Step 4:** Verify: toggle a filter off, click "Apply Filters", confirm the API call includes `sources=conversation,notes,...` with the deselected source missing. Check that the graph reloads with filtered data.

### Task 4: macOS — Wire Time Slider to API with Debounce (1 hour)

**Goal:** Make the time slider in `GraphControlPanel` actually trigger graph reloads with `point_in_time` param, with proper debounce and loading feedback.

- [ ] **Step 1:** In `MacNeuralNetViewModel.swift`, parse `earliest_fact_date` from the graph response metadata:
  ```swift
  private func applyGraphResponse(_ response: ResearchGraphResponse) {
      // ... existing code ...
      // Parse earliest_fact_date from metadata
      if let metaDict = response.metadata,
         case .string(let dateStr) = metaDict["earliest_fact_date"],
         let date = ISO8601DateFormatter().date(from: dateStr) {
          earliestFactDate = date
      }
  }
  ```

- [ ] **Step 2:** Add a debounced time slider reload method:
  ```swift
  private var timeSliderTask: Task<Void, Never>?

  func onTimeSliderChanged() {
      timeSliderTask?.cancel()
      timeSliderTask = Task {
          try? await Task.sleep(nanoseconds: 400_000_000) // 400ms debounce
          guard !Task.isCancelled else { return }
          await loadGraph()
      }
  }
  ```

- [ ] **Step 3:** In `GraphControlPanel.swift`, replace the `onChange(of: viewModel.timeSliderValue)` handler:
  ```swift
  .onChange(of: viewModel.timeSliderValue) { _, newValue in
      viewModel.timeSliderDate = viewModel.dateFromSliderValue(newValue)
      viewModel.onTimeSliderChanged()  // debounced reload
  }
  ```

- [ ] **Step 4:** Add a small loading spinner next to the time slider label when the graph is reloading due to time travel:
  ```swift
  HStack {
      Text(viewModel.timeSliderLabel)
          .font(.system(size: 10))
          .foregroundStyle(MacColors.textSecondary)
      if viewModel.isLoading {
          ProgressView()
              .controlSize(.mini)
      }
  }
  ```

- [ ] **Step 5:** Verify: switch to Facts mode, enable Time Travel, drag the slider. Confirm:
  - Graph reloads after 400ms pause (not on every pixel)
  - Time indicator badge at bottom of graph shows the selected date
  - Nodes/edges update to reflect facts valid at that point in time
  - Slider labeled "Now" at far right, earliest date at far left

### Task 5: macOS — Wire Center Entity BFS (30 min)

**Goal:** Make the "Center Entity" text field in `GraphControlPanel` actually work — typing a name and hitting Enter should center the fact graph on that entity.

- [ ] **Step 1:** Verify `MacNeuralNetViewModel.centerEntity` is already sent to `getResearchGraph()` — it is (line 202 in view model). The `centerEntityParam` is computed from `centerEntity.isEmpty ? nil : centerEntity`.

- [ ] **Step 2:** Verify `APIClient+Research.swift` sends `center_entity` query param — it does (line 37-39).

- [ ] **Step 3:** The wiring is already complete end-to-end: text field binds to `viewModel.centerEntity`, submit calls `viewModel.loadGraph()`, which sends `center_entity` to the API, which passes it to `manager.get_fact_graph()`. The only missing piece is **Task 2** (name-to-ID resolution on the backend).

- [ ] **Step 4:** After Task 2 is done, test: type an entity name in the center entity field, press Enter. Confirm:
  - Graph re-centers with the entity and its BFS neighbors
  - Clearing the field and reloading shows the full graph again

### Task 6: Tests + Verification (30 min)

- [ ] **Step 1:** Run full backend test suite: `python -m pytest tests/ -v --timeout=30`
- [ ] **Step 2:** Build macOS target: `xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS'`
- [ ] **Step 3:** Build iOS target: `xcodebuild -scheme HestiaApp -destination 'platform=iOS Simulator,name=iPhone 16'`
- [ ] **Step 4:** Manual smoke test: start server, open macOS app, navigate to Research view, test each feature:
  - Switch to Facts mode, verify time slider section appears
  - Toggle DataSource filters, verify graph updates
  - Type entity name in center entity field, verify BFS centering
  - Enable time travel, drag slider, verify temporal filtering
- [ ] **Step 5:** Verify iOS app still compiles and shows the Neural Net card without regressions

---

## Estimated Effort

| Task | Time |
|------|------|
| Task 1: Earliest fact date metadata | 30 min |
| Task 2: Center entity name resolution | 30 min |
| Task 3: DataSource filter wiring | 45 min |
| Task 4: Time slider debounce + wiring | 1 hour |
| Task 5: Center entity BFS (mostly done) | 30 min |
| Task 6: Tests + verification | 30 min |
| **Total** | **~4 hours** |

## Risk Assessment

- **Low risk:** All backend params already exist — this is wiring, not new architecture.
- **Medium risk:** Time slider debounce timing. If 400ms feels sluggish, reduce to 250ms. If API is slow, consider showing stale graph with a loading overlay rather than clearing.
- **Low risk:** Center entity fuzzy match could return wrong entity. Mitigation: use `canonical_name LIKE %term%` which is exact substring match on the deduplicated name. If ambiguous, return the first match (most recently updated).
