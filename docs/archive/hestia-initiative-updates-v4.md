# Hestia Initiative Updates (v4)

## Summary of Changes

This document contains the NEW and UPDATED sections for `hestia-initiative-enhanced.md`.
These sections should be integrated into the main document.

---

## UPDATED: Core Capabilities Section

### 1. Task Delegation and Daily Operations

**Primary use case**: Conversational task delegation with persistent memory.

**Capabilities:**
- Accept and execute tasks across domains
- Maintain context across sessions, days, and weeks
- Access Apple ecosystem (Notes, Reminders, Calendar) with full CRUD
- Access Gmail/GDrive for migration to Apple ecosystem
- Manage files, run scripts, interact with development tools
- **Background task execution** for async commands (Quick Chat, iOS Shortcuts)

**Input Methods:**

| Method | Platform | Pattern | Default Autonomy |
|--------|----------|---------|------------------|
| **Conversation** | All | Real-time back-and-forth | Level 2 (draft and confirm) |
| **iOS Shortcut** | iOS | Fire-and-forget | Level 3 for safe actions |
| **Quick Chat** | macOS (v1.5) | Fire-and-forget popup | Level 3 for safe actions |

**Autonomy Levels:**

| Level | Behavior | Usage |
|-------|----------|-------|
| 1 | Suggest only | "Here's how I'd approach this—proceed?" |
| 2 | Draft and confirm | Does work, shows result, waits for approval **(DEFAULT for conversations)** |
| 3 | Act with summary | Executes, reports afterward | Ad hoc ("go ahead") or Quick Chat/Shortcut |
| 4 | Silent execution | Does routine tasks, reports only on exception | Recurring/automated tasks |

**Autonomy Rules:**
- Default is Level 2 (conservative) for conversations
- User can authorize Level 3 as one-off: "Go ahead"
- **Quick Chat / iOS Shortcut implies Level 3** for safe internal actions
- Level 4 reserved for designated recurring tasks (e.g., overnight research)
- Feedback loop: User corrections logged and inform long-term behavior adjustment
- **Strict gate on external communication**: Nothing sent externally without explicit approval

**Actions That Always Require Approval (Even at Level 3/4):**
- External communication (emails, third-party API calls)
- Financial transactions
- Credential usage (requires biometric confirmation)
- Data deletion

---

## NEW: Section 5. Background Tasks and Activity Timeline

### Background Task Processing

**Purpose**: Enable fire-and-forget quick capture while maintaining full visibility and control.

**Task Lifecycle:**
1. **Submission**: User sends command via iOS Shortcut or Quick Chat
2. **Acknowledgment**: Immediate "Got it ✓" confirmation (UI dismisses)
3. **Evaluation**: Hestia determines autonomy level and checks escalation rules
4. **Execution or Escalation**:
   - Safe actions: Execute immediately, notify on completion
   - Unsafe actions: Set status to "awaiting approval", notify user
5. **Completion**: Push notification sent (respects Focus modes)
6. **Persistence**: Results stored in Activity Timeline and memory layer

**Autonomy for Background Tasks:**

| Task Type | Autonomy | Behavior |
|-----------|----------|----------|
| Internal actions (calendar, reminders, notes) | Level 3 | Execute → Notify |
| Research (web search, memory search) | Level 3 | Execute → Notify with summary |
| External communication | Level 2 | Draft → Await approval → Execute |
| Financial transactions | Level 2 | Never auto-execute |
| Data deletion | Level 2 | Never auto-execute |
| Credential access | Level 2 | Requires biometric + approval |

**Escalation Flow:**
```
User submits: "Email my dentist to confirm appointment"
                    │
                    ▼
Hestia evaluates: External communication detected
                    │
                    ▼
Status: "awaiting_approval"
                    │
                    ▼
Notification: "Ready to send email. Review and approve?"
                    │
                    ▼
User taps notification → Opens Activity Timeline
                    │
                    ▼
User reviews draft → [Approve] or [Edit] or [Cancel]
                    │
                    ▼
If approved: Execute → Send completion notification
```

### Activity Timeline

**Purpose**: Central view showing all Hestia background work and task history.

**Location**: Tab/widget in Command Center (iPad/Mac), accessible from main nav (iPhone)

**Content:**
- All background tasks (recent first)
- Status indicators: ✓ completed, ⏳ in progress, ⚠️ awaiting approval, ✗ failed
- Expandable details for each task
- Quick actions: approve, cancel, retry

**Task Entry Structure:**
```
┌─────────────────────────────────────────────────────────────┐
│ ✓ 2:34 PM  Added "Dentist" to calendar                     │
│            via iOS Shortcut                                 │
│            Tuesday, Jan 14 at 2:00 PM                       │
│                                                    [View >] │
└─────────────────────────────────────────────────────────────┘
```

**Filters Available:**
- By status: All, Completed, Pending, Failed, Awaiting Approval
- By source: iOS Shortcut, Quick Chat, Conversation, Scheduled
- By date range

**Task Details View:**
- Full input text
- Complete output/result
- Timestamps (created, completed)
- Autonomy level used
- Escalation reason (if applicable)
- Error message (if failed)
- Link to related memory chunks

### Output Persistence

**Background task outputs auto-persist** to memory layer:
- No staging required (user explicitly requested the action)
- Full audit trail maintained
- Outputs searchable: "What did I ask you to do last week?"
- Links between task and resulting memory chunks

**Security compliance:**
- All task submissions logged
- All executions logged with inputs/outputs
- Escalation decisions logged with reasons
- Approval actions logged (who, when)
- No sensitive data logged (credential values, etc.)

---

## NEW: Section in User Experience

### Quick Capture Methods

**iOS Shortcut (v1.0)**

Siri Shortcuts integration for rapid input:
- Trigger: Shortcut widget, Siri voice command, or automation
- Input: Text or voice transcription
- Response: Immediate "Got it ✓" confirmation
- Result: Push notification when complete
- Visibility: Full details in Activity Timeline

**Example flow:**
```
User: [Triggers Shortcut] "Add milk to grocery list"
Shortcut: [Shows] "Got it ✓"
[Background: Hestia adds item to Reminders]
[Push notification]: "Added 'milk' to Grocery List"
```

**macOS Quick Chat (v1.5)**

Menu bar popup for quick commands:
- Trigger: Global keyboard shortcut (⌘⇧H) or menu bar click
- Input: Text field popup
- Response: Immediate dismissal with "Got it ✓"
- Result: Push notification when complete
- Visibility: Full details in Activity Timeline

**Menu bar features:**
- Connection status indicator
- Recent commands (quick repeat)
- "Open Hestia" (launches full app)
- "Quick Chat..." (opens input popup)

---

## UPDATED: Technical Architecture Section

### System Architecture (Updated)

```
┌─────────────────────────────────────────────────────────────┐
│                     Apple Devices                           │
│              (Stateless thin clients)                       │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  iPhone  │  │   iPad   │  │   Mac    │  │ Menu Bar │   │
│  │   App    │  │   App    │  │   App    │  │  (v1.5)  │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │             │             │             │          │
│  ┌────┴─────────────┴─────────────┴─────────────┴────┐    │
│  │              iOS Shortcuts Integration             │    │
│  └────────────────────────┬──────────────────────────┘    │
└───────────────────────────┼────────────────────────────────┘
                            │ HTTPS / Tailscale
┌───────────────────────────▼────────────────────────────────┐
│                    Access Layer                             │
│         (Authentication, rate limiting, routing)            │
│                                                             │
│  Endpoints:                                                 │
│  - POST /v1/chat (synchronous conversation)                │
│  - POST /v1/tasks (async background task)                  │
│  - GET /v1/tasks (Activity Timeline data)                  │
└───────────────────────────┬────────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────────┐
│                  Orchestration Layer                        │
│    (Task decomposition, state management, validation)       │
│                                                             │
│  Components:                                                │
│  - Request Handler (sync conversations)                    │
│  - Background Task Manager (async tasks)                   │
│  - Autonomy Evaluator (Level 2/3/4 decisions)             │
│  - Mode Manager (Tia/Mira/Olly)                           │
└───────────────────────────┬────────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────────┐
│                    Memory Layer                             │
│  (Vector store, structured JSON, domain files, ephemeral)   │
│                                                             │
│  Tables:                                                    │
│  - conversation_chunks (with tags)                         │
│  - background_tasks (Activity Timeline)                    │
│  - user_model                                              │
│  - learning_queue                                          │
└───────────────────────────┬────────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────────┐
│                   Inference Layer                           │
│           (Mixtral 8x7B via Ollama)                        │
└───────────────────────────┬────────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────────┐
│                   Execution Layer                           │
│        (Tool calls, script execution, file operations)      │
│        (Apple ecosystem CLIs)                               │
└─────────────────────────────────────────────────────────────┘
```

---

## UPDATED: Development Plan Section

### Version Roadmap (Updated)

| Version | Timeline | Capabilities |
|---------|----------|--------------|
| **v0.1** | Weeks 1-3 | Basic inference, logging infrastructure, terminal chat |
| **v0.2** | Weeks 4-5 | Memory layer, conversation continuity |
| **v0.3** | Weeks 6-8 | Personality tuned, basic user model, **background tasks** |
| **v0.4** | Weeks 8-9 | iOS app (basic), Tailscale access, multi-device, **Activity Timeline** |
| **v1.0** | Week 10+ | **MVP**: Daily driver with chat, memory, **iOS Shortcut**, learning queue |
| **v1.5** | +2-3 months | **Menu bar + Quick Chat**, OAuth email, cloud LLM fallback, screen capture |
| **v2.0** | ~6 months | Multi-user support, secure credential storage, cloud escalation |

---

## UPDATED: Success Criteria

### v1.0 (2 months):
- [ ] Functional daily assistant
- [ ] Persistent memory across sessions
- [ ] Multi-device access via native app
- [ ] Response latency <4 seconds
- [ ] Basic learning queue operational
- [ ] **iOS Shortcut quick capture working**
- [ ] **Activity Timeline showing task history**
- [ ] **Background tasks execute correctly (Level 3 for safe, escalate for unsafe)**

### 6-month milestone:
- [ ] Seamless daily operations handling
- [ ] Reliable overnight research
- [ ] Expert-level structured learning sessions
- [ ] Natural, intuitive interactions
- [ ] Full single-user feature set complete
- [ ] **Menu bar + Quick Chat operational (macOS)**
