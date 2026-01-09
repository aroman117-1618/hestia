# Hestia Development Plan Updates (v4)

## Summary of Changes

This document contains the NEW and UPDATED sections for the development plan.
These should be integrated into `hestia-development-plan.md`.

---

## NEW: Phase 4.5: Background Task Management (Week 7-8)

### Objective
Enable asynchronous task execution for Quick Chat and iOS Shortcut inputs, with full visibility via Activity Timeline.

### Why This Phase
- iOS Shortcut quick capture is in v1.0 scope
- Fire-and-forget pattern requires background processing
- Users need visibility into what Hestia has done (Activity Timeline)
- Must integrate with autonomy levels (Level 3 for safe, escalate for unsafe)

### Tasks

#### 4.5.1 Background Task Schema
- [ ] Create `background_tasks` table in SQLite:
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
    escalated BOOLEAN DEFAULT FALSE,
    escalation_reason TEXT,
    notification_sent BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    
    INDEX idx_status (status),
    INDEX idx_created (created_at),
    INDEX idx_source (source)
);
```
- [ ] Create migrations for schema
- [ ] Add foreign key to link task outputs to memory chunks

#### 4.5.2 Task Queue Manager
- [ ] Create `hestia/orchestration/task_queue.py`:
  - `BackgroundTaskManager` class
  - Async task submission: `submit_task(input, source) -> task_id`
  - Task status polling: `get_status(task_id) -> TaskStatus`
  - Task history: `list_tasks(filters) -> List[Task]`
- [ ] Implement task worker loop (async)
- [ ] Handle task priorities (future: urgent vs. normal)
- [ ] Implement retry logic for failed tasks

#### 4.5.3 Autonomy Evaluator
- [ ] Create `hestia/orchestration/autonomy_evaluator.py`:
  - Analyze task to determine required autonomy level
  - Check against "always-require-approval" list:
    - External communication
    - Financial transactions
    - Credential usage
    - Data deletion
  - Return: `(autonomy_level, escalation_required, reason)`
- [ ] Integrate with task execution flow
- [ ] Log all autonomy decisions

#### 4.5.4 Task Execution Pipeline
- [ ] Modify request handler to support async execution:
  - Synchronous path: Normal conversation (wait for response)
  - Asynchronous path: Background task (immediate ack, process later)
- [ ] Implement execution flow:
  1. Receive task from queue
  2. Evaluate autonomy level
  3. If escalation needed: set status `awaiting_approval`, notify user
  4. If safe: execute task, update status, notify on completion
- [ ] Link task outputs to memory layer (auto-persist with audit trail)

#### 4.5.5 Notification Integration
- [ ] Create `hestia/api/notification_manager.py`:
  - `send_completion_notification(task_id)`
  - `send_approval_request(task_id)`
  - Support for push notifications (APNs)
  - Respect Focus modes (use appropriate priority)
- [ ] Notification templates:
  - Task completed: "Added 'Dentist' to calendar - Tue 2pm"
  - Approval needed: "Ready to send email. Review and approve?"
  - Task failed: "Couldn't complete: [reason]. Tap to retry."

#### 4.5.6 API Endpoints for Tasks
- [ ] `POST /v1/tasks` - Submit background task
- [ ] `GET /v1/tasks` - List tasks (with filters)
- [ ] `GET /v1/tasks/{id}` - Get task details
- [ ] `POST /v1/tasks/{id}/approve` - Approve escalated task
- [ ] `POST /v1/tasks/{id}/cancel` - Cancel pending task
- [ ] `POST /v1/tasks/{id}/retry` - Retry failed task

### Deliverables
- `hestia/orchestration/task_queue.py` module
- `hestia/orchestration/autonomy_evaluator.py` module
- `background_tasks` SQLite table with migrations
- API endpoints for task management
- Notification integration (basic, full APNs in Phase 6)

### Code Structure
```python
# hestia/orchestration/task_queue.py

from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_APPROVAL = "awaiting_approval"
    CANCELLED = "cancelled"

class TaskSource(Enum):
    QUICK_CHAT = "quick_chat"
    IOS_SHORTCUT = "ios_shortcut"
    CONVERSATION = "conversation"
    SCHEDULED = "scheduled"

@dataclass
class BackgroundTask:
    id: str
    created_at: datetime
    status: TaskStatus
    source: TaskSource
    input_summary: str
    output_summary: Optional[str] = None
    output_details: Optional[dict] = None
    autonomy_level: int = 3
    escalated: bool = False
    escalation_reason: Optional[str] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

class BackgroundTaskManager:
    """
    Manages asynchronous task execution for Quick Chat and iOS Shortcuts.
    
    Implements fire-and-forget pattern with full audit trail.
    Respects autonomy levels and escalates unsafe actions.
    """
    
    def __init__(self, db, orchestrator, notification_manager, logger):
        self.db = db
        self.orchestrator = orchestrator
        self.notifications = notification_manager
        self.logger = logger
    
    async def submit_task(
        self, 
        input_text: str, 
        source: TaskSource
    ) -> str:
        """
        Submit a new background task.
        Returns task_id immediately (fire-and-forget).
        """
        task_id = generate_uuid()
        
        task = BackgroundTask(
            id=task_id,
            created_at=datetime.utcnow(),
            status=TaskStatus.PENDING,
            source=source,
            input_summary=input_text[:200]  # Truncate for display
        )
        
        await self.db.insert_task(task)
        
        self.logger.log("task_submitted", {
            "task_id": task_id,
            "source": source.value,
            "input_length": len(input_text)
        })
        
        # Queue for async processing
        await self._enqueue(task_id)
        
        return task_id
    
    async def process_task(self, task_id: str) -> None:
        """
        Process a queued task.
        Called by worker loop.
        """
        task = await self.db.get_task(task_id)
        
        # Update status
        task.status = TaskStatus.IN_PROGRESS
        await self.db.update_task(task)
        
        try:
            # Evaluate autonomy
            autonomy = await self._evaluate_autonomy(task.input_summary)
            task.autonomy_level = autonomy.level
            
            if autonomy.requires_escalation:
                # Escalate to Level 2 (awaiting approval)
                task.status = TaskStatus.AWAITING_APPROVAL
                task.escalated = True
                task.escalation_reason = autonomy.reason
                await self.db.update_task(task)
                
                # Notify user for approval
                await self.notifications.send_approval_request(task)
                return
            
            # Execute task
            result = await self.orchestrator.handle_async(task.input_summary)
            
            # Update with results
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            task.output_summary = result.summary
            task.output_details = result.details
            await self.db.update_task(task)
            
            # Auto-persist to memory
            await self._persist_to_memory(task, result)
            
            # Notify completion
            await self.notifications.send_completion(task)
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            await self.db.update_task(task)
            
            self.logger.log("task_failed", {
                "task_id": task_id,
                "error": str(e),
                "severity": "HIGH"
            })
            
            await self.notifications.send_failure(task)
    
    async def approve_task(self, task_id: str) -> None:
        """
        Approve an escalated task for execution.
        """
        task = await self.db.get_task(task_id)
        
        if task.status != TaskStatus.AWAITING_APPROVAL:
            raise ValueError(f"Task {task_id} is not awaiting approval")
        
        self.logger.log("task_approved", {
            "task_id": task_id,
            "escalation_reason": task.escalation_reason,
            "severity": "HIGH"
        })
        
        # Re-queue for execution (now approved)
        task.status = TaskStatus.PENDING
        await self.db.update_task(task)
        await self._enqueue(task_id, approved=True)
```

### Testing Criteria
- [ ] Task submitted via iOS Shortcut endpoint appears in database
- [ ] Safe tasks (calendar, reminders) execute without approval
- [ ] Unsafe tasks (external communication) escalate correctly
- [ ] Completion notifications sent (mock APNs for testing)
- [ ] Approval flow works: escalate → approve → execute
- [ ] Failed tasks logged with full error context
- [ ] Task history queryable with filters
- [ ] Outputs persist to memory layer with audit trail

### Claude Checkpoint
Before proceeding to Phase 5, share:
- Task queue implementation
- Autonomy evaluator logic
- Sample task lifecycle (submit → process → complete)
- Escalation flow demonstration

---

## UPDATED: Phase 6: Access Layer & Native App (Week 9-10)

### Objective
Enable secure remote access from any device via native Swift app, including Activity Timeline for background task visibility.

### Tasks

#### 6.1 API Server
- [ ] FastAPI application
- [ ] Endpoint: `POST /v1/chat` (synchronous conversation)
- [ ] Endpoint: `POST /v1/tasks` (async background task submission)
- [ ] Endpoint: `GET /v1/tasks` (task history for Activity Timeline)
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
- [ ] **ActivityTimelineView.swift** ← NEW
- [ ] Auto-lock functionality (15/30/60 minutes configurable)
- [ ] Push notification support respecting Focus modes

#### 6.5 Activity Timeline UI (NEW)
- [ ] Create `ActivityTimelineView.swift`:
  - List of all background tasks (recent first)
  - Status indicators: ✓ completed, ⏳ in progress, ⚠️ awaiting approval, ✗ failed
  - Expandable rows for full details
  - Pull-to-refresh
- [ ] Task detail view:
  - Input summary
  - Output summary and details
  - Timestamps (created, completed)
  - Autonomy level used
  - Escalation reason (if applicable)
- [ ] Quick actions:
  - Approve (for escalated tasks)
  - Cancel (for pending tasks)
  - Retry (for failed tasks)
- [ ] Filters:
  - By status (all, completed, pending, failed)
  - By source (quick chat, iOS shortcut, conversation)
  - By date range

#### 6.6 iOS Shortcut Integration
- [ ] QuickCaptureIntent.swift for Shortcuts app
- [ ] Fire-and-forget input to Hestia (calls `/v1/tasks` endpoint)
- [ ] Immediate "Got it ✓" confirmation
- [ ] Links to Activity Timeline for results

### Deliverables
- `hestia/api/` module with FastAPI server
- `HestiaApp/` Xcode project with iOS and macOS targets
- Activity Timeline view integrated into Command Center
- Native app accessible at `https://hestia.your-tailnet:8443/`
- Device certificate management scripts
- iOS Shortcut for quick capture

### Activity Timeline Mockup
```
┌─────────────────────────────────────────────────────────────┐
│  Activity                                              ⚙️   │
├─────────────────────────────────────────────────────────────┤
│  Filter: [All ▼]                              🔄 Refresh    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Today                                                      │
│  ───────────────────────────────────────────────────────    │
│  ✓ 2:34 PM  Added "Dentist" to calendar                    │
│             via iOS Shortcut                                │
│             Tuesday, Jan 14 at 2:00 PM                      │
│                                                    [View >] │
│                                                             │
│  ⚠️ 1:15 PM  Email to dentist ready for review              │
│             via iOS Shortcut                                │
│             [Approve]  [Edit]  [Cancel]                     │
│                                                             │
│  ⏳ 12:30 PM Research: "Best credit cards for travel"       │
│             via Conversation                                │
│             In progress...                                  │
│                                                             │
│  ✓ 9:02 AM  Created reminder: "Call mom"                   │
│             via iOS Shortcut                                │
│             Due: Tomorrow 6:00 PM                           │
│                                                             │
│  Yesterday                                                  │
│  ───────────────────────────────────────────────────────    │
│  ✓ 11:45 PM Overnight research completed                   │
│             "Hestia security architecture"                  │
│                                           [View Full Report]│
│                                                             │
│  ✗ 3:22 PM  Failed: "Book flight to NYC"                   │
│             Error: Could not access travel site             │
│                                              [Retry] [View] │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Testing Criteria
- [ ] API responds to authenticated requests
- [ ] Unauthenticated requests rejected
- [ ] Rate limiting enforced
- [ ] App runs on iPhone, iPad, Mac via Xcode
- [ ] Face ID / Touch ID authentication works
- [ ] Auto-lock triggers correctly
- [ ] iOS Shortcut successfully sends input to Hestia
- [ ] Activity Timeline shows task history
- [ ] Approval flow works from Activity Timeline
- [ ] Push notifications received for task completion

### Claude Checkpoint
Share:
- API schema design (including task endpoints)
- Authentication flow
- SwiftUI views for review (ChatView, CommandCenterView, ActivityTimelineView)
- Security review of exposed surface

---

## UPDATED: Checklist Summary

### Phase 4: Orchestration
- [ ] Request handler
- [ ] State machine
- [ ] Mode manager (Tia/Mira/Olly)
- [ ] Validation pipeline
- [ ] **CHECKPOINT 3**: Orchestration calibration ✓

### Phase 4.5: Background Task Management (NEW)
- [ ] Background task schema (SQLite)
- [ ] Task queue manager
- [ ] Autonomy evaluator
- [ ] Task execution pipeline
- [ ] Notification integration
- [ ] API endpoints for tasks
- [ ] **CHECKPOINT 3.5**: Background tasks calibration ✓

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
- [ ] Activity Timeline view (NEW)
- [ ] iOS Shortcut integration
- [ ] **CHECKPOINT 5**: iOS app calibration ✓

### Phase 7: Integration
- [ ] End-to-end testing (including background tasks)
- [ ] Monitoring
- [ ] Reliability hardening
- [ ] Security testing
- [ ] **CHECKPOINT 6**: Production readiness calibration ✓

---

## Version Targets (Updated)

| Version | Target | Key Deliverables |
|---------|--------|------------------|
| v0.1 | Week 4 | Inference + logging + security + terminal chat |
| v0.2 | Week 6 | Memory + conversation continuity |
| v0.3 | Week 8 | Personality + basic user model + background tasks |
| v0.4 | Week 10 | iOS app + multi-device + Activity Timeline |
| v1.0 | Week 11+ | **MVP**: Daily driver with iOS Shortcut, background tasks |
| v1.5 | +2-3 months | Menu bar + Quick Chat, OAuth email, cloud LLM, screen capture |
| v2.0 | ~6 months | Multi-user support, advanced key management |
