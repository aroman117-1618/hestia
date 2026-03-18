#!/usr/bin/env bash
# gh-project-sync.sh — GitHub Project board helper for Hestia
# Usage:
#   gh-project-sync.sh list                        — show all items + status
#   gh-project-sync.sh add "<title>"               — create a new draft item
#   gh-project-sync.sh status <item-id> <status>   — set status (todo|in_progress|done)

set -euo pipefail

OWNER="aroman117-1618"
PROJECT_NUMBER="1"
PROJECT_ID="PVT_kwHODI9jOM4BSG9c"

cmd="${1:-list}"

case "$cmd" in
  list)
    echo "=== Hestia Roadmap (Project #${PROJECT_NUMBER}) ==="
    gh project item-list "$PROJECT_NUMBER" --owner "$OWNER" --format json \
      | jq -r '.items[] | "\(.status // "No Status")\t\(.title)"' \
      | column -t -s $'\t' 2>/dev/null \
      || gh project item-list "$PROJECT_NUMBER" --owner "$OWNER"
    ;;

  add)
    title="${2:?Usage: gh-project-sync.sh add \"<title>\"}"
    result=$(gh project item-create "$PROJECT_NUMBER" --owner "$OWNER" --title "$title" --format json 2>/dev/null || true)
    echo "Created: $title"
    echo "$result"
    ;;

  status)
    item_id="${2:?Usage: gh-project-sync.sh status <item-id> <todo|in_progress|done>}"
    new_status="${3:?Usage: gh-project-sync.sh status <item-id> <todo|in_progress|done>}"

    # Resolve the Status field ID and option ID
    fields=$(gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --format json)
    status_field_id=$(echo "$fields" | jq -r '.fields[] | select(.name == "Status") | .id')

    if [[ -z "$status_field_id" ]]; then
      echo "Error: could not find Status field on project" >&2
      exit 1
    fi

    # Map friendly names to GitHub option names
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
      echo "Error: status option '$option_name' not found. Valid: Todo, In Progress, Done" >&2
      exit 1
    fi

    gh project item-edit \
      --id "$item_id" \
      --field-id "$status_field_id" \
      --single-select-option-id "$option_id" \
      --project-id "$PROJECT_ID"

    echo "Updated $item_id → $option_name"
    ;;

  *)
    echo "Usage: gh-project-sync.sh <list|add|status>" >&2
    exit 1
    ;;
esac
