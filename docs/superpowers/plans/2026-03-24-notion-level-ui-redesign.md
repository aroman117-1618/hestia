# Notion-Level UI Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Elevate Hestia's macOS UI to Notion-level quality with a dual-mode Research tab (2D Research Canvas + 3D Knowledge Atlas), shared component library, and cross-linking infrastructure.

**Architecture:** Unified React Flow canvas (client-side routing for Workflow + Research Canvas in one Vite project), SwiftUI ViewModifier-based component library, SQLite-backed entity reference index for cross-linking. Apple design language (SF Symbols, geometric indicators, spring animations) — no emoji as UI chrome.

**Tech Stack:** React 19 + @xyflow/react 12.6 + Vite 6.3 (canvas), SwiftUI + WKWebView (macOS), Python/FastAPI + SQLite (backend), SceneKit (3D Atlas)

**Spec:** `docs/plans/notion-level-ui-redesign-second-opinion-2026-03-24.md`
**Discovery:** `docs/discoveries/notion-level-ui-redesign-2026-03-24.md`

---

## File Structure Overview

### Phase 1-lite: Panel Modifier (~4h)
```
Create: HestiaApp/macOS/DesignSystem/Components/HestiaPanelModifier.swift
Modify: HestiaApp/macOS/Views/Wiki/MacWikiView.swift
Modify: HestiaApp/macOS/Views/Wiki/Diagrams/DiagramKit/DiagramContainerView.swift
Modify: (any other views found via grep — Task 1 Step 5 catches remaining instances)
```

### Phase 4a: Reference Index Skeleton (~8h)
```
Create: hestia/research/references.py          (models + database for entity_references)
Create: tests/test_entity_references.py
Modify: hestia/research/database.py            (add entity_references table)
Modify: hestia/api/routes/research.py          (add reference endpoints)
```

### Phase 2: Research Canvas (~25-35h)
```
# React (unified canvas project — replaces current WorkflowCanvas)
Modify: HestiaApp/WorkflowCanvas/package.json          (add react-router-dom)
Create: HestiaApp/WorkflowCanvas/src/router.tsx         (route definitions)
Modify: HestiaApp/WorkflowCanvas/src/main.tsx           (add router provider)
Create: HestiaApp/WorkflowCanvas/src/WorkflowApp.tsx    (current App.tsx content, renamed)
Create: HestiaApp/WorkflowCanvas/src/ResearchApp.tsx    (research canvas)
Create: HestiaApp/WorkflowCanvas/src/shared/bridge.ts   (unified bridge protocol)
Create: HestiaApp/WorkflowCanvas/src/shared/theme.ts    (shared theme constants)
Create: HestiaApp/WorkflowCanvas/src/shared/types.ts    (shared TypeScript types)
Create: HestiaApp/WorkflowCanvas/src/research/nodes/EntityNode.tsx
Create: HestiaApp/WorkflowCanvas/src/research/nodes/FactNode.tsx
Create: HestiaApp/WorkflowCanvas/src/research/nodes/PrincipleNode.tsx
Create: HestiaApp/WorkflowCanvas/src/research/nodes/MemoryNode.tsx
Create: HestiaApp/WorkflowCanvas/src/research/nodes/AnnotationNode.tsx
Create: HestiaApp/WorkflowCanvas/src/research/nodes/GroupNode.tsx
Create: HestiaApp/WorkflowCanvas/src/research/components/FloatingActionBar.tsx
Create: HestiaApp/WorkflowCanvas/src/research/components/NodeMiniMap.tsx
Modify: HestiaApp/WorkflowCanvas/src/bridge.ts          (extract to shared/bridge.ts)
Modify: HestiaApp/WorkflowCanvas/src/theme.ts           (extract to shared/theme.ts)
Modify: HestiaApp/WorkflowCanvas/vite.config.ts         (hash-based routing)

# Swift
Create: HestiaApp/macOS/Views/Research/ResearchCanvasWebView.swift
Create: HestiaApp/macOS/ViewModels/ResearchCanvasViewModel.swift
Create: HestiaApp/macOS/Views/Research/ResearchCanvasSidebar.swift
Create: HestiaApp/macOS/Views/Research/ResearchCanvasDetailPane.swift
Create: HestiaApp/macOS/Models/ResearchCanvasModels.swift
Modify: HestiaApp/macOS/Views/Research/ResearchView.swift    (add .canvas mode)

# Backend
Create: hestia/research/boards.py              (board CRUD + persistence)
Create: tests/test_research_boards.py
Modify: hestia/research/database.py            (add boards tables)
Modify: hestia/api/routes/research.py          (add board + distill endpoints)
```

### Phase 1-full: Component Extraction (~8-12h)
```
Create: HestiaApp/macOS/DesignSystem/Components/HestiaDetailPane.swift
Create: HestiaApp/macOS/DesignSystem/Components/HestiaContentRow.swift
Create: HestiaApp/macOS/DesignSystem/Components/HestiaSidebarSection.swift
Modify: HestiaApp/macOS/Views/Wiki/MacWikiDetailPane.swift
Modify: HestiaApp/macOS/Views/Workflow/MacWorkflowDetailPane.swift
Modify: HestiaApp/macOS/Views/Research/NodeDetailPopover.swift
Modify: HestiaApp/macOS/Views/Research/ResearchCanvasSidebar.swift
Modify: HestiaApp/macOS/Views/Explorer/ExplorerView.swift
Modify: HestiaApp/macOS/Views/Command/CommandView.swift
```

### Phase 4b: Cross-Link UI (~12-22h)
```
Create: HestiaApp/macOS/DesignSystem/Components/HestiaCrossLinkBadge.swift
Create: HestiaApp/Shared/Models/DeepLinkModels.swift
Create: hestia/research/indexer.py              (batch entity mention indexer)
Create: tests/test_reference_indexer.py
Modify: HestiaApp/macOS/Views/WorkspaceRootView.swift    (deep link handler)
Modify: HestiaApp/macOS/Views/Research/ResearchCanvasDetailPane.swift  (cross-links section)
Modify: HestiaApp/macOS/Views/Research/NodeDetailPopover.swift        (cross-links section)
Modify: hestia/api/routes/research.py          (indexer trigger endpoint)
```

### Phase 3: 3D Atlas Refinement (~10-15h)
```
Modify: HestiaApp/macOS/Views/Research/MacSceneKitGraphView.swift  (centrality sizing, recency color, confidence opacity)
Modify: HestiaApp/macOS/Views/Research/NodeDetailPopover.swift     (use HestiaDetailPane)
Modify: HestiaApp/macOS/ViewModels/MacNeuralNetViewModel.swift     (centrality calculation)
```

---

## Task 1: HestiaPanelModifier (Phase 1-lite)

**Files:**
- Create: `HestiaApp/macOS/DesignSystem/Components/HestiaPanelModifier.swift`
- Modify: `HestiaApp/macOS/Views/Wiki/MacWikiView.swift:13-14,22-23`
- Modify: `HestiaApp/macOS/Views/Wiki/Diagrams/DiagramKit/DiagramContainerView.swift:28-29`

- [ ] **Step 1: Create the panel modifier**

```swift
// HestiaApp/macOS/DesignSystem/Components/HestiaPanelModifier.swift
import SwiftUI

struct HestiaPanelModifier: ViewModifier {
    var cornerRadius: CGFloat = MacCornerRadius.panel

    func body(content: Content) -> some View {
        content
            .background(MacColors.panelBackground)
            .clipShape(RoundedRectangle(cornerRadius: cornerRadius))
            .overlay(
                RoundedRectangle(cornerRadius: cornerRadius)
                    .strokeBorder(MacColors.cardBorder, lineWidth: 1)
            )
    }
}

extension View {
    func hestiaPanel(cornerRadius: CGFloat = MacCornerRadius.panel) -> some View {
        modifier(HestiaPanelModifier(cornerRadius: cornerRadius))
    }
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd /Users/andrewlonati/hestia && xcodebuild -scheme HestiaWorkspace -configuration Debug build 2>&1 | tail -5`
Expected: BUILD SUCCEEDED

- [ ] **Step 3: Migrate MacWikiView to use `.hestiaPanel()`**

Replace the duplicated `.background(MacColors.panelBackground).clipShape(...).overlay(...)` pattern in `MacWikiView.swift` (lines 13-14 and 22-23) with `.hestiaPanel()`.

- [ ] **Step 4: Migrate DiagramContainerView**

Replace the pattern in `DiagramContainerView.swift` (lines 28-29) with `.hestiaPanel()`.

- [ ] **Step 5: Search for remaining instances across all macOS views**

Run: `grep -rn "MacColors.panelBackground" HestiaApp/macOS/Views/` to find all remaining instances. Migrate each to `.hestiaPanel()`.

- [ ] **Step 6: Verify build still succeeds**

Run: `xcodebuild -scheme HestiaWorkspace -configuration Debug build 2>&1 | tail -5`
Expected: BUILD SUCCEEDED

- [ ] **Step 7: Commit**

```bash
git add HestiaApp/macOS/DesignSystem/Components/HestiaPanelModifier.swift
git add -u HestiaApp/macOS/Views/
git commit -m "feat(design-system): extract HestiaPanelModifier from duplicated panel styling"
```

---

## Task 2: Entity References Table (Phase 4a — Backend)

**Files:**
- Create: `hestia/research/references.py`
- Create: `tests/test_entity_references.py`
- Modify: `hestia/research/database.py`
- Modify: `hestia/api/routes/research.py`

- [ ] **Step 1: Write the failing test for reference models**

```python
# tests/test_entity_references.py
import pytest
from hestia.research.references import EntityReference, ReferenceModule

class TestEntityReferenceModels:
    def test_reference_creation(self):
        ref = EntityReference(
            entity_id="ent-123",
            module=ReferenceModule.WORKFLOW,
            item_id="wf-step-456",
            context="Used in 'Trading Bot' workflow step 3",
            user_id="user-1",
        )
        assert ref.entity_id == "ent-123"
        assert ref.module == ReferenceModule.WORKFLOW
        assert ref.item_id == "wf-step-456"

    def test_reference_to_dict(self):
        ref = EntityReference(
            entity_id="ent-123",
            module=ReferenceModule.CHAT,
            item_id="msg-789",
            context="Mentioned in chat",
            user_id="user-1",
        )
        d = ref.to_dict()
        assert d["entityId"] == "ent-123"
        assert d["module"] == "chat"
        assert d["itemId"] == "msg-789"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_entity_references.py -v --timeout=30`
Expected: FAIL — `ModuleNotFoundError: No module named 'hestia.research.references'`

- [ ] **Step 3: Write the reference models**

```python
# hestia/research/references.py
"""Entity reference models and database operations for cross-linking."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import uuid

from hestia.logging import get_logger

logger = get_logger()


class ReferenceModule(str, Enum):
    """Modules that can reference entities."""
    WORKFLOW = "workflow"
    CHAT = "chat"
    COMMAND = "command"
    RESEARCH_CANVAS = "research_canvas"
    MEMORY = "memory"


@dataclass
class EntityReference:
    """A reference to an entity from another module."""
    entity_id: str
    module: ReferenceModule
    item_id: str
    context: str
    user_id: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "entityId": self.entity_id,
            "module": self.module.value,
            "itemId": self.item_id,
            "context": self.context,
            "userId": self.user_id,
            "createdAt": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> EntityReference:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            entity_id=data.get("entity_id", data.get("entityId", "")),
            module=ReferenceModule(data.get("module", "memory")),
            item_id=data.get("item_id", data.get("itemId", "")),
            context=data.get("context", ""),
            user_id=data.get("user_id", data.get("userId", "")),
            created_at=data.get("created_at", data.get("createdAt", "")),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_entity_references.py -v --timeout=30`
Expected: PASS

- [ ] **Step 5: Write failing test for database operations**

```python
# Add to tests/test_entity_references.py
@pytest.mark.asyncio
class TestEntityReferenceDatabase:
    async def test_add_and_get_references(self, tmp_path):
        from hestia.research.database import ResearchDatabase
        db = ResearchDatabase(str(tmp_path / "test.db"))
        await db.initialize()

        ref = EntityReference(
            entity_id="ent-123",
            module=ReferenceModule.WORKFLOW,
            item_id="wf-456",
            context="Step 3 of Trading Bot",
            user_id="user-1",
        )
        await db.add_entity_reference(ref)

        refs = await db.get_entity_references("ent-123")
        assert len(refs) == 1
        assert refs[0].module == ReferenceModule.WORKFLOW

    async def test_get_references_by_module(self, tmp_path):
        from hestia.research.database import ResearchDatabase
        db = ResearchDatabase(str(tmp_path / "test.db"))
        await db.initialize()

        for module in [ReferenceModule.WORKFLOW, ReferenceModule.CHAT, ReferenceModule.CHAT]:
            ref = EntityReference(
                entity_id="ent-123",
                module=module,
                item_id=f"item-{module.value}",
                context=f"Reference from {module.value}",
                user_id="user-1",
            )
            await db.add_entity_reference(ref)

        refs = await db.get_entity_references("ent-123", module=ReferenceModule.CHAT)
        assert len(refs) == 2

    async def test_delete_references_by_item(self, tmp_path):
        from hestia.research.database import ResearchDatabase
        db = ResearchDatabase(str(tmp_path / "test.db"))
        await db.initialize()

        ref = EntityReference(
            entity_id="ent-123",
            module=ReferenceModule.WORKFLOW,
            item_id="wf-456",
            context="Test",
            user_id="user-1",
        )
        await db.add_entity_reference(ref)
        await db.delete_entity_references_by_item(ReferenceModule.WORKFLOW, "wf-456")

        refs = await db.get_entity_references("ent-123")
        assert len(refs) == 0
```

- [ ] **Step 6: Run test to verify it fails**

Run: `python -m pytest tests/test_entity_references.py::TestEntityReferenceDatabase -v --timeout=30`
Expected: FAIL — `AttributeError: 'ResearchDatabase' object has no attribute 'add_entity_reference'`

- [ ] **Step 7: Add entity_references table to ResearchDatabase**

Add to `hestia/research/database.py` in the `_create_tables()` method:

```python
CREATE TABLE IF NOT EXISTS entity_references (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    module TEXT NOT NULL,
    item_id TEXT NOT NULL,
    context TEXT DEFAULT '',
    user_id TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(entity_id, module, item_id)
);
CREATE INDEX IF NOT EXISTS idx_entity_references_entity ON entity_references(entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_references_module ON entity_references(module, item_id);
```

Add methods `add_entity_reference()`, `get_entity_references()`, `delete_entity_references_by_item()` to the database class.

- [ ] **Step 8: Run test to verify it passes**

Run: `python -m pytest tests/test_entity_references.py -v --timeout=30`
Expected: All PASS

- [ ] **Step 9: Write failing test for API endpoint**

```python
# Add to tests/test_entity_references.py
@pytest.mark.asyncio
class TestEntityReferenceAPI:
    async def test_get_references_endpoint(self, test_client):
        """GET /v1/research/entities/{entity_id}/references returns references."""
        response = await test_client.get("/v1/research/entities/ent-123/references")
        assert response.status_code == 200
        data = response.json()
        assert "references" in data
```

- [ ] **Step 10: Add API endpoints to research routes**

Add to `hestia/api/routes/research.py`:

```python
@router.get("/entities/{entity_id}/references")
async def get_entity_references(
    entity_id: str,
    module: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """Get all cross-module references for an entity."""
    ...

@router.post("/entities/{entity_id}/references")
async def add_entity_reference(entity_id: str, request: AddReferenceRequest):
    """Manually add a cross-module reference."""
    ...

@router.delete("/entities/{entity_id}/references/{reference_id}")
async def delete_entity_reference(entity_id: str, reference_id: str):
    """Delete a specific reference."""
    ...
```

- [ ] **Step 11: Run full test suite to verify no regressions**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: All pass, no regressions

- [ ] **Step 12: Commit**

```bash
git add hestia/research/references.py tests/test_entity_references.py
git add -u hestia/research/database.py hestia/api/routes/research.py
git commit -m "feat(research): add entity_references table and API for cross-linking"
```

---

## Task 3: Performance Prototype (Phase 2 — GO/NO-GO GATE)

**Files:**
- Modify: `HestiaApp/WorkflowCanvas/package.json` (add react-router-dom)
- Create: `HestiaApp/WorkflowCanvas/src/research/PerformancePrototype.tsx`

**CRITICAL: This task is a go/no-go gate. If the prototype shows >800MB memory or <30fps at 300 nodes, STOP and re-evaluate the architecture before proceeding.**

- [ ] **Step 1: Add react-router-dom to the project**

```bash
cd HestiaApp/WorkflowCanvas && npm install react-router-dom
```

- [ ] **Step 2: Create a 300-node stress test component**

```tsx
// HestiaApp/WorkflowCanvas/src/research/PerformancePrototype.tsx
import { useCallback, useMemo } from 'react';
import {
  ReactFlow, Background, Controls, MiniMap,
  type Node, type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

function generateNodes(count: number): Node[] {
  const nodes: Node[] = [];
  const cols = Math.ceil(Math.sqrt(count));
  for (let i = 0; i < count; i++) {
    nodes.push({
      id: `node-${i}`,
      position: { x: (i % cols) * 220, y: Math.floor(i / cols) * 120 },
      data: {
        label: `Entity ${i}`,
        type: ['entity', 'fact', 'principle', 'memory'][i % 4],
        connections: Math.floor(Math.random() * 12),
      },
      type: 'default',
    });
  }
  return nodes;
}

function generateEdges(nodes: Node[]): Edge[] {
  const edges: Edge[] = [];
  for (let i = 1; i < nodes.length; i++) {
    if (Math.random() > 0.6) {
      edges.push({
        id: `edge-${i}`,
        source: nodes[Math.floor(Math.random() * i)].id,
        target: nodes[i].id,
      });
    }
  }
  return edges;
}

export default function PerformancePrototype() {
  const nodes = useMemo(() => generateNodes(300), []);
  const edges = useMemo(() => generateEdges(nodes), [nodes]);
  const onNodeDrag = useCallback(() => {}, []);

  return (
    <div style={{ width: '100vw', height: '100vh', background: '#110B03' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodeDrag={onNodeDrag}
        fitView
        minZoom={0.1}
        maxZoom={2}
      >
        <Background color="rgba(224,160,80,0.06)" gap={24} size={1} />
        <Controls />
        <MiniMap style={{ background: '#0D0802' }} />
      </ReactFlow>
      <div style={{
        position: 'fixed', top: 8, right: 8, background: 'rgba(0,0,0,0.8)',
        color: '#E0A050', padding: '8px 12px', borderRadius: 8, fontSize: 12,
      }}>
        PERF TEST: {nodes.length} nodes, {edges.length} edges
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Add routing scaffold**

```tsx
// HestiaApp/WorkflowCanvas/src/router.tsx
import { createHashRouter, RouterProvider } from 'react-router-dom';
import WorkflowApp from './WorkflowApp';
import PerformancePrototype from './research/PerformancePrototype';

const router = createHashRouter([
  { path: '/', element: <WorkflowApp /> },
  { path: '/workflow', element: <WorkflowApp /> },
  { path: '/research', element: <PerformancePrototype /> },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
```

Update `main.tsx` to use `AppRouter` instead of `App` directly. Rename current `App.tsx` to `WorkflowApp.tsx`.

- [ ] **Step 4: Build and test locally**

```bash
cd HestiaApp/WorkflowCanvas && npm run build
```

Open the built `index.html` directly in a browser. Navigate to `#/research` to see 300 nodes.

- [ ] **Step 5: Test in WKWebView on Mac Mini**

Deploy the built canvas to the Mac Mini. Open the macOS app. Modify `ResearchView.swift` temporarily to load the canvas WebView at `#/research`. Profile with Instruments:

**Measurements required:**
- Web process memory (Activity Monitor → WKWebView process)
- Frame rate (Instruments → Core Animation)
- Interaction latency (pan/zoom responsiveness)

**Go/no-go thresholds:**
- Memory: <800MB for web process
- Frame rate: >30fps during pan/zoom
- Interaction: <100ms response to drag

- [ ] **Step 6: Document results**

Write results to `docs/plans/research-canvas-perf-prototype-results.md`. Include memory, fps, and interaction latency numbers. If PASS, proceed with Phase 2. If FAIL, re-evaluate (options: cap at 200 nodes, use virtualization, or switch to native SwiftUI canvas).

- [ ] **Step 7: Commit**

```bash
git add -A HestiaApp/WorkflowCanvas/
git commit -m "feat(canvas): performance prototype — 300 node React Flow stress test with routing"
```

---

## Task 4: Unified Bridge Protocol (Phase 2)

**Files:**
- Create: `HestiaApp/WorkflowCanvas/src/shared/bridge.ts`
- Create: `HestiaApp/WorkflowCanvas/src/shared/types.ts`
- Modify: `HestiaApp/WorkflowCanvas/src/WorkflowApp.tsx` (use shared bridge)

- [ ] **Step 1: Define typed message protocol**

```typescript
// HestiaApp/WorkflowCanvas/src/shared/types.ts

/** Canvas context — which canvas is sending the message */
export type CanvasContext = 'workflow' | 'research';

/** Messages from React → Swift */
export type BridgeAction =
  | { type: 'ready'; canvas: CanvasContext }
  | { type: 'nodesMoved'; canvas: CanvasContext; payload: { moves: Array<{ id: string; x: number; y: number }> } }
  | { type: 'nodeSelected'; canvas: CanvasContext; payload: { nodeId: string } }
  | { type: 'nodeDeleted'; canvas: CanvasContext; payload: { nodeId: string } }
  | { type: 'edgeCreated'; canvas: CanvasContext; payload: { source: string; target: string; sourceHandle?: string } }
  | { type: 'edgeDeleted'; canvas: CanvasContext; payload: { edgeId: string } }
  // Workflow-specific
  | { type: 'addStep'; canvas: 'workflow'; payload: { stepType: string; title: string; positionX: number; positionY: number; afterNodeId?: string } }
  // Research-specific
  | { type: 'nodesSelected'; canvas: 'research'; payload: { nodeIds: string[] } }
  | { type: 'annotationCreated'; canvas: 'research'; payload: { id: string; text: string; x: number; y: number } }
  | { type: 'annotationUpdated'; canvas: 'research'; payload: { id: string; text: string } }
  | { type: 'annotationDeleted'; canvas: 'research'; payload: { id: string } }
  | { type: 'groupCreated'; canvas: 'research'; payload: { id: string; nodeIds: string[]; label: string } }
  | { type: 'groupUpdated'; canvas: 'research'; payload: { id: string; label: string } }
  | { type: 'distillRequested'; canvas: 'research'; payload: { nodeIds: string[] } }
  | { type: 'principleApproved'; canvas: 'research'; payload: { nodeId: string } }
  | { type: 'principleRejected'; canvas: 'research'; payload: { nodeId: string } }
  | { type: 'layoutSaved'; canvas: 'research'; payload: { boardId: string; positions: Array<{ id: string; x: number; y: number }> } }
  | { type: 'crossLinkRequested'; canvas: 'research'; payload: { entityId: string; targetModule: string } };
```

- [ ] **Step 2: Create unified bridge**

```typescript
// HestiaApp/WorkflowCanvas/src/shared/bridge.ts
import type { BridgeAction, CanvasContext } from './types';

declare global {
  interface Window {
    webkit?: {
      messageHandlers?: {
        canvasAction?: { postMessage: (msg: string) => void };
      };
    };
  }
}

let debounceTimer: number | null = null;

function send(action: BridgeAction): void {
  window.webkit?.messageHandlers?.canvasAction?.postMessage(
    JSON.stringify(action)
  );
}

function sendDebounced(action: BridgeAction, ms: number = 300): void {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = window.setTimeout(() => send(action), ms);
}

export function createBridge(canvas: CanvasContext) {
  return {
    signalReady: () => send({ type: 'ready', canvas }),
    sendNodesMoved: (moves: Array<{ id: string; x: number; y: number }>) =>
      sendDebounced({ type: 'nodesMoved', canvas, payload: { moves } }),
    sendNodeSelected: (nodeId: string) =>
      send({ type: 'nodeSelected', canvas, payload: { nodeId } }),
    sendNodeDeleted: (nodeId: string) =>
      send({ type: 'nodeDeleted', canvas, payload: { nodeId } }),
    sendEdgeCreated: (source: string, target: string, sourceHandle?: string) =>
      send({ type: 'edgeCreated', canvas, payload: { source, target, sourceHandle } }),
    sendEdgeDeleted: (edgeId: string) =>
      send({ type: 'edgeDeleted', canvas, payload: { edgeId } }),
    // Research-only
    ...(canvas === 'research' ? {
      sendNodesSelected: (nodeIds: string[]) =>
        send({ type: 'nodesSelected', canvas: 'research', payload: { nodeIds } }),
      sendDistillRequested: (nodeIds: string[]) =>
        send({ type: 'distillRequested', canvas: 'research', payload: { nodeIds } }),
      sendAnnotationCreated: (id: string, text: string, x: number, y: number) =>
        send({ type: 'annotationCreated', canvas: 'research', payload: { id, text, x, y } }),
      sendAnnotationUpdated: (id: string, text: string) =>
        send({ type: 'annotationUpdated', canvas: 'research', payload: { id, text } }),
      sendAnnotationDeleted: (id: string) =>
        send({ type: 'annotationDeleted', canvas: 'research', payload: { id } }),
      sendGroupCreated: (id: string, nodeIds: string[], label: string) =>
        send({ type: 'groupCreated', canvas: 'research', payload: { id, nodeIds, label } }),
      sendPrincipleApproved: (nodeId: string) =>
        send({ type: 'principleApproved', canvas: 'research', payload: { nodeId } }),
      sendPrincipleRejected: (nodeId: string) =>
        send({ type: 'principleRejected', canvas: 'research', payload: { nodeId } }),
      sendLayoutSaved: (boardId: string, positions: Array<{ id: string; x: number; y: number }>) =>
        send({ type: 'layoutSaved', canvas: 'research', payload: { boardId, positions } }),
      sendCrossLinkRequested: (entityId: string, targetModule: string) =>
        send({ type: 'crossLinkRequested', canvas: 'research', payload: { entityId, targetModule } }),
    } : {
      // Workflow-only
      sendAddStep: (stepType: string, title: string, positionX: number, positionY: number, afterNodeId?: string) =>
        send({ type: 'addStep', canvas: 'workflow', payload: { stepType, title, positionX, positionY, afterNodeId } }),
    }),
  };
}
```

- [ ] **Step 3: Migrate WorkflowApp to use shared bridge**

Update `WorkflowApp.tsx` to import `createBridge('workflow')` from `shared/bridge.ts` instead of the old `bridge.ts`. Verify existing workflow canvas behavior is unchanged.

- [ ] **Step 4: Build and verify workflow canvas still works**

```bash
cd HestiaApp/WorkflowCanvas && npm run build
```

Open in macOS app, verify workflow canvas loads and all interactions work (node drag, edge create, node select, add step).

- [ ] **Step 5: Commit**

```bash
git add -A HestiaApp/WorkflowCanvas/src/shared/
git add -u HestiaApp/WorkflowCanvas/src/
git commit -m "feat(canvas): unified bridge protocol with typed messages for workflow + research"
```

---

## Task 5: Research Canvas React Implementation (Phase 2)

**Files:**
- Create: `HestiaApp/WorkflowCanvas/src/research/ResearchApp.tsx`
- Create: `HestiaApp/WorkflowCanvas/src/research/nodes/*.tsx` (6 node types)
- Create: `HestiaApp/WorkflowCanvas/src/research/components/FloatingActionBar.tsx`
- Modify: `HestiaApp/WorkflowCanvas/src/shared/theme.ts`

This is the largest task. Break into sub-steps:

- [ ] **Step 1: Create shared theme**

Extract `theme.ts` constants to `shared/theme.ts`. Add research-specific colors:

```typescript
// Entity type colors (matching MacColors)
export const nodeColors = {
  entity: { bg: 'rgba(74,158,255,0.06)', border: 'rgba(74,158,255,0.15)', dot: '#4A9EFF' },
  fact: { bg: 'rgba(0,212,146,0.06)', border: 'rgba(0,212,146,0.15)', dot: '#00D492' },
  principle: { bg: 'rgba(128,80,200,0.06)', border: 'rgba(128,80,200,0.15)', dot: '#8050C8' },
  memory: { bg: 'rgba(228,223,215,0.04)', border: 'rgba(228,223,215,0.1)', dot: '#888' },
  annotation: { bg: 'rgba(224,160,80,0.04)', border: 'rgba(224,160,80,0.1)', dot: '#E0A050' },
  group: { bg: 'rgba(224,160,80,0.02)', border: 'rgba(224,160,80,0.08)', dot: 'transparent' },
};

// Text colors — all UI chrome text must use these, never inline hex strings
export const textColors = {
  primary: '#E4DFD7',
  secondary: 'rgba(228,223,215,0.5)',
  faint: 'rgba(228,223,215,0.3)',
  placeholder: 'rgba(228,223,215,0.4)',
  accent: '#E0A050',
};
```

- [ ] **Step 2: Create EntityNode**

```tsx
// HestiaApp/WorkflowCanvas/src/research/nodes/EntityNode.tsx
import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { nodeColors, textColors } from '../../shared/theme';

interface EntityNodeData {
  label: string;
  entityType: string;
  connectionCount: number;
  summary?: string;
}

function EntityNode({ data, selected }: NodeProps<EntityNodeData>) {
  const colors = nodeColors.entity;
  return (
    <div style={{
      background: colors.bg,
      border: `1.5px solid ${selected ? colors.dot : colors.border}`,
      borderRadius: 12, padding: 14, minWidth: 160,
      boxShadow: selected ? `0 0 20px ${colors.bg}` : 'none',
      transition: 'border-color 0.15s, box-shadow 0.15s',
    }}>
      <Handle type="target" position={Position.Left} style={{ background: colors.dot, width: 8, height: 8 }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <div style={{ width: 8, height: 8, borderRadius: '50%', background: colors.dot }} />
        <span style={{ fontSize: 13, fontWeight: 600, color: textColors.primary }}>{data.label}</span>
      </div>
      {data.summary && (
        <div style={{ fontSize: 11, color: textColors.faint, lineHeight: 1.5, marginBottom: 8 }}>
          {data.summary.slice(0, 80)}{data.summary.length > 80 ? '...' : ''}
        </div>
      )}
      <div style={{ display: 'flex', gap: 6 }}>
        <span style={{ fontSize: 10, background: colors.bg, color: colors.dot, padding: '2px 8px', borderRadius: 4 }}>
          {data.entityType}
        </span>
        <span style={{ fontSize: 10, color: textColors.faint }}>
          {data.connectionCount} conn.
        </span>
      </div>
      <Handle type="source" position={Position.Right} style={{ background: colors.dot, width: 8, height: 8 }} />
    </div>
  );
}

export default memo(EntityNode);
```

- [ ] **Step 3: Create FactNode, PrincipleNode, MemoryNode, AnnotationNode, GroupNode**

Follow the same pattern as EntityNode. Key differences:
- **FactNode**: Shows confidence bar (0-1), temporal indicator (valid_at date), status via geometric indicator (solid dot = valid, hollow ring = uncertain, triangle = invalidated)
- **PrincipleNode**: Shows approval status via geometric indicator (hollow ring + subtle pulse = pending, solid dot green = approved, solid triangle red = rejected). In-place editable text. Approve/Reject buttons when `status === 'pending'`. All text colors and UI chrome colors MUST use `shared/theme.ts` imports — no inline hex strings
- **MemoryNode**: Shows content preview (first 100 chars), type badge, importance score
- **AnnotationNode**: Free-text editable area (textarea), no handles, lighter styling
- **GroupNode**: Uses React Flow sub-flow pattern (`type: 'group'`), collapsible, label editable

- [ ] **Step 4: Create FloatingActionBar**

```tsx
// HestiaApp/WorkflowCanvas/src/research/components/FloatingActionBar.tsx
// NOTE: All colors must use shared/theme.ts imports — no inline hex strings
import { memo } from 'react';

interface FloatingActionBarProps {
  selectedCount: number;
  position: { x: number; y: number };
  onDistill: () => void;
  onGroup: () => void;
  onRemove: () => void;
}

function FloatingActionBar({ selectedCount, position, onDistill, onGroup, onRemove }: FloatingActionBarProps) {
  if (selectedCount < 2) return null;

  return (
    <div style={{
      position: 'absolute', left: position.x, top: position.y - 48, zIndex: 1000,
      display: 'flex', gap: 4, background: '#1A1208',
      border: '1px solid rgba(224,160,80,0.15)', borderRadius: 10,
      padding: 4, boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
    }}>
      <button onClick={onDistill} style={{
        padding: '6px 14px', background: 'rgba(128,80,200,0.15)',
        border: '1px solid rgba(128,80,200,0.3)', borderRadius: 8,
        color: '#8050C8', fontSize: 12, fontWeight: 600, cursor: 'pointer',
      }}>
        Distill Principle
      </button>
      <button onClick={onGroup} style={{
        padding: '6px 14px', background: 'rgba(224,160,80,0.08)',
        border: '1px solid rgba(224,160,80,0.12)', borderRadius: 8,
        color: 'rgba(228,223,215,0.6)', fontSize: 12, cursor: 'pointer',
      }}>
        Group
      </button>
      <button onClick={onRemove} style={{
        padding: '6px 14px', background: 'rgba(255,100,103,0.06)',
        border: '1px solid rgba(255,100,103,0.1)', borderRadius: 8,
        color: 'rgba(255,100,103,0.5)', fontSize: 12, cursor: 'pointer',
      }}>
        Remove
      </button>
      <span style={{
        padding: '6px 10px', fontSize: 11, color: 'rgba(228,223,215,0.3)',
        alignSelf: 'center',
      }}>
        {selectedCount} selected
      </span>
    </div>
  );
}

export default memo(FloatingActionBar);
```

- [ ] **Step 5: Create ResearchApp (main canvas component)**

Build `ResearchApp.tsx` using the same structure as `WorkflowApp.tsx` but with:
- Research-specific node types registered (`nodeTypes` outside component, memoized)
- Multi-select enabled (`selectionOnDrag`, `selectionMode`)
- Lasso selection handler → shows FloatingActionBar
- `onSelectionChange` callback to track selected nodes
- Bridge integration via `createBridge('research')`
- Swift → React handlers: `window.loadBoard()`, `window.updatePrincipleStatus()`, `window.highlightEntity()`

- [ ] **Step 6: Update router**

Replace `PerformancePrototype` with `ResearchApp` at the `/research` route.

- [ ] **Step 7: Build and test**

```bash
cd HestiaApp/WorkflowCanvas && npm run build
```

Verify both `#/workflow` and `#/research` routes render correctly in a browser.

- [ ] **Step 8: Commit**

```bash
git add -A HestiaApp/WorkflowCanvas/src/research/
git add -u HestiaApp/WorkflowCanvas/src/
git commit -m "feat(canvas): research canvas with 6 node types, floating action bar, lasso selection"
```

---

## Task 6: Research Canvas Swift Integration (Phase 2)

**Files:**
- Create: `HestiaApp/macOS/Views/Research/ResearchCanvasWebView.swift`
- Create: `HestiaApp/macOS/ViewModels/ResearchCanvasViewModel.swift`
- Create: `HestiaApp/macOS/Views/Research/ResearchCanvasSidebar.swift`
- Create: `HestiaApp/macOS/Views/Research/ResearchCanvasDetailPane.swift`
- Create: `HestiaApp/macOS/Models/ResearchCanvasModels.swift`
- Modify: `HestiaApp/macOS/Views/Research/ResearchView.swift`

- [ ] **Step 1: Create ResearchCanvasModels**

Swift models for board state, board items, sidebar sections. Use `Codable` for bridge serialization.

- [ ] **Step 2: Create ResearchCanvasViewModel**

`@MainActor ObservableObject` with:
- Board CRUD (load, save, delete)
- Entity/memory/fact/principle loading from research API
- Selected node tracking
- Distill principle flow (API call → update canvas)
- Cross-link data loading from entity_references API
- Sidebar section state (expanded/collapsed, search filters)

- [ ] **Step 3: Create ResearchCanvasWebView**

`NSViewRepresentable` following `WorkflowCanvasWebView.swift` pattern (287 lines):
- Load bundled HTML with `#/research` hash route
- `WKScriptMessageHandler` for `canvasAction` messages
- Coordinator handles all research-specific message types
- `loadBoard()` method serializes board state to JSON, injects via `evaluateJavaScript`
- Memory management: `loadHTMLString("", baseURL: nil)` on disappear, re-inject on appear
- Shared `WKProcessPool`: Create a static `WKProcessPool` instance shared between `WorkflowCanvasWebView` and `ResearchCanvasWebView` to reduce per-process memory overhead. Pass it via the `WKWebViewConfiguration` in `makeNSView()`

- [ ] **Step 4: Create ResearchCanvasSidebar**

SwiftUI sidebar with collapsible sections:
- Memories (with search, type filter, importance sort)
- Entities (with search, type filter)
- Principles (with status filter: pending/approved/rejected)
- Pinned (items on current board)
- Collections (saved boards)
- Investigations (URL analyses from investigate module)

Each section uses `DisclosureGroup` with count badge. Items are draggable onto the canvas (send add-to-board message via bridge).

- [ ] **Step 5: Create ResearchCanvasDetailPane**

Detail pane for selected entity/fact/principle/memory. Sections:
- Header (type dot + name + type badge)
- Description (editable on tap)
- Temporal Facts (for entities — list of bi-temporal facts)
- Connected (linked entities with type-colored dots)
- Cross-Links (from entity_references — links to Workflows, Chat, Command Center)
- Actions (Approve/Reject for principles, Mark Outdated for facts)

- [ ] **Step 6: Add `.canvas` mode to ResearchView**

Add `case canvas` to `ResearchMode` enum. Add mode toggle in Research tab header (Research Canvas | Knowledge Atlas). Wire up the new views in the switch statement.

- [ ] **Step 7: Verify build**

Run: `xcodebuild -scheme HestiaWorkspace -configuration Debug build 2>&1 | tail -5`
Expected: BUILD SUCCEEDED

- [ ] **Step 8: Commit**

```bash
git add HestiaApp/macOS/Views/Research/ResearchCanvas*.swift
git add HestiaApp/macOS/ViewModels/ResearchCanvasViewModel.swift
git add HestiaApp/macOS/Models/ResearchCanvasModels.swift
git add -u HestiaApp/macOS/Views/Research/ResearchView.swift
git commit -m "feat(research): research canvas Swift integration — WebView, ViewModel, sidebar, detail pane"
```

---

## Task 7: Board Persistence Backend (Phase 2)

**Files:**
- Create: `hestia/research/boards.py`
- Create: `tests/test_research_boards.py`
- Modify: `hestia/research/database.py`
- Modify: `hestia/api/routes/research.py`

- [ ] **Step 1: Write failing tests for board CRUD**

Test board creation, retrieval, update, deletion. Board has: id, name, layout_json (JSON blob with node positions and groups), created_at, updated_at.

- [ ] **Step 2: Add boards table to ResearchDatabase**

```sql
CREATE TABLE IF NOT EXISTS research_boards (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT 'Untitled Board',
    layout_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

- [ ] **Step 3: Implement board CRUD in boards.py**

Manager pattern: `ResearchBoardManager` with async CRUD methods. Follow singleton pattern (`get_research_board_manager()` async factory).

**Design decision:** Board state uses a JSON blob (`layout_json`) rather than normalized `board_items` table. This is a conscious simplification for V1 — the blob stores node positions, groups, and annotations as a single serialized object. Normalized tables can be added later if query patterns demand it.

- [ ] **Step 4: Add API endpoints**

```
POST   /v1/research/boards              — create board
GET    /v1/research/boards              — list boards
GET    /v1/research/boards/{board_id}   — get board
PUT    /v1/research/boards/{board_id}   — update board (name, layout)
DELETE /v1/research/boards/{board_id}   — delete board
```

- [ ] **Step 5: Write failing test for distill-from-selection endpoint**

```python
async def test_distill_from_selection(self, test_client):
    response = await test_client.post("/v1/research/principles/distill-from-selection", json={
        "entity_ids": ["ent-1", "ent-2", "ent-3"],
        "board_id": "board-1",
    })
    assert response.status_code == 200
    assert "principle" in response.json()
```

- [ ] **Step 6: Implement distill-from-selection endpoint**

`POST /v1/research/principles/distill-from-selection` — Takes entity IDs, loads their content + connections, calls inference to propose a principle, returns proposed principle with confidence score and source references. Principle created with status=`pending`.

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=30`

- [ ] **Step 8: Commit**

```bash
git add hestia/research/boards.py tests/test_research_boards.py
git add -u hestia/research/database.py hestia/api/routes/research.py
git commit -m "feat(research): board persistence + distill-from-selection endpoint"
```

---

## Task 8: Component Extraction (Phase 1-full)

**Files:**
- Create: `HestiaApp/macOS/DesignSystem/Components/HestiaDetailPane.swift`
- Create: `HestiaApp/macOS/DesignSystem/Components/HestiaContentRow.swift`
- Create: `HestiaApp/macOS/DesignSystem/Components/HestiaSidebarSection.swift`
- Modify: Multiple view files (Wiki, Workflow, Explorer, Research)

By this point, Phase 2 has been built and we can see real duplication patterns. Extract only what's confirmed duplicated.

- [ ] **Step 1: Audit actual duplication across all detail panes**

Read all detail pane files (MacWikiDetailPane, MacWorkflowDetailPane, NodeDetailPopover, ResearchCanvasDetailPane) and identify the exact shared pattern. Document which parts are common vs unique.

- [ ] **Step 2: Create HestiaSidebarSection (collapsible)**

```swift
struct HestiaSidebarSection<Content: View>: View {
    let title: String
    var count: Int? = nil
    @Binding var isExpanded: Bool
    @ViewBuilder let content: () -> Content

    var body: some View {
        DisclosureGroup(isExpanded: $isExpanded) {
            content()
        } label: {
            HStack {
                Text(title)
                    .font(MacTypography.label)
                    .foregroundColor(MacColors.textPrimary)
                Spacer()
                if let count {
                    Text("\(count)")
                        .font(MacTypography.caption)
                        .foregroundColor(MacColors.textFaint)
                }
            }
        }
        .padding(.horizontal, MacSpacing.md)
    }
}
```

- [ ] **Step 3: Create HestiaContentRow**

Standardized row with: leading icon (colored dot or SF Symbol), title, subtitle, optional trailing accessory.

- [ ] **Step 4: Create HestiaDetailPane**

Generic detail pane with: header slot, divider, scrollable content slot, optional action bar footer. Handles loading/error/empty states with consistent treatment.

- [ ] **Step 5: Migrate Research sidebar to use HestiaSidebarSection**

- [ ] **Step 6: Migrate at least 2 other views to use new components**

Choose Wiki sidebar and Explorer sidebar as migration targets.

- [ ] **Step 7: Verify build**

Run: `xcodebuild -scheme HestiaWorkspace -configuration Debug build 2>&1 | tail -5`

- [ ] **Step 8: Commit**

```bash
git add HestiaApp/macOS/DesignSystem/Components/
git add -u HestiaApp/macOS/Views/
git commit -m "feat(design-system): extract HestiaDetailPane, HestiaContentRow, HestiaSidebarSection"
```

---

## Task 9: Cross-Link UI (Phase 4b)

**Files:**
- Create: `HestiaApp/Shared/Models/DeepLinkModels.swift`
- Create: `HestiaApp/macOS/DesignSystem/Components/HestiaCrossLinkBadge.swift`
- Create: `hestia/research/indexer.py`
- Create: `tests/test_reference_indexer.py`
- Modify: `HestiaApp/macOS/Views/WorkspaceRootView.swift`
- Modify: `HestiaApp/macOS/Views/Research/ResearchCanvasDetailPane.swift`

- [ ] **Step 1: Create HestiaDeepLink enum**

```swift
// HestiaApp/Shared/Models/DeepLinkModels.swift
enum HestiaDeepLink: Hashable {
    case entity(id: String)
    case fact(id: String)
    case workflow(id: String, stepId: String? = nil)
    case chat(conversationId: String, messageId: String? = nil)
    case researchCanvas(boardId: String, entityId: String? = nil)
}
```

- [ ] **Step 2: Add navigation handler to WorkspaceRootView**

Handle deep links by switching `currentView` and passing the target ID to the relevant ViewModel.

- [ ] **Step 3: Create batch entity reference indexer**

```python
# hestia/research/indexer.py
"""Batch indexer for entity references across modules."""

async def index_workflow_references(research_db, workflow_db) -> int:
    """Scan workflow steps for entity mentions, update entity_references."""
    ...

async def index_research_canvas_references(research_db) -> int:
    """Index entities pinned to research canvas boards."""
    ...

async def run_batch_index(research_db, workflow_db) -> dict:
    """Run all indexers. Returns counts per module."""
    ...
```

- [ ] **Step 4: Add indexer trigger endpoint**

`POST /v1/research/references/reindex` — triggers batch indexing, returns counts.

- [ ] **Step 5: Add cross-link badges to entity detail views**

Create `HestiaCrossLinkBadge` — small pill showing module icon + count. Add "Referenced in" section to ResearchCanvasDetailPane and NodeDetailPopover.

- [ ] **Step 6: Test deep link navigation end-to-end**

Click a cross-link badge in Research Canvas detail pane → navigates to the correct Workflow/Chat view with the target highlighted.

- [ ] **Step 7: Commit**

```bash
git add HestiaApp/Shared/Models/DeepLinkModels.swift
git add HestiaApp/macOS/DesignSystem/Components/HestiaCrossLinkBadge.swift
git add hestia/research/indexer.py tests/test_reference_indexer.py
git add -u HestiaApp/macOS/Views/WorkspaceRootView.swift
git add -u HestiaApp/macOS/Views/Research/ResearchCanvasDetailPane.swift
git commit -m "feat(research): cross-linking UI — deep links, reference indexer, cross-link badges"
```

---

## Task 10: 3D Knowledge Atlas Refinement (Phase 3)

**Files:**
- Modify: `HestiaApp/macOS/Views/Research/MacSceneKitGraphView.swift`
- Modify: `HestiaApp/macOS/ViewModels/MacNeuralNetViewModel.swift`
- Modify: `HestiaApp/macOS/Views/Research/NodeDetailPopover.swift`

- [ ] **Step 1: Add degree-centrality sizing to ViewModel**

Calculate connection count per node. Expose as `nodeScale` dictionary. Nodes with more connections render larger (1.0x baseline, up to 2.5x for highly connected).

- [ ] **Step 2: Add recency color saturation**

Newer entities render with full color saturation. Entities older than 30 days fade toward desaturated (multiply saturation by `max(0.3, 1.0 - daysSinceUpdate / 90)`).

- [ ] **Step 3: Add confidence opacity**

High confidence facts/principles render at full opacity. Low confidence (<0.3) render at 40% opacity. Provides visual weight to well-established knowledge.

- [ ] **Step 4: Apply HestiaPanelModifier to NodeDetailPopover**

Replace the hardcoded amber background in NodeDetailPopover with `.hestiaPanel()`. Add "Cross-Links" section using the same pattern from ResearchCanvasDetailPane.

- [ ] **Step 5: Cap at 300 nodes with clustering**

If total node count exceeds 300, collapse low-centrality communities into single representative nodes. Show "N nodes hidden" badge. Click to expand.

- [ ] **Step 6: Verify build and visual appearance**

Run build. Open Research tab → Knowledge Atlas mode. Verify nodes render with correct sizing, color saturation, and opacity.

- [ ] **Step 7: Commit**

```bash
git add -u HestiaApp/macOS/Views/Research/ HestiaApp/macOS/ViewModels/MacNeuralNetViewModel.swift
git commit -m "feat(research): knowledge atlas refinements — centrality sizing, recency color, confidence opacity"
```

---

## Task 11: Deploy Pipeline + CI/CD Update

**Files:**
- Modify: `scripts/deploy-to-mini.sh`
- Modify: `HestiaApp/project.yml` (if canvas output path changes)

- [ ] **Step 1: Update deploy script to build canvas**

Add `cd HestiaApp/WorkflowCanvas && npm install && npm run build` before the rsync step.

- [ ] **Step 2: Verify project.yml includes canvas resources**

The WorkflowCanvas output already goes to `macOS/Resources/WorkflowCanvas/`. Since we're using the same project with client-side routing, no project.yml changes needed.

- [ ] **Step 3: Test full deploy flow**

```bash
./scripts/deploy-to-mini.sh
```

Verify both canvas routes work on Mac Mini.

- [ ] **Step 4: Commit**

```bash
git add -u scripts/deploy-to-mini.sh
git commit -m "fix(deploy): add canvas npm build step to deploy pipeline"
```

---

## Task 12: Final Validation + Documentation

- [ ] **Step 1: Run full test suite**

```bash
python -m pytest tests/ -v --timeout=30
```

All tests pass.

- [ ] **Step 2: Run @hestia-build-validator**

Verify both macOS and iOS targets compile.

- [ ] **Step 3: Run @hestia-ui-auditor**

4-layer UI wiring audit on all new and modified Research views.

- [ ] **Step 4: Run @hestia-reviewer**

Code review on all changed files.

- [ ] **Step 5: Update CLAUDE.md**

- Add Research Canvas to project structure
- Update endpoint count
- Update test count
- Note unified canvas architecture

- [ ] **Step 6: Update SPRINT.md**

Add UI Redesign sprint entry with workstream status.

- [ ] **Step 7: Final commit**

```bash
git add -u CLAUDE.md SPRINT.md
git commit -m "docs: update project docs for notion-level UI redesign"
```
