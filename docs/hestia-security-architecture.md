# Hestia Security Architecture

## Document Purpose

This document defines the comprehensive security architecture for Hestia, targeting "Pentagon/CIA-level" security while maintaining usability. Every security decision is documented here with rationale and implementation details.

**Security Posture**: Defense in depth with zero-trust principles.

---

## Security Objectives

| Objective | Target | Measurement |
|-----------|--------|-------------|
| **Confidentiality** | No unauthorized credential access | Zero breaches in audit logs |
| **Integrity** | No unauthorized data modification | Checksums on all sensitive data |
| **Availability** | 99.9% uptime | Max 8 hours downtime/year |
| **Auditability** | Complete access trail | Every credential access logged |
| **Recoverability** | Disaster recovery < 4 hours | Regular restore testing |

---

## Threat Model

### Assets to Protect (Priority Order)

1. **Critical Assets**:
   - Master encryption keys
   - OAuth tokens (when added in v1.5)
   - SSN, financial data (credit cards, bank accounts)
   - Medical records
   - Legal documents (contracts, NDAs)

2. **High-Value Assets**:
   - API keys (Anthropic, Weather, Search)
   - User model (competency tracking, preferences)
   - Email content (potentially sensitive)
   - Calendar data (reveals schedule)

3. **Medium-Value Assets**:
   - Conversation history
   - Research outputs
   - Learning queue
   - Logs (may contain PII)

### Threat Actors

| Actor | Capability | Motivation | Likelihood |
|-------|------------|------------|------------|
| **Opportunistic Attacker** | Low skill, automated tools | Financial gain | Medium |
| **Targeted Attacker** | Medium skill, custom exploits | Corporate espionage, IP theft | Low |
| **Insider (Family)** | Physical access, social engineering | Curiosity, accidental exposure | Medium |
| **Nation-State** | High skill, zero-days | Surveillance, data collection | Very Low |

### Attack Vectors

1. **Network-Based**:
   - Man-in-the-middle (Tailscale mitigates)
   - API credential theft
   - Session hijacking

2. **Physical Access**:
   - Stolen Mac Mini
   - Stolen backup drive
   - Unauthorized access while unlocked

3. **Software Vulnerabilities**:
   - Python dependency exploit
   - Ollama vulnerability
   - macOS privilege escalation

4. **Social Engineering**:
   - Phishing for API keys
   - Tricking user into approving malicious action

5. **Insider Threats**:
   - Family member accessing sensitive data
   - Accidental exposure via shared screen

---

## Defense-in-Depth Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 7: Monitoring & Incident Response                   │
│  • Failed auth logging                                      │
│  • Anomaly detection                                        │
│  • Daily security digest                                    │
└─────────────────────────────────────────────────────────────┘
                           ▲
                           │
┌─────────────────────────────────────────────────────────────┐
│  Layer 6: Access Control                                    │
│  • Principle of least privilege                             │
│  • External communication gate                              │
│  • Admin-only deletion                                      │
│  • Full audit trail                                         │
└─────────────────────────────────────────────────────────────┘
                           ▲
                           │
┌─────────────────────────────────────────────────────────────┐
│  Layer 5: Data Security                                     │
│  • Sensitive fields encrypted (AES-256-GCM)                 │
│  • Encryption keys in Secure Enclave                        │
│  • SQLCipher for structured memory                          │
│  • Log sanitization (no credentials logged)                 │
└─────────────────────────────────────────────────────────────┘
                           ▲
                           │
┌─────────────────────────────────────────────────────────────┐
│  Layer 4: Credential Security                               │
│  • Separate Keychain (hestia.keychain-db)                   │
│  • Biometric unlock for sensitive data                      │
│  • Hardware Security Module (Secure Enclave)                │
│  • Double encryption (Fernet + Keychain AES-256)            │
└─────────────────────────────────────────────────────────────┘
                           ▲
                           │
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: Application Security                              │
│  • Biometric authentication (Face ID/Touch ID)              │
│  • Session timeout (15/30/60 min)                           │
│  • Rate limiting per device                                 │
│  • Input validation & sanitization                          │
└─────────────────────────────────────────────────────────────┘
                           ▲
                           │
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Network Security                                  │
│  • Tailscale WireGuard VPN (end-to-end encrypted)           │
│  • No public internet exposure                              │
│  • Certificate-based device auth                            │
│  • TLS 1.3 for all communication                            │
└─────────────────────────────────────────────────────────────┘
                           ▲
                           │
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Physical Security                                 │
│  • Mac Mini in home office (physically secure)              │
│  • Encrypted backups (FileVault)                            │
│  • Secure disposal of old hardware                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Credential Management Architecture

### Storage Hierarchy

```
macOS Secure Enclave (M1 Chip)
  │
  ├─► Master Encryption Key (never leaves chip)
  │     └─► Used to encrypt all other keys
  │
  └─► Key Derivation
        │
        ├─► hestia.keychain-db (separate from user passwords)
        │     │
        │     ├─► hestia.operational (API keys, operational secrets)
        │     │     ├─► anthropic_api_key (optional biometric)
        │     │     ├─► weather_api_key (optional biometric)
        │     │     └─► search_api_key (optional biometric)
        │     │
        │     ├─► hestia.sensitive (ultra-sensitive user data)
        │     │     ├─► ssn (REQUIRES Face ID)
        │     │     ├─► credit_card_primary (REQUIRES Face ID)
        │     │     ├─► bank_account_routing (REQUIRES Face ID)
        │     │     └─► medical_insurance_id (REQUIRES Face ID)
        │     │
        │     └─► hestia.system (system-level keys)
        │           └─► master_encryption_key (REQUIRES Face ID)
        │
        └─► credentials.db (SQLCipher, encrypted SQLite)
              │
              └─► oauth_credentials (v1.5+, OAuth tokens)
                    ├─► gmail_access_token (encrypted)
                    ├─► gmail_refresh_token (encrypted)
                    └─► expires_at (timestamp)
```

### Encryption Specifications

| Layer | Algorithm | Key Length | Purpose |
|-------|-----------|------------|---------|
| **Secure Enclave** | AES-256-GCM | 256-bit | Master key storage |
| **Keychain** | AES-256 | 256-bit | Credential storage |
| **Fernet (Python)** | AES-128-CBC + HMAC-SHA256 | 128-bit | Pre-Keychain encryption |
| **SQLCipher** | AES-256-CBC | 256-bit | Database encryption |
| **Tailscale** | ChaCha20-Poly1305 | 256-bit | Network transport |

### Key Lifecycle Management

#### **v1.0: Static Keys**
- Master key generated once during setup
- API keys manually entered, never rotated
- No key expiration

#### **v1.5: Rotation Policy**
- API keys rotated every 90 days (automated)
- OAuth tokens refreshed automatically on expiry
- Master key rotation: manual, annual recommendation

#### **v2.0: Advanced Key Management**
- Hardware security key support (YubiKey)
- Key escrow for recovery (encrypted, offline)
- Multi-user key isolation

---

## Authentication & Authorization

### Authentication Layers

#### **Layer 1: Device Authentication (Network)**
- **Mechanism**: Tailscale device certificates
- **Validation**: Device must be in authorized tailnet
- **Revocation**: Remove device from Tailscale admin panel
- **Logging**: All connection attempts logged

#### **Layer 2: App Authentication (Application)**
- **Mechanism**: Face ID / Touch ID
- **Fallback**: Device passcode (after 3 failed biometric attempts)
- **Timeout**: 15/30/60 minutes configurable
- **Logging**: All unlock attempts logged (success + failure)

#### **Layer 3: Credential Authentication (Data Access)**
- **Mechanism**: Face ID required for sensitive credential retrieval
- **No fallback**: If Face ID unavailable, sensitive data inaccessible
- **Logging**: Every credential access logged with reason

### Authorization Model

#### **v1.0: Single User (Andrew)**
- Full admin privileges
- Access to all features and data
- No restrictions

#### **v2.0: Multi-User**

| Role | Permissions | Restrictions |
|------|-------------|--------------|
| **Admin** (Andrew) | Full access, can view all user data (with audit trail), system configuration | None |
| **User** (Wife, MIL) | Full Hestia features, isolated memory/credentials | Cannot access other users' data, cannot modify system config |
| **Guest** (Future) | Read-only access to shared research, no memory persistence | Cannot store credentials, no access to sensitive data |

---

## Data Protection

### Encryption at Rest

| Data Type | Storage | Encryption | Key Location |
|-----------|---------|------------|--------------|
| **Credentials** | macOS Keychain | AES-256 (Keychain) + Fernet (pre-Keychain) | Secure Enclave |
| **User Model** | SQLite | SQLCipher (AES-256) | macOS Keychain |
| **Conversation History** | SQLite | SQLCipher (AES-256) | macOS Keychain |
| **Research Outputs** | File system | FileVault 2 (full disk encryption) | T2/M1 chip |
| **Logs** | Text files | FileVault 2 | T2/M1 chip |
| **Backups** | External HDD | Time Machine encryption (AES-256) | Password-protected |

### Encryption in Transit

| Communication Path | Protocol | Encryption |
|-------------------|----------|------------|
| **Device ↔ Mac Mini** | HTTPS over Tailscale | TLS 1.3 + WireGuard (double encryption) |
| **Mac Mini ↔ Ollama** | HTTP localhost | Not needed (localhost only) |
| **Mac Mini ↔ External APIs** | HTTPS | TLS 1.3 |

### Data Sanitization

#### **Logs**
- **Never log**: Passwords, API keys, credit cards, SSN
- **Redact**: Email addresses → `a***@example.com`
- **Hash**: Request IDs for traceability
- **Sanitize**: User input before logging (prevent injection)

#### **Memory**
- **Ephemeral memory**: Cleared on session end (no persistence)
- **Short-term memory**: TTL-based eviction (7 days default)
- **Long-term memory**: Human-approved only (staged commits)

#### **Backups**
- **Encrypted**: Time Machine encryption enabled
- **Offsite**: Consider encrypted cloud backup (v1.5+)
- **Retention**: 30 days rolling (daily), 1 year yearly snapshots

---

## Network Security

### Tailscale Configuration

#### **Network Topology**
```
Internet
   │
   └─► Tailscale Control Plane (login.tailscale.com)
         │
         ├─► Mac Mini (hestia-server, 100.x.x.1)
         ├─► iPhone (hestia-iphone, 100.x.x.2)
         ├─► iPad (hestia-ipad, 100.x.x.3)
         └─► MacBook (hestia-macbook, 100.x.x.4)
```

#### **ACL Policy**
```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["andrew@family"],
      "dst": ["hestia-server:8443"]
    },
    {
      "action": "accept",
      "src": ["wife@family"],
      "dst": ["hestia-server:8443"]
    }
  ],
  "ssh": [
    {
      "action": "accept",
      "src": ["andrew@family"],
      "dst": ["hestia-server"],
      "users": ["autogroup:admin"]
    }
  ]
}
```

#### **Security Features Enabled**
- ✅ MagicDNS (automatic hostname resolution)
- ✅ HTTPS certificates (automatic Let's Encrypt)
- ✅ Key expiry (require re-authentication every 180 days)
- ✅ Device approval (new devices require admin approval)
- ❌ Exit nodes (not needed, local-only)

### Rate Limiting

| Endpoint | Limit | Window | Action on Exceed |
|----------|-------|--------|------------------|
| `/v1/chat` | 60 requests | 1 minute | 429 Too Many Requests + 60s backoff |
| `/v1/auth` | 5 attempts | 5 minutes | 401 Unauthorized + account lock (15 min) |
| `/v1/admin` | 10 requests | 1 minute | 429 + alert admin |

**Implementation**: Token bucket algorithm (per device ID).

---

## Access Control

### Principle of Least Privilege

| Component | Permissions | Rationale |
|-----------|-------------|-----------|
| **Inference Layer** | Read: prompts, memory<br>No access: credentials | Doesn't need credentials to generate responses |
| **Execution Layer** | Read: file system (allowed dirs)<br>Write: sandboxed `/tmp`<br>No access: credentials | Tools run in sandbox, can't access secrets |
| **Memory Layer** | Read/Write: user model, history<br>No delete: long-term memory (admin only) | Protects against accidental data loss |
| **API Layer** | Read: credentials (when needed)<br>No write: credentials | API calls retrieve creds but can't modify |

### External Communication Gate

**Policy**: Nothing sent externally without explicit human approval.

#### **Approval Workflow**
```python
class ExternalCommunicationGate:
    def request_approval(self, action: ExternalAction) -> ApprovalResult:
        """
        Request human approval for external communication.
        
        action: Email, API call, file upload, etc.
        """
        # Present to user with clear explanation
        prompt = f"""
        Hestia wants to: {action.description}
        
        Details:
        - Type: {action.type}
        - Destination: {action.destination}
        - Data: {action.preview}  # First 200 chars
        
        This action cannot be undone. Approve?
        [Approve] [Deny] [View Full Details]
        """
        
        # Log request
        self.audit_log.log("external_action_requested", {
            "action_type": action.type,
            "destination": action.destination,
            "timestamp": datetime.utcnow()
        })
        
        # Await user response (blocking)
        result = self.wait_for_user_input(prompt)
        
        # Log decision
        self.audit_log.log("external_action_decision", {
            "action_type": action.type,
            "decision": result.approved,
            "timestamp": datetime.utcnow()
        })
        
        return result
```

#### **Exemptions** (None in v1.0)
- v1.5: Standing approval for overnight research (pre-approved domains)
- v2.0: User-configurable auto-approve rules

---

## Audit Logging

### Log Schema

```json
{
  "timestamp": "2025-01-08T15:30:45.123Z",
  "event_type": "credential_access",
  "severity": "HIGH",
  "user_id": "andrew",
  "device_id": "hestia-macbook",
  "component": "credential_manager",
  "action": "retrieve_sensitive",
  "details": {
    "credential_key": "ssn",
    "reason": "Auto-fill form for tax filing",
    "biometric_used": true,
    "success": true
  },
  "request_id": "req-abc123",
  "session_id": "sess-xyz789"
}
```

### Event Types to Log

| Event Type | Severity | Retention |
|------------|----------|-----------|
| `credential_access` | HIGH | 7 years (compliance) |
| `failed_auth` | MEDIUM | 1 year |
| `external_action` | HIGH | 7 years |
| `admin_command` | CRITICAL | 7 years |
| `data_deletion` | CRITICAL | 7 years (permanent) |
| `memory_commit` | LOW | 90 days |
| `inference_request` | LOW | 30 days |

### Audit Review

#### **Automated Monitoring**
- Daily digest emailed to admin (high-severity events)
- Anomaly detection (unusual access patterns)
- Alert on: 5+ failed auth attempts, sensitive credential access from new device

#### **Manual Review**
- Weekly: Review all HIGH+ severity events
- Monthly: Full audit log review
- Annually: Security posture assessment

---

## Incident Response

### Security Event Classification

| Severity | Examples | Response Time | Actions |
|----------|----------|---------------|---------|
| **CRITICAL** | Unauthorized access to credentials, data exfiltration | Immediate | Revoke all credentials, force re-auth all devices, investigate |
| **HIGH** | Repeated failed auth attempts, suspicious API calls | 1 hour | Investigate, potentially lock account |
| **MEDIUM** | Single failed auth, unusual access pattern | 24 hours | Monitor, log for analysis |
| **LOW** | Normal failed auth (typo), expected anomaly | Weekly review | Log only |

### Incident Response Playbook

#### **Scenario: Suspected Credential Theft**

1. **Detect** (automated):
   - Anomaly detection flags unusual API usage
   - Example: Anthropic API called 100x/min (normal: 5x/min)

2. **Respond** (immediate):
   - Automatic: Revoke API key
   - Alert: Notify admin via push notification
   - Log: Full context of suspicious requests

3. **Investigate** (1 hour):
   - Review audit logs for access pattern
   - Check device authentication logs
   - Identify compromised device/session

4. **Remediate** (4 hours):
   - Rotate all API keys
   - Force re-authentication on all devices
   - Patch vulnerability (if found)

5. **Post-Mortem** (1 week):
   - Document root cause
   - Update threat model
   - Implement additional controls

---

## Compliance & Best Practices

### Regulatory Frameworks (Inspiration, Not Requirements)

Hestia is personal use, so no regulatory compliance required. However, we adopt best practices:

#### **HIPAA-Inspired (Medical Data)**
- ✅ Encryption at rest (AES-256)
- ✅ Access audit logs (7-year retention)
- ✅ Unique user IDs (per-user isolation in v2.0)
- ❌ Business Associate Agreement (not applicable)

#### **PCI-DSS-Inspired (Financial Data)**
- ✅ Encrypt cardholder data (double encryption)
- ✅ Restrict access (biometric required)
- ✅ Never log sensitive auth data (card CVV never stored)
- ❌ Quarterly security scans (not applicable)

#### **SOC 2-Inspired (General Security)**
- ✅ Principle of least privilege
- ✅ Change management (ADRs document decisions)
- ✅ Monitoring and alerting
- ❌ Third-party audits (not applicable)

### Data Retention Policy

| Data Type | Retention | Rationale |
|-----------|-----------|-----------|
| **Audit Logs** | 7 years | Compliance best practice |
| **Credentials** | Until manually deleted | Operational necessity |
| **User Model** | Indefinite | Long-term memory goal |
| **Conversation History** | Indefinite | Learning from past interactions |
| **Research Outputs** | Indefinite | Digital library building |
| **Ephemeral Memory** | Session only | No need to persist |
| **Short-term Memory** | 7 days | TTL-based eviction |

**Annual Review**: Prompt user to review and optionally delete old data.

---

## Security Testing

### v1.0 Security Checklist

- [ ] Credential storage: Test biometric requirement for sensitive data
- [ ] Authentication: Test session timeout and forced re-auth
- [ ] Rate limiting: Test API endpoint limits (expect 429 on exceed)
- [ ] Audit logging: Verify all credential accesses logged
- [ ] External gate: Test email draft approval workflow
- [ ] Encryption: Verify FileVault enabled on Mac Mini
- [ ] Network: Confirm Tailscale ACLs block unauthorized devices
- [ ] Backup: Test restore from encrypted Time Machine backup

### Penetration Testing (v1.5+)

**Scope**: Identify vulnerabilities before expanding to multi-user.

**Tests**:
1. **Authentication bypass**: Attempt to access API without Face ID
2. **Privilege escalation**: Attempt to access admin endpoints as user
3. **SQL injection**: Test input sanitization in memory layer
4. **Credential theft**: Attempt to extract keys from Keychain
5. **Session hijacking**: Attempt to reuse expired session token

**Frequency**: Annual, or before major version release.

---

## Future Enhancements

### v1.5 Additions
- Automated API key rotation (90-day cycle)
- Anomaly detection (ML-based access pattern analysis)
- Bluetooth proximity unlock (YubiKey integration)
- Encrypted cloud backup (iCloud with client-side encryption)

### v2.0 Additions
- Per-user credential isolation (multi-user support)
- Zero-knowledge architecture (admin can't see user creds without audit trail)
- Hardware security key support (FIDO2/WebAuthn)
- Key escrow for recovery (encrypted backup of master key)

---

## Security Contacts

| Role | Contact | Escalation |
|------|---------|------------|
| **System Owner** | Andrew Roman | N/A (single user in v1.0) |
| **Incident Response** | Andrew Roman | Self |
| **Security Audit** | External consultant (v2.0+) | Andrew Roman |

---

## Document Maintenance

- **Review Frequency**: Quarterly
- **Update Triggers**: New threat identified, security incident, major version release
- **Owner**: Andrew Roman

**Last Updated**: 2025-01-08
**Next Review**: 2025-04-08
