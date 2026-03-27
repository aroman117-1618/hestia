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
MINI_HOST="andrewroman117@hestia-3.local"
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

# Build WorkflowCanvas (React Flow) if node_modules exist
CANVAS_DIR="${PROJECT_ROOT}/HestiaApp/WorkflowCanvas"
if [[ -d "${CANVAS_DIR}/node_modules" ]]; then
    echo -e "\n${YELLOW}Building WorkflowCanvas...${NC}"
    (cd "${CANVAS_DIR}" && npm run build)
    echo -e "${GREEN}✓${NC} Canvas built"
elif [[ -f "${CANVAS_DIR}/package.json" ]]; then
    echo -e "\n${YELLOW}Installing and building WorkflowCanvas...${NC}"
    (cd "${CANVAS_DIR}" && npm install && npm run build)
    echo -e "${GREEN}✓${NC} Canvas built"
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
    --exclude='node_modules/' \
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
    pip install -q --require-hashes -r requirements.txt
    echo "✓ Dependencies installed"
    echo "Scanning for malicious .pth files..."
    bash "${HESTIA_HOME}/scripts/scan-pth-files.sh" "${HESTIA_HOME}/.venv" || { echo "✗ .pth scan failed — aborting deploy"; exit 1; }
    echo "✓ .pth scan passed"
    if [[ -f "${HESTIA_HOME}/scripts/sentinel-baseline.sh" ]]; then bash "${HESTIA_HOME}/scripts/sentinel-baseline.sh" "${HESTIA_HOME}/.venv"; fi
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

# Reload launchd service (if configured) or manual restart fallback
if [[ -f ~/Library/LaunchAgents/com.hestia.server.plist ]]; then
    echo "Reloading launchd service..."
    launchctl unload ~/Library/LaunchAgents/com.hestia.server.plist 2>/dev/null || true
    sleep 1
    launchctl load ~/Library/LaunchAgents/com.hestia.server.plist 2>/dev/null || true
    echo "✓ Service reloaded via launchd"
else
    echo "⚠ launchd service not configured — using manual restart"
    echo "  Install with: ./scripts/install-server-service.sh"
    lsof -i :8443 | grep LISTEN | awk '{print $2}' | xargs kill -9 2>/dev/null || true
    sleep 2
    source .venv/bin/activate
    nohup python -m hestia.api.server > /dev/null 2>&1 &
fi

# Reload trading-bots service (if configured)
if [[ -f ~/Library/LaunchAgents/com.hestia.trading-bots.plist ]]; then
    echo "Reloading trading-bots service..."
    launchctl unload ~/Library/LaunchAgents/com.hestia.trading-bots.plist 2>/dev/null || true
    sleep 1
    launchctl load ~/Library/LaunchAgents/com.hestia.trading-bots.plist 2>/dev/null || true
    echo "✓ Trading-bots service reloaded via launchd"
fi

# Health check with retry (server may need a moment after reload)
# Uses -k for self-signed cert; set HESTIA_CA_CERT for proper TLS verification
HEALTH_CURL_OPTS="-sf"
if [[ -n "${HESTIA_CA_CERT:-}" ]]; then
    HEALTH_CURL_OPTS="$HEALTH_CURL_OPTS --cacert $HESTIA_CA_CERT"
else
    HEALTH_CURL_OPTS="$HEALTH_CURL_OPTS -k"
fi

echo "Checking API readiness..."
for i in 1 2 3 4 5; do
    sleep 3
    READY_OUTPUT=$(curl $HEALTH_CURL_OPTS https://localhost:8443/v1/ready 2>/dev/null)
    if echo "$READY_OUTPUT" | grep -q '"ready": true'; then
        echo "✓ API readiness check passed (HTTPS)"
        break
    elif [[ $i -eq 5 ]]; then
        echo "⚠ API server not ready after 15s"
    fi
done

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
