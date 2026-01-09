# Hestia Development Plan: Building with Claude Code & Xcode

## Overview

This document provides a structured plan for building Hestia from start to finish, using Claude Code as the primary AI-driven development tool and Xcode as your single IDE for everything.

---

## Your Two-Tool Workflow

### Claude Code (Terminal)
**Your primary development driver.**

Best for:
- Implementing features: "Build the memory manager"
- Writing and editing code across the project
- Running tests and commands
- Debugging with full context
- Iterating on implementation details

Workflow:
1. Describe what you want to build
2. Claude Code implements it
3. You review the result in Xcode
4. Iterate as needed

### Xcode (IDE)
**Your visual workspace for everything.**

Best for:
- Browsing code and project structure
- Building and running the Swift app
- iOS Simulator testing
- Visual Git operations (commits, diffs, branches)
- Editing any file type (Python, YAML, Swift, Markdown)
- Debugging with breakpoints

Workflow:
1. Open the Hestia project in Xcode
2. Review what Claude Code has built
3. Run builds and tests
4. Use the iOS Simulator to test the app

### The Handoff Pattern

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”     "Build this"      â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚   Claude Code   â”‚ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¶  â”‚   Your Project  â”‚
â”‚   (Implements)  â”‚                       â”‚     (Files)     â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                       â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                                  â”‚
                                                  â–¼
                                          â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                                          â”‚      Xcode      â”‚
                                          â”‚ (Review & Run)  â”‚
                                          â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                                  â”‚
        "Here's what I see, let's adjust"         â”‚
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”â—€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
â”‚   Claude Code   â”‚
â”‚   (Iterates)    â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### When to Use Which

| Task | Tool |
|------|------|
| "Create the inference client" | Claude Code |
| "Add retry logic to this function" | Claude Code |
| Browse the codebase | Xcode |
| Run the iOS app | Xcode |
| Commit changes to Git | Xcode |
| "Why is this test failing?" | Claude Code (paste error) |
| View visual diffs | Xcode |
| Edit a config file manually | Either |

---

---

## Phase 0.5: Security Foundation (Week 1)

### Objective
Establish credential management and security infrastructure BEFORE any other code. Logging (Phase 1) depends on this to avoid accidentally logging credentials.

### Why This First
- Credential management affects every subsequent component
- Can't safely log API calls without credential sanitization
- Setting security patterns early prevents retrofitting later
- Master encryption key must exist before encrypting user model fields

### Tasks

#### 0.5.1 Create Separate Keychain
- [ ] Generate `hestia.keychain-db` (separate from user's login keychain)
- [ ] Configure keychain settings (auto-lock timeout: 30 minutes)
- [ ] Test keychain access from Python

```bash
# Create separate keychain for Hestia
security create-keychain -p "" ~/Library/Keychains/hestia.keychain-db

# Set auto-lock timeout (1800 seconds = 30 minutes)
security set-keychain-settings -lut 1800 ~/Library/Keychains/hestia.keychain-db

# Add to search list
security list-keychains -d user -s ~/Library/Keychains/hestia.keychain-db
```

#### 0.5.2 Build Swift CLI: hestia-keychain-cli
- [ ] Create Xcode CLI project: `hestia-cli-tools/hestia-keychain-cli`
- [ ] Implement commands:
  - `generate-master-key`: Create master encryption key in Secure Enclave
  - `get-master-key`: Retrieve master key (requires biometric)
  - `store-credential`: Store credential in Keychain partition
  - `retrieve-credential`: Get credential (biometric if sensitive)
- [ ] Use Security.framework for Secure Enclave access
- [ ] JSON output for Python parsing
- [ ] Build automation: `make install` copies to `~/.hestia/bin/`

#### 0.5.3 Python Credential Manager
- [ ] Create `hestia/security/` module
- [ ] Implement `CredentialManager` class:
  - `store_operational(key, value)`: API keys (optional biometric)
  - `store_sensitive(key, value, reason)`: Always requires Face ID
  - `retrieve_operational(key)`: Get API key
  - `retrieve_sensitive(key, reason)`: Get sensitive data with audit
  - `delete(key)`: Admin-only deletion
- [ ] Integrate with Swift CLI via subprocess
- [ ] Double encryption: Fernet before Keychain storage
- [ ] Full audit logging (never log credential values)

#### 0.5.4 Audit Logger (Minimal for v0.5)
- [ ] Create basic audit log schema (JSON)
- [ ] Log credential access events:
  - `credential_stored`: What was stored (not value)
  - `credential_retrieved`: What was retrieved, by whom, when, reason
  - `credential_deleted`: Admin action audit trail
- [ ] Write to `~/hestia/logs/audit.log`
- [ ] Log rotation (keep 90 days)

### Deliverables
- `hestia.keychain-db` separate from user passwords
- `hestia-keychain-cli` Swift binary in `~/.hestia/bin/`
- `hestia/security/credential_manager.py` module
- Basic audit logging for credential access
- Test suite: store/retrieve with biometric prompts

### Code Structure
```python
# hestia/security/credential_manager.py

import subprocess
import keyring
from cryptography.fernet import Fernet
from datetime import datetime
from typing import Optional

class CredentialManager:
    """
    Pentagon-grade credential management.
    
    Uses macOS Keychain + Secure Enclave for hardware-backed security.
    All credentials double-encrypted (Fernet + Keychain AES-256).
    Complete audit trail for every access.
    """
    
    # Keychain partitions
    KEYCHAIN_SERVICE_OPERATIONAL = "hestia.operational"
    KEYCHAIN_SERVICE_SENSITIVE = "hestia.sensitive"
    KEYCHAIN_SERVICE_SYSTEM = "hestia.system"
    
    def __init__(self, audit_logger):
        self.audit = audit_logger
        self._ensure_master_key()
    
    def _ensure_master_key(self):
        """Generate or retrieve master encryption key from Secure Enclave."""
        result = subprocess.run(
            ['hestia-keychain-cli', 'get-master-key'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            # Generate new master key
            subprocess.run(['hestia-keychain-cli', 'generate-master-key'])
            result = subprocess.run(
                ['hestia-keychain-cli', 'get-master-key'],
                capture_output=True,
                text=True
            )
        
        self.master_key = result.stdout.strip().encode()
    
    def store_operational(self, key: str, value: str) -> None:
        """Store operational credential (API keys, OAuth tokens)."""
        # Encrypt with Fernet before storing
        cipher = Fernet(self.master_key)
        encrypted_value = cipher.encrypt(value.encode()).decode()
        
        # Store in Keychain
        keyring.set_password(
            self.KEYCHAIN_SERVICE_OPERATIONAL,
            key,
            encrypted_value
        )
        
        # Audit log (never log actual value)
        self.audit.log("credential_stored", {
            "key": key,
            "service": "operational",
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def store_sensitive(self, key: str, value: str, reason: str) -> None:
        """
        Store ultra-sensitive credential (SSN, financial data).
        Always requires Face ID to retrieve.
        """
        cipher = Fernet(self.master_key)
        encrypted_value = cipher.encrypt(value.encode()).decode()
        
        # Store in sensitive partition
        keyring.set_password(
            self.KEYCHAIN_SERVICE_SENSITIVE,
            key,
            encrypted_value
        )
        
        # Set biometric ACL via Swift CLI
        subprocess.run([
            'hestia-keychain-cli',
            'set-biometric-acl',
            self.KEYCHAIN_SERVICE_SENSITIVE,
            key
        ])
        
        # Audit log with HIGH severity
        self.audit.log("sensitive_credential_stored", {
            "key": key,
            "reason": reason,
            "severity": "HIGH",
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def retrieve_operational(self, key: str) -> Optional[str]:
        """Retrieve operational credential."""
        encrypted_value = keyring.get_password(
            self.KEYCHAIN_SERVICE_OPERATIONAL,
            key
        )
        
        if not encrypted_value:
            return None
        
        # Decrypt
        cipher = Fernet(self.master_key)
        value = cipher.decrypt(encrypted_value.encode()).decode()
        
        # Audit log
        self.audit.log("credential_retrieved", {
            "key": key,
            "service": "operational",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        return value
    
    def retrieve_sensitive(self, key: str, reason: str) -> Optional[str]:
        """
        Retrieve sensitive credential.
        Requires Face ID (enforced by Keychain ACL).
        """
        # This will prompt for Face ID due to ACL
        encrypted_value = keyring.get_password(
            self.KEYCHAIN_SERVICE_SENSITIVE,
            key
        )
        
        if not encrypted_value:
            return None
        
        # Decrypt
        cipher = Fernet(self.master_key)
        value = cipher.decrypt(encrypted_value.encode()).decode()
        
        # Audit log with reason
        self.audit.log("sensitive_credential_retrieved", {
            "key": key,
            "reason": reason,
            "severity": "HIGH",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        return value
    
    def delete(self, key: str, service: str = "operational") -> None:
        """Delete credential (admin only)."""
        keychain_service = (
            self.KEYCHAIN_SERVICE_SENSITIVE 
            if service == "sensitive" 
            else self.KEYCHAIN_SERVICE_OPERATIONAL
        )
        
        try:
            keyring.delete_password(keychain_service, key)
            
            # Audit log (CRITICAL severity)
            self.audit.log("credential_deleted", {
                "key": key,
                "service": service,
                "severity": "CRITICAL",
                "timestamp": datetime.utcnow().isoformat()
            })
        except keyring.errors.PasswordDeleteError:
            # Credential didn't exist
            pass
```

### Testing Criteria
- [ ] Master key generated in Secure Enclave (verify with security CLI)
- [ ] Operational credential stored and retrieved successfully
- [ ] Sensitive credential prompts for Face ID on retrieval
- [ ] Audit log captures all credential operations
- [ ] No credential values appear in logs (verify grep)
- [ ] Keychain partition separate from login.keychain (verify in Keychain Access.app)

### Claude Checkpoint
Before proceeding to Phase 1, share:
- Output of `security list-keychains` (verify hestia.keychain-db present)
- Sample audit log entry (verify no credential values)
- Face ID prompt screenshot (verify biometric requirement works)

### Calibration Checkpoint 1: Security Foundation

**Trigger**: After completing Phases 0 + 0.5 + 1 (Week 2)

**Andrew's preparation**:
```bash
# 1. Test credential management
hestia-keychain-cli get-master-key  # Should prompt Face ID

# 2. Store/retrieve test credential
python -c "
from hestia.security.credential_manager import CredentialManager
from hestia.logging import AuditLogger

audit = AuditLogger()
cm = CredentialManager(audit)
cm.store_operational('test_api_key', 'sk-test-12345')
value = cm.retrieve_operational('test_api_key')
print(f'Retrieved: {value[:10]}...')  # Should print: sk-test-12...
"

# 3. Check audit log
python -m hestia.logging.viewer --filter event_type=credential_access --tail 10

# 4. Verify no credential values in logs
grep -r "sk-test" ~/hestia/logs/  # Should return NOTHING

# 5. Test Face ID prompt for sensitive data
python -c "
from hestia.security.credential_manager import CredentialManager
from hestia.logging import AuditLogger

audit = AuditLogger()
cm = CredentialManager(audit)
cm.store_sensitive('test_ssn', '123-45-6789', reason='Testing')
# Should prompt for Face ID on next line:
value = cm.retrieve_sensitive('test_ssn', reason='Checkpoint test')
"
```

**Calibration session** (45-60 minutes):

1. **Review** (10 min):
   - [ ] Demonstrate Face ID prompt working
   - [ ] Show audit log entries (no credential values present)
   - [ ] Show separate hestia.keychain-db in Keychain Access.app
   - [ ] Run test commands above

2. **Explain** (15 min):
   - [ ] Q: Why do we double-encrypt credentials (Fernet + Keychain)?
   - [ ] Q: Walk me through what happens when Phase 2 retrieves an API key
   - [ ] Q: What breaks if Secure Enclave is unavailable?
   - [ ] Q: Why separate audit logs from general logs (7-year retention)?
   - [ ] Q: How would Phase 2 (Inference) use CredentialManager?

3. **Test depth** (10 min):
   - [ ] Propose: How would you add a third credential tier (e.g., "temporary" with 1-hour TTL)?
   - [ ] Propose: What if we wanted to rotate API keys automatically every 90 days?

4. **Preview** (10 min):
   - Discuss Phase 1 (Logging) and Phase 2 (Inference)
   - How logging depends on credential sanitization
   - How inference layer will retrieve API keys for cloud fallback

5. **Align** (5 min):
   - [ ] Security architecture matches ADR-009?
   - [ ] Ready to proceed to logging and inference?
   - [ ] Any concerns about Swift CLI tools?

6. **Document** (5 min):
   - [ ] Create `docs/checkpoints/checkpoint-1-notes.md`
   - [ ] Git tag: `git tag checkpoint-1-security && git push --tags`
   - [ ] Update any ADRs if decisions changed

**Expected understanding**:
- Secure Enclave stores master key (hardware-backed, never extractable)
- Fernet encrypts BEFORE Keychain (defense in depth, two separate systems)
- Audit logs have 7-year retention (compliance best practice)
- CredentialManager enforces biometric for sensitive tier (Face ID required)
- Swift CLI bridges Python ↔ Security.framework for Secure Enclave access

---

---

## Calibration Checkpoint Protocol

### Purpose
Pause development at key milestones to ensure understanding, alignment, and quality. Prevents architectural drift and ensures Andrew can explain what's been built and why.

### Philosophy
**Calibration is not review**—it's active learning verification. Andrew must demonstrate understanding, not just show working code.

---

### When to Trigger Checkpoints

#### **Scheduled Checkpoints** (After Major Phases)

```
Timeline:
├─ Week 1-2:  Phases 0 + 0.5 + 1  → CHECKPOINT 1: Security & Logging
├─ Week 3-5:  Phases 2 + 3        → CHECKPOINT 2: Inference & Memory  
├─ Week 6-7:  Phase 4             → CHECKPOINT 3: Orchestration
├─ Week 8:    Phases 5 + 5.5      → CHECKPOINT 4: Execution & Apple
├─ Week 9-10: Phase 6             → CHECKPOINT 5: iOS App
└─ Week 11+:  Phase 7             → CHECKPOINT 6: Production Ready
```

#### **Unscheduled Triggers**
- Encountering unexpected complexity (>2 hours debugging)
- Proposing significant architectural change
- >2 weeks since last checkpoint
- Andrew feels lost or uncertain about next steps

---

### Checkpoint Structure

#### **1. Review: What We Built** (10 minutes)

**Andrew demonstrates**:
- Run tests, show passing results
- Walk through key files created
- Explain data flow for primary use case
- Show logs/output from working system

**Questions to answer**:
- What did we build in this phase?
- What are the key files/functions?
- How do the components interact?
- What surprised you during implementation?

---

#### **2. Demonstrate Understanding** (15 minutes)

**Andrew explains in own words** (no looking at docs):
- Core concepts introduced in this phase
- Why we made key architectural decisions
- Trade-offs we accepted
- How this phase enables next phase

**Validation exercises** (pick 2-3):
- **Trace data flow**: "Walk me through what happens when Hestia retrieves a credential"
- **Identify edge cases**: "What breaks if Face ID is unavailable?"
- **Explain alternatives**: "Why did we choose Keychain over encrypted SQLite?"
- **Connect to future**: "How will Phase 2 (Inference) use what we just built?"

**Claude's role**: Ask probing questions, correct misunderstandings, fill gaps.

---

#### **3. Test Depth** (10 minutes)

**Andrew proposes a minor enhancement** (tests understanding):
- "How would you add a second biometric tier (Touch ID fallback)?"
- "What if we wanted to rotate API keys every 90 days?"
- "How could we add rate limiting to credential access?"

**Purpose**: Verify Andrew can extend the system, not just explain it.

---

#### **4. Preview Next Phase** (10 minutes)

**Discuss upcoming work**:
- What are we building in the next phase?
- What are the key dependencies?
- What could go wrong?
- What questions do you have before starting?

**Claude provides**:
- High-level overview of next phase
- How it builds on current phase
- Key concepts to research (if any)
- Expected challenges

---

#### **5. Alignment Check** (5 minutes)

**Review**:
- ✅ Architecture still aligned with ADRs?
- ✅ Scope creep or necessary cuts?
- ✅ Timeline on track?
- ✅ Learning pace sustainable?

**Adjustments**:
- New ADRs needed?
- Update development plan?
- Change phase sequencing?

---

#### **6. Document** (5 minutes)

**Checkpoint artifacts**:
- [ ] Notes document (Q&A transcript)
- [ ] Updated ADRs (if decisions changed)
- [ ] Updated development plan (if scope adjusted)
- [ ] Screen recording (optional, for complex phases)
- [ ] Test results (screenshots/logs)

**Commit to Git**: Tag checkpoint completion
```bash
git tag checkpoint-1-security-logging
git push origin checkpoint-1-security-logging
```

---

### Checkpoint Templates

#### **Checkpoint 1: Security & Logging Foundation**

**When**: After Phases 0 + 0.5 + 1 (Week 2)

**Andrew's prep**:
```bash
# 1. Test credential management
hestia-keychain-cli get-master-key  # Should prompt Face ID

# 2. Store test credential
python -c "
from hestia.security.credential_manager import CredentialManager
cm = CredentialManager()
cm.store_operational('test_key', 'test_value')
cm.retrieve_operational('test_key')
"

# 3. Check audit log
python -m hestia.logging.viewer --filter event_type=credential_access --tail 10

# 4. Verify logging
python -m hestia.logging.viewer --filter severity=HIGH
```

**Key questions for Andrew**:
1. Why do we double-encrypt credentials (Fernet + Keychain)?
2. Walk me through: What happens when Phase 2 retrieves an API key?
3. What breaks if the Secure Enclave is unavailable?
4. How would you add a third credential tier (e.g., "temporary")?
5. Why separate audit logs from general logs?

**Expected understanding**:
- Secure Enclave stores master key (hardware-backed, never leaves chip)
- Fernet encrypts BEFORE Keychain (defense in depth)
- Audit logs have 7-year retention (compliance)
- CredentialManager enforces biometric for sensitive tier

---

#### **Checkpoint 2: Inference & Memory**

**When**: After Phases 2 + 3 + 3.5 (Week 5)

**Andrew's prep**:
```bash
# 1. Test inference
python -c "
from hestia.inference.client import InferenceClient
client = InferenceClient()
response = await client.complete('Explain Hestia in one sentence.')
print(response)
"

# 2. Test memory tagging
python -m hestia.memory.search --semantic "security" --tags "has_decision:true"

# 3. Check token usage
python -m hestia.logging.viewer --filter event_type=inference_request --tail 5
```

**Key questions**:
1. Why is 32K context window actually BETTER than infinite for Hestia?
2. Explain the three-stage retrieval process for large context needs
3. Walk me through: How does auto-tagging work?
4. What's the difference between ChromaDB and SQLite in our memory layer?
5. When would Hestia escalate to Claude API (200K context)?

---

#### **Checkpoint 3: Orchestration**

**When**: After Phase 4 (Week 7)

**Key questions**:
1. Explain the state machine: What are valid state transitions?
2. How does mode switching work (Tia → Mira)?
3. What triggers validation retry vs. error return?
4. Walk through: Complete request lifecycle from API call to response

---

#### **Checkpoint 4: Execution & Apple Integration**

**When**: After Phases 5 + 5.5 (Week 8)

**Andrew's prep**:
```bash
# Test Apple ecosystem integration
hestia-reminders-cli list
hestia-calendar-cli list-events --after today
hestia-notes-cli list
```

**Key questions**:
1. Why EventKit (Swift) instead of AppleScript for Reminders?
2. How does Hestia access Gmail without OAuth?
3. What breaks if EventKit permission is denied?
4. Explain sandbox: How do tools execute safely?

---

#### **Checkpoint 5: iOS App**

**When**: After Phase 6 (Week 10)

**Andrew's prep**:
- Build app in Xcode, run in Simulator
- Test Face ID prompt (Simulator feature)
- Test Tailscale connection from iPhone

**Key questions**:
1. Why is the iOS app a "stateless terminal"?
2. How does Face ID in the app differ from Face ID for credentials?
3. Walk through: What happens when you send a message from iPhone?
4. Why SwiftUI instead of UIKit?

---

#### **Checkpoint 6: Production Readiness**

**When**: After Phase 7 (Week 11+)

**Key questions**:
1. How would you recover if Mac Mini fails?
2. What monitoring alerts would indicate a problem?
3. Walk through incident response for suspected credential theft
4. What's the backup strategy?

---

### Success Criteria

**Checkpoint passes if**:
- ✅ Andrew can explain core concepts without looking at docs
- ✅ Andrew can trace data flow for key use cases
- ✅ Andrew can propose valid enhancements
- ✅ No major misunderstandings about architecture
- ✅ Andrew feels confident proceeding to next phase

**Checkpoint fails if**:
- ❌ Andrew can't explain why (only what)
- ❌ Major gaps in understanding dependencies
- ❌ Can't connect current phase to next phase
- ❌ Andrew feels uncertain about proceeding

**If checkpoint fails**: Spend extra time on remediation before proceeding. Better to pause now than debug confused architecture later.

---

### Integration with Development Plan

Each phase now includes:

```markdown
### Claude Checkpoint

**Trigger**: After phase completion, before starting next phase

**Andrew's preparation**:
- [ ] Run all tests, capture results
- [ ] Review key files in Xcode
- [ ] Prepare 2-3 questions about implementation
- [ ] (Phase-specific prep commands listed above)

**Calibration session** (with Claude):
1. **Review** (10 min): Andrew demonstrates working system
2. **Explain** (15 min): Andrew explains core concepts
3. **Test** (10 min): Andrew proposes enhancement
4. **Preview** (10 min): Discuss next phase
5. **Align** (5 min): Confirm architecture/scope/timeline
6. **Document** (5 min): Create checkpoint artifacts

**Expected duration**: 45-60 minutes

**Deliverables**:
- [ ] Checkpoint notes document
- [ ] Git tag: `checkpoint-N-phase-name`
- [ ] Updated ADRs (if needed)
- [ ] Updated development plan (if scope changed)
```

---

## Phase 0: Environment Setup (Week 1)

### Objective
Get the Mac Mini configured and verify the model runs correctly.

### Tasks

#### 0.1 Hardware Setup
- [ ] Mac Mini running, connected to network
- [ ] Static IP or hostname configured on local network
- [ ] SSH access configured and tested
- [ ] Tailscale installed and connected to your tailnet

#### 0.2 Model Runtime
- [ ] Install Ollama: `curl -fsSL https://ollama.com/install.sh | sh`
- [ ] Pull Mixtral: `ollama pull mixtral:8x7b-instruct-v0.1-q4_K_M`
- [ ] Verify inference: `ollama run mixtral:8x7b-instruct-v0.1-q4_K_M "Hello, respond with one word."`
- [ ] Note inference speed and memory usage

#### 0.3 Development Environment
- [ ] Python 3.11+ installed
- [ ] Project directory created: `~/hestia`
- [ ] Virtual environment: `python -m venv .venv && source .venv/bin/activate`
- [ ] Git initialized with `.gitignore`

### Deliverables
- Working Ollama installation with Mixtral responding to prompts
- Tailscale connection from your other devices to Mac Mini
- Project directory with virtual environment

### Claude Checkpoint
Before proceeding, share with Claude:
- Output of `ollama run mixtral:8x7b-instruct-v0.1-q4_K_M "Summarize your capabilities in 50 words."`
- Memory usage during inference (`top` or Activity Monitor)
- Any errors or unexpected behavior

---

## Phase 1: Logging Infrastructure (Week 2)

### Objective
Build comprehensive logging AFTER credential management (Phase 0.5) is in place. Logging must sanitize credentials before writing.

### Why After Phase 0.5
Every subsequent component will use logging. Building it after credential management means:
- Logs can safely sanitize credentials using CredentialManager
- All future code has logging from day one
- You establish patterns other code will follow
- You can observe behavior from the earliest stages

### Tasks

#### 1.1 Log Schema Design
```python
# Ask Claude to review this schema before implementing
{
    "timestamp": "ISO-8601",
    "request_id": "UUID",
    "event_type": "request|response|memory_access|tool_call|error|state_change|credential_access",
    "severity": "LOW|MEDIUM|HIGH|CRITICAL",
    "component": "access|orchestration|memory|inference|execution|security",
    "data": {
        # Event-specific payload (sanitized)
    },
    "duration_ms": 123,
    "metadata": {
        "device_id": "...",
        "session_id": "...",
        "user_id": "..." # v2.0 multi-user
    }
}
```

#### 1.2 Logging Module Implementation
- [ ] Create `hestia/logging/` module
- [ ] Implement structured JSON logging
- [ ] Add log rotation (daily files, 90-day retention for general logs, 7-year for audit logs)
- [ ] Create helper functions for common log events
- [ ] Add request ID propagation for tracing
- [ ] **CRITICAL**: Implement credential sanitization:
  - Never log values from CredentialManager
  - Redact API keys in error messages (show first 8 chars only: `sk-ant-abc...`)
  - Redact emails: `a***@example.com`
  - Hash sensitive IDs for traceability without exposure

#### 1.3 Log Viewer
- [ ] Simple CLI tool to query logs
- [ ] Filter by time range, event type, request ID, severity
- [ ] Output in human-readable format
- [ ] Highlight HIGH/CRITICAL severity events

#### 1.4 Integration with Credential Manager
- [ ] CredentialManager logs to audit log (separate from general logs)
- [ ] Audit log: 7-year retention, never rotated
- [ ] General log: 90-day retention, daily rotation
- [ ] Sensitive operations always logged with HIGH/CRITICAL severity

### Deliverables
- `hestia/logging/` module with structured logging
- Log files writing to `~/hestia/logs/` (separate audit log)
- CLI tool: `python -m hestia.logging.viewer --tail --filter event_type=error`
- Credential sanitization prevents leaks

### Testing Criteria
- [ ] Logs are valid JSON (parseable by `jq`)
- [ ] Request IDs propagate through related events
- [ ] Log rotation works (create test logs, verify rotation)
- [ ] Viewer can filter and display logs correctly
- [ ] **CRITICAL**: Test credential sanitization:
  - Store API key via CredentialManager
  - Trigger error that would log API key
  - Verify log shows redacted version only: `anthropic_api_key: sk-ant-abc...`
- [ ] Audit log separate from general log
- [ ] Audit log retention: 7 years (verify in config)

### Claude Checkpoint
Share:
- Your log schema design
- Sample log output from test events (verify no credentials)
- Sample audit log entry (credential access)
- Any questions about what to log

---

## Phase 2: Inference Layer (Week 3)

### Objective
Wrap Ollama in a clean interface with logging, retry logic, validation, and secure credential handling.

### Tasks

#### 2.1 Ollama Client Wrapper
- [ ] Create `hestia/inference/` module
- [ ] Implement async client for Ollama API
- [ ] Add request/response logging (using Phase 1 infrastructure with credential sanitization)
- [ ] Add timeout handling (configurable, default 60s)
- [ ] Add retry logic (3 attempts with exponential backoff)
- [ ] Token counting for context window management (ADR-011)

#### 2.2 Response Validation
- [ ] Define expected response structure
- [ ] Implement validation function
- [ ] Log validation failures with full context
- [ ] Return structured error on validation failure

#### 2.3 Context Window Management (ADR-011)
- [ ] Implement token counting using `tiktoken` or similar
- [ ] Track token usage per request component:
  - System prompt: ~2K tokens
  - Tool definitions: ~1K tokens
  - User model: ~2K tokens
  - Conversation history: sliding window
  - Memory retrieval: RAG-filtered chunks
- [ ] Log warning if >28K tokens (90% of 32K limit)
- [ ] Return error if request would exceed 32K

#### 2.4 Variable Context Window Support (NEW)
- [ ] Define `ContextSize` enum:
  - `STANDARD` (32K): Local Mixtral (default, free)
  - `LARGE` (200K): Claude Sonnet API (user approval required, ~$2-3/request)
  - `XLARGE` (500K): Claude Opus API (cost warning, ~$8-10/request)
- [ ] Implement automatic model selection based on context requirements
- [ ] User can explicitly request: `@Tia [context:large] Analyze all conversations about security...`
- [ ] Implement multi-stage retrieval as cheaper alternative:
  - Stage 1: Retrieve relevant chunks (100 chunks × 1K = 100K tokens)
  - Stage 2: Summarize each chunk (parallel, fast)
  - Stage 3: Synthesize summaries (fits in 32K)
- [ ] External communication gate integration (user approves cloud API usage)
- [ ] Cost tracking: Log API usage, budget alerts
- [ ] Fallback logic: Try multi-stage retrieval first, escalate to cloud only if necessary

**Cost implications**:
- STANDARD: $0 (local)
- LARGE: ~$2-3 per request (occasional deep dives)
- XLARGE: ~$8-10 per request (rare comprehensive analysis)

**Expected usage distribution**: 99% STANDARD, <1% LARGE, <0.1% XLARGE

#### 2.5 Configuration
- [ ] Detect when Mixtral insufficient (context too large, task too complex)
- [ ] Integrate Anthropic API client for fallback
- [ ] Use CredentialManager for API key retrieval
- [ ] Log fallback decision (why local model insufficient)
- [ ] Track fallback usage for cost monitoring

#### 2.6 Configuration
- [ ] Model name configurable
- [ ] Temperature and other params configurable
- [ ] System prompt configurable
- [ ] Context window limits configurable
- [ ] Cloud fallback preferences (auto/ask/never)
- [ ] All config in `hestia/config/inference.yaml`

### Deliverables
- `hestia/inference/client.py` with clean async interface
- Configuration file for inference settings
- All inference calls logged with timing and token usage
- Secure credential handling via CredentialManager
- Optional cloud fallback integration

### Code Structure
```python
# hestia/inference/client.py
from hestia.security.credential_manager import CredentialManager

class InferenceClient:
    def __init__(self, credential_manager: CredentialManager, logger):
        self.creds = credential_manager
        self.logger = logger
    
    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> InferenceResponse:
        """
        Send prompt to model, return validated response.
        Logs request, response, timing, token usage, and any errors.
        Retries on transient failures.
        """
        # Count tokens BEFORE sending
        token_count = self._count_tokens(prompt, system)
        
        if token_count > 32000:
            # Context window exceeded
            return await self._fallback_to_cloud(prompt, system, temperature, max_tokens)
        
        # Log request (sanitized)
        self.logger.log("inference_request", {
            "tokens": token_count,
            "temperature": temperature,
            "max_tokens": max_tokens
        })
        
        # ... Ollama API call ...
    
    async def _fallback_to_cloud(self, prompt: str, system: str, temperature: float, max_tokens: int):
        """
        Fallback to Anthropic API when local model insufficient.
        Requires credential_manager to retrieve API key securely.
        """
        # Retrieve API key securely
        api_key = self.creds.retrieve_operational("anthropic_api_key")
        
        if not api_key:
            raise ValueError("Cloud fallback requested but no Anthropic API key configured")
        
        # Log fallback decision
        self.logger.log("inference_fallback", {
            "reason": "context_window_exceeded",
            "severity": "MEDIUM"
        })
        
        # ... Anthropic API call ...
        # Note: API key never logged, even in errors
```

### Testing Criteria
- [ ] Successful inference logged with timing
- [ ] Timeout handled gracefully (returns error, doesn't crash)
- [ ] Retry logic works (simulate failure, verify retry)
- [ ] Invalid responses logged with full context
- [ ] Token counting accurate (test with known prompts)
- [ ] Context window limit enforced
- [ ] Cloud fallback works (if enabled)
- [ ] API keys never appear in logs (verify grep for `sk-ant-`)

### Claude Checkpoint
Share:
- Your client interface design
- Sample logs from inference calls (verify no API keys)
- Token counting test results
- Any edge cases you're uncertain about

---

## Phase 3: Memory Layer (Week 4-5)

### Objective
Implement stratified memory with governed persistence.

### Tasks

#### 3.1 Ephemeral Memory
- [ ] In-memory dict scoped to session
- [ ] Auto-cleared on session end
- [ ] Simple key-value interface

#### 3.2 Vector Store (Long-term Semantic)
- [ ] Install ChromaDB: `pip install chromadb`
- [ ] Create `hestia/memory/vector.py`
- [ ] Implement add/query interface
- [ ] Configure embedding model (Ollama's `nomic-embed-text` or similar)
- [ ] Log all memory operations

#### 3.3 Structured Store (Short-term + Records)
- [ ] SQLite database: `~/hestia/data/structured.db`
- [ ] Schema for timestamped records
- [ ] TTL-based eviction for short-term entries
- [ ] Query interface with filtering

#### 3.4 Staging Layer
- [ ] Table for proposed memory updates
- [ ] Status: pending/approved/rejected
- [ ] CLI tool to review staged updates
- [ ] Commit approved updates to appropriate store

#### 3.5 Memory Manager
- [ ] Unified interface: `MemoryManager`
- [ ] Methods: `retrieve(query, scopes)`, `stage_update(update)`, `commit(update_id)`
- [ ] Scoped retrieval (specify which layers to query)
- [ ] Context window management (truncate if too large)

### Deliverables
- `hestia/memory/` module with all memory types
- Staging workflow for governed persistence
- CLI: `python -m hestia.memory.review` to approve/reject staged updates

---

## Phase 3.5: Tag-Based Memory Schema (Week 5)

### Objective
Enhance memory layer with multi-dimensional querying: semantic + tags + temporal + relational. Enables Datadog-style observability of conversation history.

### Why This Enhancement
Traditional vector search (semantic only) can't answer queries like:
- "Show me all unresolved action items from last month"
- "Find all conversations where we discussed security AND made decisions"
- "How did my thinking on credential management evolve over time?"

Tag-based schema enables these queries while preserving semantic search capability.

### Tasks

#### 3.5.1 Define Tag Taxonomy
- [ ] Document tag categories:
  - **topics**: Key subjects discussed (e.g., "security", "memory", "apple-ecosystem")
  - **entities**: Named entities (e.g., "Face ID", "Mixtral", "Keychain")
  - **people**: Participants (e.g., "andrew", "claude")
  - **mode**: Hestia mode active (e.g., "Tia", "Mira", "Olly")
  - **phase**: Development phase (e.g., "design", "phase-2", "implementation")
  - **status**: Action status (e.g., "active", "resolved", "deferred", "blocked", "action_item")
- [ ] Define metadata flags:
  - `has_code`: Contains code snippets
  - `has_decision`: Contains architectural decision
  - `has_action_item`: Contains task/to-do
  - `sentiment`: Overall tone (neutral/positive/negative/concerned)
  - `confidence`: Model's confidence in tagging (0.0-1.0)

#### 3.5.2 Extend SQLite Schema
```sql
CREATE TABLE conversation_chunks (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    content TEXT NOT NULL,
    embedding_id TEXT,  -- Links to ChromaDB
    
    -- Relationships
    references TEXT,    -- JSON array of chunk IDs
    supersedes TEXT,    -- Chunk ID this updates
    
    INDEX idx_session (session_id),
    INDEX idx_timestamp (timestamp)
);

CREATE TABLE chunk_tags (
    chunk_id TEXT NOT NULL,
    category TEXT NOT NULL,  -- 'topics', 'entities', 'people', etc.
    value TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    
    FOREIGN KEY (chunk_id) REFERENCES conversation_chunks(id),
    INDEX idx_chunk (chunk_id),
    INDEX idx_category_value (category, value)
);

CREATE TABLE chunk_metadata (
    chunk_id TEXT PRIMARY KEY,
    has_code BOOLEAN DEFAULT FALSE,
    has_decision BOOLEAN DEFAULT FALSE,
    has_action_item BOOLEAN DEFAULT FALSE,
    sentiment TEXT,
    confidence REAL,
    
    FOREIGN KEY (chunk_id) REFERENCES conversation_chunks(id)
);
```

#### 3.5.3 Implement Auto-Tagging Pipeline
- [ ] Create `hestia/memory/tagger.py`:
  - `MemoryTagger` class
  - Uses Mixtral for tag generation
  - Async execution (non-blocking)
  - Prompt engineering for structured output (JSON)
- [ ] Tag generation happens after conversation turn
- [ ] Store tags in SQLite (chunk_tags table)
- [ ] Link to ChromaDB embedding via embedding_id

**Tagger prompt template**:
```python
TAGGING_PROMPT = """
Analyze this conversation chunk and extract structured tags.

Chunk: {content}

Return ONLY valid JSON with:
{{
  "topics": ["topic1", "topic2"],           // 3-5 key subjects
  "entities": ["Entity1", "Entity2"],       // Named entities
  "status": ["active" | "resolved" | ...],  // Action status
  "has_code": true/false,
  "has_decision": true/false,
  "has_action_item": true/false,
  "sentiment": "neutral/positive/negative/concerned",
  "confidence": 0.0-1.0
}}

Be concise. Extract only high-confidence tags.
"""
```

#### 3.5.4 Implement Multi-Dimensional Search
- [ ] Extend `MemoryManager.retrieve()` to support:
  - **Semantic search** (ChromaDB): `semantic="security encryption"`
  - **Tag filtering** (SQLite): `tags={"topics": ["security"], "has_decision": True}`
  - **Temporal queries** (SQLite): `date_range=("2025-01-01", "2025-01-31")`
  - **Relationship traversal** (SQLite): `references=["ADR-009"]`
  - **Combined queries**: All of the above together
- [ ] Implement query optimizer (decide ChromaDB vs SQLite vs both)
- [ ] Return results with tag metadata attached

**Query interface**:
```python
# hestia/memory/manager.py

class MemoryManager:
    async def retrieve(
        self,
        semantic: Optional[str] = None,
        tags: Optional[Dict[str, List[str]]] = None,
        date_range: Optional[Tuple[str, str]] = None,
        references: Optional[List[str]] = None,
        sort: str = "relevance",  # or "chronological"
        limit: int = 10,
        max_tokens: int = 4000
    ) -> MemoryContext:
        """
        Multi-dimensional memory search.
        
        Examples:
        - retrieve(semantic="security", tags={"has_code": True})
        - retrieve(tags={"status": ["unresolved", "action_item"]}, date_range=("2025-01-01", None))
        - retrieve(semantic="credential management", sort="chronological")
        """
        pass
```

#### 3.5.5 CLI Tools
- [ ] `python -m hestia.memory.search` CLI tool:
  - `--semantic "query text"`
  - `--tags "topic:security,has_code:true"`
  - `--after "2025-01-01"`
  - `--before "2025-01-31"`
  - `--references "ADR-009"`
  - `--sort chronological|relevance`
- [ ] `python -m hestia.memory.tags list` - show tag taxonomy
- [ ] `python -m hestia.memory.tags add <chunk_id> "topic:security"` - manual tagging

#### 3.5.6 User-Facing Commands
- [ ] Hestia understands natural language queries:
  - "Show me all unresolved action items from last week"
  - "Find conversations where we made security decisions"
  - "How did my thinking on memory architecture evolve?"
- [ ] User can manually tag: "Tag this conversation as unresolved action item"

### Deliverables
- Extended SQLite schema with tags and metadata
- `hestia/memory/tagger.py` (auto-tagging pipeline)
- Enhanced `MemoryManager.retrieve()` with multi-dimensional queries
- CLI tools for searching and managing tags
- Documentation of tag taxonomy

### Testing Criteria
- [ ] Auto-tagging generates reasonable tags (manually review 10 examples)
- [ ] Tag-based search works: Find all conversations with `topic:security` AND `has_decision:true`
- [ ] Temporal search works: Find all chunks from last month
- [ ] Combined search works: Semantic + tags + temporal in one query
- [ ] Performance: Multi-dimensional query completes in <500ms
- [ ] Tagging is async (doesn't block conversation flow)

### Claude Checkpoint
Before proceeding to Phase 4, share:
- Sample auto-generated tags (verify quality)
- Example multi-dimensional query with results
- Performance metrics (query latency)
- Any challenges with tag taxonomy design

**Time estimate**: +4-5 hours to Phase 3

---

## Phase 4: Orchestration Layer (Week 6-7)
```python
# hestia/memory/manager.py
class MemoryManager:
    async def retrieve(
        self,
        query: str,
        scopes: list[MemoryScope],  # ephemeral, short_term, long_term, domain
        max_tokens: int = 4000,
    ) -> MemoryContext:
        """
        Retrieve relevant memory, respecting token budget.
        Returns structured context for prompt injection.
        """
        pass
    
    async def stage_update(
        self,
        update: MemoryUpdate,
    ) -> str:
        """
        Stage a memory update for human review.
        Returns staging ID.
        """
        pass
```

### Testing Criteria
- [ ] Vector search returns relevant results
- [ ] Short-term entries evict after TTL
- [ ] Staging workflow prevents direct long-term writes
- [ ] Memory retrieval respects token budget
- [ ] All operations logged

### Claude Checkpoint
Share:
- Your memory schema designs
- Sample retrieval results
- Staging workflow for review

---

## Phase 4: Orchestration Layer (Week 6-7)

### Objective
Build the orchestration logic that ties inference and memory together.

### Tasks

#### 4.1 Request Handler
- [ ] Parse incoming requests
- [ ] Validate request structure
- [ ] Assign request ID for tracing
- [ ] Route to appropriate workflow

#### 4.2 Prompt Construction
- [ ] System prompt templates
- [ ] Memory injection with clear boundaries
- [ ] User input formatting
- [ ] Token counting and truncation

#### 4.3 State Machine
- [ ] Define states: `received`, `processing`, `awaiting_tool`, `completed`, `failed`
- [ ] Define valid transitions
- [ ] Log all state changes
- [ ] Timeout handling per state

#### 4.4 Validation Pipeline
- [ ] Input validation (schema check)
- [ ] Output validation (structure, constraints)
- [ ] Retry with guidance on validation failure
- [ ] Graceful degradation on repeated failure

#### 4.5 Error Handling
- [ ] Categorize error types
- [ ] Appropriate response per error type
- [ ] Never expose internal errors to user
- [ ] Always log full error context

### Deliverables
- `hestia/orchestration/` module
- Request â†’ Response pipeline with logging
- State machine with validated transitions

### Code Structure
```python
# hestia/orchestration/handler.py
class RequestHandler:
    async def handle(self, request: Request) -> Response:
        """
        Main entry point for all requests.
        Orchestrates memory retrieval, inference, validation, and response.
        """
        pass

# hestia/orchestration/state.py
class TaskStateMachine:
    """
    Manages task state with logged transitions.
    Enforces valid state transitions.
    """
    pass
```

### Testing Criteria
- [ ] Valid requests produce valid responses
- [ ] Invalid requests return clear errors
- [ ] State transitions logged correctly
- [ ] Retry logic triggers on validation failure
- [ ] Graceful handling of inference failures

### Claude Checkpoint
Share:
- Your state machine design
- Prompt templates
- Sample request â†’ response flow with logs

---

## Phase 5: Execution Layer (Week 8)

### Objective
Enable tool execution with sandboxing and logging.

### Tasks

#### 5.1 Tool Registry
- [ ] Define tool interface (name, description, parameters, handler)
- [ ] Register available tools
- [ ] Tool discovery for prompt injection

#### 5.2 Tool Execution Engine
- [ ] Parse tool calls from model output
- [ ] Validate parameters
- [ ] Execute in sandboxed environment
- [ ] Capture output and errors
- [ ] Log everything

#### 5.3 Sandboxing
- [ ] Docker container for tool execution
- [ ] Limited file system access
- [ ] No network access by default
- [ ] Resource limits (CPU, memory, time)

#### 5.4 Built-in Tools
- [ ] `read_file`: Read file from allowed directories
- [ ] `write_file`: Write file (staged for review)
- [ ] `run_command`: Execute shell command (sandboxed)
- [ ] `search_web`: Web search (if desired)

### Deliverables
- `hestia/execution/` module
- Docker-based sandbox
- Initial tool set

### Testing Criteria
- [ ] Tools execute correctly in sandbox
- [ ] Sandbox prevents unauthorized access
- [ ] Tool failures handled gracefully
- [ ] All tool calls logged with inputs/outputs

### Claude Checkpoint
Share:
- Your tool interface design
- Sandbox configuration
- Security concerns for review

---

## Phase 6: Access Layer & Native App (Week 9-10)

### Objective
Enable secure remote access from any device via native Swift app.

### Tasks

#### 6.1 API Server
- [ ] FastAPI application
- [ ] Endpoint: `POST /v1/chat`
- [ ] Request/response schemas
- [ ] Async handling

#### 6.2 Authentication
- [ ] Device certificate generation
- [ ] Certificate validation middleware
- [ ] Optional TOTP for sensitive operations
- [ ] Session management

#### 6.3 Rate Limiting
- [ ] Per-device rate limits
- [ ] Global rate limits
- [ ] Graceful rejection with retry guidance

#### 6.4 Native Swift App (Xcode Project)
- [ ] Create HestiaApp.xcodeproj with iOS and macOS targets
- [ ] Shared code architecture (Models, Services, ViewModels)
- [ ] APIClient.swift for backend communication
- [ ] AuthService.swift with Face ID / Touch ID
- [ ] ChatView.swift matching Figma mockups
- [ ] CommandCenterView.swift for iPad/Mac
- [ ] Auto-lock functionality (15/30/60 minutes configurable)
- [ ] Push notification support respecting Focus modes

#### 6.5 iOS Shortcut Integration
- [ ] QuickCaptureIntent.swift for Shortcuts app
- [ ] Fire-and-forget input to Hestia
- [ ] Silent processing confirmation

### Deliverables
- `hestia/api/` module with FastAPI server
- `HestiaApp/` Xcode project with iOS and macOS targets
- Native app accessible at `https://hestia.your-tailnet:8443/`
- Device certificate management scripts
- iOS Shortcut for quick capture

### Testing Criteria
- [ ] API responds to authenticated requests
- [ ] Unauthenticated requests rejected
- [ ] Rate limiting enforced
- [ ] App runs on iPhone, iPad, Mac via Xcode
- [ ] Face ID / Touch ID authentication works
- [ ] Auto-lock triggers correctly
- [ ] iOS Shortcut successfully sends input to Hestia

### Claude Code Checkpoint
Share:
- API schema design
- Authentication flow
- SwiftUI views for review
- Security review of exposed surface

---

## Phase 7: Integration & Hardening (Week 11-12)

### Objective
Connect all components, test end-to-end, and harden for continuous operation.

### Tasks

#### 7.1 End-to-End Testing
- [ ] Test complete request flow
- [ ] Test memory persistence across sessions
- [ ] Test tool execution
- [ ] Test error scenarios
- [ ] Test from each device type

#### 7.2 Performance Tuning
- [ ] Profile inference latency
- [ ] Optimize memory retrieval
- [ ] Tune context window usage
- [ ] Benchmark under load

#### 7.3 Monitoring
- [ ] Health check endpoint
- [ ] Resource usage monitoring
- [ ] Alert on error rate spike
- [ ] Daily summary of activity

#### 7.4 Reliability
- [ ] Systemd service for auto-start
- [ ] Graceful shutdown handling
- [ ] Backup scripts for data
- [ ] Recovery procedure documentation

### Deliverables
- Fully integrated system
- Monitoring dashboard or alerts
- Backup and recovery procedures
- Operations runbook

### Testing Criteria
- [ ] System runs unattended for 48 hours
- [ ] Recovers gracefully from restart
- [ ] Handles 100 requests/hour sustained
- [ ] Memory persists correctly across restarts

---

## Phase 8: Iteration & Extension (Ongoing)

### Objective
Evolve the system based on actual usage.

### Activities
- Track which tasks Hestia handles well vs. poorly
- Identify patterns for custom tools
- Refine memory governance based on review burden
- Consider model upgrades as hardware allows
- Document learnings for future reference

### Claude's Role
Use Claude Opus for:
- Analyzing logs to identify improvement opportunities
- Reviewing proposed changes before implementation
- Debugging issues that require broad context
- Strategic decisions about system evolution

---

## Project File Structure

```
~/hestia/
â”œâ”€â”€ .venv/                      # Python virtual environment
â”œâ”€â”€ hestia/                     # Python backend
â”‚   â”œâ”€â”€ __init__.py
â”‚   â”œâ”€â”€ config/
â”‚   â”‚   â”œâ”€â”€ hestia-config.yaml      # Tia persona
â”‚   â”‚   â”œâ”€â”€ artemis-config.yaml     # Mira persona
â”‚   â”‚   â”œâ”€â”€ apollo-config.yaml      # Olly persona
â”‚   â”‚   â”œâ”€â”€ inference-config.yaml
â”‚   â”‚   â”œâ”€â”€ memory-config.yaml
â”‚   â”‚   â””â”€â”€ access-config.yaml
â”‚   â”œâ”€â”€ logging/
â”‚   â”‚   â”œâ”€â”€ __init__.py
â”‚   â”‚   â”œâ”€â”€ structured-logger.py
â”‚   â”‚   â””â”€â”€ log-viewer.py
â”‚   â”œâ”€â”€ inference/
â”‚   â”‚   â”œâ”€â”€ __init__.py
â”‚   â”‚   â””â”€â”€ inference-client.py
â”‚   â”œâ”€â”€ memory/
â”‚   â”‚   â”œâ”€â”€ __init__.py
â”‚   â”‚   â”œâ”€â”€ ephemeral-store.py
â”‚   â”‚   â”œâ”€â”€ vector-store.py
â”‚   â”‚   â”œâ”€â”€ structured-store.py
â”‚   â”‚   â”œâ”€â”€ user-model.py
â”‚   â”‚   â”œâ”€â”€ learning-queue.py
â”‚   â”‚   â”œâ”€â”€ staging-layer.py
â”‚   â”‚   â””â”€â”€ memory-manager.py
â”‚   â”œâ”€â”€ orchestration/
â”‚   â”‚   â”œâ”€â”€ __init__.py
â”‚   â”‚   â”œâ”€â”€ request-handler.py
â”‚   â”‚   â”œâ”€â”€ state-machine.py
â”‚   â”‚   â”œâ”€â”€ mode-manager.py
â”‚   â”‚   â”œâ”€â”€ prompt-builder.py
â”‚   â”‚   â””â”€â”€ autonomy-controller.py
â”‚   â”œâ”€â”€ execution/
â”‚   â”‚   â”œâ”€â”€ __init__.py
â”‚   â”‚   â”œâ”€â”€ tool-registry.py
â”‚   â”‚   â”œâ”€â”€ sandbox-runner.py
â”‚   â”‚   â””â”€â”€ tools/
â”‚   â”œâ”€â”€ persona/
â”‚   â”‚   â”œâ”€â”€ __init__.py
â”‚   â”‚   â”œâ”€â”€ tia-prompts.py
â”‚   â”‚   â”œâ”€â”€ mira-prompts.py
â”‚   â”‚   â””â”€â”€ olly-prompts.py
â”‚   â””â”€â”€ api/
â”‚       â”œâ”€â”€ __init__.py
â”‚       â”œâ”€â”€ server.py
â”‚       â”œâ”€â”€ auth-handler.py
â”‚       â””â”€â”€ notification-manager.py
â”œâ”€â”€ HestiaApp/                  # Swift native app (Xcode project)
â”‚   â”œâ”€â”€ HestiaApp.xcodeproj
â”‚   â”œâ”€â”€ Shared/                 # Shared across iOS and macOS
â”‚   â”‚   â”œâ”€â”€ Models/
â”‚   â”‚   â”œâ”€â”€ Services/
â”‚   â”‚   â”‚   â”œâ”€â”€ APIClient.swift
â”‚   â”‚   â”‚   â”œâ”€â”€ AuthService.swift
â”‚   â”‚   â”‚   â””â”€â”€ NotificationService.swift
â”‚   â”‚   â”œâ”€â”€ ViewModels/
â”‚   â”‚   â””â”€â”€ Utilities/
â”‚   â”œâ”€â”€ iOS/
â”‚   â”‚   â”œâ”€â”€ Views/
â”‚   â”‚   â”‚   â”œâ”€â”€ ChatView.swift
â”‚   â”‚   â”‚   â”œâ”€â”€ CommandCenterView.swift
â”‚   â”‚   â”‚   â””â”€â”€ SettingsView.swift
â”‚   â”‚   â””â”€â”€ Assets.xcassets
â”‚   â”œâ”€â”€ macOS/
â”‚   â”‚   â”œâ”€â”€ Views/
â”‚   â”‚   â””â”€â”€ Assets.xcassets
â”‚   â””â”€â”€ Intents/                # iOS Shortcuts
â”‚       â””â”€â”€ QuickCaptureIntent.swift
â”œâ”€â”€ admin/
â”‚   â”œâ”€â”€ dashboard/
â”‚   â””â”€â”€ scripts/
â”‚       â”œâ”€â”€ backup.sh
â”‚       â”œâ”€â”€ restore.sh
â”‚       â””â”€â”€ health-check.sh
â”œâ”€â”€ data/
â”‚   â”œâ”€â”€ vector/
â”‚   â”œâ”€â”€ structured.db
â”‚   â””â”€â”€ domain/
â”œâ”€â”€ logs/
â”œâ”€â”€ scripts/
â”‚   â””â”€â”€ setup.sh
â”œâ”€â”€ tests/
â”œâ”€â”€ docs/
â”‚   â”œâ”€â”€ runbook.md
â”‚   â””â”€â”€ recovery.md
â”œâ”€â”€ requirements.txt
â””â”€â”€ README.md
```

---

## Checklist Summary

### Phase 0: Environment
- [ ] Mac Mini configured with Tailscale
- [ ] Ollama installed with Mixtral 8x7B
- [ ] Project directory initialized
- [ ] Xcode installed and configured

### Phase 0.5: Security Foundation
- [ ] Separate hestia.keychain-db created
- [ ] hestia-keychain-cli Swift binary built
- [ ] CredentialManager Python module implemented
- [ ] Audit logging for credential access
- [ ] **CHECKPOINT 1**: Security foundation calibration ✓

### Phase 1: Logging
- [ ] Structured JSON logging with credential sanitization
- [ ] Separate audit log (7-year retention)
- [ ] Log rotation (90 days general, 7 years audit)
- [ ] CLI viewer

### Phase 2: Inference
- [ ] Ollama client wrapper with CredentialManager integration
- [ ] Token counting for context window management
- [ ] Retry logic
- [ ] Response validation
- [ ] Variable context window support (STANDARD/LARGE/XLARGE)
- [ ] Multi-stage retrieval for large context
- [ ] Cloud API fallback (Anthropic)

### Phase 3: Memory
- [ ] Ephemeral, vector, structured stores
- [ ] Staging layer
- [ ] Memory manager with token budgeting
- [ ] Encryption for sensitive user model fields

### Phase 3.5: Tag-Based Memory Schema (NEW)
- [ ] Tag taxonomy defined
- [ ] Extended SQLite schema (tags + metadata)
- [ ] Auto-tagging pipeline (async)
- [ ] Multi-dimensional search (semantic + tags + temporal)
- [ ] CLI tools for tag management
- [ ] **CHECKPOINT 2**: Inference & memory calibration ✓

### Phase 4: Orchestration
- [ ] Request handler
- [ ] State machine
- [ ] Mode manager (Tia/Mira/Olly)
- [ ] Validation pipeline
- [ ] **CHECKPOINT 3**: Orchestration calibration ✓

### Phase 5: Execution
- [ ] Tool registry
- [ ] Sandboxed execution
- [ ] Built-in tools
- [ ] External communication gate

### Phase 5.5: Apple Ecosystem Integration
- [ ] hestia-reminders-cli (Swift + EventKit)
- [ ] hestia-calendar-cli (Swift + EventKit)
- [ ] hestia-notes-cli (Swift + AppleScript for v1.0)
- [ ] Apple Mail SQLite reader
- [ ] Python wrappers for each CLI
- [ ] Integration tests
- [ ] **CHECKPOINT 4**: Execution & Apple integration calibration ✓

### Phase 6: Access & App
- [ ] FastAPI server
- [ ] Certificate auth via Tailscale
- [ ] Native Swift app (iOS + macOS)
- [ ] Face ID / Touch ID
- [ ] iOS Shortcut integration
- [ ] **CHECKPOINT 5**: iOS app calibration ✓

### Phase 7: Integration
- [ ] End-to-end testing
- [ ] Monitoring
- [ ] Reliability hardening
- [ ] Security testing (from security architecture doc)
- [ ] **CHECKPOINT 6**: Production readiness calibration ✓

### Phase 8: Iteration
- [ ] Continuous improvement based on usage
