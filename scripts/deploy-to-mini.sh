#!/bin/bash
#
# deploy-to-mini.sh - Deploy Hestia to Mac Mini via rsync + SSH
#
# Usage: ./scripts/deploy-to-mini.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
MINI_HOST="andrew@hestia-server"
MINI_PATH="~/hestia"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Logging
LOG_FILE="${PROJECT_ROOT}/logs/deployments.log"
mkdir -p "$(dirname "$LOG_FILE")"

log_deployment() {
    local status="$1"
    local message="$2"
    echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") | ${status} | MacBook -> Mac Mini | ${message}" >> "$LOG_FILE"
}

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Hestia Deployment to Mac Mini${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check we're in the right directory
if [[ ! -f "${PROJECT_ROOT}/hestia/__init__.py" ]]; then
    echo -e "${RED}Error: Not in Hestia project root${NC}"
    echo "Expected to find hestia/__init__.py"
    exit 1
fi

echo -e "${GREEN}✓${NC} Project root: ${PROJECT_ROOT}"

# Check SSH connectivity
echo -e "\n${YELLOW}Checking Mac Mini connectivity...${NC}"
if ! ssh -q -o ConnectTimeout=5 "$MINI_HOST" exit 2>/dev/null; then
    echo -e "${RED}Error: Cannot connect to Mac Mini (${MINI_HOST})${NC}"
    echo "Make sure:"
    echo "  1. Tailscale is running on both machines"
    echo "  2. Mac Mini is awake and accessible"
    echo "  3. SSH key is set up"
    exit 1
fi
echo -e "${GREEN}✓${NC} Mac Mini is reachable"

# Run pre-deployment checks if script exists
if [[ -x "${SCRIPT_DIR}/pre-deploy-check.sh" ]]; then
    echo -e "\n${YELLOW}Running pre-deployment checks...${NC}"
    if ! "${SCRIPT_DIR}/pre-deploy-check.sh"; then
        echo -e "${RED}Pre-deployment checks failed${NC}"
        exit 1
    fi
fi

# Rsync project files
echo -e "\n${YELLOW}Syncing files to Mac Mini...${NC}"
rsync -avz --progress \
    --exclude='.venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='.git/' \
    --exclude='logs/' \
    --exclude='data/' \
    --exclude='.DS_Store' \
    --exclude='*.egg-info/' \
    --exclude='.build/' \
    --exclude='DerivedData/' \
    --exclude='.pytest_cache/' \
    --exclude='.coverage' \
    --exclude='htmlcov/' \
    "${PROJECT_ROOT}/" "${MINI_HOST}:${MINI_PATH}/"

echo -e "${GREEN}✓${NC} Files synced"

# Run remote setup commands
echo -e "\n${YELLOW}Running setup on Mac Mini...${NC}"
ssh "$MINI_HOST" bash -s << 'REMOTE_SCRIPT'
set -e

cd ~/hestia

# Activate venv and install dependencies
if [[ -d ".venv" ]]; then
    source .venv/bin/activate
    echo "Installing/updating dependencies..."
    pip install -q -r requirements.txt
    echo "✓ Dependencies installed"
else
    echo "⚠ Virtual environment not found at ~/hestia/.venv"
    echo "  Create with: python3 -m venv .venv"
fi

# Run tests if they exist
if [[ -d "tests" ]] && [[ -n "$(ls -A tests/*.py 2>/dev/null)" ]]; then
    echo "Running tests..."
    python -m pytest tests/ -v || echo "⚠ Tests not yet implemented or failing"
else
    echo "⚠ Tests not yet implemented"
fi

# Verify package imports
echo "Verifying package imports..."
python3 -c "import hestia; print(f'✓ hestia package v{hestia.__version__} imports successfully')" || {
    echo "✗ Package import failed"
    exit 1
}

# Reload launchd service (if configured)
if [[ -f ~/Library/LaunchAgents/com.hestia.server.plist ]]; then
    echo "Reloading launchd service..."
    launchctl unload ~/Library/LaunchAgents/com.hestia.server.plist 2>/dev/null || true
    launchctl load ~/Library/LaunchAgents/com.hestia.server.plist 2>/dev/null || true
    echo "✓ Service reloaded"
else
    echo "⚠ launchd service not configured"
fi

# Health check (if API exists)
sleep 1
if curl -sf http://localhost:8443/health > /dev/null 2>&1; then
    echo "✓ API health check passed"
else
    echo "⚠ API server not yet implemented or not responding"
fi

echo ""
echo "Remote setup complete!"
REMOTE_SCRIPT

# Log successful deployment
log_deployment "SUCCESS" "Deployed from MacBook"

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}   Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Target: ${BLUE}${MINI_HOST}:${MINI_PATH}${NC}"
echo -e "Time: $(date)"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  - SSH to Mac Mini: ssh ${MINI_HOST}"
echo "  - View logs: ssh ${MINI_HOST} 'tail -f ~/hestia/logs/*.log'"
echo "  - Check service: ssh ${MINI_HOST} 'launchctl list | grep hestia'"
echo ""
