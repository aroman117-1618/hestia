#!/bin/bash
# Session startup hook for Claude Code
# Replaces kill-stale-servers.sh with additional context injection
# Must complete in <10 seconds
#
# Dual-mode: hook reads stdin JSON, CLI takes no args

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# --- 1. Kill stale servers on port 8443 ---
PIDS=$(lsof -ti :8443 2>/dev/null || true)
if [ -n "$PIDS" ]; then
    echo "$PIDS" | xargs kill -9 2>/dev/null || true
    echo "Killed stale server processes on port 8443: $PIDS"
else
    echo "No stale server processes found on port 8443"
fi

# --- 2. Quick health probe ---
HTTP_CODE=$(curl -sk --max-time 2 -o /dev/null -w '%{http_code}' https://localhost:8443/v1/ping 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo "Server: running (healthy on :8443)"
else
    echo "Server: not running (use /preflight to start)"
fi

# --- 3. Git status summary ---
echo ""
echo "--- Git Status ---"
cd "$PROJECT_ROOT"
git status --short 2>/dev/null | head -10
DIRTY_COUNT=$(git status --short 2>/dev/null | wc -l | tr -d ' ')
if [ "$DIRTY_COUNT" -gt 10 ]; then
    echo "... and $((DIRTY_COUNT - 10)) more files"
fi

# --- 4. Recent commits ---
echo ""
echo "--- Recent Commits ---"
git log --oneline -3 2>/dev/null || echo "No commits found"
