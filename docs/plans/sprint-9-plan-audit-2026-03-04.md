# Plan Audit: Sprint 9 — Explorer: Files (9A) + Inbox (9B)

**Date:** 2026-03-04
**Auditor:** Claude (Plan Audit Agent)
**Verdict:** APPROVE WITH CONDITIONS
**Previous audit:** `docs/plans/sprint-7-9-audit-2026-03-03.md` (conditions from that audit incorporated into this plan)

## Plan Summary

Sprint 9 builds Hestia's Explorer into a full-featured file browser (9A) and unified email inbox (9B). Sprint 9A adds file system CRUD with security-hardened path validation, audit trail, and a macOS file browser UI. Sprint 9B adds a new email module with Apple Mail + Gmail OAuth2 providers, shared OAuthManager base class, and a read-only unified inbox UI. Combined effort: ~19 working days (~114 hours). This is the highest-security-risk sprint in the project due to direct filesystem access and external OAuth flows.

---

## Scale Assessment

| Scale | 9A (Files) | 9B (Inbox) | Cost to Fix Later |
|-------|-----------|-----------|-------------------|
| **Single user** | Works | Works | N/A |
| **Family (2-5)** | **RISK.** ALLOWED_ROOTS are per-config, not per-user. All authenticated users share filesystem access. Plan specifies E4 (per-user ALLOWED_ROOTS in settings DB) — if implemented, works. | Works. Gmail OAuth tokens scoped to provider+user via Keychain keys. Apple Mail is device-local. | Files: LOW if E4 implemented now. HIGH if hardcoded. Inbox: LOW. |
| **Community (10+)** | **BREAKS.** No per-user sandboxing. Any authenticated user can traverse any ALLOWED_ROOT. Needs virtual filesystem or container isolation. | **RISK.** Gmail API quotas shared across all users. No per-user rate limiting on email endpoints. | Files: HIGH. Inbox: MEDIUM. |

**Key finding:** The plan's E4 condition (ALLOWED_ROOTS in user settings) is **essential**, not nice-to-have. Without it, multi-user is architecturally blocked. The existing `UserSettings` dataclass in `hestia/user/models.py` stores settings as a JSON blob — adding `allowed_roots: List[str]` is straightforward.

**New finding:** The plan doesn't address **user_id scoping on file audit logs**. The multi-user rules in `.claude/rules/multi-user.md` mandate `user_id` on all new tables. The plan mentions `user_id` in the audit trail but doesn't show it in the query patterns. **Must enforce.**

---

## Front-Line Engineering Review

### Sprint 9A: Files

**Feasibility: HIGH.** The codebase already has the building blocks:
- `SandboxRunner.is_path_allowed()` uses `Path.resolve()` + `relative_to()` — proven pattern
- `execution.yaml` already defines `allowed_directories` — Sprint 9A needs its own allowlist (separate concern from execution sandbox)
- `BaseDatabase` ABC is battle-tested across 11 modules
- Explorer routes (`routes/explorer.py`) provide the registration pattern

**Hidden prerequisites:**
1. **LogComponent.FILE** must be added to the enum (not `FILE_AUDIT` — keep it simple, consistent with other single-word components like `EXPLORER`, `WIKI`, `HEALTH`)
2. **`auto-test.sh` mapping** for `hestia/files/*` → `tests/test_files.py`
3. **`validate-security-edit.sh`** must add `hestia/files/` and `hestia/api/routes/files.py` to its security file list — these handle filesystem access
4. The plan's `safe_delete()` uses `osascript` for Finder trash. macOS Finder scripting requires the app to be running. On a headless Mac Mini, Finder may not be active. **Alternative: use `trash` CLI** (`brew install trash`) or Python's `send2trash` package, or simply `shutil.move()` to `.hestia-trash/`.

**Effort assessment:**
- File system backend: 4 days (plan says 4) — **ACCURATE.** TOCTOU protection, allowlist, audit trail, 8 endpoints. Tight but achievable.
- Files tab UI: 3 days (plan says 3) — **ACCURATE.** Existing `ExplorerView.swift` has the segmented control pattern. `MarkdownEditorView` (NSRulerView + NSTextView) already exists from Sprint 7.
- **Total 9A: ~7-8 days.** Plan says 8. Agree.

**Testing gaps (beyond what's in the plan):**
- No test for **headless Mac Mini** (Finder not running → osascript trash fails)
- No test for **concurrent file operations** (two requests writing to same file)
- No test for **iCloud placeholder files** (`.icloud` eviction files in iCloud Drive)
- No test for **file locked by another process** (e.g., Excel has file open)
- No test for **path with non-UTF-8 characters** in filename

### Sprint 9B: Inbox

**Feasibility: MEDIUM.** New module from scratch with external dependency (Google OAuth).

**Hidden prerequisites:**
1. **Google Cloud Console setup** — Andrew must create project, configure OAuth consent screen, create credentials, register both callback URLs. This blocks ALL Gmail work. **Do this before 9B starts.**
2. **`google-api-python-client` + `google-auth-oauthlib`** — new dependencies. Add to `requirements.in`, regenerate lockfile. Verify no conflicts with existing packages (especially `httplib2` vs `httpx`).
3. **Apple Mail database path varies by macOS version.** Current `MailClient` uses `~/Library/Mail/V10/MailData/Envelope Index`. On macOS 15.x+ this may change. The client should detect the path, not hardcode it.
4. **Shared `OAuthManager`** — the plan says "extract before Sprint 9B" but there's nothing to extract. This is a net-new abstraction. Budget it into 9B.

**Effort assessment:**
- Email backend module: 6 days (plan says 6) — **ACCURATE** for read-only scope. Two providers + OAuth flow + token lifecycle + manager pattern + dedup.
- Inbox tab UI: 3 days (plan says 3) — **ACCURATE** since compose is deferred. List + detail + filter + Gmail auth sheet.
- OAuthManager base class: included in the 6 days — tight but acceptable.
- **Total 9B: ~11 days.** Plan says 11. Agree.

**Testing gaps:**
- No test for **Gmail API rate limit response** (429 Too Many Requests → backoff)
- No test for **Apple Mail database locked** (Mail.app updating while we query)
- No test for **Gmail token revocation by user** (user revokes access in Google Account settings)
- No test for **network timeout** during OAuth callback exchange
- No test for **email with non-ASCII subject/sender** (RFC 2047 encoded headers)

---

## Architecture Review

### API Design

**9A File endpoints — ISSUES FOUND:**

| Endpoint | Issue | Fix |
|----------|-------|-----|
| `DELETE /v1/explorer/files?path=` | Query param for DELETE is correct per previous audit (T4) | OK |
| `PUT /v1/explorer/files` | Body contains `{path, content}`. Path in body is inconsistent with GET/DELETE using query param. | Use `?path=` query param + body for content only |
| `POST /v1/explorer/files/move` | POST for idempotent operation. Move is better as PUT. | Change to `PUT /v1/explorer/files/move` or keep POST (non-idempotent if destination changes) |
| `GET/PUT /v1/explorer/files/hidden-paths` | This is a user setting, not a file operation. | Move to `/v1/user/settings/file-access` or keep under explorer for UI simplicity |

**Recommendation:** Standardize path parameter handling. GET and DELETE use `?path=` query param. POST (create) and PUT (update content) use body. This matches HTTP semantics.

**9B Inbox endpoints — CLEAN.** Read-only scope makes the API simple. `PUT /v1/inbox/messages/{id}/read` for mark-as-read is correct (state mutation, not full update).

### Route Module Separation

The previous audit (T2) correctly mandated `routes/files.py` separate from `routes/explorer.py`. **Verified: this is in the plan.** The concerns are genuinely different:
- `explorer.py`: Resource aggregation (mail + notes + reminders + drafts). Business logic.
- `files.py`: Direct filesystem CRUD. Security-critical.

**For 9B:** Create `routes/inbox.py` (NOT `routes/email.py`). The UI is "Inbox", the endpoints are `/v1/inbox/*`. Name the route file to match.

### Data Model

**9A FileEntry model — GOOD.** Clean, minimal. One addition: `permissions: Optional[str]` (e.g., "rw-r--r--") for display and validation.

**9A File audit table — NEEDS user_id.** Per `.claude/rules/multi-user.md`:
```sql
CREATE TABLE file_audit (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,    -- from JWT device_id → user mapping
    device_id TEXT NOT NULL,  -- which device performed the operation
    operation TEXT NOT NULL,  -- create|read|update|delete|move
    path TEXT NOT NULL,
    destination_path TEXT,    -- for move operations
    result TEXT NOT NULL,     -- success|denied|error
    timestamp TEXT NOT NULL,
    metadata TEXT DEFAULT '{}'
);
CREATE INDEX idx_file_audit_user ON file_audit(user_id, timestamp DESC);
```

**9B EmailMessage model — needs `provider` field.** The plan shows `message_id` for dedup but doesn't show which provider the message came from. Add `provider: str` (e.g., "apple_mail", "gmail") to the model.

### Credential Tier Discrepancy

**CRITICAL FINDING:** The plan says Gmail OAuth tokens go in `sensitive` tier (Fernet + Keychain + Face ID). But the codebase exploration reveals:
- **OPERATIONAL** tier = API keys, OAuth tokens — no mandatory biometric
- **SENSITIVE** tier = SSN, financial data — requires Face ID

Gmail OAuth tokens are API tokens, NOT personal financial data. **Use OPERATIONAL tier**, not SENSITIVE. Face ID on every email sync would be terrible UX.

**However:** The master roadmap (`sprint-7-14-master-roadmap.md` line 122) explicitly says "Gmail/Whoop OAuth2 tokens in Keychain — **`sensitive` credential tier**". This is a design decision, not a bug.

**Recommendation:** Escalate to Andrew. If the intent is heightened security for third-party OAuth tokens (reasonable — they grant access to email), keep SENSITIVE. If the intent is practical usability, use OPERATIONAL. The biometric prompt on every token refresh would be disruptive.

### Dependency Analysis

**New dependencies for 9B:**
| Package | Size | License | Risk |
|---------|------|---------|------|
| `google-api-python-client` | ~10MB | Apache 2.0 | LOW — Google-maintained, widely used |
| `google-auth-oauthlib` | ~1MB | Apache 2.0 | LOW |
| `google-auth-httplib2` | ~100KB | Apache 2.0 | LOW |

**Conflict check:** `httplib2` may conflict with `httpx` (used elsewhere in Hestia). Verify in `requirements.in` that both can coexist. They should — different HTTP stacks, no shared namespace.

**Alternative considered:** Use `google-auth` with `httpx` directly instead of `httplib2`. Cleaner, fewer dependencies. But Google's official client only supports `httplib2` and `requests`. Stick with official client.

---

## Product Review

### User Value: VERY HIGH

Sprint 9 transforms Hestia from "AI chatbot with settings" to "OS companion that sees your files and email." This is the sprint that makes Hestia feel like Jarvis.

**9A delivers:**
- Browse real filesystem from Hestia's UI
- Edit text files inline (markdown, code, notes)
- Create/move/delete files without switching to Finder
- Full audit trail for accountability

**9B delivers:**
- See all email in one place (Apple Mail + Gmail)
- No more switching between mail apps
- Reminders and notifications alongside email
- Foundation for AI-powered email summarization (future)

### Scope Assessment: RIGHT-SIZED (after split)

The original Sprint 9 was too big (19 days). The 9A/9B split is correct. Each sub-sprint delivers a complete, usable feature.

**9A is the right first step.** File browsing has zero external dependencies (no OAuth, no Google Console setup). It can be built and tested entirely locally. Security hardening is self-contained.

**9B has the external dependency risk** (Google Cloud Console). Starting with 9A gives Andrew time to set up Google credentials while files are being built.

### Opportunity Cost

While building Explorer, we're NOT building:
- **Chat Redesign (Sprint 10)** — the most-used view daily
- **OutcomeTracker** — prerequisite for the Learning Cycle critical path

This is acceptable: the dependency chain says 9A/9B before 10. And files/email are higher user-value than chat polish.

### Edge Cases

| Scenario | 9A Handling | 9B Handling |
|----------|------------|------------|
| **Empty state** | "No files in this directory" | "Connect your email accounts to get started" |
| **First-time user** | Default to ~/Documents as starting directory | Gmail auth sheet on first visit to Inbox tab |
| **Offline/disconnected** | Works (local filesystem) | Apple Mail works (local DB). Gmail fails gracefully with "Last synced X ago" |
| **Large data** | 10K files in Downloads → pagination (plan specifies limit/offset) | 1000 unread emails → server-side pagination + client lazy loading |
| **Permission denied** | System-level file permissions (macOS TCC) → graceful error "Access denied to this directory" | Gmail token expired → auto-refresh. If refresh fails → "Re-authorize Gmail" prompt |

---

## UX Review

### Design System Compliance

**Amber accent:** Plan correctly uses `MacColors.amberAccent` for selected tab. Previous audit FIX-2 (amber vs orange palette) was resolved in Sprint 7 — amber is the canonical accent.

**Tab design:** The existing `ExplorerView.swift` has a segmented control (Files/Resources). Sprint 9A adds a third segment or replaces "Resources" with "Inbox" (9B). Verify that 3 segments fit in the ExplorerView header without truncation.

### Interaction Model

**File browser:**
- Breadcrumb navigation: Excellent. Familiar pattern from Finder/Explorer.
- Double-click to open: Standard. But needs clear visual distinction between "open file" and "enter directory."
- Right-click context menu: macOS native. Good.
- **Missing: keyboard navigation.** Arrow keys to move through file list, Enter to open, Delete to trash, ⌘N for new file. Essential for power users.

**Inbox:**
- Unified timeline sorted by date: Good.
- Provider badges ([Gmail], [Apple Mail]): Helps disambiguation.
- **Missing: pull-to-refresh indicator.** Need visual feedback during email sync.

### Platform Parity

Sprint 9 is **macOS-only** for UI. iOS Explorer exists but is simpler (resource list, not file browser). This is acceptable divergence — file browsing is a desktop experience. But document that iOS gets no changes in this sprint.

### Accessibility

**Not addressed in plan. Must add:**
- File list: VoiceOver labels for each row (filename, size, type, modified date)
- Breadcrumb: Accessibility navigation (each segment is a button with label)
- Inbox messages: VoiceOver reading order (sender, subject, preview, date)
- Tab selection: `accessibilityAddTraits(.isSelected)` on active tab

---

## Infrastructure Review

### Deployment Impact

| Item | Impact |
|------|--------|
| Server restart required | YES (new routes, new managers) |
| Database migration | YES (new `file_audit` table — auto-created via `_init_schema()`) |
| Config changes | YES (new `files.yaml` or additions to `execution.yaml`) |
| Google Cloud Console | YES (9B only — manual Andrew step) |
| New Python packages | YES (9B: google-api-python-client, google-auth-oauthlib) |
| Xcodegen rebuild | YES (new Swift files in macOS target) |

### New Dependencies

**9A: NONE.** Pure Python stdlib (`os`, `pathlib`, `shutil`, `mimetypes`). Zero new packages.

**9B:**
- `google-api-python-client==2.x` — pin in `requirements.in`
- `google-auth-oauthlib==1.x` — pin in `requirements.in`
- `google-auth-httplib2==0.x` — transitive dependency
- Run `pip-compile requirements.in` to regenerate lockfile

### Monitoring

**9A:**
- File operation audit trail (SQLite) — primary monitoring
- `LogComponent.FILE` structured logs for all operations
- Track: operations/hour, denied/allowed ratio, average response time for listings

**9B:**
- Gmail API error rates (log 4xx/5xx responses)
- Token refresh success/failure rate
- Email sync latency
- Provider health check endpoint (`GET /v1/inbox/accounts/gmail/status`)

### Rollback Strategy

**9A: CLEAN.** Remove `routes/files.py` registration from server.py, drop `file_audit` table, restart. No external state.

**9B: MESSY.** Gmail OAuth tokens stored in Keychain persist after code rollback. Need cleanup procedure:
1. Revoke Google OAuth tokens via API (`POST https://oauth2.googleapis.com/revoke`)
2. Delete Keychain entries via CredentialManager
3. Remove `routes/inbox.py` registration
4. Drop email cache table
5. Restart

**Recommendation:** Build a `/v1/inbox/accounts/{provider}/disconnect` endpoint that handles steps 1-2. This is already in the plan. Good.

### Resource Impact

**Mac Mini M1 (16GB):**
- File listings: Negligible. `os.scandir()` is lazy, pagination limits memory.
- Email cache: SQLite, ~1MB per 10K emails. Negligible.
- Gmail API client: ~15MB in-memory for the client library. Acceptable.
- **Concern:** Large file content reads (10MB limit in plan). Single request could temporarily consume 10MB. With concurrent requests, could spike. The 10MB limit is appropriate — don't increase it.

---

## Executive Verdicts

### CISO Review

**Verdict: APPROVE WITH CONDITIONS**

Sprint 9A adds the largest attack surface in the project's history. The plan addresses this with allowlist-first design, TOCTOU protection, and audit trail. My conditions:

| ID | Finding | Severity | Status in Plan |
|----|---------|----------|----------------|
| **E1** | Filesystem boundary check (`st_dev` match) | HIGH | In plan ✓ |
| **E2** | AppleScript injection (`shlex.quote()`) | HIGH | In plan ✓ |
| **E3** | Executable MIME filtering | MEDIUM | In plan ✓ |
| **E4** | ALLOWED_ROOTS per-user in settings DB | HIGH | In plan ✓ |
| **E5** (NEW) | `osascript` Finder trash fails on headless Mac Mini | MEDIUM | **NOT in plan** — use `shutil.move()` to `.hestia-trash/` instead |
| **E6** (NEW) | Gmail OAuth token tier: plan says SENSITIVE, should be OPERATIONAL for UX | MEDIUM | **Escalate to Andrew** |
| **E7** (NEW) | No null-byte sanitization in path validation | HIGH | Plan mentions it in test list but not in `validate_path()` code |
| **E8** (NEW) | File content response should never include raw binary for non-text MIME types | MEDIUM | **NOT in plan** — add MIME type check before content read |
| **E9** (NEW) | Gmail callback endpoint must validate `state` parameter to prevent CSRF | HIGH | **NOT in plan** — standard OAuth2 security requirement |

**Conditions for CISO approval:**
1. E5: Replace `osascript` trash with `shutil.move()` to `.hestia-trash/{timestamp}/` — works headless
2. E6: Decide OAuth token tier with Andrew before implementation
3. E7: Add explicit null-byte check in `validate_path()`: `if '\x00' in path: raise`
4. E8: Only serve content for text/* MIME types. Return metadata-only for binary files.
5. E9: Gmail OAuth must use `state` parameter with HMAC to prevent CSRF on callback

### CTO Review

**Verdict: APPROVE WITH CONDITIONS**

Architecture is sound. The plan correctly separates `routes/files.py` from `routes/explorer.py` (T2 from previous audit). Manager pattern is consistent. My conditions:

| ID | Finding | Severity |
|----|---------|----------|
| **T1** | Reuse `SandboxRunner.is_path_allowed()` pattern, don't reinvent path validation | MEDIUM |
| **T2** | Create `hestia/files/` module (not `hestia/file/`) — plural matches `hestia/orders/`, `hestia/agents/`, `hestia/tasks/` | LOW |
| **T3** | `PUT /v1/explorer/files` path-in-body inconsistency — standardize to `?path=` query param for path, body for content only | MEDIUM |
| **T4** | Create `routes/inbox.py` (not `routes/email.py`) — route name should match UI name | LOW |
| **T5** (NEW) | OAuthManager should live in `hestia/security/oauth.py`, not `hestia/email/oauth.py` — it's shared infrastructure (reused by Whoop in Sprint 12) | MEDIUM |
| **T6** (NEW) | File browser should respect `.gitignore` patterns optionally — many directories under ~/Documents/Projects contain `node_modules/`, `.git/`, build artifacts that are noise | LOW |
| **T7** (NEW) | Consider `mimetypes.guess_type()` for MIME detection instead of custom mapping — stdlib, no dependencies, handles edge cases | LOW |

**Conditions for CTO approval:**
1. T1: Extract path validation into a shared utility in `hestia/files/security.py` that wraps `SandboxRunner` patterns with the TOCTOU-safe additions
2. T5: Place `OAuthManager` in `hestia/security/oauth.py` — it's a security concern, not email-specific

### CPO Review

**Verdict: APPROVE**

Sprint 9 delivers the highest user-value feature since the chat interface. File browsing makes Hestia a real tool, not just a chatbot. The 9A/9B split is correct — ship files fast, email next.

| ID | Finding | Priority |
|----|---------|----------|
| **P1** | Ship 9A first, let Andrew use it while 9B is in development | HIGH |
| **P2** | Gmail auth flow must be frictionless — Andrew should authorize once and never think about it again | HIGH |
| **P3** | Default starting directory should be `~/Documents`, not root | LOW |
| **P4** | Add "Open in Finder" button on file detail — escape hatch to native OS | LOW |
| **P5** (NEW) | Consider adding file search across ALL allowed roots (not just current directory) — this is the killer feature vs. Finder | MEDIUM |
| **P6** (NEW) | Inbox empty state should show a one-click "Connect Gmail" button, not just text | LOW |

---

## Final Critiques

### 1. Most Likely Failure

**`osascript` Finder trash will fail on headless Mac Mini.**

The plan's `safe_delete()` uses `osascript -e 'tell application "Finder" to delete POSIX file...'`. On the Mac Mini running as a server (no active user session or Finder process), this will fail silently or error. This is the most likely production failure because it works in development (Finder running) but breaks in deployment.

**Mitigation:** Replace with Python-native approach:
```python
import shutil
from datetime import datetime

TRASH_DIR = Path("~/.hestia-trash").expanduser()

def safe_delete(path: str, user_id: str) -> None:
    resolved = Path(os.path.realpath(path))
    trash_dest = TRASH_DIR / datetime.now().strftime("%Y%m%d_%H%M%S") / resolved.name
    trash_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(resolved), str(trash_dest))
    # Log to audit trail
    audit_logger.log("delete", str(resolved), user_id, metadata={"trash_path": str(trash_dest)})
```

This is simpler, works headless, provides undo, and avoids the AppleScript injection risk (E2) entirely.

### 2. Critical Assumption

**Gmail OAuth callback will work over Tailscale.**

The plan registers two callback URLs: `localhost:8443` and `hestia-3.local:8443`. But Google OAuth requires callbacks to be HTTPS with a valid domain. `hestia-3.local` is a Tailscale MagicDNS name — Google may not accept it during OAuth consent screen configuration.

**Validation approach:** Before Sprint 9B starts, Andrew should:
1. Create the Google Cloud project
2. Try registering `https://hestia-3.local:8443/v1/inbox/accounts/gmail/callback` as a redirect URI
3. If Google rejects it (likely — it's not a public domain), fall back to `localhost` only + require local network for initial auth, then use refresh tokens remotely

**If this assumption fails:** Gmail OAuth auth flow must happen on local network. Ongoing email sync (using refresh tokens) works from anywhere. This is acceptable but must be documented.

### 3. Half-Time Cut List

If Sprint 9 had to ship in 10 days instead of 19:

**CUT from 9A (8 → 5 days):**
- Drag-and-drop file move (use context menu only)
- Grid view toggle (list view only)
- File search within directory (defer — just browsing)
- **KEEP:** CRUD operations, security hardening, breadcrumb nav, audit trail, MarkdownEditor integration, hidden paths config

**CUT from 9B (11 → 5 days):**
- Gmail OAuth entirely (Apple Mail read-only only)
- OAuthManager base class (defer to Sprint 12 when Whoop needs it)
- Reminders/Notifications in inbox (email only)
- **KEEP:** Apple Mail inbox (list + detail), mark-as-read, filter by unread, provider badge

**Half-time priority reveals:** The file CRUD security hardening and Apple Mail inbox are the core value. Gmail and OAuthManager are the stretch goals. If time gets tight, ship without Gmail and add it in a 9B.5 patch.

---

## Conditions for Approval

### Must-Fix Before Execution

| ID | Sprint | Condition | Owner |
|----|--------|-----------|-------|
| **E5** | 9A | Replace `osascript` Finder trash with Python-native `.hestia-trash/` move | Claude |
| **E6** | 9B | Decide Gmail OAuth token tier (OPERATIONAL vs SENSITIVE) | Andrew |
| **E7** | 9A | Add null-byte sanitization to `validate_path()` | Claude |
| **E8** | 9A | Only serve content for text/* MIME types; metadata-only for binary | Claude |
| **E9** | 9B | Gmail OAuth must use `state` parameter with HMAC for CSRF prevention | Claude |
| **T1** | 9A | Reuse/extend SandboxRunner patterns for path validation | Claude |
| **T5** | 9B | Place OAuthManager in `hestia/security/oauth.py` (shared infra) | Claude |

### Must-Fix During Execution

| ID | Sprint | Condition | Owner |
|----|--------|-----------|-------|
| **T2** | 9A | Module name `hestia/files/` (plural) | Claude |
| **T3** | 9A | Standardize PUT path parameter to query param | Claude |
| **T4** | 9B | Route file named `routes/inbox.py` | Claude |
| **T6** | 9A | Optional `.gitignore` pattern filtering for project directories | Claude |
| **P5** | 9A | Cross-root file search capability | Claude |

### Pre-Sprint Checklist (Andrew)

| Item | Sprint | Blocks |
|------|--------|--------|
| Decide OAuth token tier (OPERATIONAL vs SENSITIVE) | 9B | All Gmail implementation |
| Create Google Cloud project + OAuth credentials | 9B | All Gmail implementation |
| Test Tailscale callback URL registration with Google | 9B | Remote Gmail auth |
| Review ALLOWED_ROOTS defaults (Documents, Desktop, Downloads, Projects?) | 9A | File browser scope |

### Should-Do (Best Practice)

| ID | Sprint | Condition |
|----|--------|-----------|
| S1 | 9A | Keyboard navigation in file browser (arrow keys, Enter, Delete) |
| S2 | 9A | VoiceOver labels on all file browser elements |
| S3 | 9A | "Open in Finder" escape hatch button |
| S4 | 9B | "Last synced X minutes ago" indicator for email |
| S5 | 9B | Gmail API rate limit handling with exponential backoff |
| S6 | Both | Dynamic Type support in all new views |

---

## Revised Architecture Wiring Diagram

```
┌─────────────── Sprint 9A: Files ───────────────┐
│                                                  │
│  macOS UI                                        │
│  ├── ExplorerFilesView.swift (new)              │
│  ├── FileRowView.swift (new)                    │
│  ├── FilePreviewSheet.swift (new)               │
│  ├── FileEditorView.swift (reuses MarkdownEd)   │
│  ├── HiddenPathsSheet.swift (new)               │
│  └── APIClient+Files.swift (new)                │
│           │                                      │
│           ▼                                      │
│  Backend                                         │
│  ├── hestia/api/routes/files.py (new, 8 endpts) │
│  ├── hestia/api/schemas/files.py (new)          │
│  ├── hestia/files/ (new module)                 │
│  │   ├── models.py (FileEntry, AuditLog)        │
│  │   ├── database.py (FileAuditDatabase)        │
│  │   ├── security.py (PathValidator)            │
│  │   └── manager.py (FileManager)               │
│  └── hestia/config/files.yaml (new)             │
│           │                                      │
│           ▼                                      │
│  Infrastructure                                  │
│  ├── SandboxRunner (reuse patterns)             │
│  ├── AuditLogger (existing)                     │
│  ├── UserSettings (store ALLOWED_ROOTS)         │
│  └── LogComponent.FILE (new enum value)         │
└──────────────────────────────────────────────────┘

┌─────────────── Sprint 9B: Inbox ───────────────┐
│                                                  │
│  macOS UI                                        │
│  ├── ExplorerInboxView.swift (new)              │
│  ├── InboxMessageRow.swift (new)                │
│  ├── InboxMessageDetail.swift (new)             │
│  ├── GmailAuthSheet.swift (new)                 │
│  ├── InboxFilterBar.swift (new)                 │
│  └── APIClient+Inbox.swift (new)                │
│           │                                      │
│           ▼                                      │
│  Backend                                         │
│  ├── hestia/api/routes/inbox.py (new, 8 endpts) │
│  ├── hestia/email/ (new module)                 │
│  │   ├── models.py (EmailMessage, Account)      │
│  │   ├── database.py (EmailCacheDatabase)       │
│  │   ├── manager.py (EmailManager)              │
│  │   └── providers/                             │
│  │       ├── base.py (BaseEmailProvider ABC)    │
│  │       ├── apple_mail.py (wraps MailClient)   │
│  │       └── gmail.py (Google API client)       │
│  ├── hestia/security/oauth.py (NEW - shared)    │
│  └── hestia/config/email.yaml (new)             │
│           │                                      │
│           ▼                                      │
│  Infrastructure                                  │
│  ├── CredentialManager (OAuth token storage)    │
│  ├── Apple Mail MailClient (existing, read-only)│
│  ├── Google API Python Client (new dep)         │
│  └── LogComponent.EMAIL (new enum value)        │
└──────────────────────────────────────────────────┘
```

---

## Test Plan Summary

| Category | 9A Count | 9B Count | Total |
|----------|----------|----------|-------|
| API endpoints | 12 | 10 | 22 |
| Security (path validation, TOCTOU, injection) | 18 | 3 | 21 |
| Unit (manager, models, dedup) | 5 | 8 | 13 |
| Integration (OAuth, providers, Apple Mail) | 3 | 12 | 15 |
| Edge cases (large dirs, locked files, encoding) | 5 | 4 | 9 |
| **Subtotal** | **~43** | **~37** | **~80** |

Existing test count: 1312. After Sprint 9: ~1392 tests.

---

## Comparison with Previous Audit (2026-03-03)

| Previous Condition | Status |
|-------------------|--------|
| T1: Split Sprint 9 into 9A + 9B | ✅ In plan |
| T2: Separate routes/files.py | ✅ In plan |
| T3: Read-only email scope | ✅ In plan |
| T4: DELETE uses query param | ✅ In plan |
| E1-E4: CISO findings | ✅ All in plan |
| P4: Google Cloud Console pre-checklist | ✅ In plan |
| S4: user_id in file audit trail | ✅ In plan |

**All conditions from previous audit are addressed.** This audit adds 9 new findings (E5-E9, T5-T7, P5-P6).
