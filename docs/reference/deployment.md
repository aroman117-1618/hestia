# Hestia Deployment Guide

## Mac Mini Production Setup

### Prerequisites

- Mac Mini M1 accessible via Tailscale (`andrewroman117@hestia-3.local`)
- Python 3.12 venv at `~/hestia/.venv`
- Self-signed TLS certs at `~/hestia/certs/`
- Ollama running with `qwen3.5:9b`, `qwen2.5-coder:7b`, and `qwen2.5:0.5b` pulled

### First-Time Setup

1. **SSH key**: `ssh-copy-id andrewroman117@hestia-3.local`
2. **Python**: `python3 -m venv ~/hestia/.venv && source ~/.venv/bin/activate && pip install -r requirements.txt`
3. **Install server service**: `./scripts/install-server-service.sh`
4. **Install watchdog** (optional): `cp scripts/com.hestia.watchdog.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.hestia.watchdog.plist`

### Manual Deployment

```bash
./scripts/deploy-to-mini.sh
```

Performs: rsync, pip install, pytest, launchd reload (or nohup fallback), health check.

### Launchd Server Service

The server runs as a persistent launchd service (auto-restart on crash, auto-start at login):

```bash
# On the Mac Mini:
./scripts/install-server-service.sh
```

Copies `scripts/com.hestia.server.plist` to `~/Library/LaunchAgents/` and loads it.

```bash
# Check status
launchctl list | grep hestia.server

# Stop
launchctl unload ~/Library/LaunchAgents/com.hestia.server.plist

# Start
launchctl load ~/Library/LaunchAgents/com.hestia.server.plist

# View logs
tail -f ~/hestia/logs/server-stdout.log
tail -f ~/hestia/logs/server-stderr.log
```

### Watchdog

A watchdog plist polls `/v1/ping` every 5 minutes and force-restarts after 3 consecutive failures:

```bash
cp scripts/com.hestia.watchdog.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.hestia.watchdog.plist
```

Watchdog logs: `~/hestia/logs/watchdog.log`

## CI/CD (GitHub Actions)

### Required GitHub Secrets

Two secrets must be added manually at **Settings > Secrets and variables > Actions**:

| Secret | Value |
|--------|-------|
| `MAC_MINI_SSH_KEY` | Ed25519 private key for `andrewroman117@hestia-3.local` |
| `MAC_MINI_HOST` | Tailscale hostname (e.g., `hestia-3.local`) |

### Pipeline Flow

1. **Push to main** triggers `deploy.yml`
2. CI runs full test suite (`ci.yml`)
3. On success: rsync to Mac Mini, pip install, pytest (with Ollama), launchd reload
4. Health check (5 retries with 3s intervals)

### SSH Configuration

The deploy workflow uses `ssh-keyscan` for dynamic host key lookup (Tailscale IPs change) with `StrictHostKeyChecking=accept-new` as fallback.

## What Gets Deployed

**Included:** `hestia/`, `scripts/`, `tests/`, `docs/`, `requirements.txt`, `CLAUDE.md`

**Excluded:** `.venv/`, `__pycache__/`, `.git/`, `logs/`, `data/`, `.DS_Store`, `.build/`, `DerivedData/`

## Credential Sync

Credentials are **not** synced. Set up manually on each machine via `CredentialManager`.

## Rollback

```bash
# On Mac Mini:
cd ~/hestia
git log --oneline -5
git checkout <commit-hash>
launchctl unload ~/Library/LaunchAgents/com.hestia.server.plist
launchctl load ~/Library/LaunchAgents/com.hestia.server.plist
```

## Monitoring

```bash
# Server logs
ssh andrewroman117@hestia-3.local 'tail -f ~/hestia/logs/server-stderr.log'

# Watchdog logs
ssh andrewroman117@hestia-3.local 'tail -f ~/hestia/logs/watchdog.log'

# Service status
ssh andrewroman117@hestia-3.local 'launchctl list | grep hestia'

# Deployment history
cat ~/hestia/logs/deployments.log
```
