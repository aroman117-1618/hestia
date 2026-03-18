# Research View Unification Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate the standalone Memory Browser tab into the Research view as a third toggle (`Graph | Principles | Memory`), add chunk editing capability with graph refresh, and wire approved principles into Hestia's system prompt so they influence responses.

**Architecture:** Three backend changes (PUT chunk endpoint, manager update method, principles injection into prompt builder) land first so the macOS UI has a real API to call. The macOS structural refactor removes the `.memory` sidebar tab and expands `ResearchMode` to three cases. Chunk editing adds a minimal inline edit affordance to `MemoryChunkRow`. After any chunk edit, ResearchView tracks a `graphNeedsRefresh` flag and reloads the graph when the user switches back to Graph mode.

**Tech Stack:** Python/FastAPI (backend), pytest (backend tests), SwiftUI/macOS (frontend), existing `MemoryManager`, `ResearchManager`, `PromptBuilder`, `MacNeuralNetViewModel`

---

## File Map

### Backend — New / Modified
| File | Change |
|------|--------|
| `hestia/api/schemas/memory.py` | Add `MemoryChunkUpdateRequest` and `MemoryChunkUpdateResponse` Pydantic models |
| `hestia/memory/manager.py` | Add `update_chunk_content()` public method |
| `hestia/api/routes/memory.py` | Add `PUT /v1/memory/chunks/{chunk_id}` route |
| `hestia/orchestration/handler.py` | Add `_load_approved_principles()` coroutine; add to both `asyncio.gather()` calls (handle + handle_streaming); unpack `results[3]`; pass to `build()` |
| `hestia/orchestration/prompt.py` | Add `principles: str = ""` param to `build()`; inject as `## Behavioral Principles` section, excluded from cloud-safe context |

### Backend — Tests
| File | Change |
|------|--------|
| `tests/test_memory_browser.py` | Add tests for PUT `/v1/memory/chunks/{chunk_id}`: happy path, 404, partial update, empty body validation |
| `tests/test_prompt_builder.py` | Add test that `build()` injects principles when not cloud_safe; excludes when cloud_safe |

### macOS — Modified
| File | Change |
|------|--------|
| `HestiaApp/macOS/State/WorkspaceState.swift` | Remove `case memory` from `WorkspaceView` enum |
| `HestiaApp/macOS/Views/Chrome/IconSidebar.swift` | Remove `navIcon(.memory, ...)` and its tooltip label |
| `HestiaApp/macOS/Views/WorkspaceRootView.swift` | Remove `case .memory: MemoryBrowserView()` from switch |
| `HestiaApp/macOS/AppDelegate.swift` | Remove `showMemoryView()` method, remove `"5"` keyboard shortcut branch for Memory, remove Memory Browser `NSMenuItem` from `buildMainMenu()` |
| `HestiaApp/macOS/DesignSystem/Accessibility.swift` | Remove `case .memory:` from `WorkspaceView` exhaustive switch |
| `HestiaApp/macOS/State/CommandPaletteState.swift` | Remove `nav.memory` `PaletteCommand` entry |
| `HestiaApp/macOS/Views/Research/ResearchView.swift` | Rename `case explorer` → `case principles`; add `case memory`; update toggle header to 3 buttons (Graph \| Principles \| Memory); fix `headerBar` conditional so time range picker shows only in Principles mode; add memory branch to content switch; add `graphNeedsRefresh` flag + `.onChange` graph reload |
| `HestiaApp/macOS/Views/Memory/MemoryBrowserView.swift` | Add optional `onChunkEdited: (() -> Void)?` closure param passed down to rows |
| `HestiaApp/macOS/Views/Memory/MemoryChunkRow.swift` | Add edit affordance: hover pencil button, expandable edit form (TextEditor + type Picker), Save/Cancel calling async `viewModel.updateChunk()` |
| `HestiaApp/macOS/ViewModels/MacMemoryBrowserViewModel.swift` | Add `updateChunk(id:content:chunkType:tags:) async` method |
| `HestiaApp/macOS/Services/APIClient+Memory.swift` | Add `updateChunk(_ id: String, request: MemoryChunkUpdateRequest) async throws -> MemoryChunkItem` |
| `HestiaApp/macOS/Models/MemoryBrowserModels.swift` | Add `MemoryChunkUpdateRequest` Swift struct |

---

## Task 1: Backend — Memory Chunk Update Endpoint

Add `PUT /v1/memory/chunks/{chunk_id}` so users can correct chunk content, type, and tags from the macOS UI.

**Files:**
- Modify: `hestia/api/schemas/memory.py`
- Modify: `hestia/memory/manager.py`
- Modify: `hestia/api/routes/memory.py`
- Test: `tests/test_memory_browser.py`

- [ ] **Step 1.1: Understand the existing test pattern**

Before writing tests, read `tests/test_memory_browser.py` to understand the fixture and mocking pattern used. Tests in this codebase call route functions directly with a patched `get_memory_manager`, not via an HTTP client. The pattern looks like:

```python
@pytest.mark.asyncio
async def test_something():
    mock_memory = AsyncMock()
    mock_memory.some_method.return_value = expected_value
    with patch("hestia.api.routes.memory.get_memory_manager", return_value=mock_memory):
        result = await route_function(param=value, device_id="test-device")
    assert result.field == expected
```

Follow this exact pattern for the new tests.

- [ ] **Step 1.2: Write failing tests**

Add to `tests/test_memory_browser.py`:

```python
@pytest.mark.asyncio
async def test_update_chunk_content_success():
    """PUT /v1/memory/chunks/{id} returns updated chunk on success."""
    from hestia.api.routes.memory import update_memory_chunk
    from hestia.api.schemas.memory import MemoryChunkUpdateRequest
    from hestia.memory.models import ConversationChunk, ChunkType
    from unittest.mock import AsyncMock, patch, MagicMock

    fake_chunk = MagicMock(spec=ConversationChunk)
    fake_chunk.id = "chunk-123"
    fake_chunk.content = "Updated content."
    fake_chunk.chunk_type = ChunkType.FACT
    fake_chunk.chunk_type.value = "fact"
    fake_chunk.tags = None

    mock_memory = AsyncMock()
    mock_memory.update_chunk_content.return_value = fake_chunk

    with patch("hestia.api.routes.memory.get_memory_manager", return_value=mock_memory):
        result = await update_memory_chunk(
            chunk_id="chunk-123",
            request=MemoryChunkUpdateRequest(content="Updated content."),
            device_id="test-device",
        )

    assert result.chunk_id == "chunk-123"
    assert result.content == "Updated content."
    mock_memory.update_chunk_content.assert_awaited_once_with(
        chunk_id="chunk-123", content="Updated content.", chunk_type=None, tags=None
    )


@pytest.mark.asyncio
async def test_update_chunk_not_found():
    """PUT returns 404 HTTPException when manager returns None."""
    from hestia.api.routes.memory import update_memory_chunk
    from hestia.api.schemas.memory import MemoryChunkUpdateRequest
    from fastapi import HTTPException
    from unittest.mock import AsyncMock, patch

    mock_memory = AsyncMock()
    mock_memory.update_chunk_content.return_value = None

    with patch("hestia.api.routes.memory.get_memory_manager", return_value=mock_memory):
        with pytest.raises(HTTPException) as exc_info:
            await update_memory_chunk(
                chunk_id="missing-id",
                request=MemoryChunkUpdateRequest(content="anything"),
                device_id="test-device",
            )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_update_chunk_empty_body_rejected():
    """MemoryChunkUpdateRequest raises ValidationError when no fields provided."""
    from hestia.api.schemas.memory import MemoryChunkUpdateRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        MemoryChunkUpdateRequest()  # no content, chunk_type, or tags
```

- [ ] **Step 1.3: Run tests — expect failures**

```bash
source .venv/bin/activate
python -m pytest tests/test_memory_browser.py::test_update_chunk_content_success tests/test_memory_browser.py::test_update_chunk_not_found -v --timeout=30
```

Expected: `FAILED` — `update_memory_chunk` route doesn't exist yet.

- [ ] **Step 1.4: Add Pydantic schemas**

In `hestia/api/schemas/memory.py`, add after the existing staged memory schemas:

```python
class MemoryChunkUpdateRequest(BaseModel):
    """Request body for PUT /v1/memory/chunks/{chunk_id}."""
    content: Optional[str] = None
    chunk_type: Optional[str] = None
    tags: Optional[List[str]] = None

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "MemoryChunkUpdateRequest":
        if self.content is None and self.chunk_type is None and self.tags is None:
            raise ValueError("At least one of content, chunk_type, or tags must be provided.")
        return self


class MemoryChunkUpdateResponse(BaseModel):
    """Response for PUT /v1/memory/chunks/{chunk_id}."""
    chunk_id: str
    content: str
    chunk_type: str
    tags: List[str]
    updated_at: str
```

Ensure `Optional`, `List`, `model_validator` are imported (check existing imports in the file and add any missing ones).

- [ ] **Step 1.5: Add manager method**

In `hestia/memory/manager.py`, add after `flag_sensitive()`:

```python
async def update_chunk_content(
    self,
    chunk_id: str,
    content: Optional[str] = None,
    chunk_type: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Optional[ConversationChunk]:
    """
    Update a chunk's content, type, and/or tags.

    Calls database.update_chunk() then vector_store.update_chunk()
    so the ChromaDB embedding stays in sync with content changes.
    """
    chunk = await self.database.get_chunk(chunk_id)
    if chunk is None:
        return None

    if content is not None:
        chunk.content = content
    if chunk_type is not None:
        from hestia.memory.models import ChunkType
        chunk.chunk_type = ChunkType(chunk_type)
    if tags is not None:
        if chunk.tags is None:
            from hestia.memory.models import ChunkTags
            chunk.tags = ChunkTags(topics=tags)
        else:
            chunk.tags.topics = tags

    await self.database.update_chunk(chunk)
    self.vector_store.update_chunk(chunk)

    self.logger.info(
        "Chunk updated by user",
        component=LogComponent.MEMORY,
        data={"chunk_id": chunk_id},
    )
    return chunk
```

Check that `get_chunk(chunk_id)` exists in `database.py` (search for it — it should exist since `approve_memory` fetches chunks by ID). If it's named differently, use the correct method name.

- [ ] **Step 1.6: Add route**

In `hestia/api/routes/memory.py`, add after `set_memory_sensitivity()`:

```python
@router.put(
    "/chunks/{chunk_id}",
    response_model=MemoryChunkUpdateResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Chunk not found"},
        422: {"description": "No fields provided"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Update a memory chunk",
    description="Update the content, type, and/or tags of a memory chunk. "
                "Re-indexes the chunk in ChromaDB if content changes.",
)
async def update_memory_chunk(
    chunk_id: str,
    request: MemoryChunkUpdateRequest,
    device_id: str = Depends(get_device_token),
) -> MemoryChunkUpdateResponse:
    try:
        memory = await get_memory_manager()
        chunk = await memory.update_chunk_content(
            chunk_id=chunk_id,
            content=request.content,
            chunk_type=request.chunk_type,
            tags=request.tags,
        )

        if chunk is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "chunk_not_found", "message": f"Chunk '{chunk_id}' not found."},
            )

        logger.info(
            "Memory chunk updated",
            component=LogComponent.API,
            data={"device_id": device_id, "chunk_id": chunk_id},
        )

        tags_list = chunk.tags.topics if chunk.tags else []
        return MemoryChunkUpdateResponse(
            chunk_id=chunk.id,
            content=chunk.content,
            chunk_type=chunk.chunk_type.value,
            tags=tags_list,
            updated_at=datetime.utcnow().isoformat(),  # ConversationChunk has no updated_at attr
        )

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_chunk_type", "message": "Invalid chunk_type value."},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to update chunk: {sanitize_for_log(e)}",
            component=LogComponent.API,
            data={"chunk_id": chunk_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message": "Failed to update memory chunk."},
        )
```

Add `MemoryChunkUpdateRequest, MemoryChunkUpdateResponse` to the schemas import at the top of `routes/memory.py`. Ensure `datetime` is imported (check existing imports).

- [ ] **Step 1.7: Run tests — expect pass**

```bash
python -m pytest tests/test_memory_browser.py::test_update_chunk_content_success tests/test_memory_browser.py::test_update_chunk_not_found tests/test_memory_browser.py::test_update_chunk_empty_body_rejected -v --timeout=30
```

Expected: 3 PASSED.

- [ ] **Step 1.8: Run full suite — expect no regressions**

```bash
python -m pytest tests/ -q --timeout=30 2>&1 | tail -5
```

Expected: same pass count as baseline + 3 new tests.

- [ ] **Step 1.9: Commit**

```bash
git add hestia/api/schemas/memory.py hestia/memory/manager.py hestia/api/routes/memory.py tests/test_memory_browser.py
git commit -m "feat: PUT /v1/memory/chunks/{id} — user-editable memory chunks with ChromaDB re-index"
```

---

## Task 2: Backend — Wire Approved Principles Into System Prompt

Approved principles should influence every Hestia response. Add them to the parallel pre-inference gather and inject as a `## Behavioral Principles` section in the system prompt, excluded from cloud-safe context.

**Files:**
- Modify: `hestia/orchestration/handler.py`
- Modify: `hestia/orchestration/prompt.py`
- Test: `tests/test_prompt_builder.py` (or create if it doesn't exist)

- [ ] **Step 2.1: Write failing tests**

Find the prompt builder test file (`ls tests/ | grep prompt`). Create `tests/test_prompt_builder.py` if needed. Test at the `PromptBuilder.build()` level — this is the clean unit to test, not the full handler:

```python
import pytest
from unittest.mock import MagicMock, patch

from hestia.orchestration.prompt import PromptBuilder


@pytest.fixture
def prompt_builder():
    mode_manager = MagicMock()
    mode_manager.get_system_prompt.return_value = "You are Tia."
    return PromptBuilder(mode_manager=mode_manager)


def test_principles_injected_when_not_cloud_safe(prompt_builder):
    """Approved principles appear in the system message when cloud_safe=False."""
    request = MagicMock()
    request.content = "hello"
    request.mode = MagicMock()
    request.context = None

    messages, components = prompt_builder.build(
        request=request,
        memory_context="",
        principles="[scheduling] User prefers bullet summaries",
        cloud_safe=False,
    )

    # Principles are appended to full_system and appear in messages[0].content
    # (not in components.system_prompt, which is the base persona prompt only)
    system_message_content = messages[0].content
    assert "Behavioral Principles" in system_message_content
    assert "[scheduling]" in system_message_content


def test_principles_excluded_when_cloud_safe(prompt_builder):
    """Approved principles are NOT in the system message when cloud_safe=True."""
    request = MagicMock()
    request.content = "hello"
    request.mode = MagicMock()
    request.context = None

    messages, components = prompt_builder.build(
        request=request,
        memory_context="",
        principles="[scheduling] User prefers bullet summaries",
        cloud_safe=True,
    )

    system_message_content = messages[0].content
    assert "Behavioral Principles" not in system_message_content
```

Adjust the fixture and call pattern to match the actual `PromptBuilder.__init__` signature — read the top of `hestia/orchestration/prompt.py` first to confirm. `Message` is imported from `hestia.inference` and has a `.content` str attribute.

- [ ] **Step 2.2: Run tests — expect failures**

```bash
python -m pytest tests/test_prompt_builder.py -v --timeout=30
```

Expected: FAILED — `build()` doesn't accept `principles` yet.

- [ ] **Step 2.3: Add `principles` parameter to `prompt.py`'s `build()`**

In `hestia/orchestration/prompt.py`, update the `build()` signature:

```python
def build(
    self,
    request: Any,
    memory_context: str = "",
    conversation: Any = None,
    additional_system_instructions: Optional[str] = None,
    cloud_safe: bool = False,
    user_profile_context: str = "",
    principles: str = "",      # ← add this
) -> tuple:
```

Inside `build()`, locate the `full_system` assembly block (lines 412–418) which looks like:

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

Insert the principles block AFTER the memory append but BEFORE the `messages.append(...)` call:

```python
if formatted_memory:
    full_system = f"{full_system}\n\n{formatted_memory}"
# Inject approved behavioral principles (excluded from cloud-safe builds)
if principles and not cloud_safe:
    full_system = f"{full_system}\n\n## Behavioral Principles\n{principles}"
messages.append(Message(role="system", content=full_system))
```

**Important:** `build()` uses direct string concatenation on `full_system`, NOT a `parts` list. Do not use `parts.append()` — it does not exist in this method.

- [ ] **Step 2.4: Run prompt tests — expect pass**

```bash
python -m pytest tests/test_prompt_builder.py -v --timeout=30
```

Expected: 2 PASSED.

- [ ] **Step 2.5: Add `_load_approved_principles()` to handler**

In `hestia/orchestration/handler.py`, add this helper method to the `RequestHandler` class:

```python
async def _load_approved_principles(self) -> str:
    """
    Load approved behavioral principles from ResearchManager.
    Returns formatted string for system prompt injection.
    Never raises — returns empty string on any failure.
    """
    try:
        from hestia.research.manager import get_research_manager
        from hestia.research.models import PrincipleStatus
        research = await get_research_manager()
        result = await research.list_principles(status=PrincipleStatus.APPROVED, limit=20)
        principles = result.get("principles", [])
        if not principles:
            return ""
        lines = [f"[{p['domain']}] {p['content']}" for p in principles]
        return "\n".join(lines)
    except Exception as e:
        self.logger.warning(
            f"Failed to load approved principles: {type(e).__name__}",
            component=LogComponent.ORCHESTRATION,
        )
        return ""
```

- [ ] **Step 2.6: Add to both gather() calls + unpack results[3]**

There are two `asyncio.gather()` calls in handler.py:
- **`handle()`** — around line 520
- **`handle_streaming()`** — around line 795

Add `self._load_approved_principles()` as the 4th coroutine to **both**:

```python
results = await asyncio.gather(
    memory.build_context(...),
    self._load_user_profile_context(request, will_use_cloud),
    council.classify_intent(request.content),
    self._load_approved_principles(),   # ← add this
    return_exceptions=True,
)
```

After the existing `results[2]` (intent) unpack block in **each function**, add:

```python
# Unpack principles result (excluded from cloud-safe builds)
principles_context = ""
if not isinstance(results[3], Exception) and not will_use_cloud:
    principles_context = results[3] or ""
```

For `handle_streaming()`, insert this block immediately after the `# Unpack intent result` block (search for `intent = None` in the streaming function to find the right location).

- [ ] **Step 2.7: Pass principles_context to both build() calls**

In `handler.py`, there are at least 2 calls to `self._prompt_builder.build(...)`. Update each to pass `principles=principles_context`:

```python
messages, prompt_components = self._prompt_builder.build(
    request=request,
    memory_context=memory_context,
    conversation=conversation,
    additional_system_instructions=combined_instructions,
    cloud_safe=will_use_cloud,
    user_profile_context=user_profile_context,
    principles=principles_context,   # ← add this
)
```

- [ ] **Step 2.8: Run full suite**

```bash
python -m pytest tests/ -q --timeout=30 2>&1 | tail -5
```

Expected: no regressions, new prompt builder tests pass.

- [ ] **Step 2.9: Commit**

```bash
git add hestia/orchestration/handler.py hestia/orchestration/prompt.py tests/test_prompt_builder.py
git commit -m "feat: inject approved principles into system prompt (cloud-safe excluded)"
```

---

## Task 3: macOS — Structural Refactor (Remove Memory Sidebar Tab, Add Memory Toggle)

Remove the standalone Memory Browser from the sidebar. **Six files** reference `WorkspaceView.memory` — all must be updated or the build fails.

**Files:**
- Modify: `HestiaApp/macOS/State/WorkspaceState.swift`
- Modify: `HestiaApp/macOS/Views/Chrome/IconSidebar.swift`
- Modify: `HestiaApp/macOS/Views/WorkspaceRootView.swift`
- Modify: `HestiaApp/macOS/AppDelegate.swift`
- Modify: `HestiaApp/macOS/DesignSystem/Accessibility.swift`
- Modify: `HestiaApp/macOS/State/CommandPaletteState.swift`
- Modify: `HestiaApp/macOS/Views/Research/ResearchView.swift`

- [ ] **Step 3.1: Remove `.memory` from WorkspaceView enum**

In `HestiaApp/macOS/State/WorkspaceState.swift`, remove `case memory`. The enum becomes:

```swift
enum WorkspaceView: String, CaseIterable {
    case command
    case health
    case research
    case explorer
    case settings
}
```

- [ ] **Step 3.2: Remove Memory Browser sidebar icon**

In `HestiaApp/macOS/Views/Chrome/IconSidebar.swift`:
- Remove: `navIcon(.memory, systemName: "brain.head.profile", shortcut: 5)`
- Remove the `case .memory: "Memory Browser"` line from the `accessibilityLabel(for:)` / `viewLabel` switch

- [ ] **Step 3.3: Remove `.memory` case from WorkspaceRootView**

In `HestiaApp/macOS/Views/WorkspaceRootView.swift`, remove the `case .memory: MemoryBrowserView()` branch.

- [ ] **Step 3.4: Remove Memory Browser from AppDelegate**

In `HestiaApp/macOS/AppDelegate.swift`:
- Remove the `showMemoryView()` method (or the equivalent that calls `switchView(to: .memory)`)
- Remove the `case "5":` keyboard shortcut branch that calls Memory view
- Remove the "Memory Browser" `NSMenuItem` from `buildMainMenu()`

Read the file first to understand the exact method and menu structure before editing.

- [ ] **Step 3.5: Remove `.memory` from Accessibility extension**

In `HestiaApp/macOS/DesignSystem/Accessibility.swift`, remove the `case .memory:` line from the `WorkspaceView` switch statement (Swift's exhaustive switch will fail to compile otherwise).

- [ ] **Step 3.6: Remove Memory entry from CommandPaletteState**

In `HestiaApp/macOS/State/CommandPaletteState.swift`, remove the `PaletteCommand` entry whose action calls `switchView(.memory)` or similar.

- [ ] **Step 3.7: Update ResearchMode and ResearchView**

In `HestiaApp/macOS/Views/Research/ResearchView.swift`:

**1. Update ResearchMode enum** (bottom of file, around line 799):

```swift
enum ResearchMode {
    case graph
    case principles   // renamed from .explorer
    case memory       // new
}
```

**2. Fix the content switch** — rename `case .explorer:` → `case .principles:`, add `case .memory:`:

```swift
switch selectedMode {
case .graph:
    graphContentWithPanel
case .principles:
    ZStack {
        ambientBackground
        ResearchPrinciplesView(viewModel: graphViewModel)
    }
    .frame(maxWidth: .infinity, maxHeight: .infinity)
case .memory:
    MemoryBrowserView(onChunkEdited: { graphNeedsRefresh = true })
        .frame(maxWidth: .infinity, maxHeight: .infinity)
}
```

**3. Add `graphNeedsRefresh` state** at the top of the struct:

```swift
@State private var graphNeedsRefresh = false
```

**4. Hide `filterBar` in Memory mode** — `filterBar` contains graph-specific data source pills that are irrelevant in Memory mode. In the body where `filterBar` is called unconditionally after `headerBar`, wrap it:

```swift
if selectedMode != .memory {
    filterBar(compact: isCompact)
        .padding(.top, MacSpacing.sm)
}
```

Remove the original unconditional `filterBar` call.

**6. Update the toggle header** — find the `HStack` with the two mode buttons and add a third. Toggle order is Graph | Principles | Memory:

```swift
HStack(spacing: 2) {
    modeButton(.graph,      icon: "point.3.connected.trianglepath.dotted", label: "Graph",      compact: compact)
    modeButton(.principles, icon: "lightbulb",                              label: "Principles", compact: compact)
    modeButton(.memory,     icon: "brain.head.profile",                    label: "Memory",     compact: compact)
}
```

**7. Fix the `headerBar` time range conditional** — currently the `else` branch shows `timeRangePicker` for any non-graph mode. After adding `.memory`, that would incorrectly show the time picker in Memory mode. Update to be explicit:

```swift
if selectedMode == .graph {
    // refresh / graph-specific controls
} else if selectedMode == .principles {
    timeRangePicker(compact: compact)
}
// .memory mode: no trailing header control
```

Find the exact conditional in `headerBar(compact:)` and update it.

**8. Add `.onChange` for graph refresh on mode switch**:

```swift
.onChange(of: selectedMode) { _, newMode in
    if newMode == .graph && graphNeedsRefresh {
        graphNeedsRefresh = false
        Task { await graphViewModel.loadGraph() }
    }
}
```

Add this modifier to the outer `GeometryReader` or `VStack` in the view body.

- [ ] **Step 3.8: Build — expect success**

```bash
xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build -project HestiaApp/HestiaApp.xcodeproj 2>&1 | grep -E "error:|BUILD"
```

Expected: `BUILD SUCCEEDED`. If errors, they'll be exhaustive switch failures — add the missing cases or fix the references.

- [ ] **Step 3.9: Commit**

```bash
git add HestiaApp/macOS/State/WorkspaceState.swift \
        HestiaApp/macOS/Views/Chrome/IconSidebar.swift \
        HestiaApp/macOS/Views/WorkspaceRootView.swift \
        HestiaApp/macOS/AppDelegate.swift \
        HestiaApp/macOS/DesignSystem/Accessibility.swift \
        HestiaApp/macOS/State/CommandPaletteState.swift \
        HestiaApp/macOS/Views/Research/ResearchView.swift
git commit -m "feat: move Memory Browser into Research view as third toggle (Graph | Principles | Memory)"
```

---

## Task 4: macOS — API Client Update Method + Chunk Editing UI

Wire the PUT endpoint into the macOS client and add inline edit affordance to memory chunk rows.

**Files:**
- Modify: `HestiaApp/macOS/Models/MemoryBrowserModels.swift`
- Modify: `HestiaApp/macOS/Services/APIClient+Memory.swift`
- Modify: `HestiaApp/macOS/ViewModels/MacMemoryBrowserViewModel.swift`
- Modify: `HestiaApp/macOS/Views/Memory/MemoryBrowserView.swift`
- Modify: `HestiaApp/macOS/Views/Memory/MemoryChunkRow.swift`

- [ ] **Step 4.1: Add Swift request model**

In `HestiaApp/macOS/Models/MemoryBrowserModels.swift`, add:

```swift
struct MemoryChunkUpdateRequest: Codable {
    let content: String?
    let chunkType: String?
    let tags: [String]?

    enum CodingKeys: String, CodingKey {
        case content
        case chunkType = "chunk_type"
        case tags
    }
}
```

- [ ] **Step 4.2: Add APIClient method**

In `HestiaApp/macOS/Services/APIClient+Memory.swift`, add:

```swift
func updateChunk(_ id: String, request: MemoryChunkUpdateRequest) async throws -> MemoryChunkItem {
    // Path follows the same pattern as listMemoryChunks — no /v1 prefix, base URL includes it
    return try await put("/memory/chunks/\(id)", body: request)
}
```

Read existing `APIClient+*.swift` files first to confirm the exact `put()` call pattern used (generic return type, body encoding). Match it exactly.

- [ ] **Step 4.3: Add async updateChunk to ViewModel**

`MacMemoryBrowserViewModel` is `@MainActor`. Add an `async` method (not `Task { }`) consistent with the existing VM pattern:

```swift
func updateChunk(
    id: String,
    content: String?,
    chunkType: String?,
    tags: [String]?
) async {
    do {
        let request = MemoryChunkUpdateRequest(content: content, chunkType: chunkType, tags: tags)
        let updated = try await APIClient.shared.updateChunk(id, request: request)
        if let idx = chunks.firstIndex(where: { $0.id == updated.id }) {
            chunks[idx] = updated
        }
    } catch {
        errorMessage = "Failed to save changes."
    }
}
```

Add `@Published var errorMessage: String? = nil` if it doesn't already exist in the VM.

- [ ] **Step 4.4: Add `onChunkEdited` closure to MemoryBrowserView**

In `HestiaApp/macOS/Views/Memory/MemoryBrowserView.swift`:

```swift
struct MemoryBrowserView: View {
    @StateObject private var viewModel = MacMemoryBrowserViewModel()
    var onChunkEdited: (() -> Void)? = nil   // ← add this
    ...
}
```

Pass it down into each row in the `ForEach`:

```swift
ForEach(viewModel.chunks, id: \.id) { chunk in
    MemoryChunkRow(chunk: chunk, viewModel: viewModel, onChunkEdited: onChunkEdited)
}
```

- [ ] **Step 4.5: Add inline editing to MemoryChunkRow**

Read `HestiaApp/macOS/Views/Memory/MemoryChunkRow.swift` first to understand the current structure. Then add:

1. New parameters: `@ObservedObject var viewModel: MacMemoryBrowserViewModel` and `var onChunkEdited: (() -> Void)? = nil`
2. New state: `@State private var isEditing = false`, `@State private var editContent = ""`, `@State private var editChunkType = ""`, `@State private var isHovered = false`
3. Hover-triggered pencil button in the read view:

```swift
// Inside the existing row HStack, add conditionally:
if isHovered {
    Button {
        editContent = chunk.content
        editChunkType = chunk.chunkType
        isEditing = true
    } label: {
        Image(systemName: "pencil")
            .foregroundColor(.secondary)
    }
    .buttonStyle(.plain)
}
```

4. The edit view (shown when `isEditing == true`):

```swift
private var editView: some View {
    VStack(alignment: .leading, spacing: MacSpacing.sm) {
        TextEditor(text: $editContent)
            .font(MacTypography.body)
            .frame(minHeight: 80)
            .overlay(RoundedRectangle(cornerRadius: 6).stroke(Color.accentColor, lineWidth: 1))

        // ChunkType enum values from server: fact, preference, decision, action_item,
        // research, system, insight. "action_item" != "action" — use exact server values.
        let chunkTypes = [
            ("fact", "Fact"), ("preference", "Preference"), ("decision", "Decision"),
            ("action_item", "Action Item"), ("research", "Research"),
            ("system", "System"), ("insight", "Insight")
        ]
        Picker("Type", selection: $editChunkType) {
            ForEach(chunkTypes, id: \.0) { value, label in
                Text(label).tag(value)
            }
        }
        .pickerStyle(.menu)
        .frame(maxWidth: 160)

        HStack {
            Button("Save") {
                Task {
                    await viewModel.updateChunk(
                        id: chunk.id,
                        content: editContent != chunk.content ? editContent : nil,
                        chunkType: editChunkType != chunk.chunkType ? editChunkType : nil,
                        tags: nil
                    )
                    isEditing = false
                    onChunkEdited?()
                }
            }
            .buttonStyle(.borderedProminent)

            Button("Cancel") { isEditing = false }
                .buttonStyle(.bordered)
        }
    }
    .padding(MacSpacing.sm)
    .background(MacColors.cardGradient)   // use the confirmed token from existing MemoryChunkRow
    .cornerRadius(8)
}
```

Note: `MacColors.cardGradient` is the confirmed existing token for card backgrounds in this codebase. Use whatever token the existing `MemoryChunkRow` already uses for its background.

5. Wrap the body in a conditional:

```swift
var body: some View {
    if isEditing {
        editView
    } else {
        // existing content, with hover tracking added
        existingReadView
            .onHover { isHovered = $0 }
    }
}
```

- [ ] **Step 4.6: Build and verify**

```bash
xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build -project HestiaApp/HestiaApp.xcodeproj 2>&1 | grep -E "error:|BUILD"
```

Expected: `BUILD SUCCEEDED`.

- [ ] **Step 4.7: Commit**

```bash
git add HestiaApp/macOS/Models/MemoryBrowserModels.swift \
        HestiaApp/macOS/Services/APIClient+Memory.swift \
        HestiaApp/macOS/ViewModels/MacMemoryBrowserViewModel.swift \
        HestiaApp/macOS/Views/Memory/MemoryBrowserView.swift \
        HestiaApp/macOS/Views/Memory/MemoryChunkRow.swift
git commit -m "feat: inline memory chunk editing in Research Memory tab with graph refresh on switch"
```

---

## Task 5: Documentation + Cleanup

- [ ] **Step 5.1: Update CLAUDE.md API Summary table**

Memory endpoint count goes from 13 → 14. Add `PUT /v1/memory/chunks/{chunk_id}` to the Memory row's Key Routes column.

Also add to Key Architecture Notes: "Approved principles from ResearchManager are injected into every system prompt as a `## Behavioral Principles` section. Excluded from cloud-safe context. Configured via `research.list_principles(status=PrincipleStatus.APPROVED)`."

- [ ] **Step 5.2: Update docs/api-contract.md**

Add to the Memory section:
```
PUT /v1/memory/chunks/{chunk_id}
  Body: { content?, chunk_type?, tags? } — at least one required
  Returns: { chunk_id, content, chunk_type, tags, updated_at }
  Re-indexes ChromaDB embedding if content changes.
```

- [ ] **Step 5.3: Run full backend suite**

```bash
python -m pytest tests/ -q --timeout=30 2>&1 | tail -5
```

Expected: all tests pass.

- [ ] **Step 5.4: Final build check**

```bash
xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build -project HestiaApp/HestiaApp.xcodeproj 2>&1 | tail -3
```

Expected: `BUILD SUCCEEDED`.

- [ ] **Step 5.5: Commit docs**

```bash
git add CLAUDE.md docs/api-contract.md
git commit -m "docs: update API contract and CLAUDE.md for Research view unification"
```

---

## Execution Order

Tasks 1 and 2 are independent — run in parallel if using subagents. Task 3 is UI-only and also independent. Task 4 depends on Task 1 (PUT endpoint schema) and Task 3 (MemoryBrowserView closure param). Task 5 runs last.

```
Task 1 (backend PUT endpoint)  ──┐
Task 2 (principles injection)  ──┤──► Task 4 (macOS editing UI) ──► Task 5 (docs)
Task 3 (macOS structural)      ──┘
```
