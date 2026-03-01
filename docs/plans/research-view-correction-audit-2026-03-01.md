# Plan Audit: Research View Correction
**Date:** 2026-03-01
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary
Correct the Research View's SceneKit 3D graph interaction model and detail panel layout to match Figma mockups. Remove node dragging (keep camera orbit), add hover detection and selection highlights, replace the bottom card with a right-side detail panel showing connected nodes, and show the filter bar in both graph and explorer modes. Touches 3 files, all macOS-only.

## Scale Assessment
| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|----------------|-------------------|
| Single user | Yes | None — purely client-side UI | N/A |
| Family | Yes | Graph loads all 50 memories regardless of user | Low — add user_id filtering to API call |
| Community | Yes | Same as above | Low |

**Assessment:** This is purely frontend/macOS UI work. No backend changes, no data model changes, no new endpoints. Scale is irrelevant — the graph is bounded by the `limit: 50` API parameter already.

## Front-Line Engineering Review

### Feasibility: HIGH
All 8 items are straightforward SwiftUI + SceneKit modifications. No new dependencies, no new files, no architectural changes.

### Hidden Prerequisites Found
1. **GraphNode needs Equatable conformance** — the plan adds `@Binding var hoveredNode: GraphNode?` but `GraphNode` doesn't conform to `Equatable`. SwiftUI bindings to optional types need this for diffing. **Must add `Equatable` conformance by `id`.**
2. **ChunkType.rawValue display bug** — `actionItem.rawValue` is `"action_item"` (snake_case). Using `.rawValue.capitalized` produces `"Action_item"`, which is ugly. **Must add a `displayName` computed property.**
3. **NSTrackingArea is a new pattern** — no existing usage in the codebase. The plan assumes `NSTrackingArea` + `mouseMoved` but this requires careful integration with NSViewRepresentable. Alternative: use SceneKit's `SCNView` delegate methods or override mouse events in a custom SCNView subclass.

### Testing Gaps
- No automated tests for SceneKit views (visual/interaction testing is manual)
- Connected nodes lookup should be unit-testable if extracted to a pure function
- Hover detection is hard to test programmatically

### Effort Estimate: 1-2 hours
- Items 1, 6: trivial (delete code, remove guard) — 5 min
- Items 3, 4: moderate (SceneKit node manipulation) — 20 min
- Item 5: largest (new SwiftUI layout + detail panel UI) — 45 min
- Items 2, 7, 8: moderate (new code, but straightforward) — 30 min

## Architecture Review

### Fit: EXCELLENT
- All changes stay within existing file boundaries
- No layer violations — ViewModel provides data, View renders it
- SceneKit wrapper remains a clean NSViewRepresentable
- No new dependencies

### Data Model: NO CHANGES
The plan reuses existing `GraphNode`, `GraphEdge`, and `ChunkType` types. No migrations needed.

### Integration Risk: LOW
- Only touches 3 macOS-only files
- iOS builds are completely unaffected
- Backend is completely unaffected
- No shared code changes

## Product Review

### User Value: HIGH
This directly corrects the UI to match approved Figma designs. The current bottom card is wrong per mockups. Hover tooltips and connected nodes add genuine discoverability.

### Edge Cases Identified
- **Empty connected nodes**: Node with no edges should show "No connections" in detail panel
- **Very long content**: Node content text in detail panel needs truncation/scroll
- **Many tags**: Tag pills need horizontal wrapping, not just a single row
- **Selection during load**: If graph reloads while a node is selected, selection should clear

### Scope: RIGHT-SIZED
8 items sounds like a lot, but items 1 and 6 are trivial deletions. The real work is items 2, 3, 5, and 8.

### Opportunity Cost: MINIMAL
This is polish on existing work, not greenfield. It must be done before the Research tab ships.

## UX Review

### Design System Compliance: GOOD
- Plan correctly uses `MacColors.amberAccent`, `MacSpacing.*`, `MacCornerRadius.*`
- Detail panel uses consistent card styling (dark background, amber border)
- Filter bar already uses design system tokens

### Interaction Model: CLEAR
- Click node → detail panel slides in from right
- Click empty space → panel slides out
- Hover → tooltip near cursor
- Trackpad orbit/zoom/pan for camera (SceneKit built-in)

### Platform Divergence: ACCEPTABLE
- iOS NeuralNetView doesn't have a detail panel (different UX on mobile)
- macOS gets the richer interaction model — appropriate for desktop

### Accessibility Concerns
- SceneKit views are not VoiceOver-accessible by default. This is a known limitation — no change from current state. Not blocking for MVP.

### Empty States: COVERED
- Loading state: "Mapping neural connections..." with spinner
- Empty state: brain icon + "No memories yet"
- No selected node: no panel shown (clean)

## Infrastructure Review

### Deployment Impact: ZERO
- macOS-only client changes
- No server restart needed
- No database migration
- No config changes

### Rollback Strategy: CLEAN
- All changes in 3 files
- Git revert is trivial
- No data migration to undo

### Resource Impact: NEGLIGIBLE
- Hover tracking adds mouse event handling (CPU: trivial)
- Selection ring adds one SCNNode per selection (GPU: trivial)
- Text labels add SCNText nodes (GPU: minor, bounded by node count ≤ 50)

## Executive Verdicts

### CISO: ACCEPTABLE
No new data exposure, no new communication paths, no credential handling. Pure UI refactoring. No security implications whatsoever.

### CTO: ACCEPTABLE
Clean separation of concerns. No architecture violations. Removes dead code (drag handler). Adds useful features (hover, connected nodes) without over-engineering. The NSTrackingArea approach needs validation but is standard macOS pattern.

### CPO: ACCEPTABLE
Directly addresses Figma discrepancy. Right-side detail panel matches the approved design. Connected nodes feature adds genuine discovery value. Filter bar visibility fix is a clear UX win.

## Final Critiques

### 1. Most Likely Failure: NSTrackingArea + SCNView interaction
**Risk:** NSTrackingArea in an NSViewRepresentable can have lifecycle issues — tracking area may not update on view resize, or mouse events may conflict with SceneKit's camera control gesture handling.
**Mitigation:** Use a simpler approach — override `mouseMoved(with:)` in a custom `SCNView` subclass rather than adding NSTrackingArea to the existing SCNView. This is more reliable and avoids tracking area lifecycle management. Alternatively, skip hover tooltips entirely for v1 and just rely on click-to-select (which already works).

### 2. Critical Assumption: SCNText rendering quality at small sizes
**Risk:** SCNText at small font sizes in a dark scene can look blurry/aliased, especially with 3D perspective. If text labels look bad, they'll hurt more than help.
**Mitigation:** Test text rendering early. If it looks bad, fall back to SwiftUI overlay labels positioned via `projectPoint()` instead of in-scene SCNText. Or just skip text labels entirely — the detail panel shows content on click, and hover shows content on hover. In-scene text may be redundant.

### 3. Half-Time Cut List
If we had half the time, cut these (in order):
1. **Item 4 (text labels)** — redundant with hover tooltips and detail panel. Cut first.
2. **Item 2 (hover detection)** — nice-to-have, not critical. Click-to-select already works.
3. **Item 3 (highlight ring)** — visual polish. The detail panel opening is sufficient selection feedback.

**Keep at all costs:** Items 1 (remove drag), 5 (right-side panel), 6 (filter bar), 7 (type mapping), 8 (connected nodes). These are the core Figma corrections.

## Conditions for Approval

1. **Add `Equatable` conformance to `GraphNode`** (by `id` only) before adding hover binding
2. **Add `ChunkType.displayName`** computed property instead of using `.rawValue.capitalized`
3. **Deprioritize item 4 (text labels)** — implement last, and only if SCNText looks good. Skip if it doesn't.
4. **For hover (item 2)**: use `mouseMoved(with:)` override on a custom SCNView subclass, NOT NSTrackingArea. Simpler and more reliable. If too complex, defer hover to a follow-up — click-to-select is sufficient for launch.
5. **Handle edge case**: clear `selectedNode` when graph reloads
