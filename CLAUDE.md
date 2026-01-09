# CLAUDE.md - Hestia Project Context

This file provides Claude with persistent context about the Hestia project.

## What is Hestia?

Hestia is a locally-hosted personal AI assistant running on a Mac Mini M1. Think Jarvis from Iron Man: competent, adaptive, occasionally sardonic, anticipates needs without being emotionally solicitous.

**Key characteristics:**
- Single-agent architecture (one model, three personas)
- Local-first (Mixtral 8x7B via Ollama)
- Pentagon-level security (Secure Enclave, biometric auth, defense-in-depth)
- Native Swift apps for iOS/macOS

## Three Modes

| Invoke | Name | Focus |
|--------|------|-------|
| `@Tia` | Hestia | Default: daily ops, quick queries |
| `@Mira` | Artemis | Learning: Socratic teaching, research |
| `@Olly` | Apollo | Projects: focused dev, minimal tangents |

## Technical Stack

- **Hardware**: Mac Mini M1 (64GB target)
- **Model**: Mixtral 8x7B (Q4_K_M) via Ollama, 32K context
- **Backend**: Python 3.11+, FastAPI
- **Storage**: ChromaDB (vectors) + SQLite (structured) + macOS Keychain (credentials)
- **App**: Native Swift/SwiftUI (iOS + macOS)
- **Remote Access**: Tailscale
- **Development**: Claude Code + Xcode (two tools only)

## Development Phases

```
Phase 0   : Environment Setup ..................... COMPLETE
Phase 0.5 : Security Foundation ................... COMPLETE
Phase 1   : Logging Infrastructure ................ COMPLETE
Phase 2   : Inference Layer ....................... <- NEXT
Phase 3   : Memory Layer
Phase 3.5 : Tag-Based Memory
Phase 4   : Orchestration
Phase 5   : Execution Layer
Phase 5.5 : Apple Ecosystem
Phase 6   : Access Layer + Native App
Phase 7   : Integration & Hardening
Phase 8   : Iteration
```

## Key Architectural Decisions (ADRs)

- **ADR-001**: Mixtral 8x7B as primary model (fits in 64GB)
- **ADR-002**: Governed memory persistence (staged commits, human review)
- **ADR-003**: Single-agent architecture (predictable, debuggable)
- **ADR-004**: Observability over determinism (log everything)
- **ADR-009**: Credential management via macOS Keychain + Secure Enclave
- **ADR-011**: Context window management (32K budget allocation)
- **ADR-012**: Apple ecosystem via native APIs (no OAuth in v1.0)
- **ADR-013**: Tag-based memory schema (semantic + temporal + categorical)

## Security Posture

- Biometric auth (Face ID/Touch ID) for sensitive data
- Three-tier credential partitioning (operational/sensitive/system)
- Double encryption (Fernet + Keychain AES-256)
- External communication gate (nothing sent without approval)
- 7-year audit log retention for credential access

## Code Conventions

- **File naming**: kebab-case (`inference-client.py`)
- **Type hints**: Always use them
- **Logging**: Every significant operation logged with request ID
- **Config**: YAML files, never hardcode

## Andrew's Context

- **Skills**: Strong SQL/APIs, growing Python/infra, learning as we build
- **Time**: ~6 hours/week
- **Style**: 70% teach-as-we-build, 30% just-make-it-work
- **Tools**: Claude Code implements, Xcode reviews

## Effective Prompts

**Good:**
- "Build the memory manager with these specs..."
- "Debug this error: [paste full traceback]"
- "Review this implementation against ADR-009"

**Less effective:**
- "Build Hestia" (too broad)
- "Is this good?" (no context)

## Documentation

- `docs/hestia-project-context-enhanced.md` - Quick reference
- `docs/hestia-initiative-enhanced.md` - Full specification
- `docs/hestia-development-plan.md` - Phase-by-phase guide
- `docs/hestia-security-architecture.md` - Security design
- `docs/hestia-decision-log.md` - All ADRs

---

## Current Project Structure

```
hestia/
├── hestia/                      # Python package
│   ├── __init__.py              # v0.1.0
│   ├── security/
│   │   ├── __init__.py
│   │   └── credential_manager.py   # CredentialManager with Keychain + Fernet
│   ├── logging/
│   │   ├── __init__.py
│   │   ├── structured_logger.py    # HestiaLogger with JSON, sanitization
│   │   ├── audit_logger.py         # AuditLogger (7-year retention)
│   │   └── viewer.py               # CLI log viewer
│   ├── inference/               # Placeholder
│   ├── memory/                  # Placeholder
│   ├── orchestration/           # Placeholder
│   ├── execution/               # Placeholder
│   ├── persona/                 # Placeholder
│   ├── api/                     # Placeholder
│   └── config/                  # Placeholder
├── hestia-cli-tools/
│   └── hestia-keychain-cli/     # Swift CLI for Secure Enclave (built)
├── data/
├── logs/
├── docs/                        # 5 project documents
├── tests/
├── admin/
├── .venv/                       # Python 3.9 virtual environment
├── .gitignore
├── requirements.txt
├── README.md
└── CLAUDE.md
```

---

## Session Log

### 2025-01-08: Project Initialization

**Completed:**
- Phase 0: Created project structure, git repo, venv, requirements.txt
- Phase 0: Installed Ollama, pulled Mixtral 8x7B (28GB, Q4_K_M)
- Phase 0.5: Built `hestia-keychain-cli` Swift CLI
- Phase 0.5: Implemented `CredentialManager` with three-tier partitioning
- Phase 1: Implemented `HestiaLogger` with JSON logging, credential sanitization
- Phase 1: Implemented `AuditLogger` for 7-year credential access logs
- Phase 1: Created log viewer CLI
- Created CLAUDE.md for project context

**Model Verified:**
```
mixtral:8x7b-instruct-v0.1-q4_K_M (28GB)
```

**Next Session:**
1. Phase 2: Build inference layer (`hestia/inference/client.py`)
   - Ollama async client wrapper
   - Token counting with tiktoken
   - Retry logic with exponential backoff
   - Response validation
   - Context window management (32K budget)
2. Test end-to-end: Credential → Logging → Inference

**Open Questions:**
- None currently

**Decisions Made:**
- Used Python `keyring` library for Keychain access (simpler than subprocess)
- Credential sanitization patterns catch API keys, SSN, credit cards, emails
- Audit logs separate from general logs (different retention policies)
