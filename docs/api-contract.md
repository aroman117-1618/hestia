# Hestia API Contract

**Status**: Phase 6a + Phase 4.5 - COMPLETE
**Last Updated**: 2025-01-12

## Executive Summary

The FastAPI REST API layer is now **fully implemented** including background task management. The API provides HTTP access to Hestia backend capabilities including chat, memory management, mode switching, tool inspection, and background task lifecycle.

**Implemented Endpoints**: 47 (18 core + 6 task management + 7 orders + 9 agents + 6 user + 1 proactive)
**Test Coverage**: 362 passing tests

**API Location**: `hestia/api/`
**Server Port**: 8443
**Documentation**: http://localhost:8443/docs (Swagger UI)

---

## Quick Start

```bash
# Start the server
cd /path/to/hestia
source .venv/bin/activate
python -m hestia.api.server

# Register a device (no auth required)
curl -X POST http://localhost:8443/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"device_name": "my-device", "device_type": "cli"}'

# Use the returned token for all subsequent requests
export TOKEN="your-jwt-token"

# Send a message
curl -X POST http://localhost:8443/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Hestia-Device-Token: $TOKEN" \
  -d '{"message": "Hello Tia"}'
```

---

## Authentication

All endpoints except `/v1/health`, `/v1/ping`, and `/v1/auth/register` require a JWT device token.

### Device Registration

```
POST /v1/auth/register
```

**Request:**
```json
{
  "device_name": "my-iphone",
  "device_type": "ios",
  "device_info": {}
}
```

**Response:**
```json
{
  "device_id": "device-abc123def456",
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "expires_at": "2027-01-11T00:00:00Z"
}
```

### Using the Token

Include the token in all authenticated requests:

```
X-Hestia-Device-Token: <your-token>
```

---

## API Endpoints

### Health & Status

#### GET /v1/ping

Simple connectivity check (no auth).

**Response:**
```json
{
  "status": "ok",
  "message": "pong"
}
```

#### GET /v1/health

System health check (no auth).

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-11T15:30:00Z",
  "components": {
    "inference": {
      "status": "healthy",
      "ollama_available": true,
      "primary_model_available": true
    },
    "memory": {
      "status": "healthy",
      "vector_count": 1234
    },
    "state_machine": {
      "status": "healthy",
      "active_tasks": 0
    },
    "tools": {
      "status": "healthy",
      "registered_tools": 23,
      "tool_names": ["list_calendars", "create_event", ...]
    }
  }
}
```

---

### Core Chat

#### POST /v1/chat

Main conversation endpoint.

**Request:**
```json
{
  "message": "Hello Tia",
  "session_id": "sess-abc123",
  "device_id": "hestia-iphone",
  "context_hints": {}
}
```

**Response:**
```json
{
  "request_id": "req-xyz789",
  "content": "Hello! How can I help you today?",
  "response_type": "text",
  "mode": "tia",
  "session_id": "sess-abc123",
  "timestamp": "2025-01-11T15:30:00Z",
  "metrics": {
    "tokens_in": 45,
    "tokens_out": 189,
    "duration_ms": 1850
  },
  "tool_calls": null,
  "error": null
}
```

**Response Types:**
- `text`: Normal text response
- `error`: Error occurred (check `error` field)
- `tool_call`: Tool execution requested
- `clarification`: Hestia needs more information

---

### Mode Management

#### GET /v1/mode

Get current mode and available modes.

**Response:**
```json
{
  "current": {
    "mode": "tia",
    "name": "Tia",
    "full_name": "Hestia",
    "description": "Default mode for daily operations and quick queries",
    "traits": [
      "Efficient and direct",
      "Competent without being showy",
      "Occasionally sardonic wit"
    ]
  },
  "available": ["tia", "mira", "olly"]
}
```

#### POST /v1/mode/switch

Switch to a different mode.

**Request:**
```json
{
  "mode": "mira"
}
```

**Response:**
```json
{
  "previous_mode": "tia",
  "current_mode": "mira",
  "persona": {
    "mode": "mira",
    "name": "Mira",
    "full_name": "Artemis",
    "description": "Learning mode for Socratic teaching and research",
    "traits": ["Socratic approach", "Patient and thorough"]
  }
}
```

#### GET /v1/mode/{mode_name}

Get details about a specific mode.

---

### Memory Management (ADR-002)

#### GET /v1/memory/staged

List pending memory updates requiring human review.

**Response:**
```json
{
  "pending": [
    {
      "chunk_id": "chunk-abc123def",
      "content": "User prefers detailed explanations",
      "chunk_type": "preference",
      "tags": {
        "topics": ["communication", "preferences"],
        "entities": [],
        "mode": "mira"
      },
      "metadata": {
        "confidence": 0.85,
        "has_decision": false
      },
      "staged_at": "2025-01-11T14:00:00Z"
    }
  ],
  "count": 1
}
```

#### POST /v1/memory/approve/{chunk_id}

Approve a staged memory update.

**Request:**
```json
{
  "reviewer_notes": "Confirmed preference"
}
```

**Response:**
```json
{
  "chunk_id": "chunk-abc123def",
  "status": "committed",
  "scope": "long_term"
}
```

#### POST /v1/memory/reject/{chunk_id}

Reject a staged memory update.

**Response:**
```json
{
  "chunk_id": "chunk-abc123def",
  "status": "rejected",
  "scope": null
}
```

#### GET /v1/memory/search

Search memory with semantic and tag filters.

**Query Parameters:**
- `q` (required): Search query
- `topics`: Filter by topics (array)
- `entities`: Filter by entities (array)
- `limit`: Max results (default 10, max 100)
- `session_id`: Filter by session

**Response:**
```json
{
  "results": [
    {
      "chunk_id": "chunk-abc123def",
      "content": "User mentioned they work at a tech startup...",
      "relevance_score": 0.89,
      "match_type": "semantic",
      "timestamp": "2025-01-09T10:00:00Z",
      "tags": {
        "topics": ["career", "workplace"],
        "entities": ["tech startup"]
      }
    }
  ],
  "count": 1
}
```

---

### Session Management

#### POST /v1/sessions

Create a new session.

**Request:**
```json
{
  "mode": "tia",
  "device_id": "hestia-iphone"
}
```

**Response:**
```json
{
  "session_id": "sess-xyz789",
  "mode": "tia",
  "created_at": "2025-01-11T16:00:00Z"
}
```

#### GET /v1/sessions/{session_id}/history

Get conversation history for a session.

**Response:**
```json
{
  "session_id": "sess-abc123",
  "mode": "tia",
  "started_at": "2025-01-11T14:00:00Z",
  "last_activity": "2025-01-11T15:30:00Z",
  "turn_count": 5,
  "messages": [
    {"role": "user", "content": "Hello Tia"},
    {"role": "assistant", "content": "Hello! How can I help?"}
  ]
}
```

#### DELETE /v1/sessions/{session_id}

End a session (cleans up in-memory cache, preserves history).

---

### Background Tasks (IMPLEMENTED - Phase 4.5)

> **Implementation Status**: COMPLETE (2025-01-12)
> Module: `hestia/tasks/` (models.py, database.py, manager.py)
> Routes: `hestia/api/routes/tasks.py`
> Tests: 60 passing in `tests/test_tasks.py`

#### POST /v1/tasks

Submit a background task for async execution.

**Request:**
```json
{
  "input": "Schedule dentist appointment for next Tuesday",
  "source": "ios_shortcut"
}
```

**Response:**
```json
{
  "task_id": "task-abc123def456",
  "status": "pending",
  "message": "Got it ✓",
  "created_at": "2025-01-12T10:00:00Z"
}
```

#### GET /v1/tasks

List background tasks with optional filters.

**Query Parameters:**
- `status`: Filter by status (pending, in_progress, completed, failed, awaiting_approval)
- `source`: Filter by source (quick_chat, ios_shortcut, conversation)
- `limit`: Max results (default 20, max 100)
- `offset`: Pagination offset

**Response:**
```json
{
  "tasks": [
    {
      "task_id": "task-abc123",
      "status": "completed",
      "source": "ios_shortcut",
      "input_summary": "Schedule dentist...",
      "output_summary": "Added to calendar: Tue 2pm",
      "created_at": "2025-01-12T10:00:00Z",
      "completed_at": "2025-01-12T10:00:05Z"
    }
  ],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

#### GET /v1/tasks/{task_id}

Get details for a specific task.

**Response:**
```json
{
  "task_id": "task-abc123",
  "status": "completed",
  "source": "ios_shortcut",
  "input_summary": "Schedule dentist appointment for next Tuesday",
  "output_summary": "Added to calendar: Tue 2pm",
  "output_details": {
    "event_id": "evt-xyz789",
    "calendar": "Personal",
    "start": "2025-01-14T14:00:00Z",
    "end": "2025-01-14T15:00:00Z"
  },
  "autonomy_level": 3,
  "escalated": false,
  "created_at": "2025-01-12T10:00:00Z",
  "completed_at": "2025-01-12T10:00:05Z"
}
```

#### POST /v1/tasks/{task_id}/approve

Approve an escalated task awaiting approval.

**Request:**
```json
{
  "reviewer_notes": "Approved for sending"
}
```

**Response:**
```json
{
  "task_id": "task-abc123",
  "status": "in_progress",
  "message": "Task approved and resumed"
}
```

#### POST /v1/tasks/{task_id}/cancel

Cancel a pending task.

**Response:**
```json
{
  "task_id": "task-abc123",
  "status": "cancelled",
  "message": "Task cancelled"
}
```

#### POST /v1/tasks/{task_id}/retry

Retry a failed task.

**Response:**
```json
{
  "task_id": "task-abc123",
  "status": "pending",
  "message": "Task queued for retry"
}
```

---

### Tools

#### GET /v1/tools

List all available tools.

**Response:**
```json
{
  "tools": [
    {
      "name": "list_calendars",
      "description": "List all available calendars",
      "category": "calendar",
      "requires_approval": false,
      "parameters": {}
    },
    {
      "name": "create_event",
      "description": "Create a new calendar event",
      "category": "calendar",
      "requires_approval": true,
      "parameters": {
        "title": {"type": "string", "description": "Event title", "required": true},
        "start": {"type": "string", "description": "Start time (ISO)", "required": true},
        "end": {"type": "string", "description": "End time (ISO)", "required": true}
      }
    }
  ],
  "count": 23
}
```

#### GET /v1/tools/categories

List tool categories with counts.

**Response:**
```json
{
  "categories": {
    "calendar": {"count": 5, "tools": ["list_calendars", "list_events", ...]},
    "reminders": {"count": 6, "tools": ["list_reminder_lists", ...]},
    "notes": {"count": 5, "tools": ["list_note_folders", ...]},
    "mail": {"count": 5, "tools": ["list_mailboxes", ...]},
    "file": {"count": 2, "tools": ["read_file", "write_file"]}
  },
  "total_tools": 23
}
```

#### GET /v1/tools/{tool_name}

Get details about a specific tool.

---

## Error Responses

All errors follow this format:

```json
{
  "error": "validation_error",
  "message": "Request content cannot be empty",
  "request_id": "req-xyz789",
  "timestamp": "2025-01-11T15:30:00Z"
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `validation_error` | 400 | Invalid request format |
| `empty_input` | 400 | Request content empty |
| `input_too_long` | 400 | Exceeds 32K character limit |
| `forbidden_pattern` | 400 | Prompt injection detected |
| `unauthorized` | 401 | Invalid or missing device token |
| `not_found` | 404 | Resource not found |
| `timeout` | 504 | Inference timed out |
| `internal_error` | 500 | Unexpected server error |
| `model_unavailable` | 503 | No inference model available |

---

## Implementation Details

### Files

```
hestia/api/
├── __init__.py              # Package exports
├── server.py                # FastAPI app, lifecycle
├── schemas.py               # Pydantic models
├── middleware/
│   ├── __init__.py
│   └── auth.py              # JWT authentication
└── routes/
    ├── __init__.py
    ├── auth.py              # /v1/auth/*
    ├── health.py            # /v1/health, /v1/ping
    ├── chat.py              # /v1/chat
    ├── mode.py              # /v1/mode/*
    ├── memory.py            # /v1/memory/*
    ├── sessions.py          # /v1/sessions/*
    ├── tools.py             # /v1/tools/*
    └── tasks.py             # /v1/tasks/* (IMPLEMENTED - Phase 4.5)
```

### Dependencies

- `fastapi>=0.104.0`
- `uvicorn[standard]>=0.24.0`
- `python-jose[cryptography]>=3.3.0`
- `pydantic>=2.0.0`

### Testing

```bash
# Run the test script
./scripts/test-api.sh

# Or test manually with curl
curl http://localhost:8443/v1/health | jq
```

---

## Orders API (Phase 6b - COMPLETE)

Orders are scheduled, recurring prompts that Hestia executes autonomously (like standing orders).

### POST /v1/orders

Create a new order.

**Request:**
```json
{
  "name": "Morning Brief",
  "prompt": "Summarize today's calendar, important emails, and any breaking news relevant to my interests.",
  "scheduled_time": "07:30:00",
  "frequency": {
    "type": "daily",
    "minutes": null
  },
  "resources": ["calendar", "email", "firecrawl"],
  "status": "active"
}
```

**Response:**
```json
{
  "order_id": "order-abc123",
  "name": "Morning Brief",
  "prompt": "Summarize today's calendar, important emails...",
  "scheduled_time": "07:30:00",
  "frequency": {
    "type": "daily",
    "minutes": null
  },
  "resources": ["calendar", "email", "firecrawl"],
  "status": "active",
  "next_execution": "2025-01-13T07:30:00Z",
  "created_at": "2025-01-12T16:00:00Z",
  "updated_at": "2025-01-12T16:00:00Z"
}
```

**Frequency Types:**
- `once` - Execute once at scheduled time
- `daily` - Execute daily at scheduled time
- `weekly` - Execute weekly at scheduled time
- `monthly` - Execute monthly at scheduled time
- `custom` - Execute every N minutes (requires `minutes` field, minimum 15)

**Available Resources:**
- `firecrawl` - Web search and scraping
- `github` - GitHub integration
- `apple_news` - Apple News
- `fidelity` - Fidelity portfolio
- `calendar` - Apple Calendar
- `email` - Apple Mail
- `reminder` - Apple Reminders
- `note` - Apple Notes
- `shortcut` - Apple Shortcuts

---

### GET /v1/orders

List all orders.

**Query Parameters:**
- `status`: Filter by status (active, inactive)
- `limit`: Max results (default 20, max 100)
- `offset`: Pagination offset

**Response:**
```json
{
  "orders": [
    {
      "order_id": "order-abc123",
      "name": "Morning Brief",
      "prompt": "Summarize today's calendar...",
      "scheduled_time": "07:30:00",
      "frequency": {"type": "daily"},
      "resources": ["calendar", "email", "firecrawl"],
      "status": "active",
      "next_execution": "2025-01-13T07:30:00Z",
      "last_execution": {
        "execution_id": "exec-xyz789",
        "timestamp": "2025-01-12T07:30:00Z",
        "status": "success"
      },
      "created_at": "2025-01-12T16:00:00Z",
      "updated_at": "2025-01-12T16:00:00Z"
    }
  ],
  "total": 3,
  "limit": 20,
  "offset": 0
}
```

---

### GET /v1/orders/{order_id}

Get details for a specific order.

**Response:**
```json
{
  "order_id": "order-abc123",
  "name": "Morning Brief",
  "prompt": "Summarize today's calendar, important emails, and any breaking news relevant to my interests.",
  "scheduled_time": "07:30:00",
  "frequency": {
    "type": "daily",
    "minutes": null
  },
  "resources": ["calendar", "email", "firecrawl"],
  "status": "active",
  "next_execution": "2025-01-13T07:30:00Z",
  "last_execution": {
    "execution_id": "exec-xyz789",
    "timestamp": "2025-01-12T07:30:00Z",
    "status": "success",
    "hestia_read": null,
    "full_response": "Good morning! Here's your briefing..."
  },
  "execution_count": 42,
  "success_rate": 0.95,
  "created_at": "2025-01-12T16:00:00Z",
  "updated_at": "2025-01-12T16:00:00Z"
}
```

---

### PATCH /v1/orders/{order_id}

Update an existing order.

**Request:**
```json
{
  "name": "Morning Brief v2",
  "prompt": "Updated prompt...",
  "scheduled_time": "08:00:00",
  "frequency": {"type": "daily"},
  "resources": ["calendar", "email"],
  "status": "active"
}
```

All fields are optional. Only provided fields are updated.

**Response:**
```json
{
  "order_id": "order-abc123",
  "name": "Morning Brief v2",
  "prompt": "Updated prompt...",
  "scheduled_time": "08:00:00",
  "frequency": {"type": "daily"},
  "resources": ["calendar", "email"],
  "status": "active",
  "next_execution": "2025-01-13T08:00:00Z",
  "updated_at": "2025-01-12T17:00:00Z"
}
```

---

### DELETE /v1/orders/{order_id}

Delete an order.

**Response:**
```json
{
  "order_id": "order-abc123",
  "deleted": true,
  "message": "Order deleted successfully"
}
```

---

### GET /v1/orders/{order_id}/executions

Get execution history for an order.

**Query Parameters:**
- `status`: Filter by status (success, failed, running, scheduled)
- `since`: ISO timestamp for oldest execution to include
- `limit`: Max results (default 20, max 100)
- `offset`: Pagination offset

**Response:**
```json
{
  "order_id": "order-abc123",
  "executions": [
    {
      "execution_id": "exec-xyz789",
      "timestamp": "2025-01-12T07:30:00Z",
      "status": "success",
      "hestia_read": null,
      "full_response": "Good morning! Here's your briefing for today...",
      "duration_ms": 4500,
      "resources_used": ["calendar", "email", "firecrawl"]
    },
    {
      "execution_id": "exec-xyz788",
      "timestamp": "2025-01-11T07:30:00Z",
      "status": "failed",
      "hestia_read": "Unable to connect to Firecrawl service. The web search could not be completed.",
      "full_response": null,
      "duration_ms": 12000,
      "resources_used": ["calendar", "email"]
    }
  ],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

---

### POST /v1/orders/{order_id}/execute

Manually trigger an order execution.

**Response:**
```json
{
  "order_id": "order-abc123",
  "execution_id": "exec-xyz790",
  "status": "running",
  "message": "Order execution started"
}
```

---

## Agent Profiles API (Phase 6b - COMPLETE)

Agent profiles define personality, instructions, and visual customization for each Hestia mode.

### GET /v1/agents

List all agent profiles.

**Response:**
```json
{
  "agents": [
    {
      "agent_id": "00000000-0000-0000-0000-000000000001",
      "slot_index": 0,
      "name": "Tia",
      "instructions": "You are Tia (short for Hestia), a personal AI assistant...",
      "gradient_color_1": "E0A050",
      "gradient_color_2": "8B3A0F",
      "is_default": true,
      "can_be_deleted": false,
      "photo_url": null,
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-12T16:00:00Z"
    },
    {
      "agent_id": "00000000-0000-0000-0000-000000000002",
      "slot_index": 1,
      "name": "Mira",
      "instructions": "You are Mira (short for Artemis), a learning-focused AI...",
      "gradient_color_1": "090F26",
      "gradient_color_2": "00D7FF",
      "is_default": true,
      "can_be_deleted": true,
      "photo_url": null,
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-12T16:00:00Z"
    }
  ],
  "count": 3
}
```

---

### GET /v1/agents/{slot_index}

Get a specific agent profile by slot index (0, 1, 2).

**Response:**
```json
{
  "agent_id": "00000000-0000-0000-0000-000000000001",
  "slot_index": 0,
  "name": "Tia",
  "instructions": "You are Tia (short for Hestia), a personal AI assistant focused on daily operations and quick queries.\n\nPersonality: Efficient and direct...",
  "gradient_color_1": "E0A050",
  "gradient_color_2": "8B3A0F",
  "is_default": true,
  "can_be_deleted": false,
  "photo_url": null,
  "snapshots": [
    {
      "snapshot_id": "snap-abc123",
      "snapshot_date": "2025-01-10T14:00:00Z",
      "reason": "edited"
    }
  ],
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-12T16:00:00Z"
}
```

---

### PUT /v1/agents/{slot_index}

Update or create an agent profile at a slot index.

**Request:**
```json
{
  "name": "Tia",
  "instructions": "Updated instructions for the agent...",
  "gradient_color_1": "E0A050",
  "gradient_color_2": "8B3A0F"
}
```

Note: Photo upload is handled separately via `/v1/agents/{slot_index}/photo`.

**Response:**
```json
{
  "agent_id": "00000000-0000-0000-0000-000000000001",
  "slot_index": 0,
  "name": "Tia",
  "instructions": "Updated instructions for the agent...",
  "gradient_color_1": "E0A050",
  "gradient_color_2": "8B3A0F",
  "is_default": false,
  "can_be_deleted": false,
  "snapshot_created": true,
  "updated_at": "2025-01-12T17:00:00Z"
}
```

---

### DELETE /v1/agents/{slot_index}

Delete an agent profile (resets to default). Primary agent (slot 0) cannot be deleted.

**Response:**
```json
{
  "slot_index": 1,
  "reset_to_default": true,
  "default_name": "Mira",
  "snapshot_created": true,
  "message": "Agent profile reset to default"
}
```

**Error (slot 0):**
```json
{
  "error": "forbidden",
  "message": "Primary agent cannot be deleted"
}
```

---

### POST /v1/agents/{slot_index}/photo

Upload a custom photo for an agent.

**Request:** Multipart form data with `photo` file field.

```
Content-Type: multipart/form-data
```

**Response:**
```json
{
  "slot_index": 0,
  "photo_url": "/v1/agents/0/photo",
  "message": "Photo uploaded successfully"
}
```

---

### DELETE /v1/agents/{slot_index}/photo

Remove the custom photo for an agent.

**Response:**
```json
{
  "slot_index": 0,
  "photo_url": null,
  "message": "Photo removed"
}
```

---

### GET /v1/agents/{slot_index}/snapshots

List available snapshots for recovery.

**Response:**
```json
{
  "slot_index": 0,
  "snapshots": [
    {
      "snapshot_id": "snap-abc123",
      "snapshot_date": "2025-01-10T14:00:00Z",
      "reason": "edited",
      "name": "Tia",
      "instructions_preview": "You are Tia (short for Hestia)..."
    },
    {
      "snapshot_id": "snap-abc122",
      "snapshot_date": "2025-01-05T10:00:00Z",
      "reason": "edited",
      "name": "Tia",
      "instructions_preview": "Previous version of instructions..."
    }
  ],
  "count": 2,
  "retention_days": 90
}
```

---

### POST /v1/agents/{slot_index}/restore

Restore an agent profile from a snapshot.

**Request:**
```json
{
  "snapshot_id": "snap-abc123"
}
```

**Response:**
```json
{
  "slot_index": 0,
  "restored_from": "snap-abc123",
  "name": "Tia",
  "message": "Agent profile restored successfully"
}
```

---

### POST /v1/agents/sync

Sync all agent profiles from device to server (for multi-device sync).

**Request:**
```json
{
  "agents": [
    {
      "slot_index": 0,
      "name": "Tia",
      "instructions": "...",
      "gradient_color_1": "E0A050",
      "gradient_color_2": "8B3A0F",
      "updated_at": "2025-01-12T16:00:00Z"
    }
  ],
  "device_id": "hestia-iphone",
  "sync_strategy": "latest_wins"
}
```

**Sync Strategies:**
- `latest_wins` - Most recently updated version is kept
- `server_wins` - Server version always wins
- `device_wins` - Device version always wins

**Response:**
```json
{
  "synced_count": 3,
  "conflicts": [],
  "server_agents": [
    {
      "slot_index": 0,
      "name": "Tia",
      "updated_at": "2025-01-12T16:00:00Z"
    }
  ]
}
```

---

## User Settings API (Phase 6b - COMPLETE)

User profile and notification preferences.

### GET /v1/user/profile

Get current user profile.

**Response:**
```json
{
  "user_id": "user-andrew",
  "name": "Andrew",
  "description": "Tech enthusiast and Hestia power user",
  "photo_url": "/v1/user/photo",
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-12T16:00:00Z"
}
```

---

### PATCH /v1/user/profile

Update user profile.

**Request:**
```json
{
  "name": "Andrew L.",
  "description": "Updated description"
}
```

**Response:**
```json
{
  "user_id": "user-andrew",
  "name": "Andrew L.",
  "description": "Updated description",
  "updated_at": "2025-01-12T17:00:00Z"
}
```

---

### GET /v1/user/settings

Get user notification and preference settings.

**Response:**
```json
{
  "push_notifications": {
    "enabled": true,
    "order_executions": true,
    "order_failures": true,
    "proactive_briefings": true,
    "quiet_hours": {
      "enabled": true,
      "start": "22:00",
      "end": "07:00"
    }
  },
  "default_mode": "tia",
  "auto_lock_timeout_minutes": 5
}
```

---

### PATCH /v1/user/settings

Update user settings.

**Request:**
```json
{
  "push_notifications": {
    "enabled": true,
    "order_executions": true,
    "order_failures": true,
    "proactive_briefings": false,
    "quiet_hours": {
      "enabled": true,
      "start": "23:00",
      "end": "06:00"
    }
  },
  "default_mode": "mira",
  "auto_lock_timeout_minutes": 10
}
```

All fields are optional. Only provided fields are updated.

**Response:**
```json
{
  "updated": true,
  "settings": {
    "push_notifications": {
      "enabled": true,
      "order_executions": true,
      "order_failures": true,
      "proactive_briefings": false,
      "quiet_hours": {
        "enabled": true,
        "start": "23:00",
        "end": "06:00"
      }
    },
    "default_mode": "mira",
    "auto_lock_timeout_minutes": 10
  }
}
```

---

### POST /v1/user/push-token

Register APNS push token for notifications.

**Request:**
```json
{
  "push_token": "abcd1234...",
  "device_id": "hestia-iphone",
  "environment": "production"
}
```

**Environment:** `production` or `sandbox` (for TestFlight/development)

**Response:**
```json
{
  "registered": true,
  "device_id": "hestia-iphone",
  "message": "Push token registered"
}
```

---

### DELETE /v1/user/push-token

Unregister push token (disable notifications for this device).

**Response:**
```json
{
  "unregistered": true,
  "message": "Push token removed"
}
```

---

## Future Enhancements (Phase 7+)

- [ ] WebSocket support for streaming responses
- [ ] Rate limiting per device (implemented in Phase 10)
- [ ] Push notifications (APNS) - API designed above
- [ ] Session persistence across server restarts
- [ ] Token refresh endpoint
- [ ] Request logging middleware

---

## Sample cURL Commands

```bash
# Health check
curl http://localhost:8443/v1/health

# Register device
TOKEN=$(curl -s -X POST http://localhost:8443/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"device_name": "test"}' | jq -r '.token')

# Send message
curl -X POST http://localhost:8443/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Hestia-Device-Token: $TOKEN" \
  -d '{"message": "Hello Tia"}' | jq

# Get mode
curl http://localhost:8443/v1/mode \
  -H "X-Hestia-Device-Token: $TOKEN" | jq

# Search memory
curl "http://localhost:8443/v1/memory/search?q=calendar&limit=5" \
  -H "X-Hestia-Device-Token: $TOKEN" | jq

# List tools
curl http://localhost:8443/v1/tools \
  -H "X-Hestia-Device-Token: $TOKEN" | jq
```
