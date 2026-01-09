# Hestia Documentation Update Summary (v4)

**Date**: 2025-01-09
**Changes**: Quick Chat, Activity Timeline, Background Tasks

---

## Overview

This update adds support for asynchronous background task execution, enabling the fire-and-forget pattern for iOS Shortcuts (v1.0) and macOS Quick Chat (v1.5).

---

## New Features Added

### 1. Background Task Management (v1.0)
- Asynchronous task execution for iOS Shortcut inputs
- Task queue with persistent storage
- Autonomy evaluation (Level 3 for safe, escalate for unsafe)
- Full audit trail

### 2. Activity Timeline (v1.0)
- Central view showing all Hestia background work
- Part of Command Center (iPad/Mac)
- Shows completed, in-progress, and awaiting-approval tasks
- Quick actions: approve, cancel, retry

### 3. macOS Menu Bar + Quick Chat (v1.5)
- Lightweight menu bar app
- Global keyboard shortcut (⌘⇧H)
- Fire-and-forget input popup
- Connection status indicator

---

## Files Updated

### 1. hestia-project-context-enhanced.md
**Key changes:**
- Added Background Tasks & Activity Timeline section
- Updated Input Methods section
- Added Quick Chat to Technical Stack
- Updated Design Principles (exception for auto-persist on explicit requests)
- Updated Autonomy Levels (Level 3 for Quick Chat/Shortcut)
- Added Phase 4.5 to Current Phase list
- Updated Version Targets (v1.5 now includes menu bar)
- Added new glossary terms

### 2. hestia-decision-log.md
**Key changes:**
- Added ADR-014: Background Tasks and Asynchronous Execution
- Updated ADR-002: Added exception for explicit background task outputs
- Updated ADR-010: Clarified cloud LLM is v1.5 (multi-stage retrieval handles v1.0)

### 3. hestia-development-plan.md
**Key changes:**
- Added Phase 4.5: Background Task Management
- Updated Phase 6: Added Activity Timeline UI tasks
- Added background_tasks SQLite schema
- Added BackgroundTaskManager code structure
- Updated checklist with new phases
- Updated version targets

### 4. hestia-initiative-enhanced.md
**Key changes:**
- Updated Core Capabilities section with input methods table
- Added Section 5: Background Tasks and Activity Timeline
- Added Quick Capture Methods to User Experience
- Updated System Architecture diagram
- Updated Version Roadmap
- Updated Success Criteria

---

## Backward Compatibility

All changes are backward compatible:

| Existing Feature | Impact | Notes |
|------------------|--------|-------|
| Conversation (Level 2 default) | No change | Still default for real-time chat |
| iOS Shortcut | Enhanced | Now uses background task queue |
| Memory persistence staging | No change | Still required for conversation-initiated changes |
| External gate | No change | Still required for all external communication |
| Autonomy levels | Extended | Level 3 now also triggered by Quick Chat/Shortcut |

---

## New Database Schema

```sql
CREATE TABLE background_tasks (
    id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    completed_at DATETIME,
    status TEXT NOT NULL,  -- 'pending', 'in_progress', 'completed', 'failed', 'awaiting_approval'
    source TEXT NOT NULL,  -- 'quick_chat', 'ios_shortcut', 'conversation', 'scheduled'
    input_summary TEXT,
    output_summary TEXT,
    output_details TEXT,   -- JSON
    autonomy_level INTEGER,
    escalated BOOLEAN DEFAULT FALSE,
    escalation_reason TEXT,
    notification_sent BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    
    INDEX idx_status (status),
    INDEX idx_created (created_at),
    INDEX idx_source (source)
);
```

---

## New API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/tasks` | POST | Submit background task |
| `/v1/tasks` | GET | List tasks (Activity Timeline) |
| `/v1/tasks/{id}` | GET | Get task details |
| `/v1/tasks/{id}/approve` | POST | Approve escalated task |
| `/v1/tasks/{id}/cancel` | POST | Cancel pending task |
| `/v1/tasks/{id}/retry` | POST | Retry failed task |

---

## Autonomy Model for Background Tasks

| Task Type | Autonomy | Behavior |
|-----------|----------|----------|
| Internal actions | Level 3 | Execute → Notify |
| Research | Level 3 | Execute → Notify with summary |
| External communication | Level 2 | Draft → Await approval |
| Financial | Level 2 | Never auto-execute |
| Data deletion | Level 2 | Never auto-execute |
| Credential access | Level 2 | Biometric + approval |

---

## Phase Timeline Impact

| Phase | Change | Time Impact |
|-------|--------|-------------|
| Phase 4.5 (NEW) | Background Task Management | +4-5 hours |
| Phase 6 | Activity Timeline UI | +2-3 hours |
| Total | | +6-8 hours |

Still fits within 6 hours/week budget over the project timeline.

---

## Files in This Update

1. `hestia-project-context-enhanced-v4.md` - Complete updated file
2. `hestia-decision-log-v4.md` - Complete updated file  
3. `hestia-development-plan-updates-v4.md` - New/updated sections only
4. `hestia-initiative-updates-v4.md` - New/updated sections only
5. `hestia-v4-update-summary.md` - This file

---

## Integration Instructions

To integrate these updates into the project:

1. **Replace** `hestia-project-context-enhanced.md` with `hestia-project-context-enhanced-v4.md`

2. **Replace** `hestia-decision-log.md` with `hestia-decision-log-v4.md`

3. **Insert** Phase 4.5 from `hestia-development-plan-updates-v4.md` after Phase 4 in `hestia-development-plan.md`

4. **Update** Phase 6 in `hestia-development-plan.md` with Activity Timeline tasks from updates file

5. **Insert** new sections from `hestia-initiative-updates-v4.md` into appropriate locations in `hestia-initiative-enhanced.md`

---

## Verification Checklist

After integration, verify:

- [ ] ADR-014 appears in decision log
- [ ] Phase 4.5 appears in development plan
- [ ] Activity Timeline mentioned in Phase 6
- [ ] Background tasks mentioned in project context
- [ ] v1.5 scope includes menu bar + Quick Chat
- [ ] Autonomy section includes Quick Chat/Shortcut behavior
- [ ] Glossary includes Activity Timeline, Quick Chat, Background task
