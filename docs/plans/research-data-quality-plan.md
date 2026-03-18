# Research Tab Data Quality Plan

**Date:** 2026-03-18
**Status:** DRAFT — awaiting review
**Scope:** 5 interconnected issues with Research tab data quality, graph accuracy, and Apple data ingestion
**Depends on:** Sprint 20A (Quality Framework), Sprint 20B (Source Infrastructure)
**Estimated effort:** ~18–24h across Issues 1–5

---

## Table of Contents

1. [Current State Analysis](#current-state-analysis)
2. [Issue 1: Bracket Prefix Stripping Incomplete](#issue-1-bracket-prefix-stripping-incomplete)
3. [Issue 2: Insight Misclassification](#issue-2-insight-misclassification)
4. [Issue 3: Graph Data Source Filters Don't Work](#issue-3-graph-data-source-filters-dont-work)
5. [Issue 4: Daily Apple Ingestion Status](#issue-4-daily-apple-ingestion-status)
6. [Issue 5: Historical Apple Data Backfill](#issue-5-historical-apple-data-backfill)
7. [ChunkType Taxonomy Review](#chunktype-taxonomy-review)
8. [Graph Legend Mapping & Tooltip Definitions](#graph-legend-mapping--tooltip-definitions)
9. [Implementation Order](#implementation-order)
10. [Gemini Second-Opinion Prompt](#gemini-second-opinion-prompt)

---

## Current State Analysis

### Memory Chunk Inventory

**Validation queries** (run against SQLite via `hestia-cli` or direct DB):

```sql
-- Total chunk count by type
SELECT chunk_type, COUNT(*) as count
FROM memory_chunks
WHERE status = 'active'
GROUP BY chunk_type
ORDER BY count DESC;

-- Total chunk count by source
SELECT json_extract(metadata, '$.source') as source, COUNT(*) as count
FROM memory_chunks
WHERE status = 'active'
GROUP BY source
ORDER BY count DESC;

-- INSIGHT chunks with "claude_history" source (the misclassification cohort)
SELECT COUNT(*)
FROM memory_chunks
WHERE chunk_type = 'insight'
  AND json_extract(metadata, '$.source') = 'claude_history'
  AND status = 'active';

-- Sample of low-quality insights (procedural content)
SELECT content, json_extract(metadata, '$.confidence') as importance
FROM memory_chunks
WHERE chunk_type = 'insight'
  AND json_extract(metadata, '$.source') = 'claude_history'
  AND status = 'active'
ORDER BY RANDOM()
LIMIT 20;

-- Source dedup table stats
SELECT source, COUNT(*) FROM source_dedup GROUP BY source;

-- Ingestion log history
SELECT * FROM source_ingestion_log ORDER BY started_at DESC LIMIT 10;
```

### Key Numbers (estimated, pending query validation)
- ~1,008 total memory chunks (from earlier session data)
- ~988 from Claude history import (classified as INSIGHT)
- ~20 from live chat sessions
- 0 from Apple ecosystem (mail, calendar, reminders, notes)
- 0 from health data

### Architecture References

| Component | File | Purpose |
|-----------|------|---------|
| ChunkType enum | `hestia/memory/models.py:32–41` | 8 types: CONVERSATION, FACT, PREFERENCE, DECISION, ACTION_ITEM, RESEARCH, SYSTEM, INSIGHT |
| MemorySource enum | `hestia/memory/models.py` | conversation, mail, calendar, reminders, notes, health, claude_history, openai_history |
| DIKW durability | `hestia/research/models.py:63–68` | TemporalType: EPHEMERAL(0), DYNAMIC(1), STATIC(2), ATEMPORAL(3) |
| SourceCategory | `hestia/research/models.py:71–80` | conversation, imported, web, tool, user_statement, apple_ecosystem, health, voice |
| Fact extractor | `hestia/research/fact_extractor.py:27–171` | 3-phase: Entity ID → Significance Filter → PRISM Triple |
| Graph builder | `hestia/research/graph_builder.py:84–330` | Fact-based graph with durability/source filtering |
| InboxMemoryBridge | `hestia/inbox/bridge.py:79–328` | Apple data → memory chunks with dedup |
| source_dedup table | `hestia/memory/database.py:94–104` | UNIQUE(source, source_id) prevents re-ingestion |
| Learning scheduler | `hestia/learning/scheduler.py` | 6 loops: meta-monitor, memory health, triggers, consolidation, pruning, crystallization |

---

## Issue 1: Bracket Prefix Stripping Incomplete

### Current State

**`strippingBracketPrefixes()`** is defined in `NodeDetailPopover.swift:336–345`:

```swift
private func strippingBracketPrefixes(_ text: String) -> String {
    var result = text
    let pattern = #"^\[[^\]]+\]:\s*"#
    while let range = result.range(of: pattern, options: .regularExpression) {
        result.removeSubrange(range)
    }
    return result.isEmpty ? text : result
}
```

**Pattern:** Matches `[anything]:` at the start of the string, repeatedly. Strips prefixes like:
- `[IMPORTED CLAUDE HISTORY — Session Name]:`
- `[CLAUDE PROJECT — hestia]:`
- `[User]:`
- `[Assistant]:`

**Used in:** `NodeDetailPopover.swift` lines 111 and 230 (content display, connected nodes list).

**NOT used in:** `MemoryChunkRow.swift:33–36` — displays raw `chunk.content` with no cleaning.

### Proposed Solution

**Move the function to a shared utility.** Two options:

**Option A (recommended): Swift extension on String**
Create `HestiaApp/macOS/DesignSystem/StringExtensions.swift`:
```swift
extension String {
    func strippingBracketPrefixes() -> String { ... }
}
```
Then `NodeDetailPopover` and `MemoryChunkRow` both call `chunk.content.strippingBracketPrefixes()`.

**Option B: Backend stripping on ingest**
Add the regex strip to `InboxMemoryBridge._clean_content()` and to the Claude history import script so the prefix never gets stored. Downside: doesn't fix existing data without a migration.

**Recommendation:** Do both — Option A for immediate display fix, Option B for future ingest hygiene. Run a one-time SQL migration to strip prefixes from existing chunks:

```sql
-- Preview: which chunks have bracket prefixes?
SELECT id, substr(content, 1, 80) FROM memory_chunks
WHERE content LIKE '[%]:%' AND status = 'active';

-- Migrate (backup first!):
UPDATE memory_chunks
SET content = ltrim(
    replace(replace(content,
        -- This needs a regex-capable approach; SQLite can't do regex UPDATE natively.
        -- Use a Python migration script instead.
    ))
WHERE content LIKE '[%]:%';
```

Better approach: Python migration script that loads chunks, applies the regex, and updates. ~30 lines.

### Risks
- **False stripping:** Content that legitimately starts with `[bracketed text]:` (e.g., citations, code references). The `while` loop is aggressive — it strips ALL leading bracket prefixes. Mitigation: only strip known prefixes (`IMPORTED CLAUDE HISTORY`, `CLAUDE PROJECT`, `CLAUDE REASONING`, `User`, `Assistant`).
- **Empty content after stripping:** The existing code falls back to original text if result is empty. Good.

### Effort: ~1h (utility extraction + MemoryChunkRow integration + migration script)

---

## Issue 2: Insight Misclassification

### Current State

988 Claude history chunks were bulk-imported with `chunk_type = "insight"` and `metadata.source = "claude_history"`. The import script classified everything uniformly because it couldn't distinguish insight-quality content from procedural chat.

Sprint 20A built the DIKW quality framework with:
- 4-tier durability scoring (Ephemeral → Contextual → Durable → Principled)
- 3-phase extraction pipeline (Entity ID → Significance Filter → PRISM Triple)
- Ephemeral fact filter (durability=0 excluded from graph)
- Retroactive crystallization loop (weekly promotion of clustered ephemerals)

**The quality framework was never run retroactively on existing data.** It only applies to new facts extracted going forward.

### Diagnostic Queries

```sql
-- How many chunks are INSIGHT type?
SELECT COUNT(*) FROM memory_chunks
WHERE chunk_type = 'insight' AND status = 'active';

-- How many are from Claude history specifically?
SELECT COUNT(*) FROM memory_chunks
WHERE chunk_type = 'insight'
  AND json_extract(metadata, '$.source') = 'claude_history'
  AND status = 'active';

-- Sample 20 for manual quality review
SELECT id, substr(content, 1, 200), json_extract(metadata, '$.confidence') as importance
FROM memory_chunks
WHERE chunk_type = 'insight'
  AND json_extract(metadata, '$.source') = 'claude_history'
  AND status = 'active'
ORDER BY RANDOM()
LIMIT 20;

-- Distribution of importance scores in insights
SELECT
    CASE
        WHEN json_extract(metadata, '$.confidence') >= 0.7 THEN 'high (>=0.7)'
        WHEN json_extract(metadata, '$.confidence') >= 0.4 THEN 'medium (0.4-0.7)'
        ELSE 'low (<0.4)'
    END as tier,
    COUNT(*) as count
FROM memory_chunks
WHERE chunk_type = 'insight' AND status = 'active'
GROUP BY tier;
```

### Proposed Reclassification Strategy

**Phase 1: Automated triage (no LLM required)**

Use heuristic filters to identify low-quality chunks:

```python
LOW_QUALITY_PATTERNS = [
    r"^(The user wants|Great!|Sure|OK|Let me|I'll|I've|Here's|Done)",
    r"^(Looking at|Checking|Running|Starting|Updating)",
    r"ExecutionStatus|models\.py|import |def |class |async def",
    r"^.{0,30}$",  # Very short content (<30 chars)
]
```

Chunks matching these patterns → reclassify from `INSIGHT` to `CONVERSATION`.

**Estimated impact:** ~40-60% of the 988 chunks will match (procedural assistant responses, status updates, code references). Leaves ~400-600 chunks as genuine insights.

**Phase 2: LLM quality scoring on survivors**

For the remaining chunks that passed heuristic filtering, run the DIKW durability scorer:
- Ephemeral (0) → downgrade to CONVERSATION
- Dynamic (1) → keep as INSIGHT, tag as contextual
- Static (2) or Atemporal (3) → confirmed INSIGHT, high-value

**Phase 3: Fact re-extraction from high-quality survivors**

Run the 3-phase extraction pipeline on chunks scoring Durable+ (durability ≥ 2). This will:
- Extract entities and relationships
- Create proper bi-temporal facts in the research graph
- Apply significance filtering (only CORE ACTORS)

**Throttling:** Process in batches of 50 chunks, with 2-second delays between batches. Total LLM inference: ~400 chunks × ~3 calls each = ~1,200 inference calls. At ~2s/call local = ~40 minutes. Acceptable.

### Risk: Data Loss

**No chunks are deleted.** Reclassification only changes `chunk_type` from `insight` to `conversation`. The content remains searchable, retrievable, and visible in the Memory Browser. The only behavioral change:
- Downgraded chunks won't contribute to the graph with "insight" node type
- Their importance scores may decrease (type bonus removed from importance formula)
- They remain available for future re-extraction if needed

**Mitigation:** Before running, snapshot the current chunk type distribution. After running, verify no chunks were lost (total count should be identical, only type distribution changes).

### Effort: ~4h (heuristic filter script + LLM quality scoring + fact re-extraction run + validation)

---

## Issue 3: Graph Data Source Filters Don't Work

### Current State

**Frontend filter pills** (ResearchView.swift DataSource enum):
- 6 pills: Chat, Email, Notes, Calendar, Reminders, Health
- Filter by `metadata.source` value on memory chunks
- Colors are bright and visually compete with the graph legend below

**The problem:** 99%+ of graph data has source `"claude_history"` or `"conversation"`. The filter pills map to `"conversation"`, `"mail"`, `"notes"`, `"calendar"`, `"reminders"`, `"health"` — but there's no pill for `"claude_history"` or `"imported"`.

This means:
- "Chat" pill maps to `"conversation"` → shows only live chat memories (~20 chunks)
- All other pills → show nothing (no Apple data has been ingested)
- 988 imported chunks are **unfiltered** — always visible regardless of pill selection

**Additionally:** The GraphControlPanel (lines 297–341) has a **separate** set of source category filters (SourceCategory enum: conversation, imported, web, tool, user_statement, apple_ecosystem, health, voice). These are overlapping but non-identical to the DataSource pills, creating two filtering systems that don't communicate.

### Diagnostic Queries

```sql
-- What source values actually exist in memory?
SELECT json_extract(metadata, '$.source') as source, COUNT(*)
FROM memory_chunks WHERE status = 'active'
GROUP BY source;

-- What source_category values exist in facts?
SELECT source_category, COUNT(*) FROM facts
WHERE status = 'active'
GROUP BY source_category;
```

### Proposed Solution

**Consolidate to a single filter system.** The GraphControlPanel's SourceCategory filters are the correct abstraction (they map to the research models). The DataSource pills in the header bar are redundant and confusing.

**Step 1: Remove the DataSource pills from the Research view header bar.** The GraphControlPanel already provides source category filtering with the correct values.

**Step 2: Ensure "imported" is a visible filter.** Currently, 988 chunks are `source = "claude_history"` which maps to `SourceCategory.IMPORTED`. The "Imported" pill in GraphControlPanel should filter these correctly. Verify the mapping is wired.

**Step 3: Visual redesign of the remaining GraphControlPanel source pills.**
- **Unselected:** Monochrome (MacColors.textSecondary with no background)
- **Selected:** MacColors.amberAccent tint (consistent with other active states)
- Remove per-source unique colors — they compete with the legend

**Step 4: After Apple backfill (Issue 5),** the apple_ecosystem, health, and other filters will naturally populate. No frontend changes needed.

### Interaction with Legend

The graph legend shows **node types** (memory, topic, entity, principle, community, episode, fact). Source filters are orthogonal — they control **which data feeds the graph**, not how nodes look. This is already correct architecturally; the confusion was having two filter systems in different locations.

### Risks
- **Removing DataSource pills removes a familiar UI element.** Mitigation: the GraphControlPanel provides strictly more filtering power. Users who used the pills will find equivalent controls there.
- **"Imported" is a technical term.** Consider renaming to "Claude History" in the UI while keeping `IMPORTED` as the enum value.

### Effort: ~2h (remove DataSource pills, verify GraphControlPanel wiring, monochrome redesign)

---

## Issue 4: Daily Apple Ingestion Status

### Current State

**InboxMemoryBridge** (`hestia/inbox/bridge.py:79–328`) is a well-built ingestion pipeline:
- Supports: mail, calendar, reminders (via InboxManager), notes (via AppleCacheManager)
- Deduplication: `source_dedup` table with `UNIQUE(source, source_id)` prevents re-ingestion
- Content preprocessing: email signature stripping, HTML cleanup, prompt injection detection, 2000-char chunk limit
- Batch tracking: `source_ingestion_log` table records each run

**However: There is NO scheduled task.** The `LearningScheduler` (which runs 6 async loops: meta-monitor, memory health, triggers, consolidation, pruning, crystallization) does NOT include InboxMemoryBridge.

Ingestion only happens when someone calls the `/v1/memory/ingest` API endpoint (defined in `hestia/api/routes/memory.py:617`).

### Diagnostic Steps

```bash
# Check if the ingest endpoint has ever been called
sqlite3 data/memory.db "SELECT * FROM source_ingestion_log ORDER BY started_at DESC LIMIT 10;"

# Check source_dedup for any Apple data
sqlite3 data/memory.db "SELECT source, COUNT(*) FROM source_dedup GROUP BY source;"

# Check server logs for ingest calls
grep -c "memory/ingest" logs/hestia-*.log
```

### Proposed Solution

**Add InboxMemoryBridge to the LearningScheduler as a daily task.**

In `hestia/learning/scheduler.py`, add a 7th loop:

```python
async def _apple_ingestion_loop(self):
    """Daily Apple ecosystem data ingestion (3 AM)."""
    while self._running:
        await self._wait_until_hour(3)  # 3 AM
        try:
            from hestia.inbox import get_inbox_manager
            from hestia.inbox.bridge import InboxMemoryBridge

            inbox_mgr = await get_inbox_manager()
            memory_mgr = self._memory_manager
            bridge = InboxMemoryBridge(
                inbox_manager=inbox_mgr,
                memory_manager=memory_mgr,
            )
            result = await bridge.ingest_all()
            logger.info("apple_ingestion_complete", extra={"result": result})
        except Exception as e:
            logger.error("apple_ingestion_failed", extra={"error": type(e).__name__})
        await asyncio.sleep(86400)  # 24h
```

**Verification after implementation:**
1. Check `source_ingestion_log` shows daily entries
2. Check `source_dedup` table grows daily
3. Check memory chunk count by source shows non-zero apple_ecosystem values

### Why Existing Apple Data Might Not Appear in the Graph

Even if ingestion starts working, chunks won't appear in the **fact-based graph** until fact extraction runs on them. The pipeline is:

```
Apple data → InboxMemoryBridge → memory_chunks (ChromaDB + SQLite)
                                        ↓
                              Fact extraction (LLM) → facts table → graph
```

Memory chunks are always searchable in the Memory Browser. But graph nodes require fact extraction. The bridge stores chunks; it does NOT extract facts. This is a design gap — see Issue 5 for the proposed pipeline.

### Risks
- **Mac Mini Swift CLI tools must be working** for calendar/reminders/notes access. The `hestia-cli-tools/` Swift CLIs handle TCC permissions. Verify they're deployed and functional.
- **Email access requires Mail.app** to be running (or cached data). Mac Mini may not have active mail sessions.

### Effort: ~2h (add scheduler loop + verify Mac Mini CLI tools + test first ingestion)

---

## Issue 5: Historical Apple Data Backfill

### Current State

Hestia has access to Andrew's Apple ecosystem data via:
- **Email:** Mail.app via AppleScript
- **Calendar:** EventKit (direct framework access)
- **Reminders:** EventKit (direct framework access)
- **Notes:** `hestia-cli-tools/notes` Swift CLI (AppleScript bridge)
- **HealthKit:** Direct framework access (28 metric types)

**No historical backfill has ever been performed.** All Apple data paths are incremental-only (new items since last sync).

### Volume Estimation

| Source | 6-Month Estimate | Quality Mix |
|--------|-----------------|-------------|
| Email | 2,000–5,000 messages | ~70% noise (newsletters, receipts, automated), ~30% actionable |
| Calendar | 300–600 events | ~50% routine (standup, lunch), ~50% meaningful |
| Reminders | 100–300 items | ~80% actionable, low noise |
| Notes | 50–200 notes | ~90% meaningful (notes are intentional), highest quality |
| HealthKit | ~180 daily summaries | Numeric data, not chunk-worthy — already handled by health module |

**Total estimated chunks after quality gating:** 1,500–3,000

### Quality Gating Strategy

Each source needs different quality filters to prevent flooding:

**Email:**
- Skip if sender is in a configurable `SKIP_SENDERS` list (newsletters, noreply@, automated)
- Skip if subject matches noise patterns: `re: re: re:`, meeting invites, automated notifications
- Skip if body < 50 chars after signature stripping
- Keep: personal correspondence, project discussions, decisions, action items
- **Chunking:** One chunk per email (not per thread). Subject + body. Truncate at 2000 chars.

**Calendar:**
- Skip if title matches routine patterns: configurable `SKIP_TITLES` list
- Skip all-day events (usually holidays/OOO)
- Keep: events with notes/descriptions, events with non-routine titles, events with attendees
- **Chunking:** One chunk per event. Title + location + notes + attendees.

**Reminders:**
- Skip if completed > 30 days ago (stale)
- Keep all incomplete reminders
- Keep completed reminders with notes
- **Chunking:** One chunk per reminder. Title + notes + due date.

**Notes:**
- Keep all notes modified in the backfill window
- Skip notes with < 20 chars (empty/stub notes)
- **Chunking:** One chunk per note. Title + body. Split long notes at 2000-char paragraph boundaries (existing bridge logic handles this).

### Fact Extraction Throttling

Backfill will produce 1,500–3,000 chunks. Running fact extraction on ALL of them is:
- **Cost:** ~3 LLM calls per chunk × 3,000 = 9,000 inference calls
- **Time:** At ~2s/call local (Qwen 3.5 9B) = ~5 hours
- **GPU:** Mac Mini M1 saturated for 5h, blocking chat inference

**Proposed threshold:** Only extract facts from chunks with `importance >= 0.5`. This should filter out ~60% of routine content, leaving ~1,200 chunks for extraction (~2h inference time).

**Alternative:** Extract facts only from Notes and high-importance Email initially. Calendar and Reminders contribute structured data (dates, people) but rarely produce interesting knowledge graph relationships.

**Recommended phased approach:**

| Phase | Source | Est. Chunks | Fact Extraction? | Why |
|-------|--------|-------------|------------------|-----|
| 1 | Notes | 50–200 | Yes, all | Highest quality, smallest volume, validates pipeline |
| 2 | Reminders | 100–200 | Yes, importance ≥ 0.5 | Action-oriented, reveals priorities |
| 3 | Calendar | 200–400 | No (structured data only) | Dates/people useful for entity resolution, not facts |
| 4 | Email | 500–1,500 | Yes, importance ≥ 0.6 | Highest volume, most noise, strictest filter |

Run each phase, validate quality in the Memory Browser and graph, then proceed.

### Dedup Safety

The `source_dedup` table (`UNIQUE(source, source_id)`) prevents re-ingestion. After backfill:
- Subsequent daily runs (Issue 4) will skip all backfilled items
- Re-running backfill is safe — already-ingested items are skipped

**Risk:** If a note is edited after backfill, the dedup check will still skip it (same source_id). The bridge does NOT handle updates — it's insert-only. This is acceptable for v1 but should be flagged for future improvement.

### Memory Impact

Adding 3,000 chunks to the system:
- **ChromaDB:** ~3,000 embeddings × 384 dims × 4 bytes = ~4.6 MB. Negligible.
- **SQLite:** ~3,000 rows × ~2KB avg = ~6 MB. Negligible.
- **Graph nodes:** If fact extraction produces ~2 facts per chunk = ~6,000 facts. Graph builder handles this (already tested with 200+ nodes, fixed overflow in Sprint 20).
- **Mac Mini RAM:** ChromaDB is the main concern. At 3,000 embeddings, it's well within 16GB headroom.

### Risks

1. **Swift CLI tools not deployed on Mac Mini.** The notes CLI and potentially others may not be built/installed on the production server. Verify with `which hestia-notes` on the Mac Mini.

2. **Mail.app not running on Mac Mini.** Email ingestion via AppleScript requires Mail.app to be running or to have cached data. The Mac Mini may not have an active mail session. Mitigation: test email access first, skip if unavailable.

3. **TCC permissions.** Calendar, Reminders, and Contacts access requires TCC approval on the Mac Mini. These may have been granted for the server process but should be verified.

4. **Backfill script blocks inference.** Running 2–5h of fact extraction saturates the GPU. Mitigation: run at 3 AM when chat is unlikely; or implement a priority queue where chat inference preempts backfill.

5. **Quality regression.** Flooding the graph with low-quality Apple data could make the graph less useful. Mitigation: phased rollout with manual review after each phase; strict quality gating; importance threshold for fact extraction.

### Effort: ~10h (backfill script + quality filters per source + phased execution + validation)

---

## ChunkType Taxonomy Review

### Current Types

| Type | Value | Current Usage | Assessment |
|------|-------|--------------|------------|
| `CONVERSATION` | `"conversation"` | Live chat exchanges | Correct. Clear definition. |
| `FACT` | `"fact"` | Bridge uses for mail/calendar/reminders | **Overloaded.** A calendar event isn't a "fact" in the knowledge graph sense. |
| `PREFERENCE` | `"preference"` | User preferences from chat | Correct. Well-defined. |
| `DECISION` | `"decision"` | Architecture/user decisions | Correct. Well-defined. |
| `ACTION_ITEM` | `"action_item"` | Tasks from chat | Correct. Well-defined. |
| `RESEARCH` | `"research"` | Investigation/research results | Correct. Well-defined. |
| `SYSTEM` | `"system"` | System-generated (config, audit) | Correct. Well-defined. |
| `INSIGHT` | `"insight"` | Claude history + notes | **Problematic.** Name implies distilled wisdom, but 988 chunks are raw chat history. |

### Proposed Taxonomy Adjustments

1. **Rename INSIGHT → OBSERVATION.** "Insight" implies distilled knowledge. "Observation" better describes raw captured content that hasn't been quality-scored. Or keep INSIGHT but add a formal definition: "Content captured from external sources (imported history, notes) that may contain insights — quality varies, use durability score to assess."

2. **Add SOURCE_DATA type.** For structured Apple data (calendar events, reminders) that aren't "facts" in the knowledge graph sense but are useful for entity resolution and temporal context. Currently these are typed as FACT which is misleading.

3. **Keep FACT for extracted facts only.** The research graph's `facts` table should be the only producer of FACT-typed chunks. Bridge-ingested data should use SOURCE_DATA or OBSERVATION.

**Decision needed:** Is the taxonomy change worth the migration cost? The existing system works — the types just have slightly misleading names. A simpler alternative is to document clear definitions (below) without changing enum values.

---

## Graph Legend Mapping & Tooltip Definitions

### Current Legend → ChunkType Mapping

The graph legend shows **node types**, not ChunkTypes directly. The mapping:

| Legend Entry | Node Type | Source | Color | Present in Graph? |
|-------------|-----------|--------|-------|--------------------|
| Memory | `memory` | Memory chunks (all types) | Gray `#8E8E93` | Yes (legacy mode) |
| Topic | `topic` | Auto-extracted tags | Yellow `#FFD60A` | Yes (legacy mode) |
| Entity | `entity` | Entity resolution | Green `#30D158` | Yes (facts mode) |
| Principle | `principle` | Distilled principles | Violet `#BF5AF2` | Yes (both modes) |
| Community | `community` | Label propagation clusters | Pink `#FF375F` | Yes (facts mode) |
| Episode | `episode` | Episodic nodes | Cyan `#5AC8FA` | Yes (facts mode) |
| Fact | `fact` (as edge) | Bi-temporal facts | Cyan `#64D2FF` | Yes (facts mode, as edges) |

**Memory chunk type sub-colors** (shown under "Memory types:" in legend):

| Sub-Type | Color | Hex |
|----------|-------|-----|
| Chat | Blue | `#5AC8FA` |
| Insight | Gray | `#8E8E93` |
| Preference | Orange | `#FF9500` |
| Fact | Green | `#4CD964` |
| Decision | Red | `#FF3B30` |
| Action | Purple | `#AF52DE` |
| Research | Blue | `#007AFF` |

### Proposed Tooltip Definitions

These should display on hover/long-press in the legend:

| Entry | Tooltip Definition |
|-------|-------------------|
| **Memory** | "Raw memory chunks from conversations, imports, and Apple data. Size = importance score." |
| **Topic** | "Automatically extracted themes that connect related memories. Larger = more connections." |
| **Entity** | "People, tools, projects, and concepts mentioned across your memories. Resolved to canonical names." |
| **Principle** | "Distilled behavioral patterns and beliefs extracted from your conversations over time." |
| **Community** | "Clusters of related entities detected by connection analysis. Represents knowledge domains." |
| **Episode** | "Significant events or interactions that tie together multiple entities and facts." |
| **Fact** | "Verified relationships between entities with timestamps. Contradicted facts are automatically superseded." |
| **Chat** | "Direct conversation exchanges between you and Hestia." |
| **Insight** | "Captured observations from imported history and notes. Quality varies — filtered by durability score." |
| **Preference** | "Your stated preferences and working style choices." |
| **Decision** | "Architectural and personal decisions with rationale." |
| **Action** | "Tasks and action items identified in conversations." |
| **Research** | "Findings from URL investigations and research sessions." |

---

## Implementation Order

| Order | Issue | Effort | Dependencies | Priority |
|-------|-------|--------|-------------|----------|
| 1 | Issue 1: Bracket prefix stripping | 1h | None | Quick win |
| 2 | Issue 2: Insight reclassification | 4h | Run diagnostic queries first | High — fixes graph quality |
| 3 | Issue 4: Daily ingestion scheduling | 2h | Verify Mac Mini CLI tools | Medium — enables ongoing data flow |
| 4 | Issue 3: Source filter consolidation | 2h | After Issue 2 (source distribution changes) | Medium — UI cleanup |
| 5 | Issue 5: Historical backfill | 10h | After Issues 2, 3, 4 are complete | High — biggest data quality impact |
| 6 | Taxonomy + tooltips | 2h | After Issue 5 (informed by real data) | Low — documentation + UI polish |

**Total: ~21h** (can be split across 2–3 sessions)

**Critical path:** Issues 1 → 2 → 4 → 5. Issues 3 and 6 can be done in parallel after Issue 2.

---

## Gemini Second-Opinion Prompt

```markdown
You are a senior data engineer reviewing a plan to improve data quality in a personal knowledge graph system.

## System Context
- Personal AI assistant (single user) running on Mac Mini M1 (16GB)
- Knowledge graph: SQLite facts table + ChromaDB vector embeddings
- Memory system: ~1,000 chunks currently, expected to grow to ~4,000 after backfill
- Local LLM inference: Qwen 3.5 9B (~12 tok/s on M1)
- Data sources: Chat history (988 imported chunks), Apple ecosystem (mail, calendar, reminders, notes — currently 0 chunks)

## The Problem
1. 988 imported Claude history chunks were classified as "Insight" regardless of quality. Many are procedural garbage.
2. The knowledge graph is 99% Claude history — no Apple ecosystem data has been ingested despite having access.
3. The quality framework (DIKW durability scoring, 3-phase extraction) exists but was never run retroactively.

## Proposed Backfill Strategy
- Phase 1: Notes (50-200 chunks, extract all facts)
- Phase 2: Reminders (100-200, extract facts if importance ≥ 0.5)
- Phase 3: Calendar (200-400, no fact extraction — structured data only)
- Phase 4: Email (500-1,500, extract facts if importance ≥ 0.6)

Quality gates per source: skip newsletters, routine calendar entries, empty notes, completed reminders >30d old.

## Proposed Reclassification
- Heuristic filter to downgrade procedural insights to CONVERSATION type
- LLM quality scoring (DIKW durability) on survivors
- Re-extract facts from chunks scoring Durable+ (durability ≥ 2)
- No data deletion — only type reclassification

## ChunkType Taxonomy Question
Current types: CONVERSATION, FACT, PREFERENCE, DECISION, ACTION_ITEM, RESEARCH, SYSTEM, INSIGHT.
"INSIGHT" is overloaded (988 raw imports + notes = "insight"). "FACT" is used for both extracted knowledge graph facts AND Apple data chunks.

Should we:
A) Rename INSIGHT → OBSERVATION and add SOURCE_DATA for structured Apple data?
B) Keep current names but document clear definitions?
C) Something else?

## Specific Questions
1. Is the phased backfill approach correct, or should we backfill everything at once and filter after?
2. Is importance ≥ 0.5 the right threshold for fact extraction, or too aggressive/conservative?
3. For email threading — one chunk per email or one chunk per thread? (Current: one per email)
4. Should calendar events even go into the memory/knowledge graph system, or are they better served by the existing EventKit integration alone?

Please provide:
1. Assessment of the backfill strategy's strengths and weaknesses
2. Alternative quality thresholds you'd recommend
3. Your view on the ChunkType taxonomy question
4. Any risks the plan missed
5. Verdict: APPROVE, APPROVE WITH CONDITIONS, or REWORK
```

---

---

## Gemini Second-Opinion Results (2026-03-18)

**Model:** Gemini 2.5 Pro
**Verdict:** APPROVE WITH CONDITIONS

### Strengths Identified
- Phased backfill approach de-risks by isolating issues per source
- Source-specific quality gates are sophisticated and appropriate
- No-deletion reclassification preserves raw data for future reprocessing

### Conditions for Approval

1. **Taxonomy first.** Implement ChunkType changes BEFORE backfill so new data is categorized correctly from the start.
2. **Calibrate thresholds empirically.** Sample 100 items per source, score them, review the distribution, then set thresholds — don't commit to 0.5/0.6 without data.
3. **Re-evaluate calendar ingestion.** Calendar events are structured data better served by EventKit queries than vector search. Consider excluding from ChromaDB backfill entirely.
4. **Estimate processing time.** Time a 50-chunk batch end-to-end before committing to the full run.

### Novel Insights (not in internal audit)

1. **Calendar in vector store is questionable.** "Meetings about Project X" is a structured query, not a vector similarity search. Calendar events may just add noise to ChromaDB. *Recommendation: keep calendar in EventKit, don't backfill into memory system.*

2. **Email threading metadata.** One-chunk-per-email is pragmatic, but adding `thread_id` to metadata enables future thread reconstruction without current complexity. *Good low-cost enhancement.*

3. **Taxonomy proposal is more specific.** Gemini recommends:
   - `OBSERVATION` (replaces INSIGHT — raw unprocessed captures)
   - `SOURCE_STRUCTURED` (new — calendar events, reminders where value is in metadata not content)
   - `FACT` reserved for extracted knowledge graph atoms only
   - `CONVERSATION` as the downgrade target for procedural content

### Where Both Models Agree
- Phased approach is correct (Notes → Reminders → Calendar → Email)
- No data deletion — reclassify only
- Quality gating per source is essential
- Processing time on M1 is a real constraint (~2-5h for full run)
- Importance thresholds need empirical validation

### Where Models Diverge

| Topic | Claude | Gemini | Resolution |
|-------|--------|--------|------------|
| Calendar backfill | Ingest as structured data, skip fact extraction | Don't ingest at all — EventKit is sufficient | **Gemini is partially right.** Calendar doesn't benefit from vector search, BUT the knowledge graph needs calendar data for entity resolution — connecting people, projects, and temporal context across sources. Keep backfill, skip fact extraction, tag as SOURCE_STRUCTURED. |
| Taxonomy change timing | Do after backfill (informed by real data) | Do before backfill (clean from the start) | **Gemini is right.** Changing types after ingestion means a second migration. Do it first. |
| Threshold selection | Fixed 0.5/0.6 based on reasoning | Sample-calibrate-then-set based on data | **Gemini is right.** Empirical calibration is better than guessing. |
| Email threading | One chunk per email, no thread tracking | One chunk per email + thread_id in metadata | **Gemini adds value.** Low-cost metadata addition enables future improvement. |

### Updated Implementation Order (incorporating Gemini conditions)

| Order | Task | Effort |
|-------|------|--------|
| 1 | Issue 1: Bracket prefix stripping | 1h |
| 2 | ChunkType taxonomy migration (INSIGHT→OBSERVATION, add SOURCE_STRUCTURED) | 2h |
| 3 | Issue 2: Insight reclassification (heuristic + calibrated LLM scoring) | 4h |
| 4 | Issue 4: Daily ingestion scheduling | 2h |
| 5 | Issue 3: Source filter consolidation | 2h |
| 6 | Issue 5: Historical backfill (Notes → Reminders → Calendar → Email) | 10h |
| 7 | Legend tooltips + documentation | 1h |
| **Total** | | **~22h** |

---

*Plan authored by Claude Opus 4.6 with Gemini 2.5 Pro cross-validation. Ready for review.*
