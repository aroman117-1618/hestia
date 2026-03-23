# Second Opinion: Research Knowledge Graph Visualization Redesign
**Date:** 2026-03-23
**Models:** Claude Opus 4.6 (internal) + Gemini 2.5 Pro (external)
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary
Redesign the 3D Research graph to show only Principles and Facts as nodes, with hybrid edges (topic-based for principle connections, entity-based for fact connections), community-based spatial clustering, and topics/entities as detail-on-click metadata in a list panel.

## Critical Finding: Data Model Blocker

**Facts don't have topic tags.** The `Fact` dataclass has: `source_entity_id`, `relation`, `target_entity_id`, `fact_text`, `confidence`, `durability_score`, `temporal_type`, `source_category`. No `topics` field exists. The proposed Principle-to-Fact edge via "shared topics" is impossible without extending the Fact model.

**Resolution options:**
1. Add `topics: List[str]` to the Fact model (requires schema migration + re-extraction)
2. Connect Principle-to-Fact via shared entities instead (Principles have `entities: List[str]`, Facts have `source_entity_id`/`target_entity_id`)
3. Use the source memory chunk as a bridge (both Principles and Facts reference source chunks that have topics)

**Recommendation:** Option 2 — shared entities. It's structurally sound and requires no schema change. The hybrid model becomes:

| Connection | Edge Source |
|-----------|-----------|
| Principle <-> Principle | Shared topics |
| Principle <-> Fact | Shared entities (principle.entities vs fact.source/target_entity) |
| Fact <-> Fact | Shared entities (existing relationship data) |

---

## Scale Assessment

| Scale | Works? | Notes |
|-------|--------|-------|
| Single user | Yes | All data is user-scoped |
| Family | Yes | No changes needed — separate DBs |
| Community | N/A | Not relevant for knowledge graph |

## Front-Line Engineering Review

- **Feasibility:** HIGH — graph builder, API routes, and Swift frontend all exist. This is a refactor, not a greenfield build.
- **Hidden prerequisites:**
  - Fact model may need `topics` field if Option 2 isn't adopted
  - Community detection needs to be triggered (pipeline exists but not auto-running)
  - Mac Mini has 0 facts/entities/communities — need to bootstrap the pipeline
- **Testing gaps:** No integration test for the full pipeline (memory -> principle -> fact -> community -> graph). Unit tests cover individual components.
- **Effort estimate:** ~8-12 hours (backend graph builder refactor + frontend default changes + pipeline trigger)

## Architecture Review

- **Fit:** Clean — uses existing manager pattern, GraphNode/GraphEdge models, and API response format
- **Data model:** Sound for Principles. Facts need entity-bridge for cross-type edges (see critical finding above)
- **Integration risk:** LOW — the facts-mode graph builder already builds entity nodes, relationship edges, and community clusters. The main work is adding principle nodes to the facts-mode builder and wiring the hybrid edge logic.

## Product Review

- **User value:** HIGH — transforms a broken, useless view into a meaningful knowledge map
- **Cold-start problem:** CRITICAL — new users see empty graph until pipeline runs. Need empty state UX + guided onboarding ("Chat more to build your knowledge graph")
- **Opportunity cost:** This is foundational — the Research tab is a core feature that's currently non-functional

## UX Review

### Node Sizing Recommendation (Both models agree)

**Use Degree Centrality** (number of connections). It's:
- Intuitive: bigger = more connected = more important
- Easy to calculate: `len(edges_touching_this_node)`
- Structurally meaningful: highlights hub nodes

**Use OTHER visual channels for other properties:**

| Property | Visual Channel | Rationale |
|----------|---------------|-----------|
| Degree centrality | **Node size** | Structural importance |
| Recency/age | **Color saturation** | Newer = brighter, older = faded |
| Confidence | **Opacity** | Higher confidence = more solid |
| Durability (DIKW) | **Shape** (already implemented) | Distinguishes ephemeral from atemporal |

**Avoid** using size for confidence or age — these aren't structural properties.

### 3D vs 2D: Both Reviewers Flag This

**Gemini's position:** "Pivot to 2D. Useful knowledge graphs are 2D, labeled, and highly interactive. 3D is almost exclusively used for artistic presentation, not functional data exploration."

**Critic's position:** "The existing renderer has no text labels on nodes. In a Principles + Facts graph, the node content IS the signal — a torus floating in 3D space communicates nothing."

**Best-in-class references:**
- **Obsidian/Roam/Logseq:** 2D, labeled, interactive. Graph is emergent/secondary view.
- **Neo4j Bloom / Kumu.io:** Gold standard for graph analysis. 2D, excellent labeling, filtering, detail-on-demand.
- **Apple Freeform:** Fluid 2D canvas, simple interaction model.

**Resolution:** This is a real concern but NOT a blocker for this sprint. The 3D SceneKit graph is already built and works. Adding text labels in SceneKit is possible via `SCNText` with `SCNBillboardConstraint`. The 2D pivot can be a future sprint if 3D proves limiting. **Recommend: keep 3D, add billboard text labels to nodes.**

### Wiring Verification
- Node detail popover (`NodeDetailPopover.swift`) already renders per-type metadata. Adding Topics/Entities list is straightforward.
- Graph mode switching exists. Changing the default from `.legacy` to `.facts` is a one-line change.
- The selected node detail panel already shows connected nodes via `connectedNodes(for:)`.

## Infrastructure Review

- **Deployment impact:** Backend graph builder change + config change. Server restart required.
- **Rollback:** Simple — revert graph builder, change default mode back.
- **Resource impact:** Fact extraction uses LLM inference. Must run on primary model (not complex tier) to avoid timeout. Already fixed in this session.

## Executive Verdicts

- **CISO:** APPROVE — No new attack surface. Data stays local.
- **CTO:** APPROVE WITH CONDITIONS — Fix the Principle↔Fact edge model (use entities, not topics). Keep 3D but add labels.
- **CPO:** APPROVE WITH CONDITIONS — Must have good empty state UX. The cold-start experience makes or breaks adoption.
- **CFO:** APPROVE — ~10 hours investment to fix a core feature that's been broken. High ROI.
- **Legal:** APPROVE — No new external dependencies or data flows.

## Key Principles Score

| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 5 | No changes to security model |
| Empathy | 4 | Serves the user well (-1 for cold-start gap) |
| Simplicity | 4 | Hybrid edges add complexity but justified |
| Joy | 4 | Fixing a broken feature is satisfying |

## Final Critiques

1. **Most likely failure:** Empty graph for weeks while pipeline populates. **Mitigation:** Bootstrap pipeline on deploy (trigger fact extraction + community detection), show progress indicator.
2. **Critical assumption:** That the LLM pipeline will reliably produce meaningful facts and communities on the Mac Mini M1. **Validation:** Run the extraction once manually and inspect output quality before building the UI around it.
3. **Half-time cut list:** Community-based spatial clustering (fall back to force-directed). Billboard text labels (keep click-to-inspect). These are nice-to-haves; the core value is Principles + Facts as nodes with hybrid edges.

## Cross-Model Validation (Gemini 2.5 Pro)

### Gemini's Independent Assessment
Gemini approved the strategic goals but recommended a phased "Crawl, Walk, Run" approach: (1) fix the existing 2D graph with topics/entities first, (2) layer principles on top, (3) add facts and communities later. Gemini strongly advocated pivoting to 2D and using degree centrality for node sizing.

### Where Both Models Agree
- Degree centrality is the right sizing strategy
- Cold-start problem is critical and needs UX attention
- Topics/Entities as metadata-on-click is correct
- Pipeline fragility is the #1 technical risk
- The conceptual model (Principles + Facts) is strong

### Where Models Diverge

| Topic | Claude (Internal) | Gemini (External) | Resolution |
|-------|------------------|-------------------|------------|
| 3D vs 2D | Keep 3D, add labels | Pivot to 2D immediately | **Keep 3D with labels** — 3D is already built, the pivot is a large separate effort. Add billboard labels to mitigate readability. |
| Phased approach | Build the full model now | Crawl/Walk/Run with existing data first | **Hybrid** — build the target model (Principles + Facts) but also bootstrap the pipeline so there's data from day 1. |
| Principle↔Fact edges | Shared topics (original) → shared entities (revised) | Shared topics | **Shared entities** — critic correctly identified that Facts lack topic tags. |

### Novel Insights from Gemini
- **Graceful degradation:** Graph should always render with last-known-good data + "updating..." status, never block on inference.
- **Knowledge lifecycle:** Plan doesn't address temporal drift. How do superseded facts appear? Recommendation: dimmed/faded nodes for `SUPERSEDED` status.
- **Approval UX already exists** — the Principles tab with Approve/Edit/Reject is working (confirmed this session).

## Conditions for Approval

1. **Fix Principle↔Fact edge model** — use shared entities, not shared topics (data model blocker)
2. **Bootstrap the pipeline on deploy** — trigger fact extraction + community detection so the graph isn't empty
3. **Add billboard text labels to SceneKit nodes** — without labels, the graph is a visual toy, not a tool
4. **Implement degree centrality for node sizing** — biggest nodes = most connected
5. **Design a good empty state** — "Building your knowledge graph..." with progress when data is sparse
6. **Run manual extraction test** — verify the Mac Mini LLM produces usable facts before building UI around them
