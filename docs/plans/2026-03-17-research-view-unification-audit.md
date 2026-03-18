# Plan Audit: Research View Unification
**Date:** 2026-03-17
**Verdict:** APPROVE WITH CONDITIONS — 4 critical bugs must be fixed before execution

## Plan Summary
Consolidates the standalone Memory Browser sidebar tab into the Research view as a third toggle (Graph | Principles | Memory), adds inline chunk editing with graph refresh, and closes the principles loop by injecting approved principles into every system prompt. Backend: 1 new endpoint, 1 new manager method, 1 prompt builder change. macOS: 7 structural file changes + 5 UI files.

---

## Scale Assessment

| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|----------------|-------------------|
| Single user (Andrew) | ✅ Yes | None | N/A |
| Family (2–5 users) | ⚠️ Partial | `_load_approved_principles()` loads ALL principles with no user scoping. ResearchManager is a singleton; principles aren't user-scoped. All family members see same principles. | Medium — would require `user_id` param on `list_principles()` and per-user principle sets |
| Community | ❌ No | Same principle cross-contamination, plus no rate limiting on PUT /chunks (anyone can corrupt any chunk) | High |

**Verdict for current scope:** Single-user is fine. No action needed now — document the user_id gap for future.

---

## Front-Line Engineering

**Feasibility:** Buildable with corrections (see critical bugs below).

**Hidden prerequisites:**
- `get_chunk()` exists in `MemoryDatabase` (line 222 confirmed). `update_chunk_content()` does NOT yet exist in MemoryManager — plan correctly adds it.
- `datetime` must be imported in `routes/memory.py` (not currently imported — add `from datetime import datetime` or use `datetime.utcnow` from existing imports).

**Testing gaps:**
- No test for invalid `chunk_type` value (e.g., "invalid_type") — should return 422 not 500.
- No test for the principles injection path in the handler (only PromptBuilder is tested) — acceptable given handler complexity.

**Developer experience:** The plan is thorough. The instruction to "read file first" before editing `MemoryChunkRow` and `AppDelegate` is correct — both have non-obvious structure.

---

## Architecture Review

**Fit:** Follows manager pattern. New `update_chunk_content()` correctly chains `database.update_chunk()` → `vector_store.update_chunk()` as the existing async-tag flow does (line 292-293 of manager.py).

**API design:** `PUT /v1/memory/chunks/{chunk_id}` — correct HTTP semantics for idempotent update.

**Critical route path bug:** See Bug #1 below.

**Data model:** `MemoryChunkUpdateResponse` is adequate. Using `datetime.utcnow().isoformat()` for `updated_at` is a known pragmatic workaround (ConversationChunk has no `updated_at` field).

**Integration risk:** `_load_approved_principles()` adds a 4th coroutine to both gather() calls. ResearchManager cold-start on first call could add latency if ChromaDB isn't warm. Mitigated by `try/except` returning empty string on failure.

---

## Product Review

**User value:** High. Memory Browser was orphaned; placing it inside Research creates the intended workflow: see the graph → drill into Memory → correct a chunk → switch back to graph (auto-refresh). Principles injection closes a 6-month-old design debt — approved principles finally influence responses.

**Edge cases:**
- Empty Memory tab: "No memories found" empty state already exists in `MemoryBrowserView`. ✅
- No approved principles: `_load_approved_principles()` returns `""` → principles block not injected. ✅
- User edits a chunk then immediately clicks Graph: `graphNeedsRefresh` triggers reload. ✅
- Save fails mid-edit: `errorMessage` surfaces in VM, `isEditing` stays true so user doesn't lose work. ✅

**Scope:** Right-sized. 5 tasks, clean boundaries.

**Opportunity cost:** This is purely additive (Memory Browser moves, doesn't expand). Graph view bugs (SceneKit cutoff) and knowledge graph entity wiring remain deferred — correct prioritization.

---

## UX Review

**Design system compliance:** Uses `MacColors`, `MacSpacing`, `MacTypography`. `MacColors.cardGradient` confirmed as the existing card background token. ✅

**Interaction model:**
- Hover-to-reveal pencil button is standard macOS pattern. ✅
- `.onChange(of: selectedMode)` graph auto-refresh is invisible to the user — could add a brief "Refreshing..." indicator but not required for MVP.

**Empty state:** filterBar hidden in Memory mode (step 3.7 point 4). ✅

**Accessibility concern (non-blocking):** `MemoryChunkRow` edit button only visible on hover — keyboard users can't access it. Fine for initial implementation; note for future a11y pass.

---

## Infrastructure Review

**Deployment impact:** Backend restart required after Python changes. No database migration (no new columns). No new packages.

**Resource impact (Mac Mini M1):** `_load_approved_principles()` adds one DB query per inference call. At 0–50 principles it's negligible. ChromaDB is already loaded for memory/research — no new process.

**Rollback strategy:** Clean — each task commits independently. If principles injection causes issues, revert the handler commit. If Memory tab causes issues, revert Task 3 commit. No schema migrations to undo.

**Monitoring:** `_load_approved_principles()` failure silently returns empty string with a WARNING log. Sufficient.

---

## Executive Verdicts

**CISO: ACCEPTABLE**
No new credential handling. PUT endpoint is JWT-authenticated (same `get_device_token` dependency). Error sanitization maintained via `sanitize_for_log(e)`. Chunk content edits are user-authored and don't touch the security layer. One concern: no authorization check that the device owns the chunk — but Hestia is single-user, all chunks belong to Andrew, so this is acceptable.

**CTO: APPROVE WITH CONDITIONS**
Four bugs must be fixed before execution (see below). Architecture fits established patterns. The principles injection is additive and fail-safe. The `full_system` concatenation pattern must be used consistently — `parts.append` does not exist in `build()`.

**CPO: ACCEPTABLE**
Correct scope. The three-layer model (Graph → Principles → Memory) matches the intended mental model and makes previously orphaned features coherent. Principles influencing responses is the right next step before building any principle-based UI feedback.

---

## Critical Bugs — Must Fix Before Execution

### Bug #1 (CRITICAL): Route path mismatch — 404 in production
**File:** `hestia/api/routes/memory.py` + `HestiaApp/macOS/Services/APIClient+Memory.swift`

Router prefix is `/v1/memory`. Plan route is `@router.put("/{chunk_id}", ...)` → URL becomes `PUT /v1/memory/{chunk_id}`.

Swift client calls `put("/memory/chunks/\(id)", body: request)` (following pattern of existing `listMemoryChunks` which uses `/memory/chunks?...`).

These do NOT match. **Fix:** Change route to `@router.put("/chunks/{chunk_id}", ...)` → URL becomes `PUT /v1/memory/chunks/{chunk_id}`. Also update Swift client to use `/memory/chunks/\(id)` (no `/v1` prefix — base URL already includes it).

### Bug #2 (CRITICAL): `parts.append()` does not exist in `build()`
**File:** `hestia/orchestration/prompt.py`, Step 2.3

`build()` assembles the system message via direct string concatenation on `full_system` (lines 412–418):
```python
full_system = system_prompt
if formatted_user_profile:
    full_system = f"{full_system}\n\n{formatted_user_profile}"
if formatted_context:
    full_system = f"{full_system}\n\n{formatted_context}"
if formatted_memory:
    full_system = f"{full_system}\n\n{formatted_memory}"
messages.append(Message(role="system", content=full_system))
```
There is no `parts` list. The plan's `parts.append(f"\n## Behavioral Principles\n{principles}")` would `NameError` at runtime.

**Fix:** Inject after the memory block, before `messages.append`:
```python
if principles and not cloud_safe:
    full_system = f"{full_system}\n\n## Behavioral Principles\n{principles}"
messages.append(Message(role="system", content=full_system))
```

### Bug #3 (CRITICAL): "action" in Picker → wrong ChunkType value
**File:** `HestiaApp/macOS/Views/Memory/MemoryChunkRow.swift`, Step 4.5

`ChunkType.ACTION_ITEM = "action_item"` (confirmed line 38 of models.py). The plan's Picker includes `"action"` which would send `chunk_type: "action"` to the server, causing `ChunkType("action")` to raise `ValueError` → 500 Internal Server Error.

**Fix:** Replace `"action"` with `"action_item"` in the Picker values list:
```swift
ForEach(["fact", "preference", "decision", "action_item", "research", "system", "insight"], id: \.self)
```
Display label for `"action_item"` should be `"Action Item"` — use a helper dict or inline mapping.

### Bug #4 (HIGH IMPACT): Invalid chunk_type returns 500 instead of 422
**File:** `hestia/api/routes/memory.py`, Step 1.5 (manager) + Step 1.6 (route)

`ChunkType(chunk_type)` raises `ValueError` for unknown type strings. The generic `except Exception` block turns this into a 500. Should be 422.

**Fix:** In `update_chunk_content()` manager method, propagate ValueError. In the route, catch it before the generic handler:
```python
except ValueError as e:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"error": "invalid_chunk_type", "message": f"Invalid chunk_type value."},
    )
except HTTPException:
    raise
except Exception as e:
    ...
```

---

## Final Critiques

**1. Most likely failure:** `_load_approved_principles()` silently returns `""` on ANY exception, including genuine bugs like wrong ResearchManager interface. If principles distillation is ever done and approved, a broken `_load_approved_principles()` would silently never inject them. **Mitigation:** The WARNING log is there; monitor it. Accept this risk — the fail-open design is correct for a non-critical enhancement.

**2. Critical assumption:** The plan assumes `MacMemoryBrowserViewModel` is `@MainActor`. If it's actually `ObservableObject` without `@MainActor`, the `async func updateChunk()` can be called from any thread and the `@Published` mutations need `DispatchQueue.main.async`. **Validate early:** Check `class MacMemoryBrowserViewModel` declaration before writing the method.

**3. Half-time cut list:** If forced to cut, drop Task 2 (principles injection). The structural refactor (Task 3) + chunk editing (Tasks 1+4) deliver the UX value immediately. Principles injection is backend-invisible to the user until they have approved principles, which requires data. Do Task 2 only if time allows.

---

## Conditions for Approval

1. Fix Bug #1: route path → `/chunks/{chunk_id}`, Swift client → `/memory/chunks/\(id)`
2. Fix Bug #2: replace `parts.append(...)` with `full_system = f"{full_system}\n\n## Behavioral Principles\n{principles}"`
3. Fix Bug #3: `"action"` → `"action_item"` in Swift Picker; display as "Action Item"
4. Fix Bug #4: catch `ValueError` in route and return 422

All conditions are targeted edits. Plan is otherwise structurally sound.
