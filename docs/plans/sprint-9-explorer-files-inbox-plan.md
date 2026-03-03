# Sprint 9: Explorer — Files & Inbox (Split: 9A + 9B)

**Created:** 2026-03-03
**Status:** PLANNED
**Priority:** P0 — Core user-facing feature
**Estimated Effort:** Sprint 9A: ~8 days (~48 hours) | Sprint 9B: ~11 days (~66 hours) | **Total: ~19 days (~114 hours)**
**Audit:** `docs/plans/sprint-7-9-audit-2026-03-03.md`
**Prerequisites:** Sprint 7 (CacheManager, MarkdownEditorView, amber accent)

> **Audit decision (2026-03-03):** Original 14.5-day sprint split into two sub-sprints. Sprint 9A delivers Files (file system CRUD + security hardening). Sprint 9B delivers Inbox (email module + Gmail OAuth + unified inbox). This provides a natural review checkpoint, reduces risk, and avoids a 5-month mega-sprint.

---

## Objective

Build the full Explorer with two modes: Files (Finder integration + Notes) and Inbox (Apple Mail + Gmail unified inbox + Reminders + Notifications). Full CRUD on files, read-only email initially (compose deferred). Amber selected-tab accent.

## Deliverables

### Sprint 9A: Files (~8 days)
1. File system backend with security-hardened CRUD (new `routes/files.py`)
2. Files tab: Full Finder browsing with configurable hide-list, breadcrumb navigation
3. File preview and inline editing for text-based files (reuse MarkdownEditorView)
4. Notes integration via existing Apple Notes CLI
5. Amber tab selection accent matching sidebar
6. File operation audit trail with `user_id` scoping

### Sprint 9B: Inbox (~11 days)
7. Email backend module with provider pattern (Apple Mail read extension + Gmail OAuth2)
8. Shared `OAuthManager` base class (reused in Sprint 12 for Whoop)
9. Gmail OAuth2 integration with both localhost and Tailscale callback URLs
10. Unified inbox view: emails (read-only) + reminders + notifications
11. Inbox message detail view with thread context
12. Email compose/send deferred to Sprint 9C or later (read-only scope)

> **Audit decision:** Email compose/send is deferred. Read-only inbox (list + view) delivers 80% of user value at 30% of effort. Apple Mail `MailClient` is currently read-only — extending it for send/delete requires AppleScript automation that can be added incrementally.

---

## Task Breakdown

## Sprint 9A: Files

### 9.1 File System Backend (~4 days)

> **Audit adjustment (2026-03-03):** Increased from 3 to 4 days. Security-critical code (path validation, TOCTOU protection, audit trail) needs careful implementation. Also moved to separate route module per CTO review.

**New route file: `hestia/api/routes/files.py`** (NOT in `routes/explorer.py`)

> **Audit fix (T2):** File system CRUD is a different concern from Explorer resource aggregation. Different security posture, different audit requirements. Separate route module.

```
GET    /v1/explorer/files
  ?path=/Users/andrew/Documents
  ?show_hidden=false
  ?sort_by=name|date|size|type
  → { files: [FileEntry], path: str, parent_path: str|null }

GET    /v1/explorer/files/content
  ?path=/Users/andrew/file.md
  → { content: str, mime_type: str, size: int, modified: str }

POST   /v1/explorer/files
  { path: str, name: str, content: str?, type: "file"|"directory" }
  → { created: FileEntry }

PUT    /v1/explorer/files
  { path: str, content: str }
  → { updated: FileEntry }

DELETE /v1/explorer/files
  ?path=/Users/andrew/file.txt
  → { deleted: bool, moved_to_trash: bool }

  > **Audit fix (T4):** DELETE uses query param `?path=`, NOT request body. Most HTTP clients don't support DELETE with body. Consistent with GET pattern.

POST   /v1/explorer/files/move
  { source: str, destination: str }
  → { moved: FileEntry }

GET    /v1/explorer/files/hidden-paths
  → { paths: [str] }

PUT    /v1/explorer/files/hidden-paths
  { paths: [str] }
  → { updated: bool }
```

**New schema models:** `hestia/api/schemas/explorer.py`
```python
class FileEntry(BaseModel):
    name: str
    path: str
    type: Literal["file", "directory"]
    size: int                    # bytes
    modified: datetime
    mime_type: Optional[str]
    is_hidden: bool
    extension: Optional[str]

class FileListResponse(BaseModel):
    files: List[FileEntry]
    path: str
    parent_path: Optional[str]
    total: int

class FileContentResponse(BaseModel):
    content: str
    mime_type: str
    size: int
    modified: datetime
    encoding: str = "utf-8"
```

**Security implementation (hardened per audit 2026-03-03):**

> ⚠️ **Audit finding:** This sprint has the largest attack surface addition in the project. Dedicated security review required before merge.

```python
# Path validation — ALLOWLIST-FIRST approach (audit: deny-list is inherently incomplete)
# Everything is denied by default. Only ALLOWED_ROOTS are accessible.
ALLOWED_ROOTS = [
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Downloads"),
    os.path.expanduser("~/Projects"),
    # User can add more via hidden-paths config
]

# Additional safety: explicit deny-list as defense-in-depth
BLACKLISTED_PATHS = [
    "/System", "/Library", "/private", "/usr",
    os.path.expanduser("~/.ssh"),
    os.path.expanduser("~/.gnupg"),
    os.path.expanduser("~/.config/hestia/credentials"),
]

def validate_path(path: str) -> bool:
    # CRITICAL: Resolve symlinks at validation AND read time to prevent TOCTOU race
    resolved = os.path.realpath(path)
    # Allowlist check first (primary defense)
    if not any(resolved.startswith(root) for root in ALLOWED_ROOTS):
        return False
    # Deny-list as defense-in-depth
    for blocked in BLACKLISTED_PATHS:
        if resolved.startswith(blocked):
            return False
    return True

def safe_read(path: str) -> bytes:
    """Read file with TOCTOU-safe path validation."""
    # Open file descriptor immediately after validation
    validated = validate_path(path)
    if not validated:
        raise PermissionError(f"Access denied")
    # Re-resolve at read time (prevents symlink swap between validate and read)
    fd = os.open(os.path.realpath(path), os.O_RDONLY)
    try:
        return os.read(fd, MAX_CONTENT_SIZE)
    finally:
        os.close(fd)

# File size limit for content reads
MAX_CONTENT_SIZE = 10 * 1024 * 1024  # 10MB

# Delete = move to .hestia-trash/ first (audit: add undo capability), then macOS Trash
def safe_delete(path: str):
    # Log to file operation audit trail
    audit_logger.log_file_operation("delete", path, user_id)
    subprocess.run(["osascript", "-e",
        f'tell application "Finder" to delete POSIX file "{path}"'],
        check=True)
```

**File operation audit trail (audit addition):**
- All file CRUD operations (create, rename, move, delete) logged to SQLite audit table
- Fields: operation, path, **user_id** (scoped for multi-user readiness), device_id, timestamp, success/failure
- Delete operations can be undone via `.hestia-trash/` recovery (before macOS Trash empties)

**CISO Security Findings (E1–E4, mandatory):**

- **E1 — Filesystem boundary check:** `os.path.realpath()` can be confused by bind mounts and FUSE filesystems. Add explicit check that resolved path is on the **same filesystem** as the ALLOWED_ROOT:
  ```python
  import os
  def same_filesystem(path: str, root: str) -> bool:
      return os.stat(path).st_dev == os.stat(root).st_dev
  ```

- **E2 — AppleScript injection prevention:** The `osascript` delete command is vulnerable to shell metacharacters in file paths. Sanitize paths before passing:
  ```python
  import shlex
  safe_path = shlex.quote(os.path.realpath(path))
  ```

- **E3 — Executable MIME filtering:** File content reads must validate MIME type and refuse to serve executable files. Deny list: `.app`, `.sh`, `.command`, `.dmg`, `.pkg`, `.dylib`, `.so`, `.exec`.

- **E4 — ALLOWED_ROOTS per-user configurability:** Even with a single user, store ALLOWED_ROOTS in the user settings database (not hardcoded). This is cheap insurance for multi-user readiness and allows Andrew to customize without code changes.

### 9.2 Files Tab UI (~3 days)

**Files to create:**
- `macOS/Views/Explorer/ExplorerFilesView.swift` — File browser with breadcrumb nav
- `macOS/Views/Explorer/FileRowView.swift` — Icon + name + size + date per file
- `macOS/Views/Explorer/FilePreviewSheet.swift` — Quick Look-style preview
- `macOS/Views/Explorer/FileEditorView.swift` — Inline text editor (uses MarkdownEditorView)
- `macOS/Views/Explorer/HiddenPathsSheet.swift` — Configure hidden folders
- `macOS/Services/APIClient+Files.swift` — File system endpoint wrappers

**File browser layout:**
```
┌────────────────────────────────────────────────────┐
│  📁 Documents > Projects > Hestia                   │  ← Breadcrumb
│  ┌──────────────────────────────────────────────┐  │
│  │ 🔍 Search files...          [Grid] [List] ⚙️ │  │
│  ├──────────────────────────────────────────────┤  │
│  │ 📁 docs/              —      Mar 2   →      │  │
│  │ 📁 hestia/            —      Mar 3   →      │  │
│  │ 📄 CLAUDE.md          12KB   Mar 3   →      │  │
│  │ 📄 SPRINT.md          4KB    Mar 2   →      │  │
│  │ 🐍 server.py          8KB    Mar 1   →      │  │
│  └──────────────────────────────────────────────┘  │
│  [+ New File]  [+ New Folder]                       │
└────────────────────────────────────────────────────┘
```

**Features:**
- Breadcrumb navigation (click any segment to jump back)
- List view (default) and grid view toggle
- Sort by name/date/size/type (column headers clickable)
- File type icons (folder, text, code, image, PDF, etc.)
- Double-click file → preview or edit (text files open in MarkdownEditorView)
- Right-click context menu: Open, Edit, Rename, Move, Delete
- Drag-and-drop for move operations
- ⚙️ button → HiddenPathsSheet to configure hidden folders

---

## Sprint 9B: Inbox

### Pre-Sprint 9B Checklist (Audit Addition 2026-03-03)

Before Sprint 9B begins:

- [ ] **Google Cloud Console setup (Andrew — manual step, P4):** Create a Google Cloud project, configure OAuth consent screen, create OAuth2 credentials. Register BOTH callback URLs: `https://localhost:8443/v1/inbox/accounts/gmail/callback` AND `https://hestia-3.local:8443/v1/inbox/accounts/gmail/callback`. This blocks all Gmail work.
- [ ] **Sprint 9A review complete:** File system CRUD passing all tests, security review done.
- [ ] **Apple Mail write capability assessed:** Test `MailClient` read-only methods. Document which operations (send, delete, move) are feasible via AppleScript vs. requiring a new CLI tool.

### 9.3 Email Backend Module (~6 days)

> **Audit adjustment (2026-03-03):** Increased from 4 to 6 days. Building a new module from scratch with two providers, OAuth2, token management, and deduplication requires more time. Email scope reduced to **read-only** — list, view, mark-read. Compose/send deferred.

**New module:**
```
hestia/email/
├── __init__.py           # get_email_manager() factory
├── models.py             # EmailMessage, EmailAccount, EmailThread, Attachment
├── providers/
│   ├── __init__.py
│   ├── base.py           # BaseEmailProvider ABC
│   ├── apple_mail.py     # Wraps existing Apple CLI mail tool
│   └── gmail.py          # Google Gmail API (OAuth2)
├── manager.py            # EmailManager (aggregates all providers)
├── database.py           # SQLite cache for emails (offline support)
└── oauth.py              # OAuth2 flow helper
```

**EmailManager pattern:**
```python
class EmailManager:
    """Aggregates multiple email providers into unified inbox."""

    def __init__(self):
        self.providers: Dict[str, BaseEmailProvider] = {}

    async def add_provider(self, provider: BaseEmailProvider):
        self.providers[provider.name] = provider

    async def get_messages(self, provider: str = "all", folder: str = "inbox",
                          unread_only: bool = False, limit: int = 50) -> List[EmailMessage]:
        if provider == "all":
            results = await asyncio.gather(*[
                p.get_messages(folder, unread_only, limit)
                for p in self.providers.values()
            ])
            # Merge, deduplicate, sort by date, apply limit
            merged = list(chain(*results))
            deduplicated = self._deduplicate_by_message_id(merged)
            return sorted(deduplicated, key=lambda m: m.date, reverse=True)[:limit]
        return await self.providers[provider].get_messages(folder, unread_only, limit)

    def _deduplicate_by_message_id(self, messages: List[EmailMessage]) -> List[EmailMessage]:
        """Deduplicate emails that appear in both Apple Mail + Gmail by Message-ID header."""
        seen: Dict[str, EmailMessage] = {}
        for msg in messages:
            if msg.message_id not in seen:
                seen[msg.message_id] = msg
        return list(seen.values())
```

**Gmail OAuth2 flow (updated per audit 2026-03-03):**

> ⚠️ **Audit finding:** `localhost` callbacks won't work when accessing Hestia remotely via Tailscale. Use Hestia's own HTTPS endpoint with Tailscale DNS.

1. Google Cloud Console: Create OAuth2 credentials (one-time setup by Andrew)
2. Register BOTH callback URLs: `https://localhost:8443/v1/inbox/accounts/gmail/callback` AND `https://hestia-3.local:8443/v1/inbox/accounts/gmail/callback`
3. `POST /v1/inbox/accounts/gmail/authorize` → generates auth URL (detects local vs Tailscale access, selects appropriate callback URL)
4. macOS opens URL in browser → Andrew authorizes
5. Google redirects to appropriate callback URL
6. Backend exchanges code for refresh token → stores in Keychain **(`sensitive` credential tier — Fernet + Keychain)**
7. Subsequent calls: use refresh token to get short-lived access tokens

**Test OAuth flow from BOTH local and Tailscale connections before Sprint 9 ships.**

**Shared OAuthManager (audit addition):** Extract `OAuthManager` base class before implementing Gmail OAuth. This base class will be reused for Whoop in Sprint 12:
```python
class OAuthManager:
    """Base OAuth2 flow handler — shared by Gmail (Sprint 9) and Whoop (Sprint 12)."""
    async def generate_auth_url(self, provider: str, scopes: List[str]) -> str
    async def handle_callback(self, provider: str, code: str) -> TokenPair
    async def refresh_access_token(self, provider: str) -> str
    async def revoke_tokens(self, provider: str) -> bool
```

**Gmail API endpoints consumed:**
- `users.messages.list` — list messages
- `users.messages.get` — get message details (with body)
- `users.messages.send` — send email
- `users.messages.modify` — mark read/unread, star, move
- `users.messages.trash` — delete (move to trash)

**Apple Mail provider:** Wraps existing `hestia/apple/mail.py` MailClient. **Currently read-only** (reads Apple Mail SQLite database directly). Supports list, read, search. Send/delete/move require AppleScript automation — deferred to Sprint 9C.

> **Audit finding (T3):** No `hestia-cli-tools` mail CLI exists. The `MailClient` in `hestia/apple/mail.py` reads the Mail database directly. Do not assume write capabilities exist.

**Gmail OAuth2 token management:**
- Refresh tokens stored in Keychain (`sensitive` credential tier — Fernet + Keychain AES-256)
- Token rotation on every refresh (Google supports this — CISO recommendation)
- Health check endpoint to verify token validity without making API calls

**New API endpoints (read-only scope):**
```
GET    /v1/inbox/messages           — Unified message list (filterable by provider, unread)
GET    /v1/inbox/messages/{id}      — Message detail + thread
PUT    /v1/inbox/messages/{id}/read — Mark as read (lightweight state change, not full CRUD)

GET    /v1/inbox/accounts           — List email accounts + connection status
POST   /v1/inbox/accounts/gmail/authorize    — Start Gmail OAuth2
POST   /v1/inbox/accounts/gmail/callback     — Complete Gmail OAuth2
GET    /v1/inbox/accounts/gmail/status       — Token health check
DELETE /v1/inbox/accounts/{provider}         — Disconnect account + revoke tokens
```

**Deferred to Sprint 9C (or later):**
```
POST   /v1/inbox/messages           — Send email (requires Apple Mail write + Gmail send scope)
PUT    /v1/inbox/messages/{id}      — Update state (starred, folder move)
DELETE /v1/inbox/messages/{id}      — Move to trash
```

### 9.4 Inbox Tab UI (~3 days)

**Files to create:**
- `macOS/Views/Explorer/ExplorerInboxView.swift` — Unified inbox
- `macOS/Views/Explorer/InboxMessageRow.swift` — Message row (sender, subject, preview, date)
- `macOS/Views/Explorer/InboxMessageDetail.swift` — Full message view with actions
- `macOS/Views/Explorer/InboxComposeSheet.swift` — Email composer
- `macOS/Views/Explorer/GmailAuthSheet.swift` — OAuth2 flow UI
- `macOS/Views/Explorer/InboxFilterBar.swift` — Provider filter, unread toggle, search
- `macOS/Services/APIClient+Inbox.swift` — Inbox endpoint wrappers

**Inbox layout:**
```
┌────────────────────────────────────────────────────────┐
│ [All ▾] [Unread] 🔍 Search...                          │
│ ┌────────────────────────────────────────────────────┐ │
│ │ 📧 john@company.com              10:45 AM          │ │
│ │    Q4 Budget Review — Please review the...         │ │
│ │    ● unread  📎 1 attachment  [Gmail]               │ │
│ ├────────────────────────────────────────────────────┤ │
│ │ ⏰ Pay rent                       Due: Mar 5       │ │
│ │    Reminders  ○ incomplete                         │ │
│ ├────────────────────────────────────────────────────┤ │
│ │ 🔔 Daily Briefing ready          8:00 AM           │ │
│ │    Hestia Notification                              │ │
│ ├────────────────────────────────────────────────────┤ │
│ │ 📧 newsletter@substack.com       Yesterday         │ │
│ │    This Week in AI — The latest...                 │ │
│ │    [Apple Mail]                                     │ │
│ └────────────────────────────────────────────────────┘ │
│ [✉️ Compose]                                            │
└────────────────────────────────────────────────────────┘
```

**Inbox aggregates three sources:**
1. **Emails:** From Apple Mail + Gmail providers
2. **Reminders:** From existing Apple Reminders CLI (`GET /v1/explorer/resources?type=reminder`)
3. **Notifications:** From Hestia proactive system (`GET /v1/proactive/notifications`)

**Compose sheet (DEFERRED to Sprint 9C):**
~~To, CC, BCC fields, Subject, Rich text body, Account picker, Attachments~~ — requires Apple Mail write capabilities and Gmail send scope. Not in 9B scope.

**9B delivers:** Read-only unified inbox. Tap message → detail view. Mark as read. Filter by provider/unread. Search across all accounts.

### 9.5 Tab Design Update (~0.5 day)

**Amber selected tab:**
```swift
// In ExplorerView tab toggle
struct ExplorerTabButton: View {
    let title: String
    let icon: String
    let isSelected: Bool

    var body: some View {
        Button(action: { /* toggle */ }) {
            Label(title, systemImage: icon)
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
                .background(isSelected ? MacColors.amberAccent : Color.clear)
                .foregroundColor(isSelected ? .white : MacColors.textPrimary)
                .cornerRadius(8)
        }
    }
}
```

**Tab labels:**
- "Files" (was "Files") — keeps existing name
- "Inbox" (was "Resources") — renamed per spec

---

## Testing Plan

### Sprint 9A Tests (Files)

| Area | Test Count | Type |
|------|-----------|------|
| File list endpoint (various paths, sorts) | 5 | API |
| File content read (text, binary, oversized) | 4 | API |
| File CRUD (create, update, delete, move) | 6 | API |
| Path validation — allowlist enforcement | 3 | Security |
| Path traversal — symlink attacks | 2 | Security |
| Path traversal — `../` sequences + null bytes | 2 | Security |
| Path traversal — Unicode normalization | 1 | Security |
| Path traversal — TOCTOU race condition | 2 | Security |
| Path validation — filesystem boundary (E1) | 2 | Security |
| AppleScript injection prevention (E2) | 2 | Security |
| Executable MIME filtering (E3) | 2 | Security |
| File delete safety — BLACKLISTED_PATHS, non-existent, open handle | 3 | Security |
| File operation audit trail (with user_id) | 3 | Security |
| File upload size + content type validation | 2 | Security |
| Hidden paths configuration | 3 | API |
| DELETE endpoint uses query param (not body) | 1 | API |
| **9A Subtotal** | **~43** | |

### Sprint 9B Tests (Inbox)

| Area | Test Count | Type |
|------|-----------|------|
| EmailManager — multi-provider aggregation | 4 | Unit |
| EmailManager — deduplication by Message-ID | 2 | Unit |
| OAuthManager — base class token lifecycle | 3 | Unit |
| Gmail OAuth2 flow (authorize, callback, refresh) | 4 | Integration |
| Gmail OAuth2 — token refresh when expired | 2 | Integration |
| Gmail OAuth2 — refresh token expired (re-auth flow) | 1 | Integration |
| Gmail OAuth2 — concurrent refresh race | 1 | Integration |
| Gmail OAuth2 — Tailscale callback URL routing | 1 | Integration |
| Gmail OAuth2 — token rotation on refresh (CISO) | 1 | Integration |
| Apple Mail provider (list, read, search — read-only) | 3 | Integration |
| Inbox endpoints (list, detail, mark-read) | 4 | API |
| Email account management (add, status, disconnect) | 3 | API |
| Reminders integration in inbox | 3 | Integration |
| Notifications integration in inbox | 2 | Integration |
| Empty state — no accounts connected | 1 | UI |
| **9B Subtotal** | **~35** | |

| **Combined Total** | **~78** | |

## SWOT

| | Positive | Negative |
|---|---|---|
| **Strengths** | Apple CLI tools for Notes/Reminders exist. File system access unrestricted on Mac Mini. Gmail OAuth2 well-documented. Split into 9A/9B reduces risk per sprint. | Two sub-sprints still total ~19 days. File CRUD has largest security surface. Gmail OAuth2 requires Google Cloud Console setup (Andrew manual step). |
| **Opportunities** | Universal inbox with AI context is killer feature. File browsing makes Hestia a real OS companion. OAuthManager reused for Whoop in Sprint 12. | Apple Mail `MailClient` is read-only — write capabilities (send/delete/move) need future work. Gmail API has rate limits. |

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Path traversal vulnerability | Allowlist-first approach. `os.path.realpath()` at read time (not just validation). Open file descriptors immediately after validation to prevent TOCTOU. Null byte and Unicode normalization checks. |
| Gmail token expiry | Auto-refresh with retry via shared OAuthManager. Health check endpoint. Alert on persistent failure. |
| Gmail OAuth callback over Tailscale | Register both localhost and hestia-3.local callbacks. Auto-detect connection type. Test both paths. |
| Large directory listings (Downloads with 10K files) | Pagination (limit/offset). Lazy loading in UI. Server-side filtering. |
| Email delete accidents | Deferred — read-only inbox in 9B. Compose/delete in 9C. |
| Apple Mail write access | MailClient is read-only. Assess AppleScript feasibility in pre-9B checklist. Don't block inbox on this — read-only is sufficient. |
| Filesystem boundary bypass (E1) | Verify `st_dev` match between resolved path and ALLOWED_ROOT. |
| AppleScript injection (E2) | `shlex.quote()` all paths before passing to `osascript`. |

## Definition of Done

### Sprint 9A (Files)
- [ ] File CRUD in separate `routes/files.py` (not in `routes/explorer.py`)
- [ ] Files tab browses real filesystem with breadcrumb navigation
- [ ] Files: create, edit, rename, move, delete (to Trash) all working
- [ ] Hidden paths configurable and respected in listings
- [ ] ALLOWED_ROOTS stored in user settings (not hardcoded) — multi-user ready
- [ ] Notes visible in Files tab via existing integration
- [ ] Path validation: allowlist-first + TOCTOU-safe reads + filesystem boundary check (E1)
- [ ] AppleScript injection prevention via `shlex.quote()` (E2)
- [ ] Executable MIME type filtering on content reads (E3)
- [ ] DELETE endpoint uses `?path=` query param (not request body) (T4)
- [ ] File operation audit trail with `user_id` column (S4)
- [ ] Tab toggle uses amber accent
- [ ] Security review completed before merge
- [ ] All tests passing (existing + ~43 new from 9A)

### Sprint 9B (Inbox)
- [ ] Google Cloud Console configured (pre-sprint checklist item P4)
- [ ] Shared `OAuthManager` base class built (reusable for Whoop in Sprint 12)
- [ ] Gmail connected via OAuth2 flow (both localhost and Tailscale callbacks tested)
- [ ] Gmail token rotation on every refresh (CISO E3)
- [ ] Gmail tokens in `sensitive` credential tier (Fernet + Keychain)
- [ ] Inbox shows emails from Apple Mail + Gmail, unified and sorted (READ-ONLY)
- [ ] Reminders and Notifications visible in Inbox
- [ ] Email deduplication by Message-ID across providers
- [ ] "Resources" renamed to "Inbox"
- [ ] Empty state: "Connect your email accounts" when no providers configured
- [ ] Email compose/send NOT included (deferred to 9C) — read, list, mark-read only
- [ ] All tests passing (existing + ~35 new from 9B)
