# Session Handoff — 2026-03-19 (Session 9: Sprint 28 + UI Overhaul + Auto-Update)

## Priority for Next Session

1. **Complete Sparkle auto-update (~15 min):**
   - Mac Mini OS update should be done → register as self-hosted GitHub Actions runner
   - Update `release-macos.yml`: `runs-on: self-hosted` instead of `macos-15`
   - Delete stale tag: `git tag -d v1.0.1 && git push origin :refs/tags/v1.0.1`
   - Re-tag: `git tag v1.0.1 && git push --tags`
   - Verify: workflow succeeds → appcast updates → app prompts for update

2. **Check Alpaca account approval** — once approved, test AlpacaAdapter against paper API

3. **Sprint 27 post-soak review (~Mar 22)** — review trade history, confirm clean run, flip to real capital

## What Was Done This Session

### Planning & Analysis
- 3-model audits (Claude + Gemini + @hestia-critic) on Graph View plan and Sprint 28 plan
- Sparkle auto-update discovery

### Principles Pipeline Fix (4 files)
- WebSocket outcome tracking added (root cause of empty pipeline)
- High-signal filter widened, min_outcomes lowered, fallback distillation added

### Quick Wins (5 Swift files)
- Graph default filter → principle-centric
- Explore nav 3→2 tabs with Files sub-mode
- Curation buttons on fact nodes

### Sprint 28 Infrastructure (7 parallel agents)
- `get_candles()` on ABC, CoinbaseAdapter, BotRunner refactor
- Multi-exchange orchestrator with per-bot routing
- AlpacaAdapter (read-only), MarketHoursScheduler
- Product info equities, Alpaca config, backtest tests

### Command Tab Modernization (2 parallel agents)
- Removed 70px FloatingAvatarView header
- Input bar: mic/send swap + session controls + recording state
- Orders under System tab with Upcoming/Past views

### Sparkle Auto-Update (90% complete)
- SPM dependency, AppDelegate wiring, menu item, Info.plist keys
- GitHub Actions workflow, gh-pages branch, appcast live
- `/ship-it` skill created
- **Blocked:** GitHub cloud runner has Swift 6.1, need self-hosted Mac Mini runner (Swift 6.2)

## Blocking Issues

| Issue | Fix | Time |
|-------|-----|------|
| Release workflow fails (Swift version mismatch) | Register Mac Mini as self-hosted runner | 15 min |
| Alpaca account pending | Wait for approval (1-3 business days) | N/A |
| Sprint 27 soak | Ends ~Mar 22 | N/A |

## Key Decisions
- Margin account for Alpaca, regular hours only, SPY first
- Repo made public (enables GitHub Pages/Releases for Sparkle)
- Visual companion is standard for all UI brainstorming
- No manual mode switching — Hestia orchestrates, `@agent` for overrides
- Tagged commits only trigger releases

## GitHub Secrets Configured
- `SPARKLE_PRIVATE_KEY`, `AC_USERNAME`, `AC_PASSWORD`, `AC_TEAM_ID`

## Test Status
- 2552+ backend tests passing, macOS build clean
- ~30 commits shipped and deployed to Mac Mini
