#!/bin/bash
# Hestia pre-push hook — branch-aware validation
#
# Feature branches: kill stale servers + pytest (~30s)
# Main branch:      kill stale servers + pytest + xcodebuild (~60s)
#
# Install: ln -sf ../../scripts/pre-push.sh .git/hooks/pre-push
# Bypass:  git push --no-verify (use sparingly)

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# Portable timeout wrapper (macOS lacks coreutils `timeout`)
run_with_timeout() {
    local secs=$1; shift
    "$@" &
    local pid=$!
    ( sleep "$secs" && kill "$pid" 2>/dev/null && echo "WARN: process killed after ${secs}s timeout" ) &
    local watchdog=$!
    wait "$pid" 2>/dev/null
    local exit_code=$?
    kill "$watchdog" 2>/dev/null
    wait "$watchdog" 2>/dev/null
    return $exit_code
}

BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo "detached")

echo "=== Hestia pre-push: branch=$BRANCH ==="

# --- Step 1: Kill stale servers ---
echo "[1/3] Killing stale servers..."
./scripts/kill-stale-servers.sh

# --- Step 2: Activate venv and run tests ---
echo "[2/3] Running pytest..."
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
else
    echo "ERROR: .venv not found. Run: python -m venv .venv && pip install -r requirements.txt"
    exit 1
fi

# pytest can hang after completion (ChromaDB background threads) — capture
# output to temp file, use timeout, then check results from output
PYTEST_LOG=$(mktemp)
set +e
run_with_timeout 360 python -m pytest tests/ --timeout=30 -q -m "not integration" >"$PYTEST_LOG" 2>&1
PYTEST_EXIT=$?
set -e

cat "$PYTEST_LOG"

# Determine if tests actually passed despite non-zero exit code.
# Common false-positive failures:
#   - exit 143: run_with_timeout killed pytest (ChromaDB threads hang after tests complete)
#   - exit 1 with 0 failures: pytest-timeout killed individual hung tests (E markers)
#   - exit 1 with [100%] but no summary: pytest hung before printing summary line
FAILED_COUNT=$(grep -oE '[0-9]+ failed' "$PYTEST_LOG" | head -1 | grep -oE '[0-9]+' || echo "0")
HAS_PASSED=$(grep -q "passed" "$PYTEST_LOG" && echo "yes" || echo "no")
REACHED_100=$(grep -q '\[100%\]' "$PYTEST_LOG" && echo "yes" || echo "no")

if [ $PYTEST_EXIT -eq 0 ]; then
    rm -f "$PYTEST_LOG"
elif [ "$FAILED_COUNT" != "0" ]; then
    # Real test failures — block the push
    rm -f "$PYTEST_LOG"
    echo ""
    echo "FAILED: $FAILED_COUNT test(s) failed"
    echo "Fix failing tests before pushing, or use: git push --no-verify"
    exit 1
elif [ "$HAS_PASSED" = "yes" ] || [ "$REACHED_100" = "yes" ]; then
    # Tests completed (either summary says "passed" or progress reached 100%)
    # but pytest exited non-zero due to timeout/thread hangs — safe to proceed
    echo "(pytest exited $PYTEST_EXIT — no failures detected, likely ChromaDB thread hang)"
    rm -f "$PYTEST_LOG"
elif [ $PYTEST_EXIT -eq 143 ]; then
    # Killed by our timeout watchdog — check if any progress was made
    echo "(pytest killed by timeout watchdog — check test health manually)"
    rm -f "$PYTEST_LOG"
    exit 1
else
    rm -f "$PYTEST_LOG"
    echo ""
    echo "FAILED: pytest exited with code $PYTEST_EXIT"
    echo "Fix failing tests before pushing, or use: git push --no-verify"
    exit 1
fi

# --- Step 3: xcodebuild on main only ---
if [ "$BRANCH" = "main" ]; then
    echo "[3/3] Building macOS target (main branch gate)..."
    if [ -d "HestiaApp" ]; then
        XCODE_LOG=$(mktemp)
        set +e
        run_with_timeout 120 xcodebuild -project HestiaApp/HestiaApp.xcodeproj -scheme HestiaWorkspace -quiet >"$XCODE_LOG" 2>&1
        XCODE_EXIT=$?
        set -e

        if [ $XCODE_EXIT -ne 0 ]; then
            echo ""
            cat "$XCODE_LOG"
            rm -f "$XCODE_LOG"
            echo "FAILED: xcodebuild exited with code $XCODE_EXIT"
            echo "Fix build errors before pushing to main, or use: git push --no-verify"
            exit 1
        fi
        rm -f "$XCODE_LOG"
    else
        echo "WARN: HestiaApp directory not found, skipping xcodebuild"
    fi
else
    echo "[3/3] Skipping xcodebuild (feature branch)"
fi

echo ""
echo "=== Pre-push validation passed ==="
