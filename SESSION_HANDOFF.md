# Session Handoff — 2026-03-04 (Session 2)

## Mission
Implement native Ollama tool calling (so Tia can actually use Calendar/Reminders/Notes tools), fix timezone handling across the stack, and fold self-healing loop architecture into the sprint roadmap.

## Completed
- **Native Ollama tool calling** (`hestia/inference/client.py`, `hestia/orchestration/handler.py`) — commit `5858be6`
  - `tools` parameter threaded through `_call_ollama()` → `_call_local_with_retries()` → `_call_with_routing()` → `chat()`
  - `InferenceResponse.tool_calls` field populated from Ollama `message.tool_calls`
  - Native tool detection priority: API tool_calls > council extraction > text regex
  - Tool instructions simplified to behavioral guidance only (no JSON schemas in prompt)
- **Hardened native tool calling** — reviewer findings + 15 tests — commit `29f1ee7`
  - String→dict argument coercion, unknown tool skip, state machine transitions, error recovery
  - Graceful fallback when all native tool calls fail (no empty response)
  - Tool definitions fetched once outside retry loop
  - 8 handler tests + 7 inference tests
- **Self-healing loop assessment** — `docs/discoveries/self-healing-loop-assessment-2026-03-04.md`
  - Level 1-3 architecture mapped, integration points identified
  - Sprint 11: 11.8a (read settings tools), 11.8b (outcome→principle pipeline), 11.8c (correction classification)
  - Sprint 13: 13.4 (write settings tools with CorrectionConfidence scoring + granular ActionRisk)
  - Sprint 14: ActionRisk mapping refined from blanket NEVER to per-category tiers
- **Sprint plan updates** — commit `1f4de45`
  - `docs/plans/sprint-11-command-center-plan.md` — sections 11.8a/b/c added
  - `docs/plans/sprint-13-14-learning-cycle-plan.md` — section 13.4 + granular risk tiers
  - `docs/plans/sprint-7-14-master-roadmap.md` — self-healing threading noted
- **Timezone fix** across 7 files — commit `5e7581c`
  - `hestia/user/models.py` — `timezone` field on UserSettings
  - `hestia/user/config_loader.py` — `get_user_timezone()` utility
  - `hestia/apple/calendar.py` — timezone-aware `get_today_events()` / `get_upcoming_events()`
  - `hestia/apple/reminders.py` — timezone-aware `get_due_today()` / `get_overdue()`
  - `hestia/orders/scheduler.py` — user timezone for APScheduler
  - `hestia/proactive/briefing.py` — local time greeting
  - `hestia/proactive/policy.py` — local time quiet hours
- **Removed** `linkedin-series-final.md` (stored elsewhere)
- **CLAUDE.md + SPRINT.md counts fixed** — 154 endpoints, 25 route modules, 1466 tests

## In Progress
- Nothing — all work committed and pushed.

## Decisions Made
- **Native tool calling over prompt-based**: Ollama `/api/chat` `tools` parameter more reliable than text parsing for local models
- **Timezone: stored profile + sync**: `get_user_timezone()` reads from `UserIdentity.timezone` (USER-IDENTITY.md). Per-request override deferred to Sprint 11 settings tools
- **Self-healing corrections: suggest-only for now**: All corrections require user approval. Auto-apply gated on CorrectionConfidence scoring (Sprint 13-14)
- **Principle pipeline timing: hybrid threshold**: Distill when 3+ corrections in same domain within 24h, OR daily batch
- **Granular ActionRisk**: `display_settings` and `behavioral_settings` at SUGGEST tier; `security_settings` and `system_settings` at NEVER tier (Sprint 14)

## Test Status
- 1466 passing, 0 failing, 3 skipped
- All tests green. No regressions.

## Uncommitted Changes
- `CLAUDE.md` — count updates (154 endpoints, 25 routes, 1466 tests)
- `SPRINT.md` — test count update (1451→1466)

## Known Issues / Landmines
- **Mac Mini calendar is empty**: Only shows US Holidays. Google/iCloud accounts need to be added in System Settings → Internet Accounts on the Mac Mini (physical access required)
- **Council needs `qwen2.5:0.5b`** pulled on Mac Mini
- **Native tool calling untested on Mac Mini**: Works in unit tests with mocked Ollama. Need live test with `qwen2.5:7b` — ask Tia "What's on my calendar today?" after deploy
- **Timezone default is hardcoded**: `get_user_timezone()` defaults to `America/Los_Angeles` if USER-IDENTITY.md has no timezone. Verify the file has `**Timezone:** America/Los_Angeles` on Mac Mini
- **pytest hangs after completion**: ChromaDB background threads prevent clean exit. Use subprocess timeout pattern

## Next Step
1. Commit the count fixes: `git add CLAUDE.md SPRINT.md && git commit -m "docs: fix count drift — 1466 tests, 25 route modules, 154 endpoints"`
2. Push to main: `git push`
3. Deploy to Mac Mini: `./scripts/deploy-to-mini.sh`
4. Live test: Ask Tia "What's on my calendar today?" to verify native tool calling end-to-end
5. Next sprint: Sprint 11 (Command Center + MetaMonitor) — start with Decision Gate 2 review
