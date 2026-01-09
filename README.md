# Hestia

A locally-hosted personal AI assistant running on Mac Mini M1.

## Current Status

| Phase | Name | Status |
|-------|------|--------|
| 0 | Environment Setup | Complete |
| 0.5 | Security Foundation | Complete |
| 1 | Logging Infrastructure | Complete |
| 2 | Inference Layer | Next |
| 3 | Memory Layer | Planned |
| 3.5 | Tag-Based Memory | Planned |
| 4 | Orchestration | Planned |
| 5 | Execution Layer | Planned |
| 5.5 | Apple Ecosystem | Planned |
| 6 | Access Layer + Native App | Planned |
| 7 | Integration & Hardening | Planned |
| 8 | Iteration | Planned |

## Implemented Features

### Security (Phase 0.5)
- **CredentialManager**: Three-tier credential partitioning (operational/sensitive/system)
- **Double Encryption**: Fernet + macOS Keychain AES-256
- **Secure Enclave Support**: Swift CLI for biometric-protected credentials
- **Audit Trail**: Every credential access is logged

### Logging (Phase 1)
- **HestiaLogger**: JSON structured logging with request ID propagation
- **Credential Sanitization**: API keys, passwords, SSN automatically redacted
- **AuditLogger**: Tamper-resistant logging with checksums, 7-year retention
- **Log Viewer**: CLI tool for filtering and viewing logs

## Project Structure

```
hestia/
├── hestia/                      # Python package
│   ├── security/
│   │   └── credential_manager.py   # Pentagon-grade credential management
│   ├── logging/
│   │   ├── structured_logger.py    # JSON logging with sanitization
│   │   ├── audit_logger.py         # 7-year retention audit logs
│   │   └── viewer.py               # CLI log viewer
│   ├── inference/               # Placeholder (Phase 2)
│   ├── memory/                  # Placeholder (Phase 3)
│   ├── orchestration/           # Placeholder (Phase 4)
│   ├── execution/               # Placeholder (Phase 5)
│   ├── persona/                 # Placeholder
│   ├── api/                     # Placeholder (Phase 6)
│   └── config/                  # Placeholder
├── hestia-cli-tools/
│   └── hestia-keychain-cli/     # Swift CLI for Secure Enclave
├── scripts/                     # Deployment scripts
│   ├── deploy-to-mini.sh        # Rsync + setup on Mac Mini
│   ├── initial-push.sh          # First-time Git push + deploy
│   ├── pre-deploy-check.sh      # Safety checks before deploy
│   └── sync-swift-tools.sh      # Build and deploy Swift tools
├── data/                        # Data storage (git-ignored)
├── logs/                        # Log files (git-ignored)
├── docs/                        # Project documentation
└── tests/                       # Test suite
```

## Quick Start

### Development (MacBook)

```bash
# Clone and setup
cd ~/hestia
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Verify installation
python -c "import hestia; print(hestia.__version__)"
```

### Deployment to Mac Mini

```bash
# First-time deployment
./scripts/initial-push.sh

# Subsequent deployments
./scripts/deploy-to-mini.sh

# Deploy Swift tools
./scripts/sync-swift-tools.sh
```

See [docs/deployment.md](docs/deployment.md) for detailed instructions.

## Requirements

- Python 3.9+ (3.11 recommended)
- macOS (Apple Silicon for production)
- Ollama with Mixtral 8x7B model
- Tailscale (for remote access)

## Architecture

- **Model**: Mixtral 8x7B (Q4_K_M) via Ollama, 32K context
- **Backend**: Python 3.11+, FastAPI
- **Storage**: ChromaDB (vectors) + SQLite (structured) + macOS Keychain (credentials)
- **Security**: Secure Enclave, biometric auth, defense-in-depth

## Three Modes

| Invoke | Name | Focus |
|--------|------|-------|
| `@Tia` | Hestia | Default: daily ops, quick queries |
| `@Mira` | Artemis | Learning: Socratic teaching, research |
| `@Olly` | Apollo | Projects: focused dev, minimal tangents |

## Documentation

- [CLAUDE.md](CLAUDE.md) - Project context for Claude Code
- [docs/deployment.md](docs/deployment.md) - Deployment guide
- [docs/hestia-project-context-enhanced.md](docs/hestia-project-context-enhanced.md) - Quick reference
- [docs/hestia-initiative-enhanced.md](docs/hestia-initiative-enhanced.md) - Full specification
- [docs/hestia-security-architecture.md](docs/hestia-security-architecture.md) - Security design

## Troubleshooting

### Cannot connect to Mac Mini
1. Verify Tailscale is running: `tailscale status`
2. Check Mac Mini is online: `ping hestia-server`
3. Test SSH: `ssh andrew@hestia-server`

### Package import fails
1. Activate venv: `source .venv/bin/activate`
2. Install deps: `pip install -r requirements.txt`
3. Check Python version: `python --version` (need 3.9+)

### Credential access denied
1. Check Keychain Access.app for Hestia entries
2. Verify Touch ID is set up on Mac Mini
3. Review audit logs: `python -m hestia.logging.viewer`

## License

Private - All rights reserved.
