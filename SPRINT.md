# Current Sprint: Explorer Files (Sprint 9A) — COMPLETE

**Started:** 2026-03-04
**Plan:** `docs/plans/2026-03-04-sprint-9a-explorer-files.md`
**Audit:** `docs/plans/sprint-9-plan-audit-2026-03-04.md`
**Master Roadmap:** `docs/plans/sprint-7-14-master-roadmap.md`

## Sprint 9A: Explorer Files — COMPLETE

### Summary
Security-hardened file system CRUD with audit trail. New `hestia/files/` module (models, security, database, manager). 9 API endpoints in `routes/files.py`. macOS file browser with breadcrumb nav, inline editing, and context menus. 66 new tests.

### Deliverables
- **Backend:** `hestia/files/` module — PathValidator (allowlist-first, TOCTOU-safe, null-byte, fs boundary), FileAuditDatabase (user-scoped), FileManager (CRUD + audit logging)
- **API:** 9 endpoints at `/v1/files/*` — list, content, metadata, create, update, delete, move, delete-post-alias, audit-log
- **macOS UI:** ExplorerFilesView replacing local FileManager, breadcrumb nav, sort/filter/search, FileContentSheet (preview + edit), HiddenPathsSheet
- **Config:** `hestia/config/files.yaml`, FileSettings in UserSettings (per-user allowed roots)
- **Audit conditions:** E5 (no osascript), E7 (null-byte), E8 (text-only content), T1 (SandboxRunner patterns), T2 (plural module), T3 (query param), T5 (noted for 9B)

### Test Results
- 66 new tests in `tests/test_files.py`
- 1378 total (1375 passing, 3 skipped)
- macOS build clean (xcodegen + xcodebuild verified)

---

## Next: Sprint 9B — Explorer: Inbox

**Plan:** `docs/plans/sprint-9-explorer-files-inbox-plan.md` (section 9B)
**Effort:** ~11 working days (~66 hours)

### Pre-Sprint 9B Checklist (Andrew — manual steps)
- [ ] **Create Google Cloud project** — OAuth consent screen + credentials
- [ ] **Register callback URLs** — `https://localhost:8443/v1/inbox/accounts/gmail/callback` AND `https://hestia-3.local:8443/v1/inbox/accounts/gmail/callback`
- [ ] **Test Tailscale callback URL** — verify Google accepts `hestia-3.local` as redirect URI
- [ ] **Decide:** OAuth token tier confirmed as OPERATIONAL (no Face ID)
- [ ] Apple Mail write capability assessment (read-only confirmed; send/delete/move deferred)

### Sprint 9B Scope
1. Email backend module (`hestia/email/`) — providers pattern (Apple Mail + Gmail)
2. Shared `OAuthManager` in `hestia/security/oauth.py` (reused by Whoop in Sprint 12)
3. Gmail OAuth2 with CSRF `state` parameter (audit E9)
4. 8 inbox API endpoints at `/v1/inbox/*` (read-only: list, detail, mark-read, accounts, auth)
5. macOS Inbox UI in Explorer — unified view of emails + reminders + notifications
6. ~35 new tests

### Key Audit Conditions for 9B
- E6: OPERATIONAL tier for Gmail tokens (confirmed by Andrew)
- E9: Gmail OAuth `state` parameter with HMAC for CSRF prevention
- T4: Route file named `routes/inbox.py` (not `routes/email.py`)
- T5: OAuthManager in `hestia/security/oauth.py` (shared infrastructure)

---

## Previous: Research & Graph + PrincipleStore (Sprint 8) — COMPLETE

**Started:** 2026-03-03
**Plan:** `docs/plans/sprint-8-research-graph-plan.md`

### Sprint 8 Summary
- **B1:** Research module scaffold — `hestia/research/` (models.py, database.py, __init__.py). 32 tests.
- **B2:** Graph builder — memory/topic/entity nodes, 4 edge types, 3D layout, clustering. 51 total tests.
- **B3:** PrincipleStore (ChromaDB `hestia_principles`), ResearchManager, 6 API routes.
- **C1-C3:** macOS frontend — APIClient+Research, ViewModel refactor, GraphControlPanel, NodeDetailPopover, PrinciplesView.
- **D1:** Decision Gate 1 — GO. 124 chunks, 142ms. ADR-039.

---

## Previous: Profile & Settings Restructure (Sprint 7) — COMPLETE

**Started:** 2026-03-03

- **A1:** Accent color audit, VoiceOver accessibility, design tokens
- **A2:** MarkdownEditorView line numbers, roadmap verification

---

## Previous: Stability & Efficiency (Sprint 6) — COMPLETE

Readiness gate, complete shutdown (15 managers), Uvicorn recycling, parallel init, pip-compile lockfile, log compression, Cache-Control.

---

## Previous Sprints (1-5): COMPLETE

Full details in `SESSION_HANDOFF.md` and git history.
