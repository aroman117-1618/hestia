#!/bin/bash
# Hestia pre-push hook — branch-aware validation
#
# Feature branches: kill stale servers + pytest (~30s)
# Main branch:      kill stale servers + pytest + xcodebuild (~60s)
#
# Install: ln -sf ../../scripts/pre-push.sh .git/hooks/pre-push
# Bypass:  git push --no-verify (use sparingly)

set -euo pipefail
# Resolve symlink to find the real script location, then navigate to repo root
REAL_SCRIPT="$(readlink "$0" 2>/dev/null || echo "$0")"
if [[ "$REAL_SCRIPT" != /* ]]; then
    REAL_SCRIPT="$(cd "$(dirname "$0")" && cd "$(dirname "$REAL_SCRIPT")" && pwd)/$(basename "$REAL_SCRIPT")"
fi
cd "$(dirname "$REAL_SCRIPT")/.."

# Top-level timeout safety net (180s = 3 minutes)
if command -v timeout &>/dev/null; then
    TIMEOUT_CMD="timeout 180"
elif command -v gtimeout &>/dev/null; then
    TIMEOUT_CMD="gtimeout 180"
else
    TIMEOUT_CMD=""
fi

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

set +e
if [ -n "$TIMEOUT_CMD" ]; then
    $TIMEOUT_CMD python -m pytest tests/ --timeout=30 -q
else
    python -m pytest tests/ --timeout=30 -q
fi
PYTEST_EXIT=$?
set -e

if [ $PYTEST_EXIT -ne 0 ]; then
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
        # xcodebuild daemons can inherit fds and keep pipes open — use temp file
        set +e
        xcodebuild -project HestiaApp/HestiaApp.xcodeproj -scheme HestiaWorkspace -quiet >"$XCODE_LOG" 2>&1
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
