#!/usr/bin/env bash
# sync-board-from-sprint.sh — Reconcile GitHub Project board state from SPRINT.md
#
# Parses SPRINT.md for workstream completion markers and updates the GitHub
# Project board to match. Closes issues and marks Done for completed work,
# marks In Progress for active work.
#
# Usage:
#   scripts/sync-board-from-sprint.sh          — dry run (report only)
#   scripts/sync-board-from-sprint.sh --apply  — apply changes
#
# Called from:
#   - /handoff skill (Phase 4)
#   - scripts/post-commit.sh (optional)
#   - Manual invocation

set -euo pipefail

REPO="aroman117-1618/hestia"
OWNER="aroman117-1618"
PROJECT_NUMBER="1"
SPRINT_FILE="SPRINT.md"
DRY_RUN=true

if [[ "${1:-}" == "--apply" ]]; then
  DRY_RUN=false
fi

# ─── Step 1: Parse SPRINT.md for completion status ────────────────
echo "=== Sync Board from SPRINT.md ==="
echo ""

if [[ ! -f "$SPRINT_FILE" ]]; then
  echo "ERROR: $SPRINT_FILE not found" >&2
  exit 1
fi

# Build pipe-delimited pattern strings from SPRINT.md
# We look for lines containing "COMPLETE" or "IN PROGRESS" and extract
# workstream identifiers (WS1, WS2, etc.) that map to issue titles
complete_patterns=""
in_progress_patterns=""

# Extract COMPLETE markers — skip section headers (lines starting with #)
while IFS= read -r line; do
  if [[ "$line" =~ (WS[0-9]+) ]]; then
    [[ -n "$complete_patterns" ]] && complete_patterns+="|"
    complete_patterns+="${BASH_REMATCH[1]}"
  fi
done < <(grep -i "COMPLETE" "$SPRINT_FILE" | grep -v "^#" || true)

# Extract IN PROGRESS markers from non-header lines
while IFS= read -r line; do
  if [[ "$line" =~ (WS[0-9]+) ]]; then
    [[ -n "$in_progress_patterns" ]] && in_progress_patterns+="|"
    in_progress_patterns+="${BASH_REMATCH[1]}"
  fi
done < <(grep "IN PROGRESS" "$SPRINT_FILE" | grep -v "^#" || true)

# Also check section headers for sprint-level status
while IFS= read -r line; do
  if [[ "$line" =~ ^#.*Sprint\ ([0-9]+).*COMPLETE ]]; then
    [[ -n "$complete_patterns" ]] && complete_patterns+="|"
    complete_patterns+="Sprint ${BASH_REMATCH[1]}"
  fi
  if [[ "$line" =~ ^#.*Sprint\ ([0-9]+).*IN\ PROGRESS ]]; then
    [[ -n "$in_progress_patterns" ]] && in_progress_patterns+="|"
    in_progress_patterns+="Sprint ${BASH_REMATCH[1]}"
  fi
done < "$SPRINT_FILE"

# Deduplicate patterns (pipe-delimited → sort -u → rejoin)
complete_patterns=$(echo "$complete_patterns" | tr '|' '\n' | sort -u | tr '\n' '|' | sed 's/|$//')
in_progress_patterns=$(echo "$in_progress_patterns" | tr '|' '\n' | sort -u | tr '\n' '|' | sed 's/|$//')

echo "COMPLETE patterns: ${complete_patterns:-none}"
echo "IN PROGRESS patterns: ${in_progress_patterns:-none}"
echo ""

# ─── Step 2: Fetch board state ────────────────────────────────────
echo "Fetching project board state..."
board_json=$(gh project item-list "$PROJECT_NUMBER" --owner "$OWNER" --format json 2>/dev/null)

if [[ -z "$board_json" ]]; then
  echo "ERROR: Could not fetch board JSON." >&2
  exit 1
fi

# Save to temp file (avoids pipe/heredoc unicode issues with em dashes)
tmpfile=$(mktemp)
echo "$board_json" > "$tmpfile"

item_count=$(python3 -c "
import json
with open('$tmpfile') as f:
    d = json.load(f)
print(len(d.get('items', [])))
" 2>/dev/null || echo "?")
echo "Found $item_count items on board."
echo ""

# ─── Step 3: Compare and reconcile ───────────────────────────────
echo "--- Reconciliation ---"
echo ""

export DRY_RUN_PY="$DRY_RUN"
export COMPLETE_PATTERNS="$complete_patterns"
export IN_PROGRESS_PATTERNS="$in_progress_patterns"
export REPO
export BOARD_FILE="$tmpfile"

python3 << 'PYEOF'
import json, subprocess, os

dry_run = os.environ.get("DRY_RUN_PY", "true") == "true"
repo = os.environ["REPO"]

with open(os.environ["BOARD_FILE"]) as f:
    board = json.load(f)

# Patterns are pipe-delimited (e.g., "WS1|WS2|WS3|Sprint 19")
complete_raw = os.environ.get("COMPLETE_PATTERNS", "")
in_progress_raw = os.environ.get("IN_PROGRESS_PATTERNS", "")
complete_patterns = [p.strip() for p in complete_raw.split("|") if p.strip()]
in_progress_patterns = [p.strip() for p in in_progress_raw.split("|") if p.strip()]

# Remove in_progress patterns that also appear in complete (COMPLETE wins)
in_progress_patterns = [p for p in in_progress_patterns if p not in complete_patterns]

changes = []

for item in board.get("items", []):
    content = item.get("content", {})
    number = content.get("number")
    title = content.get("title", "")
    status = item.get("status", "")
    item_id = item.get("id", "")

    if number is None:
        continue

    title_lower = title.lower()

    # Determine expected status from SPRINT.md patterns
    expected = None

    # Check COMPLETE patterns against issue title
    for pat in complete_patterns:
        if pat.lower() in title_lower:
            expected = "done"
            break

    # Check IN PROGRESS patterns (only if not already matched as complete)
    if expected is None:
        for pat in in_progress_patterns:
            if pat.lower() in title_lower:
                expected = "in_progress"
                break

    if expected is None:
        continue

    current = status.lower().replace(" ", "_")
    if current == expected:
        continue

    action_desc = f"#{number} ({title[:60]}): {status} -> {expected}"

    if expected == "done" and current != "done":
        changes.append(("done", number, item_id, action_desc))
    elif expected == "in_progress" and current in ("todo",):
        changes.append(("in_progress", number, item_id, action_desc))

if not changes:
    print("Board is in sync with SPRINT.md. No changes needed.")
else:
    for action, number, item_id, desc in changes:
        prefix = "[DRY RUN] " if dry_run else ""
        if action == "done":
            print(f"\033[0;32m[CLOSE+DONE]\033[0m {prefix}{desc}")
            if not dry_run:
                subprocess.run(
                    ["gh", "issue", "close", str(number), "--repo", repo,
                     "--comment", "Closed by sync-board-from-sprint.sh (matched COMPLETE in SPRINT.md)"],
                    capture_output=True)
                subprocess.run(
                    ["bash", "scripts/roadmap-sync.sh", "status", item_id, "done"],
                    capture_output=True)
        elif action == "in_progress":
            print(f"\033[0;33m[IN PROGRESS]\033[0m {prefix}{desc}")
            if not dry_run:
                subprocess.run(
                    ["bash", "scripts/roadmap-sync.sh", "status", item_id, "in_progress"],
                    capture_output=True)

    print(f"\n{'Would make' if dry_run else 'Made'} {len(changes)} change(s).")
    if dry_run:
        print("Run with --apply to execute.")
PYEOF

rm -f "$tmpfile"

echo ""
echo "=== Sync Complete ==="
if $DRY_RUN; then
  echo "This was a DRY RUN. Use --apply to execute changes."
fi
