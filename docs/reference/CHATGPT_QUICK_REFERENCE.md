# ChatGPT Export — Quick Reference

**Location:** `/sessions/charming-tender-pascal/mnt/hestia/commercial-exports/ChatGPT/`

## VITAL STATS

| Metric | Value |
|--------|-------|
| Conversations | 518 |
| Messages | ~26,324 (median: 14 per conv) |
| Date range | Dec 2022 – Mar 2026 |
| Images | 868 references, 709 actual files |
| Hestia mentions | 53 conversations (10%) |

## CRITICAL SCHEMA

### Conversation
```json
{
  "id": "UUID",
  "title": "string",
  "create_time": 1700504589.591775,
  "update_time": 1700575857.745316,
  "current_node": "UUID (active leaf)",
  "mapping": { "UUID": MessageNode, ... }
}
```

### MessageNode (Tree structure)
```json
{
  "id": "UUID",
  "message": Message | null,
  "parent": "UUID or null",
  "children": ["UUID", ...]
}
```

### Message
```json
{
  "author": { "role": "user|assistant|system" },
  "content": {
    "content_type": "text|image_asset_pointer",
    "parts": [string or ImageObject]
  },
  "create_time": 1700504590.642135,
  "metadata": {
    "model_slug": "text-davinci-002-render-sha",
    "finish_details": {
      "type": "stop",
      "stop_tokens": [100260]
    }
  }
}
```

## KEY DECISIONS

| Issue | Solution |
|-------|----------|
| Branching (DAG) | Flatten to active thread (current_node → root) |
| Images | Store asset_pointer as-is; UUID mapping is missing |
| Timestamps | Unix float; assume UTC |

## IMPORT CHECKLIST

- [ ] Parse all 518 convs without errors
- [ ] Validate no circular parent-child refs
- [ ] Flatten to active threads
- [ ] Extract text + image references
- [ ] Preserve model_slug & finish_details
- [ ] Flag unresolved asset_pointers

## FILE LOCATIONS

- Conversations: `/ChatGPT/conversations-{000-005}.json`
- Images: `/ChatGPT/[UUID]/image/*.png` (40 folders)
- Metadata: `user.json`, `user_settings.json`, `export_manifest.json`

## GOTCHAS

1. **DAG, not list** — Messages branch; use current_node + parent pointers
2. **Image mapping lost** — asset_pointer ≠ UUID folder names
3. **Nullable fields** — author.name, gizmo_id, etc. always null
4. **No embeddings** — Must embed text during import
5. **No timestamps on images** — Can't auto-link images to conversations

## NEXT PHASE

Design tree flattening + content extraction pipeline for Hestia memory ingestion.

---

**Full report:** `CHATGPT_EXPORT_SCHEMA_ANALYSIS.md` (602 lines)
