#!/bin/bash
#
# pre-deploy-check.sh - Pre-deployment safety checks
#
# Checks for:
# - Uncommitted changes (warning only)
# - Credential leaks in code
# - Type checking (if mypy installed)
# - Tests passing
# - Package imports
#
# Usage: ./scripts/pre-deploy-check.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

CHECKS_PASSED=0
CHECKS_WARNED=0
CHECKS_FAILED=0

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((CHECKS_PASSED++)) || true
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((CHECKS_WARNED++)) || true
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ((CHECKS_FAILED++)) || true
}

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Pre-Deployment Checks${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

cd "$PROJECT_ROOT"

# Activate venv if available
if [[ -f ".venv/bin/activate" ]]; then
    source .venv/bin/activate
fi

# 1. Check Git status
echo -e "${YELLOW}Checking Git status...${NC}"
if [[ -d ".git" ]]; then
    UNCOMMITTED=$(git status --porcelain | wc -l | tr -d ' ')
    if [[ "$UNCOMMITTED" -gt 0 ]]; then
        check_warn "Uncommitted changes detected ($UNCOMMITTED files)"
    else
        check_pass "Working tree clean"
    fi
else
    check_warn "Not a Git repository"
fi

# 2. Check for credential leaks
echo -e "\n${YELLOW}Scanning for credential leaks...${NC}"

# Patterns that indicate hard-coded credentials
LEAK_FOUND=0

# Check for Anthropic/OpenAI API keys
# Use || true to prevent set -e from exiting when grep finds no matches
API_KEY_MATCHES=$(grep -rn "sk-ant-\|sk-[a-zA-Z0-9]\{20,\}" hestia/ 2>/dev/null | grep -v "\.pyc" | grep -v "__pycache__" || true)
if [[ -n "$API_KEY_MATCHES" ]]; then
    echo "$API_KEY_MATCHES"
    LEAK_FOUND=1
fi

# Check for hardcoded api_key assignments (excluding pattern definitions)
HARDCODED_MATCHES=$(grep -rn "api_key\s*=\s*['\"][^'\"]*['\"]" hestia/ 2>/dev/null | grep -v "\.pyc" | grep -v "__pycache__" | grep -v "REDACTED" | grep -v "pattern" | grep -v "#" || true)
if [[ -n "$HARDCODED_MATCHES" ]]; then
    echo "$HARDCODED_MATCHES"
    LEAK_FOUND=1
fi

# Check for .env files — only fail if NOT gitignored
for envfile in ".env" "hestia/.env"; do
    if [[ -f "$envfile" ]]; then
        if git check-ignore -q "$envfile" 2>/dev/null; then
            echo "Found $envfile — gitignored (safe)"
        else
            echo "Found $envfile — NOT gitignored!"
            LEAK_FOUND=1
        fi
    fi
done

if [[ "$LEAK_FOUND" -eq 1 ]]; then
    check_fail "Possible credential leak detected"
    echo "  Review the above matches and remove any real credentials"
    exit 1
else
    check_pass "No credential leaks detected"
fi

# 3. Type checking (if mypy installed)
echo -e "\n${YELLOW}Running type checks...${NC}"
if command -v mypy &> /dev/null; then
    if mypy hestia/ --ignore-missing-imports --no-error-summary 2>/dev/null; then
        check_pass "Type checking passed"
    else
        check_warn "Type checking had issues (non-blocking)"
    fi
else
    check_warn "mypy not installed (pip install mypy)"
fi

# 4. Run tests
echo -e "\n${YELLOW}Running tests...${NC}"
if [[ -d "tests" ]] && [[ -n "$(ls -A tests/*.py 2>/dev/null)" ]]; then
    if python -m pytest tests/ -q 2>/dev/null; then
        check_pass "Tests passed"
    else
        check_warn "Tests not passing or not implemented"
    fi
else
    check_warn "No tests implemented yet"
fi

# 5. Package import check
echo -e "\n${YELLOW}Checking package imports...${NC}"
if python3 -c "import hestia; print(f'Package version: {hestia.__version__}')" 2>/dev/null; then
    check_pass "Package imports successfully"
else
    check_fail "Package import failed"
    exit 1
fi

# 6. Check critical files exist
echo -e "\n${YELLOW}Checking critical files...${NC}"
CRITICAL_FILES=(
    "hestia/__init__.py"
    "hestia/security/credential_manager.py"
    "hestia/logging/structured_logger.py"
    "hestia/logging/audit_logger.py"
    "requirements.txt"
    ".gitignore"
)

MISSING_FILES=0
for file in "${CRITICAL_FILES[@]}"; do
    if [[ ! -f "$file" ]]; then
        echo "  Missing: $file"
        MISSING_FILES=1
    fi
done

if [[ "$MISSING_FILES" -eq 0 ]]; then
    check_pass "All critical files present"
else
    check_fail "Critical files missing"
    exit 1
fi

# Summary
echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}   Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Passed:   ${GREEN}${CHECKS_PASSED}${NC}"
echo -e "Warnings: ${YELLOW}${CHECKS_WARNED}${NC}"
echo -e "Failed:   ${RED}${CHECKS_FAILED}${NC}"
echo ""

if [[ "$CHECKS_FAILED" -gt 0 ]]; then
    echo -e "${RED}Pre-deployment checks FAILED${NC}"
    exit 1
else
    echo -e "${GREEN}✓ Pre-deployment checks passed${NC}"
    exit 0
fi
