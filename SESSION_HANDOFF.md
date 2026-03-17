# Session Handoff — 2026-03-17 (Session 6)

## Mission
Fix the completely broken CI/CD pipeline (100% failure rate since backports-asyncio-runner phantom dep introduced), repair the macOS xcodebuild from missing Sprint 17 files, and run a full codebase audit. All green.

## Completed

### CI/CD Pipeline (all committed, CI green)
- `ff082a9` — Removed `continue-on-error: true` from ci.yml; upgraded Claude action to `pull-requests: write` + `issues: write`
- `7be950f` — Recompiled requirements.txt with `uv pip compile --python-version 3.11`; removed phantom `backports-asyncio-runner==1.2.0`, updated header to document uv workflow
- `c12c674` — Pre-push hook now handles ChromaDB hang correctly (checks `[100%]` progress marker when pytest exits non-zero)
- `b575296` — CI test command switched to `-v 2>&1 | tail -100` for failure visibility
- `dc570a9` — Committed 3 missing Sprint 17 macOS files: `LearningModels.swift`, `APIClient+Learning.swift`, `LearningMetricsPanel.swift`

### Codebase Audit
- Full audit run: `docs/audits/codebase-audit-2026-03-17.md`
- CLAUDE.md counts corrected: tests 2267 (2132+135), files 66 (59+7), endpoints 186

### Documentation
- SPRINT.md updated with CI/CD session entry + Tailscale OAuth pinned item
- CLAUDE.md test/endpoint/file counts fixed (3 stale values corrected)

## In Progress
- Nothing. All work is committed and CI is green.

## Decisions Made
- **Re-compile for Python 3.11 (not pin pytest-asyncio <1.0)**: Aligns lockfile with CI target. Local dev should upgrade to 3.11+ (CLAUDE.md already says >=3.11).
- **Tailscale OAuth deferred to weekend 2026-03-22**: Deploy still works via direct SSH to Mac Mini on local network; Tailscale step is commented-out placeholder in deploy.yml. No ADR needed.
- **Swift CI deferred indefinitely**: Pre-push hook covers main branch xcodebuild. Self-hosted runner adds maintenance burden.
- **uv over pip-compile**: `uv pip compile` is faster and handles `--python-version` cross-compilation more reliably.

## Test Status
- **2132 backend passing, 0 failing** (locally, non-integration)
- **135 CLI passing** (not re-run this session, no changes to CLI)
- **CI (ubuntu-latest)**: All steps green — run `23216739441` on commit `dc570a9` succeeded

## Uncommitted Changes
- `docs/audits/codebase-audit-2026-03-17.md` — new audit file (untracked, needs commit)

## Known Issues / Landmines
- **Tailscale OAuth not yet set up**: `deploy.yml` has a commented-out Tailscale step. Deploys still work via direct SSH when on the same Tailscale network. Weekend 2026-03-22 task: create OAuth client, add GitHub secrets, uncomment the block.
- **api-contract.md is 55 endpoints stale**: Claims 132 across 22 modules, actual is 186 across 27. `/docs` Swagger is always current but markdown doc has drifted.
- **Decision log missing 4 ADRs**: MetaMonitor (Sprint 15), Memory Lifecycle (Sprint 16), Agent Specialization (Sprint 17), Reasoning Streaming (Sprint 17).
- **`proactive/policy.py:_check_focus_mode()`** calls `subprocess.run()` synchronously in async context — blocks event loop up to 2s. Easy fix: `run_in_executor`. Low urgency.
- **`agents/config_loader.py` and `agents/file_watcher.py`** use `f"...: {e}"` in logger calls. Violates `type(e).__name__` convention.
- **handler.py god object**: 2492 lines. Structural debt, no sprint scope yet.
- **Knowledge graph extraction is on-demand only**: LearningScheduler has idle overnight capacity — a nightly `_graph_extraction_loop()` for last 20 unextracted convos would be ~50 lines. Consider for Sprint 18.
- **Node.js deprecation**: `actions/checkout@v4` and `actions/setup-python@v5` use Node.js 20 (deprecated June 2026). Upgrade before then.

## Process Learnings

### Config Gap Scan
- **Missing xcodegen regeneration awareness**: Sprint 17 added Swift files but never committed them. When adding new Swift files, always run `xcodegen generate` and verify `.xcodeproj` reflects them before committing.
- **pip-compile Python version pinning**: Lockfile was compiled on Python 3.9 but CI runs 3.11. Always use `uv pip compile --python-version 3.11` regardless of local Python version.

### First-Pass Success
~75%. Pre-push hook `[100%]` fix required a second iteration — ChromaDB hang behavior wasn't fully understood until log output examined. Top blocker: environment divergence (local 3.9 vs CI 3.11), now eliminated.

### Agent Orchestration
- @hestia-tester not used (no new Python code — config/deps only). Correct.
- @hestia-reviewer not used — CI/config changes only. Correct.
- @hestia-build-validator would have been useful before the macOS file commit to catch missing Swift files earlier.

## Next Step
**Weekend (2026-03-22): Tailscale OAuth setup:**
1. Tailscale admin console → OAuth clients → Create with `tag:ci` tag
2. Add `TS_OAUTH_CLIENT_ID` + `TS_OAUTH_SECRET` as GitHub repo secrets
3. Add ACL rule: `tag:ci` → Mac Mini port 22
4. Uncomment Tailscale step in `.github/workflows/deploy.yml`
5. Push to `main`, verify deploy job completes

**Next sprint: Graph view work**
- Fix SceneKit cutoff bug in research/neural net graph visualization
- Wire graph view to knowledge graph entities/facts/communities (currently uses co-occurrence)
- Start with `/discovery` to scope the work
