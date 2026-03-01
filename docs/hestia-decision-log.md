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
[What are the implicationsâ€”good and bad?]

### Notes
[Any additional context or caveats]
```

---

## Decisions

### ADR-001: Qwen 2.5 7B as Primary Model

**Date**: 2025-01-08
**Status**: Accepted (Updated 2025-01-12)

#### Context
Need to select a model that runs locally on Mac Mini with 16GB unified memory.

#### Decision
Use Qwen 2.5 7B as the primary and only local model for v1.0.

#### Hardware Upgrade Path
When Mac Mini is upgraded to 64GB RAM:
1. Change `primary_model` in inference config to `mixtral:8x7b-instruct-v0.1-q4_K_M`
2. Qwen becomes optional fallback for simple queries (faster)
3. No code changes required—configuration only

#### Alternatives Considered
- **Mixtral 8x7B**: Better capability but requires ~28GB+ memory. Not viable on 16GB hardware.
- **Cloud API fallback**: Adds complexity, cost, and external dependency. Rejected.

#### Consequences
- Positive: Fits comfortably in 16GB, fast inference (<5 seconds)
- Positive: Architecture ready for Mixtral upgrade (config change only)
- Negative: Capability ceiling for complex reasoning tasks
- Mitigation: Multi-stage retrieval handles context limits; graceful errors for capability limits

---

### ADR-002: Governed Memory Persistence

**Date**: 2025-01-08
**Status**: Accepted

#### Context
LLMs hallucinate. If the model can freely persist to long-term memory, incorrect information will accumulate and degrade future responses.

#### Decision
All proposed long-term memory updates are staged for human review before commitment. The model cannot directly write to long-term storage.

#### Alternatives Considered
- **Automatic persistence**: Simpler but risks memory pollution
- **Confidence-based filtering**: Model self-assesses confidence before persisting. Unreliable.
- **Time-delayed persistence**: Auto-commit after N days without contradiction. Still risky.

#### Consequences
- Positive: Memory remains clean; human maintains control over knowledge base
- Negative: Creates review burden; delays memory availability
- Mitigation: Batch reviews (daily/weekly); provide good tooling for review workflow

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
**Status**: Superseded (2025-01-12)

**Superseded By**: Current implementation uses file-based sandboxing with path allowlists (`execution.yaml`) and subprocess isolation instead of Docker containers. Docker overhead was unnecessary for single-user local deployment.

#### Context
Hestia executes tools (run commands, read/write files). Unrestricted execution is a security risk.

#### Decision (Original)
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
Use only two tools:
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
1. **hestia.operational**: API keys (Weather, Search) - optional biometric
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
**Status**: Accepted (Updated 2025-01-12)

#### Context
Hestia needs external APIs for capabilities beyond local model (weather, web search). Must balance capability with cost and security.

#### Decision
**v1.0 External Services**:
- **Weather**: OpenWeatherMap API (free tier, 1000 calls/day)
- **Web Search**: Brave Search API (free tier, 2000 queries/month)

**Cloud LLM**: Not used. All inference is local via Qwen 2.5 7B (v1.0) or Mixtral 8x7B (post-hardware upgrade).

**Deferred to v1.5+**:
- Gmail API (OAuth) - for sending emails programmatically
- Google Drive API (OAuth) - for file migration

**Apple ecosystem accessed via native integration** (no OAuth needed):
- Apple Mail: Read via SQLite database query
- Apple Calendar: Full CRUD via EventKit (Calendar.app already authenticated)
- Notes/Reminders: Swift CLIs via native frameworks

#### Alternatives Considered
- **All-local (no external APIs)**: Limits capability (no weather, no web search)
- **Cloud LLM fallback**: Adds complexity, cost, and external dependency. Rejected.
- **Gmail/GDrive OAuth in v1.0**: Adds complexity, not needed since Apple Mail/Calendar already sync
- **Other search APIs**: Google (expensive), Bing (free but lower quality), Perplexity (no free tier)

#### Consequences
- Positive: Weather and search enable proactive features (research, calendar insights)
- Positive: Local-only inference maintains privacy and reduces cost
- Positive: Skipping OAuth in v1.0 simplifies security architecture
- Negative: Email sending deferred to v1.5 (Hestia drafts, user sends manually)
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

#### Alternatives Considered
- **No management**: Will hit 32K limit within ~5-10 conversation turns (unacceptable)
- **Aggressive truncation**: Keep only last 3 messages (loses context)
- **External memory**: Store full history externally, retrieve on-demand (adds latency, complex)

#### Consequences
- Positive: Can maintain long conversations without hitting context limits
- Positive: Logging token usage enables optimization over time
- Negative: Summarization may lose nuance from older messages
- Negative: Adds complexity to prompt construction
- Mitigation: Retrieval-augmented generation (RAG) ensures relevant old context is surfaced even if not in full history

#### Notes
- Monitor actual token usage in production to tune budget allocation
- Multi-stage retrieval handles most context needs
- Hardware upgrade to 64GB enables Mixtral 8x7B for more complex tasks (config change only)

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

### ADR-014: Confidence-Based Preference Learning

**Date**: 2025-01-09
**Status**: Accepted

#### Context
Hestia learns user preferences over time (communication style, topics of interest, scheduling patterns). However, preferences evolve—what was true six months ago may no longer apply. Need a mechanism to track certainty level and handle preference decay.

#### Decision
Implement confidence-tracked preference learning:
- Track confidence scores (0.0-1.0) for all learned preferences
- Decay mechanics: Reduce confidence by 10% per month without reinforcement
- User corrections immediately set confidence to 1.0
- Preferences below 0.3 confidence are treated as unlearned
- Store as extension to Phase 3.5 memory schema (SQLite)

**Confidence thresholds**:
- 1.0: Just confirmed/corrected by user
- 0.7-0.99: High confidence, use in prompts
- 0.3-0.69: Medium confidence, use with hedging
- <0.3: Treat as unlearned, don't use

#### Alternatives Considered
- **No decay**: Preferences never expire (stale data accumulates)
- **Fixed TTL**: Preferences expire after N days (loses gradual transition)
- **Explicit user management**: User manually updates preferences (too much burden)

#### Consequences
- Positive: Prevents outdated preferences from overriding current behavior
- Positive: Self-correcting system (wrong preferences naturally fade)
- Negative: Adds complexity to preference lookup
- Mitigation: Simple decay formula, indexed queries, cron job for batch decay

#### Notes
- Decay runs as background task (Phase 4.5)
- User can view confidence levels: "What do you know about my preferences?"
- Phase 3.6 implementation builds on Phase 3.5 tag-based schema

---

### ADR-015: Background Task Architecture

**Date**: 2025-01-09
**Status**: Deprecated (2025-01-12)

#### Deprecation Reason
Superseded by ADR-021 which provides a more comprehensive background task architecture with Activity Timeline integration and governed auto-persistence.

---

### ADR-015-ORIGINAL: Background Task Architecture (Deprecated)

**Date**: 2025-01-09
**Status**: Deprecated

#### Context
Some Hestia tasks require extended execution time:
- Deep research ("Research best practices for X and summarize")
- Batch operations ("Tag all conversations from last month")
- Multi-step analysis ("Analyze my calendar patterns over 6 months")

These tasks can take minutes to hours. Blocking the conversation during execution is unacceptable.

#### Decision
Implement SQLite-backed async task queue:
- **Task states**: pending, running, completed, failed, cancelled
- **Persistence**: Tasks survive process restarts
- **Progress tracking**: Percentage completion + status messages
- **Notifications**: Push (iOS) or log entries on completion
- **Resource limits**: Max 2 concurrent background tasks
- **Cancellation**: Graceful interrupt via signal

**Task schema**:
```python
class BackgroundTask:
    id: str              # UUID
    type: str            # "research", "analysis", "batch"
    description: str     # Human-readable task description
    status: TaskStatus   # pending/running/completed/failed/cancelled
    progress: float      # 0.0 to 1.0
    status_message: str  # Current step description
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    result: Optional[str]  # JSON-serialized result
    error: Optional[str]   # Error message if failed
```

#### Alternatives Considered
- **Synchronous only**: Block until complete (poor UX for long tasks)
- **External queue (Redis/RabbitMQ)**: Overkill for single-user system
- **In-memory queue**: Doesn't survive restarts

#### Consequences
- Positive: Enables "research this and get back to me" workflows
- Positive: Non-blocking conversation during long operations
- Negative: Adds queue management complexity
- Negative: User must check back for results
- Mitigation: Simple FIFO queue, push notifications, clear status UI

#### Notes
- Phase 4.5 implementation
- Integrates with Phase 9 (Proactive Intelligence) for notifications
- CLI: `python -m hestia.tasks list`, `python -m hestia.tasks cancel <id>`

---

### ADR-016: Hybrid Inference Architecture

**Date**: 2025-01-09
**Status**: Implemented (2026-02-15, via WS1 Cloud LLM)

#### Status Update
Originally deprecated (2025-01-12) when cloud fallback was removed from the roadmap. Re-implemented as part of WS1 (Cloud LLM Integration) with 3-state routing: disabled → enabled_smart → enabled_full. See ADR-025 for full details.

---

### ADR-016-ORIGINAL: Hybrid Inference Architecture (Deprecated)

**Date**: 2025-01-09
**Status**: Deprecated

#### Context
Original design assumed Mac Mini with 64GB RAM running Mixtral 8x7B (28GB model). Actual hardware has 16GB RAM, causing severe performance issues:
- Only ~45% of model fits in VRAM
- Simple queries timeout after 5+ minutes
- Model runner consumes 31% of total memory

Need alternative architecture that provides acceptable performance on current hardware while preserving path to future upgrade.

#### Decision
Implement three-tier hybrid inference with smart routing:

**Tier 1 - Primary (Local Fast)**:
- Model: Qwen 2.5 7B
- Use case: Routine queries, quick responses
- Performance: ~1-5 seconds response time
- Cost: Free (local)

**Tier 2 - Complex (Local Large)** - DISABLED:
- Model: Mixtral 8x7B-Instruct (Q4_K_M)
- Use case: Complex reasoning (when 64GB RAM available)
- Status: Disabled until hardware upgrade
- Config preserved for future activation

**Tier 3 - Cloud (Fallback)**:
- Model: Claude Sonnet (claude-sonnet-4-20250514)
- Use case: Fallback when local fails, complex analysis
- Cost: ~$0.003 per 1K input tokens, ~$0.015 per 1K output tokens

**Routing rules**:
- Default: Primary (Qwen 2.5 7B)
- Pattern match ("analyze", "debug", "explain complex"): Route to Cloud
- Token count > 500: Route to Complex (when enabled) or Cloud
- After 2 consecutive local failures: Auto-escalate to Cloud

**Implementation**:
- `ModelRouter` class in `hestia/inference/router.py`
- `CloudInferenceClient` in `hestia/inference/cloud.py`
- API key via CredentialManager (operational tier)
- All cloud calls logged with token counts for cost tracking

#### Alternatives Considered
- **Mixtral only**: Unacceptable 5+ minute timeouts
- **Cloud only**: Expensive, loses local-first philosophy
- **Smaller quantized Mixtral**: Still too large for 16GB
- **Different large model**: Qwen 72B, Llama 70B—all require >32GB

#### Consequences
- Positive: Sub-5-second responses vs 5+ minute timeouts
- Positive: Graceful degradation when local fails
- Positive: Preserves Mixtral config for future 64GB upgrade
- Negative: Cloud fallback incurs API costs
- Negative: Slightly different behavior between local and cloud models
- Mitigation: Aggressive local-first routing, budget alerts, cost logging

#### Notes
- Already implemented in Phase 2 update (2025-01-09)
- Cloud API key stored in CredentialManager (anthropic_api_key)
- Test suite includes hybrid routing tests

---

### ADR-017: Proactive Intelligence Framework

**Date**: 2025-01-09
**Status**: Proposed

#### Context
True AI assistants (like Jarvis) anticipate needs rather than just responding to requests. Hestia should proactively surface relevant information at appropriate times without being annoying.

Use cases:
- Morning briefing: "Good morning. You have 3 meetings today, 2 overdue reminders."
- Pattern-based: "You usually review the budget on Fridays. Should I prepare the summary?"
- Context-aware: "Your flight is in 4 hours. Traffic to the airport is heavy."

#### Decision
Implement proactive intelligence with user-controlled interruption policy:

**Proactive features**:
1. **Daily briefing**: Morning summary of calendar, reminders, pending tasks
2. **Pattern detection**: Identify recurring user behaviors
3. **Suggestion engine**: Proactive recommendations based on patterns
4. **Context triggers**: Time-sensitive notifications (meetings, deadlines)

**Interruption policy** (user-configurable):
- **Never**: Only respond when asked (fully reactive)
- **Daily briefing only**: One morning notification
- **Proactive**: Suggestions allowed during configured hours (e.g., 9am-6pm)
- **Always**: Proactive anytime (not recommended)

**Context awareness**:
- Respect macOS/iOS Focus modes
- Don't interrupt during calendar events marked "busy"
- Batch non-urgent suggestions (don't spam)

#### Alternatives Considered
- **Always proactive**: Too annoying, users will disable
- **Never proactive**: Loses key differentiator from simple chatbots
- **AI-determined timing**: Too unpredictable, hard to debug

#### Consequences
- Positive: Enables anticipatory assistance (core Jarvis feature)
- Positive: User maintains control over interruption frequency
- Negative: Risk of being annoying if poorly calibrated
- Negative: Adds complexity (pattern detection, scheduling)
- Mitigation: Conservative defaults, easy disable, gradual rollout

#### Notes
- Phase 9 implementation (post-MVP)
- Depends on Phase 5.5 (Apple ecosystem) for calendar/reminder access
- Depends on Phase 4.5 (Background tasks) for async pattern analysis

---

### ADR-018: Task Decomposition Strategy

**Date**: 2025-01-09
**Status**: Proposed

#### Context
Complex user requests often require multiple steps with dependencies:
- "Plan my trip to Italy" → research, booking, itinerary, packing list
- "Prepare for my presentation" → research, outline, slides, rehearsal notes
- "Organize my finances" → categorize, analyze, report, recommendations

Single-shot responses don't handle these well. Need structured task breakdown with progress tracking.

#### Decision
Implement task decomposition with checkpoint/rollback:

**Decomposition structure**:
```python
class TaskDecomposition:
    root_task: str           # Original user request
    subtasks: List[Subtask]  # Ordered list of steps
    current_step: int        # Which subtask is active
    status: DecompStatus     # pending/in_progress/completed/paused/failed

class Subtask:
    id: str
    description: str
    success_criteria: str    # How to know it's done
    dependencies: List[str]  # Subtask IDs that must complete first
    checkpoint: Optional[str]  # Saved state after completion
    status: SubtaskStatus
    result: Optional[str]
```

**Features**:
- **Decomposition engine**: LLM + rules to break down complex tasks
- **Progress tracking**: Percentage complete, current step display
- **Checkpointing**: Save state after each subtask completion
- **Rollback**: Undo to previous checkpoint on failure
- **Pause/Resume**: User can pause and resume later

**Complexity levels**:
- **Simple** (v1): Linear chains (A → B → C)
- **Advanced** (v2.1): DAG with parallel branches

#### Alternatives Considered
- **No decomposition**: Single-shot responses only (can't handle complex tasks)
- **Fully autonomous**: AI decides everything (too unpredictable)
- **User-managed breakdown**: User specifies all steps (too much burden)

#### Consequences
- Positive: Enables complex multi-step workflows
- Positive: Transparent progress tracking
- Positive: Recoverable from failures (checkpoints)
- Negative: Significant complexity in task management
- Negative: Decomposition quality depends on LLM understanding
- Mitigation: Start with linear chains, add DAG support later

#### Notes
- Phase 10 implementation (v2.0)
- Depends on Phase 4.5 (Background tasks) for async execution
- Integration with Phase 9 (Proactive) for progress notifications

---

### ADR-019: Native SwiftUI App Architecture

**Date**: 2025-01-11
**Status**: Accepted

#### Context
Phase 6b required building a native iOS/macOS app to interface with the Hestia backend. Key decisions needed around:
- iOS version target (compatibility vs modern features)
- State management pattern (SwiftUI's evolving patterns)
- Project generation (manual Xcode vs automated)
- Color scheme approach (system vs custom)

#### Decision
Build HestiaApp with:

**iOS 16+ Target**:
- Wide device compatibility (iPhone 8 and newer)
- Use ObservableObject + @Published (not @Observable which requires iOS 17+)
- Stable async/await support

**MVVM Architecture**:
- Shared code between iOS/macOS targets
- Protocol-based service layer (HestiaClientProtocol)
- MockHestiaClient for development, APIClient for production

**xcodegen for Project Generation**:
- project.yml defines project structure
- Reproducible Xcode project generation
- Avoids Xcode project merge conflicts

**Custom Color Scheme from Figma**:
- Mode-specific gradients (Tia=Orange/Brown, Mira=Blue, Olly=Green)
- Dark mode only (matches Jarvis aesthetic)
- Semantic color names in code

#### Alternatives Considered
- **iOS 17+ with @Observable**: Cleaner syntax but excludes older devices
- **Redux-style state management**: Overkill for current complexity
- **Manual Xcode project**: Harder to maintain, more merge conflicts
- **System colors only**: Less distinctive branding

#### Consequences
- Positive: Broad device support (iOS 16+)
- Positive: Familiar pattern for SwiftUI developers
- Positive: Easy mock/real client swapping for development
- Positive: Distinctive visual identity per mode
- Negative: ObservableObject pattern more verbose than @Observable
- Negative: xcodegen adds build tooling dependency
- Mitigation: Can migrate to @Observable when dropping iOS 16 support

#### Notes
- 43+ Swift files created
- Design system includes Colors, Typography, Spacing, Animations
- Mode switching via @mentions with ripple transition effects

---

### ADR-020: Face ID Authentication Flow

**Date**: 2025-01-11
**Status**: Accepted

#### Context
Hestia handles sensitive data (conversations, calendar, mail access). Need authentication without being intrusive or blocking development.

#### Decision
Implement Face ID/Touch ID with development bypass:

**Production behavior**:
- Face ID required before accessing app content
- Auto-lock after configurable timeout (30 minutes default)
- Device registration stored in Keychain

**Development behavior**:
- `#if targetEnvironment(simulator)` skips biometric auth
- Auto-authenticates in simulator for faster iteration
- Same code path, conditional compilation

**Code structure**:
```swift
func authenticate() async throws {
    #if targetEnvironment(simulator)
    // Auto-authenticate for development
    isAuthenticated = true
    return
    #else
    // Real Face ID flow
    try await evaluateBiometricPolicy()
    #endif
}
```

#### Alternatives Considered
- **Always require auth**: Blocks simulator testing
- **Debug flag in code**: Risk of shipping debug mode
- **Separate debug target**: More maintenance overhead

#### Consequences
- Positive: Fast iteration in simulator
- Positive: Same code for production and debug
- Positive: Compile-time safety (no runtime debug flags)
- Negative: Can't test real Face ID in simulator
- Mitigation: Test on physical device before release

---

### ADR-021: Background Task Management

**Date**: 2025-01-12
**Status**: Accepted (Implemented 2025-01-12)

#### Context
Users need fire-and-forget task submission via iOS Shortcuts and Quick Chat. Tasks execute asynchronously with notification on completion.

#### Decision
Implement SQLite-backed background task queue with:

**Task Lifecycle**:
1. Submission: User sends task via Shortcut/Quick Chat
2. Acknowledgment: Immediate "Got it ✓"
3. Processing: Async execution
4. Completion: Push notification (respects Focus modes)
5. Visibility: Results in Activity Timeline

**Task Schema**:
```sql
CREATE TABLE background_tasks (
    id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    completed_at DATETIME,
    status TEXT NOT NULL,  -- 'pending', 'in_progress', 'completed', 'failed', 'awaiting_approval'
    source TEXT NOT NULL,  -- 'quick_chat', 'ios_shortcut', 'conversation'
    input_summary TEXT,
    output_summary TEXT,
    output_details TEXT,   -- JSON
    autonomy_level INTEGER DEFAULT 3,
    escalated BOOLEAN DEFAULT FALSE,
    escalation_reason TEXT,
    notification_sent BOOLEAN DEFAULT FALSE
);
```

**Autonomy Rules**:
| Action Type | Default Level | Behavior |
|-------------|---------------|----------|
| Internal (calendar, reminders, notes) | Level 3 | Execute → Notify |
| Research (memory search) | Level 3 | Execute → Notify |
| External communication | Level 2 | Draft → Await approval |
| Data deletion | Level 2 | Await approval |

**Output Persistence**:
- Task outputs auto-persist to memory layer
- Actions requiring approval per existing framework still require approval
- Full audit trail maintained

#### Consequences
- Positive: Fire-and-forget UX for quick capture
- Positive: Transparent task visibility via Activity Timeline
- Negative: Adds queue management complexity
- Mitigation: Simple FIFO queue, clear status UI

---

### ADR-022: Governed Auto-Persistence for Background Tasks

**Date**: 2025-01-12
**Status**: Accepted (Implemented 2025-01-12)

#### Context
ADR-002 requires human review for all long-term memory persistence. Background tasks need an exception path for explicitly-requested work.

#### Decision
Background task outputs may auto-persist to memory layer IF:
1. Task was explicitly initiated by user (Shortcut, Quick Chat)
2. Task does NOT involve actions in the "always-require-approval" category
3. Full audit trail is maintained

Tasks requiring approval per existing framework (external communication, data deletion, credential access) still require approval before execution.

#### Relationship to ADR-002
This is an EXCEPTION to ADR-002's staging requirement, not a replacement. The exception applies only to:
- Explicit user-initiated background tasks
- Non-sensitive action categories

#### Consequences
- Positive: Smooth UX for fire-and-forget tasks
- Positive: Audit trail provides accountability
- Negative: Slightly increased risk of memory pollution
- Mitigation: User can review Activity Timeline; delete unwanted entries

#### Implementation Notes
- Phase 4.5 scope (v1.0) - IMPLEMENTED 2025-01-12
- `hestia/tasks/` module: models.py, database.py, manager.py
- 6 API endpoints in `hestia/api/routes/tasks.py`
- 60 unit tests in `tests/test_tasks.py`
- Activity Timeline UI uses mock data (Phase 6b iOS integration pending)

---

### ADR-023: Tool Definition Injection Strategy

**Date**: 2025-01-12
**Status**: Accepted (Implemented 2025-01-12)

#### Context
Hestia has 20+ Apple ecosystem tools (Calendar, Reminders, Notes, Mail) registered in the execution layer. However, the LLM (Qwen 2.5 7B) was not aware of these tools because tool definitions were never injected into the system prompt.

Symptom: When asked "What's on my calendar?", Hestia would respond with placeholder text like "I'd need you to provide your email..." instead of actually checking the calendar.

#### Decision
Inject tool definitions directly into the LLM system prompt with explicit instructions on how to call tools.

**Implementation:**
1. Call `get_tool_definitions()` in handler.py Step 6 (prompt building)
2. Append tool definitions to `additional_system_instructions`
3. Include explicit JSON format for tool calls: `{"tool_call": {"name": "...", "arguments": {...}}}`
4. Add `_try_execute_tool_from_response()` method to parse LLM output and execute tools

**Tool Call Format:**
```json
{
  "tool_call": {
    "name": "list_events",
    "arguments": {
      "calendar_id": "personal",
      "start_date": "2025-01-12"
    }
  }
}
```

#### Alternatives Considered
- **Structured function calling** (OpenAI style): Qwen 2.5 7B doesn't have native function calling support
- **Separate tool selection step**: Adds latency, complicates flow
- **Always call tools regardless of response**: Would make unnecessary API calls

#### Consequences
- Positive: LLM now knows about available tools and can request them
- Positive: Tool results formatted and returned in response
- Negative: Adds token overhead (~1K tokens for tool definitions)
- Negative: Relies on LLM outputting valid JSON (may need retry logic)
- Mitigation: JSON parsing with error handling, clear format instructions

#### Implementation Notes
- File: `hestia/orchestration/handler.py`
- Tool definitions injected at prompt building step
- Tool execution happens after LLM response, before returning to user
- Results formatted per tool type (events, reminders, notes, emails)

---

### ADR-024: Mode Invocation Patterns

**Date**: 2025-01-12
**Status**: Accepted (Implemented 2025-01-12)

#### Context
Users were saying "Hey Tia" to invoke the Tia mode, but the system only recognized `@tia` or `@hestia` patterns. This caused confusion when the mode didn't switch as expected.

#### Decision
Extend mode invocation patterns to include natural greeting forms:

**Patterns per mode:**
| Mode | Original | Extended |
|------|----------|----------|
| Tia | `@tia`, `@hestia` | + `hey tia`, `hi tia`, `hello tia` |
| Mira | `@mira`, `@artemis` | + `hey mira`, `hi mira`, `hello mira` |
| Olly | `@olly`, `@apollo` | + `hey olly`, `hi olly`, `hello olly` |

**Regex patterns (server-side):**
```python
r"@tia\b|@hestia\b|hey\s+tia\b|hi\s+tia\b|hello\s+tia\b"
```

#### Alternatives Considered
- **Intent classification**: Use LLM to detect mode invocation (overkill, adds latency)
- **Keyword anywhere**: Match "tia" anywhere in text (too many false positives)
- **Only @mentions**: Keep original patterns (users find it unnatural)

#### Consequences
- Positive: More natural interaction ("Hey Tia, what's up?")
- Positive: Consistent behavior between iOS app and server
- Negative: Slight increase in pattern matching complexity
- Mitigation: Patterns are regex-compiled, minimal performance impact

#### Implementation Notes
- Server: `hestia/orchestration/mode.py` - `invoke_pattern` updated
- iOS: `HestiaApp/Shared/ViewModels/ChatViewModel.swift` - `detectModeInvocation()` updated
- Both locations must stay in sync

---

### ADR-025: Cloud LLM Integration (WS1)

**Date**: 2026-02-10
**Status**: Implemented

#### Context
Local-only inference (Qwen 2.5 7B on M1 16GB) is adequate for routine queries but insufficient for complex reasoning, creative writing, and multi-step analysis. Users need a way to leverage cloud LLMs while keeping local inference as the default for speed and privacy.

#### Decision
Implement 3-state cloud routing with multi-provider support:
- **disabled** (default): Local-only, no cloud calls
- **enabled_smart**: Local-first with cloud spillover on failure or high token count (>16K)
- **enabled_full**: Cloud-first with local fallback

Support three providers: Anthropic, OpenAI, Google. API keys stored in macOS Keychain (never returned in API responses). 7 new endpoints for provider CRUD, state management, usage tracking, and health checks.

#### Alternatives Considered
- **Single provider**: Simpler but vendor lock-in risk
- **Always-cloud**: Defeats privacy-first design principle
- **Token-based routing only**: Misses use cases where cloud quality is preferred regardless of token count

#### Consequences
- Positive: Best-of-both-worlds — privacy by default, cloud power when needed
- Positive: State propagation via `_sync_router_state()` ensures consistency
- Negative: Cloud API costs (~$0.003/1K input tokens for Anthropic)
- Negative: Requires API key management and health monitoring

---

### ADR-026: Voice Journaling Pipeline (WS2)

**Date**: 2026-02-10
**Status**: Implemented

#### Context
Users want to dictate thoughts, reflections, and journal entries via voice. Raw speech-to-text transcripts are often noisy and need quality checking before analysis.

#### Decision
Implement a 3-stage voice pipeline:
1. **iOS SpeechAnalyzer**: On-device speech-to-text (Apple Speech framework)
2. **Quality Check**: LLM reviews transcript, flags uncertain words, returns confidence score
3. **Journal Analysis**: LLM extracts intents, cross-references calendar/reminders/mail/memory, generates action plan

Two endpoints: `/v1/voice/quality-check` and `/v1/voice/journal-analyze`.

#### Consequences
- Positive: On-device STT preserves privacy; only text sent to server
- Positive: Quality gate prevents garbage-in-garbage-out
- Negative: Journal analysis requires LLM call (uses cloud if enabled)

---

### ADR-027: Council + SLM Architecture (WS3)

**Date**: 2026-02-10
**Status**: Implemented

#### Context
Single-pass LLM inference lacks the nuance for complex requests — tool extraction, safety validation, and personality synthesis all happen in one shot. A multi-role approach can improve quality without requiring a larger model.

#### Decision
Implement a 4-role council with dual-path execution:
- **Coordinator** (SLM: qwen2.5:0.5b, ~100ms): Intent classification — runs locally even when cloud is active
- **Analyzer** (cloud-only): Tool extraction from LLM response
- **Validator** (cloud-only): Quality and safety checks
- **Responder** (cloud-only): Personality synthesis per active mode

**Dual-path**: Cloud active → all 4 roles via `asyncio.gather()` parallel execution. Cloud disabled → SLM intent only, existing pipeline handles the rest.

**Key design constraint**: Purely additive. Every council call wrapped in try/except. Failures fall back silently to existing pipeline. Council can never make things worse.

**CHAT optimization**: When intent==CHAT with confidence>0.8, skip Analyzer/Validator/Responder (saves 3 API calls for simple conversation).

#### Consequences
- Positive: Better tool extraction, safety checks, and personality consistency
- Positive: Zero-cost intent classification via local SLM (~100ms)
- Positive: Purely additive — no regression risk
- Negative: ~4 API calls per message when cloud is enabled_full

---

### ADR-028: Temporal Decay for Memory (WS4)

**Date**: 2026-02-10
**Status**: Implemented

#### Context
Memory search returns results purely by vector similarity, treating a conversation from 6 months ago the same as one from yesterday. Users expect recent context to be more relevant.

#### Decision
Apply exponential decay to memory search scores:
```
adjusted = raw_score * e^(-lambda * age_days) * recency_boost
```

Per-chunk-type lambda values (configurable in `memory.yaml`):
- `fact`: 0.0 (never decays)
- `system`: 0.0 (never decays)
- `conversation`: 0.02 (half-life ~35 days)
- `preference`: 0.005 (half-life ~139 days)
- `decision`: 0.002 (half-life ~347 days)

Recency boost: 1.2x for memories accessed within 24 hours. Minimum score floor of 0.1 prevents complete disappearance.

#### Consequences
- Positive: Recent context surfaces naturally; old conversations fade
- Positive: Facts and system knowledge persist forever
- Positive: Tunable per chunk type via config
- Negative: Hard cliff at 24h recency boost boundary (acceptable trade-off)

---

### ADR-029: Apple HealthKit Integration

**Date**: 2026-02-15
**Status**: Implemented

#### Context
Users want Hestia to understand their health context — sleep, activity, heart rate, nutrition — to provide more personalized briefings and coaching. Apple HealthKit provides a rich data source on iOS.

#### Decision
Implement full HealthKit integration with:
- **28 metric types** across 7 categories (activity, body, heart, sleep, nutrition, mindfulness, reproductive)
- **Daily sync** endpoint: iOS pushes HealthKit data to server
- **Server-side storage**: SQLite with deduplication via UNIQUE constraint
- **Coaching preferences**: User-configurable focus areas, tone, and goals
- **5 chat tools**: health_summary, health_trend, coaching_advice, sleep_analysis, activity_analysis
- **Briefing integration**: Health section in morning briefings when data available

Data stays on-device until user explicitly syncs. No cloud transmission of health data.

#### Consequences
- Positive: Rich health context for personalized assistance
- Positive: Privacy-preserving — user controls what data is shared
- Positive: Coaching preferences allow customization without exposing raw data
- Negative: Requires HealthKit entitlement and user permission grants
- Negative: 28 metric types adds complexity to data model

---

### ADR-030: Invite-Based Device Onboarding

**Date**: 2026-02-28
**Status**: Implemented

#### Context
Hestia's original `/v1/auth/register` endpoint allowed any device on the network to register without verification — an open enrollment model unsuitable for a personal assistant with access to sensitive data.

#### Decision
Implement invite-based registration:
- **Server generates invite tokens** via `POST /v1/auth/invite` (requires setup_secret from Keychain)
- **QR code payload**: `{"t":"<invite_jwt>","u":"<server_url>","f":"<cert_fingerprint>"}`
- **One-time nonce**: Each invite token contains a UUID nonce stored in SQLite; consumed on use
- **iOS**: AVFoundation QR scanner → parse → configure API → register → permissions onboarding
- **macOS**: Paste JSON payload → parse → configure API → register
- **Recovery**: `POST /v1/auth/re-invite` allows authenticated devices to generate new invites
- **Rate limiting**: 5 invites per hour
- **Permissions onboarding**: Apple HIG-compliant guided flow (Calendar → Reminders → Health → Notifications → Biometric) after first auth

Open registration (`/v1/auth/register`) remains for backward compatibility but can be disabled via `require_invite` config flag.

#### Alternatives Considered
- **Open registration**: Simpler but insecure — any device on the network could register
- **Manual token entry**: More tedious than QR scanning for mobile devices
- **Bluetooth pairing**: Over-engineered for a personal server with known devices

#### Consequences
- Positive: Only invited devices can register — eliminates unauthorized enrollment
- Positive: QR code makes mobile onboarding seamless (scan → connect)
- Positive: Certificate fingerprint in QR payload enables trust-on-first-use TLS pinning
- Positive: Guided permissions onboarding explains each permission request with context
- Negative: Requires server-side QR generation (`qrcode[pil]` dependency)
- Negative: macOS lacks camera scanner — paste workflow less elegant

---

### ADR-031: Agent Configuration Coexistence (V1/V2)

**Date**: 2026-03-01
**Status**: Accepted

#### Context
Two agent configuration systems exist in the codebase: V1 (slot-based, SQLite-backed) registered at `/v1/agents/` and V2 (name-based, .md file-backed) registered at `/v2/agents/`. The codebase audit flagged this as a "dual registration" issue and recommended migration. Investigation revealed they serve fundamentally different purposes.

#### Decision
Maintain both systems as orthogonal, complementary tools:
- **V1** serves the iOS/macOS client: slot-based profiles (Tia/Mira/Olly), photo management, snapshots/restore, multi-device sync. iOS depends on 9 V1 APIClient methods.
- **V2** serves backend development: arbitrary named agents with markdown config files (IDENTITY, MIND, TOOLS, MEMORY, ANIMA, etc.), daily notes, config CRUD, reload.

Do not deprecate V1 until iOS has full V2 coverage with an adapter layer.

#### Alternatives Considered
- **Migrate V1 to V2 and update iOS**: Breaking change requiring dual iOS versions. V1 features (photos, snapshots, sync) have no V2 equivalent. High effort, low value.
- **Merge into single system**: Would bloat V2 with photo/snapshot concerns it doesn't need, or strip V1 of markdown flexibility.

#### Consequences
- Positive: Each system evolves independently for its audience (iOS client vs backend dev)
- Positive: No breaking change to iOS app
- Negative: 20 total endpoints across 2 route modules (maintenance overhead)
- Mitigation: Clear documentation prevents future confusion. V2 can grow features (photos, snapshots) when iOS adoption warrants it.

---

### ADR-032: Newsfeed Materialized Cache

**Date**: 2026-03-01
**Status**: Accepted

#### Context
The Command Center needs a unified timeline aggregating items from orders, memory, tasks, and health. Two approaches: virtual aggregation (query all sources on every request) or materialized cache (store items in SQLite, refresh when stale).

#### Decision
Materialized cache with 30s TTL in SQLite. Items upserted on refresh, served directly from cache on reads. Forced refresh via `/v1/newsfeed/refresh` (rate-limited 1/10s per device). 30-day retention cleanup.

#### Alternatives Considered
- **Virtual aggregation**: Simpler code, no cache table. But 5+ manager calls on every poll (orders, memory, tasks, health, calendar) — too slow for real-time timeline.
- **Event-driven push**: Managers emit events when data changes. Complex wiring, premature for single-user system.

#### Consequences
- Positive: Fast reads (single SQLite query with JOIN), resilient aggregation (one source failure doesn't block others)
- Positive: Clean separation — each aggregator maps source data to NewsfeedItem independently
- Negative: 30s staleness window (acceptable for personal assistant)
- Negative: Additional SQLite table maintenance

---

### ADR-033: User-Scoped Newsfeed State for Multi-Device

**Date**: 2026-03-01
**Status**: Accepted

#### Context
Hestia is currently single-user (`"user-default"` hardcoded), but multi-user/multi-device support is planned. Read/dismiss state should sync across devices from day one.

#### Decision
`newsfeed_state` table with composite PK (`item_id`, `user_id`). Read/dismiss state is per-user, not per-device. `acted_on_device_id` stored for audit only. Currently hardcoded to `"user-default"` — swap to JWT lookup when multi-user ships. No migration needed for existing tables (newsfeed is new).

#### Alternatives Considered
- **Per-device state**: Simpler but "read on iPhone, still unread on Mac" is poor UX.
- **No state table**: Mark items as read in the items table directly. Doesn't support multi-user.

#### Consequences
- Positive: Read on iPhone = read on Mac immediately
- Positive: Zero migration cost when multi-user ships (just change user_id source)
- Negative: Slightly more complex queries (LEFT JOIN on state table)

---

### ADR-034: Device Token Revocation

**Date:** 2026-03-01
**Status:** Accepted
**Context:** JWT tokens have 90-day expiry with no revocation mechanism. Lost/stolen devices remain authorized until token expires.

#### Decision
Add `revoked_at` column to `registered_devices` table. Auth middleware checks revocation status in `get_device_token()` dependency. Two new API endpoints: `POST /v1/user/devices/{id}/revoke` and `POST /v1/user/devices/{id}/unrevoke`.

#### Design: Fail-Open
If the invite store is unavailable (DB error, init failure), the revocation check passes silently. Rationale: revocation is defense-in-depth on top of JWT validation. Availability is prioritized over blocking all auth on a secondary store failure.

#### Consequences
- Positive: Instant device revocation without waiting for token expiry
- Positive: Unrevoke path for false positives
- Negative: Additional async DB hit per authenticated request (mitigated by SQLite speed)

---

### ADR-035: Session Auto-Lock (TTL Enforcement)

**Date:** 2026-03-01
**Status:** Accepted
**Context:** `auto_lock_timeout_minutes` setting existed in UserSettings but was never enforced. In-memory conversation cache (`_conversations`) was unbounded with no eviction.

#### Decision
Handler checks `last_activity` against timeout on each `handle()` call. Expired sessions are replaced with fresh conversations. Background cleanup runs every 20 `handle()` calls to evict all stale sessions. Default timeout: 30 minutes (falls back if user settings unavailable).

#### Design: No Persistent Lock State
Session expiry is purely in-memory. The `last_activity` column in the sessions DB table is set on session end for audit purposes but not used for runtime TTL checks. This keeps the hot path fast (no DB query per request for TTL).

#### Consequences
- Positive: Bounded conversation cache (prevents unbounded memory growth)
- Positive: Stale context doesn't bleed into new conversations
- Negative: Server restart resets all sessions (acceptable — conversations are ephemeral)

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
