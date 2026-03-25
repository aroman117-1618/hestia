# Second Opinion: Notion-Level UI Redesign for Hestia

**Date:** 2026-03-24
**Models:** Claude Opus 4.6 (internal) + Gemini 2.5 Pro (external)
**Verdict:** APPROVE WITH CONDITIONS
**Focus:** Product design & engineering best practices (committed work — not a decision gate)

## Plan Summary

4-phase redesign to bring Hestia's macOS app to Notion-level quality: (1) extract shared component library from duplicated views, (2) build Investigation Board as a 2D React Flow canvas for entity curation, (3) refine 3D Knowledge Atlas as read-only published view, (4) add cross-linking infrastructure between Research entities and other features. Total estimate: 80-100h across ~8-10 weeks.

Discovery report: `docs/discoveries/notion-level-ui-redesign-2026-03-24.md`

---

## Phase 1: Consume the Plan

**Plan consumed:** Discovery report, SPRINT.md, CLAUDE.md, ui-wiring-audit-methodology doc.

**Technical assumptions validated by @hestia-explorer:**

| Assumption | Finding |
|-----------|---------|
| Bridge has 6-8 message types | **7 confirmed** (sendNodesMoved, sendEdgeCreated, sendNodeSelected, sendNodeDeleted, sendEdgeDeleted, sendAddStep, signalReady) |
| Detail panes follow consistent pattern | **Confirmed** — Header + Divider + ScrollView + Footer across all 4 implementations |
| SceneKit is the primary 3D renderer | **Confirmed** — Full 3D camera control, per-nodeType geometry (6 shapes), selection ring animation |
| React Flow v12 used | **Confirmed** — @xyflow/react ^12.6.0 |
| WebViews persist on tab switch | **Confirmed** — NSViewRepresentable creates once, updates via JS injection, no destroy/recreate |
| Reusable component library exists | **Confirmed** — 8-file DesignSystem + 5 compound component patterns (cards, chips, grids, rows, buttons) |

---

## Phase 2: Scale Assumptions Check

| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|----------------|-------------------|
| Single user (Andrew) | Yes | None — designed for this | N/A |
| Family (2-5 users) | Partial | Investigation boards are device-local (SQLite). No board sync. entity_references assumes single user context. HestiaDeepLink enum is device-bound. | Medium — would need board sync protocol + multi-tenant scoping on reference index |
| Community (small group) | No | React Flow canvas state is single-session. No collaborative editing. 3D Atlas is read-only but assumes one user's knowledge graph. | High — collaborative canvas requires CRDT or OT, fundamental architecture change |

**Assessment:** The plan correctly targets single-user. Nothing here actively blocks future scale. The `entity_references` table should include a `user_id` column from day one (costs nothing, prevents painful migration later).

---

## Phase 3: Front-Line Engineering Review

**Feasibility:** Yes — all four phases are implementable as described. The React Flow bridge pattern is proven, component extraction is straightforward refactoring, SceneKit refinements are incremental.

**Complexity — what's underestimated:**
- **Phase 1 acceptance criteria are undefined.** "Extract HestiaDetailPane" doesn't specify which variants it handles. Wiki has back-navigation, Workflow has canvas/list toggle, Research has graph/principles/memory mode. The generic component's configuration surface could balloon. **Recommendation:** Define "done" for each component as a concrete list of call-sites that adopt it.
- **Phase 2 build pipeline.** Two Vite projects require two `npm run build` steps before Xcode. Current CI/CD (`deploy-to-mini.sh`) doesn't handle this. Missing from the plan.
- **Phase 4 cross-link indexing touches the chat pipeline.** Chat is the busiest, most stability-critical code path. Adding entity mention indexing on the write path risks latency spikes.

**Hidden prerequisites:**
1. `project.yml` must be updated to include `InvestigationCanvas/` as a folder resource in the macOS target
2. `deploy-to-mini.sh` must build both React canvases
3. New SQLite tables needed: `investigation_boards` (Phase 2), `entity_references` (Phase 4)
4. New backend API endpoints: board CRUD, reference index queries, principle distillation trigger

**Testing strategy gaps:**
- No automated visual regression tests for SwiftUI views — Phase 1 refactoring can create invisible layout breakage
- WKWebView bridge protocol has no typed contract enforcement — bridge.ts and Swift coordinator can silently diverge
- The "Distill Principle" flow requires LLM inference in the loop — hard to test deterministically

---

## Phase 4: Backend Engineering Lead Review

**Architecture fit:** Strong. Component library follows existing DesignSystem patterns. Investigation Board reuses proven WKWebView bridge. Cross-linking uses standard SQLite + API pattern.

**API design considerations:**
- Investigation Board needs CRUD endpoints: `POST/GET/PUT/DELETE /v1/research/boards`
- Board state (node positions, groups) serialized as JSON blob? Or normalized tables? JSON blob is simpler for V1.
- Principle distillation: `POST /v1/research/principles/distill-from-selection` — new endpoint that takes entity IDs, returns proposed principle
- Reference index: `GET /v1/research/entities/{id}/references` — paginated cross-module references

**Data model:**
- `investigation_boards` table: id, name, layout_json, created_at, updated_at
- `board_items` table: board_id, entity_type, entity_id, position_x, position_y, group_id
- `entity_references` table: entity_id, module, item_id, context, created_at — **add user_id column from day one**

**Integration risk:**
- @hestia-critic correctly identified: the name "Investigation" collides with the existing `InvestigationModels.swift` (URL content analysis). Rename the new concept to avoid confusion — options: "Research Board", "Evidence Board", "Canvas Board".

---

## Phase 5: Product Management Review

**User value:** High. The Investigation Board is a genuine new capability — no other personal AI assistant offers a visual entity curation surface with LLM-powered principle distillation. The "lasso → distill → approve → propagate" flow is a differentiator.

**Edge cases:**
- Empty board state: What does a new user see? Suggestion: pre-populated starter board with a few sample entities from their existing knowledge graph
- First-time entity resolution: If the knowledge graph is sparse, the Investigation Board has nothing to show. Gate on minimum entity count?
- Offline: React Flow canvas works offline (local state). Principle distillation requires inference — show clear "requires connection" messaging.

**Multi-device:** Investigation Boards are macOS-only (React Flow in WKWebView). iOS has no equivalent. This is acceptable for V1 — flag as future consideration.

**Scope assessment:** Right-sized for the value delivered. The phased approach allows natural pause points (Phase 1 alone is valuable). 80-100h over 8-10 weeks is achievable at 12h/week with Claude Code acceleration.

**Opportunity cost:** This delays Trading Module S27.5 WS2-3, S28, and Memory Synthesis Engine. Trading is in a natural waiting period (need 30+ fills before S28), so the timing is good.

---

## Phase 6: Design/UX Review

**Design system compliance:** The plan explicitly builds on MacColors, MacTypography, MacSpacing, HestiaButtonStyle. Phase 1 enforces compliance by extracting shared components. Strong.

**Interaction model — the "Distill Principle" flow:**
- Lasso-select → context menu → principle proposal → edit → approve/reject is well-designed
- The "Refine" action (ask Hestia to re-propose with guidance) is a smart addition — prevents binary approve/reject frustration
- **Best practice from Miro:** After lasso-select, show a floating toolbar (not just right-click context menu) — more discoverable for new users
- **Best practice from Obsidian Canvas:** Support dragging items from the sidebar directly onto the canvas — don't require all items to be pre-populated

**Platform divergences:** iOS gets none of this in V1. Acceptable — macOS is the primary platform for power-user features.

**Accessibility gaps:** Plan doesn't mention keyboard navigation for the React Flow canvas, VoiceOver labels for canvas nodes, or Dynamic Type for the sidebar. Low priority for V1 but worth noting.

**Empty states:** Not specified for Investigation Board (new board), Knowledge Atlas (no approved principles), or sidebar sections (no memories/entities/investigations). Each needs a distinct empty state with an action CTA.

### 6.1 Wiring Verification

**Existing wiring issues relevant to this plan:**
- The ui-wiring-audit-methodology doc (2026-03-19) established that "calls an API" ≠ "fully wired." Phase 1 component extraction must verify that extracted components maintain actual data binding, not just API calls.
- NodeDetailPopover has hardcoded amber background (`Color(red: 17/255, green: 11/255, blue: 3/255)`) — this should use `MacColors.panelBackground` after Phase 1.
- Investigation Board will need thorough wiring audit after Phase 2 — add to Phase 4 review checklist.

---

## Phase 7: Infrastructure/SRE Review

**Deployment impact:**
- Phase 1: No backend changes. Xcode rebuild only. Low risk.
- Phase 2: New Vite project requires `npm install && npm run build` in CI/CD. New SQLite tables (auto-migrated). Server restart for new API endpoints.
- Phase 3: No backend changes. Xcode rebuild only.
- Phase 4: New SQLite table (auto-migrated). Indexing pipeline — batch process, not real-time. Server restart.

**New dependencies:**
- Phase 2: Second `package.json` with React, React-DOM, @xyflow/react. Same versions as WorkflowCanvas — pin to identical versions to avoid divergence.
- No new Python or Swift packages.

**Monitoring:** Add Instruments profiling checkpoints:
- WKWebView memory per canvas (target: <400MB each)
- SceneKit frame rate when Knowledge Atlas is active (target: >30fps)
- Bridge message latency (target: <50ms round-trip)

**Rollback strategy:**
- Phase 1: Git revert to pre-extraction commits. Clean separation.
- Phase 2: Research tab mode toggle — disable `.investigation` mode to fall back to current behavior.
- Phase 3: Cosmetic changes only — revert is trivial.
- Phase 4: Reference index is additive — delete table to roll back. Deep link enum is additive.

**Resource impact:** The critical constraint is M1 16GB.
- @hestia-critic's key finding: SwiftUI does NOT guarantee WebView deallocation when a `Group` branch is hidden. Both WebViews may be alive simultaneously.
- **Mitigation:** Lazy-load is necessary but insufficient. Add explicit WebView cleanup: on tab switch away from Workflow/Investigation, call `webView.loadHTMLString("", baseURL: nil)` to release the web process's page memory while keeping the WKWebView shell alive. This is the pattern used by Safari's tab suspension.

---

## Phase 8: Executive Panel

### CISO Review
**Verdict: Acceptable**
- No new attack surface. WebViews load local bundled HTML only (no remote URLs).
- React Flow canvas handles user data (entity names, fact content) entirely in-process.
- `entity_references` table contains entity IDs and module names — no PII, no credentials.
- Bridge protocol is local (WKWebView message handlers) — no network exposure.

### CTO Review
**Verdict: Approve with Conditions**
- Architecture is sound. Reusing the proven bridge pattern is the right call.
- **Condition 1:** Performance prototype MUST be the first deliverable of Phase 2. Build a 300-node React Flow canvas in WKWebView, profile with Instruments on the Mac Mini, and establish a go/no-go memory threshold (<800MB for the web process). Do not build 25-35h of canvas infrastructure on an unvalidated assumption.
- **Condition 2:** Rename "Investigation Board" to avoid collision with existing `InvestigationModels.swift`. Suggested: "Research Canvas" or "Evidence Board."
- **Condition 3:** Pin React Flow, React, and Vite versions identically across both canvas projects. Use a shared `package.json` workspace or document the version-lock requirement.
- SceneKit investment is appropriately bounded. If Apple deprecates it before the M5 upgrade, the 2D canvas is the primary interface.

### CPO Review
**Verdict: Acceptable**
- User value is real. The Investigation Board fills a genuine capability gap.
- The "lasso → distill → approve → propagate" flow is the kind of feature that makes a product feel intelligent, not just functional.
- Timing is good — trading module is in a natural fill-accumulation waiting period.
- Phase 1 component library improves every future UI sprint. Strong foundation investment.
- The dual 2D/3D model (working surface + published view) is a compelling product narrative.

---

## Phase 8.4: CFO Review

**Verdict: Acceptable**

- **Build cost:** 80-100h at ~12h/week = 7-9 weeks. With Claude Code acceleration, likely closer to 6-7 weeks wall-clock.
- **Maintenance cost:** Low — component library reduces maintenance. Two React canvases add npm audit surface but are bounded.
- **ROI:** Phase 1 pays back immediately in reduced code duplication. Phase 2 creates a unique capability. Phase 4 cross-linking increases the value of every entity in the system.
- **Opportunity cost:** Delays trading S28 (regime detection) and Memory Synthesis Engine. Both are in natural waiting states — trading needs 30+ fills, MSE is between-sprint work.

---

## Phase 8.5: Legal Review

**Verdict: Acceptable**
- No new third-party APIs or external data sharing.
- React Flow is MIT-licensed. No GPL contamination risk.
- Entity data stays local (SQLite + WKWebView). No GDPR/CCPA implications.
- No regulatory concern — this is a UI/UX improvement to an existing personal tool.

---

## Phase 8.6: Key Principles Score

| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 5 | No new attack surface. All data stays local. WebViews sandboxed. |
| Empathy | 5 | Directly serves Andrew's knowledge curation needs. The teaching metaphor (board→atlas) respects how humans build understanding. |
| Simplicity | 3 | Dual canvas + component library + cross-linking is inherently complex. Mitigated by phased delivery and reuse of proven patterns. Simplicity score reflects the necessary complexity, not over-engineering. |
| Joy | 5 | Investigation Board + 3D Atlas + principle distillation = the kind of tool you want to show people. |

---

## Phase 9: Sustained Devil's Advocate

*Incorporating findings from @hestia-critic's independent adversarial review.*

### 9.1 The Counter-Plan

@hestia-critic's strongest recommendation: **Reorder Phase 4a (reference index skeleton) before Phase 2.**

The argument is compelling: the Investigation Board's value comes from showing how entities connect across Hestia. Without cross-linking data, the board is an isolated canvas. By building the `entity_references` table skeleton first (~8h, read-only, research entities only), Phase 2 can show real cross-link data from day one instead of retrofitting it in Phase 4.

**Proposed reorder:**
1. Phase 1: Component Library (unchanged)
2. Phase 4a: Reference Index skeleton (table + research entity indexing + read API, ~8h)
3. Phase 2: Investigation Board (now built with live cross-link data)
4. Phase 4b: Cross-Link UI + Chat Indexing (~12-22h)
5. Phase 3: 3D Atlas Refinement (unchanged)

**What this sacrifices:** Clean linear phase numbering in documentation. Requires splitting Phase 4 into two parts.

**Assessment:** The reorder is worth it. The cost (documentation complexity) is trivial. The benefit (Investigation Board ships with meaningful cross-links from day one) is significant.

### 9.2 Future Regret Analysis

**3 months:** Phase 1 refactoring creates invisible layout regressions in rarely-visited views (Health archived, Explorer, Memory Browser). No automated visual regression tests exist. Manual testing burden falls on Andrew.

**6 months:** Two independent React canvas projects have diverged in React version, theme constants, or bridge protocol conventions. An npm security advisory hits one but not the other. The "shared theme" that was documented as "duplicate the 32 LOC file" has already drifted.

**12 months:** The cross-link indexer, added to the chat pipeline as a batch process, has accumulated enough entity mentions that the batch job takes >30 seconds. Frequency tuning becomes necessary. If real-time was chosen instead of batch, latency complaints would have appeared much sooner.

### 9.3 The Uncomfortable Questions

- **"Do we actually need a second React Flow canvas?"** Yes. The Investigation Board serves a fundamentally different cognitive purpose than the Workflow canvas. Extending the Workflow canvas to handle both would create a God Component with two unrelated feature sets. Separate canvases are the correct architectural boundary.

- **"Are we building this because it's valuable, or because it's interesting?"** Both — and that's fine. The component library (Phase 1) is pure engineering hygiene. The Investigation Board (Phase 2) is genuinely interesting AND valuable. The "lasso → distill" flow is a differentiator. The Knowledge Atlas (Phase 3) is the "interesting" risk — but it's bounded to 10-15h.

- **"What's the cost of doing nothing?"** Every future UI sprint continues hand-rolling panel/sidebar/detail patterns. The Research tab remains a passive 3D visualization with no curation capability. Hestia's knowledge graph grows but Andrew has no way to actively curate it. The gap between "Hestia observed this" and "Hestia understands this" stays unbridged.

### 9.4 Final Stress Tests

**1. Most likely failure:** Phase 1 component extraction takes 20-25h instead of 12-16h because each call-site has subtle differences that resist generalization. **Mitigation:** Define acceptance criteria per component before starting. Extract only the 80% common pattern; let call-sites handle their 20% via content slots/closures.

**2. Critical assumption:** WKWebView memory management allows two React canvases + SceneKit to coexist on M1 16GB. **Validation:** Performance prototype with 300 nodes must be the FIRST deliverable of Phase 2. Go/no-go threshold: web process memory <800MB, frame rate >30fps.

**3. Half-time cut list:** If we had 40-50h instead of 80-100h:
- **Keep:** Phase 1 (component library) — highest leverage, benefits everything
- **Keep:** Phase 2 (Investigation Board) — the headline feature
- **Cut:** Phase 3 (3D Atlas refinement) — already functional, incremental improvement
- **Reduce:** Phase 4 → Phase 4a only (reference index skeleton, no chat indexing, no full cross-link UI)

---

## Cross-Model Validation (Gemini 2.5 Pro)

### Gemini's Independent Assessment

**Verdict: NEEDS REFINEMENT** (focused on engineering approach, not whether to do it)

**Strengths identified:** Pragmatic tech reuse (proven bridge pattern), well-decomposed phased rollout, excellent product vision (Investigation Board vs Knowledge Atlas distinction), mature SceneKit investment bounding.

**Weaknesses identified:** High complexity from two independent Vite projects, Phase 1 component library is "premature abstraction" for a solo developer, underestimated bridge maintenance burden.

**Three key recommendations:**
1. Unify both canvases into a single React/Vite project with client-side routing (`/workflow` and `/investigation`)
2. Reverse Phase 1 and Phase 2 — build the feature first, extract shared components from actual duplication afterward
3. Redesign "Distill Principle" as an in-situ on-canvas flow (floating action bar + inline principle node) rather than context menu + overlay card

### Where Both Models Agree

- **Performance prototype is mandatory.** Both agree: 300-node React Flow in WKWebView must be profiled on M1 before committing to the full build.
- **Bridge needs typed contracts.** Both recommend typed message enums (Swift `Codable` + TypeScript discriminated union) for compile-time safety.
- **Aggressive memory management required.** Both flag that SwiftUI's `Group` hiding does not guarantee WebView deallocation. Active teardown or page-emptying is needed.
- **"Distill Principle" should feel fluid.** Both models recommend moving away from a traditional right-click context menu toward floating contextual UI after lasso selection.
- **Batch indexing for cross-links.** Both agree entity mention indexing should never be on the chat write path.

### Where Models Diverge

| Topic | Claude's View | Gemini's View | Resolution |
|-------|--------------|---------------|------------|
| **Two Vite projects vs one** | Separate projects: clean separation of concerns, independent deployment, no coupling | Single project with client-side routing: halves maintenance, shared node modules, one build step | **Gemini is right for V1.** Two separate Vite projects doubles npm audit surface, build steps, and version management for a solo developer. Client-side routing with shared theme/bridge is the pragmatic choice. The canvases share React Flow, theme constants, and bridge infrastructure — separating them creates artificial boundaries. |
| **Phase 1 before Phase 2** | Component library first: de-risks everything, shared primitives from day one | Feature first, refactor from duplication: don't abstract before you know the real patterns | **Split decision.** Gemini is right that full component library extraction before building the feature risks abstracting the wrong patterns. But the @hestia-critic correctly identified that Phase 4a (reference index) should come before Phase 2. **Revised order:** Phase 1-lite (panel modifier only, the most obvious extraction, ~4h) → Phase 4a (reference index skeleton, ~8h) → Phase 2 (Investigation Board) → Phase 1-full (extract remaining components from confirmed duplication) → Phase 4b → Phase 3. |
| **"Distill Principle" UX** | Context menu with modal-style proposal card on canvas | Floating action bar + inline principle node that loads in-situ on the canvas | **Gemini's approach is better.** Creating a "pending" principle node directly on the canvas with a shimmer/loading state, then populating it when inference completes, is more fluid than a detached proposal card. Edit-in-place on the node + approve button on the node itself follows Miro/FigJam patterns and is more discoverable. |
| **WebView lifecycle** | Load empty HTML string on tab switch to release page memory | Fully deallocate WKWebView on `onDisappear`, recreate on `onAppear` | **Claude's approach is safer.** Full deallocation risks losing WebView configuration, registered handlers, and introduces re-creation latency. Loading empty HTML releases 90%+ of page memory while keeping the shell warm for instant re-injection. This is Safari's actual tab suspension pattern. |

### Novel Insights from Gemini

1. **Shared `WKProcessPool`:** If both canvases must coexist, share a `WKProcessPool` to reduce per-process memory overhead. Not mentioned in internal audit.
2. **`Cmd+K` for canvas actions:** Extend the existing `CommandPaletteView` to work inside the Investigation Board — "Create Entity", "Add Annotation", "Distill selection" as keyboard-driven commands. Powerful for power users.
3. **SQLite as single source of truth:** Treat the React canvas as a stateless renderer. All state lives in Swift/SQLite. WebView can be destroyed and recreated on demand because it loads state fresh each time. This is the cleanest architecture for memory management.
4. **In-situ principle node:** Instead of a separate proposal card, create a real Principle node on the canvas in "pending" state with shimmer animation. Populate with LLM response. User edits text in-place and approves via button on the node. More Miro-like, more fluid.

### Reconciliation

Both models agree on the product vision, the dual-mode architecture, and the critical risks (memory, bridge complexity, SceneKit deprecation). The disagreements are tactical, not strategic.

The strongest combined recommendation is: **unify the React canvases, build the feature before abstracting components, make the Distill Principle flow in-situ on the canvas, and treat WebViews as stateless renderers with SQLite as the source of truth.** This reduces engineering overhead while improving the UX.

The revised phase ordering, incorporating both models' insights:
1. Phase 1-lite: Panel modifier extraction (~4h) — the most obvious, zero-risk extraction
2. Phase 4a: Reference index skeleton (~8h) — gives Phase 2 real cross-link data from day one
3. Phase 2: Investigation Board (~25-35h) — single Vite project, client-side routing, in-situ distill flow
4. Phase 1-full: Extract remaining components from confirmed duplication (~8-12h)
5. Phase 4b: Cross-Link UI + batch chat indexing (~12-22h)
6. Phase 3: 3D Atlas refinement (~10-15h)

---

## Design Language Constraint

**Notion for architecture, Apple for aesthetics.** The plan draws heavily from Notion's information architecture patterns (composability, cross-linking, dual views, sidebar sections). The VISUAL design must follow Apple's design language instead:

- **No emoji as UI chrome.** Chat bubbles can have emoji (user-generated content), but sidebar headers, status badges, context menus, node types, and section labels must use geometric indicators (dots, rings, bars), SF Symbols, or typographic labels. The context menu mockup in the brainstorm used emoji (sparkle, folder, link, pin, trash) — replace with SF Symbols.
- **Status via geometry, not decoration.** Active = solid dot, pending = hollow ring, error = filled triangle. Not checkmark emoji or red X emoji.
- **Typography over iconography.** Section headers use text weight and opacity for hierarchy, not icon + text pairs unless the icon adds genuine information.
- **Material and depth.** Use opacity gradients and subtle blur for panel layering — Apple's "materials" approach. Not flat colored backgrounds with hard borders.
- **Animation = physics, not personality.** Spring curves (already in MacAnimation), inertial scrolling, spatial transitions. Not bounce effects or playful wobbles.

This constraint applies to all four phases. Phase 1 component extraction is the enforcement point — shared components should embody Apple's restraint by default.

---

## Conditions for Approval (Revised — Cross-Model Consensus)

1. **Performance prototype first.** Build a 300-node React Flow canvas in WKWebView on the Mac Mini. Profile with Instruments. Go/no-go threshold: web process <800MB, frame rate >30fps at 200+ visible nodes. This is the FIRST deliverable of Phase 2, before any feature work.

2. **Rename "Investigation Board."** The name collides with existing `InvestigationModels.swift` (URL content analysis). Use "Research Canvas" or "Evidence Board" — decide before Phase 2 begins.

3. **Unify React canvases into a single Vite project.** (Gemini recommendation, Claude concurs.) Use client-side routing (`/workflow` and `/investigation`) instead of two independent projects. Halves npm maintenance, build steps, and version management. Single `package.json`, single `npm run build`, single bridge protocol.

4. **Reorder phases per cross-model consensus.** Phase 1-lite (panel modifier, ~4h) → Phase 4a (reference index skeleton, ~8h) → Phase 2 (Investigation Board, ~25-35h) → Phase 1-full (extract from real duplication, ~8-12h) → Phase 4b (cross-link UI, ~12-22h) → Phase 3 (Atlas refinement, ~10-15h).

5. **In-situ Distill Principle flow.** (Gemini recommendation, Claude concurs.) After lasso-select, show a floating action bar (not context menu). "Distill" creates a pending Principle node directly on canvas with shimmer loading state. LLM response populates the node. User edits text in-place, approves via button on node. More Miro-like, more discoverable.

6. **Cross-link indexing is batch, not real-time.** Document as an architectural constraint. Never add entity mention indexing to the chat write path.

7. **WebView memory management.** On tab switch away from a canvas, call `webView.loadHTMLString("", baseURL: nil)` to release page memory. Re-inject content when returning. Use shared `WKProcessPool` if both canvases coexist in memory.

8. **SQLite as single source of truth.** (Gemini recommendation.) Treat the React canvas as a stateless renderer. All canvas state (positions, groups, board contents) persisted in SQLite. WebView can be destroyed and recreated on demand.

9. **Add `user_id` to `entity_references` table.** Costs nothing now, prevents painful migration if multi-user ever happens.

10. **Apple design language, not emoji.** Notion inspires information architecture; Apple inspires visual design. No emoji as UI chrome — use SF Symbols and geometric indicators. Status via dots/rings/bars, not emoji badges.
