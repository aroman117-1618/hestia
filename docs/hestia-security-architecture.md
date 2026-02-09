# Hestia Security Architecture

**Last Updated**: 2026-02-27
**Previous version**: `docs/archive/hestia-security-architecture-2025-01.md`

---

## Overview

Hestia is a single-user, locally-hosted AI assistant running on a Mac Mini M1. Security is defense-in-depth: biometric authentication, encrypted credential storage, sandboxed execution, JWT device auth, and error sanitization at every layer.

**Posture**: Zero-trust for external interfaces, trust-but-verify for internal layers.

---

## 1. Credential Management

**Implementation**: `hestia/security/credential_manager.py` (CredentialManager)

### Three-Tier Keychain Partitioning

| Partition | Keychain Service | Contents | Access Control |
|-----------|-----------------|----------|----------------|
| **Operational** | `hestia.operational` | API keys (Weather, cloud LLM providers) | Optional biometric |
| **Sensitive** | `hestia.sensitive` | JWT secret, user data | Requires biometric |
| **System** | `hestia.system` | Master encryption key | System-level access |

### Double Encryption

All credentials are double-encrypted:
1. **Fernet encryption** (AES-128-CBC with HMAC-SHA256) using a master key
2. **Keychain AES-256** via macOS Keychain Services (hardware-backed on Apple Silicon)

Master key is generated via `Fernet.generate_key()` on first run and stored in the system Keychain partition. Audit trail logged for every credential access.

### Cloud LLM API Keys

**Implementation**: `hestia/cloud/manager.py`

- API keys stored via `store_operational()` in the operational Keychain partition
- Validated on input: minimum 10 characters, stripped of whitespace
- Never returned in API responses (all provider endpoints redact keys)
- Fallback: in-memory storage if Keychain unavailable (logged as warning)

---

## 2. Authentication

**Implementation**: `hestia/api/middleware/auth.py`

### Device-Based JWT

| Property | Value |
|----------|-------|
| Algorithm | HS256 |
| Token expiry | 90 days |
| Secret key storage | Keychain (sensitive partition) or env `HESTIA_JWT_SECRET` |
| Token format | `{"device_id": str, "exp": datetime, "iat": datetime}` |

### Flow

1. Device registers via `POST /v1/auth/register` (public endpoint)
2. Server creates JWT token, stores device info, returns token
3. Client sends `Authorization: Bearer <token>` on all subsequent requests
4. Token refresh via `POST /v1/auth/refresh`
5. On iOS: token stored in iOS Keychain, auto-reregistration on 401

### Public vs Protected Routes

| Route | Auth Required | Notes |
|-------|--------------|-------|
| `GET /v1/ping` | No | Health check — returns `{"status": "ok"}` |
| `POST /v1/auth/register` | No | Device registration |
| `POST /v1/auth/refresh` | No | Token refresh |
| All other 69 endpoints | Yes | JWT required via `Depends(get_current_device)` |

---

## 3. Execution Sandbox

**Implementation**: `hestia/execution/tools/file_tools.py`, `hestia/config/execution.yaml`

### File System Access Control

Sandbox uses path allowlists (source of truth: `execution.yaml`).

**Read-allowed paths**:
- `~/hestia/data`, `~/hestia/logs`
- `~/Documents`, `~/Desktop`
- `~/Library/Mobile Documents/com~apple~CloudDocs` (iCloud Drive)
- `~/Library/Mobile Documents` (app containers)
- `/tmp/hestia`

**Write-allowed paths**: Same except `~/Documents` excluded from writes.

**Auto-approved writes**: Only `~/hestia/data` — all other writes require explicit approval.

### Path Validation

- All paths resolved to absolute before checking against allowlist
- Symlink traversal prevented: `search_files` validates each rglob result against sandbox
- Hidden files (`.icloud`, `.DS_Store`) filtered by default in list/search
- `_validate_path()` checks every file operation against the allowlist

### Tool Execution

- `ToolExecutor` runs tools with subprocess isolation
- Blocked commands configured in `execution.yaml` (rm -rf, etc.)
- Communication gate: nothing leaves the system without approval

---

## 4. Error Sanitization

**Implementation**: `hestia/api/errors.py`

### Pattern

All error handling follows two rules:

1. **Log messages**: Use `sanitize_for_log(e)` (returns `type(e).__name__` only) in API route log statements, or `type(e).__name__` directly in non-API layers (avoids upward import from API to inference/cloud)
2. **HTTP responses**: Generic error messages via `safe_error_detail()` — never `detail=str(e)`

This prevents internal details (stack traces, file paths, credentials) from leaking to clients or structured logs.

### Enforcement

- `scripts/validate-security-edit.sh` hook runs on every Edit/Write to security-relevant files
- Checks for: hardcoded credentials, wildcard CORS, bare `except:` clauses
- Warns but does not block (developer override allowed)

---

## 5. HealthKit Data Privacy

**Implementation**: `hestia/health/manager.py`, `hestia/api/routes/health_data.py`

- Health data stays on-device (iOS HealthKit) until user explicitly triggers a sync
- Sync pushes metric data to local server via `POST /v1/health_data/sync`
- Server stores metrics in SQLite with deduplication (UNIQUE constraint)
- No cloud transmission of health data — all processing is local
- Coaching preferences are user-configurable (focus areas, tone, goals)
- 28 metric types across 7 categories (activity, body, heart, sleep, nutrition, mindfulness, reproductive)

---

## 6. Cloud LLM Security

**Implementation**: `hestia/inference/client.py`, `hestia/cloud/manager.py`

### Data Flow

- 3-state routing: `disabled` (default) / `enabled_smart` / `enabled_full`
- When disabled: zero data leaves the Mac Mini
- When enabled: only chat messages and system prompts sent to cloud providers
- No health data, credentials, or file contents sent to cloud providers
- Cloud state resets to `disabled` on server restart (defense against misconfiguration)

### Provider Security

- API keys validated, stored in Keychain, never returned in API responses
- Per-provider health checks verify connectivity
- Usage tracking: token counts and costs logged per request

---

## 7. Network Security

### TLS

- Server runs HTTPS on port 8443 with self-signed certificate
- `HESTIA_CA_CERT` environment variable for proper TLS verification
- Remote access via Tailscale (WireGuard-based VPN, `hestia-3.local`)

### Rate Limiting

Configured per endpoint group (middleware-enforced).

---

## 8. Logging & Audit

**Implementation**: `hestia/logging/structured_logger.py`, `hestia/logging/audit.py`

### Structured Logging

- `HestiaLogger` with 12 LogComponents: ACCESS, ORCHESTRATION, MEMORY, INFERENCE, EXECUTION, SECURITY, API, SYSTEM, VOICE, CLOUD, COUNCIL, HEALTH
- Request IDs propagated through all log entries
- Event types: INFO, WARNING, ERROR, AUDIT

### Audit Trail

- `AuditLogger` tracks all credential access events
- Logged: event type, timestamp, credential key (not value), action, outcome
- All sensitive operations (key generation, retrieval, deletion) audited

---

## 9. iOS Client Security

- Biometric authentication (Face ID / Touch ID) required to unlock app
- JWT token stored in iOS Keychain (not UserDefaults)
- Auto-reregistration on 401 (token expired)
- Certificate pinning via `HESTIA_CA_CERT` when available
- HealthKit requires explicit user permission grants per metric type

---

## Architecture Diagram

```
[iOS App] ──HTTPS/TLS──▶ [FastAPI :8443]
    │                          │
    │ Face ID                  ├── JWT Auth Middleware
    │ Keychain                 ├── Rate Limiting
    │ HealthKit                ├── Error Sanitization
    │                          │
    │                     [Route Handlers]
    │                          │
    │            ┌─────────────┼─────────────┐
    │            ▼             ▼             ▼
    │      [Inference]    [Memory]     [Execution]
    │        │    │          │             │
    │   [Ollama] [Cloud]  [ChromaDB]  [Sandbox]
    │            │        [SQLite]    [Gate]
    │            │
    │       [Keychain]     ◀── API keys, JWT secret, master key
    │       [Fernet]       ◀── Double encryption layer
    │
    └── [HealthKit] (on-device, user-controlled sync)
```

---

## Key ADRs

| ADR | Decision |
|-----|----------|
| ADR-006 | File-based sandboxing with path allowlists (superseded Docker approach) |
| ADR-009 | Keychain + Secure Enclave, 3-tier credential partitioning |
| ADR-025 | Cloud LLM: API keys in Keychain, never returned, 3-state routing |
| ADR-029 | HealthKit: on-device storage, user-controlled sync, no cloud transmission |
