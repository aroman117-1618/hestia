# Hestia Sentinel — Supply Chain Defense Automation

**Date:** 2026-03-27
**Status:** Approved (with conditions)
**Author:** Andrew Lonati + Claude
**Reviewed by:** Claude Opus 4.6 (internal audit) + Gemini 2.5 Pro (cross-model) + @hestia-critic (adversarial)
**Verdict:** APPROVE WITH CONDITIONS — see Section 9 for audit summary
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

## 2. Layer 0: Hardened Execution Environment

**This layer deploys FIRST.** Architectural prevention is more effective than reactive detection. A dedicated service user that can't read `~/.ssh/` makes credential monitoring moot — the malware simply has no access. A default-deny egress firewall makes DNS monitoring moot — unknown destinations are blocked at the kernel level.

### 2a. Dedicated Service User

- Create a non-privileged `_hestia` user on the Mac Mini (no login shell, no home directory GUI access)
- `com.hestia.server.plist` and `com.hestia.trading-bots.plist` run as `_hestia`
- `_hestia` has read access ONLY to:
  - `~/hestia/` (application code, read-only)
  - `~/hestia/data/` (runtime storage, read-write)
  - `~/hestia/logs/` (log output, read-write)
  - `~/.hestia/coinbase-credentials` (trading keys, read-only)
  - `~/hestia/data/.cloud_api_key_*.enc` (encrypted cloud keys, read-only)
- `_hestia` has NO access to:
  - `~/.ssh/` (SSH keys)
  - `~/hestia/.env` (move contents to Keychain — see 2c)
  - Any other user home directory contents
- Application code (`hestia/` Python source, `.venv/`) owned by `andrewroman117`, read-only to `_hestia`
- Sentinel code and config owned by `andrewroman117` (or root), not writable by `_hestia`

### 2b. Application-Level Egress Firewall

- Install **LuLu** (open-source, per-process egress firewall) or configure **pf** rules
- Default policy: **deny all outbound** for the `_hestia` user / Python interpreter
- Explicit allowlist (per-process where possible):
  - `bot_service.py` → `api.coinbase.com:443`, `api.alpaca.markets:443`
  - `hestia.api.server` → `api.anthropic.com:443`, `api.openai.com:443`, `generativelanguage.googleapis.com:443`, `api.push.apple.com:443`
  - All hestia processes → `localhost:11434` (Ollama), `*.tailscale.com` (remote access)
  - pip/deploy → `pypi.org:443`, `files.pythonhosted.org:443`, `github.com:443`
- Any connection to a non-allowed destination is **blocked and logged**
- This solves DNS bypass, DNS-over-HTTPS, and direct-IP exfiltration in one move
- LuLu preferred over pf for initial setup: GUI for allowlist management, per-process rules, easier to iterate

### 2c. Credential Hardening

- Migrate `.env` contents (Anthropic API key) into macOS Keychain operational partition
- Remove `.env` file from the Mini after migration (currently contains a plaintext API key)
- `~/.hestia/coinbase-credentials` remains as file (needed for headless launchd restarts) but permissions tightened: `chmod 400`, owned by `andrewroman117`, readable by `_hestia` via group membership
- Sentinel config files (`config/sentinel*.json`, `config/known-pth-files.txt`) owned by `andrewroman117`, read-only to `_hestia` — attacker running as `_hestia` cannot modify allowlists or kill switch

### 2d. Layer 0 Impact

With this layer in place, the litellm attack's exfiltration payload would fail on multiple fronts:
- Can't read `~/.ssh/` (no permission)
- Can't read `.env` (file doesn't exist, content in Keychain)
- Can't exfiltrate to C2 server (egress blocked by default-deny firewall)
- The sentinel's detection layer becomes an **audit trail and early warning system**, not the primary line of defense

---

## 3. Layer 1: Prevention (CI/CD + Deploy Time)

No new services — hardening of existing pipeline gates.

### 3a. Hash-Locked Dependencies

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

### 3b. Blocking pip-audit

- Change `pip-audit --strict` in CI from non-blocking (`|| true`) to blocking (fails the pipeline)
- Add the same check to `deploy-to-mini.sh` — no deploy with known CVEs
- Escape hatch: `.pip-audit-known.json` for specific CVEs that have been reviewed and accepted, with documented rationale
- Format:
  ```json
  [
    {"id": "PYSEC-2026-XXXX", "reason": "Not exploitable in our usage — no user-supplied input to affected function", "reviewed_by": "andrew", "date": "2026-03-27"}
  ]
  ```

### 3c. Post-Install .pth Scan

- New step in `deploy-to-mini.sh` after `pip install` but before baseline refresh or server restart
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

### 3d. Deploy Ordering Invariant

The deploy script MUST execute in this exact order — no parallelism, no reordering:

```
pip install --require-hashes → .pth scan → PASS? → pip-audit → PASS? → baseline refresh → server restart
```

This prevents the baseline refresh race condition (a malicious .pth file being blessed into the baseline before the scan catches it).

### Prevention Layer Impact

This layer alone would have stopped the litellm attack. The hash mismatch would have rejected the tampered package at install. The .pth scan is defense-in-depth for attacks that bypass pip (e.g., direct file writes).

---

## 4. Layer 2: Detection (Runtime Sentinel Daemon)

New `com.hestia.sentinel.plist` service. Lightweight Python process, independent of the hestia API server. With Layer 0 in place, this layer serves as an **audit trail and early warning system** — not the primary defense.

### 4a. Runtime Isolation (CRITICAL)

The sentinel MUST NOT run from the hestia venv. An attacker who can write .pth files or modify site-packages can patch `hashlib`, `subprocess`, or `urllib.request` at import time, blinding the sentinel.

- **Entrypoint:** `/usr/bin/python3 -m hestia.sentinel.service` (system Python)
- **Alternative:** A dedicated minimal venv at `/opt/hestia-sentinel/.venv/` with zero pip packages (just sentinel code on `PYTHONPATH`)
- The sentinel code lives in the hestia repo but is deployed to a location the `_hestia` user cannot write to
- Sentinel config files owned by `andrewroman117`, read-only to `_hestia`

### 4b. Self-Integrity Check

On startup and every 5 minutes, the sentinel hashes its own `.py` files and config files against a known-good manifest. If any file has changed outside of a deploy:
- **CRITICAL** alert — sentinel code or config has been tampered with
- Sentinel halts (cannot trust its own integrity)

### 4c. File Integrity Monitor

- **Baseline:** On deploy, snapshots `.venv/lib/*/site-packages/` — SHA-256 hashes for all `.pth` files and a package manifest (name + version + hash)
- **Poll interval:** Every 5 minutes
- **Detections:**
  - New/modified `.pth` file → **CRITICAL** — push notification, log for forensics
  - New package not in baseline → **MEDIUM** — daily digest
- **Baseline refresh:** Automatic after successful deploys (AFTER .pth scan passes) via hook in `deploy-to-mini.sh`
- **Manual refresh:** `scripts/sentinel-baseline.sh`

### 4d. Credential Access Monitor

- **Watched paths:**
  - `~/.hestia/coinbase-credentials` (trading keys)
  - `~/hestia/data/.cloud_api_key_*.enc` (encrypted cloud keys)
  - (Note: `~/.ssh/` no longer needed — `_hestia` user has no access)
  - (Note: `~/hestia/.env` no longer exists — migrated to Keychain)
- **Primary mechanism:** Investigate DTrace or OpenBSM audit for event-driven file access monitoring
  - DTrace: `dtrace -n 'syscall::open*:entry /execname == "python3"/ { printf("%s %s", execname, copyinstr(arg0)); }'` — real-time, no polling gap
  - OpenBSM: `auditctl -w /path/to/credentials -p r` — SIP-compatible, works on all macOS versions
  - If neither is feasible (SIP restrictions): fall back to `lsof` polling at 30s with honest documentation that it only catches persistent access patterns
- **Process allowlist** (`config/sentinel-process-allowlist.json`):
  - `bot_service.py` (for `~/.hestia/coinbase-credentials` only)
  - `hestia.api.server` (for `.cloud_api_key_*.enc` only)
- **Detection:** Non-allowlisted process accessing credential files → **CRITICAL** — push notification
- **Containment:** With Layer 0's dedicated user, auto-kill is less necessary. Default: alert-only. Auto-kill available behind `containment_enabled` flag for high-confidence signals only.

### 4e. DNS Query Monitor (Supplementary)

With the egress firewall in place, DNS monitoring is a **supplementary audit trail**, not a primary defense. Unknown destinations are already blocked at the network level.

- **Source:** macOS unified log (`log stream --predicate 'subsystem == "com.apple.mDNSResponder"'`) — better DNS visibility than `com.apple.networkd`
- **Domain allowlist** (`config/sentinel-dns-allowlist.json`) — built during 7-day learning period, not manually curated
- **Detections:**
  - Unknown domain → **LOW** — logged to sentinel DB, included in daily digest
  - Burst of unknown domains (3+ in 60s) → **HIGH** — push notification (likely indicates misconfiguration or compromise)
- **Known limitations (documented honestly):**
  - Bypassed by direct IP connections (mitigated by egress firewall)
  - Bypassed by DNS-over-HTTPS (mitigated by egress firewall)
  - Bypassed by exfiltration through allowed domains (mitigated by egress firewall)
  - DNS monitoring is useful for forensics and detecting misconfigurations, not as a primary exfiltration defense

### 4f. Service Architecture

- **Entrypoint:** `/usr/bin/python3` with sentinel code on `PYTHONPATH` (NOT the hestia venv)
- **launchd:** `com.hestia.sentinel.plist` (RunAtLoad, KeepAlive, runs as `andrewroman117` — NOT `_hestia`)
- **Database:** `~/hestia/data/sentinel_events.db` (append-only, Atlas-compatible schema)
- **Dependencies:** stdlib only — zero pip packages
- **Isolation:** Does NOT import from `hestia.*`. Fully decoupled from the main backend. Shares notification infra via direct HTTP calls (ntfy.sh, APNs), not hestia code.
- **Subprocess calls:** Use absolute paths — `/usr/sbin/lsof`, `/usr/bin/log`, `/usr/sbin/dtrace`
- **Heartbeat:** Pings healthchecks.io dead man's switch every 5 minutes. If the sentinel goes silent, external service alerts you (watches the watchdog).
- **Implication:** If hestia is compromised, the sentinel still functions — it runs from a different Python, as a different user, with its code in a read-only location.

---

## 5. Layer 3: Response (Alerting + Containment)

### 5a. Tiered Response Matrix

Severity levels aligned with Atlas vocabulary (LOW/MEDIUM/HIGH/CRITICAL):

| Trigger | Severity | Automated Action | Alert Channel |
|---------|----------|-----------------|---------------|
| Unknown .pth file in site-packages | CRITICAL | Abort deploy (prevention), alert (runtime) | Real-time push + ntfy.sh |
| Sentinel code/config tampered | CRITICAL | Sentinel halts | Real-time push + ntfy.sh |
| Credential file accessed by unknown process | CRITICAL | Alert (auto-kill behind flag) | Real-time push + ntfy.sh |
| Deploy hash mismatch | CRITICAL | Abort deploy, keep previous version | Real-time push + ntfy.sh |
| Egress firewall block (from LuLu/pf logs) | HIGH | Already blocked by firewall | Real-time push |
| Burst of unknown DNS domains (3+ in 60s) | HIGH | Log for forensics | Real-time push |
| pip-audit finds new CVE | HIGH | Block deploy (CI gate) | Real-time push |
| New package not in baseline | MEDIUM | Log for review | Daily digest |
| Single unknown DNS domain | LOW | Log for review | Daily digest |
| Routine scan passed | LOW | None | Sentinel log + System Status |
| Baseline refreshed after deploy | LOW | None | Sentinel log + System Status |

### 5b. Alert Batching & Anti-Fatigue

- **Real-time push:** CRITICAL and HIGH events only
- **Daily digest:** MEDIUM and LOW events aggregated into a single push notification at 8:00 AM — summary of overnight activity
- **Deduplication:** Identical events within a 1-hour window consolidated into a single entry with a count
- **Learning period:** First 7 days after deployment in **observe-only mode**:
  - All monitors active, all events logged
  - Zero push notifications (except CRITICAL)
  - DNS allowlist auto-populated from observed traffic
  - Process allowlist validated against actual access patterns
  - After 7 days: review generated allowlists, then switch to enforcement mode

### 5c. Containment Philosophy

With Layer 0 in place, auto-containment is less critical. The egress firewall already blocks exfiltration. Auto-kill is available but gated:

- **Default:** Alert-only for all detections (containment_enabled: false)
- **Opt-in containment:** When enabled, auto-kill fires ONLY on:
  - Non-allowlisted process with open FD on credential file (if using lsof/DTrace)
- The sentinel **never** auto-kills `bot_service.py` or `hestia.api.server`
- **Financial safety guard:** No auto-kill actions during active trading hours unless the signal is unambiguous (e.g., process name not in allowlist AND process is not a child of any allowlisted service)

### 5d. Kill Switch

- **Config:** `config/sentinel.json` → `"containment_enabled": false` (default)
- When `false`: sentinel monitors and alerts but takes no automated containment action
- Config file integrity protected by sentinel self-check (4b) — tampering triggers CRITICAL alert
- **Self-protection:** If the sentinel crashes 3 times in 5 minutes, it stays down and sends one final "sentinel is offline" notification + healthchecks.io goes red

### 5e. Notification Integration

- **APNs push:** Direct HTTP/2 POST to Apple's push notification service using device push tokens read from `~/hestia/data/user.db` → `push_tokens` table (read-only access, no hestia code imported). JWT auth using APNs credentials from Keychain.
- **ntfy.sh:** HTTP POST to `HESTIA_NTFY_TOPIC` env var (same pattern as watchdog: Title, Priority, Tags headers)
- **Healthchecks.io:** Sentinel pings every 5 minutes (dead man's switch for the sentinel itself)
- **System Status API:** Sentinel writes to `sentinel_events.db`. Hestia API server exposes read-only `/v1/sentinel/status` endpoint querying this DB. iOS/macOS System Status cards pull from this endpoint — no new UI architecture, just a new data source for existing cards.

---

## 6. Atlas-Compatible Data Model

### 6a. Event Schema

Severity levels aligned with Atlas vocabulary:

```python
@dataclass
class SentinelEvent:
    id: str                    # UUID
    timestamp: str             # ISO 8601
    source: str                # "sentinel.file_integrity" | "sentinel.credential_monitor" | "sentinel.dns_monitor" | "sentinel.deploy_gate" | "sentinel.self_check"
    severity: str              # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" (Atlas vocabulary)
    event_type: str            # "pth_file_detected" | "credential_access" | "unknown_dns" | "hash_mismatch" | "scan_passed" | "config_tampered" | "self_check_failed" | etc.
    summary: str               # Human-readable one-liner
    details: dict              # Structured payload (file path, process name, domain, etc.)
    action_taken: str | None   # "process_killed" | "deploy_aborted" | "sentinel_halted" | None
    acknowledged: bool         # User has reviewed this event (for UI dismissal)
```

Maps to Atlas's `AtlasEvent` model. When Atlas v2 absorbs the sentinel, events migrate with a straight table copy.

### 6b. Store Interface

- Append-only SQLite (`sentinel_events.db`)
- INSERT only. No UPDATE (except `acknowledged` flag), no DELETE. Enforced by SQLite trigger.
- Exception: `acknowledged` field can be set to `true` via the System Status API (user dismisses alert in app)
- Retention: 90 days, then archived to compressed file (aligned with hestia's log compressor schedule)

### 6c. Adapter Pattern

Each monitor is an adapter following Atlas's convention:

```
sentinel/
├── service.py              # Main daemon loop, scheduler, heartbeat
├── adapters/
│   ├── base.py             # BaseAdapter (poll interval, event emit)
│   ├── file_integrity.py   # FileIntegrityAdapter
│   ├── credential_watch.py # CredentialWatchAdapter (DTrace/OpenBSM/lsof)
│   └── dns_monitor.py      # DNSMonitorAdapter
├── store.py                # Append-only event store (Atlas-compatible)
├── alerter.py              # Notification dispatch (APNs + ntfy.sh + healthchecks.io)
├── config.py               # Allowlists, thresholds, kill switch, self-integrity
├── baseline.py             # Baseline snapshot management
└── self_check.py           # Self-integrity verification
```

Each adapter implements `poll() -> list[SentinelEvent]`. The service loop calls each adapter on its interval, writes events to the store, and dispatches alerts based on severity and batching rules.

### 6d. Migration Path to Atlas

When Atlas A1-A7 ships:

1. **Adapters:** Move from `hestia/sentinel/adapters/` to `atlas/atlas/adapters/` — rename `BaseAdapter` import
2. **Events:** `sentinel_events.db` rows INSERT into Atlas's unified `atlas_events.db` — same schema
3. **Service:** `com.hestia.sentinel.plist` retires, Atlas's collector process takes over
4. **API:** Hestia's `/v1/sentinel/status` switches to querying Atlas's store (or Atlas exposes its own API)

No data loss, no rewrite.

---

## 7. File Layout & Integration Points

### 7a. New Files

```
hestia/
├── hestia/sentinel/                        # New module (stdlib-only, no hestia imports)
│   ├── __init__.py
│   ├── service.py                          # Daemon entrypoint
│   ├── self_check.py                       # Self-integrity verification
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
│   ├── sentinel.json                       # Master config (kill switch, intervals, heartbeat URL)
│   ├── sentinel-dns-allowlist.json         # Approved domains (auto-populated during learning period)
│   ├── sentinel-process-allowlist.json     # Approved credential-accessing processes
│   ├── sentinel-self-manifest.json         # SHA-256 hashes of sentinel code + config files
│   └── known-pth-files.txt                 # Approved .pth files
├── scripts/
│   ├── launchd/com.hestia.sentinel.plist   # New launchd service (runs as andrewroman117, system Python)
│   ├── setup-hestia-user.sh                # Create _hestia user + set permissions
│   ├── setup-egress-firewall.sh            # Configure LuLu/pf rules
│   ├── scan-pth-files.sh                   # Reusable .pth scanner (CI + deploy)
│   └── sentinel-baseline.sh                # Manual baseline refresh
├── tests/test_sentinel/                    # Unit + integration tests
│   ├── test_file_integrity.py
│   ├── test_credential_watch.py
│   ├── test_dns_monitor.py
│   ├── test_store.py
│   ├── test_alerter.py
│   └── test_self_check.py
└── .pip-audit-known.json                   # Reviewed/accepted CVEs
```

### 7b. Modified Existing Files

| File | Change |
|------|--------|
| `requirements.in` | Update compile command comment to include `--generate-hashes` |
| `requirements.txt` | Regenerated with hashes |
| `.github/workflows/ci.yml` | `pip install --require-hashes`, blocking `pip-audit`, .pth scan step |
| `scripts/deploy-to-mini.sh` | `--require-hashes`, .pth scan, baseline refresh (in strict order), blocking `pip-audit` |
| `scripts/deploy-local.sh` | Same deploy hardening |
| `scripts/launchd/com.hestia.server.plist` | Run as `_hestia` user |
| `scripts/launchd/com.hestia.trading-bots.plist` | Run as `_hestia` user |
| `hestia/api/routes/system.py` (or new) | New `/v1/sentinel/status` read-only endpoint |
| iOS/macOS System Status views | Add sentinel event data source |

### 7c. Dependency Discipline

Sentinel has **zero pip dependencies**. Everything is Python stdlib:

| Need | stdlib Module |
|------|--------------|
| Event store | `sqlite3` |
| Process inspection | `subprocess` (absolute paths: `/usr/sbin/lsof`, `/usr/bin/log`, `/usr/sbin/dtrace`) |
| File hashing | `hashlib` |
| Event serialization | `json` |
| HTTP notifications | `urllib.request` |
| File operations | `pathlib`, `os` |
| Config | `json` (no PyYAML — true zero-dependency) |

### 7d. Testing Strategy

- Unit tests in `tests/test_sentinel/` following hestia's existing patterns
- Each adapter testable in isolation with fixture data:
  - Mock DTrace/lsof output for credential monitor
  - Mock DNS log lines for DNS monitor
  - Mock site-packages directory for file integrity
- Self-integrity check tested with intentional file modification
- Integration test: deploy script runs .pth scan + hash verification against a test venv
- Deploy ordering test: verify the invariant (pip install → .pth scan → pip-audit → baseline refresh → server restart)
- No test dependency on the hestia server running
- Added to `scripts/auto-test.sh` mapping for automatic test execution on sentinel file changes

---

## 8. Success Criteria

The sentinel is complete when:

**Layer 0:**
1. `_hestia` service user exists and runs all hestia services
2. `_hestia` cannot read `~/.ssh/` or any file outside its allowlist
3. Egress firewall blocks unauthorized outbound connections
4. `.env` file removed from Mini, contents in Keychain

**Layer 1:**
5. A `pip install` with a hash mismatch fails in CI and on the Mini
6. A known CVE blocks deployment until reviewed
7. An unexpected `.pth` file aborts a deploy
8. Deploy ordering invariant is enforced and tested

**Layer 2:**
9. The sentinel daemon runs from system Python, independently of the hestia server and venv
10. Sentinel self-integrity check detects code/config tampering
11. File integrity changes are detected within 5 minutes
12. Credential access by unexpected processes is detected (DTrace: real-time; lsof fallback: within 30s of persistent access)
13. DNS queries are logged for forensic audit trail
14. Healthchecks.io dead man's switch alerts if sentinel goes offline

**Layer 3:**
15. CRITICAL events trigger real-time push notifications within 60 seconds
16. MEDIUM/LOW events aggregated into daily digest
17. Learning period (7 days) auto-populates allowlists before enforcement
18. Kill switch degrades to detect-only mode without restart
19. System Status cards in iOS/macOS show sentinel events

**Cross-cutting:**
20. Event schema is 1:1 compatible with AtlasEvent model (Atlas severity vocabulary)
21. Sentinel has zero imports from `hestia.*` and zero pip dependencies

---

## 9. Audit Summary

This spec was reviewed through a 10-phase audit: internal engineering review (scale, front-line, backend lead, product, infra/SRE), executive panel (CISO, CTO, CPO, CFO, Legal), adversarial stress test (@hestia-critic), and cross-model validation (Gemini 2.5 Pro).

**Key changes from audit:**
- Added Layer 0 (dedicated service user, egress firewall, credential hardening) — unanimous recommendation from all three reviewers
- Sentinel runtime isolated from hestia venv — runs from system Python
- Added self-integrity check for sentinel code and config
- lsof replaced with DTrace/OpenBSM investigation (lsof as fallback with honest limitations)
- DNS monitoring demoted to supplementary audit trail (egress firewall is primary)
- Alert batching + 7-day learning period added to prevent notification fatigue
- Severity vocabulary aligned with Atlas (LOW/MEDIUM/HIGH/CRITICAL)
- Deploy ordering invariant defined
- Absolute paths for all subprocess calls
- Healthchecks.io dead man's switch for the sentinel itself
- Auto-containment default changed to off (alert-only), opt-in behind flag

**Full audit:** `docs/plans/hestia-sentinel-second-opinion-2026-03-27.md`

---

## 10. What This Does NOT Cover (Future Work)

- **Process-level network tracking** (PID → destination IP mapping) — supplement to egress firewall after v1 stabilizes
- **macOS Endpoint Security framework** — ideal for credential monitoring but requires Apple-approved system extension
- **Atlas v1 integration** — deferred until Atlas A1-A7 ships
- **Sentinel compiled binary** — compile sentinel to standalone executable for maximum isolation (eliminates Python interpreter dependency entirely)
