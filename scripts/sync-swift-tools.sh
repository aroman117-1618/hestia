#!/bin/bash
#
# sync-swift-tools.sh - Build and deploy Swift CLI tools to Mac Mini
#
# Handles:
# - hestia-keychain-cli (Secure Enclave operations)
# - Future Swift tools
#
# Usage: ./scripts/sync-swift-tools.sh
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
MINI_BIN_PATH="~/.hestia/bin"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Sync Swift Tools to Mac Mini${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

cd "$PROJECT_ROOT"

# Check for Swift CLI tools directory
SWIFT_TOOLS_DIR="${PROJECT_ROOT}/hestia-cli-tools"
if [[ ! -d "$SWIFT_TOOLS_DIR" ]]; then
    echo -e "${YELLOW}⚠${NC} No Swift tools directory found at hestia-cli-tools/"
    exit 0
fi

# Check SSH connectivity
echo -e "${YELLOW}Checking Mac Mini connectivity...${NC}"
if ! ssh -q -o ConnectTimeout=5 "$MINI_HOST" exit 2>/dev/null; then
    echo -e "${RED}Error: Cannot connect to Mac Mini (${MINI_HOST})${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Mac Mini is reachable"

# Create bin directory on Mac Mini
echo -e "\n${YELLOW}Creating bin directory on Mac Mini...${NC}"
ssh "$MINI_HOST" "mkdir -p ${MINI_BIN_PATH}"
echo -e "${GREEN}✓${NC} Directory ready: ${MINI_BIN_PATH}"

# Process each Swift tool
TOOLS_SYNCED=0

for tool_dir in "$SWIFT_TOOLS_DIR"/*/; do
    if [[ ! -d "$tool_dir" ]]; then
        continue
    fi

    tool_name=$(basename "$tool_dir")
    echo -e "\n${BLUE}Processing: ${tool_name}${NC}"

    # Check if it's a Swift package
    if [[ ! -f "${tool_dir}/Package.swift" ]]; then
        echo -e "${YELLOW}⚠${NC} Not a Swift package, skipping"
        continue
    fi

    # Check for existing binary
    release_binary="${tool_dir}/.build/release/${tool_name}"
    if [[ -f "$release_binary" ]]; then
        echo -e "${GREEN}✓${NC} Found built binary"
    else
        # Try to build
        echo -e "${YELLOW}Building ${tool_name}...${NC}"
        cd "$tool_dir"

        if swift build -c release 2>/dev/null; then
            echo -e "${GREEN}✓${NC} Build successful"
        else
            echo -e "${RED}✗${NC} Build failed"
            cd "$PROJECT_ROOT"
            continue
        fi

        cd "$PROJECT_ROOT"
    fi

    # Verify binary exists after build attempt
    if [[ ! -f "$release_binary" ]]; then
        echo -e "${RED}✗${NC} Binary not found after build"
        continue
    fi

    # Copy to Mac Mini
    echo -e "${YELLOW}Copying to Mac Mini...${NC}"
    scp "$release_binary" "${MINI_HOST}:${MINI_BIN_PATH}/"

    # Make executable on Mac Mini
    ssh "$MINI_HOST" "chmod +x ${MINI_BIN_PATH}/${tool_name}"
    echo -e "${GREEN}✓${NC} ${tool_name} deployed to Mac Mini"

    # Verify on Mac Mini
    echo -e "${YELLOW}Verifying on Mac Mini...${NC}"
    if ssh "$MINI_HOST" "${MINI_BIN_PATH}/${tool_name} --help" 2>/dev/null | head -1; then
        echo -e "${GREEN}✓${NC} Tool verified working"
    else
        echo -e "${YELLOW}⚠${NC} Tool may require additional setup (Secure Enclave permissions, etc.)"
    fi

    ((TOOLS_SYNCED++))
done

echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}   Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Tools synced: ${TOOLS_SYNCED}"
echo "Location on Mac Mini: ${MINI_BIN_PATH}"
echo ""

if [[ "$TOOLS_SYNCED" -gt 0 ]]; then
    echo -e "${YELLOW}Note:${NC} Swift tools using Secure Enclave may need:"
    echo "  1. First-run approval in System Preferences > Security"
    echo "  2. Touch ID/Face ID setup on the Mac Mini"
    echo "  3. Keychain access permissions"
    echo ""
    echo "Test on Mac Mini:"
    echo "  ssh ${MINI_HOST}"
    echo "  ${MINI_BIN_PATH}/hestia-keychain-cli --help"
fi

echo -e "\n${GREEN}✓ Swift tools sync complete${NC}"
