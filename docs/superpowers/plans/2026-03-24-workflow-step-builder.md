# Workflow Step Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable users to create, configure, and link workflow steps from the React Flow canvas, where each "Step" (Title/Trigger/Prompt/Resources) compiles to backend DAG nodes transparently.

**Architecture:** The UI presents Andrew's "Step" mental model (Title, Trigger, Prompt, Resources). A translation layer in TypeScript converts each Step into one or more backend nodes (e.g., a Step with both Prompt and Resources becomes `run_prompt` with `allowed_tools`). The backend gains a DELAY node type for per-step timing and a resource catalog endpoint so the UI can show categorized tool pickers. One vertical slice (Prompt Step end-to-end) validates the architecture before building all step types.

**Tech Stack:** Python/FastAPI (backend), React Flow v12 + TypeScript (canvas), SwiftUI (inspector), WKWebView bridge (Swift↔JS)

**Second Opinion Reference:** `docs/plans/workflow-step-builder-second-opinion-2026-03-24.md`
**Discovery Reference:** `docs/discoveries/workflow-step-builder-ux-2026-03-24.md`

---

## File Structure

### Backend (Python)
| File | Action | Responsibility |
|------|--------|----------------|
| `hestia/workflows/models.py` | Modify | Add `NodeType.DELAY` enum value |
| `hestia/workflows/nodes.py` | Modify | Add `execute_delay()` executor, register in `NODE_EXECUTORS` |
| `hestia/api/routes/workflows.py` | Modify | Add `POST /{wf_id}/nodes/from-step` endpoint (Step→nodes translation) |
| `hestia/api/routes/tools.py` | Modify | Enhance existing `GET /tools/categories` to include labels, icons, and parameter schemas |
| `tests/test_workflow_delay_node.py` | Create | Tests for DELAY executor |
| `tests/test_workflow_step_translation.py` | Create | Tests for Step→DAG node translation |
| `tests/test_tool_categories.py` | Create | Tests for enhanced tool categories endpoint |

### React Flow Canvas (TypeScript)
| File | Action | Responsibility |
|------|--------|----------------|
| `HestiaApp/WorkflowCanvas/src/App.tsx` | Modify | Register custom node types, add "+" button on edges, canvas context menu |
| `HestiaApp/WorkflowCanvas/src/bridge.ts` | Modify | Add `addStep` and `requestToolCategories` message types |
| `HestiaApp/WorkflowCanvas/src/nodes/PromptNode.tsx` | Create | Custom node for RUN_PROMPT (icon, label, truncated prompt) |
| `HestiaApp/WorkflowCanvas/src/nodes/ToolNode.tsx` | Create | Custom node for CALL_TOOL (tool icon, name) |
| `HestiaApp/WorkflowCanvas/src/nodes/ConditionNode.tsx` | Create | Custom node for IF_ELSE/SWITCH (diamond-ish, typed handles) |
| `HestiaApp/WorkflowCanvas/src/nodes/ActionNode.tsx` | Create | Custom node for NOTIFY/LOG (bell/log icon) |
| `HestiaApp/WorkflowCanvas/src/nodes/TriggerNode.tsx` | Create | Custom node for SCHEDULE/MANUAL (clock/play icon) |
| `HestiaApp/WorkflowCanvas/src/nodes/DelayNode.tsx` | Create | Custom node for DELAY (timer icon, duration label) |
| `HestiaApp/WorkflowCanvas/src/nodes/constants.ts` | Create | Shared node colors (extracted to avoid circular imports) |
| `HestiaApp/WorkflowCanvas/src/nodes/index.ts` | Create | Export nodeTypes map for React Flow registration |
| `HestiaApp/WorkflowCanvas/src/components/AddStepMenu.tsx` | Create | Popover menu for selecting step type (shown on edge "+" or right-click) |

### Swift (macOS)
| File | Action | Responsibility |
|------|--------|----------------|
| `HestiaApp/macOS/Views/Workflow/WorkflowCanvasWebView.swift` | Modify | Handle `addStep` bridge message, call new translation endpoint |
| `HestiaApp/macOS/Views/Workflow/MacNodeInspectorView.swift` | Modify | Add DELAY config editor, add resource picker to RUN_PROMPT |
| `HestiaApp/macOS/ViewModels/MacWorkflowViewModel.swift` | Modify | Add `addStepFromCanvas()`, `fetchToolCategories()` methods |
| `HestiaApp/macOS/Services/APIClient+Workflows.swift` | Modify | Add `createNodeFromStep()`, `getToolCategories()` API methods |
| `HestiaApp/macOS/Models/WorkflowModels.swift` | Modify | Add `StepCreateRequest`, `ToolCategory`, `DelayNode` models |

---

## Task Sequence

### Task 1: DELAY Node Type (Backend)

**Files:**
- Modify: `hestia/workflows/models.py:54-66`
- Modify: `hestia/workflows/nodes.py:293-304`
- Create: `tests/test_workflow_delay_node.py`

**Context:** The backend has 8 node types. We're adding a 9th: DELAY. This node pauses execution for a configured number of seconds. It enables per-step timing ("wait 5 minutes, then run the next step"). The executor uses `asyncio.sleep()`. This is the simplest possible implementation — no cron, no scheduling, just a pause between nodes.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_workflow_delay_node.py
"""Tests for DELAY node executor."""
import asyncio
import pytest
from hestia.workflows.models import NodeType
from hestia.workflows.nodes import execute_delay, NODE_EXECUTORS


class TestDelayNode:
    """Tests for the DELAY node executor."""

    @pytest.mark.asyncio
    async def test_delay_returns_elapsed(self):
        """DELAY node should sleep and report elapsed time."""
        config = {"delay_seconds": 0.1}
        result = await execute_delay(config, {"input": "data"})
        assert result["delayed"] is True
        assert result["delay_seconds"] == 0.1
        assert "elapsed_ms" in result

    @pytest.mark.asyncio
    async def test_delay_zero_seconds(self):
        """Zero delay should complete immediately."""
        config = {"delay_seconds": 0}
        result = await execute_delay(config, {})
        assert result["delayed"] is True
        assert result["delay_seconds"] == 0

    @pytest.mark.asyncio
    async def test_delay_missing_config(self):
        """Missing delay_seconds should default to 0."""
        result = await execute_delay({}, {})
        assert result["delayed"] is True
        assert result["delay_seconds"] == 0

    @pytest.mark.asyncio
    async def test_delay_max_capped(self):
        """Delay should be capped at 3600 seconds (1 hour)."""
        config = {"delay_seconds": 99999}
        result = await execute_delay(config, {})
        assert result["delay_seconds"] == 3600

    @pytest.mark.asyncio
    async def test_delay_passes_input_through(self):
        """DELAY should pass input_data through as output (transparent pipe)."""
        config = {"delay_seconds": 0}
        input_data = {"response": "hello", "tokens": 42}
        result = await execute_delay(config, input_data)
        assert result["input_data"] == input_data

    def test_delay_registered_in_executors(self):
        """DELAY should be registered in NODE_EXECUTORS."""
        assert NodeType.DELAY in NODE_EXECUTORS

    def test_delay_in_node_type_enum(self):
        """DELAY should be a valid NodeType."""
        assert NodeType.DELAY.value == "delay"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_workflow_delay_node.py -v`
Expected: FAIL — `AttributeError: 'NodeType' has no attribute 'DELAY'`

- [ ] **Step 3: Add DELAY to NodeType enum**

In `hestia/workflows/models.py`, add after line 66 (`MANUAL = "manual"`):

```python
    # Timing nodes
    DELAY = "delay"
```

- [ ] **Step 4: Implement execute_delay executor**

In `hestia/workflows/nodes.py`, add before the `NODE_EXECUTORS` dict:

```python
async def execute_delay(
    config: Dict[str, Any],
    input_data: Dict[str, Any],
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Execute a Delay node — pauses execution for configured seconds.

    Config keys:
        delay_seconds (float): How long to wait (max 3600, default 0)

    Returns input_data passthrough plus delay metadata.
    """
    import time

    delay = float(config.get("delay_seconds", 0))
    delay = max(0, min(delay, 3600))  # Cap at 1 hour

    start = time.monotonic()
    if delay > 0:
        await asyncio.sleep(delay)
    elapsed_ms = int((time.monotonic() - start) * 1000)

    return {
        "delayed": True,
        "delay_seconds": delay,
        "elapsed_ms": elapsed_ms,
        "input_data": input_data,
    }
```

Add `import asyncio` to the imports at the top of nodes.py (if not already present).

Register in `NODE_EXECUTORS`:

```python
NODE_EXECUTORS: Dict[NodeType, NodeExecutorFn] = {
    NodeType.RUN_PROMPT: execute_run_prompt,
    NodeType.CALL_TOOL: execute_call_tool,
    NodeType.NOTIFY: execute_notify,
    NodeType.LOG: execute_log,
    NodeType.IF_ELSE: execute_if_else,
    NodeType.SWITCH: execute_switch,
    NodeType.SCHEDULE: execute_trigger_noop,
    NodeType.MANUAL: execute_trigger_noop,
    NodeType.DELAY: execute_delay,
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_workflow_delay_node.py -v`
Expected: 7 passed

- [ ] **Step 6: Run full workflow test suite**

Run: `python -m pytest tests/test_workflow_*.py -v --timeout=30`
Expected: All pass (DELAY enum addition should not break existing tests)

- [ ] **Step 7: Commit**

```bash
git add hestia/workflows/models.py hestia/workflows/nodes.py tests/test_workflow_delay_node.py
git commit -m "feat(workflow): DELAY node type — asyncio.sleep executor with 1h cap"
```

---

### Task 2: Enhance Tool Categories Endpoint (Backend)

**Files:**
- Modify: `hestia/api/routes/tools.py:91-120`
- Create: `tests/test_tool_categories.py`

**Context:** `GET /v1/tools/categories` already exists in `hestia/api/routes/tools.py` but returns a minimal format: `{"categories": {"calendar": {"count": 2, "tools": ["list_events", ...]}}}`. The Step Builder needs a richer format with human-readable labels, SF Symbol icons, and parameter schemas per tool. We'll enhance the existing endpoint (backward-compatible — adds new fields to the response).

The existing code uses `get_tool_registry()` from `hestia.execution` (synchronous, returns singleton registry). Follow this pattern exactly.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tool_categories.py
"""Tests for enhanced tool categories endpoint."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from hestia.api.server import app


@pytest.fixture
def mock_registry():
    """Create a mock ToolRegistry with categorized tools."""
    from hestia.execution.models import Tool, ToolParam, ToolParamType

    dummy_handler = AsyncMock()

    tools = [
        Tool(
            name="list_events",
            description="List calendar events",
            parameters={"start_date": ToolParam(type=ToolParamType.STRING, description="Start date", required=True)},
            handler=dummy_handler,
            category="calendar",
        ),
        Tool(
            name="create_event",
            description="Create a calendar event",
            parameters={"title": ToolParam(type=ToolParamType.STRING, description="Event title", required=True)},
            handler=dummy_handler,
            category="calendar",
        ),
        Tool(
            name="read_file",
            description="Read a file",
            parameters={"path": ToolParam(type=ToolParamType.STRING, description="File path", required=True)},
            handler=dummy_handler,
            category="file",
        ),
    ]

    registry = MagicMock()
    registry.list_tools.return_value = tools
    registry.__len__ = lambda self: 3
    return registry


@pytest.fixture
def mock_auth():
    """Skip JWT auth for tests."""
    with patch("hestia.api.routes.tools.get_device_token", return_value="test-token"):
        yield


class TestToolCategoriesEnhanced:
    """Tests for enhanced GET /v1/tools/categories."""

    @pytest.mark.asyncio
    async def test_returns_grouped_tools_with_metadata(self, mock_registry, mock_auth):
        """Should return tools grouped by category with labels and icons."""
        with patch("hestia.api.routes.tools.get_tool_registry", return_value=mock_registry):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="https://test") as client:
                resp = await client.get(
                    "/v1/tools/categories",
                    headers={"Authorization": "Bearer test-token"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data

        cats = {c["id"]: c for c in data["categories"]}
        assert "calendar" in cats
        assert "file" in cats
        assert len(cats["calendar"]["tools"]) == 2
        assert len(cats["file"]["tools"]) == 1

    @pytest.mark.asyncio
    async def test_categories_have_labels_and_icons(self, mock_registry, mock_auth):
        """Each category should have a human-readable label and SF Symbol icon."""
        with patch("hestia.api.routes.tools.get_tool_registry", return_value=mock_registry):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="https://test") as client:
                resp = await client.get(
                    "/v1/tools/categories",
                    headers={"Authorization": "Bearer test-token"},
                )

        data = resp.json()
        for cat in data["categories"]:
            assert "id" in cat
            assert "label" in cat
            assert "icon" in cat
            assert "tools" in cat

        cal = next(c for c in data["categories"] if c["id"] == "calendar")
        assert cal["label"] == "Calendar"
        assert cal["icon"] == "calendar"

    @pytest.mark.asyncio
    async def test_tool_entries_have_schema(self, mock_registry, mock_auth):
        """Each tool entry should include name, description, and parameter schema."""
        with patch("hestia.api.routes.tools.get_tool_registry", return_value=mock_registry):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="https://test") as client:
                resp = await client.get(
                    "/v1/tools/categories",
                    headers={"Authorization": "Bearer test-token"},
                )

        data = resp.json()
        cal_cat = next(c for c in data["categories"] if c["id"] == "calendar")
        tool = cal_cat["tools"][0]
        assert "name" in tool
        assert "description" in tool
        assert "parameters" in tool
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_tool_categories.py -v --timeout=30`
Expected: FAIL — response format doesn't match (old format is dict-keyed, tests expect array with `id`/`label`/`icon`)

- [ ] **Step 3: Enhance the existing endpoint**

In `hestia/api/routes/tools.py`, first add the category metadata constant near the top (after imports):

```python
# Human-readable labels and SF Symbol icons for the Step Builder resource picker
TOOL_CATEGORY_META: Dict[str, Dict[str, str]] = {
    "calendar": {"label": "Calendar", "icon": "calendar"},
    "reminders": {"label": "Reminders", "icon": "checklist"},
    "notes": {"label": "Notes", "icon": "note.text"},
    "mail": {"label": "Mail", "icon": "envelope"},
    "file": {"label": "Files", "icon": "folder"},
    "code": {"label": "Code", "icon": "chevron.left.forwardslash.chevron.right"},
    "git": {"label": "Git", "icon": "arrow.triangle.branch"},
    "shell": {"label": "Shell", "icon": "terminal"},
    "health": {"label": "Health", "icon": "heart.fill"},
    "trading": {"label": "Trading", "icon": "chart.line.uptrend.xyaxis"},
    "investigate": {"label": "Web", "icon": "globe"},
    "general": {"label": "General", "icon": "wrench"},
}
```

Then replace the `list_categories` function body (lines ~95-120):

```python
async def list_categories(
    device_id: str = Depends(get_device_token),
) -> dict:
    """
    List all tool categories with tool details, labels, and icons.

    Returns a structured array of categories, each with human-readable
    metadata and full tool schemas for the workflow Step Builder.
    """
    registry = get_tool_registry()

    # Group tools by category
    groups: Dict[str, list] = {}
    for tool in registry.list_tools():
        cat = tool.category or "general"
        if cat not in groups:
            groups[cat] = []
        groups[cat].append({
            "name": tool.name,
            "description": tool.description,
            "parameters": {
                name: param.to_json_schema()
                for name, param in tool.parameters.items()
            },
            "requires_approval": tool.requires_approval,
        })

    # Build response with metadata
    categories = []
    for cat_id, tools in sorted(groups.items()):
        meta = TOOL_CATEGORY_META.get(cat_id, {"label": cat_id.title(), "icon": "wrench"})
        categories.append({
            "id": cat_id,
            "label": meta["label"],
            "icon": meta["icon"],
            "tools": sorted(tools, key=lambda t: t["name"]),
            "count": len(tools),
        })

    return {
        "categories": categories,
        "total_tools": len(registry),
    }
```

Note: `count` per category and `total_tools` are preserved for backward compatibility.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_tool_categories.py -v --timeout=30`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add hestia/api/routes/tools.py tests/test_tool_categories.py
git commit -m "feat(workflow): enhance GET /v1/tools/categories — add labels, icons, parameter schemas"
```

---

### Task 3: Step-to-DAG Translation Endpoint (Backend)

**Files:**
- Modify: `hestia/api/routes/workflows.py`
- Create: `tests/test_workflow_step_translation.py`

**Context:** This is the "compiler" — the key architectural piece identified by the second opinion. Andrew's "Step" has: Title, Trigger (immediate/after delay/scheduled), Prompt (LLM instructions), and Resources (tool categories). The backend needs individual nodes. This endpoint takes a Step definition and creates the correct backend nodes + edges:

- **Prompt Step** → one `run_prompt` node (with `allowed_tools` from selected resources)
- **Prompt Step + Delay trigger** → `delay` node → `run_prompt` node (two nodes, one edge)
- **Tool Step** (no prompt, just resources) → one `call_tool` node
- **Notification Step** → one `notify` node

The endpoint also handles edge insertion: if `afterNodeId` is provided, it creates edges to connect the new node(s) into the existing DAG.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_workflow_step_translation.py
"""Tests for Step-to-DAG node translation endpoint."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from hestia.api.server import app


@pytest.fixture
def mock_auth():
    with patch("hestia.api.routes.workflows.get_device_token", return_value="test-token"):
        yield


@pytest.fixture
def mock_manager():
    """Mock WorkflowManager that returns predictable node IDs."""
    manager = AsyncMock()

    call_count = 0
    async def mock_add_node(**kwargs):
        nonlocal call_count
        call_count += 1
        node = MagicMock()
        node.id = f"node-test-{call_count:03d}"
        node.to_dict.return_value = {
            "id": node.id,
            "node_type": kwargs.get("node_type", "run_prompt"),
            "label": kwargs.get("label", ""),
            "config": kwargs.get("config", {}),
            "position_x": kwargs.get("position_x", 0),
            "position_y": kwargs.get("position_y", 0),
        }
        return node

    manager.add_node = mock_add_node

    async def mock_add_edge(**kwargs):
        edge = MagicMock()
        edge.id = "edge-test-001"
        edge.to_dict.return_value = {
            "id": edge.id,
            "source_node_id": kwargs.get("source_node_id"),
            "target_node_id": kwargs.get("target_node_id"),
        }
        return edge

    manager.add_edge = mock_add_edge

    return manager


class TestStepTranslation:
    """Tests for POST /v1/workflows/{id}/nodes/from-step."""

    @pytest.mark.asyncio
    async def test_prompt_step_creates_run_prompt_node(self, mock_auth, mock_manager):
        """A Step with a prompt and no delay → single run_prompt node."""
        with patch("hestia.api.routes.workflows.get_workflow_manager", return_value=mock_manager):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="https://test") as client:
                resp = await client.post(
                    "/v1/workflows/wf-test/nodes/from-step",
                    json={
                        "title": "Summarize Email",
                        "prompt": "Summarize the latest unread emails",
                        "trigger": "immediate",
                        "resources": ["calendar", "mail"],
                        "position_x": 300,
                        "position_y": 200,
                    },
                    headers={"Authorization": "Bearer test-token"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) == 1
        node = data["nodes"][0]
        assert node["node_type"] == "run_prompt"
        assert node["label"] == "Summarize Email"

    @pytest.mark.asyncio
    async def test_delayed_step_creates_delay_plus_prompt(self, mock_auth, mock_manager):
        """A Step with delay trigger → DELAY node + run_prompt node + connecting edge."""
        with patch("hestia.api.routes.workflows.get_workflow_manager", return_value=mock_manager):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="https://test") as client:
                resp = await client.post(
                    "/v1/workflows/wf-test/nodes/from-step",
                    json={
                        "title": "Wait then Notify",
                        "prompt": "Generate a summary",
                        "trigger": "delay",
                        "delay_seconds": 300,
                        "position_x": 300,
                        "position_y": 200,
                    },
                    headers={"Authorization": "Bearer test-token"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) == 2
        assert data["nodes"][0]["node_type"] == "delay"
        assert data["nodes"][1]["node_type"] == "run_prompt"
        assert len(data["edges"]) >= 1  # delay → prompt edge

    @pytest.mark.asyncio
    async def test_step_with_after_node_creates_edge(self, mock_auth, mock_manager):
        """When afterNodeId is provided, an edge is created from that node to the new node."""
        with patch("hestia.api.routes.workflows.get_workflow_manager", return_value=mock_manager):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="https://test") as client:
                resp = await client.post(
                    "/v1/workflows/wf-test/nodes/from-step",
                    json={
                        "title": "Next Step",
                        "prompt": "Do something",
                        "trigger": "immediate",
                        "after_node_id": "node-existing-001",
                        "position_x": 300,
                        "position_y": 400,
                    },
                    headers={"Authorization": "Bearer test-token"},
                )

        assert resp.status_code == 200
        data = resp.json()
        # Should have edge from existing node to new node
        edges = data["edges"]
        assert any(e["source_node_id"] == "node-existing-001" for e in edges)

    @pytest.mark.asyncio
    async def test_resources_mapped_to_allowed_tools(self, mock_auth, mock_manager):
        """Resource categories should be expanded to tool names in allowed_tools config."""
        with patch("hestia.api.routes.workflows.get_workflow_manager", return_value=mock_manager):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="https://test") as client:
                resp = await client.post(
                    "/v1/workflows/wf-test/nodes/from-step",
                    json={
                        "title": "Check Calendar",
                        "prompt": "What's on my calendar today?",
                        "trigger": "immediate",
                        "resources": ["calendar"],
                        "position_x": 300,
                        "position_y": 200,
                    },
                    headers={"Authorization": "Bearer test-token"},
                )

        assert resp.status_code == 200
        # The run_prompt node's config should have allowed_tools populated
        # from the "calendar" category tools
        node = resp.json()["nodes"][0]
        config = node["config"]
        assert "allowed_tools" in config
        assert isinstance(config["allowed_tools"], list)
        assert len(config["allowed_tools"]) > 0

    @pytest.mark.asyncio
    async def test_step_without_prompt_rejected(self, mock_auth, mock_manager):
        """A Step must have a prompt (for now — tool-only steps come later)."""
        with patch("hestia.api.routes.workflows.get_workflow_manager", return_value=mock_manager):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="https://test") as client:
                resp = await client.post(
                    "/v1/workflows/wf-test/nodes/from-step",
                    json={
                        "title": "No Prompt",
                        "trigger": "immediate",
                        "position_x": 300,
                        "position_y": 200,
                    },
                    headers={"Authorization": "Bearer test-token"},
                )

        assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_workflow_step_translation.py -v --timeout=30`
Expected: FAIL — 404 or 405 (endpoint doesn't exist)

- [ ] **Step 3: Implement the translation endpoint**

In `hestia/api/routes/workflows.py`, add a Pydantic request model and the endpoint:

```python
from pydantic import BaseModel
from typing import List, Optional


class StepCreateRequest(BaseModel):
    """
    A user-facing 'Step' that compiles to one or more backend DAG nodes.

    The Step Builder UI sends this; the backend translates it to nodes + edges.
    """
    title: str
    prompt: Optional[str] = None
    trigger: str = "immediate"  # "immediate" | "delay"
    delay_seconds: Optional[float] = None
    resources: Optional[List[str]] = None  # Category IDs: ["calendar", "mail"]
    position_x: float = 0
    position_y: float = 0
    after_node_id: Optional[str] = None  # Insert after this node in the DAG


def _expand_resource_categories(categories: List[str]) -> List[str]:
    """Expand resource category IDs to individual tool names."""
    from hestia.execution import get_tool_registry

    registry = get_tool_registry()
    tool_names = []
    for cat in categories:
        tools = registry.get_tools_by_category(cat)
        tool_names.extend(t.name for t in tools)
    return tool_names


@router.post("/{workflow_id}/nodes/from-step")
async def create_node_from_step(
    workflow_id: str,
    request: StepCreateRequest,
    _token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """
    Create workflow node(s) from a user-facing Step definition.

    Translates the Step model (Title/Trigger/Prompt/Resources) into
    one or more backend DAG nodes. This is the 'compiler' between
    the Step Builder UI and the workflow engine.
    """
    if not request.prompt:
        return JSONResponse({"error": "Step must have a prompt"}, status_code=400)

    manager = await get_workflow_manager()
    created_nodes = []
    created_edges = []

    # Resolve resource categories → tool names
    allowed_tools = None
    if request.resources:
        allowed_tools = _expand_resource_categories(request.resources)

    # Track position for stacked nodes
    pos_x = request.position_x
    pos_y = request.position_y
    first_node_id = None

    # If delayed trigger, insert a DELAY node first
    if request.trigger == "delay" and request.delay_seconds:
        delay_node = await manager.add_node(
            workflow_id=workflow_id,
            node_type="delay",
            label=f"Wait {int(request.delay_seconds)}s",
            config={"delay_seconds": request.delay_seconds},
            position_x=pos_x,
            position_y=pos_y,
        )
        created_nodes.append(delay_node.to_dict())
        first_node_id = delay_node.id
        pos_y += 150  # Stack the prompt node below

    # Create the main run_prompt node
    prompt_config = {"prompt": request.prompt}
    if allowed_tools:
        prompt_config["allowed_tools"] = allowed_tools

    prompt_node = await manager.add_node(
        workflow_id=workflow_id,
        node_type="run_prompt",
        label=request.title,
        config=prompt_config,
        position_x=pos_x,
        position_y=pos_y,
    )
    created_nodes.append(prompt_node.to_dict())

    # Connect delay → prompt if delay was created
    if first_node_id:
        edge = await manager.add_edge(
            workflow_id=workflow_id,
            source_node_id=first_node_id,
            target_node_id=prompt_node.id,
        )
        created_edges.append(edge.to_dict())
    else:
        first_node_id = prompt_node.id

    # Connect after_node → first new node
    if request.after_node_id:
        edge = await manager.add_edge(
            workflow_id=workflow_id,
            source_node_id=request.after_node_id,
            target_node_id=first_node_id or prompt_node.id,
        )
        created_edges.append(edge.to_dict())

    return {
        "nodes": created_nodes,
        "edges": [e for e in created_edges],
    }
```

**Important:** `get_workflow_manager` is imported at the top of `workflows.py` (`from hestia.workflows.manager import get_workflow_manager`) and called as `manager = await get_workflow_manager()`. `manager.add_edge()` takes `(workflow_id, source_node_id, target_node_id, edge_label="")` — verify this matches. `_expand_resource_categories` uses `get_tool_registry()` from `hestia.execution` which is a synchronous singleton (NOT `ToolExecutor()` which would create a new instance each call).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_workflow_step_translation.py -v --timeout=30`
Expected: 5 passed

- [ ] **Step 5: Run full workflow test suite**

Run: `python -m pytest tests/test_workflow_*.py -v --timeout=30`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add hestia/api/routes/workflows.py tests/test_workflow_step_translation.py
git commit -m "feat(workflow): POST /nodes/from-step — Step-to-DAG translation endpoint"
```

---

### Task 4: Swift Models + API Client (iOS/macOS)

**Files:**
- Modify: `HestiaApp/macOS/Models/WorkflowModels.swift`
- Modify: `HestiaApp/macOS/Services/APIClient+Workflows.swift`

**Context:** Add Swift types for the new endpoints (Step creation, tool categories) and the DELAY node type. The macOS app needs these models to call the translation endpoint and display the resource picker.

- [ ] **Step 1: Add DELAY to NodeType enum**

In `HestiaApp/macOS/Models/WorkflowModels.swift`, find the `WorkflowNodeType` enum and add:

```swift
case delay
```

- [ ] **Step 2: Add StepCreateRequest model**

```swift
struct StepCreateRequest: Codable {
    let title: String
    let prompt: String?
    let trigger: String  // "immediate" | "delay"
    let delaySeconds: Double?
    let resources: [String]?  // Category IDs
    let positionX: Double
    let positionY: Double
    let afterNodeId: String?

    enum CodingKeys: String, CodingKey {
        case title, prompt, trigger, resources
        case delaySeconds = "delay_seconds"
        case positionX = "position_x"
        case positionY = "position_y"
        case afterNodeId = "after_node_id"
    }
}

struct StepCreateResponse: Codable {
    let nodes: [WorkflowNodeResponse]
    let edges: [WorkflowEdgeResponse]
}
```

- [ ] **Step 3: Add ToolCategory models**

```swift
struct ToolCategoryResponse: Codable {
    let categories: [ToolCategory]
}

struct ToolCategory: Codable, Identifiable {
    let id: String
    let label: String
    let icon: String
    let tools: [ToolSummary]
}

struct ToolSummary: Codable, Identifiable {
    let name: String
    let description: String
    let parameters: [String: AnyCodableValue]
    let requiresApproval: Bool

    var id: String { name }

    enum CodingKeys: String, CodingKey {
        case name, description, parameters
        case requiresApproval = "requires_approval"
    }
}
```

- [ ] **Step 4: Add API client methods**

In `HestiaApp/macOS/Services/APIClient+Workflows.swift`, add:

```swift
// MARK: - Step Builder

func createNodeFromStep(_ workflowId: String, step: StepCreateRequest) async throws -> StepCreateResponse {
    return try await post("/workflows/\(workflowId)/nodes/from-step", body: step)
}

func getToolCategories() async throws -> ToolCategoryResponse {
    return try await get("/tools/categories")
}
```

- [ ] **Step 5: Build both targets**

Run:
```bash
cd HestiaApp && xcodegen generate && cd ..
xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build CODE_SIGNING_ALLOWED=NO 2>&1 | tail -5
```
Expected: BUILD SUCCEEDED

- [ ] **Step 6: Commit**

```bash
git add HestiaApp/macOS/Models/WorkflowModels.swift HestiaApp/macOS/Services/APIClient+Workflows.swift
git commit -m "feat(workflow): Swift models for Step Builder — StepCreateRequest, ToolCategory, DELAY type"
```

---

### Task 5: Custom React Flow Node Components

**Files:**
- Create: `HestiaApp/WorkflowCanvas/src/nodes/PromptNode.tsx`
- Create: `HestiaApp/WorkflowCanvas/src/nodes/ToolNode.tsx`
- Create: `HestiaApp/WorkflowCanvas/src/nodes/ConditionNode.tsx`
- Create: `HestiaApp/WorkflowCanvas/src/nodes/ActionNode.tsx`
- Create: `HestiaApp/WorkflowCanvas/src/nodes/TriggerNode.tsx`
- Create: `HestiaApp/WorkflowCanvas/src/nodes/DelayNode.tsx`
- Create: `HestiaApp/WorkflowCanvas/src/nodes/index.ts`
- Modify: `HestiaApp/WorkflowCanvas/src/App.tsx`

**Context:** Currently all nodes render as React Flow's `type: "default"` (plain rectangle). We need 6 custom node components so each node type has distinct visual identity. Each component is small (~30-50 lines): an icon, the label, a type badge, and typed Handle components (source/target). Condition nodes have multiple output handles ("true"/"false" for if_else, case labels for switch).

- [ ] **Step 1: Create shared constants (separate file to avoid circular imports)**

Create `HestiaApp/WorkflowCanvas/src/nodes/constants.ts`:

```typescript
// Shared colors per node category (match MacColors tokens)
// Extracted to separate file to avoid circular imports between index.ts and node components
export const NODE_COLORS = {
  prompt: '#D4A843',     // amber accent
  tool: '#6B9BD2',       // blue
  condition: '#9B6BD2',  // purple
  action: '#6BD29B',     // green
  trigger: '#D26B6B',    // red
  delay: '#8B8B8B',      // gray
} as const;
```

- [ ] **Step 1b: Create the nodeTypes registry**

Create `HestiaApp/WorkflowCanvas/src/nodes/index.ts`:

```typescript
import type { NodeTypes } from '@xyflow/react';
import { PromptNode } from './PromptNode';
import { ToolNode } from './ToolNode';
import { ConditionNode } from './ConditionNode';
import { ActionNode } from './ActionNode';
import { TriggerNode } from './TriggerNode';
import { DelayNode } from './DelayNode';

// Re-export constants for convenience
export { NODE_COLORS } from './constants';

// Map backend node_type values to React Flow custom components
export const nodeTypes: NodeTypes = {
  run_prompt: PromptNode,
  call_tool: ToolNode,
  if_else: ConditionNode,
  switch: ConditionNode,  // Same component, handles differ based on data
  notify: ActionNode,
  log: ActionNode,
  schedule: TriggerNode,
  manual: TriggerNode,
  delay: DelayNode,
};
```

- [ ] **Step 2: Create PromptNode component**

Create `HestiaApp/WorkflowCanvas/src/nodes/PromptNode.tsx`:

```tsx
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { NODE_COLORS } from './constants';

export function PromptNode({ data, selected }: NodeProps) {
  const prompt = data.config?.prompt as string || '';
  const truncated = prompt.length > 60 ? prompt.slice(0, 57) + '...' : prompt;

  return (
    <div
      style={{
        background: '#1a1a2e',
        border: `2px solid ${selected ? NODE_COLORS.prompt : '#333'}`,
        borderRadius: 8,
        padding: '8px 12px',
        minWidth: 180,
        maxWidth: 260,
      }}
    >
      <Handle type="target" position={Position.Top} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <span style={{ fontSize: 14 }}>💬</span>
        <span style={{ color: NODE_COLORS.prompt, fontSize: 10, fontWeight: 600, textTransform: 'uppercase' }}>
          Prompt
        </span>
      </div>
      <div style={{ color: '#e0e0e0', fontSize: 12, fontWeight: 500 }}>
        {data.label as string}
      </div>
      {truncated && (
        <div style={{ color: '#888', fontSize: 10, marginTop: 4, lineHeight: 1.3 }}>
          {truncated}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
```

- [ ] **Step 3: Create ToolNode component**

Create `HestiaApp/WorkflowCanvas/src/nodes/ToolNode.tsx`:

```tsx
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { NODE_COLORS } from './constants';

export function ToolNode({ data, selected }: NodeProps) {
  const toolName = data.config?.tool_name as string || 'Unknown Tool';

  return (
    <div
      style={{
        background: '#1a1a2e',
        border: `2px solid ${selected ? NODE_COLORS.tool : '#333'}`,
        borderRadius: 8,
        padding: '8px 12px',
        minWidth: 160,
      }}
    >
      <Handle type="target" position={Position.Top} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <span style={{ fontSize: 14 }}>🔧</span>
        <span style={{ color: NODE_COLORS.tool, fontSize: 10, fontWeight: 600, textTransform: 'uppercase' }}>
          Tool
        </span>
      </div>
      <div style={{ color: '#e0e0e0', fontSize: 12, fontWeight: 500 }}>
        {data.label as string}
      </div>
      <div style={{ color: '#888', fontSize: 10, marginTop: 2 }}>
        {toolName}
      </div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
```

- [ ] **Step 4: Create ConditionNode component**

Create `HestiaApp/WorkflowCanvas/src/nodes/ConditionNode.tsx`:

```tsx
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { NODE_COLORS } from './constants';

export function ConditionNode({ data, selected }: NodeProps) {
  const nodeType = data.nodeType as string;
  const isSwitch = nodeType === 'switch';
  const cases = (data.config?.cases as Array<{ label: string }>) || [];

  return (
    <div
      style={{
        background: '#1a1a2e',
        border: `2px solid ${selected ? NODE_COLORS.condition : '#333'}`,
        borderRadius: 8,
        padding: '8px 12px',
        minWidth: 160,
      }}
    >
      <Handle type="target" position={Position.Top} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <span style={{ fontSize: 14 }}>{isSwitch ? '🔀' : '❓'}</span>
        <span style={{ color: NODE_COLORS.condition, fontSize: 10, fontWeight: 600, textTransform: 'uppercase' }}>
          {isSwitch ? 'Switch' : 'Condition'}
        </span>
      </div>
      <div style={{ color: '#e0e0e0', fontSize: 12, fontWeight: 500 }}>
        {data.label as string}
      </div>
      {isSwitch ? (
        // Switch: one handle per case + default
        <>
          {cases.map((c, i) => (
            <Handle
              key={c.label}
              type="source"
              position={Position.Bottom}
              id={c.label}
              style={{ left: `${((i + 1) / (cases.length + 2)) * 100}%` }}
            />
          ))}
          <Handle
            type="source"
            position={Position.Bottom}
            id={data.config?.default_label as string || 'default'}
            style={{ left: `${((cases.length + 1) / (cases.length + 2)) * 100}%` }}
          />
        </>
      ) : (
        // If/Else: true (left) and false (right) handles
        <>
          <Handle type="source" position={Position.Bottom} id="true" style={{ left: '30%' }} />
          <Handle type="source" position={Position.Bottom} id="false" style={{ left: '70%' }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
            <span style={{ color: '#6BD29B', fontSize: 9 }}>True</span>
            <span style={{ color: '#D26B6B', fontSize: 9 }}>False</span>
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Create ActionNode component**

Create `HestiaApp/WorkflowCanvas/src/nodes/ActionNode.tsx`:

```tsx
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { NODE_COLORS } from './constants';

export function ActionNode({ data, selected }: NodeProps) {
  const nodeType = data.nodeType as string;
  const isNotify = nodeType === 'notify';

  return (
    <div
      style={{
        background: '#1a1a2e',
        border: `2px solid ${selected ? NODE_COLORS.action : '#333'}`,
        borderRadius: 8,
        padding: '8px 12px',
        minWidth: 140,
      }}
    >
      <Handle type="target" position={Position.Top} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <span style={{ fontSize: 14 }}>{isNotify ? '🔔' : '📝'}</span>
        <span style={{ color: NODE_COLORS.action, fontSize: 10, fontWeight: 600, textTransform: 'uppercase' }}>
          {isNotify ? 'Notify' : 'Log'}
        </span>
      </div>
      <div style={{ color: '#e0e0e0', fontSize: 12, fontWeight: 500 }}>
        {data.label as string}
      </div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
```

- [ ] **Step 6: Create TriggerNode component**

Create `HestiaApp/WorkflowCanvas/src/nodes/TriggerNode.tsx`:

```tsx
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { NODE_COLORS } from './constants';

export function TriggerNode({ data, selected }: NodeProps) {
  const nodeType = data.nodeType as string;
  const isSchedule = nodeType === 'schedule';

  return (
    <div
      style={{
        background: '#1a1a2e',
        border: `2px solid ${selected ? NODE_COLORS.trigger : '#333'}`,
        borderRadius: 8,
        padding: '8px 12px',
        minWidth: 140,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <span style={{ fontSize: 14 }}>{isSchedule ? '⏰' : '▶️'}</span>
        <span style={{ color: NODE_COLORS.trigger, fontSize: 10, fontWeight: 600, textTransform: 'uppercase' }}>
          {isSchedule ? 'Schedule' : 'Manual'}
        </span>
      </div>
      <div style={{ color: '#e0e0e0', fontSize: 12, fontWeight: 500 }}>
        {data.label as string}
      </div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
```

- [ ] **Step 7: Create DelayNode component**

Create `HestiaApp/WorkflowCanvas/src/nodes/DelayNode.tsx`:

```tsx
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { NODE_COLORS } from './constants';

export function DelayNode({ data, selected }: NodeProps) {
  const seconds = data.config?.delay_seconds as number || 0;
  const label = seconds >= 3600
    ? `${Math.round(seconds / 3600)}h`
    : seconds >= 60
    ? `${Math.round(seconds / 60)}m`
    : `${seconds}s`;

  return (
    <div
      style={{
        background: '#1a1a2e',
        border: `2px solid ${selected ? NODE_COLORS.delay : '#333'}`,
        borderRadius: 8,
        padding: '8px 12px',
        minWidth: 120,
        textAlign: 'center',
      }}
    >
      <Handle type="target" position={Position.Top} />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
        <span style={{ fontSize: 14 }}>⏳</span>
        <span style={{ color: NODE_COLORS.delay, fontSize: 10, fontWeight: 600, textTransform: 'uppercase' }}>
          Delay
        </span>
      </div>
      <div style={{ color: '#e0e0e0', fontSize: 16, fontWeight: 600, marginTop: 4 }}>
        {label}
      </div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
```

- [ ] **Step 8: Register custom node types in App.tsx**

In `HestiaApp/WorkflowCanvas/src/App.tsx`, replace the default node type usage:

1. Add import at top:
```typescript
import { nodeTypes } from './nodes';
```

2. Pass `nodeTypes` to the `<ReactFlow>` component:
```tsx
<ReactFlow
  nodes={nodes}
  edges={edges}
  nodeTypes={nodeTypes}
  // ... rest of existing props
>
```

3. In the `loadWorkflow` function where nodes are mapped, ensure `type` is set to the backend's `nodeType` value (not `"default"`):
```typescript
// When mapping workflow data to React Flow nodes:
const rfNodes = data.nodes.map((n: any) => ({
  id: n.id,
  type: n.node_type,  // This maps to our nodeTypes registry
  position: { x: n.position_x, y: n.position_y },
  data: {
    label: n.label,
    nodeType: n.node_type,
    config: n.config || {},
  },
}));
```

- [ ] **Step 9: Rebuild the canvas bundle**

```bash
cd HestiaApp/WorkflowCanvas && npm run build && cd ../..
```

Expected: Single `index.html` output in `HestiaApp/macOS/Resources/WorkflowCanvas/`

- [ ] **Step 10: Build macOS target**

```bash
cd HestiaApp && xcodegen generate && cd ..
xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build CODE_SIGNING_ALLOWED=NO 2>&1 | tail -5
```

Expected: BUILD SUCCEEDED

- [ ] **Step 11: Commit**

```bash
git add HestiaApp/WorkflowCanvas/src/nodes/ HestiaApp/WorkflowCanvas/src/App.tsx HestiaApp/macOS/Resources/WorkflowCanvas/index.html
git commit -m "feat(workflow): custom React Flow node components — 6 types with typed handles"
```

---

### Task 6: Add Step Menu (Canvas UI)

**Files:**
- Create: `HestiaApp/WorkflowCanvas/src/components/AddStepMenu.tsx`
- Modify: `HestiaApp/WorkflowCanvas/src/App.tsx`
- Modify: `HestiaApp/WorkflowCanvas/src/bridge.ts`

**Context:** This is the primary interaction for adding steps to the canvas. Two entry points: (1) a "+" button on edges between nodes, (2) right-click context menu on empty canvas. Both show a compact menu with step type options. Selecting a type sends an `addStep` message through the bridge to Swift, which calls the translation endpoint.

- [ ] **Step 1: Add addStep message type to bridge**

In `HestiaApp/WorkflowCanvas/src/bridge.ts`, add a new function to send step creation requests to Swift:

```typescript
export function requestAddStep(payload: {
  title: string;
  stepType: string;  // "prompt" | "notify" | "condition" | "tool"
  positionX: number;
  positionY: number;
  afterNodeId?: string;
}) {
  sendToSwift('addStep', payload);
}
```

Ensure `sendToSwift` is the existing function that posts to WebKit message handlers. Check the existing bridge.ts for the exact pattern (likely `window.webkit.messageHandlers.canvasAction.postMessage(...)`).

- [ ] **Step 2: Create AddStepMenu component**

Create `HestiaApp/WorkflowCanvas/src/components/AddStepMenu.tsx`:

```tsx
import React from 'react';

interface AddStepMenuProps {
  x: number;
  y: number;
  afterNodeId?: string;
  canvasX: number;
  canvasY: number;
  onSelect: (stepType: string, title: string) => void;
  onClose: () => void;
}

const STEP_TYPES = [
  { type: 'prompt', label: 'Prompt Step', icon: '💬', desc: 'Send a prompt to the LLM' },
  { type: 'notify', label: 'Notification', icon: '🔔', desc: 'Send a notification' },
  { type: 'condition', label: 'Condition', icon: '❓', desc: 'Branch based on a condition' },
  { type: 'tool', label: 'Tool Call', icon: '🔧', desc: 'Execute a tool directly' },
  { type: 'delay', label: 'Delay', icon: '⏳', desc: 'Wait before continuing' },
];

export function AddStepMenu({ x, y, onSelect, onClose }: AddStepMenuProps) {
  return (
    <>
      {/* Backdrop */}
      <div
        style={{ position: 'fixed', inset: 0, zIndex: 999 }}
        onClick={onClose}
      />
      {/* Menu */}
      <div
        style={{
          position: 'fixed',
          left: x,
          top: y,
          zIndex: 1000,
          background: '#1a1a2e',
          border: '1px solid #333',
          borderRadius: 8,
          padding: 4,
          minWidth: 200,
          boxShadow: '0 4px 16px rgba(0,0,0,0.5)',
        }}
      >
        <div style={{ padding: '4px 8px', color: '#888', fontSize: 10, fontWeight: 600, textTransform: 'uppercase' }}>
          Add Step
        </div>
        {STEP_TYPES.map((st) => (
          <button
            key={st.type}
            onClick={() => onSelect(st.type, st.label)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              width: '100%',
              padding: '8px 12px',
              background: 'transparent',
              border: 'none',
              borderRadius: 4,
              cursor: 'pointer',
              textAlign: 'left',
              color: '#e0e0e0',
            }}
            onMouseEnter={(e) => { (e.target as HTMLElement).style.background = '#2a2a4e'; }}
            onMouseLeave={(e) => { (e.target as HTMLElement).style.background = 'transparent'; }}
          >
            <span style={{ fontSize: 16 }}>{st.icon}</span>
            <div>
              <div style={{ fontSize: 12, fontWeight: 500 }}>{st.label}</div>
              <div style={{ fontSize: 10, color: '#888' }}>{st.desc}</div>
            </div>
          </button>
        ))}
      </div>
    </>
  );
}
```

- [ ] **Step 3: Wire AddStepMenu into App.tsx**

In `HestiaApp/WorkflowCanvas/src/App.tsx`:

1. Add state for the menu:
```typescript
const [addMenu, setAddMenu] = useState<{
  x: number;
  y: number;
  canvasX: number;
  canvasY: number;
  afterNodeId?: string;
} | null>(null);
```

2. Add right-click handler on the ReactFlow pane:
```typescript
const onPaneContextMenu = useCallback((event: React.MouseEvent) => {
  event.preventDefault();
  const bounds = (event.target as HTMLElement).closest('.react-flow')?.getBoundingClientRect();
  if (!bounds) return;
  setAddMenu({
    x: event.clientX,
    y: event.clientY,
    canvasX: event.clientX - bounds.left,
    canvasY: event.clientY - bounds.top,
  });
}, []);
```

3. Add selection handler:
```typescript
const onStepSelected = useCallback((stepType: string, title: string) => {
  if (!addMenu) return;
  requestAddStep({
    title,
    stepType,
    positionX: addMenu.canvasX,
    positionY: addMenu.canvasY,
    afterNodeId: addMenu.afterNodeId,
  });
  setAddMenu(null);
}, [addMenu]);
```

4. Pass to ReactFlow:
```tsx
<ReactFlow
  // ... existing props
  onPaneContextMenu={onPaneContextMenu}
>
  {/* ... existing children */}
</ReactFlow>
{addMenu && (
  <AddStepMenu
    x={addMenu.x}
    y={addMenu.y}
    canvasX={addMenu.canvasX}
    canvasY={addMenu.canvasY}
    afterNodeId={addMenu.afterNodeId}
    onSelect={onStepSelected}
    onClose={() => setAddMenu(null)}
  />
)}
```

- [ ] **Step 4: Add "+" button on edges**

In App.tsx, add a custom edge type that renders a "+" button at the midpoint. Add to the ReactFlow component:

```typescript
import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath, type EdgeProps } from '@xyflow/react';

function AddButtonEdge(props: EdgeProps) {
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    targetX: props.targetX,
    targetY: props.targetY,
  });

  return (
    <>
      <BaseEdge path={edgePath} {...props} />
      <EdgeLabelRenderer>
        <button
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            width: 20,
            height: 20,
            borderRadius: '50%',
            background: '#333',
            border: '1px solid #555',
            color: '#aaa',
            fontSize: 14,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            pointerEvents: 'all',
          }}
          className="nodrag nopan"
          onClick={(e) => {
            e.stopPropagation();
            // Open add menu at button position, with afterNodeId = source
            setAddMenu({
              x: e.clientX,
              y: e.clientY,
              canvasX: labelX,
              canvasY: labelY,
              afterNodeId: props.source,
            });
          }}
        >
          +
        </button>
      </EdgeLabelRenderer>
    </>
  );
}

// Register as default edge type
const edgeTypes = { default: AddButtonEdge };
```

Pass `edgeTypes` to `<ReactFlow edgeTypes={edgeTypes} ...>`.

**Important:** Define `AddButtonEdge` INSIDE the `App` component function body so it captures `setAddMenu` via closure. React Flow will re-register the edge type on each render, but for a single-user app this performance cost is negligible. If it causes issues, extract to a separate component and use a React context to provide the `setAddMenu` callback.

- [ ] **Step 5: Rebuild canvas**

```bash
cd HestiaApp/WorkflowCanvas && npm run build && cd ../..
```

- [ ] **Step 6: Commit**

```bash
git add HestiaApp/WorkflowCanvas/src/
git commit -m "feat(workflow): Add Step menu — right-click canvas + edge plus button"
```

---

### Task 7: Swift Bridge — Handle addStep + Auto-Open Inspector

**Files:**
- Modify: `HestiaApp/macOS/Views/Workflow/WorkflowCanvasWebView.swift`
- Modify: `HestiaApp/macOS/ViewModels/MacWorkflowViewModel.swift`

**Context:** When the canvas sends an `addStep` bridge message, the Swift coordinator needs to: (1) call the translation endpoint via the ViewModel, (2) reload the workflow detail to show new nodes, (3) auto-select the first new node to open the inspector. This is the critical vertical slice — the end-to-end path from canvas click to configured node.

- [ ] **Step 1: Add addStep handler to ViewModel**

In `HestiaApp/macOS/ViewModels/MacWorkflowViewModel.swift`, add:

```swift
func addStepFromCanvas(
    workflowId: String,
    stepType: String,
    title: String,
    positionX: Double,
    positionY: Double,
    afterNodeId: String?
) async {
    do {
        // Map canvas step types to translation endpoint format
        let prompt: String? = stepType == "prompt" ? "Configure this step's prompt" : nil

        let request = StepCreateRequest(
            title: title,
            prompt: prompt,
            trigger: "immediate",
            delaySeconds: nil,
            resources: nil,
            positionX: positionX,
            positionY: positionY,
            afterNodeId: afterNodeId
        )

        let response = try await APIClient.shared.createNodeFromStep(workflowId, step: request)

        // Reload the full workflow to sync canvas
        await loadWorkflowDetail(workflowId)

        // Auto-select the first created node to open the inspector
        if let firstNode = response.nodes.first {
            selectedNodeId = firstNode.id
        }
    } catch {
        #if DEBUG
        print("Failed to add step: \(error)")
        #endif
        errorMessage = "Failed to add step"
    }
}
```

- [ ] **Step 2: Handle addStep in the bridge coordinator**

In `HestiaApp/macOS/Views/Workflow/WorkflowCanvasWebView.swift`, find the `handleCanvasAction` method in the Coordinator. Add a new case:

```swift
case "addStep":
    guard let stepType = payload["stepType"] as? String,
          let title = payload["title"] as? String,
          let posX = payload["positionX"] as? Double,
          let posY = payload["positionY"] as? Double else { return }

    let afterNodeId = payload["afterNodeId"] as? String

    Task { @MainActor [weak self] in
        guard let viewModel = self?.parent.viewModel,
              let workflowId = viewModel.selectedWorkflowId else { return }
        await viewModel.addStepFromCanvas(
            workflowId: workflowId,
            stepType: stepType,
            title: title,
            positionX: posX,
            positionY: posY,
            afterNodeId: afterNodeId
        )
    }
```

- [ ] **Step 3: Build and verify**

```bash
cd HestiaApp && xcodegen generate && cd ..
xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build CODE_SIGNING_ALLOWED=NO 2>&1 | tail -5
```

Expected: BUILD SUCCEEDED

- [ ] **Step 4: Commit**

```bash
git add HestiaApp/macOS/Views/Workflow/WorkflowCanvasWebView.swift HestiaApp/macOS/ViewModels/MacWorkflowViewModel.swift
git commit -m "feat(workflow): bridge addStep handler — canvas → translation API → inspector auto-open"
```

---

### Task 8: Resource Picker in Node Inspector

**Files:**
- Modify: `HestiaApp/macOS/ViewModels/MacWorkflowViewModel.swift`
- Modify: `HestiaApp/macOS/Views/Workflow/MacNodeInspectorView.swift`

**Context:** When editing a `run_prompt` node in the inspector, the user should be able to select which tool categories (Resources) the step can use. This adds a categorized tag-style picker below the prompt field. The ViewModel fetches tool categories from the new endpoint and caches them for the session.

- [ ] **Step 1: Add tool categories fetch to ViewModel**

In `MacWorkflowViewModel.swift`, add:

```swift
@Published var toolCategories: [ToolCategory] = []
@Published var isFetchingCategories = false

func fetchToolCategories() async {
    guard toolCategories.isEmpty else { return }  // Cache for session
    isFetchingCategories = true
    defer { isFetchingCategories = false }

    do {
        let response = try await APIClient.shared.getToolCategories()
        toolCategories = response.categories
    } catch {
        #if DEBUG
        print("Failed to fetch tool categories: \(error)")
        #endif
    }
}
```

- [ ] **Step 2: Add resource picker to RunPrompt inspector section**

In `MacNodeInspectorView.swift`, find the RunPrompt config section (where `prompt` TextEditor and `model` TextField are). Below them, add a resource picker:

```swift
// MARK: - Resource Picker (for run_prompt nodes)

@ViewBuilder
private var resourcePicker: some View {
    VStack(alignment: .leading, spacing: MacSpacing.sm) {
        Text("Resources")
            .font(MacTypography.label)
            .foregroundStyle(MacColors.textSecondary)

        if viewModel.isFetchingCategories {
            ProgressView()
                .controlSize(.small)
        } else if viewModel.toolCategories.isEmpty {
            Text("No tools available")
                .font(.system(size: 11))
                .foregroundStyle(MacColors.textFaint)
        } else {
            // Tag-style category pills (adaptive grid wraps based on available width)
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 90))], spacing: 6) {
                ForEach(viewModel.toolCategories) { category in
                    let isSelected = selectedResources.contains(category.id)
                    Button {
                        if isSelected {
                            selectedResources.remove(category.id)
                        } else {
                            selectedResources.insert(category.id)
                        }
                    } label: {
                        HStack(spacing: 4) {
                            Image(systemName: category.icon)
                                .font(.system(size: 10))
                            Text(category.label)
                                .font(.system(size: 11, weight: isSelected ? .semibold : .regular))
                        }
                        .foregroundStyle(isSelected ? MacColors.amberAccent : MacColors.textSecondary)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(isSelected ? MacColors.activeTabBackground : Color.clear)
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                        .overlay {
                            RoundedRectangle(cornerRadius: 6)
                                .strokeBorder(
                                    isSelected ? MacColors.amberAccent.opacity(0.3) : MacColors.cardBorder,
                                    lineWidth: 1
                                )
                        }
                    }
                    .buttonStyle(.hestia)
                }
            }
        }
    }
    .onAppear {
        Task { await viewModel.fetchToolCategories() }
    }
}
```

Add `@State private var selectedResources: Set<String> = []` to the view.

**FlowLayout note:** SwiftUI doesn't have a built-in flow/wrap layout. You may need to use a simple `LazyVGrid` or implement a basic `FlowLayout`. The simplest approach is a `LazyVGrid(columns: [GridItem(.adaptive(minimum: 80))], spacing: 6)`.

Wire `selectedResources` into the `saveChanges()` flow so it updates `allowed_tools` in the node config. When saving, expand category IDs to tool names (or pass categories to the backend and let the translation layer handle it).

- [ ] **Step 3: Load selected resources from existing node config**

In the `loadFromNode()` function, parse `allowed_tools` from config and reverse-map to categories:

```swift
// In loadFromNode(), after existing config parsing:
if let allowedTools = config["allowed_tools"] as? [String] {
    // For now, mark categories as selected if ANY of their tools are in the list
    // This is a heuristic — exact reverse-mapping would need the tool registry
    selectedResources = Set(
        viewModel.toolCategories
            .filter { cat in cat.tools.contains { allowedTools.contains($0.name) } }
            .map(\.id)
    )
}
```

- [ ] **Step 4: Build and verify**

```bash
cd HestiaApp && xcodegen generate && cd ..
xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build CODE_SIGNING_ALLOWED=NO 2>&1 | tail -5
```

Expected: BUILD SUCCEEDED

- [ ] **Step 5: Commit**

```bash
git add HestiaApp/macOS/Views/Workflow/MacNodeInspectorView.swift HestiaApp/macOS/ViewModels/MacWorkflowViewModel.swift
git commit -m "feat(workflow): resource picker in inspector — categorized tool tag selector"
```

---

### Task 9: DELAY Node Inspector Config

**Files:**
- Modify: `HestiaApp/macOS/Views/Workflow/MacNodeInspectorView.swift`

**Context:** The node inspector needs a config editor for the new DELAY node type. Simple: a numeric field for delay duration with a unit picker (seconds/minutes/hours).

- [ ] **Step 1: Add DELAY case to inspector**

In `MacNodeInspectorView.swift`, find the `switch` statement that renders per-type config editors. Add:

```swift
case .delay:
    delayConfigSection
```

- [ ] **Step 2: Implement delay config section**

```swift
@State private var delayValue: Double = 0
@State private var delayUnit: DelayUnit = .minutes

enum DelayUnit: String, CaseIterable {
    case seconds = "Seconds"
    case minutes = "Minutes"
    case hours = "Hours"

    var multiplier: Double {
        switch self {
        case .seconds: return 1
        case .minutes: return 60
        case .hours: return 3600
        }
    }
}

@ViewBuilder
private var delayConfigSection: some View {
    VStack(alignment: .leading, spacing: MacSpacing.sm) {
        Text("Delay Duration")
            .font(MacTypography.label)
            .foregroundStyle(MacColors.textSecondary)

        HStack(spacing: MacSpacing.sm) {
            TextField("Duration", value: $delayValue, format: .number)
                .textFieldStyle(.roundedBorder)
                .frame(width: 80)

            Picker("", selection: $delayUnit) {
                ForEach(DelayUnit.allCases, id: \.self) { unit in
                    Text(unit.rawValue).tag(unit)
                }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
        }

        Text("Max: 1 hour")
            .font(.system(size: 10))
            .foregroundStyle(MacColors.textFaint)
    }
}
```

Wire into `loadFromNode()`:
```swift
// In loadFromNode(), for DELAY type:
if let delaySec = config["delay_seconds"] as? Double {
    if delaySec >= 3600 {
        delayValue = delaySec / 3600
        delayUnit = .hours
    } else if delaySec >= 60 {
        delayValue = delaySec / 60
        delayUnit = .minutes
    } else {
        delayValue = delaySec
        delayUnit = .seconds
    }
}
```

Wire into `saveChanges()`:
```swift
// In saveChanges(), for DELAY type:
let totalSeconds = delayValue * delayUnit.multiplier
config["delay_seconds"] = min(totalSeconds, 3600)
```

- [ ] **Step 3: Build and verify**

```bash
cd HestiaApp && xcodegen generate && cd ..
xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build CODE_SIGNING_ALLOWED=NO 2>&1 | tail -5
```

Expected: BUILD SUCCEEDED

- [ ] **Step 4: Commit**

```bash
git add HestiaApp/macOS/Views/Workflow/MacNodeInspectorView.swift
git commit -m "feat(workflow): DELAY node inspector — duration picker with unit selector"
```

---

### Task 10: Pre-Populate Trigger Node on New Workflow

**Files:**
- Modify: `HestiaApp/macOS/ViewModels/MacWorkflowViewModel.swift`

**Context:** Empty canvas is an anti-pattern (n8n, Zapier, Make all pre-populate). When a new workflow is created, automatically add a trigger node so the canvas is never blank. This happens client-side after the workflow creation API call succeeds.

- [ ] **Step 1: Add NodeCreateRequest model and API method**

The backend has `POST /{workflow_id}/nodes` (the `add_node` route) but the APIClient doesn't have a `createNode` method yet. Add to `APIClient+Workflows.swift`:

```swift
struct NodeCreateRequest: Codable {
    let nodeType: String
    let label: String
    let config: [String: AnyCodableValue]
    let positionX: Double
    let positionY: Double

    enum CodingKeys: String, CodingKey {
        case nodeType = "node_type"
        case label, config
        case positionX = "position_x"
        case positionY = "position_y"
    }
}

struct NodeCreateResponse: Codable {
    let node: WorkflowNodeResponse
}

func createNode(_ workflowId: String, request: NodeCreateRequest) async throws -> NodeCreateResponse {
    return try await post("/workflows/\(workflowId)/nodes", body: request)
}
```

- [ ] **Step 1b: Add auto-trigger creation after workflow creation**

In `MacWorkflowViewModel.swift`, find the `createWorkflow()` method. After the successful creation, auto-create a trigger node:

```swift
if success, let workflowId = newWorkflow?.id {
    let triggerNodeType = triggerType == .schedule ? "schedule" : "manual"
    let triggerRequest = NodeCreateRequest(
        nodeType: triggerNodeType,
        label: triggerType == .schedule ? "Scheduled Trigger" : "Manual Trigger",
        config: [:],
        positionX: 250,
        positionY: 50
    )
    do {
        _ = try await APIClient.shared.createNode(workflowId, request: triggerRequest)
    } catch {
        // Best-effort — workflow was created successfully either way
        #if DEBUG
        print("Auto-trigger creation failed: \(error)")
        #endif
    }
}
```

- [ ] **Step 2: Build and verify**

```bash
cd HestiaApp && xcodegen generate && cd ..
xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build CODE_SIGNING_ALLOWED=NO 2>&1 | tail -5
```

Expected: BUILD SUCCEEDED

- [ ] **Step 3: Commit**

```bash
git add HestiaApp/macOS/ViewModels/MacWorkflowViewModel.swift HestiaApp/macOS/Services/APIClient+Workflows.swift HestiaApp/macOS/Models/WorkflowModels.swift
git commit -m "feat(workflow): auto-create trigger node on new workflow — no empty canvas"
```

---

### Task 11: Integration Test — Full Vertical Slice

**Files:**
- Create: `tests/test_workflow_step_e2e.py`

**Context:** Validates the end-to-end path: create workflow → add Step via translation → verify nodes exist. This is the critical integration test that proves the architecture works.

- [ ] **Step 1: Write the integration test**

```python
# tests/test_workflow_step_e2e.py
"""End-to-end integration test for the Step Builder vertical slice."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from hestia.api.server import app


@pytest.fixture
def mock_auth():
    with patch("hestia.api.routes.workflows.get_device_token", return_value="test-token"):
        yield


@pytest.fixture
def mock_manager():
    """Mock manager that tracks all created nodes and edges."""
    manager = AsyncMock()
    created_nodes = []
    created_edges = []
    node_counter = 0

    async def mock_add_node(**kwargs):
        nonlocal node_counter
        node_counter += 1
        node = MagicMock()
        node.id = f"node-{node_counter:03d}"
        node.node_type = kwargs.get("node_type", "run_prompt")
        node_dict = {
            "id": node.id,
            "node_type": kwargs.get("node_type", "run_prompt"),
            "label": kwargs.get("label", ""),
            "config": kwargs.get("config", {}),
            "position_x": kwargs.get("position_x", 0),
            "position_y": kwargs.get("position_y", 0),
        }
        node.to_dict.return_value = node_dict
        created_nodes.append(node_dict)
        return node

    edge_counter = 0

    async def mock_add_edge(**kwargs):
        nonlocal edge_counter
        edge_counter += 1
        edge = MagicMock()
        edge.id = f"edge-{edge_counter:03d}"
        edge_dict = {
            "id": edge.id,
            "source_node_id": kwargs.get("source_node_id"),
            "target_node_id": kwargs.get("target_node_id"),
            "edge_label": kwargs.get("edge_label"),
        }
        edge.to_dict.return_value = edge_dict
        created_edges.append(edge_dict)
        return edge

    manager.add_node = mock_add_node
    manager.add_edge = mock_add_edge
    manager._created_nodes = created_nodes
    manager._created_edges = created_edges

    return manager


class TestStepBuilderE2E:
    """End-to-end: Step → translation → DAG nodes."""

    @pytest.mark.asyncio
    async def test_prompt_step_with_resources_creates_correct_dag(self, mock_auth, mock_manager):
        """
        Full vertical slice: A prompt step with Calendar and Mail resources
        should create a single run_prompt node with allowed_tools populated
        from those categories.
        """
        with patch("hestia.api.routes.workflows.get_workflow_manager", return_value=mock_manager):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="https://test") as client:
                resp = await client.post(
                    "/v1/workflows/wf-test/nodes/from-step",
                    json={
                        "title": "Morning Briefing",
                        "prompt": "Summarize my calendar and unread mail for today",
                        "trigger": "immediate",
                        "resources": ["calendar", "mail"],
                        "position_x": 300,
                        "position_y": 200,
                    },
                    headers={"Authorization": "Bearer test-token"},
                )

        assert resp.status_code == 200
        data = resp.json()

        # Should be exactly 1 node (immediate trigger, no delay)
        assert len(data["nodes"]) == 1
        node = data["nodes"][0]

        # Node should be run_prompt type
        assert node["node_type"] == "run_prompt"
        assert node["label"] == "Morning Briefing"

        # Config should have the prompt and allowed_tools from calendar + mail
        config = node["config"]
        assert config["prompt"] == "Summarize my calendar and unread mail for today"
        assert "allowed_tools" in config
        tools = config["allowed_tools"]
        assert isinstance(tools, list)

    @pytest.mark.asyncio
    async def test_delayed_prompt_step_creates_delay_chain(self, mock_auth, mock_manager):
        """
        Delayed step: should create DELAY → RUN_PROMPT with connecting edge.
        """
        with patch("hestia.api.routes.workflows.get_workflow_manager", return_value=mock_manager):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="https://test") as client:
                resp = await client.post(
                    "/v1/workflows/wf-test/nodes/from-step",
                    json={
                        "title": "Delayed Check",
                        "prompt": "Check for updates",
                        "trigger": "delay",
                        "delay_seconds": 300,
                        "resources": [],
                        "position_x": 300,
                        "position_y": 200,
                    },
                    headers={"Authorization": "Bearer test-token"},
                )

        assert resp.status_code == 200
        data = resp.json()

        # Should be 2 nodes: delay + prompt
        assert len(data["nodes"]) == 2
        assert data["nodes"][0]["node_type"] == "delay"
        assert data["nodes"][1]["node_type"] == "run_prompt"

        # Should have at least 1 edge (delay → prompt)
        assert len(data["edges"]) >= 1
        edge = data["edges"][0]
        assert edge["source_node_id"] == data["nodes"][0]["id"]
        assert edge["target_node_id"] == data["nodes"][1]["id"]

    @pytest.mark.asyncio
    async def test_chained_steps_create_connected_dag(self, mock_auth, mock_manager):
        """
        Adding a step after an existing node should create an edge from
        the existing node to the new node.
        """
        with patch("hestia.api.routes.workflows.get_workflow_manager", return_value=mock_manager):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="https://test") as client:
                # First step
                resp1 = await client.post(
                    "/v1/workflows/wf-test/nodes/from-step",
                    json={
                        "title": "Step 1",
                        "prompt": "Do first thing",
                        "trigger": "immediate",
                        "position_x": 300,
                        "position_y": 100,
                    },
                    headers={"Authorization": "Bearer test-token"},
                )
                first_node_id = resp1.json()["nodes"][0]["id"]

                # Second step, after first
                resp2 = await client.post(
                    "/v1/workflows/wf-test/nodes/from-step",
                    json={
                        "title": "Step 2",
                        "prompt": "Do second thing",
                        "trigger": "immediate",
                        "after_node_id": first_node_id,
                        "position_x": 300,
                        "position_y": 300,
                    },
                    headers={"Authorization": "Bearer test-token"},
                )

        assert resp2.status_code == 200
        data = resp2.json()

        # Should have an edge from first node to second node
        edges = data["edges"]
        assert len(edges) == 1
        assert edges[0]["source_node_id"] == first_node_id
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_workflow_step_e2e.py -v --timeout=30`
Expected: 3 passed

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=30 -x`
Expected: All pass (2829+ tests)

- [ ] **Step 4: Commit**

```bash
git add tests/test_workflow_step_e2e.py
git commit -m "test(workflow): e2e integration tests for Step Builder vertical slice"
```

---

## Execution Sequence

Tasks 1-3 (backend) are independent of Tasks 4-10 (frontend) EXCEPT:
- Task 4 depends on Task 1 (DELAY NodeType enum) and Task 2 (ToolCategory models)
- Tasks 5-9 depend on Task 4 (Swift models)
- Task 10 depends on Task 4

Recommended order: **1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11**

Tasks 1, 2 can run in parallel. Task 11 runs last as a validation gate.

## Estimated Effort

| Task | Estimate | Category |
|------|----------|----------|
| 1. DELAY node type | 1h | Backend |
| 2. Tool categories endpoint | 1.5h | Backend |
| 3. Step translation endpoint | 2h | Backend |
| 4. Swift models + API client | 1h | Frontend |
| 5. Custom React Flow nodes | 2.5h | Canvas |
| 6. Add Step menu | 2h | Canvas |
| 7. Bridge + auto-open inspector | 1.5h | Integration |
| 8. Resource picker | 2h | Frontend |
| 9. DELAY inspector config | 0.5h | Frontend |
| 10. Pre-populate trigger | 0.5h | Frontend |
| 11. E2E integration test | 1h | Testing |
| **Total** | **15.5h** | |

This covers the "vertical slice" (Condition 3 from second opinion) plus all 5 conditions. The 20-28h estimate from the second opinion included Phase 2 (drag-from-sidebar, auto-layout, connection validation) which is explicitly deferred.
