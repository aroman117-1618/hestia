#!/usr/bin/env bash
# roadmap-sync.sh — Full roadmap synchronization tool for Hestia
#
# This is the SINGLE ENTRY POINT for all GitHub Project + Issue management.
# Claude should call this script whenever "add to roadmap" is requested.
#
# Usage:
#   roadmap-sync.sh reconcile                          — Reconcile: delete orphan drafts, ensure all issues are on board
#   roadmap-sync.sh issue "<title>" [options]           — Create issue + add to project board
#   roadmap-sync.sh list                                — List all project board items with status
#   roadmap-sync.sh status <item-id> <status>           — Update item status (todo|in_progress|done)
#   roadmap-sync.sh close <issue-number>                — Close an issue
#   roadmap-sync.sh labels                              — Ensure all standard labels exist
#
# Issue creation options (passed after title):
#   --labels "label1,label2"       — Comma-separated labels
#   --hours N                      — Estimated hours (added to body)
#   --sprint "Sprint 20A"          — Sprint phase tag
#   --depends "WS1,WS3"           — Dependencies (added to body)
#   --plan "path/to/plan.md"      — Reference plan document
#   --body "description"           — Full issue body (overrides auto-generation)
#   --milestone "Sprint 20"        — Milestone name
#
# Examples:
#   roadmap-sync.sh issue "WS8: New Feature" --labels "sprint-20,backend" --hours 10 --sprint "Sprint 20A"
#   roadmap-sync.sh reconcile
#   roadmap-sync.sh status PVTI_abc123 in_progress

set -euo pipefail

REPO="aroman117-1618/hestia"
OWNER="aroman117-1618"
ASSIGNEE="aroman117-1618"
PROJECT_NUMBER="1"
PROJECT_ID="PVT_kwHODI9jOM4BSG9c"

# ─── Standard Labels (bash 3.2 compatible — no associative arrays) ─
# Format: "name|color|description" per line
LABEL_DEFS="
sprint-20|0E8A16|Sprint 20: Neural Net Graph Phase 2
sprint-20a|1D76DB|Sprint 20A: Quality Framework
sprint-20b|5319E7|Sprint 20B: Source Expansion
sprint-20c|D93F0B|Sprint 20C: Notification Relay
sprint-21|0075CA|Sprint 21: Trading Foundation
workflow-orchestrator|FBCA04|Visual Workflow Orchestrator
backend|C5DEF5|Python backend changes
macos|BFD4F2|macOS SwiftUI app changes
ios|D4C5F9|iOS app changes
research|F9D0C4|Knowledge graph / research module
infrastructure|E4E669|Infra, tooling, CI/CD
skill|C2E0C6|Claude Code skill
gemini|006B75|Gemini CLI integration
trading|B60205|Trading module
notifications|FBCA04|Notification relay system
workflow-engine|D4C5F9|DAG workflow engine
ui-polish|BFD4F2|UI cleanup and polish
memory|F9D0C4|Memory system
principles|F9D0C4|Principles pipeline
"

cmd="${1:-list}"

# ─── Helper: Ensure labels ────────────────────────────────────────
ensure_labels() {
  echo "Ensuring standard labels exist..."
  echo "$LABEL_DEFS" | while IFS='|' read -r label color desc; do
    # Skip empty lines
    [ -z "$label" ] && continue
    gh label create "$label" --repo "$REPO" --color "$color" --description "$desc" 2>/dev/null && echo "  Created: $label" || true
  done
  echo "Labels synced."
}

# ─── Helper: Add issue to project board ───────────────────────────
add_to_project() {
  local issue_url="$1"
  echo "  Adding to Project #${PROJECT_NUMBER}..."
  gh project item-add "$PROJECT_NUMBER" --owner "$OWNER" --url "$issue_url" 2>/dev/null \
    && echo "  ✅ Added to project board" \
    || echo "  ⚠️  May already be on board (or project access issue)"
}

# ─── Command: list ────────────────────────────────────────────────
case "$cmd" in
  list)
    echo "=== Hestia Roadmap (Project #${PROJECT_NUMBER}) ==="
    echo ""
    # Try JSON format first for clean output
    items=$(gh project item-list "$PROJECT_NUMBER" --owner "$OWNER" --format json 2>/dev/null || echo '{"items":[]}')
    echo "$items" | jq -r '
      .items[]
      | "\(.status // "No Status")\t\(.type // "?")\t#\(.content.number // "draft")\t\(.title)"
    ' | column -t -s $'\t' 2>/dev/null \
      || gh project item-list "$PROJECT_NUMBER" --owner "$OWNER"
    ;;

  # ─── Command: labels ──────────────────────────────────────────
  labels)
    ensure_labels
    ;;

  # ─── Command: issue ───────────────────────────────────────────
  issue)
    shift
    title="${1:?Usage: roadmap-sync.sh issue \"<title>\" [--labels ...] [--hours N] [--sprint ...] [--depends ...] [--plan ...]}"
    shift

    # Parse options
    labels=""
    hours=""
    sprint=""
    depends=""
    plan=""
    body=""
    milestone=""
    start_date=""
    deadline=""

    while [[ $# -gt 0 ]]; do
      case "$1" in
        --labels)    labels="$2"; shift 2 ;;
        --hours)     hours="$2"; shift 2 ;;
        --sprint)    sprint="$2"; shift 2 ;;
        --depends)   depends="$2"; shift 2 ;;
        --plan)      plan="$2"; shift 2 ;;
        --body)      body="$2"; shift 2 ;;
        --milestone) milestone="$2"; shift 2 ;;
        --start)     start_date="$2"; shift 2 ;;
        --deadline)  deadline="$2"; shift 2 ;;
        *)           echo "Unknown option: $1" >&2; exit 1 ;;
      esac
    done

    # Auto-generate body if not provided
    if [[ -z "$body" ]]; then
      body="## Details"$'\n'
      [[ -n "$hours" ]]      && body+=$'\n'"**Estimated Hours:** ${hours}h"
      [[ -n "$sprint" ]]     && body+=$'\n'"**Sprint Phase:** ${sprint}"
      [[ -n "$start_date" ]] && body+=$'\n'"**Start Date:** ${start_date}"
      [[ -n "$deadline" ]]   && body+=$'\n'"**Deadline:** ${deadline}"
      [[ -n "$depends" ]]    && body+=$'\n'"**Dependencies:** ${depends}"
      [[ -n "$plan" ]]       && body+=$'\n'"**Plan Document:** \`${plan}\`"
      body+=$'\n\n'"---"$'\n'"_Created via roadmap-sync.sh_"
    fi

    # Build gh issue create command
    gh_args=(
      --repo "$REPO"
      --assignee "$ASSIGNEE"
      --title "$title"
      --body "$body"
    )
    [[ -n "$labels" ]]    && gh_args+=(--label "$labels")
    [[ -n "$milestone" ]] && gh_args+=(--milestone "$milestone")

    echo "Creating issue: $title"
    issue_url=$(gh issue create "${gh_args[@]}" --json url -q '.url' 2>/dev/null \
      || gh issue create "${gh_args[@]}" | tail -1)
    echo "  ✅ Created: $issue_url"

    # Add to project board
    add_to_project "$issue_url"

    # ─── Self-healing verification: ensure assignee + labels applied ───
    issue_number=$(echo "$issue_url" | grep -o '[0-9]*$')
    if [[ -n "$issue_number" ]]; then
      echo "  Verifying assignee and labels on #${issue_number}..."
      gh issue edit "$issue_number" --repo "$REPO" --add-assignee "$ASSIGNEE" 2>/dev/null \
        && echo "  ✅ Assignee verified" || true
      if [[ -n "$labels" ]]; then
        gh issue edit "$issue_number" --repo "$REPO" --add-label "$labels" 2>/dev/null \
          && echo "  ✅ Labels verified" || true
      fi
    fi

    # Set date fields on project board item if provided
    if [[ -n "$start_date" || -n "$deadline" ]]; then
      # Get the project item ID for this issue
      sleep 1  # Brief pause for project board to register the item
      item_id=$(gh project item-list "$PROJECT_NUMBER" --owner "$OWNER" --format json 2>/dev/null \
        | jq -r --arg url "$issue_url" '.items[] | select(.content.url == $url) | .id' 2>/dev/null || true)

      if [[ -n "$item_id" && "$item_id" != "null" ]]; then
        fields=$(gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --format json 2>/dev/null || echo '{"fields":[]}')

        if [[ -n "$start_date" ]]; then
          start_field_id=$(echo "$fields" | jq -r '.fields[] | select(.name == "Start date") | .id' 2>/dev/null || true)
          if [[ -n "$start_field_id" && "$start_field_id" != "null" ]]; then
            gh project item-edit --id "$item_id" --field-id "$start_field_id" --date "$start_date" --project-id "$PROJECT_ID" 2>/dev/null \
              && echo "  📅 Start date set: $start_date" || true
          fi
        fi

        if [[ -n "$deadline" ]]; then
          deadline_field_id=$(echo "$fields" | jq -r '.fields[] | select(.name == "End date" or .name == "Due date" or .name == "Deadline") | .id' 2>/dev/null || true)
          if [[ -n "$deadline_field_id" && "$deadline_field_id" != "null" ]]; then
            gh project item-edit --id "$item_id" --field-id "$deadline_field_id" --date "$deadline" --project-id "$PROJECT_ID" 2>/dev/null \
              && echo "  📅 Deadline set: $deadline" || true
          fi
        fi
      fi
    fi
    echo ""
    ;;

  # ─── Command: reconcile ──────────────────────────────────────
  reconcile)
    echo "=== Reconciling GitHub Project Board ==="
    echo ""

    # Step 1: Ensure labels
    ensure_labels
    echo ""

    # Step 2: Get all project items
    echo "Fetching project items..."
    items=$(gh project item-list "$PROJECT_NUMBER" --owner "$OWNER" --format json 2>/dev/null || echo '{"items":[]}')
    total=$(echo "$items" | jq '.items | length')
    echo "Found $total items on board."
    echo ""

    # Step 3: Identify draft items (no issue backing)
    echo "Checking for draft items (no issue backing)..."
    drafts=$(echo "$items" | jq -r '.items[] | select(.content.type == "DraftIssue" or .content.number == null) | .id')
    draft_count=$(echo "$drafts" | grep -c . 2>/dev/null || echo 0)

    if [[ "$draft_count" -gt 0 ]]; then
      echo "  Found $draft_count draft items. Listing:"
      echo "$items" | jq -r '.items[] | select(.content.type == "DraftIssue" or .content.number == null) | "  - \(.title) (ID: \(.id))"'
      echo ""
      echo "  These drafts should be converted to proper issues."
      echo "  To delete a draft: gh project item-delete $PROJECT_NUMBER --owner $OWNER --id <ITEM_ID>"
      echo ""
    else
      echo "  No orphan drafts found. ✅"
    fi

    # Step 4: Check that all open issues with sprint labels are on the board
    echo "Checking for issues missing from project board..."
    board_issue_numbers=$(echo "$items" | jq -r '.items[] | select(.content.number != null) | .content.number')

    for label in sprint-20 sprint-20a sprint-20b sprint-20c workflow-orchestrator; do
      issues=$(gh issue list --repo "$REPO" --label "$label" --state open --json number,title 2>/dev/null || echo '[]')
      echo "$issues" | jq -r '.[] | "\(.number)\t\(.title)"' | while IFS=$'\t' read -r num title; do
        if ! echo "$board_issue_numbers" | grep -q "^${num}$"; then
          echo "  ⚠️  Issue #$num ($title) has label '$label' but is NOT on the project board."
          echo "     Fix: gh project item-add $PROJECT_NUMBER --owner $OWNER --url https://github.com/$REPO/issues/$num"
        fi
      done
    done
    echo ""

    # Step 5: Summary
    echo "=== Reconciliation Complete ==="
    echo "Board items: $total"
    echo "Draft items: $draft_count"
    echo ""
    echo "To clean up drafts and replace with proper issues:"
    echo "  1. Run: roadmap-sync.sh issue \"<title>\" --labels ... --hours ..."
    echo "  2. Then delete the draft: gh project item-delete $PROJECT_NUMBER --owner $OWNER --id <ITEM_ID>"
    ;;

  # ─── Command: status ──────────────────────────────────────────
  status)
    item_id="${2:?Usage: roadmap-sync.sh status <item-id> <todo|in_progress|done>}"
    new_status="${3:?Usage: roadmap-sync.sh status <item-id> <todo|in_progress|done>}"

    fields=$(gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --format json)
    status_field_id=$(echo "$fields" | jq -r '.fields[] | select(.name == "Status") | .id')

    case "$new_status" in
      todo)        option_name="Todo" ;;
      in_progress) option_name="In Progress" ;;
      done)        option_name="Done" ;;
      *)           option_name="$new_status" ;;
    esac

    option_id=$(echo "$fields" \
      | jq -r --arg name "$option_name" \
        '.fields[] | select(.name == "Status") | .options[] | select(.name == $name) | .id')

    if [[ -z "$option_id" ]]; then
      echo "Error: status option '$option_name' not found." >&2
      exit 1
    fi

    gh project item-edit \
      --id "$item_id" \
      --field-id "$status_field_id" \
      --single-select-option-id "$option_id" \
      --project-id "$PROJECT_ID"

    echo "Updated $item_id → $option_name"
    ;;

  # ─── Command: close ───────────────────────────────────────────
  close)
    issue_number="${2:?Usage: roadmap-sync.sh close <issue-number>}"
    gh issue close "$issue_number" --repo "$REPO"
    echo "Closed issue #$issue_number"
    ;;

  *)
    echo "Usage: roadmap-sync.sh <list|issue|reconcile|status|close|labels>" >&2
    exit 1
    ;;
esac
