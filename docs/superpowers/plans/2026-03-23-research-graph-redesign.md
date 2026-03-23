# Research Knowledge Graph Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the broken 3D Research graph into a meaningful knowledge visualization showing Principles and Facts as nodes, with hybrid edges, degree-centrality sizing, billboard text labels, and community-based clustering.

**Architecture:** Extend `build_fact_graph()` to include Principle nodes alongside existing entity/fact/community nodes. Add hybrid edge logic (principle↔principle via shared topics, principle↔fact and fact↔fact via shared entities). Switch default graph mode from `legacy` to `facts`. Add SCNText billboard labels to SceneKit nodes. Show Topics/Entities as metadata list in the detail panel.

**Tech Stack:** Python/FastAPI (backend graph builder), SwiftUI/SceneKit (macOS frontend), SQLite (research.db)

**Audit reference:** `docs/plans/research-graph-redesign-second-opinion-2026-03-23.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `hestia/research/graph_builder.py` | Modify | Add principles + hybrid edges to `build_fact_graph()`, degree centrality sizing |
| `hestia/research/models.py` | Modify (minor) | Add `SHARED_TOPIC_CROSS` edge type for principle↔principle edges |
| `HestiaApp/macOS/ViewModels/MacNeuralNetViewModel.swift` | Modify | Change default graph mode to `.facts`, update `defaultNodeTypes` |
| `HestiaApp/macOS/Views/Research/MacSceneKitGraphView.swift` | Modify | Add SCNText billboard labels to nodes |
| `HestiaApp/macOS/Views/Research/NodeDetailPopover.swift` | Modify | Add Topics & Entities list section |
| `tests/test_research.py` | Modify | Add tests for hybrid edges + principle injection |

---

## Task 1: Add Principle nodes to facts-mode graph builder

**Files:**
- Modify: `hestia/research/graph_builder.py` — `build_fact_graph()` method (~line 276)
- Test: `tests/test_research.py`

- [ ] **Step 1: Write failing test for principles in fact graph**

```python
# In tests/test_research.py — new test class
class TestFactGraphWithPrinciples:
    """Test that build_fact_graph includes approved principles."""

    @pytest.mark.asyncio
    async def test_principles_included_in_fact_graph(self):
        """Approved principles appear as nodes in the fact graph."""
        builder = FactGraphBuilder(research_db=mock_db)
        # Mock: 1 entity, 1 fact, 1 approved principle
        mock_db.list_entities.return_value = [mock_entity]
        mock_db.list_facts.return_value = [mock_fact]
        mock_db.list_communities.return_value = []
        mock_db.get_episodic_nodes.return_value = []
        mock_db.list_principles.return_value = [mock_approved_principle]

        response = await builder.build_fact_graph()

        principle_nodes = [n for n in response.nodes if n.node_type == NodeType.PRINCIPLE]
        assert len(principle_nodes) == 1
        assert principle_nodes[0].id == f"principle:{mock_approved_principle.id}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_research.py::TestFactGraphWithPrinciples -v --timeout=30`

- [ ] **Step 3: Implement — inject principles into build_fact_graph()**

In `graph_builder.py`, inside `build_fact_graph()`, after line ~276 where nodes are assembled:

```python
        # ── Build principle nodes (approved only) ──────────
        principle_nodes = await self._build_principle_nodes()

        # Assemble all nodes
        all_nodes = entity_nodes + community_nodes + episode_nodes + principle_nodes
        all_edges = relationship_edges + member_edges + episode_edges
```

The existing `_build_principle_nodes()` method (lines 623-658) already queries approved principles and returns `List[GraphNode]`. Just call it and append.

- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(research): add principle nodes to facts-mode graph"
```

---

## Task 2: Implement hybrid edge model

**Files:**
- Modify: `hestia/research/graph_builder.py` — new method `_build_hybrid_edges()`
- Modify: `hestia/research/models.py` — add `TOPIC_LINK` to EdgeType
- Test: `tests/test_research.py`

- [ ] **Step 1: Add TOPIC_LINK edge type**

In `models.py`, add to `EdgeType` enum:
```python
class EdgeType(str, Enum):
    # ... existing types ...
    TOPIC_LINK = "topic_link"  # Principle↔Principle via shared topics
```

- [ ] **Step 2: Write failing tests for hybrid edges**

```python
class TestHybridEdges:
    """Test hybrid edge model: topic-based + entity-based."""

    @pytest.mark.asyncio
    async def test_principle_to_principle_shared_topics(self):
        """Two principles sharing topics get a TOPIC_LINK edge."""
        p1 = make_principle(topics=["trading", "risk"])
        p2 = make_principle(topics=["trading", "portfolio"])
        edges = builder._build_hybrid_edges([p1_node, p2_node], [], set())
        topic_edges = [e for e in edges if e.edge_type == EdgeType.TOPIC_LINK]
        assert len(topic_edges) == 1
        assert topic_edges[0].weight > 0  # Weight by shared topic count

    @pytest.mark.asyncio
    async def test_principle_to_fact_shared_entity(self):
        """Principle with entity matching a fact's entity gets SHARED_ENTITY edge."""
        # Principle has entities=["mac_mini"]
        # Fact has source_entity_id matching entity "mac_mini"
        edges = builder._build_hybrid_edges([principle_node], [entity_node], entity_id_set)
        entity_edges = [e for e in edges if e.edge_type == EdgeType.SHARED_ENTITY]
        assert len(entity_edges) == 1

    @pytest.mark.asyncio
    async def test_no_edge_without_shared_data(self):
        """No edges when principles and facts share nothing."""
        p1 = make_principle(topics=["health"], entities=["fitbit"])
        # Entity node for "chromadb" — no overlap
        edges = builder._build_hybrid_edges([p1_node], [chromadb_entity_node], set())
        assert len(edges) == 0
```

- [ ] **Step 3: Run tests to verify they fail**
- [ ] **Step 4: Implement `_build_hybrid_edges()` method**

Add to `FactGraphBuilder` class in `graph_builder.py`:

```python
    def _build_hybrid_edges(
        self,
        principle_nodes: List[GraphNode],
        entity_nodes: List[GraphNode],
        entity_id_set: Set[str],
    ) -> List[GraphEdge]:
        """Build hybrid edges connecting principles to each other and to entities.

        Edge types:
        - TOPIC_LINK: Principle↔Principle via shared topics
        - SHARED_ENTITY: Principle↔Entity via principle.entities matching entity names
        """
        edges: List[GraphEdge] = []
        seen: Set[Tuple[str, str]] = set()

        # Principle↔Principle via shared topics
        for i, p_a in enumerate(principle_nodes):
            for p_b in principle_nodes[i + 1:]:
                shared = set(t.lower() for t in p_a.topics) & set(t.lower() for t in p_b.topics)
                if shared:
                    pair = (min(p_a.id, p_b.id), max(p_a.id, p_b.id))
                    if pair not in seen:
                        seen.add(pair)
                        edges.append(GraphEdge(
                            from_id=p_a.id,
                            to_id=p_b.id,
                            edge_type=EdgeType.TOPIC_LINK,
                            weight=min(len(shared) / 3.0, 1.0),
                            count=len(shared),
                        ))

        # Principle↔Entity via shared entity names
        # Build name→node_id lookup from entity nodes
        entity_name_to_id: Dict[str, str] = {}
        for en in entity_nodes:
            for name in en.entities:
                entity_name_to_id[name.lower()] = en.id

        for p_node in principle_nodes:
            for entity_name in p_node.entities:
                entity_graph_id = entity_name_to_id.get(entity_name.lower())
                if entity_graph_id:
                    pair = (min(p_node.id, entity_graph_id), max(p_node.id, entity_graph_id))
                    if pair not in seen:
                        seen.add(pair)
                        edges.append(GraphEdge(
                            from_id=p_node.id,
                            to_id=entity_graph_id,
                            edge_type=EdgeType.SHARED_ENTITY,
                            weight=0.6,
                        ))

        return edges
```

Wire it into `build_fact_graph()` after building principle nodes:

```python
        # ── Build hybrid edges (principles ↔ entities) ────
        hybrid_edges = self._build_hybrid_edges(principle_nodes, entity_nodes, entity_id_set)
        all_edges = relationship_edges + member_edges + episode_edges + hybrid_edges
```

- [ ] **Step 5: Run tests to verify they pass**
- [ ] **Step 6: Commit**

```bash
git commit -m "feat(research): hybrid edge model — topic links + shared entities"
```

---

## Task 3: Degree centrality node sizing

**Files:**
- Modify: `hestia/research/graph_builder.py` — in `build_fact_graph()` after edge assembly
- Test: `tests/test_research.py`

- [ ] **Step 1: Write failing test**

```python
    @pytest.mark.asyncio
    async def test_degree_centrality_sizing(self):
        """Nodes with more edges get higher weight (degree centrality)."""
        response = await builder.build_fact_graph()
        # Node with most connections should have highest weight
        weights = {n.id: n.weight for n in response.nodes}
        # Hub node connected to 3 others should weigh more than leaf with 1 connection
        assert weights[hub_node_id] > weights[leaf_node_id]
```

- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement degree centrality weight override**

After all nodes and edges are assembled in `build_fact_graph()`, before `_compute_layout()`:

```python
        # ── Degree centrality sizing ──────────────────────
        degree: Counter = Counter()
        for edge in all_edges:
            degree[edge.from_id] += 1
            degree[edge.to_id] += 1
        max_degree = max(degree.values()) if degree else 1

        for node in all_nodes:
            d = degree.get(node.id, 0)
            # Blend: 70% degree centrality + 30% original weight (confidence/durability)
            centrality_weight = (d / max_degree) if max_degree > 0 else 0.2
            node.weight = centrality_weight * 0.7 + node.weight * 0.3
            node.weight = max(node.weight, 0.15)  # Minimum so isolated nodes are visible
```

- [ ] **Step 4: Run tests**
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(research): degree centrality node sizing"
```

---

## Task 4: Switch default graph mode to facts

**Files:**
- Modify: `HestiaApp/macOS/ViewModels/MacNeuralNetViewModel.swift` — `GraphMode` enum + default

- [ ] **Step 1: Update defaultNodeTypes and default mode**

```swift
enum GraphMode: String, CaseIterable {
    case legacy = "legacy"
    case facts  = "facts"

    // ...

    var defaultNodeTypes: Set<String> {
        switch self {
        case .legacy: return ["memory", "topic", "entity", "principle"]  // Fix: add memory back
        case .facts:  return ["entity", "community", "principle", "fact"]  // Add principle
        }
    }
}

// Change default:
@Published var graphMode: GraphMode = .facts {  // Was .legacy
```

- [ ] **Step 2: Build verify**

Run: `cd HestiaApp && xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build CODE_SIGNING_ALLOWED=NO -quiet`

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(research): default to facts graph mode, add principle to node types"
```

---

## Task 5: Add billboard text labels to SceneKit nodes

**Files:**
- Modify: `HestiaApp/macOS/Views/Research/MacSceneKitGraphView.swift` — `createNodeGeometry()`

- [ ] **Step 1: Add label node after geometry creation**

At the end of `createNodeGeometry(for:)`, before `return node`, add a billboard text label:

```swift
        // Billboard text label (always faces camera)
        let labelText = SCNText(string: graphNode.label.prefix(30), extrusionDepth: 0.01)
        labelText.font = NSFont.systemFont(ofSize: 0.15, weight: .medium)
        labelText.flatness = 0.3
        let labelMaterial = SCNMaterial()
        labelMaterial.diffuse.contents = NSColor(white: 0.9, alpha: 0.85)
        labelMaterial.lightingModel = .constant
        labelText.materials = [labelMaterial]

        let labelNode = SCNNode(geometry: labelText)
        // Center the text horizontally
        let (min, max) = labelNode.boundingBox
        let textWidth = max.x - min.x
        labelNode.position = SCNVector3(-textWidth / 2, Float(graphNode.radius) + 0.08, 0)
        labelNode.scale = SCNVector3(1, 1, 0.1)  // Flatten depth

        // Billboard constraint: always face camera
        let billboard = SCNBillboardConstraint()
        billboard.freeAxes = .all
        labelNode.constraints = [billboard]

        node.addChildNode(labelNode)
```

- [ ] **Step 2: Build verify**
- [ ] **Step 3: Commit**

```bash
git commit -m "feat(research): billboard text labels on graph nodes"
```

---

## Task 6: Update detail panel — Topics & Entities list

**Files:**
- Modify: `HestiaApp/macOS/Views/Research/NodeDetailPopover.swift`

- [ ] **Step 1: Add Topics & Entities section**

In `NodeDetailPopover`, after the existing tags section (~line 208), add:

```swift
    // MARK: - Topics & Entities Detail

    @ViewBuilder
    private var topicsEntitiesSection: some View {
        let hasTopics = !node.topics.isEmpty
        let hasEntities = !node.entities.isEmpty

        if hasTopics || hasEntities {
            VStack(alignment: .leading, spacing: MacSpacing.sm) {
                if hasTopics {
                    Text("Topics")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(MacColors.textFaint)
                    FlowLayout(spacing: 4) {
                        ForEach(node.topics, id: \.self) { topic in
                            Text(topic)
                                .font(.system(size: 11))
                                .foregroundStyle(MacColors.textPrimary)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 3)
                                .background(MacColors.amberAccent.opacity(0.15))
                                .clipShape(Capsule())
                        }
                    }
                }

                if hasEntities {
                    Text("Entities")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(MacColors.textFaint)
                    FlowLayout(spacing: 4) {
                        ForEach(node.entities, id: \.self) { entity in
                            Text(entity)
                                .font(.system(size: 11))
                                .foregroundStyle(MacColors.textPrimary)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 3)
                                .background(MacColors.searchInputBackground)
                                .clipShape(Capsule())
                        }
                    }
                }
            }
        }
    }
```

Wire it into the main body by calling `topicsEntitiesSection` after the content section.

- [ ] **Step 2: Build verify**
- [ ] **Step 3: Commit**

```bash
git commit -m "feat(research): topics & entities list in node detail panel"
```

---

## Task 7: Bootstrap pipeline on Mac Mini

**Files:** None (operational — run extraction commands on Mac Mini)

- [ ] **Step 1: Trigger fact extraction**

```bash
MINI_TOKEN="<valid-jwt>"
curl -sk -X POST "https://hestia-3.local:8443/v1/research/facts/extract" \
  -H "X-Hestia-Device-Token: $MINI_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"time_range_days": 30}'
```

- [ ] **Step 2: Trigger community detection**

```bash
curl -sk -X POST "https://hestia-3.local:8443/v1/research/communities/detect" \
  -H "X-Hestia-Device-Token: $MINI_TOKEN"
```

- [ ] **Step 3: Verify data populated**

```bash
ssh andrewroman117@hestia-3.local "cd ~/hestia && python3 -c \"
import sqlite3
conn = sqlite3.connect('data/research.db')
for table in ['principles', 'entities', 'facts', 'communities']:
    count = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
    print(f'{table}: {count}')
conn.close()
\""
```

- [ ] **Step 4: Deploy and restart server**

```bash
git push
ssh andrewroman117@hestia-3.local 'cd ~/hestia && git pull && pkill -f "hestia.api.server" && sleep 2 && source .venv/bin/activate && nohup python -m hestia.api.server >> logs/server.log 2>> logs/server.error.log &'
```

---

## Task 8: Ship macOS app update

- [ ] **Step 1: Version bump + xcodegen + build verify + tag + push**

Follow `/ship-it` skill: bump to v1.1.9 (build 13), xcodegen, build verify, commit, tag, push.

---

## Verification

1. **Backend:** `python -m pytest tests/test_research.py -v --timeout=30` — all tests pass
2. **macOS build:** `xcodebuild -scheme HestiaWorkspace build CODE_SIGNING_ALLOWED=NO -quiet` — clean
3. **API test:** `curl /v1/research/graph?mode=facts` returns principle + entity + fact nodes with hybrid edges
4. **Visual:** Open Research tab in macOS app — see labeled nodes clustered by community, sized by connections
5. **Detail panel:** Click a principle node — see Topics and Entities listed
