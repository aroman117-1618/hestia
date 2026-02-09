# Hestia API Contract

**Status**: Complete — All Workstreams Implemented
**Last Updated**: 2026-02-15

## Executive Summary

The FastAPI REST API provides HTTP access to all Hestia backend capabilities including chat, memory management, mode switching, cloud LLM routing, voice journaling, proactive intelligence, scheduled orders, agent profiles, user settings, background task management, and health data management.

**Endpoints**: 72 across 15 route modules
**Test Coverage**: 784+ passing tests
**Server**: HTTPS on port 8443 (self-signed cert)
**Documentation**: https://localhost:8443/docs (Swagger UI)

---

## Quick Start

```bash
# Start the server
cd /path/to/hestia
source .venv/bin/activate
python -m hestia.api.server

# Register a device (no auth required)
curl -k -X POST https://localhost:8443/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"device_name": "my-device", "device_type": "cli"}'

# Use the returned token for all subsequent requests
export TOKEN="your-jwt-token"

# Send a message
curl -k -X POST https://localhost:8443/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Hestia-Device-Token: $TOKEN" \
  -d '{"message": "Hello Tia"}'
```

> **Note**: Use `curl -k` to skip self-signed certificate verification, or set `HESTIA_CA_CERT` for proper TLS.

---

## Authentication

All endpoints except `/v1/health`, `/v1/ping`, and `/v1/auth/register` require a JWT device token.

### POST /v1/auth/register

Register a new device and receive a JWT token (no auth required).

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

### POST /v1/auth/refresh

Refresh an existing device token. **Status**: Stub (returns 501).

### Using the Token

Include the token in all authenticated requests:

```
X-Hestia-Device-Token: <your-token>
```

---

## API Endpoints

### Health & Status (2 endpoints)

#### GET /v1/ping

Simple connectivity check (no auth).

**Response:**
```json
{"status": "ok", "message": "pong"}
```

#### GET /v1/health

System health check (no auth). Returns component-level status for inference, memory, state machine, and tools.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-02-15T15:30:00Z",
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
      "registered_tools": 24,
      "tool_names": ["list_calendars", "create_event", "..."]
    }
  }
}
```

---

### Core Chat (1 endpoint)

#### POST /v1/chat

Main conversation endpoint. Processes messages through validation, mode detection, memory retrieval, inference, and memory storage.

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
  "timestamp": "2026-02-15T15:30:00Z",
  "metrics": {
    "tokens_in": 45,
    "tokens_out": 189,
    "duration_ms": 1850
  },
  "tool_calls": null,
  "error": null
}
```

**Response Types:** `text`, `error`, `tool_call`, `clarification`

---

### Mode Management (3 endpoints)

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
    "traits": ["Efficient and direct", "Occasionally sardonic wit"]
  },
  "available": ["tia", "mira", "olly"]
}
```

#### POST /v1/mode/switch

Switch to a different mode. Modes: `tia` (Hestia), `mira` (Artemis), `olly` (Apollo).

**Request:**
```json
{"mode": "mira"}
```

**Response:**
```json
{
  "previous_mode": "tia",
  "current_mode": "mira",
  "persona": { "mode": "mira", "name": "Mira", "full_name": "Artemis", "..." }
}
```

#### GET /v1/mode/{mode_name}

Get details about a specific mode.

---

### Memory Management (4 endpoints)

Implements ADR-002: Governed Memory with human-in-the-loop review.

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
      "tags": { "topics": ["communication"], "entities": [], "mode": "mira" },
      "metadata": { "confidence": 0.85, "has_decision": false },
      "staged_at": "2026-02-15T14:00:00Z"
    }
  ],
  "count": 1
}
```

#### POST /v1/memory/approve/{chunk_id}

Approve a staged memory update for long-term storage.

**Request:**
```json
{"reviewer_notes": "Confirmed preference"}
```

**Response:**
```json
{"chunk_id": "chunk-abc123def", "status": "committed", "scope": "long_term"}
```

#### POST /v1/memory/reject/{chunk_id}

Reject a staged memory update.

**Response:**
```json
{"chunk_id": "chunk-abc123def", "status": "rejected", "scope": null}
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
      "timestamp": "2026-01-09T10:00:00Z",
      "tags": { "topics": ["career", "workplace"], "entities": ["tech startup"] }
    }
  ],
  "count": 1
}
```

---

### Session Management (3 endpoints)

#### POST /v1/sessions

Create a new conversation session.

**Request:**
```json
{"mode": "tia", "device_id": "hestia-iphone"}
```

**Response:**
```json
{"session_id": "sess-xyz789", "mode": "tia", "created_at": "2026-02-15T16:00:00Z"}
```

#### GET /v1/sessions/{session_id}/history

Get conversation history for a session. Reconstructs from in-memory cache or memory chunks.

**Response:**
```json
{
  "session_id": "sess-abc123",
  "mode": "tia",
  "started_at": "2026-02-15T14:00:00Z",
  "last_activity": "2026-02-15T15:30:00Z",
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

### Tools (3 endpoints)

#### GET /v1/tools

List all available tools with definitions.

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
    }
  ],
  "count": 24
}
```

#### GET /v1/tools/categories

List tool categories with counts.

**Response:**
```json
{
  "categories": {
    "calendar": {"count": 4, "tools": ["list_calendars", "list_events", "create_event", "delete_event"]},
    "reminders": {"count": 6, "tools": ["..."]},
    "notes": {"count": 5, "tools": ["..."]},
    "mail": {"count": 5, "tools": ["..."]},
    "file": {"count": 4, "tools": ["read_file", "write_file", "list_directory", "search_files"]}
  },
  "total_tools": 24
}
```

#### GET /v1/tools/{tool_name}

Get details about a specific tool including full parameter definitions.

---

### Background Tasks (6 endpoints)

Per ADR-021/022: Background Task Management with governed auto-persistence.

#### POST /v1/tasks

Submit a background task for async execution.

**Request:**
```json
{"input": "Schedule dentist appointment for next Tuesday", "source": "ios_shortcut"}
```

**Response:**
```json
{
  "task_id": "task-abc123def456",
  "status": "pending",
  "message": "Got it ✓",
  "created_at": "2026-02-15T10:00:00Z"
}
```

#### GET /v1/tasks

List background tasks. **Query**: `status`, `source`, `limit`, `offset`.

#### GET /v1/tasks/{task_id}

Get task details including output, autonomy level, and escalation status.

#### POST /v1/tasks/{task_id}/approve

Approve an escalated task awaiting approval.

**Request:**
```json
{"reviewer_notes": "Approved for sending"}
```

#### POST /v1/tasks/{task_id}/cancel

Cancel a pending task.

#### POST /v1/tasks/{task_id}/retry

Retry a failed task.

---

### Cloud Providers (7 endpoints)

WS1: Cloud LLM Support. Manages cloud LLM providers with 3-state routing (disabled → enabled_smart → enabled_full). API keys stored in macOS Keychain, never returned in responses.

#### GET /v1/cloud/providers

List all configured cloud providers with effective routing state.

**Response:**
```json
{
  "providers": [
    {
      "id": "prov-abc123",
      "provider": "anthropic",
      "state": "enabled_full",
      "active_model_id": "claude-sonnet-4-20250514",
      "available_models": ["claude-sonnet-4-20250514", "claude-haiku-3"],
      "has_api_key": true,
      "health_status": "healthy",
      "last_health_check": "2026-02-15T12:00:00Z",
      "created_at": "2026-01-15T10:00:00Z",
      "updated_at": "2026-02-15T12:00:00Z"
    }
  ],
  "count": 1,
  "cloud_state": "enabled_full"
}
```

#### POST /v1/cloud/providers

Add a cloud provider with API key. Provider field is in the request body.

**Request:**
```json
{
  "provider": "anthropic",
  "api_key": "sk-ant-...",
  "state": "enabled_full",
  "model_id": "claude-sonnet-4-20250514"
}
```

**Response:** `201 Created` with provider details (no API key). Syncs routing state.

**Errors:** `400` (invalid key, <10 chars), `409` (provider already configured).

#### DELETE /v1/cloud/providers/{provider}

Remove a cloud provider and delete its API key from Keychain. Syncs routing state.

**Path params:** `provider` — one of `anthropic`, `openai`, `google`

**Response:**
```json
{
  "provider": "anthropic",
  "deleted": true,
  "message": "Provider 'anthropic' removed and API key deleted."
}
```

#### PATCH /v1/cloud/providers/{provider}/state

Update a provider's routing state. Syncs inference router after mutation.

**Request:**
```json
{"state": "enabled_smart"}
```

**States:** `disabled`, `enabled_smart` (local-first, cloud spillover), `enabled_full` (cloud-first, local fallback)

#### PATCH /v1/cloud/providers/{provider}/model

Select which model to use for a cloud provider.

**Request:**
```json
{"model_id": "claude-sonnet-4-20250514"}
```

#### GET /v1/cloud/usage

Get cloud API usage and cost summary.

**Query params:** `days` (1-365, default 30)

**Response:**
```json
{
  "period_days": 30,
  "total_requests": 150,
  "total_tokens_in": 45000,
  "total_tokens_out": 120000,
  "total_cost_usd": 3.45,
  "by_provider": { "anthropic": { "requests": 150, "tokens_in": 45000, "..." } },
  "by_model": { "claude-sonnet-4-20250514": { "requests": 150, "..." } }
}
```

#### POST /v1/cloud/providers/{provider}/health

Run a health check against a cloud provider's API.

**Response:**
```json
{
  "provider": "anthropic",
  "healthy": true,
  "health_status": "healthy",
  "message": "Provider 'anthropic' is healthy."
}
```

---

### Voice (2 endpoints)

WS2: Voice Journaling. Two-stage pipeline: quality check → journal analysis.

#### POST /v1/voice/quality-check

Analyze a voice transcript for potentially misheard words. LLM flags homophones, misheard proper nouns, and uncommon words.

**Request:**
```json
{
  "transcript": "I need to call John about the meeting tomorrow.",
  "known_entities": ["John Smith", "Project Alpha"]
}
```

**Response:**
```json
{
  "transcript": "I need to call John about the meeting tomorrow.",
  "flagged_words": [
    {
      "word": "call",
      "position": 3,
      "confidence": 0.7,
      "suggestions": ["call", "haul"],
      "reason": "homophone"
    }
  ],
  "overall_confidence": 0.92,
  "needs_review": false
}
```

#### POST /v1/voice/journal-analyze

Full journal analysis: intent extraction, cross-referencing against calendar/mail/memory/reminders, and action plan generation with tool call mappings.

**Request:**
```json
{
  "transcript": "I need to reschedule the dentist and remind me to buy groceries.",
  "mode": "tia"
}
```

**Response:**
```json
{
  "id": "analysis-abc123",
  "transcript": "I need to reschedule the dentist...",
  "intents": [
    {
      "id": "intent-1",
      "intent_type": "action",
      "content": "Reschedule dentist appointment",
      "confidence": 0.95,
      "entities": ["dentist"]
    }
  ],
  "cross_references": [
    {
      "source": "calendar",
      "match": "Dentist - Dr. Smith",
      "relevance": 0.9,
      "details": { "date": "2026-02-20T10:00:00Z" }
    }
  ],
  "action_plan": [
    {
      "id": "action-1",
      "action": "Reschedule dentist appointment",
      "tool_call": "list_events",
      "arguments": { "calendar": "Personal" },
      "confidence": 0.9,
      "intent_id": "intent-1"
    }
  ],
  "summary": "Two actions identified: reschedule dentist, create grocery reminder.",
  "timestamp": "2026-02-15T15:30:00Z"
}
```

---

### Orders (7 endpoints)

Scheduled, recurring prompts that Hestia executes autonomously (standing orders). Uses APScheduler for scheduling.

#### POST /v1/orders

Create a new order.

**Request:**
```json
{
  "name": "Morning Brief",
  "prompt": "Summarize today's calendar and important emails.",
  "scheduled_time": "07:30:00",
  "frequency": { "type": "daily", "minutes": null },
  "resources": ["calendar", "email"],
  "status": "active"
}
```

**Frequency Types:** `once`, `daily`, `weekly`, `monthly`, `custom` (requires `minutes` ≥ 15)

**Resources:** `firecrawl`, `github`, `apple_news`, `fidelity`, `calendar`, `email`, `reminder`, `note`, `shortcut`

**Response:** `201 Created` with order details including `next_execution`.

#### GET /v1/orders

List orders. **Query**: `status` (active/inactive), `limit`, `offset`.

#### GET /v1/orders/{order_id}

Get order details including execution stats (count, success rate) and last execution.

#### PATCH /v1/orders/{order_id}

Update an order. All fields optional.

#### DELETE /v1/orders/{order_id}

Delete an order and unschedule it.

#### GET /v1/orders/{order_id}/executions

Get execution history. **Query**: `status`, `since`, `limit`, `offset`.

**Response:**
```json
{
  "order_id": "order-abc123",
  "executions": [
    {
      "execution_id": "exec-xyz789",
      "timestamp": "2026-02-15T07:30:00Z",
      "status": "success",
      "hestia_read": null,
      "full_response": "Good morning! Here's your briefing...",
      "duration_ms": 4500,
      "resources_used": ["calendar", "email"]
    }
  ],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

#### POST /v1/orders/{order_id}/execute

Manually trigger an order execution.

---

### Agents (10 endpoints)

Agent profiles define personality, instructions, and visual customization for each Hestia mode. 3 slots (0=Tia, 1=Mira, 2=Olly).

#### GET /v1/agents

List all agent profiles.

#### GET /v1/agents/{slot_index}

Get agent profile with recent snapshots. Slot: 0, 1, or 2.

#### PUT /v1/agents/{slot_index}

Update or create an agent profile. Creates a snapshot before overwriting.

**Request:**
```json
{
  "name": "Tia",
  "instructions": "Updated instructions...",
  "gradient_color_1": "E0A050",
  "gradient_color_2": "8B3A0F"
}
```

#### DELETE /v1/agents/{slot_index}

Reset agent to default. Slot 0 returns `403 Forbidden` (primary agent cannot be deleted).

#### POST /v1/agents/{slot_index}/photo

Upload agent photo. Multipart form data, max 5MB, JPEG/PNG/WebP.

#### GET /v1/agents/{slot_index}/photo

Get agent photo. Returns image file with appropriate media type.

#### DELETE /v1/agents/{slot_index}/photo

Remove agent photo.

#### GET /v1/agents/{slot_index}/snapshots

List available snapshots for recovery. 90-day retention.

#### POST /v1/agents/{slot_index}/restore

Restore agent from a snapshot.

**Request:**
```json
{"snapshot_id": "snap-abc123"}
```

#### POST /v1/agents/sync

Sync agent profiles from device to server (multi-device support).

**Request:**
```json
{
  "agents": [
    { "slot_index": 0, "name": "Tia", "instructions": "...", "gradient_color_1": "E0A050", "gradient_color_2": "8B3A0F", "updated_at": "2026-02-15T16:00:00Z" }
  ],
  "device_id": "hestia-iphone",
  "sync_strategy": "latest_wins"
}
```

**Sync Strategies:** `latest_wins`, `server_wins`, `device_wins`

---

### User Settings (9 endpoints)

User profile, notification preferences, photo management, and push token registration.

#### GET /v1/user/profile

Get current user profile.

**Response:**
```json
{
  "user_id": "user-andrew",
  "name": "Andrew",
  "description": "Tech enthusiast and Hestia power user",
  "photo_url": "/v1/user/photo",
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-02-15T16:00:00Z"
}
```

#### PATCH /v1/user/profile

Update user profile. Fields: `name`, `description`.

#### POST /v1/user/photo

Upload profile photo. Multipart form data, max 5MB, JPEG/PNG/WebP.

#### GET /v1/user/photo

Get profile photo. Returns image file with appropriate media type.

#### DELETE /v1/user/photo

Delete profile photo.

#### GET /v1/user/settings

Get notification and preference settings.

**Response:**
```json
{
  "push_notifications": {
    "enabled": true,
    "order_executions": true,
    "order_failures": true,
    "proactive_briefings": true,
    "quiet_hours": { "enabled": true, "start": "22:00", "end": "07:00" }
  },
  "default_mode": "tia",
  "auto_lock_timeout_minutes": 5
}
```

#### PATCH /v1/user/settings

Update user settings. All fields optional.

#### POST /v1/user/push-token

Register APNS push token.

**Request:**
```json
{
  "push_token": "abcd1234...",
  "device_id": "hestia-iphone",
  "environment": "production"
}
```

**Environment:** `production` or `sandbox`

#### DELETE /v1/user/push-token

Unregister push token for this device.

---

### Proactive Intelligence (6 endpoints)

ADR-017: Proactive Intelligence Framework. Daily briefings, behavioral pattern detection, interruption policy management.

#### GET /v1/proactive/briefing

Generate today's daily briefing including calendar, reminders, weather, and suggestions.

**Response:**
```json
{
  "greeting": "Good morning, Andrew!",
  "timestamp": "2026-02-15T07:30:00Z",
  "text": "Here's your morning briefing...",
  "calendar": { "events_today": 3, "next_event": "..." },
  "reminders": { "due_today": 2, "overdue": 0 },
  "tasks": { "pending": 1 },
  "weather": { "temp": 72, "condition": "sunny" },
  "suggestions": ["Review pending memory items"],
  "sections": [{ "title": "Calendar", "items": ["..."] }]
}
```

#### GET /v1/proactive/policy

Get current proactive intelligence settings and status.

**Response:**
```json
{
  "interruption_policy": "proactive",
  "briefing": { "enabled": true, "time": "07:30", "days": [0,1,2,3,4] },
  "quiet_hours": { "enabled": true, "start": "22:00", "end": "07:00" },
  "patterns": { "detection_enabled": true },
  "weather": { "enabled": true, "location": "San Francisco" },
  "next_briefing": "2026-02-16T07:30:00Z",
  "can_interrupt_now": true
}
```

#### POST /v1/proactive/policy

Update proactive intelligence settings.

**Request (all fields optional):**
```json
{
  "interruption_policy": "daily",
  "briefing_enabled": true,
  "briefing_time": "08:00",
  "briefing_days": [0, 1, 2, 3, 4],
  "quiet_hours_enabled": true,
  "quiet_hours_start": "22:00",
  "quiet_hours_end": "07:00",
  "pattern_detection_enabled": true,
  "weather_enabled": true,
  "weather_location": "San Francisco"
}
```

**Interruption Policies:** `never`, `daily` (briefings only), `proactive` (briefings + pattern-triggered)

#### GET /v1/proactive/patterns

List detected behavioral patterns from conversation history.

**Query params:** `valid_only` (bool, default true), `refresh` (bool, default false)

**Response:**
```json
{
  "patterns": [
    {
      "type": "time_based",
      "description": "Frequently checks calendar on Monday mornings",
      "confidence": 0.85,
      "occurrences": 12,
      "last_seen": "2026-02-15T09:00:00Z"
    }
  ],
  "total_count": 5,
  "valid_count": 3,
  "last_analysis": "2026-02-15T07:30:00Z"
}
```

#### GET /v1/proactive/context

Get current interruption context (Focus mode, calendar busy, quiet hours).

**Response:**
```json
{
  "current_time": "2026-02-15T15:30:00Z",
  "day_of_week": 5,
  "is_focus_mode": false,
  "is_busy_calendar": true,
  "is_quiet_hours": false
}
```

#### POST /v1/proactive/analyze

Force re-analysis of conversation history for patterns.

---

### Health Data (7 endpoints)

Health data synced from iOS HealthKit. Manages metric storage, aggregation, coaching preferences, and sync history.

#### POST /v1/health_data/sync

Receive batch health metrics from iOS. Deduplication via UNIQUE constraint.

**Request Body:**
```json
{
  "metrics": [
    {
      "metric_type": "stepCount",
      "value": 8432,
      "unit": "count",
      "start_date": "2026-02-15T00:00:00Z",
      "end_date": "2026-02-15T23:59:59Z",
      "source": "Apple Health"
    }
  ],
  "sync_date": "2026-02-15"
}
```

**Response (200):**
```json
{
  "sync_id": "sync-abc123",
  "metrics_received": 45,
  "metrics_stored": 42,
  "metrics_deduplicated": 3,
  "duration_ms": 23.5
}
```

#### GET /v1/health_data/summary

Get today's aggregated health summary organized by category.

#### GET /v1/health_data/summary/{target_date}

Get health summary for a specific date (YYYY-MM-DD format).

#### GET /v1/health_data/trend/{metric_type}

Get trend data for a specific metric. Query param: `days` (default 7).

**Response (200):**
```json
{
  "metric_type": "stepCount",
  "days": 7,
  "data_points": [{"date": "2026-02-09", "value": 8432, "samples": 1}],
  "trend": "improving",
  "average": 8100,
  "min_value": 6200,
  "max_value": 10500
}
```

#### GET /v1/health_data/coaching

Get coaching preferences (returns defaults if never set).

#### POST /v1/health_data/coaching

Update coaching preferences. All fields optional.

**Request Body:**
```json
{
  "enabled": true,
  "daily_step_goal": 12000,
  "coaching_tone": "encouraging"
}
```

#### GET /v1/health_data/sync/history

Get recent sync history. Query param: `limit` (default 20).

---

## Error Responses

All errors follow this format:

```json
{
  "error": "validation_error",
  "message": "Request content cannot be empty",
  "request_id": "req-xyz789",
  "timestamp": "2026-02-15T15:30:00Z"
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `validation_error` | 400 | Invalid request format |
| `empty_input` | 400 | Request content empty |
| `input_too_long` | 400 | Exceeds 32K character limit |
| `forbidden_pattern` | 400 | Prompt injection detected |
| `invalid_api_key` | 400 | API key malformed (cloud) |
| `unauthorized` | 401 | Invalid or missing device token |
| `forbidden` | 403 | Action not permitted |
| `not_found` | 404 | Resource not found |
| `provider_exists` | 409 | Cloud provider already configured |
| `timeout` | 504 | Inference timed out |
| `internal_error` | 500 | Unexpected server error |
| `model_unavailable` | 503 | No inference model available |
| `not_implemented` | 501 | Endpoint stub (auth/refresh) |

---

## Implementation Details

### Files

```
hestia/api/
├── __init__.py              # Package exports
├── server.py                # FastAPI app, lifecycle, manager init
├── schemas.py               # All Pydantic request/response models
├── errors.py                # sanitize_for_log(), safe_error_detail()
├── middleware/
│   ├── __init__.py
│   └── auth.py              # JWT authentication (90-day expiry)
└── routes/
    ├── __init__.py
    ├── auth.py              # /v1/auth/* (2 endpoints)
    ├── health.py            # /v1/health, /v1/ping (2 endpoints)
    ├── chat.py              # /v1/chat (1 endpoint)
    ├── mode.py              # /v1/mode/* (3 endpoints)
    ├── memory.py            # /v1/memory/* (4 endpoints)
    ├── sessions.py          # /v1/sessions/* (3 endpoints)
    ├── tools.py             # /v1/tools/* (3 endpoints)
    ├── tasks.py             # /v1/tasks/* (6 endpoints)
    ├── cloud.py             # /v1/cloud/* (7 endpoints)
    ├── voice.py             # /v1/voice/* (2 endpoints)
    ├── orders.py            # /v1/orders/* (7 endpoints)
    ├── agents.py            # /v1/agents/* (10 endpoints)
    ├── user.py              # /v1/user/* (9 endpoints)
    └── proactive.py         # /v1/proactive/* (6 endpoints)
```

### Dependencies

- `fastapi>=0.104.0`
- `uvicorn[standard]>=0.24.0`
- `python-jose[cryptography]>=3.3.0`
- `pydantic>=2.0.0`
- `aiosqlite>=0.19.0`
- `chromadb>=0.4.0`
- `apscheduler>=3.10.0`

### Testing

```bash
# Run full test suite (784+ tests)
python -m pytest tests/ -v

# Run API smoke tests (14 standard + 5 opt-in cloud)
./scripts/test-api.sh

# Live cloud tests (requires HESTIA_CLOUD_TEST=1)
HESTIA_CLOUD_TEST=1 ./scripts/test-api.sh
```

---

## Sample cURL Commands

```bash
# Health check (no auth)
curl -k https://localhost:8443/v1/ping

# Register device
TOKEN=$(curl -k -s -X POST https://localhost:8443/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"device_name": "test"}' | jq -r '.token')

# Send message
curl -k -X POST https://localhost:8443/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Hestia-Device-Token: $TOKEN" \
  -d '{"message": "Hello Tia"}' | jq

# Get mode
curl -k https://localhost:8443/v1/mode \
  -H "X-Hestia-Device-Token: $TOKEN" | jq

# Search memory
curl -k "https://localhost:8443/v1/memory/search?q=calendar&limit=5" \
  -H "X-Hestia-Device-Token: $TOKEN" | jq

# List tools
curl -k https://localhost:8443/v1/tools \
  -H "X-Hestia-Device-Token: $TOKEN" | jq

# List cloud providers
curl -k https://localhost:8443/v1/cloud/providers \
  -H "X-Hestia-Device-Token: $TOKEN" | jq

# Get proactive briefing
curl -k https://localhost:8443/v1/proactive/briefing \
  -H "X-Hestia-Device-Token: $TOKEN" | jq

# List orders
curl -k https://localhost:8443/v1/orders \
  -H "X-Hestia-Device-Token: $TOKEN" | jq

# List agent profiles
curl -k https://localhost:8443/v1/agents \
  -H "X-Hestia-Device-Token: $TOKEN" | jq
```
