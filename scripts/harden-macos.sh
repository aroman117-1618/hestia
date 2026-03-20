#!/bin/bash
#
# harden-macos.sh — macOS hardening for enterprise-grade Hestia server
#
# Run on the Mac Mini with sudo: sudo ./scripts/harden-macos.sh
# Safe to re-run — all commands are idempotent.

set -euo pipefail

echo "=== Hestia macOS Hardening ==="

# 1. Prevent disk sleep (causes SQLite I/O errors)
echo "[1/4] Setting disksleep to 0..."
sudo pmset -a disksleep 0

# 2. Verify sleep is already disabled (should be from initial setup)
echo "[2/4] Verifying power settings..."
sudo pmset -a sleep 0
sudo pmset -a standby 0
sudo pmset -a autorestart 1

# 3. Disable automatic macOS updates (they reboot the machine)
echo "[3/4] Disabling automatic macOS updates..."
sudo defaults write /Library/Preferences/com.apple.SoftwareUpdate AutomaticDownload -bool false
sudo defaults write /Library/Preferences/com.apple.SoftwareUpdate AutomaticallyInstallMacOSUpdates -bool false
sudo defaults write /Library/Preferences/com.apple.SoftwareUpdate CriticalUpdateInstall -bool false

# 4. Verify
echo "[4/4] Verifying settings..."
echo ""
echo "Power settings:"
pmset -g | grep -E "sleep|disksleep|standby|autorestart"
echo ""
echo "Auto-update settings:"
defaults read /Library/Preferences/com.apple.SoftwareUpdate AutomaticDownload 2>/dev/null || echo "  AutomaticDownload: not set"
defaults read /Library/Preferences/com.apple.SoftwareUpdate AutomaticallyInstallMacOSUpdates 2>/dev/null || echo "  AutomaticallyInstallMacOSUpdates: not set"

echo ""
echo "=== Hardening complete ==="
