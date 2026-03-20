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
    --exclude 'certs/*.crt' \
    --exclude 'certs/*.key' \
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

# 5. Restart server
# Kill the process — launchd KeepAlive automatically restarts it.
# Do NOT use `kickstart -k` after kill: launchd already restarts on death,
# and kickstart would kill the restarting process a second time.
echo "--- Restarting server ---"
lsof -i :8443 | grep LISTEN | awk '{print $2}' | xargs kill -9 2>/dev/null || true

# If no launchd plist, start manually
if [[ ! -f ~/Library/LaunchAgents/com.hestia.server.plist ]]; then
  sleep 2
  "$HESTIA_HOME/.venv/bin/python" -m hestia.api.server &
  disown
fi

# 7. Readiness check (server needs ~50s for full manager init)
# Uses Python instead of curl to avoid LibreSSL/SecureTransport mismatches
# between interactive shell and launchd runner environments.
echo "--- Checking readiness ---"
for i in $(seq 1 12); do
  sleep 5
  if ! lsof -i :8443 | grep -q LISTEN; then
    echo "::warning::Attempt $i: No process listening on 8443 — server may have crashed"
  fi
  if "$HESTIA_HOME/.venv/bin/python" -c "
import urllib.request, ssl, sys
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
try:
    r = urllib.request.urlopen('https://localhost:8443/v1/ready', context=ctx, timeout=3)
    sys.exit(0 if b'ready' in r.read() else 1)
except Exception as e:
    print(f'  readiness check error: {e}', file=sys.stderr)
    sys.exit(1)
"; then
    echo "Server ready (attempt $i)"
    echo "=== Deploy complete ==="
    exit 0
  fi
  echo "Attempt $i: not ready, retrying..."
done

echo "::error::Readiness check failed after 60 seconds"
echo "Manual recovery: ssh andrewroman117@hestia-3.local 'launchctl load ~/Library/LaunchAgents/com.hestia.server.plist'"
exit 1
