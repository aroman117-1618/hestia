#!/usr/bin/env bash
# sentinel-baseline.sh — Refresh the Sentinel .pth file baseline.
#
# Usage: scripts/sentinel-baseline.sh [venv-path]
#
# If venv-path is omitted, defaults to .venv in the repo root.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PATH="${1:-"$REPO_ROOT/.venv"}"

# Locate site-packages inside the venv
SITE_PACKAGES="$(find "$VENV_PATH/lib" -maxdepth 2 -type d -name "site-packages" 2>/dev/null | head -1)"

if [[ -z "$SITE_PACKAGES" ]]; then
    echo "ERROR: Could not find site-packages under $VENV_PATH" >&2
    exit 1
fi

BASELINE_PATH="$REPO_ROOT/data/sentinel-pth-baseline.json"

echo "Refreshing Sentinel .pth baseline..."
echo "  site-packages : $SITE_PACKAGES"
echo "  baseline file : $BASELINE_PATH"

PYTHONPATH="$REPO_ROOT" /usr/bin/python3 - <<PYEOF
from hestia.sentinel.baseline import BaselineManager
mgr = BaselineManager("$BASELINE_PATH")
mgr.create_baseline("$SITE_PACKAGES")
print("Baseline written to $BASELINE_PATH")
PYEOF
