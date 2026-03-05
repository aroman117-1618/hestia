# Sprint 12 Blockers & Pre-Impl Checklist

## Critical Blockers (Must Fix Before Starting Feature Work)

### 1. MemoryManager.store_exchange() Missing Source Parameter
**File:** `hestia/memory/manager.py:299-337`
**Status:** 🔴 BLOCKER

Current signature:
```python
async def store_exchange(
    self,
    user_message: str,
    assistant_response: str,
    mode: Optional[str] = None,
) -> tuple[ConversationChunk, ConversationChunk]:
```

Required signature:
```python
async def store_exchange(
    self,
    user_message: str,
    assistant_response: str,
    mode: Optional[str] = None,
    source: Optional[MemorySource] = None,  # ADD THIS
) -> tuple[ConversationChunk, ConversationChunk]:
```

Also update:
- `store()` method (line 207) — add `source` param
- Handler call (orchestration/handler.py:1229) — pass `source=MemorySource.CONVERSATION`

**Impact:** Without this, all multi-source ingestion fails. Chunks stored without source tagging.

---

### 2. MemoryDatabase Missing Source Filtering
**File:** `hestia/memory/database.py:246-330`
**Status:** 🔴 BLOCKER

Current: `query_chunks()` doesn't filter by source.

Required: Add source filtering after line 296 (status filter):
```python
if query.sources:
    source_values = [s.value for s in query.sources]
    placeholders = ",".join("?" * len(source_values))
    conditions.append(f"json_extract(metadata, '$.source') IN ({placeholders})")
    params.extend(source_values)
```

Also update `MemoryQuery` model (memory/models.py:236-276) to include:
```python
sources: Optional[List[MemorySource]] = None
```

**Impact:** DataSource filters in graph UI won't work. Query API can't filter by source.

---

### 3. PrincipleStore.initialize() Not Async
**File:** `hestia/research/principle_store.py:56-83`
**Status:** 🔴 BLOCKER

Current: Synchronous initialization creates ChromaDB client synchronously.
```python
def initialize(self, persist_directory: Optional[Path] = None) -> None:
    self._client = chromadb.PersistentClient(...)  # BLOCKS
```

Required: Make async, use executor for blocking calls:
```python
async def initialize(self, persist_directory: Optional[Path] = None) -> None:
    loop = asyncio.get_event_loop()
    self._client = await loop.run_in_executor(
        None,
        chromadb.PersistentClient,
        str(persist_directory),
        Settings(...)
    )
```

**Impact:** Will deadlock when called from async context. Research graph building will hang.

---

### 4. HestiaRenderer No Animation Framework
**File:** `hestia-cli/hestia_cli/renderer.py:1-200`
**Status:** 🔴 BLOCKER

Current: Status rendering is synchronous, single-line. Can't support async animation.

Required: Refactor to state machine + async animation class:
```python
class ThinkingAnimation:
    async def start(self): ...
    async def stop(self): ...
    async def _animate_loop(self): ...

class HestiaRenderer:
    _animation: Optional[ThinkingAnimation] = None
    _render_state: RenderState = RenderState.IDLE

    def _render_status(self, event):
        if event.get("stage") == "inference":
            self._animation = ThinkingAnimation(...)
            asyncio.create_task(self._animation.start())
```

**Impact:** Can't implement fire emoji + spinner verb animation. CLI polish completely blocked.

---

### 5. Missing MemorySource Enum
**File:** `hestia/memory/models.py:1-41`
**Status:** 🔴 BLOCKER (Type Safety)

Current: `ChunkMetadata.source` is `Optional[str]`. Allows typos like `"email"` vs `"mail"`.

Required:
```python
class MemorySource(Enum):
    """Origin of memory chunk."""
    CONVERSATION = "conversation"
    MAIL = "mail"
    CALENDAR = "calendar"
    REMINDERS = "reminders"
    NOTES = "notes"
    HEALTH = "health"
    BACKGROUND_TASK = "background_task"
    IMPORT = "import"
```

Update ChunkMetadata serialization to handle enum.

**Impact:** Type safety. Prevents runtime errors from typos.

---

### 6. InboxManager.export_to_memory() Missing
**File:** `hestia/inbox/manager.py:1-366`
**Status:** 🟠 HIGH (Data Pipeline)

Current: No method to convert inbox items to memory chunks.

Required:
```python
async def export_to_memory(
    self,
    days: int = 30,
    source: Optional[InboxItemSource] = None,
    batch_size: int = 50,
) -> Dict[str, Any]:
    """Export recent inbox items to memory."""
    pass
```

Supporting methods:
- `_inbox_item_to_chunk_content()` — format item as markdown
- `_inbox_item_to_tags()` — extract tags from metadata

**Impact:** Cannot ingest Apple data into memory. Multi-source pipeline completely broken.

---

## Fix Priority Order

### Phase 1 (Do First)
1. Add MemorySource enum to memory/models.py
2. Update ChunkMetadata.source type
3. Add sources param to MemoryQuery

**Time:** 30 minutes

### Phase 2 (Do Second)
4. Update MemoryManager.store() and store_exchange() signatures
5. Update handler.py to pass source param
6. Update all callers (grep for store_exchange, store)

**Time:** 1 hour

### Phase 3 (Do Third)
7. Add source filtering SQL to memory/database.py
8. Add transaction safety (optional but recommended)

**Time:** 1 hour

### Phase 4 (Do Fourth)
9. Make PrincipleStore.initialize() async
10. Add initialization guards to all methods

**Time:** 45 minutes

### Phase 5 (Do Fifth)
11. Refactor renderer to state machine + async animation
12. Add ThinkingAnimation class

**Time:** 2-3 hours

### Phase 6 (Do Sixth)
13. Add MemoryManager.store_many() for bulk operations
14. Add MemoryManager.dedup_by_hash() for deduplication
15. Add InboxManager.export_to_memory() method

**Time:** 2 hours

---

## Verification Steps

After each phase, run:

```bash
# Type checking
mypy hestia/memory/ --strict

# Test affected modules
python -m pytest tests/memory/ -v
python -m pytest tests/research/ -v
python -m pytest hestia-cli/tests/ -v

# Check for broken imports
python -c "from hestia.memory import MemoryManager; from hestia.research import PrincipleStore"
```

---

## Feature-Blocking Dependencies

| Sprint 12 Feature | Blocked By | Phase |
|------------------|-----------|-------|
| Multi-source memory ingestion | Blockers 1, 2, 3, 6 | 1-6 |
| DataSource filters working | Blockers 2, 3 | 1-3 |
| CLI agent colors + fire animation | Blocker 4, 5 | 1, 4, 5 |
| Research graph source filtering | Blockers 2, 3 | 1-3 |
| Background inbox ingestion | Blockers 1, 2, 6 | 1-6 |

---

## Estimated Timeline

- **Phase 1-2:** 1.5 hours ← START HERE
- **Phase 3:** 1 hour
- **Phase 4:** 45 minutes
- **Phase 5:** 2-3 hours ← MOST TIME
- **Phase 6:** 2 hours

**Total:** 8-10 hours of pre-impl work before feature development begins

After completing all phases, feature work (export_to_memory, animation, graph wiring) will be straightforward and low-risk.

---

## Do Not Start Feature Work Until

- [ ] MemorySource enum exists
- [ ] MemoryManager.store_exchange() has source parameter
- [ ] MemoryDatabase.query_chunks() filters by source
- [ ] PrincipleStore.initialize() is async
- [ ] HestiaRenderer refactored to support async animation
- [ ] All grep searches for store_exchange/store show updated calls
- [ ] All tests pass with new signatures

Once all checked, proceed with Sprint 12A/B with confidence.
