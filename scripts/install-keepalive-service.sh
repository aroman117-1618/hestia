#!/bin/bash
# install-keepalive-service.sh
# Installs the Ollama keepalive launchd service on macOS.
#
# Usage: ./install-keepalive-service.sh [--uninstall]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_NAME="com.hestia.ollama-keepalive.plist"
PLIST_SOURCE="${SCRIPT_DIR}/${PLIST_NAME}"
PLIST_DEST="${HOME}/Library/LaunchAgents/${PLIST_NAME}"

# Detect current user for plist paths
CURRENT_USER=$(whoami)
USER_HOME=$(eval echo ~${CURRENT_USER})

install_service() {
    echo "Installing Ollama keepalive service..."

    # Create LaunchAgents directory if needed
    mkdir -p "${HOME}/Library/LaunchAgents"

    # Create logs directory
    mkdir -p "${USER_HOME}/hestia/logs"

    # Copy plist with correct paths for this user
    sed "s|/Users/andrewroman117|${USER_HOME}|g" "${PLIST_SOURCE}" > "${PLIST_DEST}"

    # Set correct permissions
    chmod 644 "${PLIST_DEST}"

    # Unload if already loaded
    launchctl unload "${PLIST_DEST}" 2>/dev/null || true

    # Load the service
    launchctl load "${PLIST_DEST}"

    echo "Service installed successfully!"
    echo ""
    echo "Status:"
    launchctl list | grep "com.hestia.ollama-keepalive" || echo "  (service scheduled, will run shortly)"
    echo ""
    echo "Commands:"
    echo "  View logs:      tail -f ${USER_HOME}/hestia/logs/ollama-keepalive.log"
    echo "  Manual run:     ${SCRIPT_DIR}/ollama-keepalive.sh"
    echo "  Check status:   launchctl list | grep hestia"
    echo "  Stop service:   launchctl unload ${PLIST_DEST}"
    echo "  Start service:  launchctl load ${PLIST_DEST}"
    echo "  Uninstall:      $0 --uninstall"
}

uninstall_service() {
    echo "Uninstalling Ollama keepalive service..."

    # Unload if loaded
    if launchctl list | grep -q "com.hestia.ollama-keepalive"; then
        launchctl unload "${PLIST_DEST}"
        echo "Service unloaded."
    fi

    # Remove plist
    if [[ -f "${PLIST_DEST}" ]]; then
        rm "${PLIST_DEST}"
        echo "Plist removed."
    fi

    echo "Service uninstalled successfully!"
}

# Parse arguments
case "${1:-}" in
    --uninstall|-u)
        uninstall_service
        ;;
    --help|-h)
        echo "Usage: $0 [--uninstall]"
        echo ""
        echo "Installs the Ollama keepalive launchd service."
        echo ""
        echo "Options:"
        echo "  --uninstall, -u    Uninstall the service"
        echo "  --help, -h         Show this help"
        ;;
    *)
        install_service
        ;;
esac
