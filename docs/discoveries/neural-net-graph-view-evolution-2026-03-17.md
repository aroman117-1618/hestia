# Discovery Report: Neural Net / Graph View Evolution

**Date:** 2026-03-17
**Confidence:** High
**Decision:** Restructure the graph view into a multi-layer, multi-mode visualization that exposes all 7 knowledge graph primitives with visual encoding, adds a time slider for bi-temporal fact exploration, upgrades the legend/filters for the expanded type system, and plans a SceneKit-to-RealityKit migration for the M5 era.

## Hypothesis

*How should Hestia's SceneKit/SwiftUI graph view be restructured to display the full knowledge graph — entities, bi-temporal facts, communities, episodic nodes, principles, and importance scores — in a way that's both useful and performant on Apple Silicon?*

## Current State Analysis

### What Exists Today

**Backend (well-architected, underused):**
- `GraphBuilder` with two modes: `legacy` (memory co-occurrence) and `facts` (entity-relationship)
- 7 `NodeType` enum values: MEMORY, TOPIC, ENTITY, PRINCIPLE, FACT, COMMUNITY, EPISODE
- 9 `EdgeType` enum values: SHARED_TOPIC, SHARED_ENTITY, TOPIC_MEMBERSHIP, ENTITY_MEMBERSHIP, SEMANTIC, PRINCIPLE_SOURCE, RELATIONSHIP, SUPERSEDES, COMMUNITY_MEMBER
- `CATEGORY_COLORS` dict with 17 color mappings (chunk types + entity types + meta types)
- Server-side force-directed layout (120 iterations, MAX_NODES=200, MAX_EDGES=500)
- BFS center-entity filtering for fact graph mode
- Community-based clustering in fact mode, topic-based clustering in legacy mode
- Full bi-temporal fact model (`valid_at`, `invalid_at`, `expired_at`)
- Sprint 16 adds importance scores to `memory.yaml` (composite: recency 0.3, retrieval 0.4, type_bonus 0.3)

**macOS Frontend (partially wired):**
- `MacNeuralNetViewModel` fetches from `/v1/research/graph` (legacy mode only — no `mode=facts` parameter sent)
- `GraphControlPanel` only exposes 3 node types: memory, topic, entity (missing principle, fact, community, episode)
- Legend shows 5 memory chunk types (Preference, Fact, Decision, Action, Research) — does not reflect the expanded node type system
- `NodeDetailPopover` has type-specific sections for topic/entity/principle but no fact/community/episode handling
- `ResearchView` has Graph + Principles tabs — good foundation for expansion
- `DataSource` filter bar (Chat, Email, Notes, Calendar, Reminders, Health) — maps to `sources` param but not wired to actual API call

**iOS Frontend (legacy, disconnected):**
- `NeuralNetViewModel` does client-side graph building from memory search results
- No connection to `/v1/research/graph` API — entirely local computation
- Only displays memory chunk types — no awareness of entities, facts, principles, communities, episodic nodes
- Hardcoded `UIColor` values (no hex from server)

### Gap Analysis

| Backend Capability | macOS Wired? | iOS Wired? |
|---|---|---|
| Legacy graph (memory co-occurrence) | Yes | No (client-side only) |
| Fact graph (entity-relationship) | No | No |
| 7 node types | 3 of 7 | 1 of 7 |
| 9 edge types | Partially (weight-only rendering) | No (weight-only) |
| Bi-temporal facts | No | No |
| Communities | Backend only | No |
| Episodic nodes | Backend only | No |
| Principles in graph | Backend builds, not in filter | No |
| Importance scores | Config exists, not in graph | No |
| Center-entity BFS | Not exposed in UI | No |
| Data source filtering | UI exists, not wired | No |
| Time range filtering | UI exists, not wired | No |

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Backend graph builder is well-structured with 2 modes, 7 node types, 9 edge types. Color mapping, layout, and clustering all server-side. macOS already has ResearchView with graph/principles tabs, control panel, detail popover, hover tooltips. Sprint 16 importance scoring adds meaningful weight signals. | **Weaknesses:** iOS graph view is entirely disconnected from the API — does client-side computation. macOS only sends `mode=legacy`. Filter UI exists but isn't wired to API params. Legend/control panel only show memory chunk types. No temporal exploration UI. SceneKit is soft-deprecated (WWDC 2025). Edge types rendered identically (no visual distinction). |
| **External** | **Opportunities:** Bi-temporal time slider would be unique — "show me what I knew about X in January." Importance-weighted node sizing gives immediate visual signal of what matters. Community clustering with convex hulls creates spatial meaning. Episodic nodes as a "timeline rail" could show conversation history context. M5 Ultra upgrade would support 500+ node graphs comfortably. | **Threats:** SceneKit performance degrades at 750+ nodes (Apple developer forums confirm). RealityKit migration will eventually be required. Over-engineering the visualization could obscure the core utility: "what do I know and how does it connect?" Information overload if all 7 node types visible simultaneously. |

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | **P1:** Wire `mode=facts` to macOS graph + expand filter panel to all 7 node types. **P2:** Update legend to reflect all node/edge types with distinct visual encoding. **P3:** Wire importance scores to node size (replacing confidence). **P4:** Connect iOS to `/v1/research/graph` API (kill client-side computation). | **P5:** Add center-entity BFS to control panel (text field exists, needs param). **P6:** Wire DataSource filter bar to API `sources` param. |
| **Low Priority** | **P7:** Bi-temporal time slider for fact exploration. **P8:** Community convex hull rendering. **P9:** Episodic node timeline rail. **P10:** SceneKit-to-RealityKit migration. | **P11:** Edge animation (flowing particles). **P12:** 3D community shell transparency. |

## Argue (Best Case)

The backend already supports everything needed. The graph builder produces 7 node types, 9 edge types, community clusters, and importance-weighted data. The macOS UI has the shell (control panel, detail popover, hover tooltips, two-mode view). The work is primarily **wiring** — connecting existing backend capabilities to existing frontend patterns.

Concrete evidence:
1. `GraphControlPanel` already has a `nodeTypes` array — just needs 4 more entries (principle, fact, community, episode)
2. `MacNeuralNetViewModel.loadGraph()` already calls `getResearchGraph()` — just needs `mode` parameter
3. `CATEGORY_COLORS` has 17 entries — the color system is ready
4. Backend `GraphNode.to_dict()` already serializes `nodeType`, `color`, `weight` — frontend just needs to use them
5. Importance scoring is in `memory.yaml` — graph builder can use it as `weight` directly

The highest-value feature is **mode switching** (legacy vs. facts). In legacy mode you see "what memories connect to what." In facts mode you see "what entities relate to each other via temporal facts." These are fundamentally different views of the same knowledge and both are valuable.

The time slider for bi-temporal facts is uniquely powerful. No consumer AI assistant offers "show me what I believed about my career in December 2025." This is a differentiator.

## Refute (Devil's Advocate)

**Counter-argument 1: Information overload.** Showing all 7 node types simultaneously creates visual noise. A graph with memory nodes, topic nodes, entity nodes, fact nodes, principle nodes, community nodes, and episodic nodes is overwhelming. The current 3-type view (memory + topic + entity) is already dense.

*Response:* This is valid. The solution is progressive disclosure — default to showing only the most relevant types per mode. Legacy mode: memory + topic + entity (current). Facts mode: entity + fact + community. Principles mode: principle + memory (source chunks). The filter panel controls what's visible, and sensible defaults matter more than showing everything.

**Counter-argument 2: SceneKit is dying.** Apple soft-deprecated SceneKit at WWDC 2025. Investing heavily in SceneKit graph rendering is building on a dead framework.

*Response:* SceneKit continues to work and won't be hard-deprecated. The current graph works. The proposed changes are primarily **data model and API wiring** — not SceneKit rendering changes. The visual encoding (colors, sizes, shapes) works the same whether rendered by SceneKit or RealityKit. A future RealityKit migration would reuse the ViewModel layer entirely and only swap the `MacSceneKitGraphView` component. The abstraction boundary is clean.

**Counter-argument 3: 200 nodes is the hard limit on M1.** The force-directed layout is O(n^2) per iteration. At 200 nodes and 120 iterations, that's 200*199/2*120 = 2.4M distance calculations. Adding more node types doesn't help — it just fragments the budget.

*Response:* This is a real constraint. The answer is mode-based budgets: legacy mode caps at 150 memory + 30 topic + 20 entity = 200. Facts mode caps at 100 entity + 50 community + 50 relationship = 200. The total stays at 200 but the composition changes. On M5 Ultra, raise to 500.

**Counter-argument 4: The time slider requires a new API endpoint.** Current `/v1/research/graph` doesn't accept a `point_in_time` parameter.

*Response:* True, but the backend already has `Fact.is_valid_at(point_in_time)`. Adding a query parameter and filtering in `build_fact_graph()` is ~15 lines of backend code. The heavier lift is the UI.

## Third-Party Evidence

**D3.js Temporal Force-Directed Graphs** (Observable): Demonstrates time slider integration with force layout. Key insight: stabilize node positions across time steps to prevent jarring relayout. For Hestia, this means when sliding through time, nodes should stay in place and edges should fade in/out as facts become valid/invalid.

**IVGraph (2026)**: Achieves 10,000+ node performance with WebGL. Their 86% performance improvement came from GPU-accelerated layout computation — relevant for the future RealityKit migration where Metal compute shaders could do the force simulation.

**Cambridge Intelligence**: Enterprise knowledge graph visualization tool. Their key insight: "predicate-aware styling" — different edge types get different visual treatments (dashed, colored, weighted). Hestia currently renders all edges identically. Adding edge type styling (dashed for SUPERSEDES, thick for RELATIONSHIP, thin for MEMBERSHIP) adds semantic meaning without adding clutter.

**Neo4j Bloom**: Text-based search for graph exploration. Hestia's `focusTopic` field in `GraphControlPanel` is this exact pattern — it just needs to also work with entity names and center the graph on them.

## Recommendation

### Phase 1: Wire the Full Graph (1 sprint, ~6-8 hours)

**Backend changes (minimal):**
1. Add `point_in_time` optional parameter to `/v1/research/graph` endpoint for bi-temporal filtering
2. Wire importance scores from `memory.yaml` config into `GraphBuilder._build_memory_nodes()` as `weight` (replacing `relevance_score`)
3. Add episodic nodes to the fact graph builder (currently missing from `build_fact_graph()`)

**macOS changes (primary focus):**
1. **Graph mode selector**: Add toggle to `GraphControlPanel` or header bar for `legacy` / `facts` mode (sends `mode` param to API)
2. **Expand node type filter**: Add `principle`, `fact`, `community`, `episode` to `GraphControlPanel.nodeTypes` array
3. **Update legend**: Replace hardcoded 5 memory-type legend with dynamic legend built from visible node types. Use `CATEGORY_COLORS` from API response
4. **Edge type styling**: In `MacSceneKitGraphView`, vary edge appearance by `edgeType`:
   - RELATIONSHIP: solid, thick (0.02 radius), colored by confidence
   - SUPERSEDES: dashed/dotted pattern, red tint
   - MEMBERSHIP: thin (0.005), translucent
   - PRINCIPLE_SOURCE: medium, purple tint
   - COMMUNITY_MEMBER: thin, cluster color
5. **Node shape differentiation**: Use different SceneKit geometries per node type:
   - Memory: sphere (current)
   - Topic: octahedron/diamond
   - Entity: cube
   - Principle: star/torus
   - Community: translucent large sphere (enclosing members)
   - Fact: small cylinder/pill
   - Episode: ring/torus
6. **Wire DataSource filter**: Connect existing `DataSource` filter bar to API `sources` parameter
7. **NodeDetailPopover**: Add sections for fact nodes (show `validAt`/`invalidAt`, relation text, source/target entities), community nodes (show members list, summary), episodic nodes (show session summary, linked entities/facts)

**iOS changes (catch-up):**
1. Replace client-side graph building with `/v1/research/graph` API call
2. Adopt server-provided colors, positions, node types
3. Update legend and detail card for expanded types

### Phase 2: Temporal Explorer (1 sprint, ~4-6 hours)

1. **Time slider UI**: Add a `Slider` below the graph (or in control panel) that maps to a date range
2. **API integration**: Send `point_in_time` to `/v1/research/graph?mode=facts`
3. **Smooth transitions**: When sliding, keep node positions stable. Fade edges in/out as facts enter/leave validity. Fade nodes whose only connections are invalid
4. **"Now" indicator**: Show which facts are currently active vs. historical

### Phase 3: RealityKit Migration (deferred to M5 era)

1. Replace `MacSceneKitGraphView` (NSViewRepresentable wrapping SCNView) with RealityKit `RealityView`
2. Port node/edge creation to ECS (Entity Component System)
3. Move force simulation to Metal compute shader for 500+ node support
4. Keep ViewModel layer unchanged — only swap the rendering component

### Node Type Visual Encoding Specification

| Node Type | Shape | Size Source | Color | Icon |
|-----------|-------|------------|-------|------|
| Memory | Sphere | importance score | chunk-type color (7 variants) | brain |
| Topic | Diamond/Octahedron | mention count (normalized) | #FFD60A (yellow) | tag |
| Entity | Cube | fact count (normalized) | entity-type color (6 variants) | person.text.rectangle |
| Principle | Torus | confidence | #BF5AF2 (purple) | lightbulb |
| Community | Large translucent sphere | member count | #FF375F (pink) | person.3 |
| Fact | Pill/Capsule | confidence | #64D2FF (cyan) | link |
| Episode | Ring | recency | #5AC8FA (blue) | clock |

### Edge Type Visual Encoding Specification

| Edge Type | Style | Width | Color |
|-----------|-------|-------|-------|
| RELATIONSHIP | Solid | Thick (weight-scaled) | Source node color, 40% opacity |
| SHARED_TOPIC | Solid | Medium | #FFD60A at 20% |
| SHARED_ENTITY | Solid | Medium | #30D158 at 20% |
| TOPIC_MEMBERSHIP | Dashed | Thin | Topic node color at 15% |
| ENTITY_MEMBERSHIP | Dashed | Thin | Entity node color at 15% |
| PRINCIPLE_SOURCE | Dotted | Medium | #BF5AF2 at 25% |
| SUPERSEDES | Dashed, red | Medium | #FF3B30 at 30% |
| COMMUNITY_MEMBER | Thin solid | Thin | Community color at 15% |
| SEMANTIC | Gradient | Variable | Blended source/target |

### Default Filters by Mode

| Mode | Default Visible Node Types | Rationale |
|------|---------------------------|-----------|
| Legacy | memory, topic, entity | Current behavior, shows conversation knowledge |
| Facts | entity, community | Shows structured knowledge relationships |
| Principles | principle, memory | Shows distilled insights + source evidence |
| Timeline | entity, fact, episode | Shows temporal evolution of knowledge |

## Final Critiques

- **Skeptic:** "Seven node shapes in a 3D scene will look chaotic. Users won't learn the visual language." **Response:** Fair concern. The default filters show only 2-3 types per mode. The shape differentiation is for when a user explicitly enables multiple types. Progressive disclosure prevents overload. The legend is always visible and dynamically reflects what's shown.

- **Pragmatist:** "Is this worth the effort vs. just improving the existing memory-only graph?" **Response:** The memory-only graph is a curiosity — pretty but not actionable. The entity-fact graph with temporal exploration is genuinely useful: "when did I start working on Project X?" "who is connected to this concept?" "what principles has Hestia learned?" These are questions the current graph cannot answer. The backend already supports it; the work is primarily frontend wiring.

- **Long-Term Thinker:** "SceneKit is deprecated. Should we skip straight to RealityKit?" **Response:** No. RealityKit requires iOS 26+ and has a different programming model (ECS vs. scene graph). The ViewModel/API layer we build now transfers cleanly to RealityKit. The only throwaway code is `MacSceneKitGraphView.swift` (one file, ~300 lines). The data architecture, visual encoding decisions, and interaction patterns all survive the migration. Build the right data model now; swap the renderer later.

## Open Questions

1. **Performance testing needed**: How does the M1 handle 200 nodes with mixed shapes (cubes are more expensive than spheres in SceneKit)? Need to profile before finalizing shape choices.
2. **Community rendering**: Large translucent spheres enclosing members is visually appealing but computationally expensive. Alternative: just a cluster-colored outline or background region.
3. **iOS priority**: Is iOS graph evolution worth doing now, or should iOS stay as-is until the M5/RealityKit migration when both platforms get the same renderer?
4. **Episodic node data population**: The `build_fact_graph()` method currently doesn't include episodic nodes. How are episodes being created today? Is there a scheduler or is it on-demand only?
5. **Edge styling in SceneKit**: Dashed/dotted cylinders require custom geometry or texture tricks. May be simpler to use color/opacity differentiation only, saving pattern styles for the RealityKit version.
