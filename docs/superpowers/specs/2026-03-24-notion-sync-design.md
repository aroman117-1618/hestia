# Notion Sync Script Design

**Author:** Claude + Andrew
**Date:** 2026-03-24
**Status:** Approved

## Overview

Standalone Python script (`scripts/sync-notion.py`) that syncs git docs to Notion databases and reads the Notion whiteboard. Uses direct REST API calls with `NOTION_TOKEN` env var. No MCP dependency, no server dependency.

## Architecture

```
scripts/sync-notion.py
├── CLI (argparse)
│   ├── read-whiteboard     → stdout markdown
│   ├── push [path]         → sync docs to Notion
│   ├── push --incremental  → only changed files
│   └── status              → sync state summary
│
├── NotionClient            → httpx + rate limiting + retry
├── MarkdownToBlocks        → markdown → Notion block JSON
├── DocMapper               → git path → database + properties
└── SyncState               → data/notion-sync-state.json
```

## Components

### NotionClient
- httpx with Bearer auth from `NOTION_TOKEN`
- Rate limiter: 3 req/sec, exponential backoff on 429
- Notion-Version: 2022-06-28
- Methods: search, get_page, get_blocks, create_page, update_page, append_blocks, delete_blocks

### MarkdownToBlocks
Converts markdown to Notion block arrays:
- Headings (h1-h3), paragraphs, bullet/numbered lists, code blocks, tables, dividers
- Inline: bold, italic, code → rich_text annotations
- Chunks at 100-block boundaries

### DocMapper
Routes git paths to Notion databases:

| Git Path | Database | Properties |
|----------|----------|------------|
| docs/plans/*.md | Documentation Hub | Category=Plan |
| docs/discoveries/*.md | Discoveries | Topic, date |
| docs/audits/*.md | Documentation Hub | Category=Metrics |
| docs/retrospectives/*.md | Retrospectives | Duration, findings |
| docs/reference/*.md | Documentation Hub | Category=Reference |
| docs/architecture/*.md | Documentation Hub | Category=Architecture |
| docs/archive/*.md | Archive | Category, original date |
| hestia-decision-log.md | ADR Registry | Split per ADR |
| hestia-security-architecture.md | Documentation Hub | Category=Security |
| api-contract.md | API Reference page | Split by module |

### SyncState
JSON at `data/notion-sync-state.json`:
```json
{
  "last_full_sync": "2026-03-24T11:45:00Z",
  "files": {
    "docs/plans/some-plan.md": {
      "content_hash": "sha256:abc...",
      "notion_page_id": "uuid",
      "last_synced": "2026-03-24T11:45:00Z"
    }
  }
}
```

## Database IDs

```python
DATABASES = {
    "documentation_hub": "3aa5bcff-d66e-485c-b5d6-8c68bdbf94f9",
    "adr_registry": "5b0e4074-eca7-4d9c-be40-0e7486a7f362",
    "sprints": "20e6158d-9d21-4e4d-be40-11e08f6932c3",
    "discoveries": "7af2fe3b-8cf2-440d-ad44-68e67f9e500d",
    "retrospectives": "032afae6-c8a4-4ab0-93c2-8e29565b959f",
    "archive": "feb292cc-621d-4982-942a-ea99dcf62e44",
}
WHITEBOARD_PAGE_ID = "e739da68-2b62-49ae-a4d1-979019771961"
API_REFERENCE_PAGE_ID = "3f49d829-d1aa-40be-89c0-f18cd5d3fd4e"
```

## Scope Boundaries

- One-way push only (git → Notion)
- Manual or hook-triggered (no real-time watch)
- Standalone (no Hestia server dependency)
- Hestia docs only (Steward added later)
- No database schema creation (already done)

## Special Cases

- **ADR decomposition**: Split monolithic decision log by `## ADR-NNN:` boundaries
- **API contract decomposition**: Split by route module into sub-pages
- **Large files**: Chunk at 100 blocks per append_blocks call
