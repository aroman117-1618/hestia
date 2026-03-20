# Session Handoff — 2026-03-20 (Afternoon)

## Mission
Fix the "Review Memory" button in the Graph view to navigate to the Memory Browser with the selected chunk pinned, then overhaul the broken CI/CD pipeline to use the Mac Mini's self-hosted runner.

## Completed

### Graph → Memory Browser Navigation
- Renamed "Investigate in Explorer" → "Review Memory" in `NodeDetailPopover.swift`
- Added `onReviewMemory` callback that fetches the chunk by ID, switches to Memory tab, and pins it at the top
- New backend endpoint: `GET /v1/memory/chunks/{chunk_id}` in `hestia/api/routes/memory.py`
- New client method: `APIClient.getChunk(_:)` in `APIClient+Memory.swift`
- `ResearchView` fetches chunk before switching tabs (avoids SwiftUI timing issues)
- `MemoryBrowserView` shows pinned chunk with amber border, "From Graph" label, dismiss button
- Added `Equatable` to `MemoryChunkItem` in `MemoryBrowserModels.swift`

### CI/CD Pipeline Overhaul
- **Deploy workflow** rewritten to use self-hosted runner (`[self-hosted, macos, hestia]`) — no more SSH/Tailscale tunnel
- Created `scripts/deploy-local.sh` — single deploy script for both Actions and manual use
- **CI job names** improved: "Lint, Test & Audit", "Deploy to Mac Mini" (was "test/test" and "deploy")
- **Actions bumped** to `checkout@v5` across all 4 workflows (eliminates Node.js 20 deprecation warning)
- **Stale cron** removed from `release-macos.yml`
- **requirements.txt** refreshed with Python version markers for backport packages
- **SSL certs** generated on Mac Mini (10-year self-signed, SAN: hestia-3.local + localhost)
- **Readiness check** uses Python instead of curl (LibreSSL/SecureTransport mismatch in runner context)
- **launchd restart** simplified: kill once, let KeepAlive auto-restart (was double-killing)
- Cert files excluded from rsync `--delete`

### Release
- Shipped **v1.1.3** (build 7) — macOS Release workflow built, signed, notarized, published

### Key Commits
- `4aa4ba3` fix: overhaul CI/CD — self-hosted runner, clear names, v5 actions
- `4b5de78` fix: add python_version markers to backport packages in lockfile
- `d11b13c` bump: version 1.1.3 (build 7)
- `7f20418` fix: exclude SSL certs from rsync --delete
- `4fab2a6` fix: use Python for readiness check instead of curl
- `0589b08` fix: let launchd KeepAlive handle restart, don't double-kill

## In Progress
- **Alpaca API keys** — Andrew's account approved but Alpaca dashboard returns 403 when generating API keys. Retry later. Sprint 28 blocked on this.
- **macOS app environment** set to `local` in UserDefaults (`defaults write com.andrewlonati.hestia-macos hestia_environment local`) — **reset to `tailscale` when done testing locally**: `defaults write com.andrewlonati.hestia-macos hestia_environment tailscale`

## Decisions Made
- Self-hosted runner over Tailscale GitHub Action for deploy — eliminates network dependency, faster, proven by release workflow
- Python readiness check over curl — LibreSSL in runner context can't negotiate with server's TLS
- Kill + KeepAlive over explicit kickstart — avoids double-kill race condition
- SSL certs on Mac Mini — server should always run HTTPS (was running plain HTTP)

## Test Status
- 2571 backend + 135 CLI = 2706 total, 83 test files
- All passing (3 skipped integration tests)
- Known: pytest hangs after completion due to ChromaDB background threads (pre-push hook handles this with timeout)

## Uncommitted Changes
None — all committed and pushed. Untracked files are artifacts from prior sessions:
- `.superpowers/`, `MACOS_APP_AUDIT.md`, `MACOS_AUDIT_REPORT.md`, `docs/mockups/`, `docs/plans/consumer-product-strategy.md`

## Known Issues / Landmines
- **macOS app pointed at localhost** — UserDefaults override set to `local`. The macOS app won't connect to the Mac Mini until reset to `tailscale`. Run: `defaults write com.andrewlonati.hestia-macos hestia_environment tailscale`
- **Mac Mini Python 3.9** — venv uses Xcode CLI tools Python 3.9.6. Should upgrade to 3.11+ via Homebrew to match CI. Not blocking but a latent risk for packages that drop 3.9 support.
- **Command Center bugs** (from screenshots, not yet investigated):
  - Calendar shows "No upcoming events" despite access granted — likely connecting to Mac Mini which doesn't have calendar data
  - News feed (External tab) shows only "Daily health summary" x8 — should be in Internal/Health, not External/News
- **Pre-push hook takes 4-5 min** — pytest + xcodebuild on every push. Not a bug but slows iteration.

## Process Learnings

### Config Gaps
1. **CLAUDE.MD**: No mention that Mac Mini server runs HTTP when certs are missing — caused 3 debug iterations. Fix: document in "Known Issues (Mac Mini)" section.
2. **CLAUDE.MD**: No mention that macOS app defaults to Tailscale when testing locally — caused the "Review Memory" feature to appear broken. Fix: document the UserDefaults override pattern.

### First-Pass Success
- 3/4 main tasks completed on first pass (Graph nav, deploy script, CI names)
- Deploy readiness check required 4 iterations: HTTP/HTTPS mismatch → cert generation → curl vs Python → timeout tuning
- **Top blocker**: environment mismatch between dev Mac, CI (Ubuntu/3.11), and Mac Mini (macOS/3.9/LibreSSL) — three different SSL stacks

### Agent Orchestration
- @hestia-explorer used effectively for initial Graph/Memory research
- @hestia-build-validator caught the `Equatable` conformance issue before manual testing
- @hestia-tester confirmed memory backend tests passed
- Subagent-driven development worked well for parallel CI/CD file creation (Tasks 2+3)

### Proposals (for Andrew's approval)
1. **CLAUDE.MD** — Add "Mac Mini runs HTTP if certs missing" to Known Issues section. Impact: prevents 30+ min debug cycle.
2. **CLAUDE.MD** — Add UserDefaults override pattern for macOS app environment switching. Impact: prevents "feature broken" false alarms.
3. **SCRIPT** — Upgrade Mac Mini Python to 3.11 via Homebrew. Impact: eliminates 3.9/3.11 split risk, removes backport markers from lockfile.

## Next Steps
1. **Sprint 28 (Alpaca)** — Retry API key generation on Alpaca dashboard. If still 403, contact Alpaca support. Once keys work: `python3 -c "from hestia.security.credential_manager import store_api_key; store_api_key('alpaca-api-key', 'KEY'); store_api_key('alpaca-api-secret', 'SECRET')"`
2. **Command Center bugs** — Investigate calendar wiring (likely needs Mac Mini calendar access or local server) and newsfeed source filtering (health summaries appearing in External/News)
3. **Reset macOS app** — `defaults write com.andrewlonati.hestia-macos hestia_environment tailscale`
