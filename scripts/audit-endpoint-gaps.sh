#!/usr/bin/env bash
# audit-endpoint-gaps.sh — Automated Layer 4: Backend endpoints with no client caller
#
# Usage: ./scripts/audit-endpoint-gaps.sh [platform]
#   platform: "macos" (default), "ios", or "all"
#
# Cross-references backend route definitions against Swift APIClient calls
# to find endpoints that are built but never used by the client.
#
# Output: List of uncalled endpoints grouped by module
# See: docs/discoveries/ui-wiring-audit-methodology-2026-03-19.md

set -euo pipefail

PLATFORM="${1:-macos}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROUTES_DIR="$REPO_ROOT/hestia/api/routes"
APP_DIR="$REPO_ROOT/HestiaApp"

RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
NC='\033[0m'
BOLD='\033[1m'

echo -e "${BOLD}══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Hestia UI Audit — Layer 4: Endpoint Gap Analysis${NC}"
echo -e "${BOLD}  Platform: ${CYAN}$PLATFORM${NC}"
echo -e "${BOLD}══════════════════════════════════════════════════════════════${NC}"
echo ""

# ─── 1. Extract all backend endpoints ─────────────────────────────────────────
echo -e "${BOLD}▸ Step 1: Scanning backend routes...${NC}"

TMPFILE_BACKEND=$(mktemp)
TMPFILE_CLIENT=$(mktemp)
trap "rm -f $TMPFILE_BACKEND $TMPFILE_CLIENT" EXIT

# Extract route paths from Python decorators
grep -rn '@router\.\(get\|post\|put\|delete\|patch\)' "$ROUTES_DIR" --include="*.py" 2>/dev/null \
    | grep -v '#.*@router' \
    | sed 's/.*@router\.\(get\|post\|put\|delete\|patch\)(\s*"//' \
    | sed 's/".*//' \
    | sort -u > "$TMPFILE_BACKEND"

BACKEND_COUNT=$(wc -l < "$TMPFILE_BACKEND" | tr -d ' ')
echo -e "  Found ${CYAN}$BACKEND_COUNT${NC} backend endpoints"

# ─── 2. Extract all client API calls ──────────────────────────────────────────
echo -e "${BOLD}▸ Step 2: Scanning client API calls...${NC}"

# Extract endpoint paths from Swift APIClient calls
grep -rn 'APIClient\|\.get(\|\.post(\|\.put(\|\.delete(' "$APP_DIR" --include="*.swift" 2>/dev/null \
    | grep -v 'Test\|Preview\|Mock\|protocol\|///\|//' \
    | grep -o '"/v1/[^"]*"' \
    | sed 's/"//g' \
    | sort -u > "$TMPFILE_CLIENT"

CLIENT_COUNT=$(wc -l < "$TMPFILE_CLIENT" | tr -d ' ')
echo -e "  Found ${CYAN}$CLIENT_COUNT${NC} distinct client API calls"

# ─── 3. Cross-reference ───────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}▸ Step 3: Cross-referencing...${NC}"
echo ""

# Count endpoints per route module
echo -e "${BOLD}  Endpoints by module:${NC}"
for route_file in "$ROUTES_DIR"/*.py; do
    MODULE=$(basename "$route_file" .py)
    [[ "$MODULE" == "__init__" || "$MODULE" == "__pycache__" ]] && continue

    TOTAL=$(grep -c '@router\.\(get\|post\|put\|delete\|patch\)' "$route_file" 2>/dev/null || echo 0)

    # Get the prefix for this module
    PREFIX=$(grep -o 'prefix="/v1/[^"]*"' "$route_file" 2>/dev/null | head -1 | sed 's/prefix="//;s/"//' || echo "/v1/$MODULE")

    # Count how many of this module's endpoints are called by client
    CALLED=0
    if [[ -s "$TMPFILE_CLIENT" ]]; then
        CALLED=$(grep -c "${PREFIX}" "$TMPFILE_CLIENT" 2>/dev/null || echo 0)
    fi

    UNCALLED=$((TOTAL - CALLED))
    if [[ $UNCALLED -gt 0 && $TOTAL -gt 0 ]]; then
        COVERAGE_PCT=$(( (CALLED * 100) / TOTAL ))
        echo -e "  ${YELLOW}$MODULE${NC}: $CALLED/$TOTAL endpoints called (${COVERAGE_PCT}%) — ${RED}$UNCALLED uncalled${NC}"
    elif [[ $TOTAL -gt 0 ]]; then
        echo -e "  ${GREEN}$MODULE${NC}: $CALLED/$TOTAL endpoints called (100%) ✓"
    fi
done

echo ""

# ─── 4. List specific uncalled endpoints ──────────────────────────────────────
echo -e "${BOLD}▸ Step 4: Uncalled endpoints (backend exists, no client caller)${NC}"
echo ""

UNCALLED_TOTAL=0
for route_file in "$ROUTES_DIR"/*.py; do
    MODULE=$(basename "$route_file" .py)
    [[ "$MODULE" == "__init__" || "$MODULE" == "__pycache__" ]] && continue

    PREFIX=$(grep -o 'prefix="/v1/[^"]*"' "$route_file" 2>/dev/null | head -1 | sed 's/prefix="//;s/"//' || echo "/v1/$MODULE")

    # Extract individual endpoint paths with their HTTP methods
    grep -n '@router\.\(get\|post\|put\|delete\|patch\)' "$route_file" 2>/dev/null | while IFS= read -r line; do
        LINE_NUM=$(echo "$line" | cut -d: -f1)
        METHOD=$(echo "$line" | grep -o 'router\.\(get\|post\|put\|delete\|patch\)' | sed 's/router\.//' | tr '[:lower:]' '[:upper:]')
        PATH=$(echo "$line" | grep -o '"[^"]*"' | head -1 | sed 's/"//g')

        FULL_PATH="${PREFIX}${PATH}"
        FULL_PATH=$(echo "$FULL_PATH" | sed 's|//|/|g')

        # Check if this path (with parameter wildcards) is called by client
        # Normalize: replace {param} with a generic pattern for matching
        SEARCH_PATH=$(echo "$FULL_PATH" | sed 's/{[^}]*}/[^"]*/g')

        if ! grep -qE "$SEARCH_PATH" "$TMPFILE_CLIENT" 2>/dev/null; then
            echo -e "  ${RED}$METHOD${NC} ${YELLOW}$FULL_PATH${NC}  (${CYAN}$MODULE.py:$LINE_NUM${NC})"
            UNCALLED_TOTAL=$((UNCALLED_TOTAL + 1))
        fi
    done
done

echo ""

# ─── Summary ──────────────────────────────────────────────────────────────────
echo -e "${BOLD}══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Summary: ${CYAN}$BACKEND_COUNT${NC} backend endpoints, ${CYAN}$CLIENT_COUNT${NC} client calls"
echo -e "  Coverage: $((CLIENT_COUNT * 100 / (BACKEND_COUNT > 0 ? BACKEND_COUNT : 1)))%"
echo -e "${BOLD}══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Run after backend changes or before planning UI sprints."
echo "See: docs/discoveries/ui-wiring-audit-methodology-2026-03-19.md"
