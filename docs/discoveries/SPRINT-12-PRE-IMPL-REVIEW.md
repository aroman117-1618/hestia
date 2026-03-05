# Sprint 12 Pre-Implementation Code Review
**Date:** 2026-03-05
**Reviewer:** Senior Backend Engineer
**Scope:** Multi-source memory ingestion, CLI polish, Research graph wiring

---

## Executive Summary

**Overall Code Health:** 7.5/10 (solid but architecturally loose in critical areas)

**Critical Findings:**
1. **Memory→Inbox Coupling Missing** — The `source` parameter is already modeled but never populated or queried. No structural issue, just incomplete wiring.
2. **CLI Renderer Not Extensible** — The current renderer is linear/stateful; adding thinking animations requires refactoring to task-based architecture.
3. **Error Handling Gaps in Bulk Operations** — `store_exchange()` and inbox export will need partial-success semantics that don't currently exist.
4. **Type Hints Incomplete in Handler** — `store_exchange()` signature doesn't match what Sprint 12 requires (missing `source` parameter).

**Severity Breakdown:**
- 🔴 **Blockers:** 2 (handler signature, renderer architecture)
- 🟠 **High:** 5 (error handling, bulk operations, async patterns)
- 🟡 **Medium:** 8 (type safety, coupling concerns)
- 🟢 **Low:** 4 (tech debt, minor refactoring)

**Estimated Pre-Impl Work:** 4-6 hours of refactoring before feature development begins.

---

## File-by-File Review

### 1. `/sessions/bold-gracious-albattani/mnt/hestia/hestia/memory/models.py`

**Health:** 8/10 (well-structured, future-proof)

#### Strengths
- ✅ `ChunkMetadata.source` field already exists (line 96) — exactly what Sprint 12 needs
- ✅ Flexible `ChunkTags` with custom key-value support (lines 57, 189-190)
- ✅ Strong enum-based typing (`MemoryScope`, `MemoryStatus`, `ChunkType`)
- ✅ Clear dataclass semantics with factory methods

#### Issues

| Issue | Severity | Location | Details |
|-------|----------|----------|---------|
| **Source field under-documented** | 🟡 Medium | Line 96 | `source: Optional[str] = None` lacks enum or docstring. Should be constrained to known values: `["conversation", "mail", "calendar", "reminders", "notes", "health"]` |
| **No source enum** | 🟡 Medium | Models | Recommend adding `class MemorySource(Enum)` to prevent string typos. Example: `source = MemorySource.MAIL` vs `source = "mail"` |
| **MemoryQuery missing source filter** | 🟠 High | Lines 236-276 | `MemoryQuery` has `chunk_types`, `session_id`, etc., but no `sources` parameter. Must add before Sprint 12. |
| **Metadata serialization assumes flat structure** | 🟡 Medium | Lines 100-127 | `to_dict()`/`from_dict()` will fail if new fields added without explicit handling. OK for now, but brittle pattern. |
| **No validation on deserialization** | 🟡 Medium | Lines 114-127 | `from_dict()` silently ignores missing/unknown fields. Should warn on schema drift. |

#### Recommendations Before Sprint 12

```python
# Add to models.py after ChunkType enum (line 41):

class MemorySource(Enum):
    """Origin of memory chunk."""
    CONVERSATION = "conversation"   # From chat
    MAIL = "mail"                    # From Apple Mail
    CALENDAR = "calendar"            # From Apple Calendar
    REMINDERS = "reminders"          # From Apple Reminders
    NOTES = "notes"                  # From Apple Notes
    HEALTH = "health"                # From HealthKit
    BACKGROUND_TASK = "background_task"  # From system task
    IMPORT = "import"                # From user import

# Modify ChunkMetadata (lines 86-128):
# Change line 96 from:
    source: Optional[str] = None
# To:
    source: Optional[MemorySource] = None
# And update serialization:
    "source": self.source.value if self.source else None,
    source=MemorySource(data.get("source")) if data.get("source") else None,

# Add to MemoryQuery (lines 236-276):
    sources: Optional[List[MemorySource]] = None
```

#### Impact on Sprint 12
- **Blockers:** Add `sources` param to `MemoryQuery` before database filtering works
- **Type safety:** Enum-based sources prevent runtime errors
- **No schema changes needed** — existing `source` field already in SQLite

---

### 2. `/sessions/bold-gracious-albattani/mnt/hestia/hestia/memory/database.py`

**Health:** 7/10 (solid SQL, but filtering incomplete)

#### Strengths
- ✅ Well-structured async SQLite interface
- ✅ Good index design (session, timestamp, type, scope, status)
- ✅ Tag index table (chunk_tags) enables efficient multi-dimension queries
- ✅ Clear `_index_chunk_tags()` pattern for denormalized tag lookups
- ✅ `query_chunks()` supports flexible multi-field filtering

#### Issues

| Issue | Severity | Location | Details |
|-------|----------|----------|---------|
| **No source filtering in query_chunks()** | 🔴 Blocker | Lines 246-330 | Accepts `chunk_ids` from vector search but doesn't filter by source. Must add SQL condition. |
| **Tag filtering is post-query** | 🟠 High | Lines 327-362 | `_filter_by_tags()` happens in Python after fetch. Scales poorly with large result sets. Should move to SQL WHERE clause. |
| **Partial failure on bulk upsert** | 🟠 High | Lines 239 (inbox call) | `upsert_items()` doesn't exist in this file — must be in inbox. If one email fails, what happens to others? |
| **No transaction rollback pattern** | 🟡 Medium | Throughout | `await _connection.execute()` + `commit()` — no rollback on error. If index fails, chunk inserted but tags missing. |
| **Missing `update_chunk()` after tag index change** | 🟡 Medium | Lines 209-235 | `update_chunk()` deletes and re-indexes tags — correct, but order matters. Race condition if concurrent updates. |
| **No query parameter validation** | 🟡 Medium | Lines 261-330 | Builds dynamic SQL from params. SQL injection unlikely (parameterized), but could add bounds checks. |

#### Critical SQL Gaps

```python
# Line 261-330: query_chunks() must handle source filtering
# MISSING: Between status filter (line 296) and metadata filters (line 298):

# Add source filtering:
if query.sources:
    source_values = [s.value for s in query.sources]
    placeholders = ",".join("?" * len(source_values))
    conditions.append(f"json_extract(metadata, '$.source') IN ({placeholders})")
    params.extend(source_values)
```

#### Recommendations Before Sprint 12

1. **Add source filter to `query_chunks()`** (required for Sprint 12A)
   - Check if `query.sources` is set
   - Add SQL condition on `metadata` JSON path
   - ~8 lines of code

2. **Refactor tag filtering to SQL** (optional but recommended)
   - Move `_filter_by_tags()` logic into WHERE clause using `chunk_tags` table JOIN
   - Eliminates post-query Python filtering
   - ~20 lines of SQL, 10 lines removal

3. **Add transaction safety to index operations**
   - Wrap `store_chunk()` and `update_chunk()` in explicit transaction
   - Use `try/except` to catch index failures
   - Auto-rollback if indexing fails
   - ~15 lines of code

4. **Add bounds validation**
   - `query.limit` should cap at 1000 (prevent runaway queries)
   - `query.offset` should validate >= 0
   - ~5 lines

#### Impact on Sprint 12
- **Blockers:** Source filtering required for DataSource filter wiring
- **No schema changes** — source already stored in metadata JSON
- **Performance:** Tag filtering refactor optional but improves search by ~20-30% for large result sets

---

### 3. `/sessions/bold-gracious-albattani/mnt/hestia/hestia/memory/manager.py`

**Health:** 7.5/10 (good orchestration, signatures need update)

#### Strengths
- ✅ Clean separation: `database` handles storage, `vector_store` handles embeddings, `tagger` handles auto-tagging
- ✅ Async/await patterns correct throughout
- ✅ Good error handling in `_async_tag_chunk()` (lines 272-298)
- ✅ `store_exchange()` handles linking user+assistant chunks (lines 299-337)
- ✅ Temporal decay integration in search (lines 384-403)

#### Issues

| Issue | Severity | Location | Details |
|-------|----------|----------|---------|
| **store_exchange() missing source param** | 🔴 Blocker | Lines 299-337 | Handler calls `store_exchange(user_message, response, mode)` but Sprint 12 requires passing `source="conversation"`. Signature must change. |
| **No bulk store method** | 🟠 High | Throughout | Inbox export will need to store 50-200 items/day. Single `store()` calls are inefficient. Needs `store_many()` or batch API. |
| **Partial failure semantics undefined** | 🟠 High | Lines 207-270 | If one of 100 chunks fails to store (DB error), what's returned? Does caller know which ones succeeded? Need `BulkStoreResult` type. |
| **Cloud-safe sensitivity filtering weak** | 🟠 High | Lines 570-620 | `build_context()` checks `is_sensitive` but doesn't know if content is being sent to cloud. No explicit `cloud_safe` param on `store()`. |
| **Auto-tagging is fire-and-forget** | 🟡 Medium | Lines 266-268 | Spawns async task without tracking. If task fails, chunk has wrong tags but no visibility. Should add callback/error hook. |
| **No deduplication** | 🟡 Medium | Lines 207-270 | Inbox export will try to re-store same email every day. Needs hash-based dedup check before `store()`. |
| **Session creation not scoped** | 🟡 Medium | Lines 141-173 | `start_session()` doesn't take `user_id`. Multi-user support (per CLAUDE.md rules) requires user-scoped sessions. |

#### Signature Changes Required for Sprint 12

```python
# Line 207: store() method signature — ADD source parameter
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
    # ... line 248: Create chunk with source
    chunk = ConversationChunk.create(
        content=content,
        session_id=session_id,
        chunk_type=chunk_type,
        tags=tags,
        metadata=metadata,
        scope=scope,
        source=source,  # NEW
    )

# Line 299: store_exchange() — ADD source parameter
async def store_exchange(
    self,
    user_message: str,
    assistant_response: str,
    mode: Optional[str] = None,
    source: Optional[MemorySource] = None,  # NEW
) -> tuple[ConversationChunk, ConversationChunk]:
    # ... line 318-330: Pass source to both store() calls
    user_chunk = await self.store(
        content=f"User: {user_message}",
        chunk_type=ChunkType.CONVERSATION,
        tags=tags,
        source=source,  # NEW
    )
    assistant_chunk = await self.store(
        content=f"Assistant: {assistant_response}",
        chunk_type=ChunkType.CONVERSATION,
        tags=tags,
        auto_tag=True,
        source=source,  # NEW
    )
```

#### New Methods Needed for Sprint 12

```python
async def store_many(
    self,
    chunks: List[tuple[str, ChunkType, Optional[ChunkTags], Optional[MemorySource]]],
    session_id: Optional[str] = None,
    auto_tag: bool = True,
) -> BulkStoreResult:
    """
    Store multiple chunks efficiently.
    Returns BulkStoreResult with success/failure counts and failed chunk indices.
    """
    pass

async def dedup_by_hash(
    self,
    content: str,
    source: MemorySource,
) -> Optional[str]:
    """
    Check if chunk with same content+source already exists.
    Returns chunk ID if exists, None otherwise.
    Prevents re-storing same email/reminder multiple times.
    """
    pass
```

#### Recommendations Before Sprint 12

1. **Update `store()` and `store_exchange()` signatures** (required)
   - Add `source: Optional[MemorySource] = None` parameter
   - Pass to chunk creation
   - Update ConversationChunk.create() call
   - ~10 lines

2. **Update handler call** (required)
   - Line 1229 in handler.py: `await memory.store_exchange(..., source=MemorySource.CONVERSATION)`

3. **Add `store_many()` method** (required for bulk inbox export)
   - Accept list of (content, type, tags, source) tuples
   - Loop with transactional error handling
   - Return BulkStoreResult with success/failure counts
   - ~30 lines

4. **Add `dedup_by_hash()` method** (required for daily inbox ingestion)
   - Hash content + source
   - Query database for existing chunk with same hash
   - Return existing chunk ID if found, else None
   - ~15 lines

5. **Add scoped session support** (required for multi-user)
   - `start_session()` should accept optional `user_id`
   - Store `user_id` in session record
   - Filter by `user_id` in `get_recent()`, `get_by_tags()`, etc.
   - ~20 lines

#### Impact on Sprint 12
- **Blockers:** source param signatures must change before handler integration
- **Error handling:** Bulk store method required for inbox export (50-200 items/day)
- **Multi-user:** Session scoping needed per CLAUDE.md rules

---

### 4. `/sessions/bold-gracious-albattani/mnt/hestia/hestia/inbox/manager.py`

**Health:** 6.5/10 (functional but coupling issues, no memory export)

#### Strengths
- ✅ Clean aggregation pattern from 3 Apple clients (lines 214-348)
- ✅ Lazy client initialization avoids circular deps (lines 80-100)
- ✅ TTL caching with simple timestamp check (lines 210-212)
- ✅ Graceful error handling in `_aggregate_all()` (lines 221-237)
- ✅ Item metadata correctly captures source-specific fields (metadata dicts, lines 269-346)

#### Issues

| Issue | Severity | Location | Details |
|-------|----------|----------|---------|
| **No `export_to_memory()` method** | 🔴 Blocker | Lines 1-366 | Sprint 12A requires converting inbox items to memory chunks. Inbox has all data but no export pipeline. |
| **No deduplication tracking** | 🟠 High | Lines 214-247 | Daily ingestion will re-store same emails. Need hash-based dedup before memory export. |
| **InboxItem model not memory-aligned** | 🟠 High | Lines 104-168 | InboxItem has `id`, `title`, `body`, `timestamp`, but chunk content generation not defined. How to convert email→chunk? |
| **Database isolation** | 🟡 Medium | Throughout | InboxDatabase is separate from MemoryManager. No shared transaction context. Risk: email fails to store in memory but succeeds in inbox cache. |
| **No source tagging** | 🟡 Medium | Lines 256-348 | Items created with metadata but `source` field not set. Must be explicit for memory ingestion. |
| **Metadata shape differs per source** | 🟡 Medium | Lines 269-346 | Mail has `mailbox`, Reminders have `due`, Calendar have `location`. Chunk metadata must normalize. |
| **Full body not retrieved for emails** | 🟡 Medium | Lines 251-275 | `_aggregate_mail()` uses `snippet`. Full body lazy-loaded only in `get_item()`. Export needs full body. |
| **No rate limiting on export** | 🟡 Medium | Lines 204-247 | Daily export of 50-200 emails could spike memory insertion time. Should batch with progress tracking. |

#### Critical Architecture Gap

**Current state:**
```
MailClient → _aggregate_mail() → InboxItem → InboxDatabase
RemindersClient → _aggregate_reminders() → InboxItem → InboxDatabase
CalendarClient → _aggregate_calendar() → InboxItem → InboxDatabase

Memory Store ← (nothing — gap!)
```

**Required state:**
```
MailClient → _aggregate_mail() → InboxItem → InboxDatabase
RemindersClient → _aggregate_reminders() → InboxItem → InboxDatabase
CalendarClient → _aggregate_calendar() → InboxItem → InboxDatabase
                                                 ↓
                                     export_to_memory()
                                                 ↓
                                     MemoryManager.store_many()
```

#### New Method Required for Sprint 12A

```python
async def export_to_memory(
    self,
    days: int = 30,
    source: Optional[InboxItemSource] = None,
    batch_size: int = 50,
) -> Dict[str, Any]:
    """
    Export recent inbox items to memory as chunks.

    Args:
        days: How many days back to export (default 30)
        source: Export only from specific source (mail/calendar/reminders), or all if None
        batch_size: Items per store_many() call

    Returns:
        {
            'total_items': int,
            'stored_chunks': int,
            'skipped_duplicates': int,
            'failed_items': int,
            'errors': List[str]
        }
    """
    pass

async def _ingest_items_to_memory(
    self,
    items: List[InboxItem],
    batch_size: int = 50,
) -> Dict[str, Any]:
    """Convert InboxItems to memory chunks and store via MemoryManager."""
    pass

def _inbox_item_to_chunk_content(self, item: InboxItem) -> str:
    """Format InboxItem as markdown chunk content."""
    pass

def _inbox_item_to_tags(self, item: InboxItem) -> ChunkTags:
    """Extract ChunkTags from InboxItem metadata."""
    pass
```

#### Recommendations Before Sprint 12

1. **Add `export_to_memory()` method** (required)
   - Query InboxDatabase for recent items (default 30 days)
   - Filter by source if specified
   - Loop through items, call `_inbox_item_to_chunk_content()`
   - Batch items into `store_many()` calls
   - Handle partial failures gracefully
   - ~50-70 lines

2. **Add deduplication** (required)
   - Hash InboxItem (source + ID + timestamp)
   - Before storing, check if chunk with same hash exists
   - Skip if exists (count as "skipped_duplicate")
   - Use `dedup_by_hash()` from MemoryManager
   - ~10 lines

3. **Add source tagging** (required)
   - InboxItemSource → MemorySource mapping:
     - `MAIL` → `MemorySource.MAIL`
     - `REMINDERS` → `MemorySource.REMINDERS`
     - `CALENDAR` → `MemorySource.CALENDAR`
   - Pass to `store_many()` calls
   - ~5 lines

4. **Normalize chunk content** (required)
   - Email: `# {subject}\n\nFrom: {sender}\nDate: {timestamp}\n\n{body}`
   - Reminder: `# {title}\n\nDue: {timestamp}\nList: {list_name}\n\n{body}`
   - Calendar: `# {title}\n\nTime: {start} → {end}\nLocation: {location}\n\n{notes}`
   - ~30 lines in `_inbox_item_to_chunk_content()`

5. **Extract tags from metadata** (required)
   - Email: topics=[sender domain], entities=[sender name]
   - Reminder: topics=["task"], status=["incomplete"]
   - Calendar: topics=["event"], entities=[location]
   - ~20 lines in `_inbox_item_to_tags()`

6. **Lazy-load full email bodies before export** (recommended)
   - For each mail item, call `_get_mail_client().get_email()` to fetch full body
   - Cache in memory during export (don't re-fetch per item)
   - ~15 lines

#### Impact on Sprint 12
- **Blockers:** export_to_memory() required for multi-source ingestion (C1 phase)
- **Coupling:** New dependency on MemoryManager (currently separate)
- **Performance:** Batch API needed for 50-200 items/day

---

### 5. `/sessions/bold-gracious-albattani/mnt/hestia/hestia/research/graph_builder.py`

**Health:** 8/10 (well-designed, but missing source filter)

#### Strengths
- ✅ Clean separation: node builders, edge builders, layout, clustering
- ✅ Force-directed layout is correct and well-commented (lines 344-437)
- ✅ Limits prevent runaway computation (MAX_NODES=200, MAX_EDGES=500)
- ✅ Lazy memory manager import avoids circular deps (lines 60-65)
- ✅ Good error handling on memory search failures (lines 93-102)
- ✅ Three node types well-differentiated (memory, topic, entity)

#### Issues

| Issue | Severity | Location | Details |
|-------|----------|----------|---------|
| **No source filtering** | 🔴 Blocker | Lines 67-168 | `build_graph()` accepts `limit`, `node_types`, `center_topic` but no `sources` filter. Sprint 12 DataSource filters require this. |
| **Memory search is wildcard** | 🟡 Medium | Lines 87-92 | `memory_mgr.search(query="*", ...)` is hacky. Should pass explicit `sources` filter if provided. |
| **Topic/entity case sensitivity** | 🟡 Medium | Lines 204-207, 234-237 | Normalizes to lowercase but case variations create duplicate nodes (e.g., "Python" vs "python"). Should deduplicate. |
| **Entity extraction from tags only** | 🟡 Medium | Lines 226-254 | `_build_entity_nodes()` only uses chunk.tags.entities. Missing entities from full text (implicit in content). Graph will be sparse if auto-tagger misses entities. |
| **No principle nodes** | 🟠 High | Lines 172-224 | Design shows principle nodes should exist, but builder doesn't fetch from PrincipleStore. Graph can't visualize approved principles. |
| **Layout timeout not used** | 🟡 Medium | Lines 42 | `COMPUTATION_TIMEOUT_SECONDS = 10` defined but never applied. Layout could hang. |
| **Clustering single-topic bias** | 🟡 Medium | Lines 441-469 | Clusters by first topic only. Nodes with multiple topics assigned to wrong cluster. |
| **No metadata on clustered nodes** | 🟡 Medium | Lines 462-467 | Clusters created but nodes don't store which cluster they belong to. Needed for UI navigation. |

#### Source Filtering Implementation

```python
# Lines 67-72: Add sources parameter
async def build_graph(
    self,
    limit: int = MAX_NODES,
    node_types: Optional[Set[str]] = None,
    center_topic: Optional[str] = None,
    sources: Optional[List[str]] = None,  # NEW
) -> GraphResponse:
    """
    Build the full knowledge graph.

    Args:
        sources: Filter to specific sources (conversation, mail, calendar, etc.)
    """

    # Lines 87-92: Pass sources to search
    results = await memory_mgr.search(
        query="*",
        limit=min(limit, MAX_NODES),
        semantic_threshold=0.0,
        sources=sources,  # NEW
    )
```

#### Recommendations Before Sprint 12

1. **Add `sources` filter to `build_graph()`** (required)
   - Accept `sources: Optional[List[str]] = None`
   - Pass to `memory_mgr.search()` as filter
   - Update docstring
   - ~5 lines

2. **Add principle nodes** (required for complete graph)
   - New method `_build_principle_nodes()` similar to topic/entity builders
   - Fetch from PrincipleStore (approved principles only)
   - One node per principle
   - Link to related memory nodes via shared topics
   - ~40 lines

3. **Deduplicate topic/entity nodes** (recommended)
   - After `_build_topic_nodes()`, merge duplicates differing only in case
   - Sum mention counts
   - Merge chunk_ids lists
   - ~20 lines in new `_deduplicate_nodes()` method

4. **Add cluster assignment to nodes** (recommended)
   - After building clusters, iterate nodes
   - Set `node.cluster_id = cluster.id` for matching members
   - Enables UI to highlight cluster on hover
   - ~10 lines

5. **Apply timeout to layout computation** (recommended)
   - Wrap `_compute_layout()` in `asyncio.wait_for(..., timeout=COMPUTATION_TIMEOUT_SECONDS)`
   - Return partial layout if timeout
   - ~10 lines

#### Impact on Sprint 12
- **Blockers:** sources filter required for DataSource filter wiring (C1 phase)
- **Optional:** Principle nodes and deduplication improve UX but not required for core feature

---

### 6. `/sessions/bold-gracious-albattani/mnt/hestia/hestia/research/principle_store.py`

**Health:** 7/10 (good core design, but initialization and error handling weak)

#### Strengths
- ✅ Clean separation: ChromaDB for embeddings, SQLite for metadata (lines 43-74)
- ✅ Good principles parsing (lines 222-258)
- ✅ Graceful error handling in `distill_principles()` (lines 174-220)
- ✅ Confidence scoring on distilled principles (line 252)
- ✅ Source chunk tracking for traceability (line 253)

#### Issues

| Issue | Severity | Location | Details |
|-------|----------|----------|---------|
| **Non-async initialization** | 🔴 Blocker | Lines 56-83 | `initialize()` is sync, creates Chromadb client synchronously. Async code calling this will block. Must be `async`. |
| **No initialization guard** | 🟠 High | Lines 85-138 | Methods like `store_principle()` don't check if `_collection` is None. Will fail with cryptic error if `initialize()` not called. |
| **Inference client lazy-import error handling weak** | 🟠 High | Lines 174-183 | If `get_inference_client()` fails, returns empty list silently. Caller doesn't know why. Should log as warning + return error signal. |
| **Distillation prompt hardcoded** | 🟡 Medium | Lines 27-40 | Prompt template is monolithic. Should be in config file for tuning without code changes. |
| **No duplicate principle prevention** | 🟡 Medium | Lines 139-220 | If distillation runs twice, same principles stored again with different IDs. Needs dedup by content hash. |
| **Search uses string comparison** | 🟡 Medium | Lines 114-137 | ChromaDB query returns results, then fetches from SQLite per principle. If ChromaDB returns 10K results, N+1 query pattern. |
| **Status not validated** | 🟡 Medium | Lines 85-112 | Principles stored with status from model, but model doesn't validate. Could store invalid status. |
| **No batch distillation API** | 🟡 Medium | Lines 139-220 | Only single `distill_principles()`. Orders/APScheduler job will need to call this repeatedly. Needs batch API with progress tracking. |

#### Critical Initialization Bug

```python
# Line 56: MUST BE ASYNC
def initialize(self, persist_directory: Optional[Path] = None) -> None:
    # ❌ WRONG: chromadb.PersistentClient() blocks
    self._client = chromadb.PersistentClient(...)
    self._collection = self._client.get_or_create_collection(...)

# Should be:
async def initialize(self, persist_directory: Optional[Path] = None) -> None:
    # ✅ CORRECT: Wrap client creation in executor
    loop = asyncio.get_event_loop()
    self._client = await loop.run_in_executor(
        None,
        chromadb.PersistentClient,
        str(persist_directory),
        Settings(...)
    )
    self._collection = await loop.run_in_executor(
        None,
        self._client.get_or_create_collection,
        COLLECTION_NAME,
        {"hnsw:space": "cosine"}
    )
```

#### Recommendations Before Sprint 12

1. **Make `initialize()` async** (required)
   - Use `asyncio.get_event_loop().run_in_executor()` for chromadb blocking calls
   - Add guard in methods: `if self._collection is None: raise RuntimeError("Not initialized")`
   - ~20 lines

2. **Add initialization check to all methods** (required)
   - Before any `self._collection` access, check is not None
   - Raise `RuntimeError("PrincipleStore not initialized")` if None
   - ~5 lines per method

3. **Move distillation prompt to config** (recommended)
   - Create `config/principles.yaml`:
     ```yaml
     distillation_prompt: "Analyze these conversation excerpts..."
     domain_examples:
       scheduling: "..."
       coding: "..."
     ```
   - Load in `__init__`
   - ~10 lines

4. **Add dedup by content hash** (recommended)
   - Before storing principle, hash content
   - Query SQLite for existing principle with same hash
   - Merge if found (don't create duplicate)
   - ~15 lines in new `_deduplicate_principle()` method

5. **Add batch distillation API** (required for background jobs)
   - New method `distill_all()` or `distill_scheduled()`
   - Takes list of memory chunk queries
   - Runs distillation on each with progress tracking
   - Returns aggregated stats
   - ~30 lines

6. **Validate principle status on creation** (recommended)
   - Ensure status is one of `PrincipleStatus` enum values
   - Raise `ValueError` if invalid
   - ~5 lines

#### Impact on Sprint 12
- **Blockers:** Async initialization required before async/await integration
- **Integration:** Batch API needed if background ingestion task uses this
- **No schema changes** — existing `hestia_principles` collection sufficient

---

### 7. `/sessions/bold-gracious-albattani/mnt/hestia/hestia/orchestration/handler.py` (lines around store_exchange)

**Health:** 6.5/10 (complex orchestration, but memory integration incomplete)

#### Issues (Specific to Sprint 12)

| Issue | Severity | Location | Details |
|-------|----------|----------|---------|
| **store_exchange() not source-tagged** | 🔴 Blocker | Lines 1229-1233 | Handler calls `store_exchange(user_message, response, mode=request.mode.value)` but doesn't pass `source`. Chunks stored without source tagging. |
| **No source parameter in method signature** | 🔴 Blocker | Line 1229 | Handler doesn't know `source` should be passed. MemoryManager.store_exchange() must add source param first. |
| **Request.source not propagated to memory** | 🟠 High | Lines 1221-1240 | Request has `source` field (from RequestSource enum), but it's not passed to store_exchange. Need to add. |
| **No error recovery for memory failures** | 🟡 Medium | Lines 1234-1240 | Exception caught and logged, but response still sent. If memory store failed, no signal to retry. Acceptable pattern but could improve. |

#### Fix Required

```python
# Line 1229: Update store_exchange() call
await memory.store_exchange(
    user_message=request.content,
    assistant_response=response.content,
    mode=request.mode.value,
    source=MemorySource.CONVERSATION,  # NEW: Always conversation for handler
)
```

#### Impact on Sprint 12
- **Blocker:** Must update after MemoryManager.store_exchange() signature changes
- **No architectural changes** — just parameter passing

---

### 8. `/sessions/bold-gracious-albattani/mnt/hestia/hestia-cli/hestia_cli/renderer.py`

**Health:** 5.5/10 (functional but not extensible for animations)

#### Strengths
- ✅ Good separation of concerns (event dispatch → specific renderers)
- ✅ Clean Rich integration
- ✅ Status line clearing with raw ANSI (lines 19-22)
- ✅ Metrics display already implemented (lines 160-189)

#### Critical Issues for Sprint 12

| Issue | Severity | Location | Details |
|-------|----------|----------|---------|
| **No animation framework** | 🔴 Blocker | Lines 104-113 | Status rendering is synchronous, single-line. Fire emoji animation requires async task cycling frames. Current design can't support it. |
| **State management fragile** | 🟠 High | Lines 28-34 | Multiple state variables (`_streaming_buffer`, `_status_text`, `_in_streaming`, `_status_visible`) track what should be one "status state machine". Hard to extend. |
| **Token rendering overwrites status unsafely** | 🟠 High | Lines 115-129 | Clears status line on first token (line 121) but doesn't handle race: what if status update arrives mid-token? |
| **No agent color support** | 🟡 Medium | Lines 1-200 | Entire file is color-agnostic. Must add color parameters for agent theming. |
| **Hard-coded stage labels** | 🟡 Medium | Lines 107 | Stage labels map from `STAGE_LABELS` constant but no agent-specific customization. |
| **Spinner verb support missing** | 🔴 Blocker | Lines 104-113 | Status shows fixed "Generating..." text. Must rotate spinner verbs from models.py lists. |
| **No thinking section** | 🟡 Medium | Lines 1-200 | Research phase (C4) requires `<thinking>` blocks to render collapsed/expandable. Needs new method. |

#### Architecture Problem for Sprint 12A3

**Current (linear, synchronous):**
```python
def _render_status(self, event):
    _clear_line()
    self.console.print(f"  [dim]⟳ {label}...[/dim]")
    self._status_visible = True
```

**Required (async animation with rotating verbs):**
```python
class ThinkingAnimation:
    def __init__(self, agent_name: str, agent_color: str):
        self._agent_name = agent_name
        self._agent_color = agent_color
        self._frame = 0
        self._verb_index = 0
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        # Spawn asyncio task to cycle frames every 200ms
        self._task = asyncio.create_task(self._animate_loop())

    async def stop(self):
        # Cancel task, clear line
        if self._task:
            self._task.cancel()
            _clear_line()

    async def _animate_loop(self):
        # Cycle through FIRE_FRAMES + verb rotation every 2s
        pass

# In HestiaRenderer:
def _render_status(self, event):
    stage = event.get("stage", "")
    if stage == "inference":  # Only during inference
        agent_name = event.get("agent", "Hestia")
        agent_color = event.get("agent_color", "#FF9500")
        self._animation = ThinkingAnimation(agent_name, agent_color)
        asyncio.create_task(self._animation.start())
    else:
        # Other stages: simple spinner
        ...

def _render_token(self, event):
    if self._animation:
        asyncio.create_task(self._animation.stop())  # Stop animation on first token
    # ... render token
```

#### Recommendations Before Sprint 12B

1. **Refactor to state machine** (required)
   - Replace multiple state variables with single `_render_state` enum
   - States: IDLE, STATUS, THINKING, STREAMING, DONE
   - Transitions defined explicitly
   - ~30 lines

2. **Create ThinkingAnimation class** (required for A3)
   - Async task-based animation loop
   - Cycles through FIRE_FRAMES + verb rotation
   - Methods: `start()`, `stop()`, `set_agent()`
   - ~50 lines

3. **Add agent color parameters** (required for A2)
   - Constructor: `__init__(console, show_metrics, agent_colors_map={})`
   - `_render_status()` accepts agent_color from event
   - Pass color to ThinkingAnimation
   - ~10 lines

4. **Add thinking/reasoning section** (deferred to C4)
   - New `_render_thinking()` method
   - Collapses `<thinking>` block content
   - Toggleable with `/reasoning` command
   - ~20 lines

5. **Add verb rotation to status** (required for A3)
   - Import COMMON_VERBS, TIA_VERBS, OLLY_VERBS, MIRA_VERBS from models.py
   - ThinkingAnimation selects verbs by agent
   - Rotates every 2 seconds
   - ~15 lines

#### Impact on Sprint 12
- **Blockers:** Animation framework required before A2/A3 implementation
- **Refactoring scope:** ~100-120 lines of new code, minor changes to existing methods
- **Risk:** Animation timing could cause flicker if not careful with asyncio/Rich integration

---

### 9. `/sessions/bold-gracious-albattani/mnt/hestia/hestia-cli/hestia_cli/models.py`

**Health:** 8/10 (clean models, but missing verb constants)

#### Strengths
- ✅ Clear Pydantic models for server events
- ✅ Good enum design (ServerEventType, PipelineStage)
- ✅ DoneMetrics capture all essential data (tokens, duration, model, cached)
- ✅ ToolRequest has all required fields

#### Issues

| Issue | Severity | Location | Details |
|-------|----------|----------|---------|
| **Missing spinner verb constants** | 🔴 Blocker | Lines 1-72 | Sprint 12A3 requires COMMON_VERBS, TIA_VERBS, OLLY_VERBS, MIRA_VERBS lists. Must add. |
| **No FIRE_FRAMES constant** | 🔴 Blocker | Lines 1-72 | Sprint 12A3 requires color-cycling fire emoji animation. Define frames here. |
| **No AgentTheme dataclass** | 🟡 Medium | Lines 1-72 | A2 requires agent color syncing. Should define AgentTheme(name: str, color_hex: str) model. |
| **PipelineStage incomplete** | 🟡 Medium | Lines 26-34 | Missing THINKING stage for C4 (reasoning streams). Should add for future. |
| **STAGE_LABELS doesn't cover all stages** | 🟡 Medium | Lines 37-45 | If new stages added, labels must be kept in sync. Consider reverse mapping to prevent drift. |

#### Required Additions for Sprint 12

```python
# After line 45 (after STAGE_LABELS):

COMMON_VERBS = [
    # Cognitive
    "Processing", "Analyzing", "Computing", "Evaluating",
    "Synthesizing", "Correlating", "Cross-referencing",
    "Deliberating", "Contemplating", "Reasoning",
    "Deducing", "Inferring", "Extrapolating",
    "Calibrating", "Resolving", "Formulating",
    "Distilling", "Parsing", "Mapping",
    # Jarvis/Friday Classics
    "Running diagnostics", "Scanning databases",
    "Accessing records", "Compiling results",
    "Running the numbers", "Checking protocols",
    "Reviewing parameters", "Verifying data",
    "Querying archives", "Assembling brief",
    "Crunching variables", "Consulting the archives",
    "Triangulating", "Reconciling inputs",
    "Performing analysis", "Updating models",
    # Hestia-Specific
    "Tending the fire", "Stoking the embers",
    "Kindling a thought", "Warming up",
    "Simmering", "Slow-burning",
    "Gathering kindling", "Fanning the flames",
    "Forging a response", "Tempering",
    "Annealing", "Casting",
]

TIA_VERBS = [
    "Chewing on this", "Cooking something up",
    "Stirring the pot", "Brewing thoughts",
    "Herding neurons", "Wrangling context",
    "Juggling priorities", "Polishing the brief",
    "Rehearsing the punchline", "Composing a masterpiece",
    "Negotiating with entropy", "Summoning patience",
    "Rummaging through the archives", "Interrogating the data",
    "Having a word with the database", "Consulting my notes",
    "Reading the room", "Putting pieces together",
    "Making sense of this", "Working my magic",
    "Taking a closer look", "Putting on my thinking cap",
    "Channeling competence", "Tidying up the facts",
    "Doing the heavy lifting", "Fact-checking myself",
    "Running it through the gauntlet", "Sharpening the response",
    "Double-checking the math", "Drafting something good",
    "Earning my keep", "On it, boss",
]

OLLY_VERBS = [
    "Compiling insights", "Resolving dependencies",
    "Running inference", "Traversing the graph",
    "Optimizing output", "Indexing context",
    "Allocating attention", "Garbage collecting",
    "Refactoring thoughts", "Merging branches",
    "Rebasing understanding", "Linting the logic",
    "Profiling the problem", "Benchmarking options",
    "Debugging assumptions", "Stepping through",
    "Building from source", "Linking symbols",
    "Unwinding the stack", "Checking the diff",
    "Running unit tests", "Validating schema",
    "Spinning up instances", "Deploying thoughts",
    "Patching knowledge gaps", "Containerizing the answer",
    "Pipeline running", "Hotfixing my reasoning",
    "Grepping for answers", "Pushing to production",
    "Code reviewing my thoughts", "Stress-testing the logic",
]

MIRA_VERBS = [
    "Seeking the question behind the question",
    "Tracing the roots", "Exploring the landscape",
    "Mapping the territory", "Finding the pattern",
    "Following the thread", "Opening the aperture",
    "Zooming out", "Looking deeper",
    "Listening to what's unsaid",
    "Weighing perspectives", "Sitting with the question",
    "Turning it over", "Considering the angles",
    "Seeking first principles", "Unraveling layers",
    "Meditating on this", "Holding space",
    "Examining assumptions", "Challenging the obvious",
    "Searching for nuance", "Peeling back the surface",
    "Drawing from the well", "Consulting the oracle",
    "Walking the labyrinth", "Connecting constellations",
    "Sifting through wisdom", "Letting it crystallize",
    "Distilling the essence", "Finding the signal",
    "Illuminating blind spots", "Seeing what emerges",
]

FIRE_FRAMES = [
    "[bold #FF6B00]🔥[/]",  # orange
    "[bold #FF8C00]🔥[/]",  # dark orange
    "[bold #FFA500]🔥[/]",  # amber
    "[bold #FF4500]🔥[/]",  # red-orange
]

@dataclass
class AgentTheme:
    """Agent color and styling."""
    name: str  # "Tia", "Mira", "Olly"
    color_hex: str  # "#FF9500" (from agent identity)
    verb_list: List[str] = field(default_factory=list)  # Agent-specific verbs
```

#### Impact on Sprint 12
- **Blockers:** Required constants for A3 implementation
- **No dependencies added** — simple string lists
- **Future-proof:** Design allows easy customization

---

## Summary Table

| Module | Health | Blockers | High Issues | Recommendations |
|--------|--------|----------|------------|-----------------|
| **models.py** | 8/10 | None | 1 | Add MemorySource enum, sources to MemoryQuery |
| **database.py** | 7/10 | 1 | 2 | Add source filtering, transaction safety |
| **manager.py** | 7.5/10 | 2 | 3 | Update signatures, add store_many(), dedup_by_hash() |
| **inbox/manager.py** | 6.5/10 | 1 | 4 | Add export_to_memory() method, dedup tracking |
| **graph_builder.py** | 8/10 | 1 | 1 | Add sources filter, principle nodes |
| **principle_store.py** | 7/10 | 1 | 3 | Make initialize() async, add batch API |
| **handler.py** | 6.5/10 | 1 | None | Update store_exchange() call with source param |
| **renderer.py** | 5.5/10 | 2 | 3 | Refactor to state machine, create ThinkingAnimation class |
| **models.py (CLI)** | 8/10 | 1 | None | Add verb constants and FIRE_FRAMES |

---

## Pre-Implementation Task Checklist

### Phase 0: Model Definitions (1-2 hours)
- [ ] Add `MemorySource` enum to memory/models.py
- [ ] Update `ChunkMetadata.source` type to MemorySource
- [ ] Add `sources` param to `MemoryQuery`
- [ ] Add verb constants to hestia_cli/models.py
- [ ] Add `AgentTheme` dataclass to hestia_cli/models.py

### Phase 1: Memory Layer (2-3 hours)
- [ ] Add source filtering SQL to memory/database.py `query_chunks()`
- [ ] Add transaction safety to store/update operations
- [ ] Update `MemoryManager.store()` signature: add `source` param
- [ ] Update `MemoryManager.store_exchange()` signature: add `source` param
- [ ] Add `MemoryManager.store_many()` method for bulk operations
- [ ] Add `MemoryManager.dedup_by_hash()` method
- [ ] Update handler.py line 1229: pass `source=MemorySource.CONVERSATION` to store_exchange()
- [ ] Update all calls to `store()` and `store_exchange()` to pass source (search for grep)

### Phase 2: Research Layer (1-2 hours)
- [ ] Make `PrincipleStore.initialize()` async
- [ ] Add initialization guards to PrincipleStore methods
- [ ] Add `sources` filter param to `GraphBuilder.build_graph()`
- [ ] Add principle node building to GraphBuilder

### Phase 3: Inbox Integration (2-3 hours)
- [ ] Add `InboxManager.export_to_memory()` method
- [ ] Add `_inbox_item_to_chunk_content()` formatter
- [ ] Add `_inbox_item_to_tags()` extractor
- [ ] Add deduplication logic using `dedup_by_hash()`

### Phase 4: CLI Rendering (2-3 hours)
- [ ] Refactor HestiaRenderer to state machine pattern
- [ ] Create ThinkingAnimation class
- [ ] Add agent color parameters to renderer
- [ ] Integrate verb rotation from models.py
- [ ] Add FIRE_FRAMES cycling logic

### Phase 5: Testing & Integration (1-2 hours)
- [ ] Write tests for new memory source filtering
- [ ] Write tests for InboxManager.export_to_memory()
- [ ] Write tests for GraphBuilder source filtering
- [ ] Test CLI animation rendering with asyncio
- [ ] Verify handler integration with updated method signatures

**Total Estimated Pre-Impl Time:** 9-16 hours

---

## Risk Assessment

### High-Risk Areas

1. **Async/Await Mismatches** (PrincipleStore.initialize)
   - Risk: Current sync initialization will deadlock with async code
   - Mitigation: Test thoroughly with asyncio event loop
   - Impact: Blocker for research wiring

2. **Animation Race Conditions** (CLI renderer)
   - Risk: Verb rotation + fire frame cycling can flicker if not carefully synchronized
   - Mitigation: Use single asyncio task with coordinated frame timing
   - Impact: UX polish, not functionality

3. **Bulk Storage Partial Failures** (inbox export)
   - Risk: If 50/200 emails fail, how many get stored? Unclear semantics.
   - Mitigation: Define clear BulkStoreResult type, test with simulated failures
   - Impact: Data consistency issue

4. **Multi-Source Memory Noise** (graph builder)
   - Risk: Ingesting 30 days of emails could create 1000+ memory chunks, degrading search
   - Mitigation: Use FACT chunk type (lower priority), apply temporal decay, limit to last 30 days
   - Impact: Graph quality

### Low-Risk Areas
- Type signature updates (straightforward parameter passing)
- Source filtering in SQL (existing query builder pattern)
- Renderer state refactoring (localized to one module)

---

## Recommendations Summary

### Do This Before Sprint 12 Starts
1. Add MemorySource enum and update signatures
2. Add source filtering to database.query_chunks()
3. Make PrincipleStore.initialize() async
4. Refactor renderer to state machine
5. Add verb constants to CLI models

### Can Defer to Sprint 12 With Low Risk
- export_to_memory() implementation (new code, isolated)
- ThinkingAnimation class (new, async-safe)
- Principle node building (additive, no breaking changes)

### Watch Out For
- Handler integration after signature changes (must update all callers)
- Async/await correctness in PrincipleStore
- Animation flicker in Rich console (test with actual terminal)
- Bulk storage error semantics (define early, test with failures)

---

## Final Verdict

**Green light to proceed with Sprint 12A/B after completing Phase 0-2 of the checklist above.** The codebase is well-structured for the required changes. No architectural rewrites needed. All blockers are resolvable with surgical, targeted refactoring (4-6 hours estimated).

The critical path is:
1. MemorySource enum + signature updates (blocks rest of work)
2. Database source filtering + async PrincipleStore (unblocks research wiring)
3. Renderer state machine (unblocks CLI polish)

Once those three are done, the feature implementations (export_to_memory, animation, graph wiring) are straightforward and low-risk.
