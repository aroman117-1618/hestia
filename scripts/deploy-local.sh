#!/usr/bin/env bash
# deploy-local.sh — Deploy Hestia on the Mac Mini (runs locally, not via SSH).
#
# Called by:
#   - GitHub Actions deploy job (self-hosted runner) — REPO_DIR=$GITHUB_WORKSPACE
#   - Manual invocation — REPO_DIR defaults to ~/hestia
#
# Prerequisites:
#   - ~/hestia/.venv must exist (one-time bootstrap: python3 -m venv ~/hestia/.venv)
#   - launchd plist installed at ~/Library/LaunchAgents/com.hestia.server.plist
#
# Design decisions:
#   - Integration test failures are non-blocking (Ollama may be offline, but
#     the server should still deploy). Failures log as GitHub Actions warnings.
#   - The server always runs from ~/hestia (where .venv, data/, logs/, and
#     Keychain access live), not from the Actions workspace.
set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/hestia}"
HESTIA_HOME="$HOME/hestia"

echo "=== Hestia Deploy ==="
echo "Source: $REPO_DIR"
echo "Target: $HESTIA_HOME"

# 1. Sync code to ~/hestia
if [[ "$REPO_DIR" != "$HESTIA_HOME" ]]; then
  echo "--- Syncing from Actions workspace ---"
  rsync -a --delete \
    --exclude '.venv/' \
    --exclude '__pycache__/' \
    --exclude 'logs/' \
    --exclude 'data/' \
    --exclude '.DS_Store' \
    --exclude '*.pyc' \
    --exclude '.pytest_cache/' \
    --exclude '.claude/worktrees/' \
    "$REPO_DIR/" "$HESTIA_HOME/"
else
  echo "--- Pulling latest ---"
  git fetch origin main
  git reset --hard origin/main
fi

cd "$HESTIA_HOME"
echo "Commit: $(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"

# 2. Verify venv exists
if [[ ! -d "$HESTIA_HOME/.venv" ]]; then
  echo "::error::No .venv at $HESTIA_HOME — run: python3 -m venv $HESTIA_HOME/.venv"
  exit 1
fi

# 3. Install/update dependencies (explicit venv path avoids PATH issues)
echo "--- Installing dependencies ---"
"$HESTIA_HOME/.venv/bin/pip" install -r requirements.txt -q

# 4. Run integration tests (non-blocking — Ollama may be offline)
echo "--- Running integration tests ---"
"$HESTIA_HOME/.venv/bin/python" -m pytest tests/ -v --timeout=120 -m "integration" -x 2>&1 | tail -30 || {
  echo "::warning::Integration tests failed — check logs above (non-blocking)"
}

# 5. Kill stale server processes
echo "--- Restarting server ---"
lsof -i :8443 | grep LISTEN | awk '{print $2}' | xargs kill -9 2>/dev/null || true
sleep 2

# 6. Restart via launchd (preferred) or nohup fallback
if [[ -f ~/Library/LaunchAgents/com.hestia.server.plist ]]; then
  launchctl kickstart -k "gui/$(id -u)/com.hestia.server" 2>/dev/null || {
    launchctl unload ~/Library/LaunchAgents/com.hestia.server.plist 2>/dev/null || true
    sleep 1
    launchctl load ~/Library/LaunchAgents/com.hestia.server.plist
  }
else
  "$HESTIA_HOME/.venv/bin/python" -m hestia.api.server &
  disown
fi

# 7. Readiness check (server needs ~25s for full manager init)
echo "--- Checking readiness ---"
for i in 1 2 3 4 5 6 7 8; do
  sleep 5
  if ! lsof -i :8443 | grep -q LISTEN; then
    echo "::warning::Attempt $i: No process listening on 8443 — server may have crashed"
  fi
  if curl -sk https://localhost:8443/v1/ready | grep -q '"ready": true'; then
    echo "Server ready (attempt $i)"
    echo "=== Deploy complete ==="
    exit 0
  fi
  echo "Attempt $i: not ready, retrying..."
done

echo "::error::Readiness check failed after 40 seconds"
echo "Manual recovery: ssh andrewroman117@hestia-3.local 'launchctl load ~/Library/LaunchAgents/com.hestia.server.plist'"
exit 1
