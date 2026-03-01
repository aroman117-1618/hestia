#!/bin/bash
# Kill stale Hestia server processes on port 8443
# Used as a SessionStart hook to prevent debugging stale code

PIDS=$(lsof -ti :8443 2>/dev/null)
if [ -n "$PIDS" ]; then
    echo "$PIDS" | xargs kill -9 2>/dev/null
    echo "Killed stale server processes on port 8443: $PIDS"
else
    echo "No stale server processes found on port 8443"
fi
