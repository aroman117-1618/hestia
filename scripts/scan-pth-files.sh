#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

VENV_PATH="${1:-$REPO_ROOT/.venv}"
ALLOWLIST="$REPO_ROOT/config/known-pth-files.txt"

if [[ ! -f "$ALLOWLIST" ]]; then
    echo -e "${RED}ERROR: Allowlist not found at $ALLOWLIST${NC}" >&2
    exit 1
fi

if [[ ! -d "$VENV_PATH" ]]; then
    echo -e "${RED}ERROR: Venv not found at $VENV_PATH${NC}" >&2
    exit 1
fi

UNKNOWN_FOUND=0

while IFS= read -r -d '' pth_file; do
    basename_pth="$(basename "$pth_file")"
    if ! grep -qxF "$basename_pth" "$ALLOWLIST"; then
        echo -e "${RED}WARNING: Unknown .pth file detected: $pth_file${NC}"
        echo "  First 5 lines of contents:"
        head -n 5 "$pth_file" | sed 's/^/    /'
        UNKNOWN_FOUND=1
    fi
done < <(find "$VENV_PATH" -type d -name "site-packages" -exec find {} -maxdepth 1 -name "*.pth" -print0 \;)

if [[ "$UNKNOWN_FOUND" -eq 1 ]]; then
    echo -e "${RED}DEPLOY ABORTED: Unknown .pth files found in venv.${NC}" >&2
    exit 2
fi

echo -e "${GREEN}All .pth files are known-good. Clean.${NC}"
exit 0
