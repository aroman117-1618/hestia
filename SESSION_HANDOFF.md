# Session Handoff — 2026-03-17 (Sprint 20 — Verification UI Indicators)

## Mission
Implement Sprint 20: surface the 3-layer hallucination verifier as a user-visible amber dot in iOS and macOS chat UIs, and catch up api-contract.md (54 stale endpoints, 5 missing modules).

## Completed

### Sprint 20 — All tasks done

- **Task 1 — Backend Python** (`75e4a9a`)
  - `hestia/orchestration/models.py` — `hallucination_risk: Optional[str] = None` on `Response`
  - `hestia/api/schemas/chat.py` — `hallucination_risk: Optional[str]` on `ChatResponse` Pydantic model
  - `hestia/orchestration/handler.py` — REST path: derives `"tool_bypass"` from ToolComplianceChecker, `"low_retrieval"` from retrieval_score < 0.6; streaming path: same + yields `{"type": "verification", "risk": ..., "request_id": ...}` SSE event BEFORE `done`
  - `hestia/api/routes/chat.py` — threads `hallucination_risk` into `ChatResponse` constructor

- **Task 2 — Swift client** (`197c82a`)
  - `HestiaShared/Sources/HestiaShared/Models/Response.swift` — `hallucinationRisk: String?` on `HestiaResponse`; `.verification(risk: String)` case on `ChatStreamEvent`; `parseChatStreamEvent()` handles `"verification"` type
  - `HestiaShared/Sources/HestiaShared/Models/Message.swift` — `hallucinationRisk: String?` on `ConversationMessage`
  - `HestiaApp/Shared/ViewModels/ChatViewModel.swift` — handles `.verification` in streaming loop; passes `hallucinationRisk` in REST path
  - `HestiaApp/macOS/ViewModels/MacChatViewModel.swift` — same
  - `HestiaApp/Shared/Views/Chat/Components/MessageBubble.swift` — `VerificationRiskDot` amber dot (`.orange`, popover, accessibility label)
  - `HestiaApp/macOS/Views/Chat/MacMessageBubble.swift` — `MacVerificationRiskDot` using `MacColors.statusWarning` (#FF9800), always visible (not hover-gated), after bylines, before `OutcomeFeedbackRow`

- **Task 3 — api-contract.md** (`85b8cf5`)
  - Endpoint count: 132 → 186, module count: 22 → 27
  - 5 missing modules added: files, inbox, outcomes, learning, ws_chat
  - `ChatResponse.hallucination_risk` field + enum values documented
  - SSE `verification` event type documented
  - Verification Pipeline section added (3-layer architecture)
  - Research module expanded from 6 → 18 endpoints

- **Fixes** (`bd5f624`)
  - `HestiaApp/macOS/Views/Research/ResearchView.swift` — moved `GraphControlPanel` inside ZStack (layout fix from previous session)
  - `scripts/count-check.sh` — fixed test count parser for `(N backend + N CLI)` format; fixed file count to include CLI test files

### Deploy
- `git push origin main` complete — pre-push hook: full pytest (2142 passing, 3 skipped, 0 failing) + macOS BUILD SUCCEEDED
- `./scripts/deploy-to-mini.sh` initiated in background at session end — verify Mac Mini server health before use

## In Progress
- Mac Mini deploy (background at session end) — run `lsof -i :8443` on Mac Mini to confirm server is live with Sprint 20 code

## Decisions Made
- **Streaming verification event before `done`**: yield `{"type": "verification", ...}` before `done` so Swift clients can set `hallucinationRisk` immediately when streaming completes
- **Option A disclaimer duplication**: kept text disclaimer in content AND amber dot for Sprint 20. Revisit in Sprint 21 (Option B: client-side suppression in bubble when `hallucinationRisk != nil`)
- **`hallucination_risk: Optional[str]`** not a nested object: forward-compatible; future upgrade to `VerificationSummary` documented as ADR note in api-contract.md for Sprint 22+
- **Retrieval threshold 0.6** hardcoded in handler risk derivation — matches configurable threshold in `_inject_retrieval_warning()`. Acceptable for Sprint 20

## Test Status
- **2142 backend passing, 3 skipped, 0 failing**
- **135 CLI passing** (unchanged)
- **Total: 2277**
- macOS: `BUILD SUCCEEDED`

## Uncommitted Changes
None — working tree clean.

## Known Issues / Landmines

- **SourceKit `No such module 'HestiaShared'` warnings**: IDE false positives in macOS files. `xcodebuild` compiles clean. Resolves on Xcode re-index.
- **`data-2026-03-15-22-44-27-batch-0000/` directory**: untracked in project root. Contains `conversations.json`, `memories.json`, `projects.json`, `users.json` — looks like a ChromaDB export from 2026-03-15. NOT committed (correct). Investigate: gitignore or delete if stale.
- **Text disclaimer + amber dot both visible** on flagged messages: intentional Option A for Sprint 20. Sprint 21 correction UI is the right time to suppress the text (Option B: when `hallucinationRisk != nil`, hide the ⚠ footer from the bubble renderer).
- **Tailscale OAuth for CI/CD still pending**: `deploy.yml` has commented-out Tailscale step. Manual deploy still works (`./scripts/deploy-to-mini.sh`). Weekend 2026-03-22 target passed — still pending.
- **handler.py at 2500+ lines**: structural debt, no sprint scope yet.

## Process Learnings

### Config Gap: hestia-deployer hangs on ChromaDB pytest
**What happened**: `hestia-deployer` subagent spent its entire budget running `python -m pytest` (ChromaDB background thread hang) and never reached the actual deploy step.
**Root cause**: Deployer prompt triggers a full test run without the `run_with_timeout` wrapper from `scripts/pre-push.sh`.
**Fix**: Update hestia-deployer agent definition — skip the test step (tests already ran pre-push), or invoke `scripts/pre-push.sh` which has the timeout wrapper built in.

### First-Pass Success: ~90%
- All 3 implementation tasks completed in single subagent passes
- Both spec reviews: fully compliant on first submission
- Both quality reviews: APPROVED on first submission
- One rework: `count-check.sh` needed two fix iterations for BSD grep behaviour with `[^,\n]*`
- The plan audit (4 conditions resolved pre-build) made the build extremely clean

### Agent Orchestration
- Subagent-driven-development was the right tool: implementer → spec review → quality review cycle caught nothing surprising
- `hestia-deployer` should not be used as a foreground agent when a full test run is needed — use background or invoke scripts directly

## Next Step

**Sprint 21: iOS Correction Feedback UI** (natural follow-on)

Users can now see which messages were flagged. Sprint 21 lets them act on it:
- Backend complete: `POST /v1/outcomes/{id}/feedback` live; `CorrectionClassifier` + `OutcomeDistiller` consume it
- iOS gap: `MessageBubble` needs a correction affordance on flagged messages
- Design question: integrate into the amber dot popover, or separate tap target?
- macOS already has `OutcomeFeedbackRow` on hover — check if it already covers this

Start with: `/discovery sprint 21 — iOS correction feedback UI`

First: clean up `data-2026-03-15-22-44-27-batch-0000/` (15 min, gitignore or delete) and confirm Mac Mini deploy is live.
