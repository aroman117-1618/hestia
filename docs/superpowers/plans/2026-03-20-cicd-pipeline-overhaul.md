# CI/CD Pipeline Overhaul — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the broken deploy pipeline by switching to the existing self-hosted runner, improve job clarity with descriptive names and step summaries, and resolve all warnings.

**Architecture:** The Mac Mini already runs a self-hosted GitHub Actions runner (labels: `self-hosted, macos, hestia` — matching `release-macos.yml`). We'll migrate `deploy.yml` from `ubuntu-latest` + SSH/rsync to `self-hosted` + local rsync from workspace, eliminating the Tailscale tunnel dependency entirely. CI tests stay on `ubuntu-latest` (free, fast, no Mac Mini load). Deploy runs locally on the Mac Mini.

**Tech Stack:** GitHub Actions, self-hosted runner on Mac Mini M1, Python 3.9 (Mac Mini venv), pytest, launchd

**Known constraint:** Mac Mini venv uses Python 3.9.6 (Xcode CLI tools). CI uses 3.11. The lockfile must be compatible with both. A Python 3.11 upgrade on the Mac Mini is out of scope for this plan but should be a future task.

---

## Current State

| Workflow | File | Runs On | Status |
|----------|------|---------|--------|
| `ci.yml` | Reusable CI (tests) | `ubuntu-latest` | PASS (warnings) |
| `deploy.yml` | Test + Deploy to Mac Mini | `ubuntu-latest` | **FAIL** (SSH can't resolve host — no Tailscale tunnel) |
| `release-macos.yml` | macOS app build/sign/notarize | `self-hosted, macos, hestia` | PASS |
| `claude.yml` | Claude Code on PRs | `ubuntu-latest` | PASS |

**Issues:**
1. Deploy fails — SSH to Mac Mini requires Tailscale tunnel (commented out, never configured)
2. Vague job/step names — "test / test" and "deploy" give no context
3. Node.js 20 deprecation — `actions/checkout@v4` needs v5
4. Stale `requirements.txt` — needs pip-compile refresh
5. One-time cron schedule in `release-macos.yml` should be removed (already fired)
6. Deploy runs full test suite on Mac Mini (redundant with CI — should only run integration tests)

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `.github/workflows/deploy.yml` | **Rewrite** | Switch to self-hosted runner, local deploy, clear step names |
| `.github/workflows/ci.yml` | **Modify** | Bump action versions, improve job/step names |
| `.github/workflows/release-macos.yml` | **Modify** | Remove one-time cron, bump action versions |
| `.github/workflows/claude.yml` | **Modify** | Bump action versions |
| `requirements.txt` | **Regenerate** | pip-compile from requirements.in |
| `scripts/deploy-local.sh` | **Create** | Self-contained deploy script (used by workflow and manual deploys) |

---

## Task 1: Refresh requirements.txt

**Files:**
- Modify: `requirements.txt` (regenerate)

- [ ] **Step 1: Regenerate lockfile**

Use `--python-version 3.9` to ensure compatibility with the Mac Mini's Python:

```bash
cd ~/hestia
source .venv/bin/activate
pip-compile requirements.in --output-file=requirements.txt --no-emit-index-url --python-version 3.9
```

If any packages fail to resolve on 3.9, note them — they'll need version pins in `requirements.in`.

- [ ] **Step 2: Verify tests still pass with updated deps**

```bash
python -m pytest tests/ --timeout=30 -m "not integration" -x -q
```
Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: refresh requirements.txt lockfile (Python 3.9 compat)"
```

---

## Task 2: Create deploy script and rewrite deploy.yml

This task combines the deploy script creation AND the workflow rewrite into a single unit. The script handles two contexts: GitHub Actions (workspace != ~/hestia) and manual invocation (already in ~/hestia).

**Files:**
- Create: `scripts/deploy-local.sh`
- Rewrite: `.github/workflows/deploy.yml`

- [ ] **Step 1: Write the deploy script**

```bash
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
  # rsync --delete removes files not in source, but excludes preserve runtime state
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

# 3. Install/update dependencies (all pip/pytest commands use venv Python)
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
    # Fallback to unload/load if kickstart fails
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
  # Detect "not running" vs "starting up"
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
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/deploy-local.sh
```

- [ ] **Step 3: Rewrite deploy.yml**

```yaml
name: Hestia Deploy

on:
  push:
    branches: [main]
  workflow_dispatch:

concurrency:
  group: deploy
  cancel-in-progress: false

jobs:
  test:
    name: "CI Tests (Ubuntu)"
    # No inputs by design — if adding required inputs to ci.yml,
    # update this caller too.
    uses: ./.github/workflows/ci.yml

  deploy:
    name: "Deploy to Mac Mini"
    runs-on: [self-hosted, macos, hestia]
    needs: [test]
    if: github.ref == 'refs/heads/main'
    timeout-minutes: 10

    steps:
      - name: "Checkout code"
        uses: actions/checkout@v5

      - name: "Run deploy"
        run: |
          export REPO_DIR="${{ github.workspace }}"
          ./scripts/deploy-local.sh

      - name: "Deployment summary"
        if: success()
        run: |
          echo "### Deployed to Mac Mini" >> "$GITHUB_STEP_SUMMARY"
          echo "" >> "$GITHUB_STEP_SUMMARY"
          echo "| Field | Value |" >> "$GITHUB_STEP_SUMMARY"
          echo "|-------|-------|" >> "$GITHUB_STEP_SUMMARY"
          echo "| Commit | \`$(git rev-parse --short HEAD)\` |" >> "$GITHUB_STEP_SUMMARY"
          echo "| Branch | main |" >> "$GITHUB_STEP_SUMMARY"
          echo "| Time | $(date -u +%Y-%m-%dT%H:%M:%SZ) |" >> "$GITHUB_STEP_SUMMARY"

      - name: "Failure summary"
        if: failure()
        run: |
          echo "### Deploy Failed" >> "$GITHUB_STEP_SUMMARY"
          echo "" >> "$GITHUB_STEP_SUMMARY"
          echo "Check the **Run deploy** step logs for details." >> "$GITHUB_STEP_SUMMARY"
          echo "Manual recovery: \`ssh andrewroman117@hestia-3.local 'launchctl load ~/Library/LaunchAgents/com.hestia.server.plist'\`" >> "$GITHUB_STEP_SUMMARY"
```

- [ ] **Step 4: Commit**

```bash
git add scripts/deploy-local.sh .github/workflows/deploy.yml
git commit -m "fix: switch deploy to self-hosted runner, extract deploy script

Replaces SSH/rsync-over-Tailscale with local execution on Mac Mini's
existing self-hosted runner. Eliminates tunnel dependency that caused
every deploy to fail with 'could not resolve hostname'."
```

---

## Task 3: Improve ci.yml and bump all action versions

This task combines version bumps with the name improvements — no point touching the same files twice.

**Files:**
- Modify: `.github/workflows/ci.yml` (names + versions)
- Modify: `.github/workflows/release-macos.yml` (version bump + remove stale cron)
- Modify: `.github/workflows/claude.yml` (version bump)

- [ ] **Step 1: Rewrite ci.yml with clear names and v5 actions**

```yaml
name: Hestia CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  # deploy.yml calls this as a reusable workflow.
  # No inputs by design — keep this interface stable.
  workflow_call:

jobs:
  test:
    name: "Lint, Test & Audit"
    runs-on: ubuntu-latest
    timeout-minutes: 20

    steps:
      - name: "Checkout code"
        uses: actions/checkout@v5

      - name: "Set up Python 3.11"
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: "Check lockfile freshness"
        run: |
          pip install pip-tools -q
          pip-compile requirements.in --output-file=/tmp/requirements-check.txt --no-emit-index-url --quiet 2>/dev/null
          if ! diff -q requirements.txt /tmp/requirements-check.txt > /dev/null 2>&1; then
            echo "::warning::requirements.txt is stale. Run: pip-compile requirements.in --output-file=requirements.txt --no-emit-index-url"
          fi

      - name: "Install dependencies"
        run: pip install -r requirements.txt

      - name: "Run unit tests"
        run: python -m pytest tests/ --tb=short --timeout=30 -m "not integration" -v 2>&1 | tail -100

      - name: "Verify test collection"
        run: python -m pytest tests/ --collect-only -q 2>&1 | tail -5

      - name: "Security audit (pip-audit)"
        run: |
          pip install pip-audit -q
          pip-audit --strict --desc 2>&1 || true
```

- [ ] **Step 2: Update release-macos.yml — bump checkout, remove stale cron**

In `release-macos.yml`:
- Replace `actions/checkout@v4` with `actions/checkout@v5`
- Remove the `schedule:` block:
  ```yaml
    schedule:
      - cron: '0 13 20 3 *'  # 9 AM ET March 20 — one-time retry for v1.0.1
  ```

- [ ] **Step 3: Update claude.yml — bump checkout**

Replace `actions/checkout@v4` with `actions/checkout@v5`.
Leave `anthropics/claude-code-action@v1` as-is (v2 not yet released).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml .github/workflows/release-macos.yml .github/workflows/claude.yml
git commit -m "chore: bump Actions to v5, improve CI names, remove stale cron"
```

---

## Task 4: End-to-end verification

- [ ] **Step 1: Push to main and watch the Actions run**

```bash
git push origin main
```

- [ ] **Step 2: Verify in GitHub Actions UI**

Expected:
- **"Hestia CI"** workflow: job **"Lint, Test & Audit"** — PASS, no Node.js 20 warning, no stale lockfile warning
- **"Hestia Deploy"** workflow: **"CI Tests (Ubuntu) / Lint, Test & Audit"** → **"Deploy to Mac Mini"** — both PASS
- Deploy job runs on Mac Mini runner (check runner label in UI)
- Deploy summary shows commit hash, branch, timestamp in the Summary tab

- [ ] **Step 3: Verify server is running on Mac Mini**

```bash
ssh andrewroman117@hestia-3.local "curl -sk https://localhost:8443/v1/ready"
```
Expected: `{"ready": true, ...}`

- [ ] **Step 4: Clean up unused secrets**

Verify these are only used by the old deploy.yml:
```bash
grep -r "MAC_MINI_SSH_KEY\|MAC_MINI_HOST" .github/workflows/
```

If only the old deploy.yml referenced them → delete via GitHub Settings > Secrets:
- `MAC_MINI_SSH_KEY`
- `MAC_MINI_HOST`

---

## Summary of Changes

| Before | After |
|--------|-------|
| Deploy: `ubuntu-latest` + SSH + rsync | Deploy: `self-hosted` + local script |
| SSH fails (no Tailscale tunnel) | No network dependency — runner IS the Mac Mini |
| "test / test" job name | "Lint, Test & Audit" |
| "deploy" job name | "Deploy to Mac Mini" |
| `actions/checkout@v4` (Node 20 warning) | `actions/checkout@v5` |
| Stale requirements.txt | Refreshed lockfile (Python 3.9 compatible) |
| Deploy runs ALL tests on Mac Mini | Deploy runs only integration tests |
| One-time cron in release-macos.yml | Removed |
| Deploy logic inline in YAML heredoc | Extracted to `scripts/deploy-local.sh` |
| nohup uses bare `python` | Uses explicit venv path |
| launchctl errors silently swallowed | Uses `kickstart -k` with fallback |
| No crash detection in readiness loop | `lsof` check warns if no process listening |
| No recovery instructions on failure | Manual recovery in failure summary |

## Secrets After Migration

| Secret | Used By | Status |
|--------|---------|--------|
| `MAC_MINI_SSH_KEY` | (was deploy.yml) | **Can remove** |
| `MAC_MINI_HOST` | (was deploy.yml) | **Can remove** |
| `KEYCHAIN_PASSWORD` | release-macos.yml | Keep |
| `AC_USERNAME/PASSWORD/TEAM_ID` | release-macos.yml | Keep |
| `SPARKLE_PRIVATE_KEY` | release-macos.yml | Keep |
| `ANTHROPIC_API_KEY` | claude.yml | Keep |

## Future Work (out of scope)

- **Upgrade Mac Mini Python to 3.11** via Homebrew — eliminates the 3.9/3.11 split risk
- **Add rollback automation** — capture pre-deploy SHA, add "Rollback" button in failure summary
- **Concurrent runner protection** — if release + deploy overlap, deploy waits (acceptable but could add `concurrency` group across both workflows)
