#!/usr/bin/env bash
# audit-hardcoded.sh — Automated Layer 1: Find hardcoded values in macOS/iOS Views
#
# Usage: ./scripts/audit-hardcoded.sh [target]
#   target: "macos" (default), "ios", or "all"
#
# Scans View files for:
#   1. String literals that look like real data (timestamps, counts, statuses)
#   2. Numeric constants in Views that aren't spacing/sizing
#   3. Color(hex:) literals outside DesignSystem files
#   4. Empty button closures (Button { } or Button { // comment })
#   5. TODO/FIXME/STUB comments
#
# Output: Summary table + detailed findings
# See: docs/discoveries/ui-wiring-audit-methodology-2026-03-19.md

set -euo pipefail

TARGET="${1:-macos}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

case "$TARGET" in
    macos) SEARCH_DIR="$REPO_ROOT/HestiaApp/macOS/Views" ;;
    ios)   SEARCH_DIR="$REPO_ROOT/HestiaApp/Shared/Views" ;;
    all)   SEARCH_DIR="$REPO_ROOT/HestiaApp" ;;
    *)     echo "Usage: $0 [macos|ios|all]"; exit 1 ;;
esac

if [[ ! -d "$SEARCH_DIR" ]]; then
    echo "ERROR: Directory not found: $SEARCH_DIR"
    exit 1
fi

RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color
BOLD='\033[1m'

echo -e "${BOLD}══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Hestia UI Audit — Layer 1: Hardcoded Values Scan${NC}"
echo -e "${BOLD}  Target: ${CYAN}$TARGET${NC}  Search: ${CYAN}$SEARCH_DIR${NC}"
echo -e "${BOLD}══════════════════════════════════════════════════════════════${NC}"
echo ""

TOTAL_ISSUES=0

# ─── 1. Suspicious String Literals ────────────────────────────────────────────
echo -e "${BOLD}${RED}▸ Category 1: Suspicious String Literals${NC}"
echo "  Looking for hardcoded timestamps, counts, status messages..."
echo ""

# Common patterns: "X min ago", "X updates", "ago", hardcoded numbers in text
STRINGS_FOUND=$(grep -rn \
    -e '"[0-9]* min ago"' \
    -e '"[0-9]* hour' \
    -e '"[0-9]* update' \
    -e '"Started [0-9]' \
    -e '"Finished ' \
    -e '"All systems' \
    -e '"running smoothly' \
    -e '"is running' \
    -e '"No issues' \
    -e '"Everything' \
    --include="*.swift" \
    "$SEARCH_DIR" 2>/dev/null || true)

if [[ -n "$STRINGS_FOUND" ]]; then
    COUNT=$(echo "$STRINGS_FOUND" | wc -l | tr -d ' ')
    TOTAL_ISSUES=$((TOTAL_ISSUES + COUNT))
    echo -e "  ${RED}Found $COUNT suspicious string literals:${NC}"
    echo "$STRINGS_FOUND" | while IFS= read -r line; do
        FILE=$(echo "$line" | cut -d: -f1 | sed "s|$REPO_ROOT/||")
        LINE_NUM=$(echo "$line" | cut -d: -f2)
        CONTENT=$(echo "$line" | cut -d: -f3- | xargs)
        echo -e "  ${YELLOW}$FILE:$LINE_NUM${NC} → $CONTENT"
    done
else
    echo -e "  ${GREEN}✓ No suspicious string literals found${NC}"
fi
echo ""

# ─── 2. Hardcoded Progress/Metric Values ─────────────────────────────────────
echo -e "${BOLD}${RED}▸ Category 2: Hardcoded Numeric Values in Views${NC}"
echo "  Looking for hardcoded progress values, percentages, counts..."
echo ""

NUMS_FOUND=$(grep -rn \
    -e 'value: 0\.[0-9][0-9]' \
    -e 'value: [0-9]\.[0-9]' \
    -e 'label: "[0-9]*\.*[0-9]*%"' \
    -e 'width:.*\* 0\.[0-9]' \
    --include="*.swift" \
    "$SEARCH_DIR" 2>/dev/null \
    | grep -iv 'opacity\|cornerRadius\|spacing\|padding\|font\|animation\|lineWidth\|frame.*width.*[0-9]$' \
    || true)

if [[ -n "$NUMS_FOUND" ]]; then
    COUNT=$(echo "$NUMS_FOUND" | wc -l | tr -d ' ')
    TOTAL_ISSUES=$((TOTAL_ISSUES + COUNT))
    echo -e "  ${RED}Found $COUNT suspicious numeric values:${NC}"
    echo "$NUMS_FOUND" | while IFS= read -r line; do
        FILE=$(echo "$line" | cut -d: -f1 | sed "s|$REPO_ROOT/||")
        LINE_NUM=$(echo "$line" | cut -d: -f2)
        CONTENT=$(echo "$line" | cut -d: -f3- | xargs)
        echo -e "  ${YELLOW}$FILE:$LINE_NUM${NC} → $CONTENT"
    done
else
    echo -e "  ${GREEN}✓ No suspicious numeric values found${NC}"
fi
echo ""

# ─── 3. Color Literals Outside DesignSystem ───────────────────────────────────
echo -e "${BOLD}${RED}▸ Category 3: Color Literals (should be design tokens)${NC}"
echo "  Looking for Color(hex:) outside DesignSystem files..."
echo ""

COLORS_FOUND=$(grep -rn \
    'Color(hex:' \
    --include="*.swift" \
    "$SEARCH_DIR" 2>/dev/null \
    | grep -v 'DesignSystem\|MacColors\|HestiaColors\|ColorTokens\|Preview' \
    || true)

if [[ -n "$COLORS_FOUND" ]]; then
    COUNT=$(echo "$COLORS_FOUND" | wc -l | tr -d ' ')
    TOTAL_ISSUES=$((TOTAL_ISSUES + COUNT))
    echo -e "  ${RED}Found $COUNT color literals outside DesignSystem:${NC}"
    echo "$COLORS_FOUND" | while IFS= read -r line; do
        FILE=$(echo "$line" | cut -d: -f1 | sed "s|$REPO_ROOT/||")
        LINE_NUM=$(echo "$line" | cut -d: -f2)
        CONTENT=$(echo "$line" | cut -d: -f3- | xargs)
        echo -e "  ${YELLOW}$FILE:$LINE_NUM${NC} → $CONTENT"
    done
else
    echo -e "  ${GREEN}✓ No color literals outside DesignSystem${NC}"
fi
echo ""

# ─── 4. Empty Button Closures ─────────────────────────────────────────────────
echo -e "${BOLD}${RED}▸ Category 4: Empty/Stub Button Closures${NC}"
echo "  Looking for Button { } and Button { // comment } patterns..."
echo ""

BUTTONS_FOUND=$(grep -rn \
    -e 'Button {}' \
    -e 'Button { }' \
    -e 'Button {$' \
    --include="*.swift" \
    -A1 "$SEARCH_DIR" 2>/dev/null \
    | grep -E '(Button \{\}|Button \{ \}|// TODO|// .*action|^[^:]*-[[:space:]]*\}[[:space:]]*label)' \
    || true)

# Simpler approach: find Button with empty or comment-only body
BUTTONS_EMPTY=$(grep -rn 'Button {} label' --include="*.swift" "$SEARCH_DIR" 2>/dev/null || true)
BUTTONS_COMMENT=$(grep -rn '// TODO.*action\|// .*Order action\|// View Reports\|// TODO: Open' --include="*.swift" "$SEARCH_DIR" 2>/dev/null || true)

COMBINED_BUTTONS=$(printf "%s\n%s" "$BUTTONS_EMPTY" "$BUTTONS_COMMENT" | grep -v '^$' | sort -u || true)

if [[ -n "$COMBINED_BUTTONS" ]]; then
    COUNT=$(echo "$COMBINED_BUTTONS" | wc -l | tr -d ' ')
    TOTAL_ISSUES=$((TOTAL_ISSUES + COUNT))
    echo -e "  ${RED}Found $COUNT empty/stub button closures:${NC}"
    echo "$COMBINED_BUTTONS" | while IFS= read -r line; do
        FILE=$(echo "$line" | cut -d: -f1 | sed "s|$REPO_ROOT/||")
        LINE_NUM=$(echo "$line" | cut -d: -f2)
        CONTENT=$(echo "$line" | cut -d: -f3- | xargs)
        echo -e "  ${YELLOW}$FILE:$LINE_NUM${NC} → $CONTENT"
    done
else
    echo -e "  ${GREEN}✓ No empty button closures found${NC}"
fi
echo ""

# ─── 5. TODO/FIXME/STUB Comments ─────────────────────────────────────────────
echo -e "${BOLD}${YELLOW}▸ Category 5: TODO/FIXME/STUB Comments${NC}"
echo "  Looking for unresolved work markers..."
echo ""

TODOS_FOUND=$(grep -rn \
    -e '// TODO' \
    -e '// FIXME' \
    -e '// STUB' \
    -e '// HACK' \
    -e '// PLACEHOLDER' \
    --include="*.swift" \
    "$SEARCH_DIR" 2>/dev/null || true)

if [[ -n "$TODOS_FOUND" ]]; then
    COUNT=$(echo "$TODOS_FOUND" | wc -l | tr -d ' ')
    echo -e "  ${YELLOW}Found $COUNT TODO/FIXME markers:${NC}"
    echo "$TODOS_FOUND" | while IFS= read -r line; do
        FILE=$(echo "$line" | cut -d: -f1 | sed "s|$REPO_ROOT/||")
        LINE_NUM=$(echo "$line" | cut -d: -f2)
        CONTENT=$(echo "$line" | cut -d: -f3- | xargs)
        echo -e "  ${CYAN}$FILE:$LINE_NUM${NC} → $CONTENT"
    done
else
    echo -e "  ${GREEN}✓ No TODO/FIXME markers found${NC}"
fi
echo ""

# ─── Summary ──────────────────────────────────────────────────────────────────
echo -e "${BOLD}══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Summary: ${RED}$TOTAL_ISSUES issues${NC} found (categories 1-4)"
if [[ -n "$TODOS_FOUND" ]]; then
    TODO_COUNT=$(echo "$TODOS_FOUND" | wc -l | tr -d ' ')
    echo -e "  Plus ${YELLOW}$TODO_COUNT TODO/FIXME${NC} markers (category 5)"
fi
echo -e "${BOLD}══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Run as part of Sprint reviews or after any UI sprint."
echo "See: docs/discoveries/ui-wiring-audit-methodology-2026-03-19.md"
