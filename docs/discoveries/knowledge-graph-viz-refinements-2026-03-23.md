# Discovery Report: Knowledge Graph Visualization Refinements
**Date:** 2026-03-23
**Confidence:** High
**Decision:** All 7 items are feasible and well-scoped. Implement as a single sprint (~10-14h). Items 3 (fuzzy dedup) and 7 (extraction prompts) deliver the highest ROI by improving data quality upstream of all visual improvements.

## Hypothesis
Seven refinements to Hestia's knowledge graph visualization will improve clarity, reduce noise, and make the 3D graph genuinely useful for exploring personal knowledge:
1. Shape-per-entity-type in SceneKit
2. Hide community nodes from 3D graph
3. Entity dedup/fuzzy matching in EntityRegistry
4. Remove text labels from graph nodes
5. Fix entity node colors vs legend
6. LLM-generated community labels
7. Tighter extraction prompts to reject conversation fragments as entities

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** SceneKit already uses per-nodeType shapes (sphere, cube, torus, capsule, cylinder); 3-phase extraction pipeline with significance filter exists; legend is dynamic and data-driven; community detection via label propagation works | **Weaknesses:** Entity resolution is exact-match only (`canonical = name.lower().strip()`); community labels are generic (`community-1`, `community-2`); entity nodes in facts mode use `entity_type.value` as category (person/tool/concept) but legend shows a single "Entity" color (#30D158); labels on all nodes create clutter at scale |
| **External** | **Opportunities:** Fuzzy matching would collapse duplicates (e.g., "claude code" vs "Claude Code" already handled, but "andrew" vs "Andrew Roman" not); LLM community labels would make communities meaningful; removing labels would dramatically improve visual clarity | **Threats:** Aggressive fuzzy matching could incorrectly merge distinct entities; LLM community labeling adds inference cost per community detection run; shape variety could reduce visual coherence if overdone |

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | (3) Entity fuzzy dedup, (7) Tighter extraction prompts, (5) Fix entity colors vs legend | (4) Remove text labels |
| **Low Priority** | (6) LLM community labels | (1) Shape-per-entity-type refinement, (2) Hide community nodes |

## Item-by-Item Analysis

### Item 1: Shape-per-entity-type in SceneKit

**Current state:** `MacSceneKitGraphView.createNodeGeometry()` already switches on `nodeType` (topic=diamond, entity=cube, principle=torus, community=translucent sphere, episode=capsule, fact=cylinder, memory=sphere). However, within `entity` nodes, all entity *types* (person, tool, concept, place, project, organization) render as the same cube.

**Recommendation:** Add entity-type differentiation within the `"entity"` case. Use the `category` field (which is `entity_type.value` for fact-graph entity nodes) to select sub-shapes:
- person: sphere (human, organic)
- tool: cube (angular, built)
- concept: octahedron/diamond (abstract)
- project: capsule (compound, ongoing)
- organization: box with chamfer (institutional)
- place: cylinder (grounded)

**Effort:** ~1.5h. Modify `createNodeGeometry()` to sub-switch on `graphNode.category` when `nodeType == "entity"`.

**Risk:** Low. Pure frontend change. If too many shapes become confusing, fall back to cube+color differentiation only.

### Item 2: Hide community nodes from 3D graph

**Current state:** Community nodes render as large translucent spheres. They're useful conceptually but in practice they obscure other nodes and add visual noise. Communities are auto-detected via label propagation and currently labeled generically.

**Recommendation:** Remove `community` from `GraphMode.facts.defaultNodeTypes` so they're hidden by default but can be re-enabled via the filter panel. Keep the community detection logic and edges (they still affect layout via spring forces). This is a one-line change in `MacNeuralNetViewModel.swift`.

**Effort:** ~0.25h. Change `defaultNodeTypes` for `.facts` from `["entity", "community", "principle", "fact"]` to `["entity", "principle", "fact"]`.

**Risk:** None. User can re-enable via GraphControlPanel toggle.

### Item 3: Entity dedup/fuzzy matching in EntityRegistry

**Current state:** `EntityRegistry.resolve_entity()` does exact canonical match only: `canonical = name.lower().strip()`. This means "Andrew" and "Andrew Roman" create two separate entities. "Claude Code" and "claude code" are already handled (case-insensitive), but abbreviations, name variations, and typos are not.

**Recommendation:** Implement a 2-tier resolution pipeline:
1. **Exact match** (current behavior, fast path)
2. **Fuzzy match** with Jaro-Winkler similarity (threshold >= 0.88) against all existing entity names of the same type

Jaro-Winkler is preferred over Levenshtein for names because it gives more weight to prefix matches ("Andrew" vs "Andrew Roman" scores higher than "Andrew" vs "Wandrew"). Python's `jellyfish` library provides a fast C implementation.

**Implementation:**
```python
async def resolve_entity(self, name, entity_type, ...):
    canonical = name.lower().strip()
    # 1. Exact match
    existing = await self._db.find_entity_by_name(canonical)
    if existing:
        return existing
    # 2. Fuzzy match against same-type entities
    candidates = await self._db.list_entities_by_type(entity_type, limit=500)
    best_match, best_score = None, 0.0
    for candidate in candidates:
        score = jaro_winkler_similarity(canonical, candidate.canonical_name)
        if score > best_score:
            best_match, best_score = candidate, score
    if best_match and best_score >= 0.88:
        return best_match
    # 3. Create new
    ...
```

**Effort:** ~3h. Add `jellyfish` dependency, implement fuzzy matching, add `list_entities_by_type()` to ResearchDatabase, write tests.

**Risk:** Medium. False positives (merging distinct entities) are worse than false negatives (keeping duplicates). The 0.88 threshold is conservative. Add logging so merged entities are visible. Consider adding a merge audit trail.

### Item 4: Remove text labels from graph nodes

**Current state:** `addBillboardLabel()` in `MacSceneKitGraphView.swift` adds 3D text labels (SCNText) to every node. These billboard-constrained labels are capped at 25 chars. At 50+ nodes they create significant visual clutter.

**Recommendation:** Remove labels from all nodes. Rely on:
- Hover tooltip (already exists and works)
- Click → NodeDetailPopover (already exists)
- Node shape + color for type identification

Simply skip the `addBillboardLabel()` call. Or, implement LOD-based labels: only show labels for high-weight nodes (top 20%).

**Effort:** ~0.5h for full removal, ~1.5h for LOD-based approach.

**Risk:** None for removal. Users lose the ability to read labels without hovering, but the hover tooltip already provides this. The LOD approach is cleaner but more complex.

### Item 5: Fix entity node colors vs legend

**Current state:** There is a mismatch between how entity nodes are colored and how the legend displays them.

**Backend:** Entity nodes in fact-graph mode use `category = entity.entity_type.value` (e.g., "person", "tool", "concept"). The `CATEGORY_COLORS` dict maps these to distinct colors:
- person: `#FF9F0A` (orange)
- tool: `#30D158` (green)
- concept: `#64D2FF` (light blue)
- project: `#5AC8FA` (blue)
- organization: `#BF5AF2` (purple)
- place: `#FF375F` (red/pink)

**Frontend legend:** Shows a single "Entity" entry with color `Color(red: 0.19, green: 0.82, blue: 0.35)` = `#30D158` (green). This matches only "tool" entities. All other entity types show their correct backend color in the 3D graph but the legend only shows one green dot.

**Recommendation:** Update the legend to show entity sub-types when in facts mode. When `graphMode == .facts`, instead of a single "Entity" legend entry, show the per-entity-type breakdown (like the existing memory-type breakdown):
```swift
if graphViewModel.graphMode == .facts && graphViewModel.activeNodeTypes.contains("entity") {
    legendColorDot(color: Color(hex: "#FF9F0A"), label: "Person")
    legendColorDot(color: Color(hex: "#30D158"), label: "Tool")
    legendColorDot(color: Color(hex: "#64D2FF"), label: "Concept")
    // ...
}
```

**Effort:** ~1h. Modify `graphLegend` in ResearchView.swift. Could also make it dynamic by collecting unique categories from entity nodes.

**Risk:** None. Pure visual fix.

### Item 6: LLM-generated community labels

**Current state:** `EntityRegistry.detect_communities()` assigns labels as `community-{N}` (e.g., "community-1", "community-2"). These are meaningless to the user.

**Recommendation:** After community detection, send each community's member entity names to the LLM with a prompt like:
```
Given these related entities: [entity1, entity2, entity3, ...]
Generate a 2-4 word descriptive label that captures their common theme.
Return JSON: {"label": "..."}
```

**Implementation:** Add a `_label_communities()` method called after `detect_communities()`. Use `force_tier="primary"` (local LLM) to keep cost zero.

**Effort:** ~2h. LLM call per community (typically <10 communities), prompt engineering, fallback to generic label on failure.

**Risk:** Low. LLM might generate poor labels, but they'd still be better than "community-1". Wrap in try/except with fallback.

### Item 7: Tighter extraction prompts to reject conversation fragments

**Current state:** The 3-phase extraction pipeline (Phase 1: entities, Phase 2: significance filter, Phase 3: PRISM triples) already has some quality guards:
- Phase 2 filters to "CORE ACTORS" vs "BACKGROUND DETAIL"
- Phase 3 PRISM prompt says "Skip entirely if text is procedural or thinking-out-loud"
- Durability scoring (0-3) with ephemeral facts (durability=0) excluded from graph

**Problem:** Despite these guards, conversation fragments like "let me think about this", "okay so", "that makes sense" can still slip through as entities or fact text. The Phase 1 entity prompt says "Only include specific named entities, not pronouns or generic references" but doesn't explicitly reject conversational fillers.

**Recommendation:** Strengthen the Phase 1 and Phase 3 prompts:

Phase 1 addition:
```
EXCLUDE: Do not extract conversational fragments, filler phrases, thinking-out-loud expressions,
procedural language, or instructions to yourself. Only extract entities that would appear in an
encyclopedia or professional directory.
```

Phase 3 addition:
```
REJECTION CRITERIA: Skip the entire extraction if the text is:
- A conversational exchange with no factual content
- Instructions or commands (e.g., "please do X", "can you help with Y")
- Stream-of-consciousness or brainstorming without conclusions
- Meta-commentary about the conversation itself
```

**Effort:** ~1h. Prompt modification + test with sample inputs.

**Risk:** Low. Could be slightly over-aggressive (rejecting valid entities mentioned in casual conversation), but the 3-phase pipeline provides multiple checkpoints.

## Third-Party Evidence

**Entity Resolution:** The Graphiti project (by Zep, open-source) uses embedding-based entity resolution with a similarity threshold. Microsoft's GraphRAG uses LLM-based entity resolution. Both validate that exact-match-only is insufficient for production knowledge graphs.

**Community Labels:** Microsoft GraphRAG generates community summaries using LLMs (map-reduce over community members). Graphiti uses entity descriptions for context. Both confirm that auto-generated labels are standard practice.

**Extraction Quality:** LlamaIndex's `KnowledgeGraphIndex` and LangChain's `LLMGraphTransformer` both use schema-constrained extraction. Few-shot examples and negative constraints are widely recommended.

## Gemini Web-Grounded Validation
**Model:** Gemini 2.5 Pro (thinking + google_web_search)

### Confirmed Findings
- Shape-per-type is standard practice but should be limited to simple, distinguishable primitives (confirmed)
- Jaro-Winkler is preferred for name matching due to prefix weighting (confirmed)
- Multi-stage entity resolution (blocking + scoring + refinement) is industry best practice (confirmed)
- Billboard labels with LOD-based visibility are the standard approach for 3D graph label management (confirmed)
- Negative constraints in extraction prompts significantly reduce noise (confirmed)

### Contradicted Findings
- None material. Gemini's research aligned with internal analysis on all major points.

### New Evidence
- **Excentric labeling** technique: When hovering over dense clusters, arrange labels in a circle around the cluster with leader lines. Worth considering for future enhancement.
- **2D billboard icons** as an alternative to 3D shape variation for node type encoding. More performant and avoids perspective distortion. Could be a future direction using SpriteKit textures on SceneKit planes.

### Sources
Gemini provided general best-practice guidance without specific URLs (the queries were broad enough that it synthesized from multiple sources rather than citing individual pages).

## Philosophical Layer
- **Ethical check:** All changes serve genuine user needs (clearer visualization, less noise, more accurate data). No ethical concerns.
- **First principles:** The fundamental question is "does the graph help the user understand their knowledge?" Currently, noise (duplicates, conversation fragments, cluttered labels) undermines this. These 7 items attack noise from multiple angles.
- **Moonshot:** SHELVE. A moonshot version would be a fully interactive graph with real-time LLM-powered exploration (click a cluster, ask "what connects these?"). This requires the current cleanup work first. Revisit when the graph data is clean.

## Key Principles Score
| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 5 | No new attack surface. All changes are display/extraction logic. |
| Empathy | 5 | Every item directly improves the user experience of the graph. |
| Simplicity | 4 | Items are individually simple. The fuzzy matching adds complexity but is essential. |
| Joy | 4 | A clean, readable graph with meaningful labels will be satisfying to explore. |

## Recommendation
Implement all 7 items as a focused sprint. Recommended order:

**Phase A — Data Quality (backend, do first):**
1. Item 7: Tighter extraction prompts (~1h)
2. Item 3: Entity fuzzy dedup (~3h)
3. Item 6: LLM community labels (~2h)

**Phase B — Visual Cleanup (frontend, depends on cleaner data):**
4. Item 2: Hide community nodes by default (~0.25h)
5. Item 5: Fix entity colors vs legend (~1h)
6. Item 4: Remove/LOD text labels (~1h)
7. Item 1: Shape-per-entity-type (~1.5h)

**Total estimate:** ~10h

**Confidence:** High. All items are well-understood, self-contained, and low-risk. The codebase is well-structured for these changes.

**What would change this recommendation:** If the knowledge graph had <20 entities total, items 3/6/7 would be premature optimization. But given active daily use with growing entity count, data quality improvements are urgent.

## Final Critiques
- **Skeptic:** "Fuzzy matching will merge entities that shouldn't be merged." **Response:** The 0.88 Jaro-Winkler threshold is conservative, and we match within entity type only. Add an audit log so incorrect merges are discoverable and reversible. Start conservative, loosen later.
- **Pragmatist:** "Is 10h of graph polish worth it vs. trading module work?" **Response:** The graph is the primary way Andrew explores his knowledge base. Noisy data and unreadable visualizations undermine trust in the system. This is infrastructure that compounds.
- **Long-Term:** "Will these changes survive the M5 upgrade?" **Response:** Yes. All changes are in application logic (Swift views, Python extraction/resolution), not hardware-dependent. The M5 upgrade only affects model performance, which makes LLM community labeling faster.

## Open Questions
1. Should fuzzy matching use `jellyfish` (C extension, fast) or pure Python (no new dependency)?
2. Should the LOD label approach use a fixed threshold (top 20% by weight) or a dynamic one based on zoom level?
3. Should community labels be cached or regenerated on each community detection run?
4. Is there a need for a "merge entities" UI for manual dedup in addition to automatic fuzzy matching?
