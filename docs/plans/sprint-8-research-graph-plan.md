# Sprint 8: Research & Graph View + PrincipleStore

**Created:** 2026-03-03
**Status:** PLANNED
**Priority:** P1 — Foundation for Learning Cycle Phase A
**Estimated Effort:** ~13 days (~78 hours)
**Audit:** `docs/plans/sprint-7-9-audit-2026-03-03.md`
**Prerequisites:** Sprint 7 (CacheManager, MarkdownEditorView)
**Learning Cycle Phase:** A (part 1) — PrincipleStore

---

## Objective

Wire the Neural Net graph to real hybrid data (knowledge + activity), fix Explorer loading issues, establish the research view as a genuine intelligence dashboard, and lay the foundation for the Learning Cycle's Principle Store.

## Deliverables

1. New `hestia/research/` backend module with graph builder
2. `GET /v1/research/graph` endpoint returning real knowledge + activity data
3. Refactored NeuralNetGraphView consuming production data
4. Graph control panel (filters, depth, focus topic)
5. Node detail popover (tap node → see details)
6. Explorer loading bug fixed
7. PrincipleStore ChromaDB collection + distillation endpoint

---

## Pre-Sprint Checklist (Audit Addition 2026-03-03)

Before Sprint 8 begins, validate these assumptions:

- [ ] **Data volume check:** Run `chromadb_collection.count()` to verify memory chunk count. Minimum thresholds:
  - **<50 chunks:** Graph will be sparse. Add a data seeding step (import Notes, Calendar history, or conversation transcripts into memory) OR implement onboarding empty state first.
  - **50–100 chunks:** Graph is meaningful but clustering will be weak. Proceed with simple category-based coloring instead of community detection.
  - **100+ chunks:** Full graph pipeline viable.
- [ ] **Add `LogComponent.RESEARCH`** to the enum in `hestia/logging/__init__.py` before writing any research module code.
- [ ] **Add `auto-test.sh` mapping** for `hestia/research/` → `tests/test_research.py`.
- [ ] **Verify frontend contract:** The existing `ResearchView.swift` and `MacSceneKitGraphView.swift` expect a specific data model. Backend `GraphNode` must include: `id`, `content`, `confidence`, `topics`, `entities`, `position` (x/y/z), `radius`, `color`. Backend `GraphEdge` must include: `fromId`, `toId`, `weight`. Match these exactly or budget 1 day for view refactoring.

---

## Task Breakdown

### 8.1 Research Backend Module (~4 days)

> **Audit adjustment (2026-03-03):** Increased from 3 days to 4. Cross-database correlation (ChromaDB + SQLite tasks + SQLite orders + SQLite sessions) is the hard part. Tool execution logs are in orders/tasks tables, not a dedicated table — extracting and correlating this data is non-trivial. Consider building a `DataCorrelator` utility that other modules can reuse.

**New module structure:**
```
hestia/research/
├── __init__.py           # get_research_manager() factory
├── models.py             # GraphNode, GraphEdge, GraphCluster, GraphResponse, Principle
├── graph_builder.py      # Queries memory + tools + orders, builds graph
├── principle_store.py    # ChromaDB collection for distilled principles
├── manager.py            # ResearchManager (singleton pattern)
└── database.py           # SQLite cache for computed graphs
```

#### 8.1.1 Data Models (`models.py`)

```python
@dataclass
class GraphNode:
    """Must match the frontend contract in ResearchView.swift / MacSceneKitGraphView.swift."""
    id: str
    content: str            # Brief summary (displayed in node detail)
    type: Literal["knowledge", "activity"]
    label: str
    category: str           # finance, health, coding, communication, etc.
    confidence: float       # 0.0–1.0 (used for node opacity/prominence)
    weight: float           # 0.0–1.0 importance/frequency (used for radius)
    topics: List[str]       # Topic tags for filtering
    entities: List[str]     # Named entities extracted
    position: Dict[str, float]  # {"x": 0.5, "y": 0.5, "z": 0.5} — computed by graph layout
    radius: float           # Node size, proportional to weight
    color: str              # Hex color, determined by category
    last_active: datetime
    metadata: Dict[str, Any]  # chunk_type, source, tool_name, etc.

@dataclass
class GraphEdge:
    """Must match frontend: fromId/toId/weight (NOT source/target)."""
    fromId: str             # node ID (camelCase to match Swift convention)
    toId: str               # node ID
    type: Literal["co_occurrence", "similarity", "causal"]
    weight: float           # 0.0–1.0 strength
    count: int              # number of co-occurrences

@dataclass
class GraphCluster:
    id: str
    label: str
    node_ids: List[str]
    color: str              # hex color for rendering

@dataclass
class GraphResponse:
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    clusters: List[GraphCluster]
    generated_at: datetime
    node_count: int
    edge_count: int

@dataclass
class Principle:
    id: str
    content: str            # "Andrew prefers concise responses for scheduling"
    source_interactions: List[str]  # session IDs that contributed
    confidence: float       # 0.0–1.0 how validated
    domain: str             # scheduling, coding, health, etc.
    created_at: datetime
    last_validated: datetime
    validation_count: int
    contradiction_count: int
```

#### 8.1.2 Graph Builder (`graph_builder.py`)

**Pipeline:**
1. **Knowledge nodes:** Query ChromaDB for top-N memory chunks, group by topic/entity. Each unique topic/entity becomes a node with weight = frequency × recency.
2. **Activity nodes:** Query tool execution logs (from SQLite tasks/orders tables) for tool usage. Each unique tool becomes a node with weight = usage frequency.
3. **Edges — Co-occurrence:** Two nodes share an edge if they appeared in the same session. Weight = number of shared sessions.
4. **Edges — Similarity:** For knowledge nodes, compute cosine similarity from ChromaDB embeddings. Threshold at 0.7 for edge creation.
5. **Edges — Causal:** If tool X was always used after topic Y was discussed, create a causal edge. Weight = conditional probability.
6. **Clustering:** Simple label propagation or connected components for initial version. Assign colors from a predefined palette.
7. **Cache:** Store computed graph in SQLite with 5-minute TTL.

**Performance constraints (Mac Mini M1, 16GB):**
- Max 200 nodes, 500 edges per query
- ChromaDB query limit: 100 chunks per call
- Graph computation timeout: 10 seconds
- Cache aggressively — graph doesn't need real-time updates

> ⚠️ **Audit finding:** 200-node/500-edge limits are arbitrary. Profile M1 memory/CPU at 100, 200, 500, 1000 nodes before committing to limits. Build a SceneKit stress test scene early — have 2D Canvas fallback (SwiftUI Canvas) ready if 3D performance is insufficient.

#### 8.1.3 Principle Store (`principle_store.py`)

**ChromaDB collection:** `hestia_principles` (separate from `hestia_memory`)

> ⚠️ **Audit finding (2026-03-03):** Using the same `hestia_memory` collection would risk metadata conflicts and query pollution. PrincipleStore MUST use a dedicated `hestia_principles` collection with a separate embedding space. See `docs/architecture/chromadb-collections.md` for the unified collection strategy.

**Operations:**
- `store_principle(content, domain, source_sessions)` — Add new principle
- `search_principles(query, domain?, limit)` — Retrieve relevant principles
- `validate_principle(id)` — Increment validation count
- `contradict_principle(id)` — Increment contradiction count
- `get_principles(domain?, min_confidence?)` — List principles with filters

**Principle review step (MANDATORY — audit non-negotiable):** Distilled principles MUST NOT be auto-accepted as ground truth. Implementation:
1. New principles are stored with `status: "pending"` (not `"active"`)
2. `GET /v1/research/principles?status=pending` returns unreviewed principles
3. `POST /v1/research/principles/{id}/approve` → sets status to `"active"`, increments validation_count
4. `POST /v1/research/principles/{id}/reject` → sets status to `"rejected"`, logged for analysis
5. `PUT /v1/research/principles/{id}` → allows editing content before approval
6. Pending principles appear in daily briefing (`BriefingGenerator` new section: `PRINCIPLE_REVIEW`)
7. Only `"active"` principles influence future behavior (PredictionEngine, CuriosityDrive, etc.)

Without this gate, Hestia could learn wrong patterns silently and compound errors across the learning cycle.

**Distillation trigger:** `POST /v1/research/principles/distill`
- Takes optional session_id or time range
- Uses LLM (Qwen 7B or cloud) to analyze interactions and extract principles
- Prompt template:

```
Analyze these conversation excerpts and extract reusable behavioral principles about the user.
Focus on: communication preferences, workflow patterns, decision-making style, recurring needs.
Output format: One principle per line, prefixed with [domain].

Examples:
[scheduling] User prefers morning meetings summarized in bullet points
[coding] User wants tests written before implementation
[health] User tracks sleep quality and correlates with productivity
```

### 8.2 API Endpoint (`/v1/research/graph`) (~1 day)

**New route file:** `hestia/api/routes/research.py`

**Endpoints:**
```
GET /v1/research/graph
  Query params:
    node_types: str = "knowledge,activity"  (comma-separated filter)
    depth: int = 2                           (hop distance from center)
    limit: int = 200                         (max nodes)
    center_topic: str? = None                (optional focus node)
  Response: GraphResponse (200)

POST /v1/research/principles/distill
  Body: { session_id?: str, time_range_days?: int = 7 }
  Response: { principles_extracted: int, new: int, updated: int }

GET /v1/research/principles
  Query params:
    domain: str? = None
    min_confidence: float = 0.0
    limit: int = 50
  Response: { principles: List[Principle], total: int }
```

**Schema file:** `hestia/api/schemas/research.py`

**Registration:** Add to `hestia/api/server.py` router includes.

### 8.3 macOS Graph View Refactor (~3 days)

**Files to create/modify:**
- `macOS/Services/APIClient+Research.swift` — wraps research endpoints
- `macOS/ViewModels/MacResearchViewModel.swift` — graph data management
- `macOS/Views/Research/NeuralNetGraphView.swift` — refactor to consume real data
- `macOS/Views/Research/GraphControlPanel.swift` — filter/depth/focus controls
- `macOS/Views/Research/NodeDetailPopover.swift` — tap node → details

**NeuralNetGraphView refactor:**
- Currently: hardcoded demo nodes/edges in SceneKit
- Target: `GraphResponse` from API drives node placement, edge drawing, cluster coloring
- Force-directed layout algorithm for node positioning
- Color coding: knowledge nodes = blue tones, activity nodes = orange tones
- Node size proportional to weight
- Edge thickness proportional to weight
- Cluster boundaries as transparent colored regions

**GraphControlPanel:**
```
┌─────────────────────────────────┐
│ Node Types: [🔵 Knowledge] [🟠 Activity] │
│ Depth:  [1] [2] [3]            │
│ Focus:  [All Topics ▾]         │
│ Layout: [Force] [Radial] [Grid]│
└─────────────────────────────────┘
```

**NodeDetailPopover:** Tap a node → popover shows:
- Node type, label, category
- Last active date
- For knowledge: related memory chunks (top 3)
- For activity: usage count, last execution, linked order (if any)
- Related nodes (edges from this node)

### 8.4 Explorer Loading Fix (~1 day)

**Diagnosis steps:**
1. Check if `APIClient+Explorer.swift` exists in macOS/Services/ — if not, create it
2. Verify `MacExplorerViewModel` is calling correct endpoint (`GET /v1/explorer/resources`)
3. Check server startup: is ExplorerManager initialized? (check `server.py` lifecycle)
4. Test endpoint directly via curl to isolate frontend vs backend issue
5. Check for auth header propagation in the Explorer API calls

**Fix:** Dependent on diagnosis. Most likely one of:
- Missing APIClient extension (create it)
- ViewModel not triggering load on appear (add `.task {}` or `.onAppear {}`)
- ExplorerManager not registered in server lifecycle (add to init sequence)

---

## Testing Plan

| Area | Test Count | Type |
|------|-----------|------|
| GraphBuilder — knowledge nodes from ChromaDB | 5 | Unit |
| GraphBuilder — activity nodes from tool logs | 4 | Unit |
| GraphBuilder — edge computation | 5 | Unit |
| GraphBuilder — clustering | 3 | Unit |
| GraphBuilder — node limit enforcement (at 201 nodes) | 2 | Unit |
| GraphBuilder — SceneKit stress test (200 nodes) | 1 | Performance |
| PrincipleStore — CRUD operations | 5 | Unit |
| PrincipleStore — distillation | 3 | Integration |
| PrincipleStore — deduplication (same principle distilled twice) | 2 | Unit |
| PrincipleStore — ChromaDB collection isolation (no hestia_memory bleed) | 2 | Integration |
| PrincipleStore — review lifecycle (pending → approve/reject/edit) | 4 | API |
| `/v1/research/graph` endpoint | 4 | API |
| `/v1/research/principles/*` endpoints | 4 | API |
| Graph computation timeout (10-second limit enforced) | 2 | Unit |
| Empty ChromaDB (zero chunks → onboarding state, not crash) | 2 | Edge case |
| Backend GraphNode/GraphEdge matches frontend contract | 2 | Integration |
| Explorer loading fix | 2 | Integration |
| **Total** | **~52** | |

## SWOT

| | Positive | Negative |
|---|---|---|
| **Strengths** | ChromaDB already has embeddings for similarity. Tool/order logs exist in SQLite. PrincipleStore is the foundation for ALL future learning. | Graph computation could be expensive. Community detection adds dependencies. 3D SceneKit performance on M1 may limit node count. |
| **Opportunities** | Graph view is unique differentiator — no consumer AI has this. PrincipleStore creates training data for future fine-tuning. | If data is sparse (few memories), graph looks empty. Need minimum data thresholds for meaningful visualization. |

## Definition of Done

- [ ] Pre-sprint data volume validated (chunk count checked, onboarding path defined if <50)
- [ ] `LogComponent.RESEARCH` added to enum; `auto-test.sh` mapping added
- [ ] `GET /v1/research/graph` returns real knowledge + activity nodes
- [ ] Backend `GraphNode`/`GraphEdge` models match existing frontend contract (id, content, confidence, topics, entities, position, radius, color / fromId, toId, weight)
- [ ] NeuralNetGraphView renders production data with force-directed layout
- [ ] Graph controls filter by node type, depth, and focus topic
- [ ] Node detail popover shows relevant context on tap
- [ ] Empty state: <50 chunks shows onboarding message ("Keep chatting to build your knowledge graph")
- [ ] Graph computation timeout enforced (10 seconds max)
- [ ] PrincipleStore operational with distillation endpoint
- [ ] Principle review lifecycle: pending → approve/reject/edit (3 new endpoints)
- [ ] Only `"active"` principles (not `"pending"`) influence downstream systems
- [ ] Pending principles surfaced in daily briefing (`PRINCIPLE_REVIEW` section)
- [ ] Explorer loads resources without errors
- [ ] ChromaDB `hestia_principles` collection isolated from `hestia_memory`
- [ ] SceneKit stress test passes with 200 nodes (or 2D fallback ready)
- [ ] **Decision Gate 1:** PrincipleStore producing useful principles? ChromaDB performing well? → Go/No-Go
- [ ] All tests passing (existing + ~52 new)
- [ ] Both Xcode targets build clean
