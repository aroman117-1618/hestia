# ChatGPT History Backfill: Research & Implementation Plan

**Date:** 2026-03-20
**Author:** Claude (Architect) + Andrew (Direction)
**Status:** PROPOSED
**Sprint:** 27A (parallel to Go-Live soak)

---

## Executive Summary

Import 3+ years of Andrew's ChatGPT conversation history (518 conversations, ~26K messages, Dec 2022–Mar 2026) into Hestia's memory pipeline. This gives Tia deep context on Andrew's preferences, decisions, technical patterns, and project history — the kind of knowledge a real assistant would accumulate over years of working together.

The existing Claude history importer (`importers/claude.py` + `pipeline.py`) provides 80% of the infrastructure. We need a new OpenAI parser, a preprocessing/summarization layer for high-volume conversations, and a priority-based phased import.

**Effort:** ~8–10 hours across 3 workstreams
**Risk:** Low — additive-only, reuses proven pipeline, idempotent re-import

---

## Table of Contents

1. Data Landscape
2. Architecture Design
3. Workstream Breakdown
4. Acceptance Criteria
5. Risks & Mitigations

---

## 1. Data Landscape

### 1.1 Export Structure

| Metric | Value |
|--------|-------|
| Total conversations | 518 |
| Total messages | ~26,324 |
| Date range | Dec 12, 2022 – Mar 15, 2026 |
| Files | `conversations-000.json` through `conversations-005.json` (89MB) |
| Text-only conversations | 378 (73%) |
| With image references | 140 (27%) |
| Conversations >100 messages | 43 (8%) — these are the high-value deep sessions |
| Median messages/conversation | 14 |

### 1.2 Schema Quirks

**Message tree (DAG, not list):** ChatGPT stores messages in a `mapping` dict keyed by UUID, with parent/children pointers. Conversations can branch when the user edits a message. We need a tree-flattening algorithm to extract the active thread.

**Image references:** 868 `file-service://` asset pointers in messages, 709 image files in UUID-named subfolders. The asset pointer IDs don't map to folder names — linking is lost. We'll store pointers as metadata but skip image content.

**Timestamps:** Unix floats, no timezone. Treat as UTC.

**Model metadata:** `metadata.model_slug` tells us which model responded (GPT-3.5, GPT-4, etc.). Useful for confidence scoring — GPT-4 conversations likely contain higher-quality reasoning.

### 1.3 Content Triage

| Category | Count | Memory Value | Import Phase |
|----------|-------|-------------|--------------|
| Project-specific (Hestia, trading, infra) | 53 | **HIGH** | Phase 1 |
| Personal preferences (health, style, goals) | ~18 | **HIGH** | Phase 1 |
| Technical knowledge (SQL, APIs, debugging) | ~184 | MEDIUM | Phase 2 |
| Professional context (Salesforce, Rev, career) | ~102 | MEDIUM | Phase 2 |
| Creative/content (writing, design, brainstorming) | ~68 | MEDIUM | Phase 2 |
| Research/learning (topic exploration) | ~28 | MEDIUM | Phase 2 |
| Transactional (quick lookups, calculations) | ~65 | LOW | Skip |

---

## 2. Architecture Design

### 2.1 Module Structure

```
hestia/memory/importers/
├── claude.py          # Existing — Claude.ai parser
├── openai.py          # NEW — ChatGPT export parser
├── pipeline.py        # Extended — add import_openai_history()
└── summarizer.py      # NEW — LLM-based conversation distillation
```

### 2.2 Parser Design (`openai.py`)

**Responsibilities:**
- Load multi-file ChatGPT export (`conversations-000.json` through `conversations-NNN.json`)
- Flatten message DAG to active thread (walk `current_node` → root via parent pointers)
- Extract user/assistant turns, skip system messages
- Apply credential stripping (reuse `CREDENTIAL_PATTERNS` from claude.py)
- Chunk conversations at 2000-char boundaries (match existing `MAX_CHUNK_CHARS`)
- Tag with `source = MemorySource.OPENAI_HISTORY`
- Set `scope = MemoryScope.LONG_TERM`
- Preserve conversation metadata: title, create_time, model_slug

**Chunk types produced:**
- `CONVERSATION` — standard user/assistant exchanges (confidence 0.8)
- `PREFERENCE` — conversations tagged as personal preference during triage (confidence 0.9)
- `DECISION` — conversations containing architecture/life decisions (confidence 0.85)
- `OBSERVATION` — image-heavy or creative sessions where value is contextual (confidence 0.6)

### 2.3 Summarizer Design (`summarizer.py`)

For conversations with >50 messages, raw chunking produces too much noise. The summarizer distills these into high-signal memory chunks.

**Algorithm:**
1. Group messages into ~10-turn windows
2. For each window, call inference (local Qwen or cloud) with extraction prompt:
   - "What decisions were made?"
   - "What preferences did the user express?"
   - "What facts were established?"
   - "What was the outcome?"
3. Produce 1-3 distilled chunks per window (DECISION, PREFERENCE, or FACT type)
4. For conversations <50 messages, skip summarization — chunk raw text directly

**Fallback:** If inference unavailable, fall back to raw chunking (same as Claude importer). Summarization is additive quality, not a gate.

### 2.4 Pipeline Extension

Add `import_openai_history()` to `ImportPipeline`, mirroring `import_claude_history()`:

```python
async def import_openai_history(
    self,
    export_dir: str,
    phase: int = 1,           # 1 = high-value only, 2 = all
    summarize: bool = True,   # Use LLM distillation for long convos
    dry_run: bool = False,    # Preview mode
) -> ImportResult:
```

**Dedup:** Same stable-hash strategy — `md5(content)[:16]` keyed by `session_id:hash`. Safe to re-run.

### 2.5 API Endpoint

```
POST /v1/memory/import/openai
Body: {
    "export_dir": "/path/to/ChatGPT/",
    "phase": 1,
    "summarize": true,
    "dry_run": false
}
Response: ImportResult
```

### 2.6 Data Flow

```
ChatGPT JSON files
  → OpenAIHistoryParser.parse_export()
    → Flatten DAG → active thread
    → Strip credentials
    → Chunk at 2000 chars
    → Tag with source/scope/type
  → Summarizer (optional, for >50-message convos)
    → LLM extraction → distilled DECISION/PREFERENCE/FACT chunks
  → ImportPipeline.import_openai_history()
    → Stable-hash dedup (skip duplicates)
    → memory_manager.store() → SQLite + ChromaDB
    → record_dedup() → idempotency tracking
  → ImportResult (stored/skipped/failed counts)
```

---

## 3. Workstream Breakdown

### WS1: OpenAI Parser + Pipeline Extension (~4h)

| Task | Hours | Details |
|------|-------|---------|
| `openai.py` parser | 2.0 | DAG flattener, turn extractor, credential stripper, chunker |
| Pipeline extension | 0.5 | `import_openai_history()` in pipeline.py, multi-file loading |
| API endpoint | 0.5 | POST `/v1/memory/import/openai` with phase/summarize/dry_run params |
| Tests | 1.0 | Parser unit tests, pipeline integration tests, DAG edge cases |

### WS2: Conversation Summarizer (~3h)

| Task | Hours | Details |
|------|-------|---------|
| `summarizer.py` | 1.5 | Window grouping, extraction prompt, chunk production |
| Prompt engineering | 0.5 | Tune extraction prompt for decision/preference/fact yield |
| Integration | 0.5 | Wire into pipeline, add fallback for inference-down |
| Tests | 0.5 | Summarizer unit tests, mock inference |

### WS3: Import Execution + Validation (~2h)

| Task | Hours | Details |
|------|-------|---------|
| Phase 1 import | 0.5 | Run against ~71 high-value conversations |
| Validation | 0.5 | Spot-check chunks via `/v1/memory/search`, verify dedup |
| Consolidation | 0.5 | Run dedup preview, merge any near-duplicates with existing memory |
| Phase 2 import | 0.5 | Run against remaining ~380 medium-value conversations |

**Total: ~9 hours**

---

## 4. Acceptance Criteria

- [ ] `OpenAIHistoryParser` correctly flattens DAG to active thread for all 518 conversations
- [ ] Credential patterns stripped (API keys, tokens, passwords)
- [ ] All chunks tagged with `source=openai_history`, `scope=LONG_TERM`
- [ ] Conversations with >50 messages produce summarized DECISION/PREFERENCE/FACT chunks
- [ ] Conversations with <50 messages produce raw CONVERSATION chunks
- [ ] Idempotent: re-running import produces 0 new chunks (all skipped as duplicates)
- [ ] Phase 1 imports ~71 conversations (project-specific + personal preferences)
- [ ] Phase 2 imports remaining ~380 medium-value conversations
- [ ] `Tia, what do I think about X?` queries return relevant results from imported history
- [ ] No image binaries stored — only asset pointer references in metadata
- [ ] Import stats endpoint returns accurate counts
- [ ] All existing tests still pass (no regressions)

---

## 5. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| 89MB JSON parse causes memory spike | LOW | Stream conversations one file at a time, don't load all 6 simultaneously |
| Summarizer LLM calls slow (518 × N windows) | MED | Phase 1 is only ~71 convos; summarize only >50-msg; fallback to raw chunk |
| ChromaDB embedding backlog | LOW | Batch add via `vector_store.add_chunks()`; ChromaDB handles batching internally |
| Dedup false positives (similar convos across ChatGPT and Claude) | LOW | Source-specific dedup keys (`openai_history:hash` vs `claude_history:hash`) |
| Stale/outdated preferences in old conversations | MED | ImportanceScorer will naturally decay old memories; summarizer focuses on decisions not opinions |
| DAG flattening loses valuable alternate branches | LOW | 95%+ of conversations are linear; branching is rare in practice |
