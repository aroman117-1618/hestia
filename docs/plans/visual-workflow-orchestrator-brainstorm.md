# Visual Workflow Orchestrator — Brainstorm & Development Map (v2 — Gemini-Reconciled)

**Date:** 2026-03-18
**Context:** Evolution of Hestia's Orders system into a visual DAG-based workflow engine
**Inspiration:** n8n-style visual orchestration, fully owned, macOS-native
**Gemini Review:** Incorporated — TaskGroup, checkpointing, dead path elimination, debounce keys, JMESPath, OS-level hooks, HMAC webhooks, version snapshotting

---

## Vision

Transform the Orders system from "scheduled prompts" into a full visual workflow engine. Users build DAG workflows by connecting trigger, action, condition, and join nodes on a canvas. Workflows can fan out (parallel branches), converge (joins), and branch conditionally. Everything runs on the existing APScheduler + Hestia inference stack.

**What this replaces:** The current Orders system (7 endpoints, time-based scheduling, prompt execution stub). The new system is a superset — every existing Order can be represented as a single-node workflow.

**What this is NOT:** A general-purpose automation platform. This is Hestia-specific — nodes are Hestia capabilities (inference, tools, memory, notifications). The value proposition is that Hestia understands context, can reason about results, and chains actions intelligently.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────┐
│                  macOS Canvas UI                  │
│  (SwiftUI drag-drop DAG editor, node config)      │
└──────────────────────┬───────────────────────────┘
                       │ REST API
┌──────────────────────▼───────────────────────────┐
│              Workflow Engine (Python)              │
│  ┌─────────┐ ┌──────────┐ ┌───────────────────┐  │
│  │ DAG     │ │ Node     │ │ Execution         │  │
│  │ Parser  │ │ Registry │ │ Runtime           │  │
│  └─────────┘ └──────────┘ └───────────────────┘  │
│  ┌─────────────────┐ ┌───────────────────────┐   │
│  │ Trigger Engine   │ │ Condition Evaluator   │   │
│  │ (APScheduler +   │ │ (Expression engine)   │   │
│  │  EventListeners)  │ └───────────────────────┘   │
│  └─────────────────┘                              │
└──────────────────────┬───────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   Inference      Tool Executor    Notification
   Pipeline       (Apple, MCP)     Relay (WS6)
```

---

## Node Type Taxonomy

### 1. Trigger Nodes (entry points — every workflow has ≥1)

| Node | Config | Implementation |
|------|--------|----------------|
| **Schedule** | Time, frequency (daily/weekly/monthly/custom) | Existing APScheduler triggers |
| **Cron** | Raw cron expression | APScheduler CronTrigger |
| **Email Arrival** | Filter: sender, subject pattern, has attachment | EventListener on InboxManager (poll-based, 60s) |
| **Calendar Event** | Minutes before event, event filter (title pattern) | EventListener on CalendarService (poll-based, 60s) |
| **Health Threshold** | Metric type, operator (>, <, =), threshold value | EventListener on HealthManager (daily sync hook) |
| **Memory Trigger** | Chunk count threshold, type filter | EventListener on MemoryManager.store() hook |
| **System Event** | Server start, order failure, learning alert | Internal event bus |
| **Manual** | Button press in UI | Direct API call |
| **Webhook** | Inbound HTTP POST to `/v1/workflows/{id}/trigger` | New endpoint |
| **Market Condition** | Ticker, condition (price >, volume >, % change) | EventListener (future: Trading module) |

### 2. Action Nodes (do something)

| Node | Config | Implementation |
|------|--------|----------------|
| **Run Prompt** | Prompt template (with `{{variable}}` interpolation from upstream nodes), model preference, agent routing | Existing handler pipeline |
| **Call Tool** | Tool name + parameters (from tool registry) | ToolExecutor |
| **Send Notification** | Title, body, priority, target (macOS/iPhone/both) | WS6 NotificationManager |
| **Create Memory** | Content, chunk_type, tags | MemoryManager.store() |
| **Extract Facts** | Source text (from upstream), extraction mode | ResearchManager.extract_facts() |
| **HTTP Request** | URL, method, headers, body template | New: aiohttp call |
| **Transform Data** | JSONPath expression, format template | New: lightweight data mapper |
| **Delay** | Duration (seconds/minutes/hours) | asyncio.sleep in executor |
| **Log** | Message template, log level | Logger output + execution history |
| **Update Order** | Target workflow ID, status change | Self-modification for chain control |

### 3. Condition Nodes (branch based on data)

| Node | Config | Implementation |
|------|--------|----------------|
| **If/Else** | Expression: `{{upstream.field}} operator value` | ConditionEvaluator |
| **Switch** | Multiple cases: `{{field}} == "A"` → path1, `== "B"` → path2, default | Multi-output ConditionEvaluator |
| **Contains** | Check if text contains keyword/pattern | Regex match |
| **Confidence Gate** | Threshold on upstream LLM confidence score | Numeric comparison |
| **Time Window** | Only proceed during hours X-Y | datetime check |
| **Rate Limit** | Max N executions per time period | Counter with TTL |

### 4. Control Nodes (flow management)

| Node | Config | Implementation |
|------|--------|----------------|
| **Join (AND)** | Wait for ALL upstream branches to complete | Execution barrier |
| **Join (OR)** | Proceed when ANY upstream branch completes | First-complete trigger |
| **Merge** | Combine outputs from multiple branches into one payload | Data aggregation |
| **Loop** | Iterate over list from upstream output | Sequential re-execution |
| **Error Handler** | Catch failures from upstream, execute recovery path | Try/except wrapper |
| **Sub-Workflow** | Call another workflow as a node | Recursive execution |

---

## Data Model Evolution

### Current → New

```
Current:
  Order → OrderExecution (flat, single-action)

New:
  Workflow → WorkflowNode[] → WorkflowEdge[] (DAG)
  Workflow → WorkflowRun → NodeExecution[] (per-node tracking)
```

### New Schema

```python
@dataclass
class Workflow:
    id: str                              # wf-{12 hex chars}
    name: str
    description: str
    nodes: List[WorkflowNode]            # All nodes in the DAG
    edges: List[WorkflowEdge]            # Connections between nodes
    status: WorkflowStatus               # DRAFT, ACTIVE, INACTIVE, ERROR
    trigger_config: Dict                  # Denormalized trigger settings
    created_at: datetime
    updated_at: datetime
    run_count: int
    success_count: int
    last_run: Optional[WorkflowRun]
    tags: List[str]                      # User-defined categories

@dataclass
class WorkflowNode:
    id: str                              # node-{8 hex chars}
    workflow_id: str
    node_type: NodeType                  # TRIGGER, ACTION, CONDITION, CONTROL
    node_subtype: str                    # "schedule", "run_prompt", "if_else", etc.
    label: str                           # User-visible name
    config: Dict                         # Node-specific configuration
    position_x: float                    # Canvas position (for UI)
    position_y: float
    metadata: Dict                       # UI state (collapsed, color, notes)

@dataclass
class WorkflowEdge:
    id: str
    source_node_id: str
    target_node_id: str
    source_port: str                     # "output", "true", "false", "error"
    target_port: str                     # "input"
    condition_label: Optional[str]       # UI label on the edge

@dataclass
class WorkflowRun:
    id: str                              # run-{12 hex chars}
    workflow_id: str
    trigger_type: str                    # What initiated this run
    trigger_data: Dict                   # Trigger-specific context
    started_at: datetime
    completed_at: Optional[datetime]
    status: RunStatus                    # RUNNING, SUCCESS, PARTIAL, FAILED
    node_executions: List[NodeExecution] # Per-node results
    duration_ms: Optional[float]

@dataclass
class NodeExecution:
    id: str
    run_id: str
    node_id: str
    started_at: datetime
    completed_at: Optional[datetime]
    status: ExecutionStatus              # PENDING, RUNNING, SUCCESS, FAILED, SKIPPED
    input_data: Dict                     # What this node received
    output_data: Dict                    # What this node produced
    error_message: Optional[str]
    duration_ms: Optional[float]
```

### SQLite Tables

```sql
CREATE TABLE workflows (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    trigger_config TEXT DEFAULT '{}',  -- JSON
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    run_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    tags TEXT DEFAULT '[]',            -- JSON array
    user_id TEXT DEFAULT 'default'
);

CREATE TABLE workflow_nodes (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    node_type TEXT NOT NULL,
    node_subtype TEXT NOT NULL,
    label TEXT NOT NULL,
    config TEXT DEFAULT '{}',          -- JSON
    position_x REAL DEFAULT 0,
    position_y REAL DEFAULT 0,
    metadata TEXT DEFAULT '{}',        -- JSON
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
);

CREATE TABLE workflow_edges (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    source_node_id TEXT NOT NULL,
    target_node_id TEXT NOT NULL,
    source_port TEXT DEFAULT 'output',
    target_port TEXT DEFAULT 'input',
    condition_label TEXT,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
);

CREATE TABLE workflow_versions (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    snapshot TEXT NOT NULL,            -- Full JSON of nodes + edges at activation time
    created_at TEXT NOT NULL,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
);
CREATE INDEX idx_versions_workflow ON workflow_versions(workflow_id, version_number DESC);

CREATE TABLE workflow_runs (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    version_id TEXT,                   -- FK to workflow_versions (immutable for this run)
    trigger_type TEXT NOT NULL,
    trigger_data TEXT DEFAULT '{}',
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    duration_ms REAL,
    token_budget_used INTEGER DEFAULT 0,  -- Running token count
    token_budget_max INTEGER,             -- From workflow config (NULL = unlimited)
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE,
    FOREIGN KEY (version_id) REFERENCES workflow_versions(id)
);

CREATE TABLE node_executions (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    input_data TEXT DEFAULT '{}',
    output_data TEXT DEFAULT '{}',
    error_message TEXT,
    duration_ms REAL,
    FOREIGN KEY (run_id) REFERENCES workflow_runs(id) ON DELETE CASCADE
);
```

---

## DAG Execution Runtime

### Core Algorithm

```python
class DAGExecutor:
    """Executes a workflow DAG with structured concurrency and checkpoint recovery."""

    async def execute(self, workflow: Workflow, trigger_data: Dict) -> WorkflowRun:
        run = await self._create_run(workflow, trigger_data)
        graph = self._build_graph(workflow.nodes, workflow.edges)

        # Resume from checkpoint if recovering from crash
        if run.status == RunStatus.RECOVERING:
            graph = await self._restore_from_checkpoints(run, graph)

        # Start with trigger nodes (in-degree 0)
        ready = [n for n in workflow.nodes if graph.in_degree[n.id] == 0]

        while ready:
            # Execute all ready nodes in parallel using TaskGroup (not gather)
            results: Dict[str, Any] = {}
            async with asyncio.TaskGroup() as tg:
                for node in ready:
                    tg.create_task(self._execute_and_checkpoint(run, node, graph, results))
            # TaskGroup ensures all tasks complete or all are cancelled on failure

            # Determine which downstream nodes are now ready
            ready = []
            for node in list(results.keys()):
                result = results[node]
                active_ports = self._resolve_ports(graph.nodes[node], result)
                inactive_ports = self._get_inactive_ports(graph.nodes[node], active_ports)

                # Propagate DEAD_PATH signals along inactive ports
                for edge in graph.outgoing[node]:
                    if edge.source_port in inactive_ports:
                        await self._propagate_dead_path(graph, edge.target_node_id, run)

                # Activate downstream nodes on active ports
                for edge in graph.outgoing[node]:
                    if edge.source_port in active_ports:
                        target = graph.nodes[edge.target_node_id]
                        graph.in_degree[target.id] -= 1
                        graph.node_inputs[target.id][node] = result
                        if graph.in_degree[target.id] == 0:
                            ready.append(target)

            ready = self._check_joins(ready, graph)

        return await self._finalize_run(run)

    async def _execute_and_checkpoint(self, run, node, graph, results):
        """Execute node and persist output to SQLite for crash recovery."""
        result = await self._execute_node(run, node, graph)
        await self._checkpoint_node(run.id, node.id, result)  # Persist to node_executions
        results[node.id] = result

    async def _propagate_dead_path(self, graph, node_id, run):
        """Mark a node and all its downstream descendants as DEAD_PATH."""
        await self._checkpoint_node(run.id, node_id, status=NodeStatus.DEAD_PATH)
        graph.in_degree[node_id] = -1  # Sentinel: never becomes ready
        for edge in graph.outgoing.get(node_id, []):
            await self._propagate_dead_path(graph, edge.target_node_id, run)
```

### Variable Interpolation

Nodes pass data downstream via `output_data`. Downstream nodes reference upstream outputs using template syntax:

```
{{trigger.data.sender}}           — Trigger node output
{{node_abc123.output.text}}       — Specific node output
{{node_abc123.output.confidence}} — Numeric field
{{previous.output}}               — Shorthand for immediate upstream
```

Resolved at execution time by the runtime before each node executes.

### Condition Evaluation

```python
class ConditionEvaluator:
    """Evaluates condition expressions against node output data."""

    OPERATORS = {
        "==": operator.eq,
        "!=": operator.ne,
        ">": operator.gt,
        "<": operator.lt,
        ">=": operator.ge,
        "<=": operator.le,
        "contains": lambda a, b: b in str(a),
        "matches": lambda a, b: bool(re.search(b, str(a))),
        "is_empty": lambda a, _: not a,
        "is_not_empty": lambda a, _: bool(a),
    }

    def evaluate(self, expression: Dict, context: Dict) -> bool:
        field = self._resolve_variable(expression["field"], context)
        op = self.OPERATORS[expression["operator"]]
        value = expression.get("value")
        return op(field, value)
```

---

## Event Listener System

### Architecture

```python
class EventBus:
    """Central event dispatcher for non-time-based triggers."""

    _listeners: Dict[EventType, List[Callable]] = {}

    async def emit(self, event_type: EventType, data: Dict):
        for listener in self._listeners.get(event_type, []):
            await listener(data)

    def subscribe(self, event_type: EventType, callback: Callable):
        self._listeners.setdefault(event_type, []).append(callback)

class EventType(Enum):
    EMAIL_ARRIVED = "email_arrived"
    CALENDAR_SOON = "calendar_soon"         # Event starting within N minutes
    HEALTH_THRESHOLD = "health_threshold"
    MEMORY_STORED = "memory_stored"
    ORDER_FAILED = "order_failed"
    LEARNING_ALERT = "learning_alert"
    MARKET_CONDITION = "market_condition"    # Future: Trading module
    WEBHOOK_RECEIVED = "webhook_received"
    SERVER_STARTED = "server_started"
```

### Event Sources (Hybrid: OS-Native + Poll)

| Source | Method | Implementation |
|--------|--------|----------------|
| Email | **Poll (60s)** | `InboxManager.refresh()` → diff against last seen → emit `EMAIL_ARRIVED`. No native macOS push API for Mail. |
| Calendar | **OS-native** | `EKEventStore` observer via `NotificationCenter` (`EKEventStoreChanged`). Near-instant detection. |
| Reminders | **OS-native** | `EKEventStore` observer (shared with Calendar). |
| Filesystem | **OS-native** | `FSEvents` API for directory monitoring. Optimized for M1 storage controller. |
| Health | **On daily sync** | `HealthManager.sync()` hook → check thresholds → emit `HEALTH_THRESHOLD` |
| Memory | **On store** | `MemoryManager.store()` hook → emit `MEMORY_STORED` |
| System | **On event** | Direct emit from relevant managers |
| Webhook | **On request** | `/v1/workflows/{id}/trigger` → emit `WEBHOOK_RECEIVED`. HMAC-SHA256 verified. |
| Market | **Poll (configurable)** | Future: Trading module market data poller → emit `MARKET_CONDITION` |

### Trigger Registration

When a workflow with event triggers is activated, the WorkflowScheduler registers listeners:

```python
async def activate_workflow(self, workflow: Workflow):
    for node in workflow.trigger_nodes:
        if node.node_subtype == "email_arrival":
            self.event_bus.subscribe(
                EventType.EMAIL_ARRIVED,
                lambda data: self._check_and_execute(workflow, node, data)
            )
        elif node.node_subtype == "schedule":
            # Existing APScheduler path
            self.scheduler.add_job(...)
```

---

## macOS Canvas UI

### Technology Choice: SwiftUI Canvas

Use SwiftUI's `Canvas` view with `DragGesture` for the node editor. Not SceneKit (overkill for 2D), not WebView (latency, non-native feel).

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│ Workflows      [+ New Workflow]  [▶ Run]  [⏸ Pause]        │
├──────────┬──────────────────────────────────────────────────┤
│          │                                                   │
│ Workflow │              Canvas (DAG Editor)                  │
│ List     │                                                   │
│          │    [📧 Email] ──→ [🤖 Run Prompt] ──→ [📲 Notify] │
│ ▸ Morning│         │                                         │
│   Brief  │         ▼                                         │
│ ▸ Market │    [⚡ Condition] ──→ [📝 Log]                    │
│   Watch  │                                                   │
│ ▸ Weekly │                                                   │
│   Report │                                                   │
│          │                                                   │
├──────────┴──────────────────────────────────────────────────┤
│ Node Inspector                                               │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ Type: Run Prompt                                          │ │
│ │ Label: Summarize Email                                    │ │
│ │ Prompt: "Summarize this email: {{trigger.data.body}}"     │ │
│ │ Agent: Artemis (analysis)                                 │ │
│ │ Output preview: (last run result)                         │ │
│ └──────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ Execution History    [Run #47: ✅ 2.3s]  [Run #46: ✅ 1.8s] │
└─────────────────────────────────────────────────────────────┘
```

### Node Palette (drag from sidebar)

Organized by category with icons:

```
TRIGGERS          ACTIONS           CONDITIONS        CONTROL
⏰ Schedule       🤖 Run Prompt     ❓ If/Else        🔀 Join (AND)
📧 Email          🔧 Call Tool      🔀 Switch         ⚡ Join (OR)
📅 Calendar       📲 Notify         📊 Confidence     📦 Merge
❤️ Health         🧠 Create Memory  🕐 Time Window    🔄 Loop
🌐 Webhook        🔍 Extract Facts  🚦 Rate Limit     ⚠️ Error Handler
👆 Manual         🌐 HTTP Request                     📋 Sub-Workflow
📊 Market         ⏱ Delay
🔔 System         📝 Log
```

### Interaction Model

1. **Create node:** Drag from palette onto canvas
2. **Connect nodes:** Click source output port (highlights) → click target input port (connection created). More precise than drag, better for trackpad.
3. **Configure node:** Click node → Inspector panel populates with node-specific form
4. **Delete node/edge:** Select → Delete key (with confirmation for connected nodes)
5. **Move node:** Drag on canvas (edges follow)
6. **Zoom/Pan:** Scroll to zoom, two-finger drag to pan (standard macOS gestures). Semantic zoom: zoomed out = icons only, zoomed in = full config preview.
7. **Run workflow:** ▶ button (manual trigger, ignores trigger node config)
8. **View execution:** Click run in history → nodes light up green/red showing execution path with checkpoint data

### Visual Feedback During Execution

When a workflow is running, the canvas shows real-time state:
- **Running node:** Pulsing amber border
- **Completed node:** Green border + checkmark
- **Failed node:** Red border + X
- **Skipped node (condition false):** Dimmed, grey border
- **Pending node:** Default border, waiting
- **Edge carrying data:** Animated dot moving along the connection line

---

## Backend Module Structure

```
hestia/workflows/
├── models.py              # Workflow, WorkflowNode, WorkflowEdge, WorkflowRun, NodeExecution, WorkflowVersion
├── database.py            # SQLite CRUD (workflows, nodes, edges, versions, runs, node_executions)
├── manager.py             # WorkflowManager singleton (lifecycle, CRUD, version snapshotting)
├── executor.py            # DAGExecutor (TaskGroup, dead path elimination, checkpointing)
├── scheduler.py           # WorkflowScheduler (APScheduler + EventBus integration)
├── event_bus.py           # EventBus, EventType, EventListener, keyed debouncing
├── conditions.py          # ConditionEvaluator (expression engine + JMESPath)
├── interpolation.py       # Variable resolver (simple templates + JMESPath for complex JSON)
├── checkpoint.py          # Checkpoint manager (persist/restore node state for crash recovery)
├── token_budget.py        # Token budget tracker (per-workflow + per-node limits)
├── nodes/                 # Node implementations (one file per category)
│   ├── triggers.py        # ScheduleTrigger, EmailTrigger, CalendarTrigger, WebhookTrigger, etc.
│   ├── actions.py         # RunPromptAction, CallToolAction, NotifyAction, etc.
│   ├── conditions.py      # IfElseCondition, SwitchCondition, ConfidenceGate, etc.
│   └── control.py         # JoinAND, JoinOR, Merge, Loop, ErrorHandler, SubWorkflow
├── registry.py            # NodeRegistry (maps subtype → implementation class)
├── webhook_auth.py        # HMAC-SHA256 signature verification for inbound webhooks
└── migration.py           # Migrate existing Orders → single-node Workflows
```

### API Endpoints (New)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/workflows` | POST | Create workflow |
| `/v1/workflows` | GET | List workflows (with status/tag filters) |
| `/v1/workflows/{id}` | GET | Get workflow with full DAG (nodes + edges) |
| `/v1/workflows/{id}` | PUT | Update workflow (nodes, edges, config) |
| `/v1/workflows/{id}` | DELETE | Delete workflow + all runs |
| `/v1/workflows/{id}/activate` | POST | Activate (register triggers) |
| `/v1/workflows/{id}/deactivate` | POST | Deactivate (unregister triggers) |
| `/v1/workflows/{id}/trigger` | POST | Manual trigger / webhook |
| `/v1/workflows/{id}/runs` | GET | List execution history |
| `/v1/workflows/{id}/runs/{run_id}` | GET | Get run detail with per-node results |
| `/v1/workflows/{id}/duplicate` | POST | Clone workflow |
| `/v1/workflows/templates` | GET | Pre-built workflow templates |
| `/v1/workflows/import` | POST | Import from JSON |
| `/v1/workflows/{id}/export` | GET | Export as JSON |

### Migration from Orders

```python
async def migrate_orders_to_workflows():
    """Convert existing Orders into single-node Workflows."""
    orders = await order_manager.list_orders()
    for order in orders:
        workflow = Workflow(
            name=order.name,
            description=f"Migrated from Order {order.id}",
            nodes=[
                WorkflowNode(
                    node_type=NodeType.TRIGGER,
                    node_subtype="schedule",
                    label="Schedule",
                    config={"time": str(order.scheduled_time), "frequency": order.frequency.type.value}
                ),
                WorkflowNode(
                    node_type=NodeType.ACTION,
                    node_subtype="run_prompt",
                    label=order.name,
                    config={"prompt": order.prompt, "resources": [r.value for r in order.resources]}
                ),
            ],
            edges=[WorkflowEdge(source=trigger.id, target=action.id)],
            status=WorkflowStatus.ACTIVE if order.status == OrderStatus.ACTIVE else WorkflowStatus.INACTIVE
        )
        # Migrate execution history too
```

---

## Pre-Built Templates

Ship with workflow templates that cover common patterns:

1. **Morning Brief** — Schedule(8am) → RunPrompt("Summarize calendar, email, news") → Notify(iPhone)
2. **Email Triage** — EmailArrival(filter: important) → RunPrompt("Assess urgency") → IfElse(urgent?) → Notify(iPhone) / Log
3. **Health Alert** — HealthThreshold(steps < 5000, 3pm) → RunPrompt("Generate motivation") → Notify(macOS)
4. **Weekly Research Digest** — Schedule(Sunday 9am) → ExtractFacts(last 7 days) → RunPrompt("Synthesize patterns") → CreateMemory → Notify
5. **Market Watch** — Schedule(every 30min) → HTTPRequest(market API) → Condition(price change > 3%) → RunPrompt("Analyze movement") → Notify(iPhone)
6. **Memory Janitor** — Schedule(Sunday 2am) → RunPrompt("Review low-importance memories") → Loop(batch) → ExtractFacts → Log

---

## Phased Implementation

### Phase 1: Engine + Linear Flows (~35 hours)

**Backend:**
- Workflow/Node/Edge/Run/NodeExecution data models + SQLite tables
- DAGExecutor with `asyncio.TaskGroup` for parallel execution (not `gather`)
- Dead path elimination (propagate DEAD_PATH signals on inactive condition ports)
- SQLite checkpointing (persist node output on completion, resume from last checkpoint on crash)
- Workflow version snapshotting (`workflow_versions` table, `version_id` on `WorkflowRun`)
- WorkflowScheduler wrapping APScheduler
- 4 Action nodes: RunPrompt, CallTool, Notify, Log
- 2 Trigger nodes: Schedule, Manual
- Migration script (Orders → Workflows)
- 10 API endpoints
- Tests

**macOS UI:**
- Workflow list sidebar
- Basic canvas with drag-and-drop nodes
- Connection drawing (click source port → click target port, not drag)
- Node Inspector panel (config form per node type)
- Run button + execution history list
- Real-time execution feedback (green/red/amber node borders)

### Phase 2: Conditions + Branching (~18 hours)

**Backend:**
- ConditionEvaluator (expression engine)
- If/Else and Switch condition nodes
- Variable interpolation: simple `{{node.output.field}}` templates + JMESPath for complex JSON
- Optional Pydantic schemas for node I/O (type validation at boundaries, auto-retry on mismatch)
- Edge port routing (true/false/error paths)
- Confidence Gate node
- Keyed debouncing (hash of trigger type + metadata, leading/trailing modes)

**macOS UI:**
- Condition node with multiple output ports
- Edge labels showing condition
- Branch visualization (layout algorithm for diverging paths)

### Phase 3: Events + Advanced Control (~22 hours)

**Backend:**
- EventBus + EventListener infrastructure
- OS-level hooks: EventKit observers (calendar/reminders), FSEvents (filesystem)
- Poll-based: email (60s), health (daily sync hook)
- Email, Calendar, Health, Memory, Webhook trigger nodes
- HMAC-SHA256 webhook authentication (per-workflow secret in Keychain)
- Token budget enforcement (per-workflow + per-node `max_tokens`)
- Join (AND/OR), Merge, Loop control nodes
- Error Handler node
- Sub-Workflow node

**macOS UI:**
- Event trigger configuration (filter builders)
- Join node visualization (multiple inputs converging)
- Loop visualization
- Error path styling (red dashed edges)

### Phase 4: Polish + Templates (~10 hours)

- Pre-built workflow templates (6 shipped)
- Workflow export/import (JSON)
- Duplicate workflow
- Execution replay (step through a past run with checkpoint visualization)
- Semantic zoom (3 levels: icon-only → label+status → full config)
- Sugiyama auto-layout (with manual override persistence)
- Node search (find nodes across workflows)
- Keyboard shortcuts (Cmd+N new node, Delete, Cmd+Z undo)

---

## Total Estimated Effort (Revised Post-Gemini)

| Phase | Hours | Delivers |
|-------|-------|----------|
| Phase 1: Engine + Linear | 35 | Core DAG execution, checkpointing, basic canvas UI, migration |
| Phase 2: Conditions + Data | 18 | Branching, JMESPath, Pydantic schemas, keyed debouncing |
| Phase 3: Events + Control | 22 | OS-level hooks, HMAC webhooks, token budgets, advanced control |
| Phase 4: Polish | 10 | Templates, semantic zoom, Sugiyama layout, replay |
| **Total** | **85 hours (~7 sprint weeks)** |

---

## Key Design Decisions (Finalized)

| Decision | Resolution | Rationale |
|----------|-----------|-----------|
| Replace Orders entirely? | **Migrate to Workflows.** `/v1/orders` kept as deprecated aliases. | Superset — every Order is a 2-node workflow. |
| Canvas technology | **SwiftUI Canvas.** NSViewRepresentable fallback for 50+ nodes. | Consistency with app. SwiftUI `GraphicsContext` handles 2D well. |
| Node execution isolation | **In-process async** (TaskGroup). Ollama runs in separate process. | M1 single-user. LLM isolation via Ollama process boundary. |
| Parallel execution | **`asyncio.TaskGroup`** (not `gather`). | Structured concurrency, proper cleanup on partial failure. |
| Join edge case handling | **Dead path elimination.** Propagate DEAD_PATH signals on inactive condition ports. | Prevents AND-join deadlocks when branches are skipped. |
| Crash recovery | **SQLite checkpointing.** Persist node output on completion. Resume from last checkpoint. | 90% of Temporal's value at 10% complexity. |
| Workflow versioning | **Snapshot JSON on activate.** `WorkflowRun` bound to `version_id`. | Edits during execution don't affect in-progress runs. |
| Event triggers | **OS-native where possible** (EventKit, FSEvents). Poll only for email. | Lower latency, lower resource usage than universal 60s polling. |
| Webhook auth | **HMAC-SHA256.** Per-workflow secret in Keychain. Constant-time comparison. | Right model for single-user Tailscale setup. |
| Debouncing | **Keyed debouncing.** Hash of trigger type + metadata. Leading/trailing modes. | Per-context, not global. Email from boss ≠ email from newsletter. |
| Variable interpolation | **Simple templates (Phase 1) + JMESPath (Phase 2).** | Templates for 80% of cases. JMESPath for nested JSON transforms. |
| Node I/O types | **Optional Pydantic schemas (Phase 2).** Dynamic typing in Phase 1. | Enables auto-retry on LLM output mismatch. Progressive strictness. |
| Token budgets | **Per-workflow + per-node `max_tokens`.** | Prevents runaway cloud costs and M1 memory bandwidth starvation. |
| Max workflow complexity | **50 nodes per workflow.** | Prevents pathological DAGs. Sub-workflows for larger compositions. |
| Execution timeout | **Both.** Node default 60s, workflow default 300s. Configurable. | Defense-in-depth against hung inference. |
| Event bus persistence | **SQLite event log.** TTL 7 days. | Debugging. "Why did this workflow fire at 3am?" |
| Connection UX | **Click-click** (not click-drag). | More precise, better for trackpad. Drag reserved for node movement. |
| Zoom behavior | **Semantic zoom** (3 levels: icon → label → full config). | Prevents overwhelm at 30-50 nodes. |

---

## Relationship to Sprint 20 + Trading Module

This workflow engine is foundational for several downstream features:

- **Sprint 20 WS6 (Notification Relay):** Notify action node wraps the bump system
- **Sprint 21+ (Trading Module):** Market condition triggers, portfolio monitoring workflows
- **Principles Pipeline:** Auto-distillation can be a template workflow (Schedule → ExtractFacts → DistillPrinciples)
- **Memory Lifecycle:** Consolidation/pruning can be workflows instead of hardcoded scheduler loops

The engine effectively replaces `LearningScheduler` and `OrderScheduler` with a unified, visual, user-configurable orchestration layer. Andrew can see and modify any background process Hestia runs.

---

## Open Questions (Resolved by Gemini Review)

| Question | Resolution |
|----------|-----------|
| Webhook security | **HMAC-SHA256 signature verification.** Shared secret per workflow, `X-Hestia-Signature` header, constant-time comparison. |
| Concurrent runs | **Keyed debouncing.** Hash of trigger type + metadata as debounce key. Leading mode (first executes, rest suppressed within window) for email triggers. Trailing mode (wait for silence) for batch triggers. |
| Workflow sharing | **Yes — JSON export/import.** Confirmed in Phase 4. |
| Execution cost | **Token budget per workflow.** `max_tokens` config on workflow + per-node. Throttle parallel LLM nodes to prevent M1 memory bandwidth starvation. |
| Mobile view | Deferred. iOS stays command-center summary for now. |

## Open Questions (Remaining)

1. **EventKit permissions:** macOS Sequoia tightened Calendar/Reminders access. Need to verify entitlements for background EventKit observers.
2. **Sugiyama implementation:** Write our own or use a Swift port? No obvious SwiftUI-native Sugiyama library exists.
3. **Sub-workflow recursion depth:** Should sub-workflows be allowed to call other sub-workflows? If yes, what's the max depth?
4. **LearningScheduler migration timeline:** When do we migrate the 6 existing scheduler loops to workflows? Phase 4, or later?

---

## Gemini Review: Reconciliation Summary

### Critical Changes to Original Design

**1. `asyncio.TaskGroup` replaces `asyncio.gather`**
`gather` can kill successful parallel branches when a single branch fails. `TaskGroup` (Python 3.11+) provides structured concurrency with proper cleanup. All parallel execution in the DAG executor uses `TaskGroup`.

**2. Dead path elimination for joins**
When a condition node routes away from a branch, the downstream join must be notified that the signal will never arrive. Without this, AND-joins deadlock forever waiting for a branch that was skipped. Implementation: when a condition resolves, propagate "DEAD_PATH" signals along all inactive output ports. Joins track both completed and dead-path inputs.

**3. Checkpointing (not full event-sourcing)**
Persist each node's status + output to SQLite `node_executions` table upon completion. On crash recovery, the executor scans for the last `WorkflowRun` with status=RUNNING, identifies completed vs pending nodes, and resumes from the first incomplete node. This is 90% of Temporal's value at 10% of the complexity.

**4. Keyed debouncing replaces global rate limiting**
Instead of "max 1 execution per 5 minutes," use a debounce key = hash(trigger_type + metadata). Email from boss@company.com gets its own debounce window, separate from email from newsletter@spam.com. Two modes: leading (first-fires, suppress rest) and trailing (wait for silence, then batch).

**5. OS-level hooks replace polling for Calendar/Reminders/Files**
- Calendar + Reminders: `EKEventStore` observers via `NotificationCenter` (`EKEventStoreChanged`)
- Filesystem: `FSEvents` API for file monitoring triggers
- Email: Keep 60s polling (no native macOS push API for Mail)
- Health: Keep daily sync hook (no real-time HealthKit push on macOS)

**6. Click-click connection model (not click-drag)**
Click source port → port highlights → click target port → connection created. More precise, lower motor effort, better for trackpad users. Drag only for moving nodes on canvas.

**7. Semantic zoom levels**
- Zoomed out (>30 nodes visible): Icon + color only, no text
- Medium zoom (10-30 nodes): Icon + label + status badge
- Zoomed in (<10 nodes): Full config preview + last execution output

**8. Workflow version snapshotting**
When a workflow is activated/triggered, snapshot the full JSON to a `workflow_versions` table. `WorkflowRun` gets a `version_id` FK. Edits during execution don't affect in-progress runs.

**9. HMAC-SHA256 for webhook authentication**
Per-workflow shared secret stored in Keychain. Sender hashes payload with SHA-256, attaches `X-Hestia-Signature` header. Backend re-hashes and compares (constant-time). Prevents spoofed webhook triggers over Tailscale.

**10. Token budget pattern**
Per-workflow `max_tokens` limit. Per-node `max_tokens` limit. If a workflow exceeds its budget, remaining LLM nodes are skipped with status=BUDGET_EXCEEDED. Prevents runaway inference costs on cloud models and memory bandwidth starvation on local models.

### Changes to Phase Plan

**Phase 1 additions:** Checkpointing, `TaskGroup`, dead path elimination, version snapshotting
**Phase 2 additions:** JMESPath interpolation (alongside simple templates), Pydantic node I/O schemas, keyed debouncing
**Phase 3 additions:** EventKit/FSEvents observers (replacing polling), HMAC webhook auth, token budget enforcement
**Phase 4 additions:** Semantic zoom, Sugiyama auto-layout, execution replay with checkpoint visualization

### Revised Effort Estimates

| Phase | Original Hours | Revised Hours | Delta | Reason |
|-------|---------------|---------------|-------|--------|
| Phase 1 | 30 | 35 | +5 | Checkpointing, dead path elimination, version snapshotting |
| Phase 2 | 15 | 18 | +3 | JMESPath, Pydantic schemas, keyed debouncing |
| Phase 3 | 20 | 22 | +2 | EventKit/FSEvents integration, HMAC auth |
| Phase 4 | 10 | 10 | 0 | Semantic zoom replaces simpler zoom; net neutral |
| **Total** | **75** | **85** | **+10** | More robust but +10h is justified by crash recovery + security |

### Gemini's "Over-Engineering" Challenge — Assessment

Gemini asked whether linear chains with branches would deliver 80% of value at 20% complexity. **Assessment: right for Phase 1, wrong long-term.** Andrew's use cases (trading module monitoring, multi-source briefings, health + calendar compound triggers) genuinely need parallel branches and joins. The Phase 1 UX guides toward simple linear flows — the DAG engine supports full complexity but doesn't require it. Users graduate to complexity.

Gemini suggested embedding `async-graph-data-flow` library. **Assessment: too minimal.** No condition routing, no join semantics, no checkpoint persistence. The integration depth with Hestia's inference pipeline, tool executor, and notification relay makes custom the right call.
