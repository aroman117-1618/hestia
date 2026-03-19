#!/usr/bin/env bash
# create-sprint20-issues.sh — Create GitHub Issues for Sprint 20 + Workflow Orchestrator
# Run from your MacBook (needs gh CLI authenticated)
# Usage: bash scripts/create-sprint20-issues.sh

set -euo pipefail

REPO="aroman117-1618/hestia"
ASSIGNEE="aroman117-1618"

echo "=== Creating labels (idempotent) ==="
gh label create "sprint-20" --repo "$REPO" --color "0E8A16" --description "Sprint 20: Neural Net Graph Phase 2" 2>/dev/null || true
gh label create "sprint-20a" --repo "$REPO" --color "1D76DB" --description "Sprint 20A: Quality Framework" 2>/dev/null || true
gh label create "sprint-20b" --repo "$REPO" --color "5319E7" --description "Sprint 20B: Source Expansion" 2>/dev/null || true
gh label create "sprint-20c" --repo "$REPO" --color "D93F0B" --description "Sprint 20C: Notification Relay" 2>/dev/null || true
gh label create "workflow-orchestrator" --repo "$REPO" --color "FBCA04" --description "Visual Workflow Orchestrator (future)" 2>/dev/null || true
gh label create "backend" --repo "$REPO" --color "C5DEF5" --description "Python backend changes" 2>/dev/null || true
gh label create "macos" --repo "$REPO" --color "BFD4F2" --description "macOS SwiftUI app changes" 2>/dev/null || true
gh label create "ios" --repo "$REPO" --color "D4C5F9" --description "iOS app changes" 2>/dev/null || true
gh label create "research" --repo "$REPO" --color "F9D0C4" --description "Knowledge graph / research module" 2>/dev/null || true
gh label create "infrastructure" --repo "$REPO" --color "E4E669" --description "Infra, tooling, CI/CD" 2>/dev/null || true
gh label create "skill" --repo "$REPO" --color "C2E0C6" --description "Claude Code skill" 2>/dev/null || true
gh label create "gemini" --repo "$REPO" --color "006B75" --description "Gemini CLI integration" 2>/dev/null || true

echo ""
echo "=== Sprint 20A Issues ==="

gh issue create --repo "$REPO" --assignee "$ASSIGNEE" \
  --title "WS1: Insight Quality Framework — DIKW tiers, 3-phase extraction, durability scoring" \
  --label "sprint-20,sprint-20a,backend,research" \
  --body "$(cat <<'EOF'
## Summary
Implement DIKW-aligned tiered knowledge classification with durability scoring (0-3) for the knowledge graph. Replace generic fact extraction with a 3-phase staged pipeline (Entity ID → Significance Filter → Triple Extraction) using PRISM prompt pattern.

## Scope
- Add `durability_score` (0-3) and `temporal_type` fields to facts table
- Revised importance formula: `S = 0.2R + 0.2F + 0.3T + 0.3D`
- 3-phase staged extraction pipeline optimized for 9B models
- Ingest-time quality filter (downgrade ephemeral insights to conversation type)
- Graph builder filter (exclude durability=0 from visualization)
- Retroactive cleanup script for existing low-quality insights
- Retroactive crystallization (weekly community detection on ephemeral clusters)

## Estimated Hours: 13h
## Plan: `docs/plans/research-tab-development-plan.md` — WS1

## Acceptance Criteria
- [ ] Facts have durability_score 0-3 assigned at extraction
- [ ] Ephemeral facts (durability=0) excluded from graph visualization
- [ ] Importance formula uses 4-factor weighting
- [ ] Existing low-quality insights reclassified
- [ ] Tests pass
EOF
)"
echo "  ✅ WS1: Insight Quality Framework"

gh issue create --repo "$REPO" --assignee "$ASSIGNEE" \
  --title "WS2: Principles Pipeline Fix + Auto-Distillation" \
  --label "sprint-20,sprint-20a,backend,research" \
  --body "$(cat <<'EOF'
## Summary
Fix empty Principles tab (likely never triggered distillation) and wire weekly auto-distillation into LearningScheduler.

## Scope
- Verify principles table is empty, trigger manual distillation
- Add `_run_principle_distillation()` to LearningScheduler (weekly, Sunday 3am)
- Config in `memory.yaml`: `principle_distillation` section
- Verify macOS UI renders distilled principles

## Estimated Hours: 3h
## Plan: `docs/plans/research-tab-development-plan.md` — WS2

## Acceptance Criteria
- [ ] Principles appear after manual distillation trigger
- [ ] Weekly auto-distillation scheduled in LearningScheduler
- [ ] macOS Principles tab renders pending/approved/rejected sections
- [ ] Tests pass
EOF
)"
echo "  ✅ WS2: Principles Pipeline Fix"

gh issue create --repo "$REPO" --assignee "$ASSIGNEE" \
  --title "WS3: Memory Tab UI Polish — Sort toggle, spacing cleanup" \
  --label "sprint-20,sprint-20a,macos" \
  --body "$(cat <<'EOF'
## Summary
Fix vertically compressed "Sort" text in segmented Picker. Audit and fix spacing issues on Memory tab.

## Scope
- Externalize Picker label, add `.labelsHidden()`, widen frame
- Audit filter pill spacing, pagination button boundaries, chunk row padding
- Build verification (both macOS and iOS targets)

## Estimated Hours: 2h
## Plan: `docs/plans/research-tab-development-plan.md` — WS3

## Acceptance Criteria
- [ ] Sort toggle text renders cleanly without vertical compression
- [ ] No spacing or boundary issues on Memory tab
- [ ] Both Xcode schemes build clean
EOF
)"
echo "  ✅ WS3: Memory Tab UI Polish"

gh issue create --repo "$REPO" --assignee "$ASSIGNEE" \
  --title "WS4: Graph Visual Weight System — diameter/opacity/glow mapped to durability/confidence/recency" \
  --label "sprint-20,sprint-20a,macos,research" \
  --body "$(cat <<'EOF'
## Summary
Implement perceptual visual encoding in 3D SceneKit graph. Node diameter maps to durability, opacity to confidence, glow to recency.

## Scope
- Update `MacSceneKitGraphView.swift` node rendering with multi-dimensional visual encoding
- Add "Significance" filter slider to `GraphControlPanel.swift`
- Diameter: 0.1 + (durability/3.0) * 0.2
- Opacity: 0.3 + confidence * 0.7
- Glow: recency * 0.8

## Estimated Hours: 3h
## Depends on: WS1 (durability scores must exist on facts)
## Plan: `docs/plans/research-tab-development-plan.md` — WS4

## Acceptance Criteria
- [ ] Graph nodes visually distinguish significance levels
- [ ] Filter slider hides nodes below durability threshold
- [ ] Both Xcode schemes build clean
EOF
)"
echo "  ✅ WS4: Graph Visual Weight System"

echo ""
echo "=== Sprint 20B Issues ==="

gh issue create --repo "$REPO" --assignee "$ASSIGNEE" \
  --title "WS5: Graph Source Expansion — Imported Knowledge + External Research categories" \
  --label "sprint-20,sprint-20b,backend,macos,research" \
  --body "$(cat <<'EOF'
## Summary
Add "Imported Knowledge" (Claude/ChatGPT/Gemini history) and "External Research" (task/order insights) as trackable, filterable source categories in the knowledge graph.

## Scope
- `SourceCategory` enum + `source_category` field on facts/entities
- `import_sources` table for tracking imports
- File import pipeline (3 providers: Claude existing, ChatGPT/Gemini new)
- Paste/ingest UI for ad-hoc snippets
- Memory tab staging workflow (imported content → review → approve → graph)
- Graph control panel source filtering
- macOS Import View within Research tab
- 4 new API endpoints (`/v1/research/import/*`)

## Estimated Hours: 18h
## Depends on: WS1 (quality framework for filtering imported content)
## Plan: `docs/plans/research-tab-development-plan.md` — WS5

## Acceptance Criteria
- [ ] Can import Claude/ChatGPT/Gemini conversation history
- [ ] Can paste ad-hoc text with provider tag
- [ ] Imported content lands in Memory tab for staging/review
- [ ] Approved content enters graph with source provenance
- [ ] Graph filterable by source category
- [ ] Tests pass
EOF
)"
echo "  ✅ WS5: Graph Source Expansion"

gh issue create --repo "$REPO" --assignee "$ASSIGNEE" \
  --title "WS7: Gemini CLI + /second-opinion skill (replaces /plan-audit)" \
  --label "sprint-20,sprint-20b,skill,gemini,infrastructure" \
  --body "$(cat <<'EOF'
## Summary
Install Gemini CLI, build /second-opinion skill that absorbs all 9 phases of /plan-audit and adds Phase 10: cross-model validation via Gemini.

## Scope
- Install `@google/gemini-cli` globally
- New skill: `.claude/skills/second-opinion/SKILL.md`
- Phases 1-9: Carried over from /plan-audit
- Phase 10: Prompt construction → Gemini dispatch → Response parsing → Reconciliation report
- Output: `docs/plans/[name]-second-opinion-[date].md`
- Remove old `/plan-audit` skill directory
- Future: Wire into Artemis as cross-model validation capability

## Estimated Hours: 4.25h
## Plan: `docs/plans/research-tab-development-plan.md` — WS7

## Acceptance Criteria
- [ ] `gemini --version` works
- [ ] `/second-opinion` runs Phases 1-9 (internal audit)
- [ ] Phase 10 dispatches to Gemini CLI and captures response
- [ ] Reconciliation report saved to docs/plans/
- [ ] Old /plan-audit removed
EOF
)"
echo "  ✅ WS7: Gemini CLI + /second-opinion"

echo ""
echo "=== Sprint 20C Issues ==="

gh issue create --repo "$REPO" --assignee "$ASSIGNEE" \
  --title "WS6: Intelligent Notification Relay — context-aware bumps to macOS or iPhone" \
  --label "sprint-20,sprint-20c,backend,macos,ios,infrastructure" \
  --body "$(cat <<'EOF'
## Summary
Build notification relay so Claude Code sessions can push approval requests to Andrew's iPhone or MacBook based on activity context. MacBook active → macOS notification. Idle >2min → APNs push to iPhone.

## Scope
**Backend (new `hestia/notifications/` module):**
- BumpRequest/BumpResponse models + SQLite table
- NotificationRouter with idle detection (IOKit HIDIdleTime)
- APNs HTTP/2 client (aioapns)
- macOS notifier (osascript or UNUserNotificationCenter)
- Rate limiting (1 bump/5min/session), keyed debouncing
- Quiet hours + Focus mode respect
- Bump expiry (15 min)
- 5 new API endpoints (`/v1/notifications/*`)

**iOS:**
- `registerForRemoteNotifications()` in app startup
- Device token capture → API registration
- Actionable notifications (force-touch: Approve / Deny)
- `UNUserNotificationCenterDelegate` response handling

**Claude Code integration:**
- `hestia bump` CLI command (blocks until response)

## Estimated Hours: 20h
## Prerequisites: Apple Developer account with push capability, APNs auth key
## Plan: `docs/plans/research-tab-development-plan.md` — WS6

## Acceptance Criteria
- [ ] Claude Code can trigger bump via API
- [ ] MacBook notification when active
- [ ] iPhone push when idle >2 min
- [ ] Force-touch approve/deny works on iPhone
- [ ] Rate limiting prevents spam
- [ ] Quiet hours respected
- [ ] Tests pass
EOF
)"
echo "  ✅ WS6: Notification Relay"

echo ""
echo "=== Workflow Orchestrator Issues (Future) ==="

gh issue create --repo "$REPO" --assignee "$ASSIGNEE" \
  --title "Workflow Orchestrator Phase 1: DAG Engine + Linear Canvas UI + Orders Migration" \
  --label "workflow-orchestrator,backend,macos" \
  --body "$(cat <<'EOF'
## Summary
Build the core DAG execution engine with asyncio.TaskGroup, SQLite checkpointing, dead path elimination, and a basic SwiftUI canvas editor. Migrate existing Orders to 2-node workflows.

## Scope
- Workflow/Node/Edge/Run/NodeExecution data models + SQLite tables
- DAGExecutor with TaskGroup (structured concurrency)
- Dead path elimination for condition branches
- SQLite checkpointing (crash recovery)
- Workflow version snapshotting
- WorkflowScheduler wrapping APScheduler
- 4 Action nodes: RunPrompt, CallTool, Notify, Log
- 2 Trigger nodes: Schedule, Manual
- Orders → Workflows migration script
- 10+ API endpoints
- macOS canvas: node palette, click-click connections, node inspector, execution feedback

## Estimated Hours: 35h
## Plan: `docs/plans/visual-workflow-orchestrator-brainstorm.md`
## Prerequisites: Sprint 20C (Notification Relay for Notify node)

## Acceptance Criteria
- [ ] Can create and run linear workflows visually
- [ ] Parallel branches execute via TaskGroup
- [ ] Crash recovery resumes from last checkpoint
- [ ] Existing Orders migrated to workflows
- [ ] Real-time execution feedback on canvas
- [ ] Tests pass, both Xcode schemes build
EOF
)"
echo "  ✅ Orchestrator Phase 1"

gh issue create --repo "$REPO" --assignee "$ASSIGNEE" \
  --title "Workflow Orchestrator Phase 2: Conditions + JMESPath + Pydantic Schemas + Debouncing" \
  --label "workflow-orchestrator,backend,macos" \
  --body "$(cat <<'EOF'
## Summary
Add conditional branching (If/Else, Switch, Confidence Gate), JMESPath variable interpolation, optional Pydantic schemas for node I/O, and keyed debouncing.

## Estimated Hours: 18h
## Depends on: Phase 1
## Plan: `docs/plans/visual-workflow-orchestrator-brainstorm.md`
EOF
)"
echo "  ✅ Orchestrator Phase 2"

gh issue create --repo "$REPO" --assignee "$ASSIGNEE" \
  --title "Workflow Orchestrator Phase 3: EventKit/FSEvents Triggers + HMAC Webhooks + Token Budgets" \
  --label "workflow-orchestrator,backend,macos" \
  --body "$(cat <<'EOF'
## Summary
Add OS-native event triggers (EventKit for calendar/reminders, FSEvents for filesystem), HMAC-SHA256 webhook authentication, token budget enforcement, and advanced control nodes (Join, Merge, Loop, Error Handler, Sub-Workflow).

## Estimated Hours: 22h
## Depends on: Phase 2
## Plan: `docs/plans/visual-workflow-orchestrator-brainstorm.md`
EOF
)"
echo "  ✅ Orchestrator Phase 3"

gh issue create --repo "$REPO" --assignee "$ASSIGNEE" \
  --title "Workflow Orchestrator Phase 4: Templates + Semantic Zoom + Sugiyama Layout + Replay" \
  --label "workflow-orchestrator,backend,macos" \
  --body "$(cat <<'EOF'
## Summary
Polish phase: 6 pre-built workflow templates, JSON export/import, semantic zoom (3 levels), Sugiyama auto-layout, execution replay with checkpoint visualization, keyboard shortcuts.

## Estimated Hours: 10h
## Depends on: Phase 3
## Plan: `docs/plans/visual-workflow-orchestrator-brainstorm.md`
EOF
)"
echo "  ✅ Orchestrator Phase 4"

echo ""
echo "=== Done! ==="
echo "Created 11 issues with labels and assignments."
echo ""
echo "Next: Add issues to Project board manually or via:"
echo "  gh project item-add 1 --owner $ASSIGNEE --url <issue-url>"
