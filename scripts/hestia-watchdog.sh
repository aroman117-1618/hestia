#!/bin/bash
#
# hestia-watchdog.sh — Health-check watchdog for Hestia server
#
# Primary check: /v1/ready (proves full manager stack is initialized).
# Secondary check: /v1/health (reports degraded components).
# After 2 consecutive readiness failures, force-restarts via launchctl.
#
# Designed to run as a launchd StartInterval job (every 60s).
# Max silent downtime: 2 failures × 60s = 2 minutes.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${PROJECT_ROOT}/logs/watchdog.log"
STATE_FILE="${PROJECT_ROOT}/logs/.watchdog-failures"

mkdir -p "$(dirname "$LOG_FILE")"

MAX_FAILURES=2
READY_URL="https://localhost:8443/v1/ready"
HEALTH_URL="https://localhost:8443/v1/health"
SERVICE_LABEL="com.hestia.server"

# External monitoring — ping Healthchecks.io on success (dead man's switch)
# Set this to your check UUID after creating at https://healthchecks.io
HC_PING_URL="${HESTIA_HC_PING_URL:-}"

# Push notifications via ntfy.sh on restart events
NTFY_TOPIC="${HESTIA_NTFY_TOPIC:-}"

log() {
    echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") | $1" >> "$LOG_FILE"
}

# Read current failure count
if [[ -f "$STATE_FILE" ]]; then
    FAILURES=$(cat "$STATE_FILE" 2>/dev/null)
    # Validate it's a number
    if ! [[ "$FAILURES" =~ ^[0-9]+$ ]]; then
        FAILURES=0
    fi
else
    FAILURES=0
fi

# Readiness check (replaces ping — catches both down AND still-initializing)
READY_OUTPUT=$(curl -sk --max-time 10 "$READY_URL" 2>/dev/null)
if echo "$READY_OUTPUT" | grep -q '"ready": true'; then
    # Ready succeeded — reset failure counter
    if [[ $FAILURES -gt 0 ]]; then
        log "RECOVERED | Ready check succeeded after ${FAILURES} failure(s)"
    fi
    echo "0" > "$STATE_FILE"

    # Ping Healthchecks.io — dead man's switch (alert if pings stop)
    if [[ -n "$HC_PING_URL" ]]; then
        curl -fsS --retry 3 --max-time 5 "$HC_PING_URL" > /dev/null 2>&1 || true
    fi

    # Optional: check /v1/health for degraded status
    HEALTH_OUTPUT=$(curl -sk --max-time 15 "$HEALTH_URL" 2>/dev/null)
    if echo "$HEALTH_OUTPUT" | grep -q '"degraded"'; then
        log "DEGRADED | Server ready but health is degraded"
    fi
else
    # Ready failed (server down, still initializing, or not ready)
    FAILURES=$((FAILURES + 1))
    echo "$FAILURES" > "$STATE_FILE"
    log "FAILURE ${FAILURES}/${MAX_FAILURES} | Ready check failed"

    if [[ $FAILURES -ge $MAX_FAILURES ]]; then
        log "RESTART | ${MAX_FAILURES} consecutive failures — restarting server"

        # Try launchctl kickstart first (restarts without unload/load)
        if launchctl kickstart -k "gui/$(id -u)/${SERVICE_LABEL}" 2>/dev/null; then
            log "RESTART | launchctl kickstart succeeded"
        else
            # Fallback: manual unload/load
            log "RESTART | kickstart failed, trying unload/load"
            launchctl unload ~/Library/LaunchAgents/${SERVICE_LABEL}.plist 2>/dev/null || true
            sleep 2
            launchctl load ~/Library/LaunchAgents/${SERVICE_LABEL}.plist 2>/dev/null || true
        fi

        # Reset counter after restart attempt
        echo "0" > "$STATE_FILE"

        # Push notification via ntfy.sh
        if [[ -n "$NTFY_TOPIC" ]]; then
            curl -fsS --max-time 5 \
                -H "Title: Hestia Server Restarted" \
                -H "Priority: high" \
                -H "Tags: warning" \
                -d "Watchdog restarted server after ${MAX_FAILURES} consecutive health check failures" \
                "https://ntfy.sh/${NTFY_TOPIC}" > /dev/null 2>&1 || true
        fi

        # Ping Healthchecks.io with failure signal
        if [[ -n "$HC_PING_URL" ]]; then
            curl -fsS --retry 3 --max-time 5 "${HC_PING_URL}/fail" > /dev/null 2>&1 || true
        fi
    fi
fi
