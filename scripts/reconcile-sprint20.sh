#!/usr/bin/env bash
# reconcile-sprint20.sh — One-time script to clean up draft items and create proper issues
#
# Run from MacBook: bash scripts/reconcile-sprint20.sh
#
# This script:
# 1. Ensures all standard labels exist
# 2. Deletes all existing draft items from the project board
# 3. Creates proper GitHub Issues with labels, assignees, bodies, and dates
# 4. Adds each issue to the Project board with start/deadline dates
#
# Timeline: Sprint 20 runs Wed March 18 - Sat March 21, 2026
# Andrew's availability: ~12 hours/week hands-on + autonomous Claude Code acceleration
# Phase 20A (~21h): Wed Mar 18 - Thu Mar 20
# Phase 20B (~22h): Fri Mar 21 - following week
# Phase 20C (~20h): Can parallel with Sprint 21

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYNC="$SCRIPT_DIR/roadmap-sync.sh"

echo "============================================"
echo "  Hestia Sprint 20 — Full Reconciliation"
echo "============================================"
echo ""

# ─── Step 1: Ensure labels ─────────────────────────────────────
echo "Step 1: Ensuring labels..."
"$SYNC" labels
echo ""

# ─── Step 2: Delete existing draft items ───────────────────────
echo "Step 2: Cleaning up draft items from project board..."
OWNER="aroman117-1618"
PROJECT_NUMBER="1"

items=$(gh project item-list "$PROJECT_NUMBER" --owner "$OWNER" --format json 2>/dev/null || echo '{"items":[]}')
drafts=$(echo "$items" | jq -r '.items[] | select(.content.type == "DraftIssue" or .content.number == null) | .id' 2>/dev/null || true)

if [[ -n "$drafts" ]]; then
  echo "$drafts" | while read -r draft_id; do
    if [[ -n "$draft_id" ]]; then
      title=$(echo "$items" | jq -r --arg id "$draft_id" '.items[] | select(.id == $id) | .title')
      echo "  Deleting draft: $title ($draft_id)"
      gh project item-delete "$PROJECT_NUMBER" --owner "$OWNER" --id "$draft_id" 2>/dev/null || true
    fi
  done
  echo "  ✅ Drafts cleaned up."
else
  echo "  No drafts to clean up."
fi
echo ""

# ─── Step 3: Create Sprint 20A Issues (Wed Mar 18 - Thu Mar 20) ─
echo "Step 3: Creating Sprint 20A issues..."
echo ""

"$SYNC" issue "WS2: Principles Pipeline Fix + Auto-Distillation" \
  --labels "sprint-20,sprint-20a,backend,research,principles" \
  --hours 3 \
  --sprint "Sprint 20A" \
  --start "2026-03-18" \
  --deadline "2026-03-18" \
  --plan "docs/plans/research-tab-development-plan.md" \
  --body "$(cat <<'EOF'
## Summary
Fix empty Principles tab (likely never triggered distillation) and wire weekly auto-distillation into LearningScheduler.

## Scope
- Verify principles table is empty, trigger manual distillation
- Add `_run_principle_distillation()` to LearningScheduler (weekly, Sunday 3am)
- Config in `memory.yaml`: `principle_distillation` section
- Verify macOS Principles tab renders pending/approved/rejected sections

## Estimated Hours: 3h
**Start Date:** 2026-03-18 | **Deadline:** 2026-03-18
**Sprint Phase:** Sprint 20A
**Plan:** `docs/plans/research-tab-development-plan.md` — WS2

## Acceptance Criteria
- [ ] Principles appear after manual distillation trigger
- [ ] Weekly auto-distillation scheduled in LearningScheduler
- [ ] macOS Principles tab renders pending/approved/rejected sections
- [ ] Tests pass
EOF
)"

"$SYNC" issue "WS3: Memory Tab UI Polish — Sort toggle, spacing cleanup" \
  --labels "sprint-20,sprint-20a,macos,ui-polish" \
  --hours 2 \
  --sprint "Sprint 20A" \
  --start "2026-03-18" \
  --deadline "2026-03-18" \
  --plan "docs/plans/research-tab-development-plan.md" \
  --body "$(cat <<'EOF'
## Summary
Fix vertically compressed "Sort" text in segmented Picker. Audit and fix spacing issues on Memory tab.

## Scope
- Externalize Picker label, add `.labelsHidden()`, widen frame
- Audit filter pill spacing, pagination button boundaries, chunk row padding
- Build verification (both macOS and iOS targets)

## Estimated Hours: 2h
**Start Date:** 2026-03-18 | **Deadline:** 2026-03-18
**Sprint Phase:** Sprint 20A
**Plan:** `docs/plans/research-tab-development-plan.md` — WS3

## Acceptance Criteria
- [ ] Sort toggle text renders cleanly without vertical compression
- [ ] No spacing or boundary issues on Memory tab
- [ ] Both Xcode schemes build clean
EOF
)"

"$SYNC" issue "WS1: Insight Quality Framework — DIKW tiers, 3-phase extraction, durability scoring" \
  --labels "sprint-20,sprint-20a,backend,research,memory" \
  --hours 13 \
  --sprint "Sprint 20A" \
  --start "2026-03-18" \
  --deadline "2026-03-20" \
  --plan "docs/plans/research-tab-development-plan.md" \
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
**Start Date:** 2026-03-18 | **Deadline:** 2026-03-20
**Sprint Phase:** Sprint 20A
**Plan:** `docs/plans/research-tab-development-plan.md` — WS1

## Acceptance Criteria
- [ ] Facts have durability_score 0-3 assigned at extraction
- [ ] Ephemeral facts (durability=0) excluded from graph visualization
- [ ] Importance formula uses 4-factor weighting
- [ ] Existing low-quality insights reclassified
- [ ] Tests pass
EOF
)"

"$SYNC" issue "WS4: Graph Visual Weight System — perceptual mapping" \
  --labels "sprint-20,sprint-20a,macos,research" \
  --hours 3 \
  --sprint "Sprint 20A" \
  --start "2026-03-20" \
  --deadline "2026-03-20" \
  --depends "WS1 (durability scores must exist)" \
  --plan "docs/plans/research-tab-development-plan.md" \
  --body "$(cat <<'EOF'
## Summary
Implement perceptual visual encoding in 3D SceneKit graph. Node diameter maps to durability, opacity to confidence, glow to recency.

## Scope
- Update `MacSceneKitGraphView.swift` node rendering with multi-dimensional encoding
- Add "Significance" filter slider to `GraphControlPanel.swift`
- Diameter: 0.1 + (durability/3.0) * 0.2
- Opacity: 0.3 + confidence * 0.7
- Glow: recency * 0.8

## Estimated Hours: 3h
**Start Date:** 2026-03-20 | **Deadline:** 2026-03-20
**Dependencies:** WS1 (durability scores must exist on facts)
**Sprint Phase:** Sprint 20A
**Plan:** `docs/plans/research-tab-development-plan.md` — WS4

## Acceptance Criteria
- [ ] Graph nodes visually distinguish significance levels
- [ ] Filter slider hides nodes below durability threshold
- [ ] Both Xcode schemes build clean
EOF
)"

echo ""
echo "=== Sprint 20B Issues (Fri Mar 21+) ==="
echo ""

"$SYNC" issue "WS5: Graph Source Expansion — Imported Knowledge + External Research" \
  --labels "sprint-20,sprint-20b,backend,macos,research" \
  --hours 18 \
  --sprint "Sprint 20B" \
  --start "2026-03-21" \
  --deadline "2026-03-28" \
  --depends "WS1 (quality framework)" \
  --plan "docs/plans/research-tab-development-plan.md" \
  --body "$(cat <<'EOF'
## Summary
Add "Imported Knowledge" (Claude/ChatGPT/Gemini history) and "External Research" (task/order insights) as trackable, filterable source categories in the knowledge graph.

## Scope
- `SourceCategory` enum + `source_category` field on facts/entities
- `import_sources` table for tracking imports
- File import pipeline (3 providers: Claude existing, ChatGPT/Gemini new)
- Paste/ingest UI for ad-hoc snippets
- Memory tab staging workflow
- Graph control panel source filtering
- macOS Import View within Research tab
- 4 new API endpoints

## Estimated Hours: 18h
**Start Date:** 2026-03-21 | **Deadline:** 2026-03-28
**Dependencies:** WS1 (quality framework for filtering imported content)
**Sprint Phase:** Sprint 20B
**Plan:** `docs/plans/research-tab-development-plan.md` — WS5

## Acceptance Criteria
- [ ] Can import Claude/ChatGPT/Gemini conversation history
- [ ] Can paste ad-hoc text with provider tag
- [ ] Imported content lands in Memory tab for staging/review
- [ ] Approved content enters graph with source provenance
- [ ] Graph filterable by source category
- [ ] Tests pass
EOF
)"

"$SYNC" issue "WS7: Gemini CLI + /second-opinion skill (replaces /plan-audit)" \
  --labels "sprint-20,sprint-20b,skill,gemini,infrastructure" \
  --hours 4.25 \
  --sprint "Sprint 20B" \
  --start "2026-03-21" \
  --deadline "2026-03-22" \
  --plan "docs/plans/research-tab-development-plan.md" \
  --body "$(cat <<'EOF'
## Summary
Install Gemini CLI, build /second-opinion skill that absorbs all 9 phases of /plan-audit and adds Phase 10: cross-model validation via Gemini.

## Scope
- Install `@google/gemini-cli` globally
- New skill: `.claude/skills/second-opinion/SKILL.md` (Phases 1-9 from plan-audit + Phase 10 Gemini dispatch)
- Output: `docs/plans/[name]-second-opinion-[date].md`
- Remove old /plan-audit skill directory

## Estimated Hours: 4.25h
**Start Date:** 2026-03-21 | **Deadline:** 2026-03-22
**Sprint Phase:** Sprint 20B
**Plan:** `docs/plans/research-tab-development-plan.md` — WS7

## Acceptance Criteria
- [ ] `gemini --version` works
- [ ] `/second-opinion` runs Phases 1-9 + Phase 10 (Gemini dispatch)
- [ ] Reconciliation report saved to docs/plans/
- [ ] Old /plan-audit removed
EOF
)"

echo ""
echo "=== Sprint 20C Issues (Parallel with Sprint 21) ==="
echo ""

"$SYNC" issue "WS6: Intelligent Notification Relay — macOS/iPhone context-aware bumps" \
  --labels "sprint-20,sprint-20c,backend,macos,ios,notifications,infrastructure" \
  --hours 20 \
  --sprint "Sprint 20C" \
  --start "2026-03-24" \
  --deadline "2026-04-04" \
  --plan "docs/plans/research-tab-development-plan.md" \
  --body "$(cat <<'EOF'
## Summary
Build notification relay so Claude Code sessions can push approval requests to Andrew's iPhone or MacBook based on activity context. MacBook active → macOS notification. Idle >2min → APNs push to iPhone.

## Scope
**Backend (`hestia/notifications/`):** BumpRequest model, NotificationRouter (idle detection via IOKit), APNs HTTP/2 client, macOS notifier, rate limiting, quiet hours, 5 API endpoints.
**iOS:** registerForRemoteNotifications, device token capture, actionable notifications (force-touch approve/deny).
**Claude Code:** `hestia bump` CLI command.

## Estimated Hours: 20h
**Start Date:** 2026-03-24 | **Deadline:** 2026-04-04
**Prerequisites:** Apple Developer account with push capability
**Sprint Phase:** Sprint 20C
**Plan:** `docs/plans/research-tab-development-plan.md` — WS6

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

echo ""
echo "=== Workflow Orchestrator Issues (Future) ==="
echo ""

"$SYNC" issue "Workflow Orchestrator Phase 1: DAG Engine + Linear Canvas UI + Orders Migration" \
  --labels "workflow-orchestrator,backend,macos,workflow-engine" \
  --hours 35 \
  --sprint "Future" \
  --start "2026-04-07" \
  --deadline "2026-04-25" \
  --depends "Sprint 20C (Notification Relay for Notify node)" \
  --plan "docs/plans/visual-workflow-orchestrator-brainstorm.md" \
  --body "$(cat <<'EOF'
## Summary
Build the core DAG execution engine with asyncio.TaskGroup, SQLite checkpointing, dead path elimination, and a basic SwiftUI canvas editor. Migrate existing Orders to 2-node workflows.

## Scope
- Workflow/Node/Edge/Run/NodeExecution data models + SQLite tables
- DAGExecutor with TaskGroup (structured concurrency)
- Dead path elimination, SQLite checkpointing (crash recovery)
- Workflow version snapshotting
- 4 Action nodes + 2 Trigger nodes + Orders migration
- 10+ API endpoints
- macOS canvas: node palette, click-click connections, node inspector, execution feedback

## Estimated Hours: 35h
**Start Date:** 2026-04-07 | **Deadline:** 2026-04-25
**Dependencies:** Sprint 20C (Notification Relay for Notify node)
**Plan:** `docs/plans/visual-workflow-orchestrator-brainstorm.md`
EOF
)"

"$SYNC" issue "Workflow Orchestrator Phase 2: Conditions + JMESPath + Pydantic Schemas" \
  --labels "workflow-orchestrator,backend,macos,workflow-engine" \
  --hours 18 \
  --sprint "Future" \
  --start "2026-04-28" \
  --deadline "2026-05-09" \
  --depends "Orchestrator Phase 1" \
  --plan "docs/plans/visual-workflow-orchestrator-brainstorm.md"

"$SYNC" issue "Workflow Orchestrator Phase 3: EventKit/FSEvents + HMAC Webhooks + Token Budgets" \
  --labels "workflow-orchestrator,backend,macos,workflow-engine" \
  --hours 22 \
  --sprint "Future" \
  --start "2026-05-12" \
  --deadline "2026-05-23" \
  --depends "Orchestrator Phase 2" \
  --plan "docs/plans/visual-workflow-orchestrator-brainstorm.md"

"$SYNC" issue "Workflow Orchestrator Phase 4: Templates + Semantic Zoom + Sugiyama Layout" \
  --labels "workflow-orchestrator,backend,macos,workflow-engine" \
  --hours 10 \
  --sprint "Future" \
  --start "2026-05-26" \
  --deadline "2026-05-30" \
  --depends "Orchestrator Phase 3" \
  --plan "docs/plans/visual-workflow-orchestrator-brainstorm.md"

echo ""
echo "============================================"
echo "  ✅ Reconciliation Complete!"
echo "============================================"
echo ""
echo "Created 11 issues with:"
echo "  - Labels and assignee"
echo "  - Estimated hours and acceptance criteria"
echo "  - Start dates and deadlines"
echo "  - Dependencies and plan references"
echo "  - All linked to Project #1"
echo ""
echo "Timeline:"
echo "  Sprint 20A: Wed Mar 18 - Thu Mar 20 (21h)"
echo "  Sprint 20B: Fri Mar 21 - Fri Mar 28 (22.25h)"
echo "  Sprint 20C: Mon Mar 24 - Fri Apr 4 (20h, parallel with S21)"
echo "  Orchestrator P1: Mon Apr 7 - Fri Apr 25 (35h)"
echo "  Orchestrator P2: Mon Apr 28 - Fri May 9 (18h)"
echo "  Orchestrator P3: Mon May 12 - Fri May 23 (22h)"
echo "  Orchestrator P4: Mon May 26 - Fri May 30 (10h)"
