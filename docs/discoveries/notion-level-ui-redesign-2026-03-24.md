# Discovery Report: Notion-Level UI Redesign for Hestia
**Date:** 2026-03-24
**Confidence:** High
**Decision:** Proceed with a 4-phase redesign: (1) Shared component library extraction, (2) Investigation Board via second React Flow canvas, (3) 3D Knowledge Atlas refinement, (4) Cross-linking infrastructure. Component library first — it de-risks everything else.

## Hypothesis
Hestia can achieve a cohesive, Notion-quality UI by extracting shared SwiftUI components, building a dual-canvas Research tab (2D React Flow Investigation Board + 3D SceneKit Knowledge Atlas), and establishing cross-linking between Research entities and other modules (Workflows, Chat, Command Center) — without a ground-up rewrite.

## Current State Analysis

### Codebase Inventory
- **18,661 LOC** across macOS Views (10 modules)
- **Largest modules:** Command (2,993), Explorer (2,503), Research (2,160), Workflow (1,858), Wiki (1,761)
- **Existing React Flow canvas:** WorkflowCanvas (6 node types, bridge.ts, dark theme, ~300 LOC React + ~80 LOC Swift bridge)
- **Existing SceneKit 3D graph:** MacSceneKitGraphView (orbit/zoom/pan, per-type shapes, selection ring, hover)
- **Design system:** MacColors (138 LOC, 50+ tokens), MacSpacing (100 LOC), MacTypography, HestiaButtonStyle
- **Backend:** 20 research endpoints, 5 investigate endpoints, entity/fact/principle/community/episode models

### Duplication Identified
Wiki and Workflow views have **identical panel structure** (verified via diff):
```swift
// Both Wiki and Workflow use this exact pattern:
.background(MacColors.panelBackground)
.clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
.overlay { RoundedRectangle(cornerRadius: MacCornerRadius.panel)
    .strokeBorder(MacColors.cardBorder, lineWidth: 1) }
```
Three detail panes (`MacWikiDetailPane`, `MacWorkflowDetailPane`, `NodeDetailPopover`) share structural patterns: toolbar + divider + loading/error/empty states + content. All hand-rolled separately.

---

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** React Flow v12 bridge proven (WKWebView + Swift bidirectional messaging works). SceneKit 3D graph functional with shapes, selection, hover. Design token system mature (MacColors, MacSpacing, MacCornerRadius, MacAnimation). 20 research API endpoints ready. Dark theme already ported to React (theme.ts matches MacColors). | **Weaknesses:** No shared component library — each view hand-rolls panel styling, loading states, error states, sidebar sections. Detail panes duplicated 3x. No cross-linking infrastructure. ResearchView only has 3 modes (graph/principles/memory) — no investigation canvas. React Flow canvas is workflow-specific (node types, bridge messages). |
| **External** | **Opportunities:** React Flow v12 sub-flows + grouping + annotation nodes enable investigation boards natively. SwiftUI ViewModifier extraction can eliminate ~500 LOC of panel boilerplate. Component library positions Hestia for iOS parity. Bidirectional linking (Obsidian/Roam pattern) proven for knowledge tools. | **Threats:** WKWebView memory pressure with two React canvases (no public benchmarks for 500+ nodes). SceneKit is legacy-track (Apple investing in RealityKit). Bridge complexity doubles with second canvas. M1 16GB is the constraint — two WKWebViews + SceneKit + SwiftUI is ambitious. |

---

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | Shared component library (de-duplicates 3+ views, enables all other work). Investigation Board canvas (new capability, high user value). Cross-linking infrastructure (entity -> workflow/chat references). | Panel ViewModifier extraction (saves LOC but low user-visible impact). |
| **Low Priority** | 3D Atlas refinement (already functional, incremental improvement). Bidirectional backlinks UI (high value but dependent on cross-linking infra). | Visual consistency audit (cosmetic, design tokens already exist). React Flow theme unification (current theme.ts already matches). |

---

## Argue (Best Case)

1. **Proven bridge pattern.** The WorkflowCanvas bridge (bridge.ts + WorkflowCanvasWebView.swift) demonstrates React Flow in WKWebView works. The Investigation Board reuses this exact architecture — second canvas project, second WebView wrapper, same message protocol pattern. Effort is additive, not novel.

2. **React Flow v12 is purpose-built for investigation boards.** Sub-flows allow entity grouping. Annotation nodes enable pinning notes/hypotheses. Custom node types (Entity, Fact, Principle, Memory) map directly to Hestia's data model. The feature overview at reactflow.dev shows annotation + toolbar + grouping nodes working together.

3. **Component extraction is high-leverage.** Wiki, Workflow, and Research views share identical panel/sidebar/detail-pane structure. A `HestiaPanel` ViewModifier + `HestiaDetailPane` protocol extracts ~500 LOC of duplication and ensures every future module gets the same polish for free.

4. **Cross-linking has strong UX precedent.** Obsidian, Notion, and Roam prove that bidirectional entity references are the killer feature for knowledge tools. Hestia already has the data model (entities link to facts, facts link to memories, memories link to chat conversations). The infrastructure is a display-layer problem, not a data-layer problem.

5. **Dual 2D/3D is validated.** Gemini's research confirms: Obsidian, InfraNodus, and TheBrain all successfully combine 2D (focused work, local navigation) with 3D (structural discovery, macro analysis). The key insight: each view must serve a distinct cognitive purpose. Investigation Board = focused analysis. Knowledge Atlas = structural exploration.

## Refute (Devil's Advocate)

1. **Memory pressure is the real risk.** Two WKWebViews (Workflow canvas + Investigation Board) + SceneKit 3D + SwiftUI = four rendering pipelines on 16GB M1. No public benchmarks exist for this combination. WKWebView's multi-process architecture means each WebView spawns a separate web process. At 500+ nodes with grouping, this could push memory past 4GB for the web processes alone.

2. **Bridge complexity compounds.** The current bridge handles 6 message types. The Investigation Board needs at minimum: node selection, grouping, annotation CRUD, entity expansion, fact drilling, cross-link navigation, layout save/restore. That's 12+ message types. Two independent bridges doubles the surface area for desync bugs.

3. **SceneKit is on borrowed time.** Apple has not meaningfully updated SceneKit since 2019. RealityKit is the future. Investing in SceneKit 3D refinements risks building on a deprecated framework. The previous second-opinion report (2026-03-23) noted that Gemini recommended pivoting to 2D entirely: "Useful knowledge graphs are 2D, labeled, and highly interactive."

4. **Component library extraction can become over-engineering.** Hestia has ~10 macOS views. The duplication is real but bounded. An SPM-packaged design system with protocol-oriented styles is the "right" answer for a team of 5+ — for a solo developer with ~12 hrs/week, a simpler ViewModifier approach achieves 80% of the value at 20% of the cost.

5. **Cross-linking requires backend work.** While entity relationships exist in the data model, there's no unified "reference" table that tracks which entity appears in which workflow step, which chat message, or which command. Building the display layer without the reference index means the links will be slow (full-text search) or incomplete (heuristic matching).

---

## Third-Party Evidence

### React Flow at Scale
- React Flow stress test example demonstrates hundreds of nodes rendering smoothly in browser
- Performance guide emphasizes: memoize nodeTypes outside component, use `useCallback` for handlers, avoid creating objects in render
- Sub-flows and grouping are first-class features in v12 with `LabeledGroupNode` component
- No documented production deployment in WKWebView — this is a blind spot

### Dual 2D/3D Knowledge Tools
- **Obsidian** 3D Graph Plugin: users use 2D for daily navigation, 3D to find structural gaps — validates dual-mode approach
- **InfraNodus**: 3D specifically for identifying "structural gaps" between idea clusters
- **TheBrain**: 2D/3D hybrid with animated depth transitions — most polished commercial example

### SwiftUI Design Systems
- Production pattern (per Gemini research): SPM Package for distribution + Protocol-Oriented Styles for controls + ViewModifiers for atomic styling
- Kiwi.com's `orbit-swiftui` is an open-source reference implementation
- For Hestia's scale (single developer, 2 targets), ViewModifiers + extensions are sufficient without SPM overhead

---

## Gemini Web-Grounded Validation
**Model:** Gemini 2.5 Pro (thinking + google_web_search)

### Confirmed Findings
- React Flow v12 grouping/sub-flows are production-ready (official examples + docs)
- Dual 2D/3D visualization is validated by Obsidian, InfraNodus, TheBrain
- ViewModifier is the idiomatic SwiftUI pattern for reusable panel styling

### Contradicted Findings
- **"Component library needs SPM package"** — Gemini says the full layered approach (SPM + protocols + modifiers) is ideal, but for a single-developer project, ViewModifiers alone achieve most of the value. SPM adds build complexity without proportional benefit at Hestia's scale.
- **"SceneKit is fine for knowledge graphs"** — Gemini and the prior second-opinion both flag that 2D is functionally superior for data exploration. 3D is better for "wow factor" and structural discovery but not daily use.

### New Evidence
- **WKWebView memory concern confirmed:** No public benchmarks exist for React Flow in WKWebView at 500+ nodes. Gemini explicitly recommends building a prototype to measure with Instruments.
- **Bidirectional linking is the killer UX pattern** for knowledge tools — every successful knowledge management tool (Obsidian, Notion, Roam) uses it as a core navigation mechanism.

### Sources
- [React Flow Performance Guide](https://reactflow.dev/learn/advanced-use/performance)
- [React Flow Sub-Flows](https://reactflow.dev/learn/layouting/sub-flows)
- [React Flow Grouping](https://reactflow.dev/examples/grouping/selection-grouping)
- [React Flow Mind Map Tutorial](https://reactflow.dev/learn/tutorials/mind-map-app-with-react-flow)
- [React Flow Feature Overview](https://reactflow.dev/examples/overview)
- [SwiftUI Design System Guide (DEV Community)](https://dev.to/swift_pal/swiftui-design-system-a-complete-guide-to-building-consistent-ui-components-2025-299k)
- [Reusable SwiftUI Modules with SPM](https://medium.com/@danis.preldzic/building-reusable-swiftui-modules-with-swift-package-manager-a-practical-guide-d3a7cf6e47bd)
- [Notion Sidebar UI Breakdown](https://medium.com/@quickmasum/ui-breakdown-of-notions-sidebar-2121364ec78d)
- [Bidirectional Linking (ClickUp)](https://clickup.com/blog/bidirectional-linking/)

---

## Philosophical Layer

### Ethical Check
Fully ethical. This is a personal productivity tool improving the user's ability to navigate and connect their own knowledge. No privacy, fairness, or consent concerns.

### First Principles Challenge
**Why a second React Flow canvas instead of enhancing the SceneKit graph?**
The SceneKit graph serves structural discovery (3D rotation reveals hidden clusters). But investigation — pinning evidence, grouping related items, annotating hypotheses — is inherently 2D work. You don't rotate a detective's evidence board. These are fundamentally different cognitive tasks requiring different tools. The dual-canvas approach respects this distinction rather than forcing one tool to do both jobs.

**Why not just use a SwiftUI-native canvas instead of React Flow?**
SwiftUI's Canvas view is for drawing, not for interactive node-based UIs. Building drag-and-drop, edge routing, grouping, minimap, and annotation from scratch in SwiftUI would be 10x the effort of using React Flow, which has all of these as built-in features. The WKWebView bridge cost is real but bounded.

### Moonshot: Knowledge Workspace with Live Entity Resolution

**What's the moonshot version?** A single unified canvas where entities from Chat, Workflows, Research, and the Investigation Board are live-linked — editing a fact in the Investigation Board updates the Knowledge Atlas in real-time, and clicking an entity in any view navigates to its canonical profile page with all references, backlinks, and temporal history.

**Technical viability:** Feasible. The entity_registry and fact models already exist. The missing piece is a `reference_index` table (entity_id -> module, item_id, context) and a SwiftUI `EntityProfileView` that aggregates all references. Real-time sync via WebSocket or SSE between the React canvases and SwiftUI views.

**Effort estimate:** 40-50 hours beyond the base redesign. The reference index is ~8h, EntityProfileView is ~12h, live sync is ~15h, and the remaining is wiring/testing.

**Risk assessment:** Worst case if moonshot fails: the reference index still has value as a backend utility for search and linking. No wasted work.

**MVP scope:** Just the reference_index table + EntityProfileView (no live sync). Click entity -> see all places it appears. ~20h.

**Verdict:** SHELVE for now, but build the reference_index in Phase 4 (cross-linking) as the foundation. The moonshot becomes achievable after the base redesign is complete.

### Key Principles Score

| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 5 | No new attack surface. WebView already sandboxed. No new data exposure. |
| Empathy | 5 | Directly serves Andrew's knowledge management needs. Investigation Board is a genuine power-user tool. |
| Simplicity | 3 | Dual canvas + component library + cross-linking is inherently complex. Mitigated by phased delivery and reusing proven patterns. |
| Joy | 5 | This is the kind of tool you want to live in. The 3D Atlas is viscerally satisfying, the Investigation Board is intellectually powerful. |

---

## Recommendation

### Phased Architecture (4 Phases, ~80-100 hours total)

#### Phase 1: Shared Component Library (12-16h)
Extract reusable components from the existing 18,661 LOC view layer. No new features — purely structural.

**Components to extract:**
1. **`HestiaPanelModifier`** — ViewModifier replacing the duplicated `background + clipShape + overlay + strokeBorder` pattern used identically in Wiki, Workflow, Explorer, and Research views. Estimated elimination of 60+ LOC of boilerplate.
2. **`HestiaDetailPane<Content>`** — Generic view with toolbar + divider + loading/error/empty state routing + content slot. Replaces custom implementations in MacWikiDetailPane, MacWorkflowDetailPane, and NodeDetailPopover.
3. **`HestiaContentRow`** — Standardized list row with icon, title, subtitle, trailing accessory. Currently reimplemented differently in WikiSidebarView, WorkflowSidebarView, ExplorerFilesView.
4. **`HestiaSidebarSection`** — Collapsible section header with count badge. Used in at least 4 sidebar views with slight variations.
5. **`HestiaCardGrid`** — Responsive card layout with consistent spacing and border treatment. Used in Command Center, Explorer, Health.

**Location:** `macOS/DesignSystem/Components/` — no SPM package overhead. ViewModifier + View extensions.

**Migration order:** Panel modifier first (lowest risk, highest duplication), then DetailPane, then rows/sections.

#### Phase 2: Investigation Board Canvas (25-35h)

New React Flow canvas for entity investigation, separate from the Workflow canvas.

**Architecture:**
```
HestiaApp/
  InvestigationCanvas/        # New Vite + React project (sibling to WorkflowCanvas)
    src/
      App.tsx                  # React Flow with investigation-specific config
      bridge.ts                # Swift<->JS bridge (same pattern as WorkflowCanvas)
      theme.ts                 # Shared dark theme (import from common or duplicate)
      nodes/
        EntityNode.tsx         # Entity with type badge, connection count
        FactNode.tsx           # Fact with confidence bar, temporal indicator
        PrincipleNode.tsx      # Principle with approval status
        MemoryNode.tsx         # Memory chunk preview
        AnnotationNode.tsx     # Free-text note/hypothesis (React Flow annotation pattern)
        GroupNode.tsx           # Collapsible grouping container (sub-flow pattern)
      components/
        ContextMenu.tsx        # Right-click: expand entity, add note, group, link
        MiniMap.tsx            # Custom minimap with entity-type coloring
```

**Swift side:**
- `InvestigationCanvasWebView.swift` — NSViewRepresentable (copy WorkflowCanvasWebView pattern)
- `InvestigationBoardViewModel.swift` — Manages canvas state, bridges to research API
- Research tab gets a new mode: `.investigation` alongside `.graph`, `.principles`, `.memory`

**Bridge messages (Investigation -> Swift):**
- `entitySelected`, `factSelected`, `principleSelected` (navigate to detail)
- `annotationCreated`, `annotationUpdated`, `annotationDeleted`
- `groupCreated`, `groupUpdated` (entity grouping)
- `crossLinkRequested` (navigate to entity in another module)
- `layoutSaved` (persist canvas positions per board)

**Bridge messages (Swift -> Investigation):**
- `loadBoard` (entities + facts + principles + annotations + groups + positions)
- `highlightEntity` (external navigation into canvas)
- `updateEntityStatus` (reflect backend changes)

**Key decisions:**
- Separate Vite project (not extending WorkflowCanvas) to keep concerns clean
- Shared theme constants via a small shared npm package or duplicated file (prefer duplication at this scale — 32 LOC)
- Canvas positions persisted in SQLite per board (new `investigation_boards` table)

**Performance mitigation:**
- Lazy-load WKWebView: only instantiate when Investigation tab is selected
- Cap initial render at 200 nodes, load more on viewport expansion
- Memoize all node types outside component (per React Flow performance guide)
- Profile with Instruments before committing to 500+ node target

#### Phase 3: 3D Knowledge Atlas Refinement (10-15h)

The SceneKit graph already works. Refinements, not rewrite.

1. **Integrate Phase 1 components** — detail popover uses `HestiaDetailPane`
2. **Degree-centrality node sizing** — bigger = more connected (per second-opinion recommendation)
3. **Color saturation for recency** — newer entities brighter, older faded
4. **Opacity for confidence** — high confidence = solid, low = translucent
5. **Smooth transitions** between graph modes (legacy <-> facts) with animation
6. **Performance:** Cap at 300 SceneKit nodes with level-of-detail clustering (distant communities become single representative nodes)

**No major architectural changes.** SceneKit stays as-is. If Apple deprecates it, the Investigation Board (Phase 2) is the primary research interface and the 3D view becomes optional.

#### Phase 4: Cross-Linking Infrastructure (20-30h)

The foundation for bidirectional references between Research entities and other modules.

**Backend: Reference Index**
```python
# New table: entity_references
# entity_id TEXT, module TEXT, item_id TEXT, context TEXT, created_at TEXT
# Modules: "workflow", "chat", "command", "investigation", "memory"
```

**Indexing pipeline:**
- Workflow steps that reference entities (tool calls, prompt mentions) -> auto-indexed
- Chat messages containing entity names -> indexed via entity_registry fuzzy match
- Investigation Board annotations linking entities -> indexed on save
- Memory chunks already linked to entities via knowledge graph

**Frontend: Cross-Link UI**
- Entity detail views show "Referenced in" section with clickable links
- Links navigate to the specific workflow step, chat message, or investigation board
- Backlink count badges on entities in all views
- `HestiaCrossLinkBadge` component (part of Phase 1 library)

**Navigation protocol:**
```swift
// Universal deep-link for entity navigation
enum HestiaDeepLink {
    case entity(id: String)
    case fact(id: String)
    case workflow(id: String, stepId: String?)
    case chat(conversationId: String, messageId: String?)
    case investigation(boardId: String, entityId: String?)
}
```

Centralized navigation handler in `WorkspaceRootView` that switches tabs and highlights the target item.

---

## Final Critiques

### The Skeptic: "Why won't this work?"
**Challenge:** Two WKWebViews + SceneKit on M1 16GB is too much. You'll hit memory limits and the app will stutter.

**Response:** Valid concern, but mitigated by lazy loading. Only one canvas is ever active at a time (tab-based switching). The Workflow canvas is only loaded when viewing a workflow. The Investigation canvas is only loaded when on that tab. SceneKit is only rendering when the 3D tab is active. Peak memory = one WebView + one SceneKit view, never all three simultaneously. The performance prototype (recommended in Phase 2) will validate this before full investment.

### The Pragmatist: "Is the effort worth it?"
**Challenge:** 80-100 hours is 7-8 weeks at 12 hrs/week. That's nearly two months of Andrew's time. Is a Notion-quality UI worth delaying trading module improvements?

**Response:** The component library (Phase 1, 12-16h) pays for itself immediately in every future module. The Investigation Board (Phase 2) is a genuine new capability that no other personal AI assistant offers. The cross-linking (Phase 4) is what makes Hestia a knowledge tool rather than a chat wrapper. These phases can be interleaved with trading work — they're independent workstreams.

### The Long-Term Thinker: "What happens in 6 months?"
**Challenge:** SceneKit gets deprecated. React Flow has a breaking v13. The WKWebView bridge accumulates tech debt.

**Response:** Phase 1 (component library) and Phase 4 (cross-linking) are pure SwiftUI and backend — zero dependency risk. Phase 2 (Investigation Board) uses React Flow, but the bridge pattern is well-contained (bridge.ts + one Swift wrapper). If React Flow changes, the migration is scoped to one directory. Phase 3 (SceneKit refinement) is explicitly low-investment (10-15h) precisely because of deprecation risk. If SceneKit dies, the Investigation Board is the primary research interface.

---

## Open Questions

1. **Performance prototype results needed.** Before committing to Phase 2, build a 500-node React Flow canvas in WKWebView and profile with Instruments. Go/no-go based on memory < 1GB and frame rate > 30fps.
2. **Investigation Board persistence model.** Should boards be per-entity, per-topic, or freeform? Freeform (user creates boards) is most flexible but needs naming/organization UX.
3. **Cross-link indexing frequency.** Real-time (on every chat message) vs. batch (periodic scan)? Real-time is better UX but adds latency to chat pipeline.
4. **M5 Ultra timeline.** If the hardware upgrade happens mid-build, Phase 3 (SceneKit) constraints relax significantly — could render 1000+ nodes.
5. **Should the Investigation Board support collaboration** (multiple canvases open, shared annotations)? Not for V1, but the persistence model should not preclude it.

---

## Suggested Phase Ordering & Dependencies

```
Phase 1 (Component Library) ─────────────> Phase 3 (3D Atlas uses new components)
        │
        └──> Phase 2 (Investigation Board) ──> Phase 4 (Cross-Linking)
                                                       │
                                                       └──> Moonshot (Live Entity Resolution)
```

Phase 1 is prerequisite for everything. Phases 2 and 3 can run in parallel after Phase 1. Phase 4 depends on Phase 2 (Investigation Board creates references that need indexing).

**Recommended start:** Phase 1 immediately. It's the highest-leverage, lowest-risk work and benefits every future sprint regardless of whether Phases 2-4 proceed.
