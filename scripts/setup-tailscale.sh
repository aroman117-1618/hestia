#!/bin/bash
# Setup Tailscale for Hestia remote access
#
# This script:
# 1. Checks Tailscale is installed and running
# 2. Gets the Tailscale hostname
# 3. Generates SSL certificate for that hostname
# 4. Creates a launchd plist for auto-starting Hestia
#
# Run this on the Mac Mini after installing Tailscale.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║           Hestia Tailscale Setup                           ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if Tailscale is installed
if ! command -v tailscale &> /dev/null; then
    echo "❌ Tailscale is not installed"
    echo ""
    echo "Install Tailscale from:"
    echo "  https://tailscale.com/download/mac"
    echo ""
    echo "Or via Homebrew:"
    echo "  brew install tailscale"
    exit 1
fi

echo "✓ Tailscale is installed"

# Check if Tailscale is running and connected
if ! tailscale status &> /dev/null; then
    echo "❌ Tailscale is not running or not connected"
    echo ""
    echo "Start Tailscale and log in:"
    echo "  tailscale up"
    exit 1
fi

echo "✓ Tailscale is running"

# Get Tailscale hostname
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "")
TAILSCALE_DNS=$(tailscale status --json | python3 -c "import sys,json; print(json.load(sys.stdin)['Self']['DNSName'].rstrip('.'))" 2>/dev/null || echo "")

if [ -z "$TAILSCALE_DNS" ]; then
    echo "⚠ Could not determine Tailscale DNS name"
    echo "  Your Tailscale IP is: $TAILSCALE_IP"
    echo ""
    echo "Enter your Tailscale hostname manually (e.g., hestia-mini.tail12345.ts.net):"
    read -r TAILSCALE_DNS
fi

echo "✓ Tailscale hostname: $TAILSCALE_DNS"
echo "  Tailscale IP: $TAILSCALE_IP"
echo ""

# Generate SSL certificate
echo "Generating SSL certificate..."
"$SCRIPT_DIR/generate-cert.sh" "$TAILSCALE_DNS"

# Create launchd plist for auto-start
PLIST_PATH="$HOME/Library/LaunchAgents/com.hestia.api.plist"
VENV_PATH="$PROJECT_DIR/.venv"
PYTHON_PATH="$VENV_PATH/bin/python"

echo ""
echo "Creating launchd service..."

cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.hestia.api</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_PATH</string>
        <string>-m</string>
        <string>hestia.api.server</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>8443</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HESTIA_SSL_CERT</key>
        <string>$PROJECT_DIR/certs/hestia.crt</string>
        <key>HESTIA_SSL_KEY</key>
        <string>$PROJECT_DIR/certs/hestia.key</string>
        <key>PYTHONPATH</key>
        <string>$PROJECT_DIR</string>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/logs/hestia-api.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/logs/hestia-api.error.log</string>
</dict>
</plist>
EOF

echo "✓ Created launchd plist: $PLIST_PATH"

# Create logs directory
mkdir -p "$PROJECT_DIR/logs"

# Load the service
echo ""
echo "Loading launchd service..."
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

echo "✓ Service loaded and started"

# Summary
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    Setup Complete                          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Hestia API is now running on:"
echo "  Local:      https://localhost:8443"
echo "  Tailscale:  https://$TAILSCALE_DNS:8443"
echo ""
echo "Service management:"
echo "  View logs:  tail -f $PROJECT_DIR/logs/hestia-api.log"
echo "  Stop:       launchctl unload $PLIST_PATH"
echo "  Start:      launchctl load $PLIST_PATH"
echo "  Restart:    launchctl kickstart -k gui/\$(id -u)/com.hestia.api"
echo ""
echo "iOS Configuration:"
echo "  1. Trust the certificate on your iOS device:"
echo "     AirDrop $PROJECT_DIR/certs/hestia.crt to your device"
echo "     Settings > General > VPN & Device Management > Install"
echo "     Settings > General > About > Certificate Trust Settings > Enable"
echo ""
echo "  2. Update Hestia app settings:"
echo "     Environment: Tailscale"
echo "     Custom Host: $TAILSCALE_DNS"
echo ""
echo "Test the connection:"
echo "  curl -k https://$TAILSCALE_DNS:8443/v1/health"
