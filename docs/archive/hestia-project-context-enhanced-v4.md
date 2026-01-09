# Hestia Project Context (Enhanced)

## Purpose of This Document

This file provides Claude with persistent context about the Hestia project. Add this to your Claude Project to ensure consistent, informed collaboration across conversations.

**Last Updated**: v4 - 2025-01-09 (Added Quick Chat, Activity Timeline, Background Tasks)

---

---

## Locked Decisions (Post Q&A Session - 2025-01-08)

### Security Posture
**Target**: Pentagon/CIA-level security  
**Approach**: Defense-in-depth with hardware-backed security (Secure Enclave)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Credential Storage** | macOS Keychain + Secure Enclave, three partitions (operational/sensitive/system) | Hardware security, biometric gates, zero setup |
| **Encryption** | Double encryption (Fernet + Keychain AES-256) | Defense in depth |
| **Biometric Auth** | Face ID/Touch ID required for sensitive data | Seamless yet secure |
| **Audit Trail** | Complete logging (7-year retention for credential access) | Compliance best practices |
| **Data Retention** | Indefinite with annual review prompt | Long-term memory goal |

### Apple Ecosystem Integration (OAuth-Free)
**Strategy**: Leverage native integration, no OAuth needed for v1.0

| Component | Access Method | Capabilities |
|-----------|---------------|--------------|
| **Apple Mail** | SQLite query (`~/Library/Mail/V10/`) | Full read access to Gmail (already synced via IMAP) |
| **Apple Calendar** | Swift CLI + EventKit | Full CRUD on all calendars (including Google Calendar via CalDAV sync) |
| **Apple Reminders** | Swift CLI + EventKit | Full CRUD with all features (subtasks, priorities, due dates) |
| **Apple Notes** | Swift CLI + AppleScript (v1.0 tactical) | Text-only CRUD, attachments deferred to v1.5 |
| **Email Sending** | Deferred to v1.5 | v1.0: Hestia drafts, user sends via Mail.app |

**Key Insight**: User's Gmail account already synced to Apple Mail/Calendar via System Settings → Internet Accounts. No need to touch Gmail/GDrive APIs.

### External APIs (v1.0 Scope)

| Service | Purpose | Free Tier | Cost if Exceeded |
|---------|---------|-----------|------------------|
| **OpenWeatherMap** | Weather for proactive calendar insights | 1000 calls/day | $0.0001/call over limit |
| **Brave Search** | Web search for research | 2000 queries/month | $5/1000 queries over limit |

**Monthly Budget Target**: <$100 (likely $10-20 if staying within free tiers)

**Deferred to v1.5**:
- Anthropic API (Cloud LLM for vision/large context) - most cases handled by multi-stage retrieval
- Gmail API (OAuth) - for programmatic email sending
- Google Drive API (OAuth) - for file migration
- SMTP with app password (simpler alternative to Gmail API)
- Menu bar app with Quick Chat
- Screen capture/vision capabilities

### Context Window Management (ADR-011)
**Challenge**: Mixtral 8x7B has 32K token limit (~24K words)

**Token Budget Allocation**:
- System prompt: 2K (fixed)
- Tool definitions: 1K (fixed)
- User model: 2K (summarized)
- Conversation history: up to 20K (sliding window)
- Memory retrieval: up to 4K (RAG-filtered)
- User input: ~3K (remaining)

**Management Strategies**:
1. Sliding window: Keep last N messages in full, summarize older
2. RAG pattern: Retrieve only relevant memory chunks
3. Compression: Aggressive summarization for messages >10 exchanges old
4. Token counting: Log actual usage, alert at 90% (28K tokens)
5. **Multi-stage retrieval**: For large context needs, retrieve → summarize → synthesize (stays local)

**Escalation** (v1.5): Fallback to Anthropic API only when multi-stage retrieval insufficient

### Development Workflow Confirmed

| Tool | Purpose | When to Use |
|------|---------|-------------|
| **Claude Code** | Primary development driver | "Build the memory manager", "Add retry logic", "Debug this error" |
| **Xcode** | IDE for everything | Browse code, run builds, use iOS Simulator, Git operations, edit any file type |

**Pattern**: Claude Code implements → You review in Xcode → Iterate

**No other IDEs**: No VS Code, no Cursor. Two tools, maximum power.

### Multi-User Timeline

| User | Timeline | Access Level |
|------|----------|--------------|
| **Andrew** | Now | Admin (full access) |
| **Wife** | Few months after MVP | User (isolated memory/credentials) |
| **Mother-in-law** | Years | User (isolated memory/credentials) |

**v2.0 Design**: Per-user encryption keys, admin can view all (with audit trail)

---

## Project Summary

**Hestia** is a locally-hosted, single-agent AI system running on Andrew's Mac Mini. It serves as a personal operating layer providing:

- **Task delegation** with persistent context across sessions and devices
- **Research capabilities** including overnight autonomous research
- **Structured education** with competency tracking and Socratic teaching
- **Three operational modes**: Tia (default), Mira (learning), Olly (projects)
- **Background task processing** with Activity Timeline visibility (v1.0)
- **Quick capture** via iOS Shortcuts (v1.0) and macOS Quick Chat (v1.5)

**Key mental model**: Hestia is like Jarvis from Iron Man—competent, adaptive, occasionally sardonic, anticipates needs without being emotionally solicitous.

---

## Identity Quick Reference

| Invoke | Name | Full Name | Focus |
|--------|------|-----------|-------|
| `@Tia` | Tia | Hestia | Default: daily ops, quick queries, general assistance |
| `@Mira` | Mira | Artemis | Learning: Socratic teaching, research synthesis |
| `@Olly` | Olly | Apollo | Projects: focused development, minimal tangents |

**Personality**: High sarcasm/wit, high adaptiveness/pragmatism, moderate empathy/curiosity, dry humor, never sycophantic.

**Voice rules**: Says "I" for self, refers to other modes in third person ("That's a question for Mira").

---

## Technical Stack

| Component | Technology | Notes |
|-----------|------------|-------|
| Hardware | Mac Mini M1, 64GB target | Future: M3 Ultra Mac Studio |
| Model | Mixtral 8x7B (Q4_K_M) | Via Ollama, text-only (no vision) |
| Language | Python 3.11+ | Backend implementation |
| App | Native Swift (SwiftUI) | iPhone, iPad, macOS—single codebase |
| Naming | kebab-case | Files and variables |
| Vector DB | ChromaDB | Semantic search for memory |
| Structured DB | SQLite | Tags, metadata, relationships, background tasks |
| Memory Query | Hybrid (ChromaDB + SQLite) | Multi-dimensional: semantic + tags + temporal (ADR-013) |
| API | FastAPI | Async, modern Python |
| Remote Access | Tailscale | Zero-config VPN |
| Quick Capture | iOS Shortcut (v1.0), macOS Quick Chat (v1.5) | Fire-and-forget input |
| Backup | External HDD | Terabytes of storage |
| Monitoring | Admin GUI + Activity Timeline | In-app dashboard |

### Development Tooling

| Tool | Purpose |
|------|---------|
| **Claude Code** | Primary development driver—AI implements, you review |
| **Xcode** | IDE for everything: Swift apps, Python editing, file browsing, Git |

**That's it.** Two tools. Minimal stack, maximum power.

---

## Architecture Overview

```
Apple Devices (stateless terminals)
         │
    Tailscale + Biometric Auth
         │
    Access Layer (auth, sessions, notifications respecting Focus)
         │
    Orchestration Layer (mode management, state machine, autonomy, background tasks)
         │
    Memory Layer (user model, learning queue, research, staging, task history)
         │
    Inference Layer (Mixtral 8x7B, persona prompts)
         │
    Execution Layer (Apple ecosystem, tools, external gate)
         │
    Admin Layer (GUI dashboard, Activity Timeline, logs, health monitoring)
```

---

## Design Principles

### 1. Observability Over Determinism
LLMs are stochastic. Log everything, enable replay, validate outputs. Don't claim determinism.

### 2. Single Agent, Multiple Modes
One model instance, three personas (Tia/Mira/Olly). Modes are stances, not separate agents.

### 3. Governed Memory Persistence
Model cannot auto-persist to long-term memory. Updates staged for human review.
**Exception**: Explicitly-requested background tasks (Quick Chat, iOS Shortcut) auto-persist outputs with full audit trail.

### 4. Conservative Autonomy with Escalation
Default Level 2 (draft and confirm). User authorizes Level 3/4 ad hoc or standing.
**Quick Chat/iOS Shortcut**: Implies Level 3 for safe actions; unsafe actions escalate to Level 2.

### 5. Strict External Gate
Nothing sent externally without explicit approval. All actions logged.

### 6. Flow-Respecting Proactivity
No interruptions during focus. Surface insights during scheduled touchpoints.
Background task completions delivered via notification (respects Focus modes).

---

## Input Methods

### Conversational (Default)
- Full app UI on iPhone, iPad, Mac
- Real-time back-and-forth with Hestia
- Default autonomy: Level 2 (draft and confirm)

### iOS Shortcut Quick Capture (v1.0)
- Fire-and-forget input via Shortcuts app
- Immediate "Got it ✓" confirmation
- Notification when task completes
- Results visible in Activity Timeline
- Autonomy: Level 3 for safe actions, escalates for unsafe

### macOS Menu Bar Quick Chat (v1.5)
- Global keyboard shortcut (⌘⇧H)
- Lightweight popup for quick commands
- Same fire-and-forget pattern as iOS Shortcut
- Menu bar icon shows connection status
- Autonomy: Level 3 for safe actions, escalates for unsafe

---

## Background Tasks & Activity Timeline

### Background Task Model
Tasks submitted via Quick Chat or iOS Shortcut execute asynchronously:

1. **Submission**: User sends task → immediate "Got it ✓" confirmation
2. **Processing**: Hestia works in background
3. **Completion**: Push notification sent (respects Focus modes)
4. **Visibility**: Full history in Activity Timeline

### Activity Timeline (v1.0)
Central view in Command Center showing all Hestia activity:
- Completed tasks with timestamps
- In-progress tasks (e.g., overnight research)
- Tasks awaiting approval (escalated from Level 3 → Level 2)
- Quick access to task details and outputs

### Task Persistence
- All background tasks logged to SQLite (`background_tasks` table)
- Outputs auto-persist (no staging required for explicit user requests)
- Full audit trail for security compliance
- Outputs linked to memory layer for future retrieval

### Autonomy for Background Tasks

| Task Type | Autonomy Level | Behavior |
|-----------|----------------|----------|
| Internal actions (calendar, reminders, notes) | Level 3 | Execute → Notify when done |
| Research (web search, memory search) | Level 3 | Execute → Notify with summary |
| External communication (email, API calls) | Level 2 | Draft → Notify for approval |
| Financial transactions | Level 2 | Never auto-execute |
| Data deletion | Level 2 | Never auto-execute |
| Credential access | Level 2 | Requires biometric + approval |

---

## Andrew's Context

### Skill Level
- Strongest: SQL, APIs, website development
- Growing: zshell, Python, infrastructure
- Learning as we build: Most other areas
- Expects Claude Code/Hestia to handle most implementation or teach him

### Development Setup
- Develops on MacBook/iPad
- Deploys to Mac Mini
- **Claude Code** as primary development driver
- **Xcode** as only IDE (handles Swift, Python, everything)
- GitHub for version control
- Two tools total—minimal stack

### Time Commitment
- ~6 hours/week for development
- 2-month target for MVP
- Bi-weekly tweaks, 6-week feature sprints

### Learning Style
- 70% teach-as-we-build (understand why)
- 30% just-make-it-work (note for later learning)

---

## User Model Dimensions

Hestia tracks these about Andrew (and future users):

| Category | What's Tracked |
|----------|---------------|
| Competency | Fine-grained skill levels per domain/topic |
| Communication | Concise vs. thorough preference, caveat placement |
| Work patterns | Peak times, context-switching habits |
| Decision style | Options vs. recommendations, challenge vs. support |
| Goals | Medium-term objectives, daily-to-arc connections |
| Trust calibration | What can be autonomous vs. needs confirmation |
| Tool preferences | Stack, formatting, trusted sources |
| Information diet | Source preferences, summary vs. depth |
| Failure patterns | Where user gets stuck |
| Temporal context | Calendar, deadlines, urgency impact |

**NOT tracked**: Emotional/energy state. Hestia is Jarvis, not a therapist.

---

## Key Behaviors

### Autonomy Levels
| Level | Behavior | Authorization |
|-------|----------|---------------|
| 1 | Suggest only | — |
| 2 | Draft and confirm | **DEFAULT** for conversations |
| 3 | Act with summary | Ad hoc ("go ahead") or Quick Chat/Shortcut for safe actions |
| 4 | Silent execution | Standing (overnight research, etc.) |

### Actions That Always Require Approval (Even at Level 3/4)
- External communication (emails, third-party API calls)
- Financial transactions
- Credential usage (requires biometric)
- Data deletion

### Error Handling
- **Don't know**: Admit it, offer to research. Never confabulate.
- **Uncertain intent**: Ask clarifying questions.
- **Made mistake**: Log, explain, propose resolution.
- **Hitting limits**: Be transparent for hardware/scaling analysis.
- **Disagree with user**: Single pushback with severity rating (1-5), then defer.

### Research Outputs
- **Curated digest**: Stored for depth when wanted
- **Synthesized briefing**: Default presentation (80-90%)
- **Decision-ready**: When task warrants (10-20%)

### Mode Switching
- Session-sticky (persists until switched)
- Seamless auto-switching with announcement
- Manual override via explicit @mention

---

## Code Conventions

### File Naming
```
kebab-case-for-everything.py
hestia-config.yaml
inference-client.py
user-model.py
background-task-manager.py
```

### Logging
Every significant operation logged with:
- Timestamp
- Request ID
- Event type
- Relevant data
- Duration

### Error Handling
Never swallow exceptions. Log full context before user-facing error.

### Type Hints
Use everywhere. They're documentation and catch bugs.

### Config Over Hardcoding
Anything that might change goes in YAML config files.

---

## Current Phase

**Update this section as the project progresses.**

- [ ] Phase 0: Environment Setup
- [ ] **Phase 0.5: Security Foundation** ← (Week 1, before logging)
- [ ] Phase 1: Logging Infrastructure  
- [ ] Phase 2: Inference Layer
- [ ] Phase 3: Memory Layer
- [ ] Phase 3.5: Tag-Based Memory Schema
- [ ] Phase 4: Orchestration Layer (including modes)
- [ ] **Phase 4.5: Background Task Management** ← NEW
- [ ] Phase 5: Execution Layer
- [ ] Phase 5.5: Apple Ecosystem Integration (Swift CLIs + Python wrappers)
- [ ] Phase 6: Access Layer + App (includes Activity Timeline)
- [ ] Phase 7: Integration & Hardening
- [ ] Phase 8: Iteration

**Recent Updates** (v4 - 2025-01-09):
- Added Background Task Management (Phase 4.5)
- Added Activity Timeline to App UI (Phase 6)
- Defined Quick Chat autonomy model (Level 3 for safe, escalate for unsafe)
- Added ADR-014 (Background Tasks and Asynchronous Execution)
- Clarified: Cloud LLM fallback deferred to v1.5 (multi-stage retrieval handles most cases)
- Clarified: Screen capture/vision deferred to v1.5 (requires cloud API)
- Added macOS Menu Bar + Quick Chat to v1.5 scope

**Previous Updates** (v3 - 2025-01-08):
- Added ADR-013 (Tag-Based Memory Schema for multi-dimensional queries)
- Added Phase 2.4 (Variable Context Window via multi-stage retrieval)
- Added Phase 3.5 (Tag-Based Memory implementation)
- Added Calibration Checkpoint Protocol (6 checkpoints throughout development)
- Clarified Apple ecosystem approach (no OAuth, EventKit for Calendar/Reminders)
- Locked external API strategy (Weather, Search)
- Defined context window management strategy (ADR-011)

---

## Version Targets

| Version | Target | Key Deliverables |
|---------|--------|------------------|
| v0.1 | Week 4 | Inference + logging + security + terminal chat |
| v0.2 | Week 6 | Memory + conversation continuity |
| v0.3 | Week 8 | Personality + basic user model |
| v0.4 | Week 10 | iOS app + multi-device + Activity Timeline |
| v1.0 | Week 11+ | **MVP**: Daily driver with background tasks, iOS Shortcut |
| v1.5 | +2-3 months | Menu bar + Quick Chat, OAuth email, cloud LLM fallback, screen capture |
| v2.0 | ~6 months | Multi-user support, advanced key management |

**Note**: Weeks are cumulative development time (~6 hours/week), not calendar weeks.

---

## Success Criteria

### MVP (2 months)
- Functional daily assistant
- Persistent memory across sessions
- Multi-device access via native app
- Response latency <4 seconds
- Basic learning queue operational
- Background tasks via iOS Shortcut
- Activity Timeline showing task history

### 6-Month Milestone
- Seamless daily operations
- Reliable overnight research
- Expert-level structured learning
- Natural, intuitive interactions
- Full single-user feature set
- Menu bar + Quick Chat (macOS)

---

## Multi-User Notes (v2+)

- Each user gets full experience with isolated memory
- Same personality across users
- No data sharing between users
- Admin (Andrew) has full visibility for debugging
- Planned users: Andrew (now), wife (few months), mother-in-law (years)

---

## Security Requirements

- Biometric auth (Face ID / Touch ID)
- Auto-lock: configurable 15/30/60 minutes
- Local-first; secure cloud escalation only when needed (v1.5+)
- Encrypted credential storage
- External communication requires explicit approval
- Admin-only deletion commands
- Monthly operational budget: <$100
- Background task outputs logged with full audit trail

---

## Cold Start Plan

1. **Pre-seed**: Ingest emails, calls, texts, notes, reminders
2. **Analysis**: Hestia synthesizes patterns, builds initial model
3. **Validation**: Presents understanding, Andrew corrects
4. **Structured intake**: Targeted questions to fill gaps
5. **Ongoing**: Organic learning from every interaction

---

## Effective Prompts for This Project

**Good:**
- "I'm working on the mode-manager. Here's my implementation—does the switching logic match the spec?"
- "Help me design the learning-queue schema. It needs to track deferred topics with context."
- "This is Olly mode behavior—am I capturing the 'minimal tangents' personality correctly?"
- "Design the background_tasks table schema for the Activity Timeline."

**Less effective:**
- "Build Hestia" (too broad)
- "Is this good?" (no context)
- "Help with the app" (which part?)

---

## Reference Documents

When you need full details, refer to:
- `hestia-initiative-enhanced.md` — Complete specification
- `hestia-development-plan.md` — Phase-by-phase build guide
- `hestia-decision-log.md` — Architectural decisions (ADR-001 through ADR-014)
- `hestia-security-architecture.md` — Security design
- `hestia-prompt-templates.md` — Templates for common interactions

---

## Glossary

| Term | Meaning |
|------|---------|
| Tia | Default Hestia mode—general assistant |
| Mira | Artemis mode—learning and research |
| Olly | Apollo mode—focused project work |
| User model | Hestia's evolving understanding of the user |
| Learning queue | Deferred teaching topics for later sessions |
| Staging layer | Proposed memory updates awaiting approval |
| External gate | Approval checkpoint for any outbound communication |
| Severity rating | 1-5 scale for pushback strength |
| Activity Timeline | UI showing all Hestia background work and task history |
| Quick Chat | macOS menu bar popup for fire-and-forget commands (v1.5) |
| Background task | Asynchronous work Hestia performs after Quick Chat/Shortcut input |

---

*Keep this document updated as the project evolves so Claude always has accurate context.*
