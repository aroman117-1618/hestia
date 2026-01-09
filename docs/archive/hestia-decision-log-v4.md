# Hestia: Architectural Decision Log

Record significant decisions here. This creates institutional memory and prevents re-litigating resolved questions.

---

## Template

```markdown
## ADR-[NUMBER]: [Title]

**Date**: YYYY-MM-DD
**Status**: Proposed | Accepted | Deprecated | Superseded by ADR-X

### Context
[What situation prompted this decision?]

### Decision
[What did we decide?]

### Alternatives Considered
[What other options were evaluated?]

### Consequences
[What are the implications—good and bad?]

### Notes
[Any additional context or caveats]
```

---

## Decisions

### ADR-001: Mixtral 8x7B as Primary Model

**Date**: 2025-01-08
**Status**: Accepted

#### Context
Need to select a model that runs locally on Mac Mini with 64GB unified memory while providing reasonable capability for general tasks.

#### Decision
Use Mixtral 8x7B-Instruct with Q4_K_M quantization as the primary and only local model.

#### Alternatives Considered
- **Mixtral 8x22B**: Better capability but requires ~80-90GB memory. Not viable on current hardware.
- **Llama 3 70B**: Also exceeds memory capacity with reasonable quantization.
- **Smaller models (7B class)**: Fit easily but capability too limited for target use cases.
- **Cloud API fallback**: Adds complexity, latency, and dependency. Deferred to v1.5.

#### Consequences
- Positive: Fits comfortably in memory, good inference speed, strong multilingual support
- Negative: Capability ceiling for complex tasks; some requests may exceed model ability
- Negative: Text-only (no vision capabilities)
- Mitigation: Multi-stage retrieval for large context; cloud fallback in v1.5 for vision

---

### ADR-002: Governed Memory Persistence

**Date**: 2025-01-08
**Status**: Accepted

#### Context
LLMs hallucinate. If the model can freely persist to long-term memory, incorrect information will accumulate and degrade future responses.

#### Decision
All proposed long-term memory updates are staged for human review before commitment. The model cannot directly write to long-term storage.

**Exception (ADR-014)**: Explicitly-requested background tasks (Quick Chat, iOS Shortcut) auto-persist outputs with full audit trail, since the user explicitly initiated the action.

#### Alternatives Considered
- **Automatic persistence**: Simpler but risks memory pollution
- **Confidence-based filtering**: Model self-assesses confidence before persisting. Unreliable.
- **Time-delayed persistence**: Auto-commit after N days without contradiction. Still risky.

#### Consequences
- Positive: Memory remains clean; human maintains control over knowledge base
- Negative: Creates review burden; delays memory availability
- Mitigation: Batch reviews (daily/weekly); provide good tooling for review workflow
- Mitigation: Background tasks bypass staging since user explicitly requested action

---

### ADR-003: Single-Agent Architecture

**Date**: 2025-01-08
**Status**: Accepted

#### Context
Multi-agent systems can solve complex problems by delegating subtasks to specialized agents. However, they introduce coordination complexity, drift, and debugging difficulty.

#### Decision
Hestia uses a single model instance with explicit orchestration logic (code-based state machines and rules), not multi-agent coordination.

#### Alternatives Considered
- **Multi-agent with coordinator**: More capability but harder to debug and predict
- **Tool-using agent swarm**: Flexible but emergent behavior is hard to control
- **Hybrid (local + cloud agents)**: Complexity of multi-agent plus cloud dependency

#### Consequences
- Positive: Behavior is predictable; debugging is tractable; no coordination overhead
- Negative: Complex tasks must be decomposed in code, not by agents
- Mitigation: Good orchestration framework; clear task decomposition patterns

---

### ADR-004: Observability as Primary Reliability Strategy

**Date**: 2025-01-08
**Status**: Accepted

#### Context
"Determinism" is often cited as a goal, but LLM inference is inherently stochastic. Even temperature=0 doesn't guarantee identical outputs.

#### Decision
Prioritize complete observability (comprehensive logging, request tracing, replay capability) over attempts at determinism. "Reproducible" means "can reconstruct conditions," not "identical output."

#### Alternatives Considered
- **Pursue determinism**: Would require custom inference engine, still wouldn't fully work
- **Caching**: Cache responses for identical inputs. Limits flexibility, storage-intensive.

#### Consequences
- Positive: Realistic expectations; debugging is possible; can learn from variations
- Negative: Must accept output variability; some users may expect determinism
- Mitigation: Clear documentation; validation checkpoints catch problematic outputs

---

### ADR-005: Tailscale for Remote Access

**Date**: 2025-01-08
**Status**: Accepted

#### Context
Need secure remote access from multiple devices without exposing ports to public internet.

#### Decision
Use Tailscale for all remote access. Devices join a private tailnet; no public exposure.

#### Alternatives Considered
- **Port forwarding + HTTPS**: Exposes attack surface; requires dynamic DNS
- **Cloudflare Tunnel**: Third-party dependency; traffic routes through Cloudflare
- **VPN server on Mac Mini**: More setup; Tailscale handles this better

#### Consequences
- Positive: Zero-config, encrypted, no exposed ports, works from anywhere
- Negative: Tailscale dependency; requires Tailscale account
- Mitigation: Tailscale is reliable; self-hosted Headscale is fallback option

---

### ADR-006: Docker Sandboxing for Tool Execution

**Date**: 2025-01-08
**Status**: Accepted

#### Context
Hestia executes tools (run commands, read/write files). Unrestricted execution is a security risk.

#### Decision
All tool execution occurs in Docker containers with limited filesystem access, no network by default, and resource constraints.

#### Alternatives Considered
- **No sandboxing**: Simpler but dangerous if model produces malicious commands
- **macOS sandbox-exec**: Less flexible than Docker; platform-specific
- **Firecracker/microVMs**: Overkill for this use case

#### Consequences
- Positive: Tool execution is isolated; host system protected
- Negative: Docker overhead; some tools may need special configuration
- Mitigation: Pre-configure containers for common tool patterns

---

### ADR-007: Claude Code + Xcode as Minimal Development Stack

**Date**: 2025-01-08
**Status**: Accepted

#### Context
Need to select development tooling that balances power with simplicity. Andrew is learning as he builds and wants to minimize cognitive overhead from tools.

#### Decision
Use exactly two tools:
- **Claude Code**: Primary development driver (AI implements, Andrew reviews)
- **Xcode**: Single IDE for everything (Swift apps, Python editing, Git, file browsing)

#### Alternatives Considered
- **Claude Code + VS Code + Xcode**: VS Code is redundant since Xcode handles all IDE needs
- **Claude Code + Cursor**: Cursor's AI features redundant with Claude Code
- **Electron app to avoid Xcode**: Would lose native iOS features and require additional tooling anyway

#### Consequences
- Positive: Minimal stack (two tools), no IDE redundancy, leverages Xcode's full capabilities
- Positive: Native Swift app enables full iOS features (Face ID, Shortcuts, push notifications)
- Negative: Xcode's Python/YAML support is basic compared to VS Code
- Mitigation: Claude Code handles code quality; Xcode is just for viewing and running

---

### ADR-008: Native Swift App over Electron/Web

**Date**: 2025-01-08
**Status**: Accepted

#### Context
Need to build the Hestia client app for iPhone, iPad, and Mac. Options include native Swift, Electron, or progressive web app.

#### Decision
Build a native SwiftUI app with shared codebase across iOS and macOS.

#### Alternatives Considered
- **Electron**: Cross-platform but can't run on iOS; would need web fallback for mobile
- **Progressive Web App**: Works everywhere but limited iOS features (no real push notifications, no Shortcuts integration, no Face ID)
- **React Native**: Cross-platform including iOS, but adds complexity and another framework to learn

#### Consequences
- Positive: Full native features (Face ID, Touch ID, iOS Shortcuts, proper push notifications)
- Positive: Clean, snappy performance
- Positive: Single codebase for iOS and macOS via SwiftUI
- Negative: Requires learning Swift (but Claude Code will implement most of it)
- Negative: Requires Xcode (but we need an IDE anyway)

---

### ADR-009: Credential Management Architecture

**Date**: 2025-01-08
**Status**: Accepted

#### Context
Hestia needs to store and manage various credentials (API keys, sensitive user data like SSN/financial info) with "Pentagon-level" security. The system must balance maximum security with usability, and support future multi-user expansion.

#### Decision
Use macOS Keychain with Secure Enclave integration, organized into three partitions:
1. **hestia.operational**: API keys (Anthropic, Weather, Search) - optional biometric
2. **hestia.sensitive**: User secrets (SSN, credit cards, medical) - REQUIRES Face ID
3. **hestia.system**: Master encryption key - REQUIRES Face ID

All credentials double-encrypted: Fernet (Python) pre-encryption + Keychain's AES-256.

#### Alternatives Considered
- **Encrypted SQLite only**: More complex, still needs Keychain for master key bootstrap
- **1Password/External manager**: Adds dependency, doesn't integrate with Secure Enclave
- **HashiCorp Vault**: Massive overkill for personal use, another service to maintain

#### Consequences
- Positive: Hardware-backed security (Secure Enclave), biometric gates for sensitive data, complete audit trail
- Positive: Keychain is zero-setup, macOS-native, integrates with Face ID
- Positive: Separate partition isolates Hestia's secrets from user's personal passwords
- Negative: OAuth token management (v1.5+) will require adding SQLCipher for token refresh tracking
- Mitigation: Hybrid approach in v1.5—Keychain for static secrets, SQLCipher for OAuth tokens

#### Notes
- Master key never leaves Secure Enclave (hardware security)
- Every credential access logged with reason (audit trail)
- v2.0 will add per-user partitioning for multi-user support

---

### ADR-010: External API Strategy

**Date**: 2025-01-08
**Status**: Accepted (Updated 2025-01-09)

#### Context
Hestia needs external APIs for capabilities beyond local model (weather, web search). Must balance capability with cost and security.

#### Decision
**v1.0 External Services**:
- **Weather**: OpenWeatherMap API (free tier, 1000 calls/day)
- **Web Search**: Brave Search API (free tier, 2000 queries/month)

**Deferred to v1.5+**:
- Anthropic API (Cloud LLM for vision/large context) - most cases handled by multi-stage retrieval locally
- Gmail API (OAuth) - for sending emails programmatically
- Google Drive API (OAuth) - for file migration

**Apple ecosystem accessed via native integration** (no OAuth needed):
- Apple Mail: Read via SQLite database query
- Apple Calendar: Full CRUD via EventKit (Calendar.app already authenticated)
- Notes/Reminders: Swift CLIs via native frameworks

#### Alternatives Considered
- **All-local (no external APIs)**: Limits capability (no weather, no web search)
- **Gmail/GDrive OAuth in v1.0**: Adds complexity, not needed since Apple Mail/Calendar already sync
- **Other search APIs**: Google (expensive), Bing (free but lower quality), Perplexity (no free tier)

#### Consequences
- Positive: Weather and search enable proactive features (research, calendar insights)
- Positive: Skipping OAuth and cloud LLM in v1.0 simplifies security architecture
- Positive: Multi-stage retrieval handles 99%+ of large context needs locally
- Negative: Monthly cost for APIs (~$10-20/month if free tiers exceeded)
- Negative: Email sending deferred to v1.5 (Hestia drafts, user sends manually)
- Negative: Vision/screen capture deferred to v1.5 (requires cloud API)
- Mitigation: Monitor API usage, set budget alerts, rate-limit to stay within free tiers

#### Notes
- Apple Mail already syncs Gmail via IMAP (read access free)
- Apple Calendar already syncs Google Calendar via CalDAV (full CRUD free)
- SMTP with app password is simpler than Gmail API OAuth for email sending (consider for v1.5)

---

### ADR-011: Context Window Management

**Date**: 2025-01-08
**Status**: Accepted

#### Context
Mixtral 8x7B has 32K token context window (~24K words). If we inject user model + conversation history + research + tool definitions, we'll hit limits quickly. Need aggressive management strategy.

#### Decision
Implement token budget system with priority-based allocation:

**Token Budget Allocation** (32K total):
- System prompt: 2K tokens (fixed)
- Tool definitions: 1K tokens (fixed)
- User model (current): 2K tokens (summarized)
- Conversation history: Up to 20K tokens (sliding window)
- Memory retrieval: Up to 4K tokens (RAG-filtered)
- User input: Remaining (~3K tokens)

**Management strategies**:
1. **Sliding window**: Keep last N messages in full, summarize older messages
2. **RAG pattern**: Retrieve only relevant memory chunks (not entire history)
3. **Compression**: Aggressive summarization for messages >10 exchanges old
4. **Token counting**: Log actual usage per request, alert if >28K (90% threshold)
5. **Multi-stage retrieval**: For large context, retrieve → summarize → synthesize (stays local)

#### Alternatives Considered
- **No management**: Will hit 32K limit within ~5-10 conversation turns (unacceptable)
- **Aggressive truncation**: Keep only last 3 messages (loses context)
- **Cloud fallback for every large request**: Expensive, unnecessary for most cases

#### Consequences
- Positive: Can maintain long conversations without hitting context limits
- Positive: Multi-stage retrieval handles most large context needs locally (free)
- Positive: Logging token usage enables optimization over time
- Negative: Summarization may lose nuance from older messages
- Negative: Adds complexity to prompt construction
- Mitigation: Retrieval-augmented generation (RAG) ensures relevant old context is surfaced

#### Notes
- Monitor actual token usage in production to tune budget allocation
- Cloud fallback (v1.5) only when multi-stage retrieval is insufficient (rare)
- 32K is actually ideal for Hestia's chatbot use case—forces good retrieval architecture

---

### ADR-012: Apple Ecosystem Integration (OAuth-Free Approach)

**Date**: 2025-01-08
**Status**: Accepted

#### Context
Hestia needs full CRUD access to Apple Notes, Reminders, Calendar, and read access to Apple Mail. User's Gmail account already synced to Apple Mail/Calendar via native integration.

#### Decision
**No OAuth required** for Apple ecosystem in v1.0. Use native access methods:

**Apple Mail** (Read-Only):
- Access via SQLite query: `~/Library/Mail/V10/MailData/Envelope Index`
- Full email history already synced via IMAP
- No credentials needed (Mail.app authenticated)

**Apple Calendar** (Full CRUD):
- Swift CLI tool using EventKit framework
- Access all calendars Calendar.app can access (including Google Calendar)
- No credentials needed (Calendar.app authenticated)

**Apple Reminders** (Full CRUD):
- Swift CLI tool using EventKit framework
- Native API supports all features (subtasks, priorities, due dates)
- No credentials needed

**Apple Notes** (Text-Only for v1.0):
- Swift CLI tool wrapping AppleScript (tactical v1.0 solution)
- Supports title, body (text), folder assignment
- Attachments deferred to v1.5 (requires CloudKit reverse-engineering)

**Email Sending** (Deferred to v1.5):
- v1.0: Hestia drafts email, user sends via Mail.app manually
- v1.5: Add SMTP with app password (simpler than Gmail API OAuth)

#### Alternatives Considered
- **Gmail/GDrive API with OAuth**: Unnecessary—Apple apps already provide access
- **AppleScript for everything**: Fragile for Calendar/Reminders (EventKit is more robust)
- **PyObjC bridge**: Clunky, poorly documented, not worth complexity

#### Consequences
- Positive: No OAuth complexity in v1.0 (faster development)
- Positive: Native EventKit APIs are stable and well-documented
- Positive: User gets full CRUD on Google Calendar via Apple Calendar integration
- Negative: Email sending requires manual step in v1.0
- Negative: Notes attachment handling deferred to v1.5
- Mitigation: Manual email sending acceptable for MVP; most notes are text-only

#### Notes
- User must have Google account added in System Settings → Internet Accounts
- EventKit requires one-time permission prompt (macOS will ask user)
- Swift CLI tools in Phase 5.5 provide robust, future-proof integration

---

### ADR-013: Memory Query Architecture (Tag-Based Schema)

**Date**: 2025-01-08
**Status**: Accepted

#### Context
Traditional RAG (semantic search only) is insufficient for Hestia's long-term memory needs. Need multi-dimensional querying: semantic similarity + temporal filters + categorical tags + relationship traversal. Inspired by Datadog's tag-based observability model.

#### Decision
Implement **hybrid memory architecture** with tag-based schema:

**Storage**:
- **ChromaDB** (vector store): Embeddings for semantic search
- **SQLite** (structured store): Tags, metadata, relationships
- Linked by `chunk_id`

**Schema**:
```python
class ConversationChunk:
    id: str                    # UUID
    session_id: str
    timestamp: datetime
    content: str
    embedding: List[float]     # ChromaDB
    
    # Tag-based metadata (SQLite)
    tags: {
        "topics": ["security", "encryption"],
        "entities": ["Face ID", "Secure Enclave"],
        "people": ["andrew"],
        "mode": ["Tia"],
        "phase": ["design"],
        "status": ["active", "unresolved"]
    }
    
    metadata: {
        "has_code": bool,
        "has_decision": bool,
        "has_action_item": bool,
        "sentiment": str,
        "confidence": float
    }
    
    references: List[str]      # Links to other chunks
    supersedes: Optional[str]  # If this updates old info
```

**Auto-Tagging**: Use Mixtral to generate tags from conversation content (async, non-blocking).

**Query Examples**:
- Semantic + tags: `search(semantic="security", tags={"has_code": True})`
- Temporal: `search(tags={"status": "unresolved"}, date_range="last_month")`
- Relationship: `search(references=["ADR-009"])`

#### Alternatives Considered
- **Vector DB only**: No structured queries (can't filter by date, status, etc.)
- **SQL full-text search**: Poor semantic understanding, no embeddings
- **Graph database**: Overkill for relationships, adds complexity

#### Consequences
- Positive: Multi-dimensional queries (semantic + tags + temporal + relational)
- Positive: Enables "Datadog-style" observability of memory ("show me all unresolved action items")
- Positive: Tracks evolution ("how did my thinking on X change over time?")
- Negative: Adds complexity (two storage systems, tagging pipeline)
- Negative: Auto-tagging adds latency (mitigated by async execution)
- Mitigation: Tagging is async/non-blocking; queries are fast (indexed SQLite + ChromaDB)

#### Notes
- Tagging happens after conversation turn (user doesn't wait)
- User can manually add/edit tags: "Tag this as unresolved action item"
- Batch re-tagging possible when improving tagger model
- Phase 3.5 implementation (~4-5 hours additional work)

---

### ADR-014: Background Tasks and Asynchronous Execution

**Date**: 2025-01-09
**Status**: Accepted

#### Context
Users want to submit quick commands via iOS Shortcut (v1.0) or macOS Quick Chat (v1.5) and have Hestia work on them in the background. This requires:
- Asynchronous task execution
- Persistent task tracking
- Notification on completion
- Visibility into task history (Activity Timeline)
- Clear autonomy rules for what can execute without confirmation

#### Decision
Implement **Background Task Management** with the following architecture:

**Task Lifecycle**:
1. **Submission**: User sends task via Quick Chat/iOS Shortcut
2. **Acknowledgment**: Immediate "Got it ✓" confirmation
3. **Processing**: Task queued and executed asynchronously
4. **Completion**: Push notification sent (respects Focus modes)
5. **Persistence**: Results stored in Activity Timeline

**Task Storage** (SQLite):
```sql
CREATE TABLE background_tasks (
    id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    completed_at DATETIME,
    status TEXT NOT NULL,  -- 'pending', 'in_progress', 'completed', 'failed', 'awaiting_approval'
    source TEXT NOT NULL,  -- 'quick_chat', 'ios_shortcut', 'conversation', 'scheduled'
    input_summary TEXT,    -- "Schedule dentist for next Tuesday"
    output_summary TEXT,   -- "Added to calendar: Tuesday 2pm"
    output_details TEXT,   -- JSON with full details
    autonomy_level INTEGER,-- Level used for this task
    escalated BOOLEAN DEFAULT FALSE,  -- True if escalated from L3 to L2
    notification_sent BOOLEAN DEFAULT FALSE,
    
    INDEX idx_status (status),
    INDEX idx_created (created_at)
);
```

**Autonomy Model for Background Tasks**:

| Task Type | Default Level | Behavior |
|-----------|---------------|----------|
| Internal actions (calendar, reminders, notes) | Level 3 | Execute → Notify when done |
| Research (web search, memory search) | Level 3 | Execute → Notify with summary |
| External communication | Level 2 | Draft → Notify for approval → Execute after approval |
| Financial transactions | Level 2 | Never auto-execute from background |
| Data deletion | Level 2 | Never auto-execute from background |
| Credential access | Level 2 | Requires biometric + approval |

**Escalation Flow**:
- If task requires action in "always-require-approval" category, status becomes `awaiting_approval`
- Notification prompts user: "Ready to send email. Review and approve?"
- User approves in Activity Timeline → task executes → completion notification

**Output Persistence**:
- Background task outputs auto-persist to memory layer (no staging required)
- Full audit trail maintained (task ID, timestamps, inputs, outputs)
- Outputs linked to memory for future retrieval ("What did I ask you to research last week?")

**Activity Timeline** (UI Component):
- Shows all background task history
- Filters: completed, in-progress, awaiting approval
- Each task expandable for full details
- Quick actions: approve, cancel, retry

#### Alternatives Considered
- **No background tasks**: All interactions synchronous. Limits utility for quick capture.
- **Level 4 (silent) for all background tasks**: Too risky; external communication could happen silently.
- **All background tasks require approval**: Too much friction; defeats "fire-and-forget" purpose.

#### Consequences
- Positive: Fire-and-forget quick capture works as expected
- Positive: User maintains control over sensitive actions via escalation
- Positive: Full visibility into what Hestia has done (Activity Timeline)
- Positive: Outputs are searchable in memory ("what did I ask you to do last month?")
- Negative: Adds complexity (task queue, state management, notifications)
- Negative: Risk of notification fatigue if user submits many background tasks
- Mitigation: Notifications respect Focus modes; batch notifications possible in future

#### Notes
- iOS Shortcut quick capture (v1.0) uses same task queue infrastructure
- macOS Quick Chat (v1.5) is identical pattern, different input method
- Activity Timeline is part of Command Center view (iPad/Mac)
- Phase 4.5 implements core task management; Phase 6 implements UI

---

## Adding New Decisions

When making a significant architectural decision:

1. Copy the template above
2. Fill in all sections
3. Add to this log
4. Reference the ADR number in related code comments

Decisions worth logging:
- Technology choices (databases, frameworks, protocols)
- Structural decisions (how components interact)
- Trade-off resolutions (choosing between competing approaches)
- Scope decisions (what's in/out of scope)

Not worth logging:
- Implementation details that can easily change
- Obvious choices with no real alternatives
- Temporary workarounds (track these separately)
