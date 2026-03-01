#!/bin/bash
# PreCompact hook — outputs context to stdout for re-injection after compaction
# Must complete in <5 seconds

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# --- 1. Preserve session handoff ---
if [ -f "$PROJECT_ROOT/SESSION_HANDOFF.md" ]; then
    echo "=== SESSION HANDOFF (preserved for post-compaction continuity) ==="
    cat "$PROJECT_ROOT/SESSION_HANDOFF.md"
    echo ""
fi

# --- 2. Current sprint context ---
if [ -f "$PROJECT_ROOT/SPRINT.md" ]; then
    echo "=== SPRINT STATUS (first 30 lines) ==="
    head -30 "$PROJECT_ROOT/SPRINT.md"
    echo ""
fi

echo "Context preserved for post-compaction continuity"
