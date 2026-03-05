# Session Handoff — 2026-03-05

## Mission
Implement zero-friction CLI bootstrap so `hestia` can be typed in any terminal and immediately auto-start the server, auto-register, and begin chatting. Fix prompt engineering issue where Tia ignored injected project context for small models.

## Completed
- **Zero-friction bootstrap** (`hestia-cli/hestia_cli/bootstrap.py`) — `3945682`
  - `_is_localhost()` security gate: auto-start/auto-register only for localhost URLs
  - `ensure_server_running()`: ping → launchd kickstart → subprocess fallback → poll up to 14s
  - `ensure_authenticated()`: token check → POST `/v1/auth/register` for localhost → Keychain store
  - Wired into both REPL (`repl.py`) and batch mode (`app.py`)
  - `hestia setup` subcommand with `install-service` and `status`
  - `config.py`: `auto_start: True` default
  - 14 new bootstrap tests (66 CLI tests total)
- **Error sanitization** in `app.py` — replaced pre-existing `str(e)` with fixed strings in batch JSON output
- **Context instruction fix** (`hestia/orchestration/handler.py:707-712`) — `80a3f59`
  - Tells Qwen 7B to reference injected project files for project questions
  - Without this, "hestia roadmap" triggered calendar tools instead of referencing SPRINT.md
- **Reviewer fixes applied**: kickstart return code check, `.get()` for token parsing, sync `_start_server_launchd`, poll timeout accuracy, hostname truncation
- **Doc updates**: CLAUDE.md (test counts 1466→1611, project structure, CLI sprints table), SPRINT.md (CLI sprint history)

## In Progress
- Nothing — all work committed.

## Decisions Made
- **Auto-register uses legacy `/v1/auth/register`** — no invite required, gated client-side by `_is_localhost()`
- **Server auto-start: launchd preferred, subprocess fallback** — covers Mac Mini (production) and dev Mac (no launchd)
- **Context instruction safe for larger models** — keep after Mac Studio upgrade, cheap insurance

## Test Status
- 1545 backend passing, 3 skipped, 0 failing
- 66 CLI passing, 0 failing
- **1611 total** (up from 1466)

## Uncommitted Changes
- `CLAUDE.md`, `SPRINT.md`, `SESSION_HANDOFF.md` — this handoff commit

## Known Issues / Landmines
- **pytest conftest collision**: Running `pytest` from repo root collects both `tests/` and `hestia-cli/tests/`, causing `ImportPathMismatchError`. Always run separately: `pytest tests/` and `cd hestia-cli && pytest tests/`
- **`count-check.sh` is broken**: Script exists but errors out. Counts verified manually this session.
- **Context instruction for small models**: `handler.py:707-712` helps Qwen 7B use project context. Larger MoE models may not need it — test after Mac Studio upgrade.
- **Server running on port 8443** at handoff
- **2 untracked discovery docs** in `docs/discoveries/` — pre-existing, not from this session
- **CLI not yet installed on Mac Mini**: Need `pip install -e hestia-cli/` after deploy

## Next Step
1. Commit handoff docs: `git add CLAUDE.md SPRINT.md SESSION_HANDOFF.md`
2. Push to main: `git push origin main`
3. Deploy CLI to Mac Mini: `pip install -e hestia-cli/` on the Mini
4. Test bootstrap on Mac Mini via Tailscale — remote path should require `hestia auth login`
5. Sprint 11 (Command Center + MetaMonitor) is next per SPRINT.md
