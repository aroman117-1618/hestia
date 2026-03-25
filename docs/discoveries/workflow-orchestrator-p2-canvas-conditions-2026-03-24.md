# Discovery Report: Workflow Orchestrator P2 — Visual Canvas + Conditions

**Date:** 2026-03-24
**Confidence:** High
**Decision:** Build P2 using WebView + React Flow (bundled via `vite-plugin-singlefile`) for the visual canvas, with ConditionEvaluator extended to support switch nodes and variable interpolation. AudioKit Flow confirmed viable as native fallback but React Flow is the pragmatic choice given existing WKWebView infrastructure.

## Hypothesis

Can we build a production-quality visual node editor (canvas with drag/drop, zoom/pan, edge drawing) and enhanced condition system (switch nodes, multi-port routing, variable interpolation) on top of the completed P1 engine, using WebView + React Flow bundled into the macOS app?

---

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** P1 engine complete with 15 API endpoints, node CRUD, position fields already in schema. MarkdownWebView pattern proven in codebase (WKWebView + loadFileURL + JS bridge). WorkflowModels.swift already has positionX/positionY. Existing ConditionEvaluator has 12 operators with safe dot-path traversal. All backend plumbing (nodes, edges, runs, SSE events) is wired. | **Weaknesses:** Vite's default ES module output is incompatible with WKWebView (type="module" not supported). Adding npm/Vite introduces a second build pipeline. JS-Swift bridge debugging crosses language boundaries. Current ConditionEvaluator only handles simple field comparisons — no expressions, no variable interpolation, no switch/case. No batch position update endpoint (canvas moves generate many PATCH calls). |
| **External** | **Opportunities:** React Flow v12 is mature (25K+ stars, used by Stripe/Discord). `vite-plugin-singlefile` solves the WKWebView bundling problem (single HTML with all JS/CSS inlined). AudioKit Flow confirmed to support multi-output labeled ports (Gemini validated). WWDC 2025 announced native SwiftUI WebView (macOS 26) — future migration path. React Flow has a [Workflow Editor template](https://reactflow.dev/ui/templates/workflow-editor) for exactly this use case. | **Threats:** `vite-plugin-singlefile` bundles entire app into one HTML — could be large (1.5-2MB) if not tree-shaken carefully. React Flow v12 had breaking changes from v11 — must pin version. WKWebView has memory overhead (~30-50MB base) vs native SwiftUI. WebView content doesn't perfectly match native macOS look/feel (selection, context menus, keyboard shortcuts). AudioKit Flow is only 390 stars — risky for long-term maintenance. |

---

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | React Flow canvas in WKWebView with Swift-JS bridge. Batch position update endpoint (`PATCH /v1/workflows/{id}/layout`). ConditionEvaluator switch node type. Variable interpolation (mustache-style `{{node_id.field}}`). Real-time execution overlay (SSE → canvas node coloring). | Node config inspector panel in native SwiftUI (sidebar). |
| **Low Priority** | Minimap and keyboard shortcuts. Auto-layout (dagre/elkjs). Undo/redo stack. | Sugiyama layout algorithm. Semantic zoom (show config at high zoom). Execution replay/scrubber. |

---

## Argue (Best Case)

**React Flow + vite-plugin-singlefile is the right call:**
- React Flow eliminates 70% of the canvas engineering (zoom, pan, edge routing, selection, snapping, keyboard shortcuts, minimap are all built-in)
- `vite-plugin-singlefile` produces a single `index.html` with all JS/CSS inlined — no ES module issues, works perfectly with `loadFileURL()`. This is the exact pattern used by offline Capacitor/Cordova apps
- The existing MarkdownWebView coordinator pattern (template ready → content injection via evaluateJavaScript) maps directly to canvas initialization (template ready → inject workflow data)
- Custom React Flow nodes are just React components — creating 7 node type renderers (prompt, tool, notify, log, if_else, switch, trigger) is straightforward
- Bidirectional communication via `WKScriptMessageHandler` (JS→Swift) and `evaluateJavaScript` (Swift→JS) is well-documented and proven in the codebase

**ConditionEvaluator extension is clean:**
- The existing `_OPERATORS` dict + `_resolve_path()` dot-path traversal already handles the hard parts
- Switch node is just an if_else with N outputs instead of 2 — same evaluator, different branch routing
- Variable interpolation (`{{node_id.field}}`) can be applied as a pre-processing step on node config before execution — keeps interpolation logic separate from node executors
- JMESPath is overkill for P2 — simple mustache-style `{{path}}` replacement covers 90% of use cases

**The backend is already ready:**
- Node positions (position_x, position_y) are persisted in SQLite and returned in API responses
- Edge labels ("true"/"false") already support if_else routing — extending to switch ("case_1", "case_2", "default") uses the same mechanism
- The SSE event bus already publishes node_started/node_completed/node_failed — the canvas just subscribes and colors nodes

---

## Refute (Devil's Advocate)

**WebView canvas risks:**
- **Bundle size.** React Flow v12 + React 19 + ReactDOM = ~300-400KB minified+gzipped. With `vite-plugin-singlefile` inlining everything (no gzip for local files), the raw HTML could be 1.5-2MB. This is a one-time load but adds to app bundle size.
- **Memory overhead.** WKWebView uses a separate process (~30-50MB baseline). With React Flow rendering 50+ nodes, this could climb to 80-100MB. On M1 with 16GB this is fine; on M1 with 8GB it's noticeable.
- **Non-native feel.** Context menus, keyboard shortcuts (Cmd+Z undo), selection behavior, and scrollbar appearance will differ from native SwiftUI. CSS can approximate but not perfectly match macOS native UI.
- **Bridge latency accumulation.** Every node drag/move generates a position update that crosses the JS→Swift bridge (1-5ms per message). Dragging 10 nodes simultaneously = 10-50ms of bridge overhead per frame. Solution: debounce position updates and batch them.

**ConditionEvaluator extension risks:**
- **Switch node complexity.** If_else has 2 output ports (true/false). Switch has N ports (case_1, case_2, ..., default). The executor's `_mark_dead_paths` logic currently assumes binary branching — needs generalization for N-ary branching.
- **Variable interpolation injection.** If `{{node_id.field}}` is resolved from user-provided node outputs, a malicious workflow could inject template syntax. Mitigation: interpolation only resolves from the `results` dict, never from external input, and the regex is strict.
- **Circular references in interpolation.** Node A references Node B's output, Node B references Node A's output. Topological execution order prevents this at runtime, but config-time validation should catch it.

**AudioKit Flow as alternative:**
- Gemini confirmed AudioKit Flow supports multi-output labeled ports — this removes the biggest concern from P1 research
- However: AudioKit Flow does NOT provide zoom/pan/minimap/edge routing/keyboard shortcuts — these would need to be built from scratch (~15-20h additional)
- The library is designed for audio signal chains — node config inspectors, execution state overlays, and condition-specific UI would all be custom
- 390 stars, last meaningful commit activity unclear — long-term maintenance risk

**Scope risk:**
- P2 as scoped could easily balloon to 30-40h if node config forms (7 types x inspector panel + validation) are included
- The canvas itself (React Flow integration) is ~15h. The ConditionEvaluator + switch + interpolation is ~5h. The risk is in the inspector panels and polish.

---

## Third-Party Evidence

**vite-plugin-singlefile:**
- npm: 100K+ weekly downloads, actively maintained (v2.1.0 as of early 2026)
- GitHub: 600+ stars, specifically designed for "offline web applications bundled into a single HTML file"
- Used by Capacitor/Cordova apps embedding web content in WKWebView — exact same pattern
- Produces a single `index.html` with all JS/CSS inlined via base64 data URIs and inline scripts

**React Flow Workflow Editor template:**
- Official template at reactflow.dev/ui/templates/workflow-editor demonstrates condition branching, multiple output handles, custom node types with forms
- Multiple source handles are supported natively — each handle gets a unique ID, used for edge source/target matching
- elkjs integration for auto-layout is documented with multi-handle support

**WKScriptMessageHandlerWithReply (iOS 14+):**
- Returns promises from Swift to JS — eliminates manual callback tracking
- Main-actor isolated — safe for SwiftUI coordination
- Documented by multiple authors with production examples

---

## Gemini Web-Grounded Validation

**Model:** Gemini 2.5 Pro (thinking + google_web_search)

### Confirmed Findings
- **Vite IIFE workaround confirmed.** Gemini provided a working `vite.config.js` using `build.lib` with `formats: ['iife']` and also recommended `vite-plugin-singlefile` as the preferred approach for WKWebView bundling
- **AudioKit Flow multi-output confirmed.** Gemini validated that AudioKit/Flow supports multi-output nodes with labeled ports via `Node(name:, inputs:, outputs:)` API. Each output is indexed and can be wired independently via `Wire(from: OutputID(nodeIndex, portIndex), to: InputID(...))`
- **React Flow custom nodes are React components** — confirmed straightforward for creating 7 node type renderers

### Contradicted Findings
- **None material.** The P1 research's assessment of React Flow as primary and AudioKit Flow as fallback holds up. Gemini's confirmation of AudioKit Flow's multi-port support elevates it from "probably not viable" to "credible alternative," but the effort gap (AudioKit would need zoom/pan/minimap built from scratch) still favors React Flow.

### New Evidence
- **`vite-plugin-singlefile`** is the recommended solution over manual IIFE configuration — it handles all asset inlining automatically and is specifically designed for offline/embedded web contexts
- AudioKit Flow's API is cleaner than expected: `Patch`, `Node`, `Wire`, `NodeEditor` — simple model-binding pattern similar to SwiftUI List/ForEach
- WKScriptMessageHandlerWithReply returns promises (iOS 14+), which is a cleaner bridge than the callback pattern used in MarkdownWebView

### Sources
- [vite-plugin-singlefile GitHub](https://github.com/richardtallent/vite-plugin-singlefile)
- [vite-plugin-singlefile npm](https://www.npmjs.com/package/vite-plugin-singlefile)
- [AudioKit Flow GitHub](https://github.com/AudioKit/Flow)
- [React Flow Workflow Editor Template](https://reactflow.dev/ui/templates/workflow-editor)
- [React Flow Custom Nodes](https://reactflow.dev/learn/customization/custom-nodes)
- [React Flow Multiple Handles Discussion](https://github.com/xyflow/xyflow/discussions/1808)
- [Vite + WKWebView type="module" Issue](https://github.com/vitejs/vite/discussions/14485)
- [WKScriptMessageHandlerWithReply Apple Forums](https://forums.developer.apple.com/forums/thread/751086)
- [WKWebView Bidirectional Communication](https://oleksandrbandyliuk.dev/posts/2024/03/how-to-establish-two-way-communication-bridge-between-native-ios-swift-app-and-javascript-using-wkwebview/)
- [WWDC 2025: WebKit for SwiftUI](https://developer.apple.com/videos/play/wwdc2025/231/)

---

## Deep-Dive: Architecture Decisions

### Decision 1: Canvas Technology — React Flow via vite-plugin-singlefile

**Recommended approach (refined from P1 discovery):**

```
HestiaApp/
  WorkflowCanvas/          # React + Vite project
    src/
      App.tsx               # React Flow canvas component
      nodes/                # Custom node type components (7 types)
        PromptNode.tsx
        ToolNode.tsx
        ConditionNode.tsx
        SwitchNode.tsx
        NotifyNode.tsx
        LogNode.tsx
        TriggerNode.tsx
      bridge.ts             # Swift-JS message protocol
      theme.ts              # Dark theme matching macOS DesignSystem
    vite.config.ts          # vite-plugin-singlefile config
    package.json
  macOS/
    Views/Workflow/
      WorkflowCanvasWebView.swift    # NSViewRepresentable WKWebView wrapper
      MacWorkflowCanvasPane.swift    # Canvas + inspector split view
```

**Vite configuration:**
```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'

export default defineConfig({
  plugins: [react(), viteSingleFile()],
  base: './',
  build: {
    outDir: '../macOS/Resources/WorkflowCanvas',
    assetsInlineLimit: 100000000,  // Inline everything
  }
})
```

**Swift-JS Bridge Protocol:**
```typescript
// bridge.ts — messages from Swift to JS
interface WorkflowData {
  nodes: Array<{ id: string; type: string; position: { x: number; y: number }; data: any }>;
  edges: Array<{ id: string; source: string; target: string; sourceHandle?: string; label?: string }>;
}

// Messages from JS to Swift via window.webkit.messageHandlers
type BridgeMessage =
  | { type: 'nodeAdded'; payload: { nodeType: string; position: { x: number; y: number } } }
  | { type: 'nodesMoved'; payload: Array<{ id: string; x: number; y: number }> }
  | { type: 'edgeCreated'; payload: { source: string; target: string; sourceHandle?: string; label?: string } }
  | { type: 'edgeDeleted'; payload: { edgeId: string } }
  | { type: 'nodeSelected'; payload: { nodeId: string } }
  | { type: 'nodeDeleted'; payload: { nodeId: string } }
  | { type: 'executionUpdate'; payload: { nodeId: string; status: string } }  // SSE → canvas
```

Key refinements from P1 discovery:
1. **vite-plugin-singlefile** instead of manual IIFE — handles all asset inlining automatically
2. **Batch position updates** — debounce node moves (300ms) and send as array, not individual PATCH calls
3. **WKScriptMessageHandlerWithReply** instead of one-way handler — enables request-response pattern (e.g., "get node config for inspector")

### Decision 2: Batch Position Update Endpoint

**New endpoint needed for canvas efficiency:**

```
PATCH /v1/workflows/{workflow_id}/layout
Body: { "positions": [{ "node_id": "...", "position_x": 100, "position_y": 200 }, ...] }
```

Without this, dragging 5 nodes generates 5 individual PATCH calls. The batch endpoint reduces this to 1 call with 300ms debounce from the canvas.

### Decision 3: Switch Node + N-ary Branching

**Extend NodeType enum:**
```python
class NodeType(str, Enum):
    # ... existing types ...
    SWITCH = "switch"  # N-ary condition branching
```

**Switch node config:**
```json
{
  "field": "response.category",
  "cases": [
    { "value": "urgent", "label": "case_urgent" },
    { "value": "normal", "label": "case_normal" }
  ],
  "default_label": "case_default"
}
```

**Executor changes:**
- `_mark_dead_paths` generalized from binary (true/false) to N-ary (case_X labels)
- Matched case label becomes the live path; all other case edges become dead paths
- Default label is the fallback when no case matches

### Decision 4: Variable Interpolation

**Simple mustache-style, pre-execution:**

```python
import re

INTERPOLATION_RE = re.compile(r'\{\{(\w+(?:\.\w+)*)\}\}')

def interpolate_config(config: dict, results: dict) -> dict:
    """Replace {{node_id.field}} references with actual values from prior nodes."""
    serialized = json.dumps(config)

    def replacer(match):
        path = match.group(1)
        value = _resolve_path(results, path)
        if value is None:
            return match.group(0)  # Leave unresolved
        return json.dumps(value) if not isinstance(value, str) else value

    interpolated = INTERPOLATION_RE.sub(replacer, serialized)
    return json.loads(interpolated)
```

Applied in `DAGExecutor._execute_node_task` before calling the node executor:
```python
# Before executor call:
interpolated_config = interpolate_config(node.config, results)
output = await executor_fn(interpolated_config, input_data)
```

This is:
- **Safe**: Only resolves from the results dict (populated by prior node outputs)
- **Simple**: No expression language, no eval, no JMESPath dependency
- **Sufficient**: Covers "use the response from node A as input to node B" which is 90% of workflows

### Decision 5: Execution Overlay via SSE

The SSE event bus already publishes `node_started`, `node_completed`, `node_failed` events. The canvas subscribes to the SSE stream and colors nodes in real time:

- **Pending**: gray border
- **Running**: amber pulsing border (CSS animation)
- **Success**: green border + checkmark badge
- **Failed**: red border + error badge
- **Skipped**: faded/dimmed

Implementation: Swift subscribes to `/v1/workflows/stream` SSE, forwards events to JS via `evaluateJavaScript("updateNodeStatus('node-id', 'success')")`.

---

## Philosophical Layer

### Ethical Check
Building a visual workflow editor for personal automation is productive and ethical. No PII leaves the device. The variable interpolation is sandboxed to node output data. No concerns.

### First Principles Challenge
**Why WebView + React Flow instead of pure SwiftUI?**
- SwiftUI Canvas can render nodes and edges, but building zoom/pan/snapping/edge routing/minimap/selection from scratch is 40-50h of work
- React Flow provides all of these out of the box with 25K+ stars of battle-testing
- The 15% native-feel gap is acceptable for a power-user automation tool (not a consumer app)
- WWDC 2025 announced native SwiftUI WebView (macOS 26) — when Hestia raises its deployment target, the WebView integration becomes even cleaner

**Why not AudioKit Flow (now that multi-port is confirmed)?**
- AudioKit Flow provides: node rendering, wire drawing, port connections
- AudioKit Flow does NOT provide: zoom/pan controls, minimap, edge path routing, keyboard shortcuts, selection rect, snapping, auto-layout integration
- Building those features adds ~15-20h on top of AudioKit Flow integration (~10h) = 25-30h total vs ~15h for React Flow
- AudioKit Flow becomes compelling ONLY if we value 100% native feel enough to pay the 15h premium

### Moonshot: Live Canvas Collaboration
**What if two devices (Mac + iPhone) could both view the same workflow canvas in real time, with execution state updating simultaneously?**

- Technical viability: MEDIUM. SSE already broadcasts execution events. The canvas state (node positions, edges) is persisted in SQLite. A second client just needs to subscribe to SSE + periodically poll for layout changes.
- Effort: 8-10h on top of P2 (SSE subscription on iOS, read-only canvas view)
- Risk: WKWebView on iOS has different performance characteristics. iPhone screen is too small for meaningful canvas editing.
- MVP: iPhone shows read-only execution visualization (node status lights) while Mac does editing
- **Verdict: SHELVE.** The value is marginal for a single-user system. What would change: if Hestia becomes multi-user or Andrew wants to monitor workflows from phone while away from Mac.

### Key Principles Score

| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 5 | Variable interpolation sandboxed to results dict. No eval/exec. WebView loads from app bundle only (no network). |
| Empathy | 5 | Visual node editor is the #1 UX improvement — transforms workflow creation from "type JSON config" to "drag and connect." |
| Simplicity | 3 | WebView + React adds complexity (two stacks). But React Flow eliminates far more complexity than it introduces. Net simplification vs building from scratch. |
| Joy | 5 | Dragging nodes, drawing edges, watching them light up green as they execute — this is the dream. |

---

## Recommendation

**Build P2 in two phases with clear deliverables:**

### P2A: Canvas Foundation (~12-15h)
1. **React Flow project scaffolding** — `WorkflowCanvas/` with Vite + vite-plugin-singlefile (2h)
2. **7 custom node type components** — styled to match macOS dark theme (3h)
3. **WorkflowCanvasWebView.swift** — NSViewRepresentable with bidirectional bridge (3h)
4. **Swift-JS bridge protocol** — node CRUD, edge CRUD, position sync with debounced batch updates (2h)
5. **Batch layout endpoint** — `PATCH /v1/workflows/{id}/layout` (1h)
6. **Canvas integration in MacWorkflowDetailPane** — toggle between list view and canvas view (1h)
7. **Execution overlay** — SSE → canvas node status coloring (2h)

### P2B: Conditions + Interpolation (~5-8h)
1. **Switch node type** — NodeType.SWITCH, N-ary branching evaluator, dead-path generalization (2h)
2. **Variable interpolation** — `{{node_id.field}}` pre-processing in DAGExecutor (2h)
3. **Multi-port rendering** — condition/switch nodes show labeled output handles in React Flow (1h)
4. **Tests** — switch topology, interpolation edge cases, bridge protocol (2-3h)

### Total: 17-23h

### Confidence: HIGH

The architecture is sound. The Vite + WKWebView bundling concern (the biggest P2 risk from P1 research) is definitively solved by `vite-plugin-singlefile`. The backend is already fully wired — P2 is primarily a frontend effort.

### What would change the recommendation:
- If `vite-plugin-singlefile` output exceeds 3MB, consider code splitting with manual asset management
- If WKWebView memory exceeds 150MB with 50+ nodes, investigate React Flow's virtualization options or switch to AudioKit Flow
- If macOS deployment target moves to 26.0+, evaluate native SwiftUI WebView as replacement for NSViewRepresentable wrapper
- If P2A takes >20h, cut execution overlay and inspector panels — canvas editing alone is valuable

---

## Final Critiques

### The Skeptic: "Why won't this work?"
**Challenge:** You're embedding a React application inside a WKWebView inside a SwiftUI app. That's three layers of abstraction. When something breaks in the bridge, debugging crosses JS → WebKit → Swift boundaries. What happens when React Flow has a breaking change?

**Response:** The bridge protocol is intentionally thin — 7 message types, each a simple JSON payload. The React Flow version is pinned in `package.json`. The MarkdownWebView already demonstrates this exact pattern works reliably in Hestia. The key difference is that MarkdownWebView does one-way injection (Swift→JS) while the canvas needs bidirectional communication — but WKScriptMessageHandler handles JS→Swift cleanly. The debugging concern is real but bounded: the bridge is the only cross-language seam, and both sides can log independently.

### The Pragmatist: "Is the effort worth it?"
**Challenge:** 17-23h is 1.5-2 weeks of Andrew's time. The list UI from P1 already works — you can create workflows, add nodes, trigger runs. Is a visual canvas really necessary?

**Response:** The list UI works for viewing workflows but not for building them. Creating a 5-node workflow currently requires: 5 POST calls for nodes, 4 POST calls for edges, manual position coordinates for layout. A canvas reduces this to: drag 5 nodes, draw 4 connections. The difference between "technically possible" and "actually usable" is the canvas. P2A (canvas only, 12-15h) delivers the core value. P2B (conditions + interpolation) can be deferred if time is tight.

### The Long-Term Thinker: "What happens in 6 months?"
**Challenge:** React Flow is a JS dependency that will need updates. The npm ecosystem moves fast. In 6 months, will this be a maintenance burden?

**Response:** React Flow is pinned to a specific version. The canvas is a self-contained module (`WorkflowCanvas/`) with zero interaction with the rest of the codebase except through the bridge protocol. If React Flow releases a breaking change, we simply don't update until ready. The `vite-plugin-singlefile` output is a static HTML file — once built, it's inert. The long-term risk is actually lower than a custom SwiftUI canvas, which would need ongoing maintenance of zoom/pan/edge routing code. When macOS 26 deployment target becomes feasible, the native SwiftUI WebView provides a cleaner integration point without changing the React Flow canvas itself.

---

## Open Questions

1. **Build pipeline integration:** Should `npm run build` in `WorkflowCanvas/` be part of the xcodegen build phase, or a manual pre-build step? Recommend: manual (run once, output committed to repo as `macOS/Resources/WorkflowCanvas/index.html`). Avoids adding Node.js as a CI/CD dependency.
2. **Inspector panel location:** Should node config editing happen inside the WebView (React form) or in native SwiftUI (sidebar inspector)? Recommend: Native SwiftUI sidebar — keeps complex form validation in Swift, reduces bridge traffic, feels more macOS-native. The canvas handles layout; Swift handles configuration.
3. **Canvas state persistence:** Should the canvas's viewport (zoom level, pan position) persist between sessions? Nice-to-have — store in UserDefaults keyed by workflow_id. Low priority.
4. **Dark theme precision:** How closely should the canvas match the macOS DesignSystem tokens (MacColors, MacTypography)? Recommend: 80% match using CSS custom properties derived from the Swift tokens. Perfect match is diminishing returns.
5. **Execution overlay reconnection:** If the SSE stream disconnects during a long-running workflow, the canvas may show stale node states. Solution: on reconnect, fetch the latest run status via REST and reconcile.
