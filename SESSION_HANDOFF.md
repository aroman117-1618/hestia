# Session Handoff — 2026-03-16

## Mission
Resolve known landmines from Sprint 13 handoff, then live-test and fix the agentic coding loop (iterative tool chaining with cloud inference).

## Completed
- **Landmine: count-check.sh broken** — Two bugs: pytest collected from hestia-cli/tests (conftest collision) and run_with_timeout kill guards failed under set -euo pipefail. Fixed both. (4206e0a)
- **Landmine: Memory import relevance penalty** — 0.9x multiplier for claude_history/openai_history chunks in search results, applied before temporal decay. 1 new test. (a2b29a1)
- **Landmine: HestiaShared gitignored** — Committed as tracked SPM package, deleted 27 duplicate files from Shared/, removed exclude list from project.yml. Both Xcode schemes build clean. Also fixed pre-existing WikiView #if !os(iOS) guard. (55db881)
- **Agentic cloud routing** — Added force_cloud parameter to chat() and _call_with_routing() so handle_agentic() bypasses the router and goes directly to cloud. Improved error messages with sanitized details. (56057b0)
- **Claude CLI subscription fallback** — When Anthropic API returns billing (HTTP 400) or rate-limit (HTTP 429) errors, automatically falls back to claude -p (subscription billing via OAuth). Strips ANTHROPIC_API_KEY from subprocess env. Default model: sonnet. 7 new tests. (7a411cf)
- **Cleanup** — Removed .serena/ directory (unused MCP plugin), added scripts/add-cloud-key.sh, CI workflow_call trigger, tasks/lessons.md template. (eb4f315)

## In Progress
- **CLI fallback Phase 2 (tool calling helper)** — Deferred. Live testing proved the existing text-based tool extraction works with the CLI path without explicit tool schema embedding. Helper (_tool_defs_to_instructions()) can be added if a failure case is found.
- **CLI fallback Phase 3 (UI indicator)** — Deferred to roadmap. inference_source field exists on InferenceResponse but is not yet threaded through API responses or displayed in iOS/macOS UI.

## Decisions Made
- HestiaShared is the single source of truth for foundational Swift code (models, networking, design system, config). Shared/ retains ViewModels, Views, and platform services only.
- CLI fallback uses sonnet by default (not opus) to control subscription cost.
- CLI fallback applies to ALL cloud paths (chat, stream, agentic), not just agentic.
- Phase 3 UI indicator (inference source badge) deferred to existing UI roadmap.
- .serena/ removed — built-in tools (Grep, Glob, Read) + hestia-explorer sub-agent cover all needs.

## Test Status
- 1917 collected, 1914 passing, 3 skipped (Ollama integration)
- No failures
- 8 new tests this session (1 memory import penalty, 7 CLI fallback)
- count-check.sh passes clean

## Uncommitted Changes
- None — all committed

## Known Issues / Landmines
- **Anthropic API billing** — The API key's credits show "credit balance too low" (HTTP 400). $148.73 remaining with $1,068 pending. Anthropic support contacted. The CLI fallback masks this completely — agentic loop works via subscription.
- **Agentic sandbox paths** — read_file with relative paths (e.g. "hestia/memory/models.py") is denied by sandbox. The model works around it via glob_files + grep_files, but teaching absolute paths in the agentic system prompt would reduce iteration count.
- **Integration tests hit Ollama** — TestInferenceClientIntegration (2 tests) claim to skip when Ollama is unavailable, but the skip logic doesn't work. They timeout instead. Pre-existing.
- **HestiaShared on Mac Mini** — Fresh deploy needs xcodegen regeneration since project.yml changed. The deploy script should handle this, but verify after next push.
- **Cloud cold-boot** — After server restart, cloud defaults to disabled. First /v1/cloud/providers call syncs from SQLite to enabled_full. Documented behavior, not a bug.

## Process Learnings
- **Config gap: security hook false positive** — The security_reminder_hook.py triggers on "exec" in Python test files that mock asyncio.create_subprocess. It's designed for JS child_process and doesn't apply to Python async subprocesses. Consider adding a file-type filter to the hook.
- **First-pass success: ~90%** — Rework was minimal: WikiView iOS build error (exposed by cleanup, not caused by it), test fixture using wrong store() parameter (source= vs metadata=ChunkMetadata(source=)). Both caught quickly.
- **Agent orchestration: good** — Used hestia-explorer effectively for parallel research (3 calls). Could have used hestia-reviewer for the HestiaShared restructure given its scope (39 files). Skipped due to confidence in Xcode build verification.
- **Key debugging insight** — The "14-char API key" mystery was solved by direct Keychain retrieval (sk-invalid-key placeholder). Adding debug logging to _call_cloud() was essential — the original error messages were opaque (CloudAuthError: CloudAuthError). The improved warning-level logging is now permanent.

## Next Step
1. **Agentic sandbox paths** — In hestia/orchestration/handler.py, update the agentic system prompt to tell the model to use absolute paths (e.g., /Users/andrewlonati/hestia/...) for file tools. This will reduce tool iteration waste from 11 to ~3 iterations.
2. **Deploy to Mac Mini** — 41 commits ahead of remote. Run ./scripts/deploy-to-mini.sh. Verify xcodegen regenerates correctly with the new project.yml.
3. **When API billing resolves** — Re-test agentic loop without CLI fallback to confirm native API tool calling works. Check logs for inference_source: "api" vs "subscription".
4. **Phase 3 UI indicator** — Add inference_source to chat/stream/agentic response metrics and display in iOS/macOS chat bubble metadata. Blend into next UI sprint.
