# Discovery Report: Workflow Step Builder UX

**Date:** 2026-03-24
**Confidence:** High
**Decision:** Build a hybrid step creation UX combining an "Add Node" sidebar palette with contextual "+" buttons on edges, plus custom React Flow node types with typed handles, all configured via the existing native SwiftUI inspector sidebar.

## Hypothesis

The current Hestia workflow editor has a complete backend DAG engine (8 node types, interpolation, switch branching) and a React Flow canvas that renders existing workflows, but provides no way to add, configure, or link new steps. The question: what is the right UX to close this gap and make workflow authoring feel as natural as n8n or Zapier, given our architecture constraints (React Flow in WKWebView, native Swift inspector sidebar, single-user personal assistant)?

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Backend is complete (8 node types, interpolation, condition evaluator, switch branching). React Flow canvas already renders, moves, deletes, and connects nodes. Swift-JS bridge is bidirectional with 7 message types. Node inspector sidebar exists with per-type config editors for all 8 types. API has full CRUD for nodes/edges/layout. SSE real-time execution coloring works. | **Weaknesses:** No way to add nodes from the canvas (must be API-only today). Canvas uses `type: "default"` for all nodes (no custom React Flow node components). No node palette/sidebar in the canvas. Bridge doesn't support "add node" messages yet. No visual distinction between node types on canvas. No empty-canvas onboarding. |
| **External** | **Opportunities:** n8n's "+" on edges and drag-from-sidebar are proven patterns with wide user acceptance. React Flow v12 has first-class custom node support, Placeholder Node component, and workflow builder template. The single-user context means we can optimize for power-user speed (keyboard shortcuts, drag-from-port) without onboarding friction. | **Threats:** Over-engineering the UX for a single user. WKWebView adds latency to every bridge message (~5-15ms per round trip). Custom React Flow nodes increase the JS bundle size inside the single-file HTML. Complexity creep if we try to match n8n feature parity. |

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | Custom node types with typed handles (visual identity per node type). "Add Node" panel triggered from canvas (+ button or edge drop). Bridge message for `addNode` action. Pre-populated trigger node on new workflow. | Node type icons inside React Flow nodes. Keyboard shortcut for add-node search. |
| **Low Priority** | Drag-from-sidebar palette (can come later). Auto-layout with ELKjs. Data flow preview on hover. | Template library. AI-generated workflow from prompt. Connection type validation (isValidConnection). |

## Argue (Best Case)

**This is a high-leverage, medium-effort feature that transforms a demo into a usable tool.**

Evidence:
1. **Backend is 100% ready.** `POST /{workflow_id}/nodes` already accepts `node_type`, `label`, `config`, `position_x`, `position_y`. The inspector sidebar already edits all 8 node types. The only gap is *getting nodes onto the canvas in the first place*.

2. **React Flow provides the building blocks.** The v12 Workflow Builder example demonstrates exactly the pattern we need: placeholder nodes, "+" on edges, and add-on-edge-drop. Custom nodes are a documented first-class feature.

3. **n8n's UX is proven at scale.** Their three methods (sidebar palette, "+" on edges, drag-from-port) cover discovery, guided flow, and power-user speed. We can implement the two highest-value patterns (edge "+" and canvas add panel) in a fraction of the effort.

4. **The Swift inspector sidebar is already built.** `MacNodeInspectorView` handles all 8 node types with proper config editing and save. We don't need to build configuration UI -- just the creation entry point.

5. **Single-user advantage.** We can skip onboarding tours, permission systems, collaboration features, and template libraries. Ship the core interaction loop and iterate.

## Refute (Devil's Advocate)

**Risk of building UI that Andrew uses twice then abandons in favor of CLI/chat commands.**

Counter-evidence:
1. **Visual workflows are fundamentally different from chat.** The DAG structure, parallel fan-out, and condition branching are genuinely hard to author via text. This isn't a vanity feature.

2. **WKWebView bridge latency could make the UX feel sluggish.** Every "add node" → API call → reload detail → re-inject into canvas is a full round trip. If it takes >500ms, it will feel broken.
   - Mitigation: Optimistic UI in React Flow (add node immediately, reconcile with server response).

3. **Custom nodes increase JS bundle size.** Each typed node component adds to the single-file HTML.
   - Mitigation: The nodes are small (50-80 lines each). Total addition is ~400 lines of TSX. Vite tree-shaking handles dead code.

4. **Scope creep risk.** "Just add nodes" can balloon into drag-from-sidebar, auto-layout, data flow preview, connection validation, undo/redo, etc.
   - Mitigation: Strict MVP scope. Phase 1: add node via canvas "+" → inspector opens. Phase 2 (later): drag-from-sidebar, auto-layout.

## Third-Party Evidence

### n8n's Node Addition UX (Production Reference)
- Three methods: (1) Click "+" icon on canvas or node edge, (2) Press N key, (3) Drag from output handle into empty space
- First node is always a Trigger, reducing empty canvas confusion
- After trigger, panel shows categorized node types: Actions, Data, Flow, AI
- Search-first: typing immediately filters the node list
- Source: [n8n Docs: Navigating the editor UI](https://docs.n8n.io/courses/level-one/chapter-1/)

### React Flow Workflow Builder Template
- Uses placeholder nodes that convert to real nodes on click
- "+" buttons on edges insert nodes between existing connections
- ELKjs for auto-layout (optional, not required for basic functionality)
- Source: [React Flow: Workflow Builder](https://reactflow.dev/examples/layout/workflow-builder)

### Retool Workflows
- Left sidebar palette with drag-and-drop
- Right sidebar inspector for configuration
- Modal for complex setups (authentication, data mapping)
- Source: [Retool Workflows documentation](https://docs.retool.com/workflows/)

### Key Anti-Pattern: Empty Canvas
Every successful tool pre-populates with a trigger node. Blank canvas → user confusion → abandonment. This is consistent across n8n, Zapier, Make, and Retool.

## Gemini Web-Grounded Validation

**Model:** Gemini 2.5 Pro (thinking + google_web_search)

### Confirmed Findings
- **Hybrid add-node pattern is industry standard.** n8n, Zapier, Make, Retool all use sidebar palette + edge "+" buttons. No production tool relies on a single method.
- **Sidebar inspector is the dominant configuration pattern.** Preserves workflow context while configuring. Used by Zapier, n8n, Retool.
- **Pre-populated trigger node solves empty canvas.** Universal pattern across all surveyed tools.
- **React Flow v12 custom nodes with typed handles** are the standard approach. Handle `id` attributes (`"true"`, `"false"`) map directly to edge routing in the DAG executor.

### Contradicted Findings
- **Drag-from-sidebar is NOT strictly necessary for MVP.** Gemini's research confirms that the "add on edge drop" pattern alone (drag from port into empty space, or "+" on edge) is sufficient for power users. The sidebar palette is primarily for discoverability with new users -- less critical for a single-user tool.

### New Evidence
- **Progressive disclosure for node config** is critical. Show only required fields (prompt text for run_prompt, tool name for call_tool). Advanced options (model, memory_write, force_local) in accordion/tab. Our existing `MacNodeInspectorView` already follows this pattern partially.
- **`isValidConnection` on handles** prevents invalid connections at the UI level. This is a production best practice but can be deferred to Phase 2.
- **Windmill uses command palette (Cmd+K)** as the primary add-node method for developer-centric workflows -- relevant for Andrew's power-user profile.

### Sources
- [React Flow: Custom Nodes](https://reactflow.dev/learn/customization/custom-nodes)
- [React Flow: Workflow Builder Example](https://reactflow.dev/examples/layout/workflow-builder)
- [n8n: Node UI Design](https://docs.n8n.io/integrations/creating-nodes/plan/node-ui-design/)
- [n8n: Navigating the Editor UI](https://docs.n8n.io/courses/level-one/chapter-1/)

## Philosophical Layer

### Ethical Check
Straightforward tool-building. No ethical concerns. The workflow editor helps a single user automate personal tasks.

### First Principles
The fundamental question is: "What is the minimum interaction to go from intent to executable DAG step?" The answer is:
1. User indicates WHERE (click "+" on an edge, or on the canvas)
2. User indicates WHAT (select node type from a compact menu)
3. User indicates HOW (configure in the inspector sidebar)

Every additional interaction beyond these three is friction. The design should minimize steps 1-2 to a single gesture where possible.

### Moonshot: Chat-to-Workflow
**What if Andrew could say "build me a workflow that checks my email every morning, summarizes unread messages, and sends me a notification"?**
- **Technical viability:** High. The backend already has all the primitives (run_prompt, call_tool, notify, schedule trigger). An LLM could generate the DAG JSON.
- **Effort estimate:** 8-12h for a basic version (prompt → JSON → create workflow via API)
- **Risk:** Generated workflows may be subtly wrong (wrong tool names, bad conditions). Needs human review.
- **MVP scope:** Accept a natural language description, generate the workflow, open it in the canvas for review/edit.
- **Verdict:** SHELVE for now. Build the manual editor first; the chat-to-workflow can layer on top once the manual path is solid. What would change the answer: if Andrew finds himself building the same workflow patterns repeatedly.

### Key Principles Score

| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 5 | No new attack surface. All node creation goes through existing authenticated API. |
| Empathy | 4 | Transforms a display-only canvas into a usable authoring tool. Minus one because the learning curve of a DAG editor is inherently steeper than chat. |
| Simplicity | 4 | Three-step interaction (where, what, how). Custom nodes add complexity to the React layer but simplify the user's mental model. |
| Joy | 5 | Dragging connections between nodes and watching workflows execute in real-time is genuinely satisfying. |

## Recommendation

**Build the Step Builder UX in two focused phases:**

### Phase 1: Core Step Creation (10-14h)
The minimum to make the canvas usable for authoring.

**React Flow (TypeScript) changes:**
1. **5 custom node components** — `PromptNode`, `ToolNode`, `ConditionNode` (if_else + switch with true/false/case handles), `ActionNode` (notify + log), `TriggerNode` (schedule + manual). Each shows: icon, label, node type badge, typed source/target handles.
2. **"Add Node" interaction** — Two entry points:
   - **"+" button on edges** — Clicking inserts a node type selector (compact dropdown/popover), creates the node via bridge → Swift → API, and re-renders.
   - **Canvas context menu (right-click)** — Shows node type options at click position.
3. **Register `nodeTypes` map** in App.tsx instead of using `type: "default"` for everything.

**Bridge (TypeScript + Swift) changes:**
4. **New bridge message: `addNode`** — Payload: `{ nodeType, label, positionX, positionY, afterNodeId? }`. Swift coordinator receives this, calls `POST /{workflow_id}/nodes`, optionally creates edge, then re-injects the full workflow.
5. **Optimistic rendering** — React Flow adds a temporary node immediately; reconciles with server response.

**Swift changes:**
6. **Auto-open inspector on node creation** — When `addNode` response arrives, set `selectedNodeId` to the new node ID, which triggers `MacNodeInspectorView` to slide in.
7. **Pre-populate trigger node** — When creating a new workflow, auto-create a Manual trigger node at position (100, 200) so the canvas is never empty.

### Phase 2: Polish & Power User (6-8h, later)
- Drag-from-sidebar node palette
- Cmd+K canvas search to add nodes
- Auto-layout with ELKjs
- `isValidConnection` handle validation
- Node type color coding on the minimap

**Confidence: High.** The backend is complete, the inspector is built, and the bridge protocol is proven. This is purely a frontend interaction gap with well-established industry patterns.

**What would change the recommendation:** If WKWebView bridge latency proves >200ms per add-node round trip, we'd need to move more logic into the React layer (optimistic creates with client-side IDs, batch sync). If Andrew prefers CLI-based workflow authoring, the entire canvas effort should be deprioritized.

## Final Critiques

### The Skeptic: "Why won't this work?"
**Challenge:** WKWebView is a bottleneck. Every node add requires: bridge message → Swift → HTTP API → response → bridge inject. That's 3-4 async hops. If any hop fails silently, the canvas and backend drift out of sync.
**Response:** The existing move/delete/edge operations already traverse this exact path and work reliably. The bridge has error handling. Optimistic rendering in React Flow means the user sees instant feedback regardless of backend latency. The reconciliation pattern (reload full workflow after mutation) prevents drift.

### The Pragmatist: "Is the effort worth it?"
**Challenge:** 10-14h for Phase 1 is significant. Andrew could just use the API directly or the CLI to create workflows.
**Response:** The visual editor is the entire point of the Workflow Orchestrator feature. Without step creation, the canvas is read-only -- a visualization tool, not an authoring tool. The backend investment (8 node types, interpolation, switch, executor, SSE) was 40+ hours. Spending 10-14h to make it usable is a 25% premium for 100% of the usability.

### The Long-Term Thinker: "What happens in 6 months?"
**Challenge:** Will this become a maintenance burden? React Flow upgrades, custom node complexity, bridge protocol versioning.
**Response:** React Flow v12 is stable (major version, unlikely to break). Custom nodes are plain React components with no exotic dependencies. The bridge protocol is versioned by message type strings. The maintenance risk is low. The bigger long-term risk is NOT building this -- leaving a half-finished feature that discourages use of the entire workflow system.

## Open Questions

1. **Node positioning algorithm** -- When adding a node via edge "+", where exactly should it be placed? Midpoint of the edge? Below the source node? This needs a simple heuristic (e.g., target position + 200px offset in the flow direction).
2. **Edge insertion semantics** -- When adding a node on an edge, should the old edge be deleted and two new edges created (source→new, new→target)? Or should this be a single atomic "insert node" API call? The current API requires separate calls.
3. **Trigger node auto-creation** -- Should `POST /workflows` auto-create a trigger node, or should the client handle this? Client-side is simpler and more flexible.
4. **Switch node handle count** -- Switch nodes have N output handles (one per case). How should the custom node component handle dynamic handle creation? React Flow supports this but the UX for adding/removing cases needs design.
