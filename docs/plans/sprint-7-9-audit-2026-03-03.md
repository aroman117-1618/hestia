# Plan Audit: Sprints 7–9 (Profile, Research, Explorer)

**Date:** 2026-03-03
**Auditor:** Claude (Plan Audit Agent)
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary

Three sequential sprints transforming Hestia's macOS app from a partially-wired demo into a fully live, editable, persistent application. Sprint 7 restructures Settings as a 4-section accordion with full profile/agent editing. Sprint 8 builds a research backend with knowledge graph and PrincipleStore (Learning Cycle Phase A). Sprint 9 adds full file system browsing, Gmail OAuth, and a unified inbox. Combined: ~38.5 days estimated effort (~231 hours, ~38 weeks at 6hr/wk).

---

## Scale Assessment

| Scale | Sprint 7 | Sprint 8 | Sprint 9 |
|-------|----------|----------|----------|
| **Single user** | Works | Works | Works |
| **Family (2-5)** | Profile is user-scoped via JWT — works. Agent configs are global (shared agents). | PrincipleStore needs user_id on principles. Graph data is implicitly per-user via memory ownership. | **BREAKS.** File system CRUD operates on host filesystem. ALLOWED_ROOTS are hardcoded paths. No user-scoped file isolation. |
| **Community** | Works if agent configs become per-user. | Works with user_id scoping. | **BREAKS BADLY.** Any authenticated user can access any ALLOWED_ROOT path. No per-user sandboxing. |
| **Cost to fix later** | Low — add user_id to agent config | Low — add user_id to principles table | **HIGH** — requires architectural rethink (per-user virtual filesystems, container isolation, or path namespacing) |

**Recommendation:** Sprint 9 file CRUD should add a `user_id` column to the file operation audit trail and ensure ALLOWED_ROOTS are per-user configurable (even if there's only one user now). This is cheap insurance. Gmail OAuth tokens are already user-scoped via device token → acceptable.

---

## Phase 3: Front-Line Engineering Review

### Sprint 7 — Profile & Settings Restructure

**Feasibility:** HIGH. All backend endpoints confirmed. Zero new backend work.

**Hidden prerequisites:**
- V2 agent API uses `/config/{file_name}`, NOT `/files/{file_name}` as stated in the plan. The plan references `GET /v2/agents/{name}/files/IDENTITY.md` — actual path is `GET /v2/agents/{name}/config/IDENTITY.md`. **Must fix plan references.**
- `AgentConfigFile` is an enum — only pre-defined file names are valid. Verify IDENTITY.md and ANIMA.md are in the enum.
- Photo crop on macOS requires `NSImage` manipulation (not UIKit's `UIImagePickerController`). SwiftUI has no native crop overlay — this is a custom component (~1 day, correctly estimated).

**Effort assessment:**
- MarkdownEditorView with syntax highlighting (2 days) — **UNDERESTIMATED.** SwiftUI's `TextEditor` has very limited styling. For line numbers + syntax highlighting, you need `NSTextView` wrapped in `NSViewRepresentable`. Budget 3 days, not 2.
- Accordion shell (1 day) — Correctly estimated. `DisclosureGroup` with custom styling works.
- Model deduplication (0.5 day) — Correctly estimated, but Xcode target membership changes are fiddly. Have a fallback plan if shared models import HestiaShared types that macOS doesn't have.

**Testing gaps:**
- No test for "only one accordion section expanded at a time" behavior.
- No test for markdown editor undo/redo (⌘Z/⌘⇧Z).
- No test for photo crop with non-square images or very small images.

**Revised effort estimate:** ~14.5 days (was 13). MarkdownEditorView takes longer than planned.

### Sprint 8 — Research & Graph + PrincipleStore

**Feasibility:** MEDIUM. Requires entirely new backend module. No existing code to build on.

**Hidden prerequisites:**
- The macOS `ResearchView.swift` (726 lines) and `MacSceneKitGraphView.swift` (304 lines) already exist with a specific data model (`GraphNode` with id/content/confidence/topics/entities/position/radius/color, `GraphEdge` with fromId/toId/weight). The new backend **must match these existing frontend contracts** or the view needs refactoring.
- ChromaDB currently uses a single collection (`hestia_memory`). Adding `hestia_principles` requires verifying ChromaDB PersistentClient supports multiple collections at the same persist path (it does, but test this explicitly).
- `LogComponent.RESEARCH` doesn't exist yet — needs adding to the enum.

**Effort assessment:**
- Graph Builder (3 days) — **UNDERESTIMATED.** Building co-occurrence edges requires cross-referencing session IDs across memory chunks AND tool execution logs. Tool execution logs are in the orders/tasks tables, not a dedicated table. Extracting and correlating this data is non-trivial. Budget 4 days.
- Graph API endpoint (1 day) — Correctly estimated.
- macOS Graph View refactor (3 days) — Correctly estimated IF the backend data model matches the frontend contract. If not, add 1 day for view refactoring.
- PrincipleStore (included in 3 days) — The principle distillation prompt needs iteration. First version will produce noisy results. Budget a "tune the prompt" day.

**Testing gaps:**
- No test for graph computation timeout (10-second limit mentioned but not tested).
- No test for empty ChromaDB (zero memory chunks → what does the graph look like?).
- No performance test for ChromaDB query with 2 collections open simultaneously.

**Revised effort estimate:** ~13 days (was 11). Graph builder correlation logic and prompt tuning add time.

### Sprint 9 — Explorer: Files & Inbox

**Feasibility:** LOW-MEDIUM. Two entirely new backend modules (file system CRUD + email). Gmail OAuth is an external dependency.

**Hidden prerequisites:**
- **No mail CLI tool exists.** The plan assumes "wraps existing Apple CLI mail tool" but `hestia-cli-tools/` has no mail CLI. The `hestia/apple/mail.py` MailClient exists but is **read-only** (reads Apple Mail database directly). Send/delete/move require either extending this or building a new CLI tool.
- **Gmail OAuth requires Google Cloud Console setup by Andrew** — project creation, OAuth consent screen, credentials. This is a manual step that blocks development. Must happen before Sprint 9 starts.
- **Shared OAuthManager base class** — Sprint 9 says "extract before Sprint 9" but there's no existing OAuth code to extract from. This is a new abstraction built during Sprint 9.
- `pdfplumber` or `pymupdf` for lab PDF parsing is mentioned in Sprint 12, not Sprint 9, but the email module's attachment handling may need basic PDF awareness.

**Effort assessment:**
- File system backend (3 days) — **UNDERESTIMATED.** Path validation with TOCTOU protection, allowlist management, audit trail, safe delete via `osascript` — this is security-critical code that needs careful implementation. Budget 4 days.
- Files tab UI (3 days) — Correctly estimated. Existing `FileTreeView` and `FilePreviewArea` can be extended.
- Email backend module (4 days) — **SIGNIFICANTLY UNDERESTIMATED.** Building a new module from scratch with two providers (Apple Mail + Gmail), OAuth2 flow, token management, deduplication by Message-ID, and a unified manager — this is at least 6 days. Apple Mail send/delete requires extending the read-only MailClient or building AppleScript automation.
- Inbox tab UI (3 days) — **UNDERESTIMATED** if email compose is included. A compose sheet with To/CC/BCC autocomplete, account picker, and attachment support is 2 days alone. Budget 4 days for inbox UI.
- Tab design + orange accent (0.5 day) — Correctly estimated.

**Testing gaps:**
- No test for file operations on network-mounted volumes (NFS, SMB).
- No test for email compose with large attachments.
- No test for Gmail OAuth token refresh during active email listing.
- No test for Apple Mail database access when Mail.app is closed.

**Revised effort estimate:** ~19 days (was 14.5). Email module and security hardening are significantly underestimated.

---

## Phase 4: Backend Architecture Lead Review

### Sprint 7
- **Architecture fit:** No backend changes — N/A. Frontend follows existing patterns.
- **Data model:** No changes needed. All schemas exist.
- **Integration risk:** LOW. Only consumes existing APIs.

### Sprint 8
- **Architecture fit:** GOOD. New `hestia/research/` module follows the standard manager pattern. `get_research_manager()` async factory. LogComponent.RESEARCH to add.
- **API design:** `GET /v1/research/graph` with query params for filtering — clean. `POST /v1/research/principles/distill` — POST is correct (triggers computation). `GET /v1/research/principles` — standard list endpoint.
- **Data model concern:** The `Principle` model has `source_interactions: List[str]` (session IDs). This could grow unbounded. Consider a junction table or limit to last N source sessions.
- **ChromaDB collection isolation:** The plan correctly separates `hestia_principles` from `hestia_memory`. Verify both collections can coexist in the same PersistentClient (they can).
- **Integration risk:** MEDIUM. Graph builder needs to query both ChromaDB and multiple SQLite databases (tasks, orders, sessions). Cross-database correlation is the hard part.

### Sprint 9
- **Architecture fit:** CONCERNING. The file system CRUD breaks the clean API-first pattern. `hestia/api/routes/explorer.py` currently serves Explorer resources (aggregated from Apple clients). Adding raw file system access to the same route file conflates two different concerns.
- **API design concern:** File endpoints use `?path=` query params for GET but body params for POST/PUT/DELETE. This is inconsistent — the plan should standardize. Also, `DELETE /v1/explorer/files` with a body is non-standard (most HTTP clients don't support DELETE with body). Use `?path=` query param instead.
- **Data model:** `FileEntry` model is clean. Email models need `message_id` (RFC 822 Message-ID header) for deduplication — this is correctly specified.
- **New dependency risk:** Gmail API requires `google-api-python-client` + `google-auth-oauthlib`. These are well-maintained but add ~15MB to the dependency tree. Pin versions in `requirements.in`.
- **Integration risk:** HIGH. Two new modules, OAuth2 token lifecycle, Apple Mail write access (currently read-only).

**Recommendation (Sprint 9):** Split file system CRUD into its own route module (`routes/files.py`) separate from `routes/explorer.py`. Explorer aggregates resources; Files provides raw filesystem access. This is a cleaner separation of concerns.

---

## Phase 5: Product Management Review

### Sprint 7 — User Value: HIGH
- Makes every setting editable and persistent. This is the "make it real" sprint.
- MarkdownEditorView is reused in 4+ future sprints — high leverage.
- CacheManager provides instant load UX — noticeable quality improvement.
- **Opportunity cost:** While building Settings, you're not building the chat redesign (Sprint 10) which is the most-used view. Acceptable trade-off because Sprint 7 produces shared components.

### Sprint 8 — User Value: MEDIUM
- The knowledge graph is visually impressive but its day-to-day utility is unclear until there's significant memory data.
- PrincipleStore is infrastructure — Andrew won't directly interact with it until Sprint 11's daily briefing integration.
- **Concern:** If the graph looks empty or noisy with current data volume, it could feel like wasted effort. Needs a "minimum data threshold" check — if <20 memory chunks, show an onboarding state ("Keep chatting to build your knowledge graph") instead of a sparse graph.
- **Opportunity cost:** Building Research/Graph instead of Chat Redesign (Sprint 10). The chat is used daily; the graph may be used weekly. However, PrincipleStore is a prerequisite for the learning cycle — skipping it would break the dependency chain.

### Sprint 9 — User Value: VERY HIGH (but scope is too large)
- File browsing + email unified inbox would make Hestia a genuine OS companion.
- Gmail integration is a killer feature for anyone who uses both Apple Mail and Gmail.
- **Scope concern:** This is the largest sprint (14.5 estimated → 19 actual days). At 6hr/wk, that's ~19 weeks — almost 5 months for one sprint. **This should be split into two sub-sprints:**
  - **9A: Files** (file system CRUD + Files tab UI + security hardening) — ~8 days
  - **9B: Inbox** (email module + Gmail OAuth + unified inbox UI) — ~11 days

### Edge Cases
- **Empty data:** All three sprints need empty-state designs. Sprint 7: "Set up your profile" prompt. Sprint 8: "Keep chatting to build your graph" with minimum threshold. Sprint 9: "Connect your accounts to see your inbox."
- **First-time user:** Sprint 7 is the first thing a new user would customize. The accordion should default to Profile expanded.
- **Offline:** Sprint 7's CacheManager handles this. Sprint 8's graph needs a cached version (5-min TTL specified). Sprint 9's email requires explicit "last synced X minutes ago" indicator.

---

## Phase 6: UX Review

### Design System Compliance
- Sprint 7 plan correctly references `MacColors` tokens. The existing accent system uses amber (`E0A050`, `FFB900`, `FF8904`), NOT the `#FF6B35` orange specified in the plan. **DISCREPANCY:** The plan's new tokens use `#FF6B35` (Hestia orange) but the existing `MacColors.swift` uses amber tones. These need reconciliation — either update the plan to match existing amber, or update MacColors to use the new orange. Don't have two competing accent palettes.
- The plan adds `statusNormal`, `statusWarning`, `statusError`, etc. — but `MacColors.swift` already has `healthGreen`, `healthRed`, `healthGold`, `healthAmber`, and `statusGreen`. **Naming collision.** Reconcile before adding new tokens.

### Interaction Model
- Sprint 7: Accordion with "only one section expanded" — confirm with Andrew. Some users prefer multiple sections open. Consider making this a preference.
- Sprint 8: Node detail popover on tap is good. But 3D SceneKit graphs can be disorienting. Include a "Reset Camera" button.
- Sprint 9: Breadcrumb navigation is well-designed. Right-click context menu needs careful implementation on macOS (differs from iOS).

### Platform Parity
- Sprint 7 is macOS-only. iOS Settings already exists but with different structure. This creates divergence — acceptable for now, but document the gap.
- Sprint 8: Research/Graph is macOS-only. No iOS equivalent planned. Acceptable — the 3D graph is a desktop experience.
- Sprint 9: Explorer exists on both platforms but Sprint 9 enhancements are macOS-focused. iOS explorer is simpler. Acceptable divergence.

### Accessibility
- No mention of VoiceOver support in any sprint plan. The 3D SceneKit graph (Sprint 8) is completely inaccessible to VoiceOver users. Add `accessibilityLabel` to all interactive elements.
- Dynamic Type is not mentioned. All new views should respect system text size preferences.

### Empty States
- Sprint 7: Not specified. Need "Add your photo" prompt, "Write about yourself" for MIND.md.
- Sprint 8: Partially specified (minimum data threshold mentioned). Need explicit empty-state design.
- Sprint 9: "Connect your email accounts" and "No files in this directory" states needed.

---

## Phase 7: Infrastructure / SRE Review

### Sprint 7
- **Deployment impact:** NONE. Pure frontend. No server restart needed.
- **New dependencies:** None for backend. macOS may need a markdown rendering library (or use native `AttributedString`).
- **Rollback:** Easy — revert commit, rebuild macOS app.
- **Resource impact:** None.

### Sprint 8
- **Deployment impact:** New backend module requires server restart. New manager added to Phase 2 parallel init.
- **New dependencies:** None for ChromaDB (already installed). May need `networkx` or similar for graph algorithms (clustering, layout). Pin in `requirements.in`.
- **Monitoring:** Add LogComponent.RESEARCH. Graph computation time should be logged.
- **Rollback:** Remove research routes from server.py, restart. Clean but requires deploy.
- **Resource impact:** Second ChromaDB collection doubles embedding storage. At current scale (<1000 chunks), negligible. At 10K chunks, could add 50-100MB. Monitor.

### Sprint 9
- **Deployment impact:** SIGNIFICANT. New file system routes, new email module, Gmail OAuth callback URL registration. Requires server restart + Google Cloud Console config.
- **New dependencies:** `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`. Add to `requirements.in` and regenerate lockfile.
- **Monitoring:** File operation audit trail provides monitoring. Gmail API errors should trigger alerts. Add health check for email providers.
- **Rollback:** DIFFICULT. If Gmail OAuth is set up and tokens are stored, rolling back the code means orphaned tokens in Keychain. Need a cleanup procedure.
- **Resource impact:** File listings of large directories (Downloads with 10K files) could spike memory. Pagination is specified — enforce server-side limit.

---

## Phase 8: Executive Panel

### CISO Review

**Sprint 7:** ACCEPTABLE. No new attack surface. All data flows through existing authenticated endpoints.

**Sprint 8:** ACCEPTABLE WITH NOTE. PrincipleStore contains distilled user behavior patterns — this is sensitive data. Ensure `hestia_principles` ChromaDB collection is in the same protected data directory as `hestia_memory`. Principle content should not be returned in error messages.

**Sprint 9:** NEEDS REMEDIATION.
- File system CRUD is the largest attack surface addition in the project's history. The allowlist-first approach is correct, but:
  - **E1:** `os.path.realpath()` can be confused by bind mounts and FUSE filesystems. Add explicit check that resolved path is on the same filesystem as ALLOWED_ROOT.
  - **E2:** The plan uses `osascript` for delete operations. AppleScript injection is possible if the path contains shell metacharacters. Sanitize paths before passing to `osascript`.
  - **E3:** Gmail OAuth refresh tokens stored in `sensitive` credential tier — correct. But the plan doesn't specify token rotation policy. Add: rotate refresh tokens on every use (Google supports this).
  - **E4:** File content reads should validate MIME type and refuse to serve executable files (`.app`, `.sh`, `.command`, `.dmg`).
- **Verdict:** NEEDS REMEDIATION — address E1-E4 before Sprint 9 ships.

### CTO Review

**Sprint 7:** ACCEPTABLE. Clean separation. High component reuse. Model deduplication addresses known tech debt.

**Sprint 8:** ACCEPTABLE WITH NOTE. The graph builder's cross-database correlation (ChromaDB + SQLite tasks + SQLite orders + SQLite sessions) is architecturally complex. Consider building a `DataCorrelator` utility that other modules can reuse, rather than baking correlation logic into the graph builder.

**Sprint 9:** NEEDS REMEDIATION.
- **T1:** Sprint 9 is too large (19 actual days). Split into 9A (Files) and 9B (Inbox). This reduces risk and allows a natural review checkpoint.
- **T2:** File CRUD should be in `routes/files.py`, not crammed into `routes/explorer.py`. Different concerns, different security posture.
- **T3:** The plan assumes Apple Mail write capabilities exist. They don't — `MailClient` is read-only. Either scope Sprint 9 to read-only email (list + view), or budget time for building mail send/delete (likely via AppleScript).
- **T4:** `DELETE` with request body is non-standard HTTP. Use `DELETE /v1/explorer/files?path=...` with query param.
- **Verdict:** NEEDS REMEDIATION — address T1-T4.

### CPO Review

**Sprint 7:** ACCEPTABLE. Highest-leverage sprint — produces shared components and makes everything editable. Correct to prioritize first.

**Sprint 8:** ACCEPTABLE WITH CONDITIONS.
- **P1:** Must include minimum data threshold for graph visualization. An empty or sparse graph is worse than no graph — it signals "nothing's happening" even though Hestia is working.
- **P2:** PrincipleStore "principle review" step (principles appear in daily briefing for approval) — this is critical. Without it, Hestia could learn wrong patterns silently. Don't defer this.
- **Verdict:** ACCEPTABLE if P1 and P2 are non-negotiable requirements.

**Sprint 9:** NEEDS REMEDIATION.
- **P3:** Split into 9A (Files) and 9B (Inbox). A 5-month sprint is demoralizing. Two 2.5-month sprints with visible milestones is better for momentum.
- **P4:** Gmail OAuth requires Andrew to set up a Google Cloud project. This is a non-trivial manual step — document it as a pre-sprint checklist item, not a mid-sprint surprise.
- **P5:** Email send/compose can be deferred to a later sprint. Read-only email (list + view) is 80% of the value at 30% of the effort. Ship list+view first, add compose later.
- **Verdict:** NEEDS REMEDIATION — address P3-P5.

---

## Phase 9: Final Critiques

### 1. Most Likely Failure

**Sprint 9's email module will run over budget by 2-3x.**

The plan estimates 4 days for the email backend, but it requires: new module structure, two provider implementations (one read-only extension, one full OAuth2), token lifecycle management, a shared OAuthManager base class, message deduplication, and a unified manager pattern. Each of these is a day of work.

**Mitigation:** Split Sprint 9. Ship Files first (9A). Build email as 9B with reduced scope (read-only first, compose later).

### 2. Critical Assumption

**Sprint 8 assumes sufficient memory data exists to produce a meaningful knowledge graph.**

If Andrew has <50 memory chunks in ChromaDB, the graph will be sparse, edges will be statistically meaningless, and PrincipleStore distillation will produce generic/useless principles. The entire Learning Cycle depends on data density that may not exist yet.

**Validation:** Before Sprint 8, run `chromadb_collection.count()` to check data volume. If <50 chunks, add a "data seeding" step (import existing Notes, Calendar history, or conversation transcripts into memory) before building the graph. Define minimum thresholds: 50 chunks for graph, 100 for meaningful clustering, 200 for principle distillation.

### 3. Half-Time Cut List

If you had half the time for each sprint:

**Sprint 7 (13 → 6.5 days) — CUT:**
- Photo crop editor (use simple NSOpenPanel file picker instead, no cropping)
- Field Guide migration (keep as separate tab — saves 1 day)
- BODY.md editor (keep MIND.md only — one markdown editor, not two)
- **KEEP:** Accordion shell, profile editing, agent profiles, Resources consolidation, CacheManager, MarkdownEditorView, model dedup, orange accent

**Sprint 8 (11 → 5.5 days) — CUT:**
- PrincipleStore (defer to Sprint 10) — the graph alone has value without principle distillation
- Graph clustering (show unclustered nodes with simple category coloring)
- Node detail popover (defer — tap does nothing initially)
- **KEEP:** Research backend module, graph builder (knowledge + activity nodes + edges), graph endpoint, graph view wired to real data, Explorer loading fix

**Sprint 9 (14.5 → 7 days) — CUT:**
- Gmail OAuth (defer entirely — Apple Mail only)
- Email compose/send (read-only inbox)
- Drag-and-drop file move (defer — use context menu only)
- Inbox tab (defer entirely — ship Files only)
- **KEEP:** File system backend with security hardening, Files tab UI, hidden paths config

---

## Conditions for Approval

The plan is **APPROVED WITH CONDITIONS**. All conditions must be addressed before execution begins:

### Must-Fix (Block execution)

| ID | Sprint | Condition | Severity |
|----|--------|-----------|----------|
| **T1** | 9 | Split Sprint 9 into 9A (Files, ~8 days) and 9B (Inbox/Email, ~11 days) | HIGH |
| **T2** | 9 | Move file CRUD to separate `routes/files.py`, not in `routes/explorer.py` | MEDIUM |
| **T3** | 9 | Scope email to read-only in 9B. Defer compose/send to 9C or Sprint 10 | HIGH |
| **E1-E4** | 9 | Address all CISO findings (filesystem checks, osascript sanitization, token rotation, executable MIME filtering) | HIGH |
| **P4** | 9 | Document Google Cloud Console setup as pre-sprint checklist item | MEDIUM |

### Must-Fix (During execution)

| ID | Sprint | Condition | Severity |
|----|--------|-----------|----------|
| **FIX-1** | 7 | Correct V2 agent API paths from `/files/` to `/config/` in plan and code | LOW |
| **FIX-2** | 7 | Reconcile accent color palette: plan says `#FF6B35`, MacColors uses amber (`E0A050`/`FFB900`/`FF8904`). Pick one. | MEDIUM |
| **FIX-3** | 7 | Reconcile status color names: plan adds `statusNormal`/`statusWarning`/etc but `healthGreen`/`healthRed`/etc already exist | LOW |
| **FIX-4** | 7 | Budget 3 days for MarkdownEditorView (not 2) — NSTextView wrapping is non-trivial | LOW |
| **FIX-5** | 8 | Add LogComponent.RESEARCH to enum before starting | LOW |
| **FIX-6** | 8 | Validate ChromaDB data volume before building graph. Define minimum thresholds (50/100/200 chunks) | MEDIUM |
| **FIX-7** | 8 | Match graph backend data model to existing frontend contract in ResearchView.swift | MEDIUM |
| **P1** | 8 | Implement minimum data threshold for graph — show onboarding state if <50 chunks | MEDIUM |
| **P2** | 8 | Principle review step is non-negotiable — must surface in daily briefing | MEDIUM |
| **T4** | 9 | Use query param for DELETE file path, not request body | LOW |

### Should-Do (Best practice, not blocking)

| ID | Sprint | Condition |
|----|--------|-----------|
| S1 | 7 | Add VoiceOver accessibility labels to all new interactive elements |
| S2 | 8 | Add "Reset Camera" button to 3D graph view |
| S3 | 8 | Consider `DataCorrelator` utility for cross-database queries |
| S4 | 9 | Add `user_id` column to file operation audit trail for multi-user readiness |
| S5 | All | Design empty states for all new views before implementation |

---

## Revised Effort Estimates

| Sprint | Original | Revised | Delta | At 6hr/wk |
|--------|----------|---------|-------|-----------|
| 7 | 13 days | 14.5 days | +1.5 | ~14.5 weeks |
| 8 | 11 days | 13 days | +2 | ~13 weeks |
| 9A (Files) | — | 8 days | (split) | ~8 weeks |
| 9B (Inbox) | — | 11 days | (split) | ~11 weeks |
| **Total** | **38.5 days** | **46.5 days** | **+8 days** | **~46.5 weeks** |

**Calendar time at 6hr/wk:** ~11 months for all three sprints (was ~9.5 months).

---

## Appendix: Codebase Verification Summary

| Assumption | Verified? | Notes |
|------------|-----------|-------|
| Profile endpoints exist | YES | 5 endpoints in `routes/user.py` |
| V2 Agent endpoints exist | YES | 10 endpoints, but path is `/config/` not `/files/` |
| MacColors has accent tokens | YES | Uses amber palette, not `#FF6B35` |
| 5 duplicate model files | YES | WikiModels, ToolModels, DeviceModels, HealthDataModels, NewsfeedModels |
| Wiki in nav enum | YES | `.wiki` is top-level case in `WorkspaceView` |
| `hestia/research/` module | NO | Does not exist — must be built |
| NeuralNetGraphView exists | YES | 304-line SceneKit view + 726-line ResearchView |
| ChromaDB single collection | YES | `hestia_memory` collection, cosine similarity |
| 16 managers at startup | YES | 3-phase init in server.py |
| Explorer module exists | YES | 6 endpoints, full draft CRUD |
| `hestia/email/` module | NO | Does not exist — must be built |
| Mail CLI tool exists | NO | 4 CLI tools (keychain, calendar, reminders, notes) — no mail |
| Apple Mail client exists | YES | `hestia/apple/mail.py` — **READ-ONLY** |
| macOS Explorer views exist | YES | 6 files, Files + Resources modes |
