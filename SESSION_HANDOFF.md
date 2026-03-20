# Session Handoff — 2026-03-20 (Session 9+10 Combined)

## Priority for Next Session

1. **Check if v1.0.1 release succeeded** — scheduled retry at 9 AM ET March 20:
   - `gh run list --workflow=release-macos.yml --limit=1`
   - If succeeded: verify appcast has `edSignature`, test "Check for Updates" in app
   - If failed: check `gh run view <id> --log-failed` — likely notarization timeout again
   - **Remove the `schedule:` cron line from `.github/workflows/release-macos.yml`** after success (it's a one-time retry)

2. **Fix EdDSA signing** — the `edSignature` field in appcast.xml was empty last run. The Sparkle private key (44 chars, from Mac Mini Keychain) is in GitHub Secrets but `sign_update` may need a different input format. Debug by checking the "Sign with EdDSA" step output in the workflow logs.

3. **Check Alpaca account approval** — once approved, test AlpacaAdapter against paper API

4. **Sprint 27 post-soak review** (~Mar 22) — review trade history, confirm clean run, flip to real capital

## What Was Built (Sessions 9+10 Combined)

### Planning & Analysis
- 3-model audits (Claude + Gemini + @hestia-critic) on Graph View plan and Sprint 28 plan
- Sparkle auto-update discovery
- Command Tab modernization design (with browser-based visual companion mockups)

### Backend Fixes
- **Principles pipeline unblocked** — WebSocket outcome tracking, widened filter, fallback distillation
- **Sprint 28 infrastructure** (7 parallel agents) — get_candles() ABC, AlpacaAdapter, MarketHoursScheduler, multi-exchange orchestrator, product info equities, backtest tests

### UI Changes
- Graph default filter → principle-centric
- Explore nav 3→2 tabs with Files sub-mode
- Curation "Mark Outdated" button on fact nodes
- Removed 70px FloatingAvatarView chat header
- Redesigned input bar: mic/send swap + session controls + recording state
- Orders moved under System tab with Upcoming/Past views
- Chat empty bubble fixes (parallel session)

### Sparkle Auto-Update (95% complete)
- Sparkle 2 SPM, AppDelegate wiring, "Check for Updates" menu item
- GitHub Actions release workflow on self-hosted Mac Mini runner
- Build → sign (Developer ID) → notarize (Apple) → all working
- GitHub Release creation working
- Appcast on GitHub Pages working
- **Blocked:** Apple notarization queue very slow (~30 min timeout). Scheduled retry at 9 AM ET.
- **EdDSA signing:** Key piped via stdin but signature may be empty — check workflow logs

### Infrastructure
- Mac Mini registered as self-hosted GitHub Actions runner (labels: macos, hestia)
- Xcode installed on Mac Mini (26.3, Swift 6.2)
- `/ship-it` skill created (bumps version, tags, pushes)
- Repo made public (enables GitHub Pages + Releases)

## GitHub Secrets Configured
- `SPARKLE_PRIVATE_KEY` — Ed25519 private key (44 chars from Mac Mini Keychain)
- `AC_USERNAME` — andrew.roman117@gmail.com
- `AC_PASSWORD` — app-specific password for notarization
- `AC_TEAM_ID` — 563968AM8L
- `KEYCHAIN_PASSWORD` — Mac Mini login password (for CI Keychain unlock)

## Key Decisions
- Margin account for Alpaca, regular hours only, SPY first
- Visual companion is standard for all UI brainstorming
- No manual mode switching — Hestia orchestrates, @agent for overrides
- Tagged commits only trigger releases
- Self-hosted Mac Mini runner (not GitHub cloud — Swift 6.2 requirement)

## Known Issues
- **Python venv on dev Mac** — linked to Xcode Python 3.9, needs `python3.12 -m venv .venv`
- **Xcode stale builds** — clean build (Shift+Cmd+K) needed after Swift changes
- **`startNewConversation`** still calls `loadInitialGreeting()` — remove if greeting permanently deprecated

## Test Status
- 2552+ backend tests passing on Mac Mini
- macOS + iOS builds clean
