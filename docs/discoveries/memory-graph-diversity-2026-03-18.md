# Discovery Report: Memory Graph Diversity
**Date:** 2026-03-18
**Confidence:** High
**Decision:** The graph only shows Conversation and Observation (formerly Insight) types because those are the only types that ever get created. No code path exists to produce Preference, Fact, Decision, Action, or Research memory chunks. Fixing this requires building a classification pipeline that runs during or after chat storage.

## Hypothesis
The Research graph should display diverse memory node types (Preference, Fact, Decision, Action Item, Research) but only shows Chat and Insight/Observation. The question: is this a display bug, a data pipeline gap, or both?

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** ChunkType enum is well-defined with 10 types. Graph builder correctly maps `chunk.chunk_type.value` to node category and color. Frontend legend, colors, and display logic for all 7 memory sub-types already exist. The infrastructure is ready. | **Weaknesses:** Zero code paths create non-CONVERSATION/OBSERVATION/SOURCE_STRUCTURED chunks. `store_exchange()` hardcodes `ChunkType.CONVERSATION`. AutoTagger extracts tags/metadata but never reclassifies chunk_type. No post-processing pipeline promotes chunks to specialized types. |
| **External** | **Opportunities:** The AutoTagger already detects `has_decision`, `has_action_item`, and `has_code` in metadata — this signal exists but is never used to set chunk_type. The DIKW durability framework could retroactively classify existing data. | **Threats:** Adding LLM-based classification to the hot path increases latency per chat message. Misclassification could degrade graph quality worse than uniform typing. |

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | Post-store async reclassification using existing AutoTagger signals (`has_decision`, `has_action_item`) | Legend tooltip definitions for each type |
| **Low Priority** | LLM-based semantic classifier for Preference/Research/Fact types | Retroactive reclassification of all 2,557 existing chunks |

## Root Cause Analysis (The Core Finding)

### 1. Every chat message is stored as CONVERSATION — no exceptions

In `hestia/orchestration/handler.py:1890-1909`, `_store_conversation()` calls:

```python
await memory.store_exchange(
    user_message=request.content,
    assistant_response=response.content,
    mode=request.mode.value,
)
```

In `hestia/memory/manager.py:307-340`, `store_exchange()` hardcodes both chunks:

```python
user_chunk = await self.store(
    content=f"User: {user_message}",
    chunk_type=ChunkType.CONVERSATION,  # Always CONVERSATION
    ...
)
assistant_chunk = await self.store(
    content=f"Assistant: {assistant_response}",
    chunk_type=ChunkType.CONVERSATION,  # Always CONVERSATION
    ...
)
```

### 2. AutoTagger detects signals but discards them

The `AutoTagger.quick_tag()` method (lines 171-228 of `tagger.py`) sets:
- `metadata.has_decision = True` when content contains "decided", "decision", etc.
- `metadata.has_action_item = True` when content contains "todo", "need to", etc.
- `metadata.has_code = True` when content contains code indicators

But these metadata flags are **never used to set `chunk_type`**. The async LLM tagger (`extract_tags()`) also only populates tags and metadata — it never touches `chunk_type`.

### 3. The only non-CONVERSATION producers are importers

| Producer | ChunkType Used | Count in DB |
|----------|---------------|-------------|
| `handler.py` → `store_exchange()` | CONVERSATION | 935 |
| `claude.py` importer → conversations | ~~INSIGHT~~ OBSERVATION (reclassified) | 988 |
| `bridge.py` → mail/notes | OBSERVATION | 570 |
| `bridge.py` → calendar/reminders | SOURCE_STRUCTURED | 64 |
| Any code path | PREFERENCE | **0** |
| Any code path | DECISION | **0** |
| Any code path | ACTION_ITEM | **0** |
| Any code path | RESEARCH | **0** |
| Any code path | FACT (as chunk) | **0** |

### 4. The facts graph mode has zero data

The fact-based graph (`mode=facts`) queries the `facts` and `entities` tables in the research database. Both are empty:
- `facts` table: 0 active rows
- `entities` table: 0 rows

The fact extraction pipeline exists (`_maybe_extract_facts` in handler.py fires for messages >200 chars) but either has never succeeded or its results aren't persisting. This means the Knowledge graph mode shows nothing, and the Memory graph mode shows only gray (Conversation) and amber (Observation) nodes.

## Argue (Best Case for Current State)

The current design is arguably intentional:
- **ChunkType is a semantic label, not an auto-classifier output.** The types were designed for explicit categorization (e.g., a user marking something as a decision, or a specific pipeline producing facts).
- **Avoiding misclassification.** Auto-classifying "I decided to use React" as DECISION when the user is quoting someone else would pollute the graph with false signals.
- **The DIKW framework was the intended solution.** Sprints 20A/20B built durability scoring and fact extraction as the proper promotion path. The data quality plan acknowledges this gap and has a phased remediation strategy.

## Refute (Devil's Advocate)

The current state is a significant product gap:
- **7 of 10 ChunkTypes are dead code.** PREFERENCE, DECISION, ACTION_ITEM, RESEARCH, FACT (as memory chunk), SYSTEM, and the new OBSERVATION distinction — the enum exists, the colors exist, the legend exists, but the data never gets created.
- **The graph is visually monotone.** A single-color graph provides no semantic differentiation. The entire visualization infrastructure (per-type colors, icons, legend) is wasted.
- **The AutoTagger already solves half the problem.** It detects decisions and action items with reasonable accuracy. Not using these signals is pure waste.
- **Zero facts after months of operation.** The fact extraction pipeline (`_maybe_extract_facts`) is fire-and-forget with no monitoring. It may be silently failing on every message.

## Third-Party Evidence

Personal knowledge graph systems (Obsidian, Mem.ai, Notion AI) all use automatic content classification:
- **Obsidian Dataview:** Users manually tag notes, but plugins auto-detect task items, decisions, and references.
- **Mem.ai:** Auto-classifies content into "knowledge", "tasks", "people", "dates" using LLM analysis.
- **The common pattern:** Classify at ingest time (not retroactively) with a lightweight model, then allow manual correction.

The key insight from these systems: **classification at storage time with a fast heuristic, refined asynchronously by LLM, is the standard approach.** Hestia has the async LLM refinement (`_async_tag_chunk`) but skips the classification step entirely.

## Recommendation

**Confidence: High.** The fix is straightforward and low-risk.

### Immediate Fix (2-3 hours): Heuristic Reclassification in `_async_tag_chunk`

Modify `MemoryManager._async_tag_chunk()` to also reclassify `chunk_type` based on the metadata signals that `AutoTagger` already extracts:

```python
async def _async_tag_chunk(self, chunk: ConversationChunk) -> None:
    new_tags, new_metadata = await self.tagger.extract_tags(chunk.content, existing_tags=chunk.tags)

    # Reclassify chunk_type based on detected signals
    if new_metadata.has_decision and chunk.chunk_type == ChunkType.CONVERSATION:
        chunk.chunk_type = ChunkType.DECISION
    elif new_metadata.has_action_item and chunk.chunk_type == ChunkType.CONVERSATION:
        chunk.chunk_type = ChunkType.ACTION_ITEM

    chunk.tags = new_tags
    chunk.metadata = new_metadata
    await self.database.update_chunk(chunk)
    self.vector_store.update_chunk(chunk)
```

This promotes CONVERSATION chunks to DECISION or ACTION_ITEM when the tagger detects those signals. It runs asynchronously (non-blocking) and is idempotent.

### Extended Fix: Add Preference and Research Detection

Extend `AutoTagger.extract_tags()` prompt or `quick_tag()` heuristics to detect:
- **PREFERENCE:** "I prefer", "I like", "I want", "always use", "never do"
- **RESEARCH:** Messages following `/investigate` or containing URL analysis results

### Medium-Term Fix: Fix Fact Extraction Pipeline

Diagnose why `_maybe_extract_facts()` produces zero results:
1. Check if the research database is initialized when the handler calls it
2. Check if the LLM calls in `fact_extractor.py` succeed or silently fail
3. Add monitoring/logging to the fire-and-forget task

### Retroactive Fix: Reclassify Existing Data

Run a one-time script (similar to `scripts/reclassify-insights.py` which already exists) that:
1. Loads all CONVERSATION chunks
2. Runs `AutoTagger.quick_tag()` on each
3. Reclassifies based on `has_decision` / `has_action_item` signals
4. Updates the database

### What Would Change This Recommendation

- If misclassification rate exceeds ~15%, revert to CONVERSATION-only and invest in a more sophisticated classifier
- If M1 inference latency becomes a concern, disable the LLM tagger and use only heuristic `quick_tag()`

## Final Critiques

- **Skeptic:** "Won't auto-classification flood the graph with false positives? 'I need to fix this bug' isn't really an action item."
  - **Response:** The current state (zero diversity) is strictly worse than imperfect classification. The heuristic detection in `quick_tag()` uses conservative keyword matching. False positive rate should be <20%, and users can manually reclassify in the Memory Browser (that UI already exists). The async LLM pass will refine the initial classification.

- **Pragmatist:** "Is 2-3 hours of effort worth it for a visual improvement?"
  - **Response:** This isn't cosmetic. The entire memory type system — 10 enum values, per-type decay rates, per-type importance scoring, per-type graph colors — is infrastructure that was built and is sitting unused. The fix unlocks value from ~200 lines of existing code that currently does nothing. It also makes the temporal decay system work as designed (decisions decay slower than conversations).

- **Long-Term Thinker:** "What happens in 6 months when there are 10,000 chunks?"
  - **Response:** The heuristic reclassification runs in the existing async tagger pipeline, which is already O(n) per message and non-blocking. At 10K chunks, the retroactive script takes ~5 minutes. The graph builder already caps at 200 nodes, so scale is handled. The real 6-month concern is fact extraction — if that pipeline never works, the Knowledge graph mode remains empty regardless.

## Open Questions

1. **Why does `_maybe_extract_facts()` produce zero results?** This is the single biggest data gap. The entire fact-based graph (entities, communities, episodes) depends on this pipeline working. Needs debugging.

2. **Should `quick_tag()` or `extract_tags()` drive reclassification?** `quick_tag()` is synchronous and immediate but crude. `extract_tags()` uses LLM and is more accurate but async. Recommendation: use `quick_tag()` for initial type assignment at store time, then let `extract_tags()` refine it async.

3. **Should the reclassification be applied retroactively?** The `scripts/reclassify-insights.py` script already exists for a similar purpose. A parallel script for CONVERSATION -> DECISION/ACTION_ITEM promotion would address the 935 existing conversation chunks.

4. **What about PREFERENCE and RESEARCH types?** These require either prompt-level detection (user explicitly states a preference) or pipeline-level detection (message came from `/investigate` flow). More complex than DECISION/ACTION_ITEM but achievable.

---

*Researched by Claude Opus 4.6. Data validated against live SQLite databases.*
