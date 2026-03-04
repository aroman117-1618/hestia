# ChromaDB Collection Strategy

**Created:** 2026-03-03 (from audit recommendation)
**Updated:** 2026-03-03 (Sprint 8 complete — both collections operational)
**Status:** Reference document — update as collections are added

---

## Overview

Hestia uses ChromaDB for vector storage. As the project grows, multiple modules need vector search. This document defines the collection strategy to prevent namespace collisions, query pollution, and performance degradation.

## Collections

| Collection Name | Module | Sprint | Embedding Model | Purpose | Max Documents |
|----------------|--------|--------|----------------|---------|---------------|
| `hestia_memory` | MemoryManager | Existing | Ollama nomic-embed-text | Conversation memories, facts, preferences | Unlimited (decay manages size) |
| `hestia_principles` | PrincipleStore | 8 | Ollama nomic-embed-text | Distilled behavioral principles | ~500 (reviewed + validated) |
| `hestia_graph` | GraphBuilder | 8 (if needed) | Ollama nomic-embed-text | Graph node embeddings for similarity edges | ~200 (node limit) |

## Rules

1. **One collection per domain.** Never store principles in `hestia_memory` — metadata conflicts and query pollution will occur.

2. **Consistent embedding model.** All collections use the same embedding model (`nomic-embed-text` via Ollama) so that cross-collection similarity queries are meaningful.

3. **Metadata schema per collection.** Each collection has a defined metadata schema. Do not add ad-hoc metadata fields without updating this document.

4. **Query isolation.** Always query a specific collection by name. Never use global search across collections.

5. **Document ID format.** Use `{collection_prefix}_{uuid}` to prevent ID collisions if collections are ever merged for analysis: `mem_abc123`, `prin_def456`, `graph_ghi789`.

## Metadata Schemas

### `hestia_memory`
```python
{
    "chunk_type": str,       # "conversation", "fact", "preference", "system"
    "session_id": str,
    "created_at": str,       # ISO 8601
    "decay_lambda": float,   # Per-type decay rate
    "tags": List[str],
    "agent": str,            # "tia", "mira", "olly"
}
```

### `hestia_principles`
```python
{
    "domain": str,           # "scheduling", "coding", "health", etc.
    "confidence": float,     # 0.0–1.0
    "validation_count": int,
    "contradiction_count": int,
    "source_sessions": List[str],
    "created_at": str,
    "last_validated": str,
    "status": str,           # "pending_review", "approved", "rejected"
}
```

### `hestia_graph` (if needed)
```python
{
    "node_type": str,        # "knowledge", "activity"
    "category": str,         # "finance", "health", "coding", etc.
    "weight": float,
    "last_active": str,
}
```

## Performance Considerations

- **M1 16GB constraint:** ChromaDB keeps an in-memory index. With 3 collections and moderate document counts (<5K total), memory usage should be ~200-500MB. Monitor if adding more collections.
- **Startup time:** Each collection loads its index on first query. Lazy-load collections not needed at boot.
- **Backup:** ChromaDB persists to `data/chroma/`. Include in backup rotation.

## Future Collections (Not Yet Planned)

- `hestia_research` — If graph builder needs separate embedding space for research documents
- `hestia_health` — If health data needs vector similarity (e.g., finding similar health patterns)
- `hestia_files` — If Explorer (Sprint 9) needs content-based file search
