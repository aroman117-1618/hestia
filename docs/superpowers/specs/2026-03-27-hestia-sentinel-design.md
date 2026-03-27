# Hestia Sentinel — Supply Chain Defense Automation

**Date:** 2026-03-27
**Status:** Draft
**Author:** Andrew Lonati + Claude
**Motivation:** litellm PyPI supply chain attack (CVE-2026-33634, March 24 2026) — TeamPCP compromised Trivy → Checkmarx → litellm. Malicious .pth file exfiltrated SSH keys, cloud credentials, API keys, database passwords from any machine that installed litellm 1.82.7/1.82.8.

---

## 1. System Identity & Scope

**Name:** Hestia Sentinel (migrates to Atlas v2 when Atlas matures)

**Mission:** Protect hestia's software supply chain and runtime integrity through layered prevention, detection, and response — using Atlas-compatible interfaces from day one.

### What It Protects

- Mac Mini production environment (trading bots, API server, credentials)
- CI/CD pipeline integrity (GitHub Actions, deploy scripts)
- Dependency supply chain (PyPI packages, transitive deps)

### What It Does NOT Do

- Physical/environmental monitoring (Atlas v1 scope)
- Offensive security (Atlas charter: no offensive capabilities)
- Replace hestia's existing security (credential manager, sandbox, CommGate) — it *watches* those systems, doesn't duplicate them

### Boundary with Atlas

The sentinel is an early instantiation of Atlas v2-v3 capabilities. It uses Atlas's `AtlasEvent` model, append-only store interface, and adapter pattern. When Atlas A1-A7 ships, the sentinel's adapters and event history migrate into Atlas's unified store with zero data loss and minimal code changes.

### Atlas Evolution Path

| Version | Scope | Sentinel Relationship |
|---------|-------|----------------------|
| Atlas v1 (A1-A7) | Physical sensors (Flipper, Lynis, nmap, USB/HID) — passive only | Independent; shared event schema |
| Atlas v2 | Software integrity monitoring | Sentinel adapters migrate into Atlas |
| Atlas v3 | Network intelligence (DNS, egress, process-level) | Sentinel DNS monitor migrates |
| Atlas v4 | Active defense (containment) | Sentinel containment logic migrates |

---

## 2. Prevention Layer (CI/CD + Deploy Time)

No new services — hardening of existing pipeline gates.

### 2a. Hash-Locked Dependencies

- `pip-compile --generate-hashes` replaces current `pip-compile` in the workflow
- `pip install --require-hashes -r requirements.txt` enforced in:
  - `.github/workflows/ci.yml`
  - `scripts/deploy-to-mini.sh`
  - `scripts/deploy-local.sh`
- Local dev (MacBook) remains unrestricted — hashes enforced only on Mini and CI
- A tampered package on PyPI is rejected at install time because the hash won't match
- Updated compile command:
  ```bash
  uv pip compile requirements.in --python-version 3.11 --output-file requirements.txt --no-emit-index-url --generate-hashes
  ```

### 2b. Blocking pip-audit

- Change `pip-audit --strict` in CI from non-blocking (`|| true`) to blocking (fails the pipeline)
- Add the same check to `deploy-to-mini.sh` — no deploy with known CVEs
- Escape hatch: `.pip-audit-known.json` for specific CVEs that have been reviewed and accepted, with documented rationale
- Format:
  ```json
  [
    {"id": "PYSEC-2026-XXXX", "reason": "Not exploitable in our usage — no user-supplied input to affected function", "reviewed_by": "andrew", "date": "2026-03-27"}
  ]
  ```

### 2c. Post-Install .pth Scan

- New step in `deploy-to-mini.sh` after `pip install` but before server restart
- Scans `.venv/lib/*/site-packages/*.pth` against a known-good allowlist
- Allowlist maintained in repo: `config/known-pth-files.txt`
- Current known-good .pth files:
  ```
  __editable__.hestia_cli-0.1.0.pth
  distutils-precedence.pth
  coloredlogs.pth
  ```
- Unknown .pth file → deploy aborts, CRITICAL alert, server stays on previous version
- Script: `scripts/scan-pth-files.sh` (reusable by CI and deploy)

### Prevention Layer Impact

This layer alone would have stopped the litellm attack. The hash mismatch would have rejected the tampered package at install. The .pth scan is defense-in-depth for attacks that bypass pip (e.g., direct file writes).

---

## 3. Detection Layer (Runtime Sentinel Daemon)

New `com.hestia.sentinel.plist` service. Lightweight Python process, independent of the hestia API server.

### 3a. File Integrity Monitor

- **Baseline:** On deploy, snapshots `.venv/lib/*/site-packages/` — SHA-256 hashes for all `.pth` files and a package manifest (name + version + hash)
- **Poll interval:** Every 5 minutes
- **Detections:**
  - New/modified `.pth` file → **CRITICAL** — kill any Python process that loaded it, push notification
  - New package not in baseline → **WARNING** — push notification
- **Baseline refresh:** Automatic after successful deploys via hook in `deploy-to-mini.sh`
- **Manual refresh:** `scripts/sentinel-baseline.sh`

### 3b. Credential Access Monitor

- **Watched paths:**
  - `~/.ssh/` (SSH keys)
  - `~/.hestia/coinbase-credentials` (trading keys)
  - `~/hestia/.env` (API keys)
  - `~/hestia/data/.cloud_api_key_*.enc` (encrypted cloud keys)
- **Poll interval:** Every 30 seconds via `lsof`
- **Process allowlist** (`config/sentinel-process-allowlist.json`):
  - `ssh-agent`, `sshd`
  - `bot_service.py` (for `~/.hestia/coinbase-credentials` only)
  - `hestia.api.server` (for `.env` and `.cloud_api_key_*.enc` only)
- **Detection:** Non-allowlisted process reading credential files → **CRITICAL** — kill the process, push notification
- **Why lsof, not macOS Endpoint Security:** ES requires a system extension with Apple approval + notarization. Overkill for single-user. lsof at 30s catches any persistent exfiltration (the threat model — malware that reads and sends, not a one-shot read).

### 3c. DNS Query Monitor

- **Source:** macOS unified log (`log stream --predicate 'subsystem == "com.apple.networkd"'`)
- **Domain allowlist** (`config/sentinel-dns-allowlist.json`):
  ```json
  {
    "domains": [
      "api.coinbase.com",
      "api.alpaca.markets",
      "*.tailscale.com",
      "api.anthropic.com",
      "api.openai.com",
      "generativelanguage.googleapis.com",
      "github.com",
      "*.githubusercontent.com",
      "pypi.org",
      "files.pythonhosted.org",
      "localhost"
    ]
  }
  ```
- **Detections:**
  - Single unknown domain → **WARNING** — logged + push notification
  - 3+ unknown domains in 60 seconds → **CRITICAL** — likely active exfiltration, urgent push notification
- **No blocking at this stage.** DNS-only monitoring per design decision. Process-level network tracking (mapping PID → destination IP/port) is the fast-follow for a future iteration.

### 3d. Service Architecture

- **Entrypoint:** `python -m hestia.sentinel.service`
- **launchd:** `com.hestia.sentinel.plist` (RunAtLoad, KeepAlive)
- **Database:** `~/hestia/data/sentinel_events.db` (append-only, Atlas-compatible schema)
- **Dependencies:** stdlib only — zero pip packages. This is deliberate: a supply chain defense tool that can itself be supply-chain attacked through its own dependencies would be self-defeating.
- **Isolation:** Does NOT import from `hestia.*`. Fully decoupled from the main backend. Shares notification infra via direct HTTP calls (ntfy.sh, APNs), not hestia code.
- **Implication:** If hestia is compromised, the sentinel still functions.

---

## 4. Response Layer (Alerting + Containment)

### 4a. Tiered Response Matrix

| Trigger | Severity | Automated Action | Alert Channel |
|---------|----------|-----------------|---------------|
| Unknown .pth file in site-packages | CRITICAL | Kill Python processes that loaded it, abort deploy | APNs push + ntfy.sh |
| Credential file accessed by unknown process | CRITICAL | Kill the accessing process | APNs push + ntfy.sh |
| 3+ unknown DNS domains in 60s | CRITICAL | Log all details for forensics | APNs push + ntfy.sh |
| Deploy hash mismatch | CRITICAL | Abort deploy, keep previous version running | APNs push + ntfy.sh |
| pip-audit finds new CVE | WARNING | Block deploy (CI gate) | APNs push |
| Single unknown DNS domain | WARNING | Log for review | APNs push |
| New package not in baseline | WARNING | Log for review | APNs push |
| Routine scan passed | INFO | None | Sentinel log + System Status |
| Baseline refreshed after deploy | INFO | None | Sentinel log + System Status |

### 4b. Containment Philosophy

Auto-containment fires only on **high-confidence, unambiguous threats**:
- Unknown `.pth` file → near-zero false positive rate
- Rogue process touching credential files → near-zero false positive rate

The sentinel **never** auto-kills `bot_service.py` or `hestia.api.server` — those are on the process allowlist. Worst case for a false positive: a push notification about a process you recognize and dismiss.

For WARNING-level signals (unknown DNS, new CVE), the sentinel alerts but does not act. User decides.

### 4c. Kill Switch

- **Config:** `config/sentinel.json` → `"containment_enabled": true`
- When `false`: sentinel still monitors and alerts but takes no automated action (detect-only mode)
- **Self-protection:** If the sentinel crashes 3 times in 5 minutes, it stays down and sends one final "sentinel is offline" notification rather than restart-looping

### 4d. Notification Integration

- **APNs push:** Direct HTTP POST to Apple's push notification service using device push tokens read from `~/hestia/data/hestia.db` (read-only access to `device_push_tokens` table — no hestia code imported)
- **ntfy.sh:** HTTP POST to `HESTIA_NTFY_TOPIC` env var (same pattern as watchdog)
- **System Status API:** Sentinel writes to `sentinel_events.db`. Hestia API server exposes read-only `/v1/sentinel/status` endpoint querying this DB. iOS/macOS System Status cards pull from this endpoint — no new UI architecture, just a new data source for existing cards.

---

## 5. Atlas-Compatible Data Model

### 5a. Event Schema

```python
@dataclass
class SentinelEvent:
    id: str                    # UUID
    timestamp: str             # ISO 8601
    source: str                # "sentinel.file_integrity" | "sentinel.credential_monitor" | "sentinel.dns_monitor" | "sentinel.deploy_gate"
    severity: str              # "CRITICAL" | "WARNING" | "INFO"
    event_type: str            # "pth_file_detected" | "credential_access" | "unknown_dns" | "hash_mismatch" | "scan_passed" | etc.
    summary: str               # Human-readable one-liner
    details: dict              # Structured payload (file path, process name, domain, etc.)
    action_taken: str | None   # "process_killed" | "deploy_aborted" | None
    acknowledged: bool         # User has reviewed this event (for UI dismissal)
```

Maps 1:1 to Atlas's `AtlasEvent` model — same fields, same types. When Atlas v2 absorbs the sentinel, events migrate with a straight table copy.

### 5b. Store Interface

- Append-only SQLite (`sentinel_events.db`)
- INSERT only. No UPDATE (except `acknowledged` flag), no DELETE. Enforced by SQLite trigger.
- Exception: `acknowledged` field can be set to `true` via the System Status API (user dismisses alert in app)
- Retention: 90 days, then archived to compressed file (aligned with hestia's log compressor schedule)

### 5c. Adapter Pattern

Each monitor is an adapter following Atlas's convention:

```
sentinel/
├── service.py              # Main daemon loop, scheduler
├── adapters/
│   ├── base.py             # BaseAdapter (poll interval, event emit)
│   ├── file_integrity.py   # FileIntegrityAdapter
│   ├── credential_watch.py # CredentialWatchAdapter
│   └── dns_monitor.py      # DNSMonitorAdapter
├── store.py                # Append-only event store (Atlas-compatible)
├── alerter.py              # Notification dispatch (APNs + ntfy.sh)
├── config.py               # Allowlists, thresholds, kill switch
└── baseline.py             # Baseline snapshot management
```

Each adapter implements `poll() -> list[SentinelEvent]`. The service loop calls each adapter on its interval, writes events to the store, and dispatches alerts based on severity.

### 5d. Migration Path to Atlas

When Atlas A1-A7 ships:

1. **Adapters:** Move from `hestia/sentinel/adapters/` to `atlas/atlas/adapters/` — rename `BaseAdapter` import
2. **Events:** `sentinel_events.db` rows INSERT into Atlas's unified `atlas_events.db` — same schema
3. **Service:** `com.hestia.sentinel.plist` retires, Atlas's collector process takes over
4. **API:** Hestia's `/v1/sentinel/status` switches to querying Atlas's store (or Atlas exposes its own API)

No data loss, no rewrite.

---

## 6. File Layout & Integration Points

### 6a. New Files

```
hestia/
├── hestia/sentinel/                        # New module (stdlib-only, no hestia imports)
│   ├── __init__.py
│   ├── service.py                          # Daemon entrypoint
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── file_integrity.py
│   │   ├── credential_watch.py
│   │   └── dns_monitor.py
│   ├── store.py
│   ├── alerter.py
│   ├── config.py
│   └── baseline.py
├── config/
│   ├── sentinel.json                       # Master config
│   ├── sentinel-dns-allowlist.json         # Approved domains
│   ├── sentinel-process-allowlist.json     # Approved credential-accessing processes
│   └── known-pth-files.txt                 # Approved .pth files
├── scripts/
│   ├── launchd/com.hestia.sentinel.plist   # New launchd service
│   ├── scan-pth-files.sh                   # Reusable .pth scanner (CI + deploy)
│   └── sentinel-baseline.sh                # Manual baseline refresh
├── tests/test_sentinel/                    # Unit + integration tests
│   ├── test_file_integrity.py
│   ├── test_credential_watch.py
│   ├── test_dns_monitor.py
│   ├── test_store.py
│   └── test_alerter.py
└── .pip-audit-known.json                   # Reviewed/accepted CVEs
```

### 6b. Modified Existing Files

| File | Change |
|------|--------|
| `requirements.in` | Update compile command comment to include `--generate-hashes` |
| `requirements.txt` | Regenerated with hashes |
| `.github/workflows/ci.yml` | `pip install --require-hashes`, blocking `pip-audit`, .pth scan step |
| `scripts/deploy-to-mini.sh` | `--require-hashes`, .pth scan, baseline refresh hook, blocking `pip-audit` |
| `scripts/deploy-local.sh` | Same deploy hardening |
| `hestia/api/routes/system.py` (or new) | New `/v1/sentinel/status` read-only endpoint |
| iOS/macOS System Status views | Add sentinel event data source |

### 6c. Dependency Discipline

Sentinel has **zero pip dependencies**. Everything is Python stdlib:

| Need | stdlib Module |
|------|--------------|
| Event store | `sqlite3` |
| Process inspection | `subprocess` (lsof, log stream) |
| File hashing | `hashlib` |
| Event serialization | `json` |
| HTTP notifications | `urllib.request` |
| File operations | `pathlib`, `os` |
| Config parsing | `yaml` — **exception**: PyYAML is already in hestia's venv, OR use `json` config files instead to maintain true zero-dependency |

**Decision:** JSON config files to maintain true zero-dependency. The sentinel must be able to run from a bare Python install. Readability tradeoff is minimal for config files this small.

### 6d. Testing Strategy

- Unit tests in `tests/test_sentinel/` following hestia's existing patterns
- Each adapter testable in isolation with fixture data:
  - Mock `lsof` output for credential monitor
  - Mock DNS log lines for DNS monitor
  - Mock site-packages directory for file integrity
- Integration test: deploy script runs .pth scan + hash verification against a test venv
- No test dependency on the hestia server running
- Added to `scripts/auto-test.sh` mapping for automatic test execution on sentinel file changes

---

## 7. Success Criteria

The sentinel is complete when:

1. **Prevention:** A `pip install` with a hash mismatch fails in CI and on the Mini
2. **Prevention:** A known CVE blocks deployment until reviewed
3. **Prevention:** An unexpected `.pth` file aborts a deploy
4. **Detection:** The sentinel daemon runs independently of the hestia server
5. **Detection:** File integrity changes are detected within 5 minutes
6. **Detection:** Credential access by unexpected processes is detected within 30 seconds
7. **Detection:** Unknown DNS queries generate alerts
8. **Response:** CRITICAL events trigger push notifications within 60 seconds
9. **Response:** Auto-containment kills rogue processes on CRITICAL triggers
10. **Response:** Kill switch degrades to detect-only mode without restart
11. **Integration:** System Status cards in iOS/macOS show sentinel events
12. **Atlas:** Event schema is 1:1 compatible with AtlasEvent model
13. **Isolation:** Sentinel has zero imports from `hestia.*` and zero pip dependencies

---

## 8. What This Does NOT Cover (Future Work)

- **Process-level network tracking** (PID → destination IP mapping) — fast-follow after DNS monitoring proves stable
- **Egress firewall rules** (pf) — requires careful allowlist tuning with live trading bots
- **Dedicated service user** for trading bots — reduces blast radius but requires credential migration
- **macOS Keychain migration** for all secrets (move .env contents into Keychain) — separate hardening effort
- **Atlas v1 integration** — deferred until Atlas A1-A7 ships
