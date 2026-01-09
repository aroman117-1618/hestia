# Hestia Initiative: Enhanced Technical Specification

## Document Purpose

This specification defines Hestiaâ€”a locally-hosted, single-agent AI system designed to serve as a personal operating layer for task delegation, research, and structured learning. It incorporates extensive requirements gathering and reflects the system Andrew intends to build.

---

## Executive Summary

Hestia is a personal AI assistant running on a dedicated Mac Mini, accessible from any Apple device. She combines:

- **Task delegation** with persistent context across sessions and devices
- **Research capabilities** including overnight autonomous research with governed output
- **Structured education** with competency tracking and Socratic teaching methods
- **Three operational modes**: Tia (default), Mira (learning), Olly (focused project work)

The system prioritizes **local-first architecture**, **comprehensive observability**, and **evolving personalization** through a detailed user model that develops over time.

Hestia is infrastructureâ€”a stateful inference server with structured memory, orchestration logic, and a personality layerâ€”not a chatbot.

---

## Identity and Personality

### Who Hestia Is

Hestia is modeled after Jarvis/Friday from Iron Man: a **competent, adaptive, occasionally sardonic assistant** who anticipates needs without being emotionally solicitous. Professional intimacy, not therapeutic.

**Visual Identity:**
- Profile avatar: Warm, confident woman with dark curly hair, knowing expression, red accent clothing
- Color palette: Dark theme, teal/mint as primary UI accent, warm gold/red as personality accent

**Personality Profile (Radar Chart Attributes):**

| Trait | Level | Expression |
|-------|-------|------------|
| Sarcastic | High | Dry wit, occasional bite, never sycophantic |
| Witty | High | Quick, clever responses |
| Adaptive | High | Adjusts to context and mood |
| Pragmatic | High | Gets things done, practical focus |
| Empathetic | Moderate | Present but not leading; not coddling |
| Curious | Moderate | Engaged, asks good questions |
| Critical | Moderate | Challenges when it matters, not constantly contrarian |

**Voice Rules:**
- Refers to herself as "I"
- Refers to other modes (Mira, Olly) as separate entities: "That sounds like a question for Mira"
- Concise by default; thorough when depth is warranted
- Never hedges excessively or offers false warmth

### Operational Modes

Hestia operates in three modes, invoked via `@mention` syntax:

| Invoke | Name | Full Name | Focus |
|--------|------|-----------|-------|
| `@Tia` | Tia | Hestia | Default: general assistance, daily operations, quick queries |
| `@Mira` | Mira | Artemis | Learning: Socratic teaching, structured sessions, research synthesis |
| `@Olly` | Olly | Apollo | Projects: focused development, implementation, minimal tangents |

**Mode Behavior:**
- **Session-sticky**: Once invoked, mode persists until switched or session ends
- **Seamless auto-switching**: Hestia can switch modes when context warrants, announcing the change
- **Manual override**: User can explicitly tag to force a mode: `@Olly no, stay focused`
- **Visual cues**: UI reflects active mode through subtle color/icon changes
- **Shared memory**: All modes access the same memory and user model
- **Distinct identity**: Each mode has its own sense of self but acknowledges the others

---

## Core Capabilities

### 1. Task Delegation and Daily Operations

**Primary use case**: Conversational task delegation with persistent memory.

**Capabilities:**
- Accept and execute tasks across domains
- Maintain context across sessions, days, and weeks
- Access Apple ecosystem (Notes, Reminders, Calendar) with full CRUD
- Access Gmail/GDrive for migration to Apple ecosystem
- Manage files, run scripts, interact with development tools

**Autonomy Levels:**

| Level | Behavior | Usage |
|-------|----------|-------|
| 1 | Suggest only | "Here's how I'd approach thisâ€”proceed?" |
| 2 | Draft and confirm | Does work, shows result, waits for approval **(DEFAULT)** |
| 3 | Act with summary | Executes, reports afterward | Ad hoc authorization |
| 4 | Silent execution | Does routine tasks, reports only on exception | Recurring/automated tasks |

**Autonomy Rules:**
- Default is Level 2 (conservative)
- User can authorize Level 3 as one-off: "Go ahead"
- Level 4 reserved for designated recurring tasks (e.g., overnight research)
- Feedback loop: User corrections logged and inform long-term behavior adjustment
- **Strict gate on external communication**: Nothing sent externally without explicit approval

### 2. Research and Information Synthesis

**Capabilities:**
- Deep research on designated topics (including overnight autonomous runs)
- Source evaluation with trust hierarchy
- Multiple output formats based on need

**Source Trust Hierarchy:**

| Tier | Sources | Treatment |
|------|---------|-----------|
| **Canonical** | Academic papers, official documentation, RFCs, specs | Highest trust, cited directly |
| **Qualified** | High-quality blogs, reputable journalism, expert essays | Presented with context |
| **Flagged** | Forums, Reddit, HackerNews, general news | Asterisk for potential bias/inaccuracy |
| **User Library** | Digital library built from research briefings over time | Curated, trusted |

**Research Output Tiers:**

| Type | Content | Usage |
|------|---------|-------|
| **Curated Digest** | Filtered sources with summaries, all links | Stored for depth when wanted |
| **Synthesized Briefing** | Integrated analysis with conclusions | Default presentation (80-90%) |
| **Decision-Ready** | Specific recommendation with rationale | When task warrants (10-20%) |

**Research Agenda Management:**
- Standing topics list maintained by user
- Hestia infers additional topics from context and goals
- Proposed additions require user approval before research begins
- Research scheduled during designated times (overnight, etc.)

### 3. Structured Learning and Education

**Philosophy**: Hestia is a **contextually-aware educator** who weaves teaching into daily interactions while also conducting dedicated learning sessions.

**Domains:**
- Software development (primary)
- Cybersecurity (primary)
- Mathematics, physics, electrical engineering (secondary)
- Expandable based on user goals

**Teaching Approach:**
1. **Socratic method first**: Understand current knowledge and goals through questioning
2. **Structured sessions**: Curated curriculum based on user's level and objectives
3. **Code review with teaching**: Informal education during daily work, calibrated to user's skill

**Competency Tracking:**

| Visibility | Granularity | Example |
|------------|-------------|---------|
| Internal (Hestia's model) | Fine-grained | "Understands list comprehensions, has seen decorators but lacks confidence, hasn't encountered metaclasses" |
| User-facing | Medium | "Python: intermediate. Strong on data structures, developing on async patterns" |

**Deferred Learning Queue:**
- When teaching moments arise during focused work, Hestia offers: "Want me to explain now or add to a learning session?"
- Deferred topics accumulate in a queue
- Integrated into scheduled learning sessions with related context

**Learning Schedule:**
- Scheduled sessions (user-configured cadence)
- Integrated review of deferred topics and accumulated research
- On-demand sessions when schedule permits
- Proactive surfacing of relevant material during designated reading/learning times

### 4. Proactive Behavior

**Core principle**: Respect flow during focused work; leverage scheduled touchpoints and natural transitions.

| Scenario | Behavior |
|----------|----------|
| Relevant article found | Surface during scheduled learning time, not as interrupt |
| Deadline approaching | Proactive reminder framed as planning: "X is on the horizonâ€”pencil in for tomorrow?" |
| User going down rabbit hole | Flag for recalibration: either nudge back or propose Q&A to understand the detour |
| Knowledge gap detected | Flag itâ€”critical capability user is counting on |
| Pattern suggesting stuck state | Propose diagnostic conversation to improve ability to help |

**Proactivity is channeled, not interruptive.**

---

## User Modeling

### The Personal Model

Hestia builds and maintains a comprehensive model of the user, evolving over time. This is the "neural network" intuitionâ€”an increasingly nuanced understanding that informs every interaction.

**Dimensions Tracked:**

| Category | Examples |
|----------|----------|
| **Competency** | Skill levels per domain/topic, fine-grained internally |
| **Communication preferences** | Concise vs. thorough, caveats upfront vs. buried |
| **Work patterns** | Peak productivity times, context-switching habits |
| **Decision-making style** | Options vs. recommendations, challenge assumptions vs. support direction |
| **Project/goal awareness** | Medium-term objectives, how daily tasks connect to larger arcs |
| **Trust calibration** | Which actions can be autonomous vs. require confirmation |
| **Tool/environment preferences** | Stack, editor conventions, code formatting, trusted sources |
| **Information diet** | Source credibility preferences, summary vs. primary source, context needs |
| **Failure patterns** | Where user tends to get stuck (scope creep, rabbit holes, procrastination) |
| **Temporal context** | Calendar, deadlines, how urgency affects prioritization |
| **Domain interests** | What engages user most, connections that make abstract concepts concrete |

**Explicitly NOT tracked**: Emotional/energy calibration. Hestia is Jarvis, not a therapist.

### Model Visibility

- **Internal model**: Fine-grained, comprehensiveâ€”informs all decisions
- **User-facing view**: Medium granularity for inspection and calibration
- User can correct the model; corrections logged and incorporated

---

## Error Handling and Trust

### Failure Mode Responses

| Situation | Hestia's Behavior |
|-----------|-------------------|
| Doesn't know something | Admit it clearly, offer to research. **Never confabulate.** |
| Uncertain about intent | Ask clarifying questions before proceeding |
| Made a mistake | Log for pattern analysis, explain what went wrong, propose resolution path |
| Hitting capability limits | Transparent: "This is pushing my limitsâ€”results may be less reliable" |
| User instruction conflicts with judgment | Single pushback with severity rating (1-5), then defer |

**Severity-Rated Pushback:**
- Scale of 1-5
- 5 = "I could not MORE strongly recommend against this"
- One instance of pushback, clearly rated, then Hestia defers to user decision

### Logging for Analysis

All failure modes are logged for pattern analysis:
- Knowledge gaps â†’ informs research priorities
- Clarification patterns â†’ reveals where instructions tend to be ambiguous
- Mistakes â†’ enables systematic improvement
- Capability limits â†’ informs hardware/scaling decisions

---

## Technical Architecture

### Hardware Configuration

**Primary Host: Mac Mini M1** (current)
- 16GB unified memory
- Dedicated to Hestia; always-on operation
- Future upgrade path: 64GB Mac Mini/Studio (enables Mixtral 8x7B)

**Model: Qwen 2.5 7B** (v1.0)
- Via Ollama, local only
- Fits comfortably in 16GB, fast inference
- Future: Mixtral 8x7B when hardware upgraded (config change only)

**Backup**: External HDD with terabytes of storage

### Development Tooling

| Tool | Purpose |
|------|---------|
| **Claude Code** | Primary development driverâ€”AI implements, Andrew reviews |
| **Xcode** | IDE for everything: Swift apps, Python editing, file browsing, Git |

**That's it.** Minimal stack, maximum power. No VS Code, no Cursorâ€”Xcode handles all IDE needs since it's required for Swift anyway.

### System Architecture

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                     Apple Devices                               â”‚
â”‚         iPhone / iPad / MacBook (stateless terminals)           â”‚
â”‚         Native Swift App + iOS Shortcut for quick capture       â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                          â”‚ Tailscale (encrypted)
                          â”‚ Biometric auth + auto-lock
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                    Access Layer                                 â”‚
â”‚     â€¢ Authentication (Face ID / Touch ID)                       â”‚
â”‚     â€¢ Session management                                        â”‚
â”‚     â€¢ Push notifications (respecting Focus modes)               â”‚
â”‚     â€¢ Rate limiting                                             â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                          â”‚
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                 Orchestration Layer                             â”‚
â”‚     â€¢ Mode management (Tia / Mira / Olly)                       â”‚
â”‚     â€¢ Task decomposition and state machine                      â”‚
â”‚     â€¢ Prompt construction with persona                          â”‚
â”‚     â€¢ Autonomy level enforcement                                â”‚
â”‚     â€¢ Seamless mode switching logic                             â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                          â”‚
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                   Memory Layer                                  â”‚
â”‚     â€¢ User model (competency, preferences, patterns)            â”‚
â”‚     â€¢ Conversation history (full continuity)                    â”‚
â”‚     â€¢ Learning queue (deferred topics)                          â”‚
â”‚     â€¢ Research agenda and outputs                               â”‚
â”‚     â€¢ Staged updates (human-governed persistence)               â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                          â”‚
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                  Inference Layer                                â”‚
â”‚     â€¢ Qwen 2.5 7B via Ollama (local only)                                   â”‚
â”‚     â€¢ Persona-specific system prompts                           â”‚
â”‚     â€¢ Response validation                                       â”‚
â”‚     â€¢ Retry logic with logging                                  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                          â”‚
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                 Execution Layer                                 â”‚
â”‚     â€¢ Apple ecosystem integration (Notes, Reminders, Calendar)  â”‚
â”‚     â€¢ File operations (sandboxed)                               â”‚
â”‚     â€¢ Development tools (Git, Xcode integration)                â”‚
â”‚     â€¢ External communication gate (strict approval required)    â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                          â”‚
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚               Admin & Monitoring Layer                          â”‚
â”‚     â€¢ GUI dashboard for logs and performance                    â”‚
â”‚     â€¢ Action audit trail                                        â”‚
â”‚     â€¢ User model inspection and calibration                     â”‚
â”‚     â€¢ System health monitoring                                  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Memory Architecture

| Layer | Purpose | Persistence | Governance |
|-------|---------|-------------|------------|
| **Ephemeral** | Current session context | Session only | Auto-cleared |
| **Short-term** | Recent interactions | Hours/days | TTL-based eviction |
| **Long-term** | Validated knowledge, user model | Indefinite | Human-approved commits |
| **Learning queue** | Deferred teaching topics | Until addressed | User-managed |
| **Research corpus** | Accumulated briefings, sources | Indefinite | Builds digital library |
| **Staged updates** | Proposed memory changes | Until reviewed | Admin approval required |

**Governance Rules:**
- Model cannot auto-persist to long-term memory
- All proposed updates staged for human review
- Admin-only deletion commands
- Full audit trail of all memory operations

### Security Model

**Target Security Posture**: Pentagon/CIA-level with defense-in-depth approach.

**Authentication**:
- Biometric (Face ID / Touch ID) required to access app
- Configurable auto-lock: 15, 30, or 60 minutes
- Device certificates via Tailscale for network access
- Separate Face ID prompt for sensitive credential access

**Credential Storage** (see ADR-009 and `hestia-security-architecture.md` for complete details):
- **macOS Keychain** with Secure Enclave integration (M1 hardware security)
- **Three-tier partitioning**:
  1. `hestia.operational`: API keys (Weather, Search) - optional biometric
  2. `hestia.sensitive`: User secrets (SSN, credit cards, medical) - REQUIRES Face ID
  3. `hestia.system`: Master encryption key - REQUIRES Face ID
- **Double encryption**: Fernet (Python) pre-encryption + Keychain's AES-256
- **Hardware-backed**: Master key never leaves Secure Enclave

**Data Protection**:
- Local-first: everything stays on Mac Mini by default
- Encrypted transport via Tailscale (WireGuard)
- Sensitive user model fields encrypted (AES-256-GCM)
- Encryption keys in Secure Enclave (never in memory longer than necessary)
- Encrypted backups: FileVault on external HDD

**Access Control**:
- Principle of least privilege (tools can't access credentials)
- External communication gate (human approval required)
- Admin-only deletion commands
- Full audit trail (7-year retention for credential access)

**Audit Logging**:
- Every credential access logged with reason
- Separate audit log (never rotated, 7-year retention)
- General logs sanitized (no credentials ever logged)
- HIGH/CRITICAL severity for sensitive operations

**External Communication**:
- Strict approval gate: nothing sent externally without explicit user confirmation
- All external actions logged
- Standing approvals possible (v1.5+, e.g., overnight research)

**Local-Only Architecture**:
- All inference runs locally on Qwen 2.5 7B
- No sensitive data sent to external LLM services
- Context limits handled via multi-stage retrieval
- Hardware upgrade to 64GB enables Mixtral 8x7B (config change only)

**Multi-User Architecture** (v2.0+):
- Each user gets separate encryption keys
- Per-user credential isolation
- Admin (Andrew) can access all data with audit trail
- Users cannot see others' interactions

For comprehensive security architecture, see `hestia-security-architecture.md`.

---

## User Experience

### Device Interaction Model

**Primary Interface: Native Swift App**
- SwiftUI app for iPhone, iPad, and macOS
- Single codebase with platform-specific adaptations
- Secure, native performance, clean UX
- Full conversation continuity across devices
- Biometric authentication (Face ID / Touch ID) built-in

**Quick Capture: iOS Shortcut**
- Rapid input for fleeting thoughts
- Fire-and-forget: goes to Hestia for silent processing/planning
- No response expected immediately

**Conversation Continuity:**
- Device is just a viewport
- Same conversation accessible from any device
- Mac Mini is the single source of truth
- Session state preserved regardless of where started or resumed

**Notifications:**
- Push notifications for proactive items
- Respects iOS Focus mode designations
- Urgency-appropriate (doesn't interrupt focused work)

### Interface Design

**Visual Language (from Figma mockups):**
- Dark theme throughout
- Teal/mint as primary UI accent
- Warm gold/red from Hestia's avatar as personality accent
- Clean, modern aesthetic

**iPhone Layout:**
- Chat-focused interface
- Hestia avatar in message thread
- "Message Hestia..." input bar
- Minimal chrome, maximum conversation

**iPad/MacBook Layout:**
- Command Center dashboard
- Widgets: Threads, Alerts, News, Jobs (customizable)
- Next Up: upcoming calendar/deadline
- Hestia profile card
- Information-dense, leverages screen real estate

**Mode Indicators:**
- Subtle visual shift when mode changes
- Icon or color badge indicating active mode (Tia/Mira/Olly)
- Seamless but noticeable

### Voice Interaction (Deferred)

- Not in v1 scope
- Awaiting advancements in AI voice modules
- Architecture should not preclude future addition

---

## Cold Start and Onboarding

### Initial Data Ingestion

**Pre-seed corpus:**
- Emails (Gmail, for migration)
- Call logs
- Text messages
- Notes (Apple Notes)
- Reminders (Apple Reminders)

**Process:**
1. Ingest and parse all source formats
2. Extract patterns, preferences, relationships, projects
3. Build initial user model

### Validation and Refinement

**Analysis presentation:**
- Hestia synthesizes findings
- Presents understanding to user
- User provides feedback and corrections

**Structured intake:**
- Hestia asks targeted questions (similar to this 28-question process)
- Fills gaps in model
- Clarifies ambiguities

**Ongoing learning:**
- Organic evolution from every interaction
- Continuous model refinement
- Periodic explicit check-ins as needed

---

## Development Plan

### Constraints

- **Builder**: Andrew (solo, with AI assistance)
- **Tools**: Claude Code (primary), Xcode (IDE for everything)
- **Time**: ~6 hours/week
- **Timeline**: MVP in ~2 months

**Tooling Philosophy**: Minimal stack, maximum power. Claude Code drives development; Xcode handles IDE needs, Swift builds, and file management. No VS Code, no Cursorâ€”two tools only.

### Learning Approach

- **70% teach-as-we-build**: Understand each component, why it's designed that way, alternatives considered
- **30% just-make-it-work**: Note topics for future learning once Hestia is stable
- Hestia eventually helps teach how she was built (recursive!)

### Version Roadmap

| Version | Scope |
|---------|-------|
| **v1.0** | Core chat, memory, modes, API (23 endpoints), native app, background tasks, Activity Timeline, iOS Shortcuts |
| **v1.5** | Menu bar + Quick Chat, Push notifications (APNs), Proactive intelligence |
| **v2.0** | Multi-user support, per-user credential isolation |

### Iteration Cadence

- **Bi-weekly**: Low-hanging fruit, bug fixes, minor tweaks
- **Every 6 weeks**: Feature sprints for substantial additions
- **Continuous**: Hestia identifies enhancement opportunities and proposes scheduling

### Success Criteria

**v1.0 (2 months):**
- [ ] Functional daily assistant
- [ ] Persistent memory across sessions
- [ ] Multi-device access via native app
- [ ] Response latency <4 seconds
- [ ] Basic learning queue operational

**6-month milestone:**
- [ ] Seamless daily operations handling
- [ ] Reliable overnight research
- [ ] Expert-level structured learning sessions
- [ ] Natural, intuitive interactions
- [ ] Full single-user feature set complete

---

## Project Structure

```
~/hestia/
â”œâ”€â”€ hestia/                           # Python backend
â”‚   â”œâ”€â”€ __init__.py
â”‚   â”œâ”€â”€ config/
â”‚   â”‚   â”œâ”€â”€ hestia-config.yaml        # Tia persona config
â”‚   â”‚   â”œâ”€â”€ artemis-config.yaml       # Mira persona config
â”‚   â”‚   â”œâ”€â”€ apollo-config.yaml        # Olly persona config
â”‚   â”‚   â”œâ”€â”€ inference-config.yaml
â”‚   â”‚   â”œâ”€â”€ memory-config.yaml
â”‚   â”‚   â””â”€â”€ access-config.yaml
â”‚   â”œâ”€â”€ logging/
â”‚   â”‚   â”œâ”€â”€ __init__.py
â”‚   â”‚   â”œâ”€â”€ structured-logger.py
â”‚   â”‚   â””â”€â”€ log-viewer.py
â”‚   â”œâ”€â”€ inference/
â”‚   â”‚   â”œâ”€â”€ __init__.py
â”‚   â”‚   â”œâ”€â”€ inference-client.py
â”‚   â”‚   â””â”€â”€ response-validator.py
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
â”‚   â”‚   â”œâ”€â”€ apple-ecosystem/
â”‚   â”‚   â”‚   â”œâ”€â”€ notes-client.py
â”‚   â”‚   â”‚   â”œâ”€â”€ reminders-client.py
â”‚   â”‚   â”‚   â””â”€â”€ calendar-client.py
â”‚   â”‚   â””â”€â”€ external-gate.py
â”‚   â”œâ”€â”€ persona/
â”‚   â”‚   â”œâ”€â”€ __init__.py
â”‚   â”‚   â”œâ”€â”€ personality-engine.py
â”‚   â”‚   â”œâ”€â”€ tia-prompts.py
â”‚   â”‚   â”œâ”€â”€ mira-prompts.py
â”‚   â”‚   â””â”€â”€ olly-prompts.py
â”‚   â””â”€â”€ api/
â”‚       â”œâ”€â”€ __init__.py
â”‚       â”œâ”€â”€ server.py
â”‚       â”œâ”€â”€ auth-handler.py
â”‚       â””â”€â”€ notification-manager.py
â”œâ”€â”€ HestiaApp/                        # Swift native app (Xcode project)
â”‚   â”œâ”€â”€ HestiaApp.xcodeproj
â”‚   â”œâ”€â”€ Shared/                       # Shared code across platforms
â”‚   â”‚   â”œâ”€â”€ Models/
â”‚   â”‚   â”œâ”€â”€ Services/
â”‚   â”‚   â”‚   â”œâ”€â”€ APIClient.swift
â”‚   â”‚   â”‚   â”œâ”€â”€ AuthService.swift
â”‚   â”‚   â”‚   â””â”€â”€ NotificationService.swift
â”‚   â”‚   â”œâ”€â”€ ViewModels/
â”‚   â”‚   â””â”€â”€ Utilities/
â”‚   â”œâ”€â”€ iOS/                          # iPhone/iPad specific
â”‚   â”‚   â”œâ”€â”€ Views/
â”‚   â”‚   â”‚   â”œâ”€â”€ ChatView.swift
â”‚   â”‚   â”‚   â”œâ”€â”€ CommandCenterView.swift
â”‚   â”‚   â”‚   â””â”€â”€ SettingsView.swift
â”‚   â”‚   â””â”€â”€ Assets.xcassets
â”‚   â”œâ”€â”€ macOS/                        # Mac specific
â”‚   â”‚   â”œâ”€â”€ Views/
â”‚   â”‚   â””â”€â”€ Assets.xcassets
â”‚   â””â”€â”€ Intents/                      # iOS Shortcuts integration
â”‚       â””â”€â”€ QuickCaptureIntent.swift
â”œâ”€â”€ admin/
â”‚   â”œâ”€â”€ dashboard/                    # Admin GUI
â”‚   â””â”€â”€ scripts/
â”‚       â”œâ”€â”€ backup.sh
â”‚       â”œâ”€â”€ restore.sh
â”‚       â””â”€â”€ health-check.sh
â”œâ”€â”€ data/
â”‚   â”œâ”€â”€ vector/
â”‚   â”œâ”€â”€ structured.db
â”‚   â”œâ”€â”€ user-model/
â”‚   â”œâ”€â”€ learning-queue/
â”‚   â””â”€â”€ research-corpus/
â”œâ”€â”€ logs/
â”œâ”€â”€ tests/
â”œâ”€â”€ docs/
â”‚   â”œâ”€â”€ runbook.md
â”‚   â”œâ”€â”€ recovery.md
â”‚   â””â”€â”€ architecture-decisions/
â””â”€â”€ README.md
```

---

---

## Reference Documents

For complete details on specific aspects of the architecture:

- **`hestia-security-architecture.md`**: Comprehensive security design with Pentagon-grade best practices
- **`hestia-decision-log.md`**: All architectural decisions (ADR-001 through ADR-012)
- **`hestia-development-plan.md`**: Phase-by-phase implementation guide
- **`hestia-project-context-enhanced.md`**: Quick reference for Claude collaboration
- **`hestia-prompt-templates.md`**: Templates for working with Claude Code

---

## Appendices

### A. Personality Configuration Reference

**Tia (Default Hestia)**
```yaml
name: tia
full-name: hestia
role: general-assistant
traits:
  sarcasm: 0.8
  wit: 0.8
  adaptiveness: 0.9
  pragmatism: 0.8
  empathy: 0.5
  curiosity: 0.6
  critical: 0.5
voice:
  self-reference: "I"
  other-modes: third-person  # "Mira would be better for this"
  verbosity: concise-default
  formality: casual-professional
```

**Mira (Artemis - Learning Mode)**
```yaml
name: mira
full-name: artemis
role: educator
traits:
  # Inherits base, with adjustments
  curiosity: 0.8              # Higher in learning mode
  socratic-tendency: 0.9      # Asks questions to guide learning
voice:
  self-reference: "I"
  other-modes: third-person
  verbosity: thorough         # More explanation in teaching
  formality: casual-professional
focus:
  - structured-learning-sessions
  - socratic-questioning
  - research-synthesis
  - competency-calibration
```

**Olly (Apollo - Project Mode)**
```yaml
name: olly
full-name: apollo
role: project-executor
traits:
  # Inherits base, with adjustments
  pragmatism: 0.95            # Maximum focus on getting things done
  tangent-tolerance: 0.1      # Actively redirects rabbit holes
voice:
  self-reference: "I"
  other-modes: third-person
  verbosity: minimal          # Terse, action-oriented
  formality: casual-professional
focus:
  - implementation
  - debugging
  - code-review
  - task-completion
```

### B. Source Trust Configuration

```yaml
source-tiers:
  canonical:
    - academic-papers
    - official-documentation
    - rfcs
    - language-specs
    - peer-reviewed-journals
    trust-level: 1.0
    citation-style: direct
    
  qualified:
    - expert-blogs
    - reputable-tech-journalism
    - conference-talks
    - established-tutorials
    trust-level: 0.7
    citation-style: with-context
    
  flagged:
    - forums
    - reddit
    - hackernews
    - stackoverflow
    - general-news
    trust-level: 0.4
    citation-style: with-caveat
    disclaimer: "Note: Forum sourceâ€”verify independently"
```

### C. Autonomy Level Configuration

```yaml
autonomy:
  default-level: 2
  
  level-definitions:
    1:
      name: suggest-only
      behavior: "Propose approach, wait for approval"
      
    2:
      name: draft-and-confirm
      behavior: "Complete work, present for approval before effect"
      
    3:
      name: act-with-summary
      behavior: "Execute and report afterward"
      authorization: ad-hoc  # User says "go ahead"
      
    4:
      name: silent-execution
      behavior: "Execute routine tasks, report only on exception"
      authorization: standing  # Pre-configured for specific task types
      
  standing-level-4-tasks:
    - overnight-research
    # Add more as authorized
    
  always-require-approval:
    - external-communication
    - financial-transactions
    - credential-usage
    - data-deletion
```

### D. Pushback Severity Scale

```yaml
pushback:
  max-instances: 1
  
  severity-scale:
    1:
      label: "Minor concern"
      description: "I'd suggest a different approach, but this works"
      
    2:
      label: "Moderate concern"
      description: "This has notable downsides worth considering"
      
    3:
      label: "Significant concern"
      description: "I recommend against thisâ€”here's why"
      
    4:
      label: "Strong concern"
      description: "This is likely to cause problems"
      
    5:
      label: "Critical concern"
      description: "I could not MORE strongly recommend against this"
      
  behavior: "State concern once with severity rating, then defer to user decision"
```

---

## Summary

Hestia is a personal AI operating system designed for Andrew's specific needs:

- **Daily assistant** with persistent, cross-device context
- **Research engine** with overnight autonomous capability and governed outputs
- **Personal educator** that tracks competency and teaches adaptively
- **Three modes** (Tia, Mira, Olly) for different interaction needs
- **Local-first architecture** on Mac Mini with secure multi-device access
- **Evolving user model** that grows more nuanced over time
- **Jarvis-like personality**: competent, dry, adaptive, never sycophantic

The system will be built iteratively over ~2 months to MVP, with Andrew learning alongside Claude Code. Success is measured by natural interaction, seamless context, and <4 second response latency.

At 6 months: a fully functional single-user system handling daily operations, research, and structured learning.

Beyond: multi-user support, enhanced security, and continuous sophistication.

---

*This specification reflects requirements gathered through 28 structured questions and serves as the authoritative reference for the Hestia initiative.*
