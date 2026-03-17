#!/bin/bash
# count-check.sh
# Verifies that CLAUDE.md counts match actual codebase counts.
# Report-only — exits non-zero if drift is detected.
#
# Usage:   ./scripts/count-check.sh
#
# Checks:
#   1. Test count (pytest --collect-only)
#   2. Test file count (ls tests/test_*.py)
#   3. Route module count (ls hestia/api/routes/*.py)
#
# Expected CLAUDE.md format for test count line:
#   "NNNN tests (NNNN passing, N skipped), NN test files."
# If this format changes, update the grep patterns below.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLAUDE_MD="$PROJECT_ROOT/CLAUDE.md"

# Use venv python (same pattern as auto-test.sh)
if [ -f "$PROJECT_ROOT/.venv/bin/python" ]; then
    PYTHON="$PROJECT_ROOT/.venv/bin/python"
else
    PYTHON="python3"
fi

# Kill a process after N seconds (same pattern as auto-test.sh / pre-push.sh)
run_with_timeout() {
    local secs=$1; shift
    "$@" &
    local pid=$!
    ( sleep "$secs" && kill "$pid" 2>/dev/null ) &
    local watchdog=$!
    wait "$pid" 2>/dev/null
    local exit_code=$?
    kill "$watchdog" 2>/dev/null || true
    wait "$watchdog" 2>/dev/null || true
    return $exit_code
}

DRIFT=0

echo "[COUNT-CHECK] Verifying codebase counts against CLAUDE.md..."
echo ""

# --- 1. Test count ---
COLLECT_OUTPUT=$(run_with_timeout 30 "$PYTHON" -m pytest "$PROJECT_ROOT/tests/" --collect-only -q 2>&1 | tail -3) || true
ACTUAL_TESTS=$(echo "$COLLECT_OUTPUT" | grep -oE '^[0-9]+ tests? collected' | grep -oE '^[0-9]+' || echo "0")

if [ "$ACTUAL_TESTS" = "0" ]; then
    echo "[COUNT-CHECK] WARNING: Could not collect test count from pytest"
    DRIFT=1
else
    # Extract declared test count from CLAUDE.md (first occurrence of "NNNN tests (")
    DECLARED_TESTS=$(grep -oE '^[0-9]+ tests \(' "$CLAUDE_MD" | head -1 | grep -oE '^[0-9]+' || echo "")
    if [ -z "$DECLARED_TESTS" ]; then
        echo "[COUNT-CHECK] WARNING: Could not find test count pattern in CLAUDE.md"
        DRIFT=1
    elif [ "$ACTUAL_TESTS" != "$DECLARED_TESTS" ]; then
        echo "[COUNT-CHECK] DRIFT: Test count — CLAUDE.md says $DECLARED_TESTS, actual is $ACTUAL_TESTS"
        DRIFT=1
    else
        echo "[COUNT-CHECK] OK: Test count ($ACTUAL_TESTS)"
    fi
fi

# --- 2. Test file count ---
ACTUAL_TEST_FILES=$(ls "$PROJECT_ROOT"/tests/test_*.py 2>/dev/null | wc -l | tr -d ' ')

# Extract from "NN test files" pattern
DECLARED_TEST_FILES=$(grep -oE '[0-9]+ test files' "$CLAUDE_MD" | head -1 | grep -oE '^[0-9]+' || echo "")
if [ -z "$DECLARED_TEST_FILES" ]; then
    echo "[COUNT-CHECK] WARNING: Could not find test file count pattern in CLAUDE.md"
    DRIFT=1
elif [ "$ACTUAL_TEST_FILES" != "$DECLARED_TEST_FILES" ]; then
    echo "[COUNT-CHECK] DRIFT: Test file count — CLAUDE.md says $DECLARED_TEST_FILES, actual is $ACTUAL_TEST_FILES"
    DRIFT=1
else
    echo "[COUNT-CHECK] OK: Test file count ($ACTUAL_TEST_FILES)"
fi

# --- 3. Route module count ---
ACTUAL_ROUTE_MODULES=$(ls "$PROJECT_ROOT"/hestia/api/routes/*.py 2>/dev/null | grep -v __init__ | wc -l | tr -d ' ')

# Extract from "NN route modules" pattern
DECLARED_ROUTE_MODULES=$(grep -oE '[0-9]+ route modules' "$CLAUDE_MD" | head -1 | grep -oE '^[0-9]+' || echo "")
if [ -z "$DECLARED_ROUTE_MODULES" ]; then
    echo "[COUNT-CHECK] WARNING: Could not find route module count pattern in CLAUDE.md"
    DRIFT=1
elif [ "$ACTUAL_ROUTE_MODULES" != "$DECLARED_ROUTE_MODULES" ]; then
    echo "[COUNT-CHECK] DRIFT: Route module count — CLAUDE.md says $DECLARED_ROUTE_MODULES, actual is $ACTUAL_ROUTE_MODULES"
    DRIFT=1
else
    echo "[COUNT-CHECK] OK: Route module count ($ACTUAL_ROUTE_MODULES)"
fi

# --- Summary ---
echo ""
if [ $DRIFT -eq 0 ]; then
    echo "[COUNT-CHECK] All counts match. No drift detected."
else
    echo "[COUNT-CHECK] DRIFT DETECTED — update CLAUDE.md before committing."
    echo "[COUNT-CHECK] Also check: agent definitions (.claude/agents/*.md) and MEMORY.md topic files."
fi

exit $DRIFT
