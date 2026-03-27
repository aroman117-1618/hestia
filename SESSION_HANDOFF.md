# Session Handoff — 2026-03-27 (Hestia Sentinel)

## Mission
Investigate the litellm PyPI supply chain attack (CVE-2026-33634), verify both machines were unaffected, then design and implement a layered supply chain defense system (Hestia Sentinel) to prevent similar attacks from compromising the Mac Mini production environment.

## Completed
- Investigated litellm supply chain attack — confirmed both MacBook and Mac Mini are clean
- Designed Hestia Sentinel with full brainstorming, 10-phase second opinion (Claude + Gemini + @hestia-critic)
  - Spec: `docs/superpowers/specs/2026-03-27-hestia-sentinel-design.md`
  - Audit: `docs/plans/hestia-sentinel-second-opinion-2026-03-27.md`
- Implemented all 20 tasks (19 commits merged to main):
  - **Layer 0**: `scripts/setup-hestia-user.sh`, `scripts/setup-egress-firewall.sh`, launchd plist updates for `_hestia` user
  - **Layer 1**: Hash-locked `requirements.txt`, `scripts/scan-pth-files.sh` + allowlist, hardened `deploy-to-mini.sh`, `deploy-local.sh`, `ci.yml`
  - **Layer 2**: `hestia/sentinel/` — store, config, self-check, adapters (file integrity, credential watch, DNS monitor), alerter, service daemon + launchd plist
  - **Layer 3**: `/v1/sentinel/status` + `/v1/sentinel/acknowledge` endpoints, auto-test mapping
- 65 new sentinel tests (all passing), updated CLAUDE.md

## In Progress
- None — all code merged to main

## Decisions Made
- Sentinel in hestia (not Atlas) with Atlas-compatible interfaces for future migration
- Layer 0 (dedicated user + egress firewall) before detection — per unanimous audit recommendation
- eslogger over DTrace for future credential monitoring (DTrace broken with SIP)
- JSON configs (not YAML) for true zero-dependency sentinel
- Alert batching: CRITICAL/HIGH real-time, MEDIUM/LOW daily digest, 7-day learning period
- Severity aligned with Atlas: LOW/MEDIUM/HIGH/CRITICAL

## Test Status
- 3115 total (2980 backend + 135 CLI), all passing
- 65 sentinel tests across 8 test files

## Uncommitted Changes
- `hestia/data/` — runtime data directory (gitignored), no action needed

## Known Issues / Landmines
- **Layer 0 not deployed yet**: `_hestia` user, LuLu firewall, and .env migration need manual execution on Mac Mini
- **Sentinel not running yet**: Needs baseline generation + launchd plist load after Layer 0
- **eslogger not yet integrated**: Credential watch uses lsof fallback. eslogger needs root + Full Disk Access testing
- **CI may fail on first push**: Hash-locked requirements compiled locally; may need regeneration if platform differs
- **iOS/macOS System Status cards deferred**: API endpoint ready, SwiftUI cards not built
- **ntfy_topic absent from sentinel.json**: Service defaults to `"hestia-sentinel"`, update before deploying

## Process Learnings
- Subagent bash permissions caused 3-4 manual fixups (85% first-pass success rate)
- Parallel agents caused branch divergence requiring cherry-pick — use `isolation: "worktree"` next time
- Python 3.9 compatibility missed by agents writing `dict | None` syntax — add version constraint to prompts

## Next Steps
1. **Deploy Layer 0 on Mac Mini** (~30 min manual):
   - `ssh andrewroman117@hestia-3.local`
   - `cd ~/hestia && git pull`
   - `sudo bash scripts/setup-hestia-user.sh`
   - Install LuLu, configure rules per `scripts/setup-egress-firewall.sh`
   - Migrate .env to Keychain (instructions in setup script output)
2. **Start sentinel**: `bash scripts/sentinel-baseline.sh .venv` then load launchd plist
3. **Verify**: `curl -k https://localhost:8443/v1/sentinel/status`
4. **iOS/macOS System Status cards**: Separate sprint
