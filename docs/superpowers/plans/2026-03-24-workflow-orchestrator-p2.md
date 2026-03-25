# Workflow Orchestrator P2: Visual Canvas + Conditions

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a visual node editor (React Flow in WKWebView) and enhanced condition system (Switch node, variable interpolation) so all Hestia Orders — daily briefings, research pipelines, investigations, scheduled prompts — become visual, editable DAGs.

**Architecture:** React Flow v12 bundled via vite-plugin-singlefile into a single index.html loaded by WKWebView. Swift-JS bidirectional bridge for canvas ↔ app communication. Backend extended with batch layout endpoint, Switch node, and mustache-style variable interpolation. Native SwiftUI inspector sidebar for node config editing.

**Tech Stack:** React 19, React Flow v12, Vite + vite-plugin-singlefile, TypeScript, WKWebView (NSViewRepresentable), Python (ConditionEvaluator, DAGExecutor)

**Estimate:** 25-35h (adjusted per second opinion)

**Second Opinion:** `docs/plans/workflow-orchestrator-p2-second-opinion-2026-03-24.md` — APPROVE WITH CONDITIONS

**Discovery:** `docs/discoveries/workflow-orchestrator-p2-canvas-conditions-2026-03-24.md`

---

## File Structure

### New Files — Backend (Python)

| File | Responsibility |
|------|---------------|
| `hestia/workflows/interpolation.py` | Variable interpolation engine (`{{node_id.field}}` resolution) |
| `tests/test_workflow_interpolation.py` | Interpolation unit tests |
| `tests/test_workflow_switch.py` | Switch node + N-ary branching tests |

### Modified Files — Backend (Python)

| File | Changes |
|------|---------|
| `hestia/workflows/models.py` | Add `NodeType.SWITCH` enum value |
| `hestia/workflows/nodes.py` | Add `execute_switch()` executor + register in `NODE_EXECUTORS` |
| `hestia/workflows/executor.py` | Insert interpolation call in `_execute_node_task()`, generalize `_mark_dead_paths()` for N-ary |
| `hestia/workflows/database.py` | Add `batch_update_positions()` method |
| `hestia/workflows/manager.py` | Add `batch_update_layout()` method |
| `hestia/api/routes/workflows.py` | Add `PATCH /{id}/layout` batch endpoint |

### New Files — Canvas (React/TypeScript)

| File | Responsibility |
|------|---------------|
| `HestiaApp/WorkflowCanvas/package.json` | npm dependencies (React, React Flow, Vite) |
| `HestiaApp/WorkflowCanvas/tsconfig.json` | TypeScript config |
| `HestiaApp/WorkflowCanvas/vite.config.ts` | Vite + vite-plugin-singlefile |
| `HestiaApp/WorkflowCanvas/src/App.tsx` | React Flow canvas root |
| `HestiaApp/WorkflowCanvas/src/bridge.ts` | Swift-JS message protocol (7 message types) |
| `HestiaApp/WorkflowCanvas/src/theme.ts` | Dark theme CSS matching MacColors |
| `HestiaApp/WorkflowCanvas/src/nodes/PromptNode.tsx` | run_prompt node renderer |
| `HestiaApp/WorkflowCanvas/src/nodes/ToolNode.tsx` | call_tool node renderer |
| `HestiaApp/WorkflowCanvas/src/nodes/ConditionNode.tsx` | if_else + switch node renderer (multi-port) |
| `HestiaApp/WorkflowCanvas/src/nodes/ActionNode.tsx` | notify + log node renderer |
| `HestiaApp/WorkflowCanvas/src/nodes/TriggerNode.tsx` | schedule + manual trigger renderer |

### New Files — macOS (Swift)

| File | Responsibility |
|------|---------------|
| `HestiaApp/macOS/Views/Workflow/WorkflowCanvasWebView.swift` | NSViewRepresentable + Coordinator (bidirectional bridge) |
| `HestiaApp/macOS/Views/Workflow/MacWorkflowCanvasPane.swift` | Canvas + inspector split view |
| `HestiaApp/macOS/Views/Workflow/MacNodeInspectorView.swift` | Native SwiftUI node config editor |
| `HestiaApp/macOS/Resources/WorkflowCanvas/index.html` | Built artifact from vite-plugin-singlefile (committed) |

### Modified Files — macOS (Swift)

| File | Changes |
|------|---------|
| `HestiaApp/macOS/Views/Workflow/MacWorkflowDetailPane.swift` | Add canvas/list toggle |
| `HestiaApp/macOS/ViewModels/MacWorkflowViewModel.swift` | Add canvas state, bridge message handling, SSE subscription |
| `HestiaApp/macOS/Models/WorkflowModels.swift` | Add bridge message types |
| `HestiaApp/macOS/Services/APIClient+Workflows.swift` | Add batch layout method |

---

## Phase P2B: Backend Conditions + Interpolation (Tasks 1-4)

*Pure Python. No new dependencies. Standalone value.*

### Task 1: Variable Interpolation Engine

**Files:**
- Create: `hestia/workflows/interpolation.py`
- Create: `tests/test_workflow_interpolation.py`

- [ ] **Step 1: Write failing tests for interpolation**

```python
# tests/test_workflow_interpolation.py
import pytest
from hestia.workflows.interpolation import interpolate_config


class TestInterpolateConfig:
    def test_simple_substitution(self) -> None:
        config = {"prompt": "Summarize: {{nodeA.response}}"}
        results = {"nodeA": {"response": "The market rose 5%"}}
        out = interpolate_config(config, results)
        assert out["prompt"] == "Summarize: The market rose 5%"

    def test_nested_path(self) -> None:
        config = {"prompt": "Score: {{nodeA.metrics.score}}"}
        results = {"nodeA": {"metrics": {"score": 0.95}}}
        out = interpolate_config(config, results)
        assert out["prompt"] == "Score: 0.95"

    def test_unresolved_left_intact(self) -> None:
        config = {"prompt": "Value: {{missing.field}}"}
        results = {}
        out = interpolate_config(config, results)
        assert out["prompt"] == "Value: {{missing.field}}"

    def test_multiple_substitutions(self) -> None:
        config = {"prompt": "{{a.x}} and {{b.y}}"}
        results = {"a": {"x": "hello"}, "b": {"y": "world"}}
        out = interpolate_config(config, results)
        assert out["prompt"] == "hello and world"

    def test_numeric_value_stringified(self) -> None:
        config = {"threshold": "{{nodeA.count}}"}
        results = {"nodeA": {"count": 42}}
        out = interpolate_config(config, results)
        assert out["threshold"] == "42"

    def test_nested_config_dict(self) -> None:
        config = {"condition": {"field": "{{a.output}}", "value": 10}}
        results = {"a": {"output": "status"}}
        out = interpolate_config(config, results)
        assert out["condition"]["field"] == "status"

    def test_empty_results_no_crash(self) -> None:
        config = {"prompt": "Hello {{x.y}}"}
        out = interpolate_config(config, {})
        assert out["prompt"] == "Hello {{x.y}}"

    def test_no_templates_passthrough(self) -> None:
        config = {"prompt": "No templates here"}
        out = interpolate_config(config, {"a": {"b": "c"}})
        assert out["prompt"] == "No templates here"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andrewlonati/hestia && python -m pytest tests/test_workflow_interpolation.py -v --timeout=30`
Expected: FAIL — `ModuleNotFoundError: No module named 'hestia.workflows.interpolation'`

- [ ] **Step 3: Implement interpolation engine**

```python
# hestia/workflows/interpolation.py
"""
Variable interpolation for workflow node configs.

Resolves {{node_id.field.path}} references against prior node results.
Sandboxed: only resolves from the results dict, never external input.
"""

import json
import re
from typing import Any, Dict

INTERPOLATION_RE = re.compile(r"\{\{(\w+(?:\.\w+)*)\}\}")


def _resolve_path(data: Dict[str, Any], path: str) -> Any:
    """Resolve a dot-path like 'nodeA.response.content' against nested dicts."""
    current: Any = data
    for key in path.split("."):
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current


def interpolate_config(config: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Replace {{node_id.field}} references in config with values from results.

    - Only resolves from the results dict (populated by prior node outputs)
    - Unresolved references are left intact (safe default)
    - Works recursively on nested dicts
    """
    serialized = json.dumps(config)

    def replacer(match: re.Match) -> str:
        path = match.group(1)
        value = _resolve_path(results, path)
        if value is None:
            return match.group(0)  # Leave unresolved
        if isinstance(value, str):
            return value
        return str(value)

    interpolated = INTERPOLATION_RE.sub(replacer, serialized)
    return json.loads(interpolated)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/andrewlonati/hestia && python -m pytest tests/test_workflow_interpolation.py -v --timeout=30`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add hestia/workflows/interpolation.py tests/test_workflow_interpolation.py
git commit -m "feat(workflow): variable interpolation engine — {{node_id.field}} resolution"
```

---

### Task 2: Wire Interpolation into DAG Executor

**Files:**
- Modify: `hestia/workflows/executor.py` (line ~231, before executor_fn calls)
- Modify: `tests/test_workflow_executor.py` (add integration test)

- [ ] **Step 1: Write failing integration test**

Add to `tests/test_workflow_executor.py`:

```python
class TestVariableInterpolationIntegration:
    @pytest.mark.asyncio
    async def test_interpolation_in_linear_chain(self) -> None:
        """Node B's config references Node A's output via {{a.response}}."""
        nodes = [
            _node("a", NodeType.LOG, config={"message": "hello from A"}),
            _node("b", NodeType.LOG, config={"message": "A said: {{a.message}}"}),
        ]
        edges = [_edge("a", "b")]
        run = _run()

        executor = DAGExecutor()
        completed = await executor.execute(nodes, edges, run)

        # Node B's output should show the interpolated message
        b_exec = next(ne for ne in completed if ne.node_id == "b")
        assert b_exec.output_data["message"] == "A said: hello from A"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/andrewlonati/hestia && python -m pytest tests/test_workflow_executor.py::TestVariableInterpolationIntegration -v --timeout=30`
Expected: FAIL — config not interpolated, message is literal `{{a.message}}`

- [ ] **Step 3: Wire interpolation into executor**

In `hestia/workflows/executor.py`, add import at top:

```python
from hestia.workflows.interpolation import interpolate_config
```

Then in `_execute_node_task()`, before both `executor_fn(node.config, input_data)` calls (the semaphore-wrapped and unwrapped paths), replace `node.config` with interpolated config:

```python
        # Interpolate config with prior node results
        interpolated_config = interpolate_config(node.config, results)

        # Determine timeout
        timeout = (
            self._prompt_timeout
            if node.node_type == NodeType.RUN_PROMPT
            else self._node_timeout
        )

        # Acquire semaphore for LLM nodes only
        if node.node_type == NodeType.RUN_PROMPT:
            async with self._semaphore:
                output = await asyncio.wait_for(
                    executor_fn(interpolated_config, input_data),
                    timeout=timeout,
                )
        else:
            output = await asyncio.wait_for(
                executor_fn(interpolated_config, input_data),
                timeout=timeout,
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/andrewlonati/hestia && python -m pytest tests/test_workflow_executor.py::TestVariableInterpolationIntegration -v --timeout=30`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `cd /Users/andrewlonati/hestia && python -m pytest tests/test_workflow_executor.py -v --timeout=30`
Expected: All existing tests + new test pass

- [ ] **Step 6: Commit**

```bash
git add hestia/workflows/executor.py tests/test_workflow_executor.py
git commit -m "feat(workflow): wire variable interpolation into DAG executor"
```

---

### Task 3: Switch Node (N-ary Branching)

**Files:**
- Modify: `hestia/workflows/models.py` (add SWITCH to NodeType)
- Modify: `hestia/workflows/nodes.py` (add execute_switch + register)
- Modify: `hestia/workflows/executor.py` (generalize _mark_dead_paths for N-ary)
- Create: `tests/test_workflow_switch.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_workflow_switch.py
import pytest
from hestia.workflows.models import NodeType, WorkflowNode, WorkflowEdge, WorkflowRun
from hestia.workflows.nodes import execute_switch
from hestia.workflows.executor import DAGExecutor


def _node(nid: str, ntype: NodeType = NodeType.LOG, config: dict = None) -> WorkflowNode:
    return WorkflowNode(id=nid, workflow_id="wf-test", node_type=ntype,
                        label=nid, config=config or {})

def _edge(src: str, tgt: str, label: str = "") -> WorkflowEdge:
    return WorkflowEdge(id=f"e-{src}-{tgt}", workflow_id="wf-test",
                        source_node_id=src, target_node_id=tgt, edge_label=label)

def _run() -> WorkflowRun:
    from datetime import datetime, timezone
    return WorkflowRun(id="run-test", workflow_id="wf-test", workflow_version=1,
                       started_at=datetime.now(timezone.utc), trigger_source="manual")


class TestSwitchExecutor:
    @pytest.mark.asyncio
    async def test_switch_matches_case(self) -> None:
        config = {
            "field": "category",
            "cases": [
                {"value": "urgent", "label": "case_urgent"},
                {"value": "normal", "label": "case_normal"},
            ],
            "default_label": "case_default",
        }
        result = await execute_switch(config, {"category": "urgent"})
        assert result["branch"] == "case_urgent"

    @pytest.mark.asyncio
    async def test_switch_default(self) -> None:
        config = {
            "field": "category",
            "cases": [{"value": "urgent", "label": "case_urgent"}],
            "default_label": "case_default",
        }
        result = await execute_switch(config, {"category": "unknown"})
        assert result["branch"] == "case_default"

    @pytest.mark.asyncio
    async def test_switch_no_cases_returns_default(self) -> None:
        config = {"field": "x", "cases": [], "default_label": "fallback"}
        result = await execute_switch(config, {"x": "anything"})
        assert result["branch"] == "fallback"


class TestSwitchDAGExecution:
    @pytest.mark.asyncio
    async def test_switch_routes_to_correct_branch(self) -> None:
        """Switch node routes to matched case, skips other branches."""
        nodes = [
            _node("trigger", NodeType.MANUAL),
            _node("switch", NodeType.SWITCH, config={
                "field": "category",
                "cases": [
                    {"value": "urgent", "label": "case_urgent"},
                    {"value": "normal", "label": "case_normal"},
                ],
                "default_label": "case_default",
            }),
            _node("urgent_handler", config={"message": "handling urgent"}),
            _node("normal_handler", config={"message": "handling normal"}),
            _node("default_handler", config={"message": "handling default"}),
        ]
        edges = [
            _edge("trigger", "switch"),
            _edge("switch", "urgent_handler", label="case_urgent"),
            _edge("switch", "normal_handler", label="case_normal"),
            _edge("switch", "default_handler", label="case_default"),
        ]
        run = _run()

        # Mock trigger to produce category=urgent
        from unittest.mock import AsyncMock, patch
        mock_trigger = AsyncMock(return_value={"category": "urgent"})
        with patch.dict("hestia.workflows.nodes.NODE_EXECUTORS",
                        {NodeType.MANUAL: mock_trigger}):
            executor = DAGExecutor()
            completed = await executor.execute(nodes, edges, run)

        statuses = {ne.node_id: ne.status.value for ne in completed}
        assert statuses["urgent_handler"] == "success"
        assert statuses["normal_handler"] == "skipped"
        assert statuses["default_handler"] == "skipped"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andrewlonati/hestia && python -m pytest tests/test_workflow_switch.py -v --timeout=30`
Expected: FAIL — `NodeType has no member 'SWITCH'`

- [ ] **Step 3: Add SWITCH to NodeType enum**

In `hestia/workflows/models.py`, add to `NodeType`:

```python
    SWITCH = "switch"
```

- [ ] **Step 4: Implement execute_switch and register**

In `hestia/workflows/nodes.py`, add after `execute_if_else`:

```python
async def execute_switch(
    config: Dict[str, Any],
    input_data: Dict[str, Any],
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Execute a Switch node — N-ary condition branching.

    Config keys:
        field (str): dot-path to evaluate
        cases (list): [{"value": ..., "label": "case_X"}, ...]
        default_label (str): label for no-match fallback

    Returns:
        {"branch": "case_X"} — the label of the matched case
    """
    field_path = config.get("field", "")
    cases = config.get("cases", [])
    default_label = config.get("default_label", "default")

    actual = _resolve_path(input_data, field_path)

    for case in cases:
        if actual == case.get("value"):
            return {"branch": case["label"], "matched_value": actual}

    return {"branch": default_label, "matched_value": actual}
```

Add to `NODE_EXECUTORS`:

```python
    NodeType.SWITCH: execute_switch,
```

- [ ] **Step 5: Generalize _mark_dead_paths for N-ary branching**

In `hestia/workflows/executor.py`, update `_mark_dead_paths`:

```python
    def _mark_dead_paths(
        self,
        condition_node_id: str,
        branch: str,
        edge_labels: Dict[str, Dict[str, str]],
        results: Dict[str, Dict[str, Any]],
        skipped_nodes: Set[str],
        sorter: TopologicalSorter,
    ) -> None:
        """Mark nodes on dead paths of a condition/switch as skipped.

        For if_else: branch is "true"/"false" — skip the opposite.
        For switch: branch is "case_X" — skip all other case edges.
        """
        targets = edge_labels.get(condition_node_id, {})

        for target_id, label in targets.items():
            if label and label != branch:
                self._collect_downstream(target_id, edge_labels, skipped_nodes)
```

Also update the call site to handle SWITCH:

```python
        # Handle if_else/switch branching — mark dead-path nodes as skipped
        if node.node_type in (NodeType.IF_ELSE, NodeType.SWITCH) and isinstance(output, dict):
            branch = output.get("branch", "false")
            self._mark_dead_paths(
                node_id, branch, edge_labels, results, skipped_nodes, sorter
            )
```

- [ ] **Step 6: Run tests**

Run: `cd /Users/andrewlonati/hestia && python -m pytest tests/test_workflow_switch.py -v --timeout=30`
Expected: All pass

- [ ] **Step 7: Run full executor test suite**

Run: `cd /Users/andrewlonati/hestia && python -m pytest tests/test_workflow_executor.py tests/test_workflow_switch.py -v --timeout=30`
Expected: All pass (existing if_else tests still green)

- [ ] **Step 8: Commit**

```bash
git add hestia/workflows/models.py hestia/workflows/nodes.py hestia/workflows/executor.py tests/test_workflow_switch.py
git commit -m "feat(workflow): Switch node — N-ary branching with generalized dead-path marking"
```

---

### Task 4: Batch Layout Endpoint

**Files:**
- Modify: `hestia/workflows/database.py` (add batch_update_positions)
- Modify: `hestia/workflows/manager.py` (add batch_update_layout)
- Modify: `hestia/api/routes/workflows.py` (add PATCH endpoint)
- Modify: `tests/test_workflow_routes.py` (add endpoint test)

- [ ] **Step 1: Add batch_update_positions to database**

In `hestia/workflows/database.py`:

```python
    async def batch_update_positions(
        self, workflow_id: str, positions: list[dict],
    ) -> int:
        """Update position_x/position_y for multiple nodes atomically."""
        updated = 0
        for pos in positions:
            cursor = await self.connection.execute(
                """UPDATE workflow_nodes SET position_x=?, position_y=?
                   WHERE id=? AND workflow_id=?""",
                (pos["position_x"], pos["position_y"], pos["node_id"], workflow_id),
            )
            updated += cursor.rowcount
        await self.connection.commit()
        return updated
```

- [ ] **Step 2: Add batch_update_layout to manager**

In `hestia/workflows/manager.py`:

```python
    async def batch_update_layout(
        self, workflow_id: str, positions: list[dict],
    ) -> int:
        """Batch update node positions (from canvas drag operations)."""
        wf = await self.db.get_workflow(workflow_id)
        if not wf:
            raise ValueError(f"Workflow not found: {workflow_id}")
        return await self.db.batch_update_positions(workflow_id, positions)
```

- [ ] **Step 3: Add PATCH endpoint**

In `hestia/api/routes/workflows.py`, add schema and endpoint:

```python
class LayoutUpdateRequest(BaseModel):
    positions: List[Dict[str, Any]] = Field(
        ..., description="List of {node_id, position_x, position_y}"
    )


@router.patch("/{workflow_id}/layout")
async def batch_update_layout(
    workflow_id: str,
    request: LayoutUpdateRequest,
    _token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Batch update node positions (from canvas drag operations)."""
    try:
        manager = await get_workflow_manager()
        updated = await manager.batch_update_layout(workflow_id, request.positions)
        return {"updated": updated, "workflow_id": workflow_id}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=404)
    except Exception as e:
        logger.error(
            "Failed to update layout",
            component=LogComponent.WORKFLOW,
            data={"error": sanitize_for_log(e)},
        )
        return JSONResponse({"error": "Failed to update layout"}, status_code=500)
```

- [ ] **Step 4: Add route test**

In `tests/test_workflow_routes.py`, add:

```python
@pytest.mark.asyncio
async def test_batch_update_layout(client, mock_manager):
    mock_manager.batch_update_layout = AsyncMock(return_value=3)
    response = client.patch(
        "/v1/workflows/wf-123/layout",
        json={"positions": [
            {"node_id": "n1", "position_x": 100, "position_y": 200},
            {"node_id": "n2", "position_x": 300, "position_y": 400},
            {"node_id": "n3", "position_x": 500, "position_y": 600},
        ]},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["updated"] == 3
```

- [ ] **Step 5: Run tests**

Run: `cd /Users/andrewlonati/hestia && python -m pytest tests/test_workflow_routes.py -v --timeout=30`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add hestia/workflows/database.py hestia/workflows/manager.py hestia/api/routes/workflows.py tests/test_workflow_routes.py
git commit -m "feat(workflow): batch layout endpoint — PATCH /v1/workflows/{id}/layout"
```

---

## Phase P2A: Visual Canvas (Tasks 5-10)

*React Flow + WKWebView. Introduces npm toolchain.*

### Task 5: React Flow Project Scaffolding

**Files:**
- Create: `HestiaApp/WorkflowCanvas/` (entire project)
- Create: `HestiaApp/macOS/Resources/WorkflowCanvas/index.html` (built artifact)

- [ ] **Step 1: Scaffold Vite + React + TypeScript project**

```bash
cd /Users/andrewlonati/hestia/HestiaApp
npm create vite@latest WorkflowCanvas -- --template react-ts
cd WorkflowCanvas
npm install @xyflow/react
npm install -D vite-plugin-singlefile
```

- [ ] **Step 2: Configure vite for single-file output**

```typescript
// HestiaApp/WorkflowCanvas/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'

export default defineConfig({
  plugins: [react(), viteSingleFile()],
  base: './',
  build: {
    outDir: '../macOS/Resources/WorkflowCanvas',
    assetsInlineLimit: 100000000,
  }
})
```

- [ ] **Step 3: Create minimal App.tsx with React Flow**

```tsx
// HestiaApp/WorkflowCanvas/src/App.tsx
import { useCallback, useEffect, useState } from 'react'
import {
  ReactFlow,
  Controls,
  MiniMap,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Node,
  Edge,
  BackgroundVariant,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { bridge, BridgeMessage } from './bridge'
import { darkTheme } from './theme'

export default function App() {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])

  // Receive workflow data from Swift
  useEffect(() => {
    bridge.onLoadWorkflow((data) => {
      setNodes(data.nodes)
      setEdges(data.edges)
    })
    bridge.onUpdateNodeStatus((nodeId, status) => {
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId ? { ...n, data: { ...n.data, executionStatus: status } } : n
        )
      )
    })
    bridge.signalReady()
  }, [])

  // Send position changes to Swift (debounced in bridge)
  const handleNodesChange = useCallback(
    (changes: any) => {
      onNodesChange(changes)
      const moved = changes.filter((c: any) => c.type === 'position' && c.position)
      if (moved.length > 0) {
        bridge.sendNodesMoved(
          moved.map((c: any) => ({ id: c.id, x: c.position.x, y: c.position.y }))
        )
      }
    },
    [onNodesChange]
  )

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) => addEdge(connection, eds))
      bridge.sendEdgeCreated(connection)
    },
    [setEdges]
  )

  const onNodeClick = useCallback((_: any, node: Node) => {
    bridge.sendNodeSelected(node.id)
  }, [])

  return (
    <div style={{ width: '100vw', height: '100vh', ...darkTheme.container }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={handleNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Controls />
        <MiniMap style={darkTheme.minimap} />
        <Background variant={BackgroundVariant.Dots} color={darkTheme.dotColor} gap={20} />
      </ReactFlow>
    </div>
  )
}
```

- [ ] **Step 4: Create bridge.ts**

```typescript
// HestiaApp/WorkflowCanvas/src/bridge.ts

interface WorkflowData {
  nodes: any[]
  edges: any[]
}

interface Position {
  id: string
  x: number
  y: number
}

type MessageHandler = {
  loadWorkflow?: (data: WorkflowData) => void
  updateNodeStatus?: (nodeId: string, status: string) => void
}

const handlers: MessageHandler = {}
let debounceTimer: number | null = null

export const bridge = {
  signalReady() {
    window.webkit?.messageHandlers?.canvasReady?.postMessage('ready')
  },

  onLoadWorkflow(fn: (data: WorkflowData) => void) {
    handlers.loadWorkflow = fn
  },

  onUpdateNodeStatus(fn: (nodeId: string, status: string) => void) {
    handlers.updateNodeStatus = fn
  },

  sendNodesMoved(positions: Position[]) {
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
      window.webkit?.messageHandlers?.canvasAction?.postMessage(
        JSON.stringify({ type: 'nodesMoved', payload: positions })
      )
    }, 300) as unknown as number
  },

  sendEdgeCreated(connection: any) {
    window.webkit?.messageHandlers?.canvasAction?.postMessage(
      JSON.stringify({ type: 'edgeCreated', payload: connection })
    )
  },

  sendNodeSelected(nodeId: string) {
    window.webkit?.messageHandlers?.canvasAction?.postMessage(
      JSON.stringify({ type: 'nodeSelected', payload: { nodeId } })
    )
  },

  sendNodeDeleted(nodeId: string) {
    window.webkit?.messageHandlers?.canvasAction?.postMessage(
      JSON.stringify({ type: 'nodeDeleted', payload: { nodeId } })
    )
  },

  sendEdgeDeleted(edgeId: string) {
    window.webkit?.messageHandlers?.canvasAction?.postMessage(
      JSON.stringify({ type: 'edgeDeleted', payload: { edgeId } })
    )
  },
}

// Global functions called from Swift via evaluateJavaScript
;(window as any).loadWorkflow = (json: string) => {
  const data = JSON.parse(json)
  handlers.loadWorkflow?.(data)
}
;(window as any).updateNodeStatus = (nodeId: string, status: string) => {
  handlers.updateNodeStatus?.(nodeId, status)
}
```

- [ ] **Step 5: Create theme.ts**

```typescript
// HestiaApp/WorkflowCanvas/src/theme.ts
export const darkTheme = {
  container: {
    backgroundColor: '#110B03',
    color: '#E4DFD7',
  },
  minimap: {
    backgroundColor: '#0D0802',
    maskColor: 'rgba(235, 223, 209, 0.08)',
  },
  dotColor: 'rgba(254, 154, 0, 0.08)',
}
```

- [ ] **Step 6: Build and verify output**

```bash
cd /Users/andrewlonati/hestia/HestiaApp/WorkflowCanvas
npm run build
ls -la ../macOS/Resources/WorkflowCanvas/index.html
```

Expected: Single `index.html` file (1-2MB) in `macOS/Resources/WorkflowCanvas/`

- [ ] **Step 7: Add WorkflowCanvas/ to .gitignore (node_modules only) and commit**

Add to `.gitignore`:
```
HestiaApp/WorkflowCanvas/node_modules/
```

```bash
git add HestiaApp/WorkflowCanvas/src/ HestiaApp/WorkflowCanvas/package.json HestiaApp/WorkflowCanvas/tsconfig.json HestiaApp/WorkflowCanvas/vite.config.ts HestiaApp/macOS/Resources/WorkflowCanvas/index.html .gitignore
git commit -m "feat(workflow): React Flow canvas scaffolding with vite-plugin-singlefile"
```

---

### Task 6: WorkflowCanvasWebView (Swift-JS Bridge)

**Files:**
- Create: `HestiaApp/macOS/Views/Workflow/WorkflowCanvasWebView.swift`

- [ ] **Step 1: Create NSViewRepresentable with bidirectional bridge**

```swift
// HestiaApp/macOS/Views/Workflow/WorkflowCanvasWebView.swift
import SwiftUI
@preconcurrency import WebKit

struct WorkflowCanvasWebView: NSViewRepresentable {
    let workflowDetail: WorkflowDetail?
    let onNodeSelected: (String) -> Void
    let onNodesMoved: ([NodePosition]) -> Void
    let onEdgeCreated: (String, String, String?) -> Void  // source, target, sourceHandle
    let onNodeDeleted: (String) -> Void
    let onEdgeDeleted: (String) -> Void

    struct NodePosition {
        let id: String
        let x: Double
        let y: Double
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(
            onNodeSelected: onNodeSelected,
            onNodesMoved: onNodesMoved,
            onEdgeCreated: onEdgeCreated,
            onNodeDeleted: onNodeDeleted,
            onEdgeDeleted: onEdgeDeleted
        )
    }

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        let coordinator = context.coordinator
        config.userContentController.add(coordinator, name: "canvasReady")
        config.userContentController.add(coordinator, name: "canvasAction")

        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = coordinator
        webView.setValue(false, forKey: "drawsBackground")

        coordinator.webView = webView

        if let url = Bundle.main.url(
            forResource: "index",
            withExtension: "html",
            subdirectory: "WorkflowCanvas"
        ) {
            let resourceDir = url.deletingLastPathComponent()
            webView.loadFileURL(url, allowingReadAccessTo: resourceDir)
        }

        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        let coordinator = context.coordinator
        guard coordinator.canvasReady else { return }
        guard let detail = workflowDetail else { return }
        guard coordinator.currentWorkflowId != detail.id else { return }

        coordinator.injectWorkflow(detail)
    }

    // MARK: - Coordinator

    @MainActor
    class Coordinator: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
        var webView: WKWebView?
        var canvasReady = false
        var currentWorkflowId: String?
        var pendingDetail: WorkflowDetail?

        let onNodeSelected: (String) -> Void
        let onNodesMoved: ([NodePosition]) -> Void
        let onEdgeCreated: (String, String, String?) -> Void
        let onNodeDeleted: (String) -> Void
        let onEdgeDeleted: (String) -> Void

        init(
            onNodeSelected: @escaping (String) -> Void,
            onNodesMoved: @escaping ([NodePosition]) -> Void,
            onEdgeCreated: @escaping (String, String, String?) -> Void,
            onNodeDeleted: @escaping (String) -> Void,
            onEdgeDeleted: @escaping (String) -> Void
        ) {
            self.onNodeSelected = onNodeSelected
            self.onNodesMoved = onNodesMoved
            self.onEdgeCreated = onEdgeCreated
            self.onNodeDeleted = onNodeDeleted
            self.onEdgeDeleted = onEdgeDeleted
        }

        // MARK: - WKScriptMessageHandler

        func userContentController(
            _ userContentController: WKUserContentController,
            didReceive message: WKScriptMessage
        ) {
            switch message.name {
            case "canvasReady":
                canvasReady = true
                if let pending = pendingDetail {
                    injectWorkflow(pending)
                    pendingDetail = nil
                }
            case "canvasAction":
                guard let body = message.body as? String,
                      let data = body.data(using: .utf8),
                      let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                      let type = json["type"] as? String,
                      let payload = json["payload"]
                else { return }

                handleCanvasAction(type: type, payload: payload)
            default:
                break
            }
        }

        private func handleCanvasAction(type: String, payload: Any) {
            switch type {
            case "nodeSelected":
                if let dict = payload as? [String: Any],
                   let nodeId = dict["nodeId"] as? String {
                    onNodeSelected(nodeId)
                }
            case "nodesMoved":
                if let positions = payload as? [[String: Any]] {
                    let mapped = positions.compactMap { p -> NodePosition? in
                        guard let id = p["id"] as? String,
                              let x = p["x"] as? Double,
                              let y = p["y"] as? Double
                        else { return nil }
                        return NodePosition(id: id, x: x, y: y)
                    }
                    onNodesMoved(mapped)
                }
            case "edgeCreated":
                if let dict = payload as? [String: Any],
                   let source = dict["source"] as? String,
                   let target = dict["target"] as? String {
                    onEdgeCreated(source, target, dict["sourceHandle"] as? String)
                }
            case "nodeDeleted":
                if let dict = payload as? [String: Any],
                   let nodeId = dict["nodeId"] as? String {
                    onNodeDeleted(nodeId)
                }
            case "edgeDeleted":
                if let dict = payload as? [String: Any],
                   let edgeId = dict["edgeId"] as? String {
                    onEdgeDeleted(edgeId)
                }
            default:
                #if DEBUG
                print("[CanvasWebView] Unknown action: \(type)")
                #endif
            }
        }

        // MARK: - Inject Workflow

        func injectWorkflow(_ detail: WorkflowDetail) {
            guard let webView else { return }
            currentWorkflowId = detail.id

            let rfNodes = detail.nodes.map { node -> [String: Any] in
                [
                    "id": node.id,
                    "type": node.nodeType,
                    "position": ["x": node.positionX, "y": node.positionY],
                    "data": ["label": node.label, "nodeType": node.nodeType, "config": [:] as [String: Any]],
                ]
            }
            let rfEdges = detail.edges.map { edge -> [String: Any] in
                var e: [String: Any] = [
                    "id": edge.id,
                    "source": edge.sourceNodeId,
                    "target": edge.targetNodeId,
                ]
                if !edge.edgeLabel.isEmpty {
                    e["label"] = edge.edgeLabel
                    e["sourceHandle"] = edge.edgeLabel
                }
                return e
            }

            let payload: [String: Any] = ["nodes": rfNodes, "edges": rfEdges]
            guard let jsonData = try? JSONSerialization.data(withJSONObject: payload),
                  let jsonString = String(data: jsonData, encoding: .utf8)
            else { return }

            let escaped = jsonString
                .replacingOccurrences(of: "\\", with: "\\\\")
                .replacingOccurrences(of: "'", with: "\\'")

            webView.evaluateJavaScript("loadWorkflow('\(escaped)')") { _, error in
                #if DEBUG
                if let error { print("[CanvasWebView] JS error: \(error)") }
                #endif
            }
        }

        func updateNodeStatus(_ nodeId: String, _ status: String) {
            webView?.evaluateJavaScript("updateNodeStatus('\(nodeId)', '\(status)')") { _, _ in }
        }

        // MARK: - Navigation Policy

        func webView(
            _ webView: WKWebView,
            decidePolicyFor navigationAction: WKNavigationAction,
            decisionHandler: @escaping @MainActor @Sendable (WKNavigationActionPolicy) -> Void
        ) {
            if navigationAction.navigationType == .other {
                decisionHandler(.allow)
                return
            }
            decisionHandler(.cancel)
        }
    }
}
```

- [ ] **Step 2: Regenerate Xcode project and build**

```bash
cd /Users/andrewlonati/hestia/HestiaApp && xcodegen generate
xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build 2>&1 | tail -5
```

Expected: BUILD SUCCEEDED

- [ ] **Step 3: Commit**

```bash
git add HestiaApp/macOS/Views/Workflow/WorkflowCanvasWebView.swift
git commit -m "feat(workflow): WorkflowCanvasWebView — bidirectional Swift-JS bridge"
```

---

### Task 7: Canvas Integration in Detail Pane

**Files:**
- Create: `HestiaApp/macOS/Views/Workflow/MacWorkflowCanvasPane.swift`
- Modify: `HestiaApp/macOS/Views/Workflow/MacWorkflowDetailPane.swift` (add toggle)
- Modify: `HestiaApp/macOS/ViewModels/MacWorkflowViewModel.swift` (add canvas state)
- Modify: `HestiaApp/macOS/Services/APIClient+Workflows.swift` (add batchUpdateLayout)

- [ ] **Step 1: Add canvas state to ViewModel**

In `MacWorkflowViewModel.swift`, add:

```swift
    @Published var showCanvas = false
    @Published var selectedNodeId: String?
```

Add bridge handler methods and batch layout call. Wire SSE subscription for execution overlay.

- [ ] **Step 2: Create MacWorkflowCanvasPane**

Wrap `WorkflowCanvasWebView` with toolbar (toggle button, add-node menu) and connect to ViewModel.

- [ ] **Step 3: Add canvas/list toggle to MacWorkflowDetailPane**

Add a segmented control or toggle button in the detail header to switch between list view and canvas view.

- [ ] **Step 4: Add batchUpdateLayout to APIClient**

```swift
    func batchUpdateLayout(_ workflowId: String, positions: [[String: Any]]) async throws {
        struct LayoutRequest: Codable { let positions: [[String: AnyCodableValue]] }
        // Use the batch endpoint
        let _: EmptyResponse = try await patch(
            "/v1/workflows/\(workflowId)/layout",
            body: ["positions": positions]
        )
    }
```

- [ ] **Step 5: Build both targets**

```bash
cd /Users/andrewlonati/hestia/HestiaApp && xcodegen generate
xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build
xcodebuild -scheme HestiaApp -destination 'generic/platform=iOS' build
```

- [ ] **Step 6: Commit**

```bash
git add HestiaApp/macOS/Views/Workflow/ HestiaApp/macOS/ViewModels/ HestiaApp/macOS/Services/
git commit -m "feat(workflow): canvas integration — list/canvas toggle, bridge wiring, batch layout"
```

---

### Task 8: Node Inspector (Native SwiftUI)

**Files:**
- Create: `HestiaApp/macOS/Views/Workflow/MacNodeInspectorView.swift`

- [ ] **Step 1: Create inspector view**

Native SwiftUI sidebar showing selected node's config. Form fields vary by node type:
- **run_prompt**: prompt text, model selection
- **call_tool**: tool name picker, parameters
- **notify**: message, channel
- **log**: message, level
- **if_else**: field, operator, value
- **switch**: field, cases list, default label
- **trigger nodes**: cron expression (schedule) or manual label

- [ ] **Step 2: Wire to ViewModel**

Inspector reads `selectedNodeId` from ViewModel, displays node config, sends updates via API.

- [ ] **Step 3: Build and commit**

```bash
git commit -m "feat(workflow): native SwiftUI node inspector — per-type config editing"
```

---

### Task 9: Execution Overlay (SSE → Canvas)

**Files:**
- Modify: `HestiaApp/macOS/ViewModels/MacWorkflowViewModel.swift` (SSE subscription)

- [ ] **Step 1: Subscribe to SSE in ViewModel**

When a workflow is triggered, subscribe to `/v1/workflows/stream` SSE. Parse events and forward `node_started`/`node_completed`/`node_failed` to canvas via `coordinator.updateNodeStatus()`.

- [ ] **Step 2: Update React Flow nodes with execution state**

In `App.tsx`, use the `executionStatus` data field to apply CSS classes:
- pending: gray border
- running: amber pulsing animation
- success: green border + checkmark
- failed: red border + error icon
- skipped: dimmed opacity

- [ ] **Step 3: Rebuild canvas bundle**

```bash
cd /Users/andrewlonati/hestia/HestiaApp/WorkflowCanvas && npm run build
```

- [ ] **Step 4: Build and commit**

```bash
git add HestiaApp/macOS/ViewModels/ HestiaApp/WorkflowCanvas/src/ HestiaApp/macOS/Resources/WorkflowCanvas/
git commit -m "feat(workflow): execution overlay — SSE → canvas node status coloring"
```

---

### Task 10: Final Integration + Full Test Suite

- [ ] **Step 1: Run full backend test suite**

```bash
cd /Users/andrewlonati/hestia && python -m pytest tests/ -v --timeout=30
```

Expected: All 2809+ tests pass

- [ ] **Step 2: Build both Xcode targets**

```bash
cd /Users/andrewlonati/hestia/HestiaApp && xcodegen generate
xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build
xcodebuild -scheme HestiaApp -destination 'generic/platform=iOS' build
```

- [ ] **Step 3: Run @hestia-reviewer on all changed files**

- [ ] **Step 4: Update CLAUDE.md**

Add WorkflowCanvas to project structure. Update endpoint count. Note npm toolchain in project context.

- [ ] **Step 5: Update SPRINT.md**

Mark P2 complete. Update sprint history.

- [ ] **Step 6: Final commit**

```bash
git commit -m "docs: P2 complete — workflow canvas, switch node, variable interpolation"
```

---

## Execution Order Summary

| Task | Phase | Hours | Dependencies |
|------|-------|-------|-------------|
| 1. Interpolation engine | P2B | 1-2h | None |
| 2. Wire interpolation into executor | P2B | 1h | Task 1 |
| 3. Switch node | P2B | 2-3h | None (parallel with 1-2) |
| 4. Batch layout endpoint | P2B | 1-2h | None (parallel with 1-3) |
| 5. React Flow scaffolding | P2A | 3-4h | None |
| 6. WorkflowCanvasWebView | P2A | 3-4h | Task 5 |
| 7. Canvas integration | P2A | 3-4h | Task 6 |
| 8. Node inspector | P2A | 3-4h | Task 7 |
| 9. Execution overlay | P2A | 2-3h | Tasks 7, 5 |
| 10. Final integration | — | 2h | All above |

**P2B total: 5-8h** (Tasks 1-4, parallelizable)
**P2A total: 14-19h** (Tasks 5-9, sequential)
**Integration: 2h** (Task 10)
**Grand total: 21-29h**
