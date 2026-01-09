# Hestia Deployment Guide

This document covers deploying Hestia from the development MacBook to the production Mac Mini.

## Prerequisites

### Mac Mini Setup (One-time)

1. **Tailscale**: Install and authenticate
   ```bash
   brew install tailscale
   # Follow auth instructions
   ```

2. **SSH Key**: Copy your MacBook's public key
   ```bash
   # On MacBook:
   ssh-copy-id andrew@hestia-server
   ```

3. **Python Environment**:
   ```bash
   # On Mac Mini:
   cd ~/hestia
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   ```

4. **Ollama**: Install and pull model
   ```bash
   brew install ollama
   ollama pull mixtral:8x7b-instruct-v0.1-q4_K_M
   ```

5. **Git Repository**: Initialize bare repo
   ```bash
   cd ~
   mkdir hestia && cd hestia
   git init
   ```

6. **launchd Service** (optional):
   ```bash
   # Create ~/Library/LaunchAgents/com.hestia.server.plist
   # Service will be loaded by deployment script
   ```

### MacBook Setup

1. **Tailscale**: Install and authenticate
2. **SSH Config** (optional, add to `~/.ssh/config`):
   ```
   Host hestia-server
       HostName hestia-server
       User andrew
       IdentityFile ~/.ssh/id_ed25519
   ```

## First-Time Deployment

Run the initial push script from your MacBook:

```bash
cd ~/hestia
./scripts/initial-push.sh
```

This will:
1. Run pre-deployment checks
2. Stage and commit all files
3. Add Mac Mini as Git remote `mini`
4. Push to Mac Mini (force push for initial)
5. Run full deployment

### What Gets Deployed

**Included:**
- `hestia/` - Python package
- `scripts/` - Deployment scripts
- `tests/` - Test suite
- `docs/` - Documentation
- `requirements.txt`
- `README.md`
- `CLAUDE.md`

**Excluded (never deployed):**
- `.venv/` - Virtual environment (created on each machine)
- `__pycache__/` - Python cache
- `.git/` - Git directory
- `logs/` - Log files
- `data/` - Data files
- `.DS_Store` - macOS metadata

## Regular Deployment Workflow

For subsequent deployments after the initial push:

```bash
# Quick deploy (rsync only, no git)
./scripts/deploy-to-mini.sh

# Or commit and push via git
git add -A
git commit -m "Your commit message"
git push mini main
```

### deploy-to-mini.sh Flow

1. Verify project structure
2. Check Mac Mini connectivity
3. Run pre-deployment checks (credential scan, type check, tests)
4. Rsync files to Mac Mini
5. Install/update Python dependencies
6. Run tests
7. Reload launchd service (if configured)
8. Health check (if API running)
9. Log deployment event

## Deploying Swift Tools

Swift CLI tools (like `hestia-keychain-cli`) need to be compiled and deployed separately:

```bash
./scripts/sync-swift-tools.sh
```

This will:
1. Build Swift tools in release mode
2. Copy binaries to `~/.hestia/bin/` on Mac Mini
3. Set executable permissions
4. Verify tools work

### First Run of Swift Tools

On Mac Mini, Swift tools using Secure Enclave require:
1. **Security Approval**: System Preferences > Security & Privacy
2. **Touch ID Setup**: If using biometric authentication
3. **Keychain Access**: May prompt for permission

## Rollback Procedure

### Quick Rollback (Git)

```bash
# On Mac Mini:
cd ~/hestia
git log --oneline -5  # Find commit to rollback to
git checkout <commit-hash>

# Reload service
launchctl unload ~/Library/LaunchAgents/com.hestia.server.plist
launchctl load ~/Library/LaunchAgents/com.hestia.server.plist
```

### Full Rollback

If the deployment is severely broken:

```bash
# On Mac Mini:
cd ~/hestia
git reset --hard HEAD~1  # Go back one commit
pip install -r requirements.txt  # Restore dependencies

# Restart service
launchctl unload ~/Library/LaunchAgents/com.hestia.server.plist
launchctl load ~/Library/LaunchAgents/com.hestia.server.plist
```

## Credential Sync

Credentials are **NOT** synced automatically for security reasons. They must be set up manually on each machine.

### Setting Up Credentials on Mac Mini

```bash
# SSH to Mac Mini
ssh andrew@hestia-server

# Activate environment
cd ~/hestia
source .venv/bin/activate

# Use Python to store credentials
python3 << 'EOF'
from hestia.security.credential_manager import CredentialManager

cm = CredentialManager()

# Store operational credentials (API keys)
cm.store_operational("anthropic_api_key", "your-key-here")

# Store sensitive credentials (requires biometric on access)
cm.store_sensitive("ssn", "xxx-xx-xxxx", reason="Initial setup")
EOF
```

### Verifying Credentials

```bash
python3 << 'EOF'
from hestia.security.credential_manager import CredentialManager

cm = CredentialManager()
key = cm.retrieve_operational("anthropic_api_key")
print(f"Key present: {key is not None}")
EOF
```

## Common Issues and Solutions

### SSH Connection Fails

```
Error: Cannot connect to Mac Mini (andrew@hestia-server)
```

**Solutions:**
1. Check Tailscale: `tailscale status`
2. Wake Mac Mini (if sleeping)
3. Verify SSH key: `ssh -v andrew@hestia-server`

### Package Import Fails

```
Error: Package import failed
```

**Solutions:**
1. Check venv is activated
2. Reinstall dependencies: `pip install -r requirements.txt`
3. Check for syntax errors: `python -m py_compile hestia/__init__.py`

### Credential Leak Detected

```
Error: Possible credential leak detected
```

**Solutions:**
1. Review flagged files
2. Remove hardcoded credentials
3. Use CredentialManager instead
4. Add sensitive files to `.gitignore`

### launchd Service Won't Start

**Check service status:**
```bash
launchctl list | grep hestia
```

**Check logs:**
```bash
tail -f ~/hestia/logs/hestia.log
```

**Manual restart:**
```bash
launchctl unload ~/Library/LaunchAgents/com.hestia.server.plist
launchctl load ~/Library/LaunchAgents/com.hestia.server.plist
```

### Tests Failing

Tests are non-blocking warnings. To investigate:

```bash
# Run with verbose output
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/test_logging.py -v
```

## Deployment Checklist

Before deploying:
- [ ] All changes committed locally
- [ ] Pre-deployment checks pass
- [ ] No credentials in code
- [ ] Tests pass (or expected failures documented)

After deploying:
- [ ] Package imports successfully on Mac Mini
- [ ] Service running (if applicable)
- [ ] Health check passes (if API running)
- [ ] Logs show expected startup messages

## Monitoring

### View Logs

```bash
# Tail main log
ssh andrew@hestia-server 'tail -f ~/hestia/logs/hestia.log'

# View audit log
ssh andrew@hestia-server 'tail -f ~/hestia/logs/audit.log'

# Use log viewer
ssh andrew@hestia-server 'cd ~/hestia && source .venv/bin/activate && python -m hestia.logging.viewer'
```

### Check Service Status

```bash
ssh andrew@hestia-server 'launchctl list | grep hestia'
```

### Deployment History

```bash
cat ~/hestia/logs/deployments.log
```
