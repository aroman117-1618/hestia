# Notion Sync V2 — Consolidation & Automation

**Author:** Claude + Andrew
**Date:** 2026-03-25
**Status:** Approved

## Overview

Evolve `scripts/sync-notion.py` to consolidate three Notion databases into one Archive, convert API Reference from a page to a per-endpoint database, automate sprint syncing, and trigger full reconciliation from five Claude Code skills.

## Goals

1. Simplify the Hestia Notion sidebar from 5 items to 3 (Sprints, API Reference, Archive)
2. Make API endpoints individually queryable and filterable in Notion
3. Automate sprint state sync from SPRINT.md — no manual `sync-sprints` calls
4. Wire `sync-all` into `/pickup`, `/discovery`, `/ship-it`, `/handoff`, `/codebase-audit`
5. Maintain the Whiteboard → Plan → Sprint card lifecycle

## Current State

- `sync-notion.py` (~1,300 lines) with NotionClient, MarkdownToBlocks, DocMapper, SyncState
- 4 Notion databases: `planning_logs`, `adr_registry`, `sprints`, `archive`
- 1 Notion page: `API_REFERENCE_PAGE_ID` (single page, not a database)
- Commands: `read-whiteboard`, `push`, `push-adrs`, `status`, `search`, `read-page`, `query-db`, `update-page`
- Whiteboard reads from a hardcoded page ID (not the Sprint board card)

---

## Design

### 1. Database Consolidation: Archive

Merge `planning_logs`, `adr_registry`, and `archive` into a single **Archive** database.

**Archive database properties:**

| Property | Type | Purpose |
|----------|------|---------|
| Title | title | Document title |
| Type | select | ADR, Plan, Discovery, Audit, Retrospective, Spec, Reference, Architecture, Security, Archive |
| Status | select | Active, Accepted, Deprecated, Superseded |
| Date | date | Document date |
| Domain/Topic | multi_select | Trading, Security, Inference, Memory, Council, UI, Orchestration, API, Architecture, Deployment, Health, Wiki, Research, Performance |
| ADR Number | number | Only for ADR type (sortable, filterable) |
| Git Path | rich_text | Source file path in git |
| Last Synced | date | Sync timestamp |
| Linked Sprint | relation | Link to Sprints database |
| Superseded By | relation | Self-relation for ADR chains (ADR-040 supersedes ADR-001) |

**Script changes:**
- `DATABASES` dict: remove `planning_logs` and `adr_registry`, keep `archive` with consolidated database ID
- `DocMapper.ROUTING`: all routes point to `"archive"` instead of `"planning_logs"`
- `DocMapper.build_properties()`: unified property builder for all types, with `Type` select distinguishing ADRs from Plans from Discoveries etc.
- `cmd_push_adrs()`: targets `archive` database, sets `Type=ADR` property
- ADR-specific properties (ADR Number, Status=Accepted/Deprecated/Superseded) set alongside shared properties

### 2. API Reference Database

New Notion database with one row per endpoint (~129 documented in `api-contract.md`).

**API Reference database properties:**

| Property | Type | Purpose |
|----------|------|---------|
| Title | title | Endpoint description (e.g. "Register device") |
| Method | select | GET, POST, PUT, PATCH, DELETE |
| Path | rich_text | `/v1/auth/register` |
| Module | select | Auth, Chat, Memory, Trading, Health, etc. (26 modules) |
| Auth Required | checkbox | Whether JWT is needed |
| Status | select | Active, Stub, Deprecated |
| Response Codes | multi_select | 200, 400, 401, 403, 404, 409, 429, 501 |
| Request Body | checkbox | Whether endpoint accepts a request body |
| Last Synced | date | Sync timestamp |

**Page body:** Full endpoint documentation — request/response schemas, error codes, examples — parsed from the `api-contract.md` section for that endpoint.

**Parsing logic:**
- Split `api-contract.md` by `### Module Name (N endpoints)` headers → module name
- Split each module by `#### METHOD /path` → individual endpoints
- Auth detection: endpoints under "Health & Status" or noted as "no auth" → `false`, else `true`
- Status detection: endpoints noted as "Stub (returns 501)" → `Stub`, else `Active`
- Response codes: regex for `**Errors:**` lines extracting HTTP status codes
- Request body: presence of `**Request:**` section with JSON body

**Incremental sync:** Each endpoint keyed as `api:METHOD:/v1/path` in sync state with content hash.

**Security:** Token redaction — strip JWT-shaped strings (`eyJ...`) from example payloads before pushing to Notion. They're fake example tokens, but good hygiene for a database that could be shared.

### 3. Sprint Whiteboard Integration

**Reading the Whiteboard:**
- Update `cmd_read_whiteboard()` to query the Sprints database for the item with Status="Planning" and Title containing "Whiteboard" (replaces hardcoded `WHITEBOARD_PAGE_ID`)
- Falls back to the old page ID if no matching sprint card found (backward compat)
- Returns page body as markdown via existing `blocks_to_markdown()`
- Already wired into `/pickup` skill — no SKILL.md change needed for reads

**Plan → Sprint card lifecycle (new `create-sprint-item` command):**
1. Push plan doc to Archive (Type=Plan, Linked Sprint relation)
2. Create new Sprint card in Sprints database (Status="Next Up", title from plan)
3. Link the Sprint card and Archive record via relation property
4. Update sync state for both records

**Sprint state sync (new `sync-sprints` command):**
- Parse `SPRINT.md` for sprint entries: name, status, hours, workstreams, test counts, dates
- Query existing Sprint cards in Notion
- Create/update cards to match SPRINT.md state
- Property mapping: Status (Planning/Next Up/In Progress/Done), Hours Estimated, Hours Actual, Start Date, End Date, Test Count, Workstreams

### 4. Automated Sync via Skill Hooks

New `sync-all` command runs full reconciliation. Triggered by 5 skills automatically.

**`sync-all --incremental` does:**
1. Push changed docs → Archive database
2. Push changed ADRs → Archive database
3. Reconcile SPRINT.md → Sprints database
4. Parse api-contract.md → API Reference database (only if content hash changed)

**Skill integration:**

| Skill | Hook point | What it catches |
|-------|-----------|-----------------|
| `/pickup` | After reading SESSION_HANDOFF.md | Changes from previous session |
| `/discovery` | After discovery doc is written | New discovery → Archive |
| `/ship-it` | After version bump + tag | Sprint status, release notes |
| `/handoff` | Session end (before retro) | All docs changed during session |
| `/codebase-audit` | After audit doc is written | New audit → Archive, test counts |

**SKILL.md additions** (one line each):
```
Run `source .venv/bin/activate && python scripts/sync-notion.py sync-all --incremental 2>&1`
```

**Performance:** Incremental sync uses content hashes — typically 5-15 Notion API calls, under 10 seconds. Full sync (`sync-all --force`) available for manual recovery.

### 5. Migration & Cleanup

**One-time migration steps:**

1. **Create API Reference database** in Notion under Hestia with properties from Section 2
2. **Add new properties to Archive database** — ADR Number (number), Superseded By (self-relation), Linked Sprint (relation to Sprints)
3. **Run `migrate` command** (new) that:
   - Queries all pages from `planning_logs` and `adr_registry`
   - Re-creates them in the consolidated `archive` database with correct Type tags
   - Updates `notion-sync-state.json` with new page IDs
4. **Manually archive** `planning_logs` and `adr_registry` databases from Notion sidebar after verifying migration
5. **Update script constants** — remove old database IDs, add `api_reference` database ID, remove `WHITEBOARD_PAGE_ID` (now queried dynamically)
6. **Add `_redact_tokens()` method** to strip JWT-shaped strings from API contract content

**Post-migration Notion sidebar:**
```
Hestia
├── Sprints       (database — board view)
├── API Reference (database — table view)
└── Archive       (database — table/gallery view)
```

---

## Scope Boundaries

- One-way push only (git → Notion), except whiteboard reads (Notion → Claude)
- No real-time file watching — sync is skill-triggered or manual
- Standalone script — no Hestia server dependency
- No database schema creation via API — databases created manually in Notion first
- Token redaction is best-effort regex (`eyJ[A-Za-z0-9_-]{20,}`)

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| API Reference initial push is ~129 endpoints × ~3 API calls each = ~400 calls | One-time cost (~2-3 min with rate limiting). Incremental after that. |
| Migration could lose data if Archive DB properties don't match | Run `migrate --dry-run` first to validate property mapping |
| Sprint card title matching is fragile | Use Status="Planning" + title contains "Whiteboard" with fallback to hardcoded ID |
| `SPRINT.md` parsing breaks on format changes | Regex-based with graceful fallback — log warnings for unparseable entries, don't fail the whole sync |
| Notion rate limiting during `sync-all` | Existing rate limiter (3 req/sec with exponential backoff) handles this |

## New Commands Summary

| Command | Purpose |
|---------|---------|
| `sync-all [--incremental\|--force]` | Full reconciliation: Archive + Sprints + API Reference |
| `sync-sprints` | SPRINT.md → Sprints database |
| `push-api` | api-contract.md → API Reference database |
| `create-sprint-item <title> [--plan <path>]` | Create Sprint card + linked Archive record |
| `migrate [--dry-run]` | One-time migration from old databases to consolidated Archive |

Existing commands (`push`, `push-adrs`, `read-whiteboard`, `status`, `search`, `read-page`, `query-db`, `update-page`) remain unchanged except `read-whiteboard` queries the Sprint board dynamically.
