# Sprint 12: Coupling & Integration Analysis

## Coupling Concerns: Multi-Source Memory Ingestion

### Current State: Separated Layers

```
┌─────────────────────────────────────────────────────────────┐
│ Orchestration Layer                                         │
│  - RequestHandler.handle()                                  │
│  - Stores conversation via memory.store_exchange()          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Memory Layer (CONVERSATION source only)                     │
│  - MemoryManager (database + vector store + tagger)         │
│  - Stores CONVERSATION chunks → ChromaDB + SQLite           │
│  - Source tagging: NOT YET IMPLEMENTED                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Storage Backends                                            │
│  - SQLite: memory_chunks table + metadata JSON              │
│  - ChromaDB: hestia_memory collection (vectors)             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Inbox Layer (APPLE DATA only)                               │
│  - InboxManager (Mail + Reminders + Calendar clients)       │
│  - Aggregates items → InboxDatabase cache                   │
│  - Source tagging: NOT exported to memory                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ InboxDatabase Storage                                       │
│  - Separate SQLite table (inbox_items)                      │
│  - Read/archive state per user                              │
│  - Data is ephemeral (30s TTL cache)                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Research Layer                                              │
│  - GraphBuilder (queries memory only)                       │
│  - PrincipleStore (ChromaDB hestia_principles)              │
│  - No access to Apple data → sparse graph                   │
└─────────────────────────────────────────────────────────────┘
```

**Result:** Three independent towers. Apple data never reaches memory system. Research graph doesn't visualize inbox/calendar/notes/health.

---

### Sprint 12 Required State: Connected Layers

```
┌─────────────────────────────────────────────────────────────┐
│ Orchestration Layer                                         │
│  - RequestHandler.handle()                                  │
│  - Stores conversation via memory.store_exchange()          │
│    WITH source=MemorySource.CONVERSATION                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Memory Layer (Multi-source)                                 │
│  - MemoryManager supports all sources:                      │
│    CONVERSATION, MAIL, CALENDAR, REMINDERS, NOTES, HEALTH   │
│  - Source param on store() and store_exchange()             │
│  - Stores ALL chunks → ChromaDB + SQLite with source tag    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Storage Backends                                            │
│  - SQLite: memory_chunks.metadata.source (JSON)             │
│  - ChromaDB: hestia_memory collection (all sources)         │
└─────────────────────────────────────────────────────────────┘
     ↑                                          ↑
     │                                          │
┌────┴──────────────────────────────────────────┴────┐
│ Background Task (Orders/APScheduler)               │
│  - Daily inbox export job:                         │
│    InboxManager.export_to_memory()                 │
│    → Converts mail/calendar/reminders to chunks    │
│    → Calls MemoryManager.store_many(...,           │
│       source=MemorySource.MAIL)                    │
│    → Deduplicates by hash                          │
│    → Progress tracking & error recovery            │
└────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Research Layer (Multi-source)                               │
│  - GraphBuilder:                                            │
│    - build_graph(sources=[...]) filters by source           │
│    - Returns nodes from CONVERSATION, MAIL, CALENDAR, etc.  │
│  - DataSource filters (Chat/Email/Notes/Calendar/Reminders)│
│    directly map to sources parameter                        │
│  - UI shows unified knowledge graph across all sources      │
└─────────────────────────────────────────────────────────────┘
```

**Result:** Unified data pipeline. All insights (conversation + email + calendar + notes) flow into single memory system. Research graph shows complete knowledge landscape.

---

## Coupling Points & Risk Factors

### 1. MemoryManager ↔ InboxManager Coupling
**Type:** New, Optional (Unidirectional)

**Direction:** InboxManager → MemoryManager
- InboxManager calls `memory_manager.store_many(chunks)` daily
- Inbox owns the data; Memory owns the insight extraction

**Risk Level:** 🟢 LOW
- Unidirectional (only inbox calls memory)
- No circular dependency
- Clean interface (export_to_memory returns list of chunks)

**Coupling Strength:** Loose
- InboxManager doesn't depend on MemoryManager internally
- Only called from background task scheduler
- Can be bypassed if needed

**Mitigation:**
- Define clear contract: InboxManager returns List[ChunkData] tuples
- MemoryManager.store_many() is side-effect-safe
- Each export run is independent (no state mutation)

---

### 2. Handler ↔ MemoryManager Source Parameter
**Type:** Existing Interface Change

**Change:** Add `source` param to store_exchange()

**Risk Level:** 🟡 MEDIUM
- Breaking change to public interface
- Must update all callers (grep found 1 call in handler.py)
- Handler directly calls MemoryManager

**Coupling Strength:** Tight
- Handler and MemoryManager have established relationship
- But only one call site (line 1229)

**Mitigation:**
- Update call site immediately after signature change
- Add type hints for source parameter
- Document default value (CONVERSATION)

---

### 3. GraphBuilder ↔ MemoryManager Source Filter
**Type:** Existing Interface Enhancement

**Change:** Add `sources` filter to memory search

**Risk Level:** 🟢 LOW
- Additive change (new optional parameter)
- Existing queries unaffected (sources defaults to None)
- GraphBuilder already calls search(), just adds param

**Coupling Strength:** Loose
- GraphBuilder uses MemoryManager as service
- No hard dependency on source field existence

**Mitigation:**
- Add sources as optional parameter with sensible default (all sources)
- Handle None → fetch all sources
- Test with and without filter

---

### 4. PrincipleStore ↔ ChromaDB Client
**Type:** Existing, Needs Async Refactor

**Issue:** Sync initialization in async context

**Risk Level:** 🔴 HIGH
- PrincipleStore.initialize() must be async
- Called from research route handler (async context)
- Will deadlock otherwise

**Coupling Strength:** Tight
- Hard dependency on ChromaDB PersistentClient
- No abstraction layer

**Mitigation:**
- Wrap client creation in asyncio executor
- Add initialization guard to all methods
- Test initialization in asyncio context

---

### 5. InboxManager ↔ MailClient (Lazy Initialization)
**Type:** Existing, No Change Needed

**Pattern:** Lazy initialization via `_get_mail_client()`

**Risk Level:** 🟢 LOW
- Already decoupled
- No circular dependency
- Tested pattern

**Status:** ✅ No changes needed for Sprint 12

---

### 6. Data Consistency: Inbox vs Memory
**Type:** New, Cross-Database

**Concern:** Inbox and Memory use separate SQLite tables. What if export fails halfway?

**Risk Level:** 🟠 MEDIUM
- Two independent databases without transaction coordination
- Email in InboxDatabase but not in MemoryDatabase = data loss
- No rollback mechanism across databases

**Coupling Strength:** Loose (currently)
- InboxDatabase and MemoryDatabase don't share connections
- No shared transaction context

**Mitigation:**
- Define clear success/failure semantics for export
- Use hash-based dedup to prevent re-attempting failed items
- Export returns: {total, stored, skipped, failed, errors}
- Log failures for manual recovery
- Consider idempotency: re-running export is safe (dedup prevents duplicates)

**Example Safe Pattern:**
```python
async def export_to_memory(self, days=30):
    items = await self._database.get_items(days)

    failed = []
    skipped = 0
    stored = 0

    for item in items:
        # Check if already exported
        if await memory_mgr.dedup_by_hash(content, source=MAIL):
            skipped += 1
            continue

        try:
            await memory_mgr.store(content, source=MAIL)
            stored += 1
        except Exception as e:
            failed.append((item.id, str(e)))

    return {
        'total': len(items),
        'stored': stored,
        'skipped': skipped,
        'failed': len(failed),
        'errors': failed
    }
```

If export crashes mid-way, re-running is safe (dedup prevents dups, skips already-stored items).

---

## Interface Contracts

### MemoryManager.store() Updated Signature

```python
async def store(
    self,
    content: str,
    chunk_type: ChunkType = ChunkType.CONVERSATION,
    tags: Optional[ChunkTags] = None,
    metadata: Optional[ChunkMetadata] = None,
    session_id: Optional[str] = None,
    auto_tag: bool = True,
    scope: MemoryScope = MemoryScope.SESSION,
    source: Optional[MemorySource] = None,  # NEW
) -> ConversationChunk:
```

**Callers Must Update:**
- `handler.py:1229` — store_exchange() call
- Any direct `store()` calls (grep for them)

**Default Behavior:**
- If source not specified, defaults to None (existing behavior)
- Chunks without source still stored but can't be filtered by source
- Backward compatible

---

### MemoryManager.store_many() New Method

```python
async def store_many(
    self,
    chunks: List[tuple[str, ChunkType, Optional[ChunkTags], Optional[MemorySource]]],
    session_id: Optional[str] = None,
    auto_tag: bool = True,
) -> Dict[str, Any]:
    """
    Store multiple chunks in batch.

    Args:
        chunks: List of (content, type, tags, source) tuples
        session_id: Session for all chunks
        auto_tag: Enable async auto-tagging

    Returns:
        {
            'stored': List[str],      # Chunk IDs of stored chunks
            'failed': List[tuple[str, str]],  # (content_preview, error_msg)
            'success_count': int,
            'failure_count': int,
            'dedup_count': int,       # Skipped as duplicates
        }
    """
```

**Semantics:**
- Partial success allowed (not all-or-nothing)
- Deduplication is transparent (returns skipped count)
- Returns which chunks succeeded/failed
- Auto-tagging is non-blocking (async background task)

---

### InboxManager.export_to_memory() New Method

```python
async def export_to_memory(
    self,
    memory_manager: Optional[MemoryManager] = None,
    days: int = 30,
    source: Optional[InboxItemSource] = None,
    batch_size: int = 50,
) -> Dict[str, Any]:
    """
    Export inbox items to memory as chunks.

    Args:
        memory_manager: MemoryManager instance (lazy-loads if None)
        days: Export last N days
        source: Export only from specific source, or all if None
        batch_size: Items per store_many() call

    Returns:
        {
            'total_items': int,
            'stored_chunks': int,
            'skipped_duplicates': int,
            'failed_items': List[tuple[str, str]],  # (item_id, error)
            'export_duration_ms': float,
        }
    """
```

**Semantics:**
- Idempotent (safe to run multiple times)
- Deduplication prevents duplicate chunks
- Batch size controls memory/performance tradeoff
- Returns detailed statistics

---

### GraphBuilder.build_graph() Updated Signature

```python
async def build_graph(
    self,
    limit: int = MAX_NODES,
    node_types: Optional[Set[str]] = None,
    center_topic: Optional[str] = None,
    sources: Optional[List[str]] = None,  # NEW
) -> GraphResponse:
```

**Semantics:**
- `sources` is optional (defaults to all sources)
- Filter applied at memory search level
- No breaking change (existing calls work)
- DataSource filter in UI maps directly to sources param

**Mapping (UI → API):**
- Chat → sources=["conversation"]
- Email → sources=["mail"]
- Notes → sources=["notes"]
- Calendar → sources=["calendar"]
- Reminders → sources=["reminders"]
- Health → sources=["health"]
- All → sources=None (fetch all)

---

## Testing Strategy

### Unit Tests (No Breaking)
- Test MemoryManager.store() with various source values
- Test MemoryDatabase.query_chunks() source filtering
- Test InboxManager.export_to_memory() with mocked MemoryManager
- Test GraphBuilder.build_graph() with sources filter

### Integration Tests
- Test full pipeline: email → InboxManager.export_to_memory() → MemoryManager.store_many() → GraphBuilder.build_graph()
- Test deduplication (same email exported twice, should deduplicate)
- Test partial failure (some items fail, others succeed)
- Test DataSource filters in graph (select Chat only, Email only, etc.)

### Async Safety Tests
- Test PrincipleStore.initialize() in asyncio context (no deadlock)
- Test animation rendering with asyncio tasks (no flicker)
- Test concurrent store() calls (thread safety)

### Backward Compatibility Tests
- Existing calls to store_exchange() without source param still work
- Existing graph queries without sources filter still work
- Existing memory chunks without source tag still retrievable

---

## Coupling Summary

| Coupling | Type | Risk | Strength | Mitigation |
|----------|------|------|----------|-----------|
| InboxManager → MemoryManager | New, One-way | LOW | Loose | Clean interface, no circular deps |
| Handler → MemoryManager source | Interface change | MEDIUM | Tight | 1 call site, easy to update |
| GraphBuilder ↔ MemoryManager sources | Enhancement | LOW | Loose | Optional param, backward compatible |
| PrincipleStore ↔ ChromaDB | Async refactor | HIGH | Tight | Use asyncio executor, add guards |
| Inbox ↔ Memory consistency | Cross-DB | MEDIUM | Loose | Hash dedup, idempotent export |

**Overall Coupling Health:** 🟡 MEDIUM

New integration between Inbox and Memory adds coupling but is unidirectional and well-designed. PrincipleStore async refactor is necessary and manageable.

**Recommendation:** ✅ Proceed with Sprint 12 after completing blockers. Coupling is manageable and risk is well-mitigated.
