# Hestia UI Data Models

**Status**: Phase 6b Active
**Last Updated**: 2025-01-12 (Orders, Agent Profiles, Calendar integration)

This document describes the actual data structures that the UI will consume from the backend, based on what exists in the codebase.

---

## Core Conversation Models

### Request (User Input)

```python
# From hestia/orchestration/models.py

@dataclass
class Request:
    id: str                          # "req-abc123def456"
    content: str                     # User's message
    mode: Mode                       # TIA, MIRA, OLLY
    source: RequestSource            # API, CLI, IOS_SHORTCUT, QUICK_CHAT
    session_id: Optional[str]        # "session-abc12345"
    device_id: Optional[str]         # "hestia-iphone"
    timestamp: datetime              # UTC timestamp
    context_hints: Dict[str, Any]    # Additional context
    tool_results: Optional[List[Dict]]  # For tool call continuations
```

**UI Representation:**
```swift
struct HestiaRequest: Codable {
    let id: String
    let content: String
    let mode: String           // "tia", "mira", "olly"
    let source: String         // "api", "cli", "ios_shortcut", "quick_chat"
    let sessionId: String?
    let deviceId: String?
    let timestamp: Date
}
```

---

### Response (Assistant Output)

```python
# From hestia/orchestration/models.py

@dataclass
class Response:
    request_id: str                  # Links to original request
    content: str                     # Assistant's response text
    response_type: ResponseType      # TEXT, ERROR, TOOL_CALL, CLARIFICATION
    mode: Mode                       # Mode used for this response
    timestamp: datetime
    tokens_in: int                   # Input tokens used
    tokens_out: int                  # Output tokens generated
    duration_ms: float               # Total processing time
    tool_calls: Optional[List[Dict]] # If tools were requested
    error_code: Optional[str]        # "validation_error", "timeout", etc.
    error_message: Optional[str]     # Human-readable error
    memory_operations: List[str]     # What memory ops occurred
```

**UI Representation:**
```swift
struct HestiaResponse: Codable {
    let requestId: String
    let content: String
    let responseType: ResponseType   // .text, .error, .toolCall, .clarification
    let mode: String
    let timestamp: Date
    let metrics: ResponseMetrics
    let error: ResponseError?
}

struct ResponseMetrics: Codable {
    let tokensIn: Int
    let tokensOut: Int
    let durationMs: Double
}

struct ResponseError: Codable {
    let code: String
    let message: String
}

enum ResponseType: String, Codable {
    case text
    case error
    case toolCall = "tool_call"
    case clarification
}
```

---

### Conversation Session

```python
# From hestia/orchestration/models.py

@dataclass
class Conversation:
    session_id: str
    mode: Mode                       # Current active mode
    started_at: datetime
    last_activity: datetime
    messages: List[Dict[str, str]]   # [{"role": "user/assistant", "content": "..."}]
    device_id: Optional[str]
    turn_count: int                  # Number of exchanges
```

**UI Representation:**
```swift
struct ConversationSession: Codable {
    let sessionId: String
    let mode: String
    let startedAt: Date
    let lastActivity: Date
    let turnCount: Int
    let deviceId: String?
}

struct ConversationMessage: Codable, Identifiable {
    let id: String                   // Generated from index
    let role: MessageRole
    let content: String
}

enum MessageRole: String, Codable {
    case user
    case assistant
}
```

---

## Mode & Persona Models

### Mode Enum

```python
# From hestia/orchestration/models.py

class Mode(Enum):
    TIA = "tia"     # Default: daily ops, quick queries
    MIRA = "mira"   # Learning: Socratic teaching, research
    OLLY = "olly"   # Projects: focused dev, minimal tangents
```

**UI Representation:**
```swift
enum HestiaMode: String, Codable, CaseIterable {
    case tia
    case mira
    case olly

    var displayName: String {
        switch self {
        case .tia: return "Tia"
        case .mira: return "Mira"
        case .olly: return "Olly"
        }
    }

    var fullName: String {
        switch self {
        case .tia: return "Hestia"
        case .mira: return "Artemis"
        case .olly: return "Apollo"
        }
    }

    var description: String {
        switch self {
        case .tia: return "Daily operations & quick queries"
        case .mira: return "Learning & Socratic teaching"
        case .olly: return "Focused project work"
        }
    }

    var accentColor: Color {
        switch self {
        case .tia: return .blue
        case .mira: return .purple
        case .olly: return .orange
        }
    }
}
```

### PersonaConfig (Server-side)

```python
# From hestia/orchestration/mode.py

@dataclass
class PersonaConfig:
    name: str               # "Tia"
    full_name: str          # "Hestia"
    invoke_pattern: str     # r"@tia\b|@hestia\b"
    description: str        # "Default mode for daily operations..."
    traits: list[str]       # ["Efficient and direct", ...]
    system_prompt: str      # Full system prompt (not exposed to UI)
    temperature: float      # 0.0 for Tia/Olly, 0.3 for Mira
```

**UI Representation (subset):**
```swift
struct PersonaInfo: Codable {
    let mode: String
    let name: String
    let fullName: String
    let description: String
    let traits: [String]
}
```

---

## Memory Models

### ConversationChunk

The core memory unit. Contains conversation snippets with rich metadata.

```python
# From hestia/memory/models.py

@dataclass
class ConversationChunk:
    id: str                          # "chunk-abc123def456"
    session_id: str
    timestamp: datetime
    content: str                     # The actual text
    chunk_type: ChunkType            # CONVERSATION, FACT, PREFERENCE, etc.
    scope: MemoryScope               # SESSION, SHORT_TERM, LONG_TERM
    status: MemoryStatus             # ACTIVE, STAGED, COMMITTED, SUPERSEDED
    tags: ChunkTags                  # Rich metadata
    metadata: ChunkMetadata          # Additional flags
    references: List[str]            # Links to other chunks
    supersedes: Optional[str]        # If this replaces another chunk
    parent_id: Optional[str]         # For threaded conversations
```

**UI Representation:**
```swift
struct MemoryChunk: Codable, Identifiable {
    let id: String
    let sessionId: String
    let timestamp: Date
    let content: String
    let chunkType: ChunkType
    let scope: MemoryScope
    let status: MemoryStatus
    let tags: ChunkTags
    let metadata: ChunkMetadata
}

enum ChunkType: String, Codable {
    case conversation
    case fact
    case preference
    case decision
    case actionItem = "action_item"
    case research
    case system
}

enum MemoryScope: String, Codable {
    case session
    case shortTerm = "short_term"
    case longTerm = "long_term"
}

enum MemoryStatus: String, Codable {
    case active
    case staged           // Awaiting human review
    case committed        // Approved for long-term
    case superseded       // Replaced by newer info
    case archived
}
```

### ChunkTags

Tag-based metadata for multi-dimensional queries.

```python
# From hestia/memory/models.py

@dataclass
class ChunkTags:
    topics: List[str]           # ["security", "encryption"]
    entities: List[str]         # ["Face ID", "Secure Enclave"]
    people: List[str]           # ["andrew"]
    mode: Optional[str]         # "tia", "mira", "olly"
    phase: Optional[str]        # "design", "implementation"
    status: List[str]           # ["active", "unresolved"]
    custom: Dict[str, str]      # User-defined tags
```

**UI Representation:**
```swift
struct ChunkTags: Codable {
    let topics: [String]
    let entities: [String]
    let people: [String]
    let mode: String?
    let phase: String?
    let status: [String]
    let custom: [String: String]
}
```

### ChunkMetadata

Additional flags about content characteristics.

```python
# From hestia/memory/models.py

@dataclass
class ChunkMetadata:
    has_code: bool              # Contains code snippets
    has_decision: bool          # Contains a decision
    has_action_item: bool       # Contains TODO/action
    sentiment: Optional[str]    # "positive", "neutral", "negative"
    confidence: float           # 0.0 - 1.0
    token_count: int
    source: Optional[str]       # "conversation", "import", "background_task"
```

**UI Representation:**
```swift
struct ChunkMetadata: Codable {
    let hasCode: Bool
    let hasDecision: Bool
    let hasActionItem: Bool
    let sentiment: String?
    let confidence: Double
    let tokenCount: Int
    let source: String?
}
```

### MemorySearchResult

Returned from semantic search.

```python
# From hestia/memory/models.py

@dataclass
class MemorySearchResult:
    chunk: ConversationChunk
    relevance_score: float      # 0.0 - 1.0
    match_type: str             # "semantic", "tag", "temporal", "exact"
```

**UI Representation:**
```swift
struct MemorySearchResult: Codable, Identifiable {
    let chunk: MemoryChunk
    let relevanceScore: Double
    let matchType: String

    var id: String { chunk.id }
}
```

---

## Memory Staging (ADR-002)

The governed memory system stages updates for human review before committing to long-term memory.

### StagedMemory (Database Schema)

```sql
-- From hestia/memory/database.py

CREATE TABLE staged_memory (
    id TEXT PRIMARY KEY,
    chunk_id TEXT NOT NULL,
    staged_at TEXT NOT NULL,
    reviewed_at TEXT,
    review_status TEXT,          -- pending, approved, rejected
    reviewer_notes TEXT,
    FOREIGN KEY (chunk_id) REFERENCES memory_chunks(id)
);
```

**UI Representation:**
```swift
struct StagedMemoryUpdate: Codable, Identifiable {
    let id: String
    let chunkId: String
    let stagedAt: Date
    let reviewStatus: ReviewStatus
    let chunk: MemoryChunk       // Joined from memory_chunks
}

enum ReviewStatus: String, Codable {
    case pending
    case approved
    case rejected
}

// For approval action
struct MemoryApprovalRequest: Codable {
    let reviewerNotes: String?
}
```

---

## Tool Execution Models

### Tool Definition

```python
# From hestia/execution/models.py

@dataclass
class Tool:
    name: str                        # "create_event"
    description: str                 # Human-readable for prompts
    parameters: Dict[str, ToolParam]
    handler: Callable                # Not exposed to UI
    requires_approval: bool          # Needs external comm gate
    timeout: float                   # Per-tool timeout
    allowed_paths: Optional[List[str]]
    category: str                    # "calendar", "reminders", etc.
```

**UI Representation:**
```swift
struct ToolDefinition: Codable, Identifiable {
    let name: String
    let description: String
    let category: String
    let requiresApproval: Bool
    let parameters: [String: ToolParameter]

    var id: String { name }
}

struct ToolParameter: Codable {
    let type: String             // "string", "integer", "boolean", etc.
    let description: String
    let required: Bool
    let defaultValue: String?
    let enumValues: [String]?
}
```

### ToolResult

```python
# From hestia/execution/models.py

@dataclass
class ToolResult:
    call_id: str
    tool_name: str
    status: ToolResultStatus     # SUCCESS, ERROR, TIMEOUT, DENIED, NOT_FOUND
    output: Any
    error: Optional[str]
    duration_ms: float
    timestamp: datetime
```

**UI Representation:**
```swift
struct ToolExecutionResult: Codable {
    let callId: String
    let toolName: String
    let status: ToolResultStatus
    let output: AnyCodable?      // JSON-encoded result
    let error: String?
    let durationMs: Double
    let timestamp: Date
}

enum ToolResultStatus: String, Codable {
    case success
    case error
    case timeout
    case denied
    case notFound = "not_found"
}
```

---

## Apple Ecosystem Models

### Calendar Event

```python
# From hestia/apple/models.py (inferred structure)

@dataclass
class Event:
    id: str
    title: str
    calendar: str
    start: datetime
    end: datetime
    location: Optional[str]
    notes: Optional[str]
    is_all_day: bool
```

**UI Representation:**
```swift
struct CalendarEvent: Codable, Identifiable {
    let id: String
    let title: String
    let calendar: String
    let start: Date
    let end: Date
    let location: String?
    let isAllDay: Bool
}
```

### Reminder

```python
@dataclass
class Reminder:
    id: str
    title: str
    list_name: str
    is_completed: bool
    due: Optional[datetime]
    priority: int              # 0=none, 1-4=high, 5=medium, 6-9=low
    notes: Optional[str]
```

**UI Representation:**
```swift
struct ReminderItem: Codable, Identifiable {
    let id: String
    let title: String
    let listName: String
    let isCompleted: Bool
    let due: Date?
    let priority: Int
}
```

### Email (Read-Only)

```python
@dataclass
class Email:
    message_id: str
    subject: str
    sender: str
    sender_email: str
    date: datetime
    snippet: str
    is_read: bool
    is_flagged: bool
```

**UI Representation:**
```swift
struct EmailPreview: Codable, Identifiable {
    let messageId: String
    let subject: String
    let sender: String
    let senderEmail: String
    let date: Date
    let snippet: String
    let isRead: Bool
    let isFlagged: Bool

    var id: String { messageId }
}
```

---

## Health & Status Models

### System Health

```python
# From hestia/orchestration/handler.py health_check()

{
    "status": "healthy",
    "components": {
        "inference": {...},
        "memory": {...},
        "state_machine": {...},
        "tools": {...}
    }
}
```

**UI Representation:**
```swift
struct SystemHealth: Codable {
    let status: HealthStatus
    let timestamp: Date
    let components: HealthComponents
}

enum HealthStatus: String, Codable {
    case healthy
    case degraded
    case unhealthy
}

struct HealthComponents: Codable {
    let inference: InferenceHealth
    let memory: MemoryHealth
    let stateMachine: StateMachineHealth
    let tools: ToolsHealth
}

struct InferenceHealth: Codable {
    let status: HealthStatus
    let ollamaAvailable: Bool
    let primaryModelAvailable: Bool
    let complexModelAvailable: Bool
}

struct MemoryHealth: Codable {
    let status: HealthStatus
    let vectorCount: Int
}

struct StateMachineHealth: Codable {
    let status: HealthStatus
    let activeTasks: Int
}

struct ToolsHealth: Codable {
    let status: HealthStatus
    let registeredTools: Int
    let toolNames: [String]
}
```

---

## Background Task Models

### BackgroundTask

```python
# From hestia/tasks/models.py (per ADR-021)

@dataclass
class BackgroundTask:
    id: str                          # "task-abc123def456"
    status: TaskStatus               # pending, in_progress, completed, failed, awaiting_approval
    source: TaskSource               # quick_chat, ios_shortcut, conversation
    input_summary: str               # User's input (truncated)
    output_summary: Optional[str]    # Result summary
    output_details: Optional[Dict]   # Full result as JSON
    autonomy_level: int              # 2-4
    escalated: bool                  # Required manual approval
    escalation_reason: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
```

**UI Representation:**
```swift
struct BackgroundTask: Codable, Identifiable {
    let id: String
    let status: TaskStatus
    let source: TaskSource
    let inputSummary: String
    let outputSummary: String?
    let outputDetails: AnyCodable?
    let autonomyLevel: Int
    let escalated: Bool
    let escalationReason: String?
    let createdAt: Date
    let completedAt: Date?
}

enum TaskStatus: String, Codable {
    case pending
    case inProgress = "in_progress"
    case completed
    case failed
    case awaitingApproval = "awaiting_approval"
    case cancelled
}

enum TaskSource: String, Codable {
    case quickChat = "quick_chat"
    case iosShortcut = "ios_shortcut"
    case conversation
}
```

---

## Orders System Models (Implemented)

### Order

Scheduled recurring prompts that Hestia executes automatically.

```swift
// From HestiaApp/Shared/Models/Order.swift

struct Order: Codable, Identifiable {
    let id: UUID
    let name: String
    let prompt: String
    let scheduledTime: Date
    let frequency: OrderFrequency
    let resources: Set<MCPResource>
    let orderStatus: OrderStatus
    let lastExecution: OrderExecution?
    let createdAt: Date
    let updatedAt: Date
}

enum OrderFrequency: Codable {
    case once
    case daily
    case weekly
    case monthly
    case custom(minutes: Int)
}

enum OrderStatus: String, Codable {
    case active
    case inactive
}

enum MCPResource: String, Codable, CaseIterable, Identifiable {
    case calendar
    case email
    case reminders
    case notes
    case weather
    case stocks
}
```

### OrderExecution

Records of when orders were executed.

```swift
struct OrderExecution: Codable, Identifiable {
    let id: UUID
    let orderId: UUID
    let timestamp: Date
    let status: ExecutionStatus
    let hestiaRead: String?      // LLM analysis of the result
    let fullResponse: String?    // Raw response data
}

enum ExecutionStatus: String, Codable {
    case scheduled
    case running
    case success
    case failed
}
```

---

## Agent Profile Models (Implemented)

### AgentProfile

User-customizable persona slots (3 slots available).

```swift
// From HestiaApp/Shared/Models/AgentProfile.swift

struct AgentProfile: Codable, Identifiable {
    let id: UUID
    let slotIndex: Int           // 0, 1, or 2
    let name: String             // "Tia", "Mira", "Olly"
    let fullName: String         // "Hestia", "Artemis", "Apollo"
    let traits: [String]         // ["Efficient", "Direct", "Helpful"]
    let photoData: Data?         // Custom profile photo (JPEG)
    let voiceId: String?         // Future: voice synthesis ID
    let colorTheme: String       // Hex color for UI
    let isDefault: Bool          // Reset to default available
    let createdAt: Date
    let updatedAt: Date
}
```

### AgentSnapshot

Allows saving/restoring agent configurations.

```swift
struct AgentSnapshot: Codable, Identifiable {
    let id: UUID
    let agentSlotIndex: Int
    let snapshotName: String
    let profileData: AgentProfile
    let createdAt: Date
}
```

---

## Calendar Models (Implemented)

### CalendarEvent

Events from Apple Calendar via EventKit.

```swift
// From HestiaApp/Shared/Models/CalendarEvent.swift

struct CalendarEvent: Identifiable, Codable {
    let id: String               // EKEvent identifier
    let title: String
    let startDate: Date
    let endDate: Date
    let location: String?
    let notes: String?
    let calendarTitle: String?
    let isAllDay: Bool

    var startsIn: TimeInterval { startDate.timeIntervalSinceNow }
}
```

---

## Core Data Entities (Programmatic)

The app uses programmatic Core Data model definition (no .xcdatamodeld file).

### OrderEntity
```swift
// Attributes: id, name, prompt, scheduledTime, frequencyType,
//             frequencyCustomMinutes, resources (Transformable),
//             orderStatus, createdAt, updatedAt
// Relationships: executions (to-many OrderExecutionEntity)
```

### OrderExecutionEntity
```swift
// Attributes: id, timestamp, status, hestiaRead, fullResponse
// Relationships: order (to-one OrderEntity)
```

### AgentProfileEntity
```swift
// Attributes: id, slotIndex, name, fullName, traits (Transformable),
//             photoData, voiceId, colorTheme, isDefault, createdAt, updatedAt
```

---

## What the UI Will NOT Have Access To

These are internal-only:

1. **System prompts** - Full persona system prompts are not exposed
2. **Raw embeddings** - Vector store embeddings (ChromaDB)
3. **Tool handlers** - Python function references
4. **Credentials** - All Keychain data stays server-side
5. **Inference details** - Token-by-token streaming (not implemented yet)
6. **Internal state machine** - Task lifecycle states are internal
