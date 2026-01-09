#!/bin/bash
#
# initial-push.sh - First-time Git push to Mac Mini + deployment
#
# This script:
# 1. Verifies we're in a Git repo
# 2. Shows what will be committed
# 3. Commits current state
# 4. Pushes to Mac Mini remote
# 5. Runs deployment
#
# Usage: ./scripts/initial-push.sh
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
MINI_HOST="andrew@hestia-server"
MINI_PATH="~/hestia"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Hestia Initial Push to Mac Mini${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

cd "$PROJECT_ROOT"

# Verify we're in a Git repo
if [[ ! -d ".git" ]]; then
    echo -e "${RED}Error: Not a Git repository${NC}"
    echo "Initialize with: git init"
    exit 1
fi
echo -e "${GREEN}✓${NC} Git repository found"

# Show current status
echo -e "\n${YELLOW}Current Git status:${NC}"
echo "---"
git status --short
echo "---"

# Count files to be committed
UNTRACKED=$(git status --porcelain | grep -c "^??" || true)
MODIFIED=$(git status --porcelain | grep -c "^ M\|^M " || true)
STAGED=$(git status --porcelain | grep -c "^A \|^M " || true)

echo ""
echo "Files to commit:"
echo "  - Untracked: $UNTRACKED"
echo "  - Modified:  $MODIFIED"
echo "  - Staged:    $STAGED"
echo ""

# Confirm with user
echo -e "${YELLOW}This will:${NC}"
echo "  1. Stage all files (respecting .gitignore)"
echo "  2. Commit with message 'Initial Hestia deployment from MacBook'"
echo "  3. Add Mac Mini as Git remote 'mini'"
echo "  4. Force push to Mac Mini (overwrites any existing repo)"
echo "  5. Run deployment script"
echo ""
read -p "Continue? [y/N] " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# Run pre-deployment checks if available
if [[ -x "${SCRIPT_DIR}/pre-deploy-check.sh" ]]; then
    echo -e "\n${YELLOW}Running pre-deployment checks...${NC}"
    if ! "${SCRIPT_DIR}/pre-deploy-check.sh"; then
        echo -e "${RED}Pre-deployment checks failed. Fix issues before pushing.${NC}"
        exit 1
    fi
fi

# Stage all files
echo -e "\n${YELLOW}Staging files...${NC}"
git add -A
echo -e "${GREEN}✓${NC} Files staged"

# Commit
echo -e "\n${YELLOW}Creating commit...${NC}"
git commit -m "$(cat <<'EOF'
Initial Hestia deployment from MacBook

Phase 0: Environment Setup - COMPLETE
Phase 0.5: Security Foundation - COMPLETE
Phase 1: Logging Infrastructure - COMPLETE

Implemented:
- CredentialManager with three-tier partitioning (Keychain + Fernet)
- HestiaLogger with JSON output and credential sanitization
- AuditLogger with 7-year retention and tamper detection
- hestia-keychain-cli Swift tool for Secure Enclave

Next: Phase 2 - Inference Layer

🤖 Generated with Claude Code
EOF
)" || {
    echo -e "${YELLOW}⚠ Nothing to commit (working tree clean)${NC}"
}

# Add Mac Mini as remote
echo -e "\n${YELLOW}Setting up Mac Mini remote...${NC}"
if git remote | grep -q "^mini$"; then
    echo "Remote 'mini' already exists, updating URL..."
    git remote set-url mini "${MINI_HOST}:${MINI_PATH}"
else
    git remote add mini "${MINI_HOST}:${MINI_PATH}"
fi
echo -e "${GREEN}✓${NC} Remote 'mini' configured: ${MINI_HOST}:${MINI_PATH}"

# Ensure main branch exists
CURRENT_BRANCH=$(git branch --show-current)
if [[ -z "$CURRENT_BRANCH" ]]; then
    echo -e "\n${YELLOW}Creating main branch...${NC}"
    git checkout -b main
    CURRENT_BRANCH="main"
fi

# Push to Mac Mini (force for initial push)
echo -e "\n${YELLOW}Pushing to Mac Mini...${NC}"
git push mini "$CURRENT_BRANCH" --force
echo -e "${GREEN}✓${NC} Pushed to Mac Mini"

# Run deployment
echo -e "\n${YELLOW}Running deployment...${NC}"
if [[ -x "${SCRIPT_DIR}/deploy-to-mini.sh" ]]; then
    "${SCRIPT_DIR}/deploy-to-mini.sh"
else
    echo -e "${YELLOW}⚠ deploy-to-mini.sh not found or not executable${NC}"
fi

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}   Initial Push Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Git remote 'mini' is now configured."
echo ""
echo -e "${YELLOW}Future deployments:${NC}"
echo "  - Quick deploy: ./scripts/deploy-to-mini.sh"
echo "  - Git push:     git push mini main"
echo ""
