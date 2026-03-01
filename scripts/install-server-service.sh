#!/bin/bash
#
# install-server-service.sh — Install Hestia server as a launchd service
#
# Usage: ./scripts/install-server-service.sh
#
# Copies the plist to ~/Library/LaunchAgents/ and loads it.
# Run on the Mac Mini (production) or dev machine for local testing.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_NAME="com.hestia.server.plist"
PLIST_SRC="${SCRIPT_DIR}/${PLIST_NAME}"
PLIST_DST="$HOME/Library/LaunchAgents/${PLIST_NAME}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Verify plist exists
if [[ ! -f "$PLIST_SRC" ]]; then
    echo -e "${RED}Error: ${PLIST_NAME} not found at ${PLIST_SRC}${NC}"
    exit 1
fi

# Create logs directory
mkdir -p "$HOME/hestia/logs"

# Unload existing service if present
if launchctl list | grep -q "com.hestia.server"; then
    echo -e "${YELLOW}Unloading existing service...${NC}"
    launchctl unload "$PLIST_DST" 2>/dev/null || true
    sleep 1
fi

# Copy plist
echo "Installing plist to ${PLIST_DST}"
cp "$PLIST_SRC" "$PLIST_DST"

# Load service
echo "Loading service..."
launchctl load "$PLIST_DST"

echo -e "${GREEN}Service loaded.${NC} Waiting for server to start..."

# Health check with retry
for i in 1 2 3 4 5; do
    sleep 3
    if curl -sk https://localhost:8443/v1/ping 2>/dev/null | grep -q "pong"; then
        echo -e "${GREEN}Health check passed (attempt ${i}).${NC}"
        echo ""
        echo "Service status:"
        launchctl list | grep hestia.server || true
        exit 0
    fi
    echo "  Attempt ${i} — waiting..."
done

echo -e "${RED}Health check failed after 5 attempts.${NC}"
echo "Check logs: tail -f ~/hestia/logs/server-stderr.log"
exit 1
