# Implementation Plan: Architecture Efficiency Optimizations

**Date:** 2026-03-15
**Discovery:** `docs/discoveries/architecture-efficiency-2026-03-15.md`
**Estimated Total Effort:** 4-5 sessions
**Sprint Designation:** Sprint 12: Architecture Efficiency

---

## Overview

Five optimizations ordered by implementation sequence. The first two are trivial (same session), the third is the flagship change (2 sessions), the fourth is a follow-up (1 session), and the fifth is research-only.

| # | Optimization | Type | Effort | Impact |
|---|-------------|------|--------|--------|
| O1 | Parallel pre-inference pipeline | Backend refactor | 1 hour | -150-350ms per request |
| O2 | Council bypass heuristic | Backend tweak | 30 min | -80-150ms for short messages |
| O3 | SSE streaming for iOS/macOS chat | Full-stack feature | 2 sessions | Perceived latency 5s -> <500ms TTFB |
| O4 | Client-side ETag caching | Full-stack feature | 1 session | Near-zero load for repeat views |
| O5 | MLX benchmark | Research | 1 session | Data for future hardware decision |

---

## O1: Parallel Pre-Inference Pipeline

**Goal:** Run memory retrieval, user profile loading, and council intent classification concurrently instead of sequentially.

### Current Code (handler.py, lines ~431-534)

```
Step 5.5: memory.build_context()          # 50-200ms
Step 6:   user_config_loader.load()       # 10-30ms
Step 6.5: council.classify_intent()       # 80-150ms
                                 Total: 140-380ms (sequential)
```

### Target Code

```
asyncio.gather(memory, profile, council)   # max(200, 30, 150) = ~200ms
                                  Savings: ~100-200ms per request
```

### Files to Modify

| File | Change |
|------|--------|
| `hestia/orchestration/handler.py` | Refactor `handle()` steps 5-6.5 into `asyncio.gather` |
| `hestia/orchestration/handler.py` | Same refactor in `handle_streaming()` steps 5.5-6.5 |
| `tests/test_handler.py` | Add test for parallel execution (mock timing) |

### Implementation Steps

**Step 1: Extract profile loading into a helper method**

Currently, user profile loading (step 6) is inline code spanning ~40 lines. Extract it to `_load_user_profile_context(request, will_use_cloud)` that returns `(user_profile_context: str, command_system_instructions: str)`.

```python
async def _load_user_profile_context(
    self, request: Request, will_use_cloud: bool
) -> tuple[str, str]:
    """Load user profile and detect command expansion.

    Returns:
        (user_profile_context, command_system_instructions)
    """
    user_profile_context = ""
    command_system_instructions = ""
    try:
        from hestia.user.config_loader import get_user_config_loader
        from hestia.user.config_models import TOPIC_KEYWORDS, UserConfigFile
        user_loader = await get_user_config_loader()
        user_config = await user_loader.load()
        # ... existing logic ...
    except Exception as e:
        self.logger.warning(...)
    return user_profile_context, command_system_instructions
```

**Step 2: Wrap independent operations in asyncio.gather**

Replace the sequential steps 5.5-6.5 in `handle()`:

```python
# Step 5.5-6.5: Parallel pre-inference pipeline
memory = await self._get_memory_manager()
council = self._get_council_manager()

memory_coro = memory.build_context(
    query=request.content, max_tokens=4000,
    include_recent=True, cloud_safe=will_use_cloud,
)
profile_coro = self._load_user_profile_context(request, will_use_cloud)
intent_coro = council.classify_intent(request.content)

results = await asyncio.gather(
    memory_coro, profile_coro, intent_coro,
    return_exceptions=True,
)

# Unpack with error resilience
memory_context = results[0] if not isinstance(results[0], Exception) else ""
if isinstance(results[0], Exception):
    self.logger.warning(
        f"Memory retrieval failed: {type(results[0]).__name__}",
        component=LogComponent.ORCHESTRATION,
    )

profile_result = results[1] if not isinstance(results[1], Exception) else ("", "")
if isinstance(results[1], Exception):
    self.logger.warning(
        f"Profile loading failed: {type(results[1]).__name__}",
        component=LogComponent.ORCHESTRATION,
    )
user_profile_context, command_system_instructions = (
    profile_result if not isinstance(profile_result, Exception) else ("", "")
)

intent = results[2] if not isinstance(results[2], Exception) else None
if isinstance(results[2], Exception):
    self.logger.warning(
        f"Council intent failed: {type(results[2]).__name__}",
        component=LogComponent.ORCHESTRATION,
    )
elif intent is not None:
    task.context["intent"] = {
        "type": intent.primary_intent.value,
        "confidence": intent.confidence,
    }
```

**Step 3: Apply same pattern to handle_streaming()**

The streaming handler has identical sequential code at lines ~700-826. Apply the same `asyncio.gather` pattern. Note: streaming yields status events between steps. The parallel version should yield a single combined status event:

```python
yield {"type": "status", "stage": "preparing", "detail": "Loading memory, profile, and classifying intent"}
```

**Step 4: Add timing telemetry**

Log the parallel duration vs what sequential would have been:

```python
parallel_start = time.perf_counter()
results = await asyncio.gather(...)
parallel_ms = (time.perf_counter() - parallel_start) * 1000
self.logger.info(
    f"Parallel pre-inference complete in {parallel_ms:.0f}ms",
    component=LogComponent.ORCHESTRATION,
    data={"request_id": request.id, "parallel_ms": parallel_ms},
)
```

### Edge Cases

- **Command expansion mutates `request.content`**: The `/command` expansion in profile loading modifies `request.content`. This must happen BEFORE prompt building but AFTER the gather. Solution: `_load_user_profile_context` returns the expanded content as a third tuple element; the caller applies it after gather completes.
- **`will_use_cloud` depends on inference client state**: This is already computed before the gather, so no issue.
- **Memory manager lazy init**: `_get_memory_manager()` is async but idempotent (singleton). Call it before the gather to ensure it is initialized.

### Test Strategy

- Unit test: mock `memory.build_context`, `user_config_loader.load`, and `council.classify_intent` with sleep delays. Verify total wall time is less than sum of individual delays.
- Existing `test_handler.py` tests must still pass (behavior unchanged, only timing).

### Rollback

Revert to sequential execution. No data model changes, no API changes.

---

## O2: Council Bypass Heuristic

**Goal:** Skip the SLM intent classification call for trivially simple messages that will always classify as CHAT.

### Files to Modify

| File | Change |
|------|--------|
| `hestia/council/manager.py` | Add fast-path check at top of `classify_intent()` |
| `hestia/orchestration/handler.py` | Extract tool-trigger keywords to module constant |
| `tests/test_council.py` | Add tests for bypass conditions |

### Implementation Steps

**Step 1: Define tool trigger keywords**

In `handler.py`, the `TOOL_INSTRUCTIONS` constant already lists tool names. Extract a minimal keyword set:

```python
# hestia/council/manager.py (or a shared constants module)
TOOL_TRIGGER_KEYWORDS = frozenset({
    "note", "notes", "calendar", "schedule", "event", "reminder",
    "email", "mail", "health", "sleep", "steps", "heart",
    "file", "read", "write", "search", "list", "create",
    "investigate", "url", "compare", "command", "run",
    "briefing", "today", "tomorrow", "week",
})
```

**Step 2: Add fast-path in classify_intent()**

At the top of `CouncilManager.classify_intent()`, before the SLM call:

```python
async def classify_intent(
    self,
    user_message: str,
    context: Optional[str] = None,
) -> IntentClassification:
    # Existing disabled check...

    # Fast-path: skip SLM for trivially simple messages
    words = user_message.split()
    if (
        len(words) < 8
        and not any(kw in user_message.lower() for kw in TOOL_TRIGGER_KEYWORDS)
        and not user_message.strip().startswith("/")
    ):
        self.logger.debug(
            "Council fast-path: short non-tool message",
            component=LogComponent.COUNCIL,
        )
        return IntentClassification.create(
            primary_intent=IntentType.CHAT,
            confidence=0.9,
            reasoning="fast-path: short message without tool keywords",
        )

    # Existing SLM/cloud classification logic...
```

**Step 3: Add bypass metrics**

Track how often the fast-path fires for observability:

```python
# In council manager __init__
self._fast_path_count = 0
self._slm_count = 0

# In fast-path
self._fast_path_count += 1

# In SLM path
self._slm_count += 1
```

### Edge Cases

- **"hey what's on my calendar"** — 6 words, contains "calendar" -> not bypassed (correct)
- **"hello"** — 1 word, no tool keywords -> bypassed as CHAT (correct)
- **"what do you think about quantum computing?"** — 7 words, no tool keywords -> bypassed (correct, this is pure CHAT)
- **"explain how the memory system works step by step"** — 9 words -> NOT bypassed (over threshold, SLM classifies)
- **"/briefing"** — starts with "/" -> NOT bypassed (command expansion needs intent)

### Test Strategy

- Unit test: verify bypass triggers for short messages, does not trigger for tool-keyword messages
- Unit test: verify bypass returns IntentType.CHAT with 0.9 confidence
- Integration: verify existing handler tests still pass (council result is the same for CHAT messages)

### Rollback

Remove the fast-path block. No data model changes.

---

## O3: SSE Streaming for iOS/macOS Chat

**Goal:** Stream chat response tokens to iOS and macOS clients in real time via Server-Sent Events, eliminating the 3-8 second blank-screen wait.

This is the flagship optimization. It spans backend (new endpoint), iOS (new streaming path in ChatViewModel), and macOS (same in MacChatViewModel).

### Architecture Decision

**SSE over WebSocket because:**
- iOS `URLSession` supports `bytes(for:)` natively — no library needed
- Chat is request-response (client sends message, server streams back) — not bidirectional
- SSE works through existing HTTP middleware (auth, rate limiting, security headers)
- The CLI already uses WebSocket for its unique bidirectional tool-approval flow — that stays
- SSE over POST is well-supported by FastAPI via `StreamingResponse`

**Protocol:**
```
POST /v1/chat/stream
Content-Type: application/json
Accept: text/event-stream
X-Hestia-Device-Token: <token>

Body: { "message": "...", "session_id": "...", "force_local": false }

Response: text/event-stream
event: status
data: {"stage": "memory", "detail": "Retrieving context"}

event: token
data: {"content": "Hello", "request_id": "req-abc123"}

event: token
data: {"content": " there", "request_id": "req-abc123"}

event: tool_call
data: {"tool_name": "get_today_events", "arguments": {...}, "result": "..."}

event: done
data: {"request_id": "req-abc123", "metrics": {...}, "mode": "tia", "session_id": "..."}

event: error
data: {"code": "internal_error", "message": "An error occurred."}
```

### Phase 3A: Backend SSE Endpoint (Session 1, ~2 hours)

#### Files to Create/Modify

| File | Change |
|------|--------|
| `hestia/api/routes/chat.py` | Add `POST /v1/chat/stream` SSE endpoint |
| `hestia/api/schemas/__init__.py` | Add `ChatStreamRequest` schema (same as `ChatRequest`) |
| `tests/test_chat_routes.py` | Add SSE endpoint tests |

#### Implementation

**New SSE endpoint in chat.py:**

```python
from fastapi.responses import StreamingResponse

@router.post(
    "/stream",
    summary="Send a message with streaming response",
    description="Send a message and receive SSE token stream.",
)
async def send_message_stream(
    request: ChatRequest,
    device_id: str = Depends(get_device_token),
) -> StreamingResponse:
    """SSE streaming chat endpoint for iOS/macOS clients."""
    request_id = f"req-{uuid4().hex[:12]}"
    session_id = request.session_id or f"sess-{uuid4().hex[:12]}"

    logger.info(
        "Chat stream request received",
        component=LogComponent.API,
        data={"request_id": request_id, "device_id": device_id},
    )

    async def event_generator():
        try:
            handler = await get_request_handler()
            internal_request = Request.create(
                content=request.message,
                source=RequestSource.API,
                session_id=session_id,
                device_id=request.device_id or device_id,
            )
            internal_request.id = request_id
            internal_request.force_local = request.force_local
            if request.context_hints:
                internal_request.context_hints = request.context_hints

            # Reuse existing handle_streaming()
            async for event in handler.handle_streaming(internal_request):
                event_type = event.get("type", "status")
                # Map internal event types to SSE event names
                yield f"event: {event_type}\ndata: {json.dumps(event)}\n\n"

        except Exception as e:
            logger.error(
                f"SSE stream error: {type(e).__name__}",
                component=LogComponent.API,
                data={"request_id": request_id},
            )
            error_event = {"type": "error", "code": "internal_error",
                          "message": "An error occurred."}
            yield f"event: error\ndata: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Request-ID": request_id,
            "X-Accel-Buffering": "no",  # Disable nginx buffering if proxied
        },
    )
```

**Key decisions:**
- Reuses `handler.handle_streaming()` directly — same pipeline as CLI WebSocket, zero duplication
- Auth via standard `X-Hestia-Device-Token` header (no protocol upgrade)
- `X-Accel-Buffering: no` prevents reverse proxies from buffering the stream
- Outcome tracking (Learning Cycle) fires within `handle_streaming` already

**Outcome tracking addition:**

The existing REST `send_message` does outcome tracking before and after the response. The SSE endpoint needs this too. Add to the `event_generator` closure:

```python
# Before streaming: detect implicit signal (same as REST)
try:
    outcome_mgr = await get_outcome_manager()
    await outcome_mgr.detect_implicit_signal(
        session_id=session_id, user_id=device_id,
        new_message_content=request.message,
    )
except Exception:
    pass

# After streaming: track response (triggered by "done" event)
```

The "done" event from `handle_streaming` contains metrics. Capture it to fire `outcome_mgr.track_response()` before yielding the final event.

#### Tests

- Test SSE endpoint returns `text/event-stream` content type
- Test auth requirement (401 without token)
- Test event format (proper SSE framing with `event:` and `data:` lines)
- Test error handling (mock handler failure -> error event)

### Phase 3B: iOS Streaming Integration (Session 2, ~3 hours)

#### Files to Create/Modify

| File | Change |
|------|--------|
| `HestiaApp/Shared/Services/APIClient.swift` | Add `sendMessageStream()` method |
| `HestiaApp/Shared/Services/Protocols/HestiaClientProtocol.swift` | Add streaming protocol method |
| `HestiaApp/Shared/ViewModels/ChatViewModel.swift` | Replace `sendMessage` with streaming path |
| `HestiaApp/Shared/Services/MockHestiaClient.swift` | Add mock streaming implementation |

#### APIClient Streaming Method

```swift
// In APIClient.swift

/// Send a message and receive an SSE token stream
/// Returns an AsyncThrowingStream of ChatStreamEvent
func sendMessageStream(
    _ message: String,
    sessionId: String?,
    forceLocal: Bool = false
) -> AsyncThrowingStream<ChatStreamEvent, Error> {
    AsyncThrowingStream { continuation in
        Task {
            do {
                let body = HestiaRequest(
                    message: message, sessionId: sessionId,
                    deviceId: nil, forceLocal: forceLocal, contextHints: nil
                )

                var request = URLRequest(url: URL(string: "\(baseURL)/chat/stream")!)
                request.httpMethod = "POST"
                request.httpBody = try encoder.encode(body)
                request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
                addHeaders(to: &request)

                let (bytes, response) = try await session.bytes(for: request)

                guard let httpResponse = response as? HTTPURLResponse,
                      httpResponse.statusCode == 200 else {
                    continuation.finish(throwing: HestiaError.serverError(
                        statusCode: (response as? HTTPURLResponse)?.statusCode ?? 0,
                        message: "Stream request failed"
                    ))
                    return
                }

                // Parse SSE stream
                var currentEvent = ""
                var currentData = ""

                for try await line in bytes.lines {
                    if line.hasPrefix("event: ") {
                        currentEvent = String(line.dropFirst(7))
                    } else if line.hasPrefix("data: ") {
                        currentData = String(line.dropFirst(6))
                    } else if line.isEmpty {
                        // Empty line = end of event
                        if !currentData.isEmpty {
                            if let event = parseChatStreamEvent(
                                type: currentEvent, data: currentData
                            ) {
                                continuation.yield(event)
                                if case .done = event {
                                    continuation.finish()
                                    return
                                }
                                if case .error = event {
                                    continuation.finish()
                                    return
                                }
                            }
                        }
                        currentEvent = ""
                        currentData = ""
                    }
                }

                continuation.finish()
            } catch {
                continuation.finish(throwing: error)
            }
        }
    }
}
```

#### ChatStreamEvent Model

```swift
// In APIModels.swift or a new ChatStreamModels.swift

enum ChatStreamEvent {
    case status(stage: String, detail: String)
    case token(content: String, requestId: String)
    case toolCall(toolName: String, arguments: [String: AnyCodableValue]?, result: String?)
    case done(requestId: String, metrics: ResponseMetrics?, mode: String, sessionId: String?)
    case error(code: String, message: String)
    case insight(content: String, key: String)
}
```

#### ChatViewModel Streaming Path

Replace the blocking `sendMessage` flow with streaming:

```swift
func sendMessage(_ text: String, appState: AppState) async {
    // ... existing validation, mode detection, user message append ...

    isLoading = true

    do {
        let wasForceLocal = forceLocal
        forceLocal = false

        // Create a placeholder assistant message for streaming
        let assistantMessage = ConversationMessage(
            id: UUID().uuidString,
            role: .assistant,
            content: "",
            timestamp: Date(),
            mode: appState.currentMode
        )
        messages.append(assistantMessage)
        let messageIndex = messages.count - 1

        isTyping = true
        currentTypingText = ""

        // Stream tokens
        let stream = client.sendMessageStream(
            text, sessionId: sessionId, forceLocal: wasForceLocal
        )

        for try await event in stream {
            switch event {
            case .token(let content, _):
                // Append token to the live message
                currentTypingText = (currentTypingText ?? "") + content
                messages[messageIndex].content += content

            case .status(_, let detail):
                // Optional: show status in a subtle indicator
                #if DEBUG
                print("[Stream] \(detail)")
                #endif

            case .done(_, let metrics, let mode, let returnedSessionId):
                // Finalize
                if sessionId == nil, let sid = returnedSessionId {
                    sessionId = sid
                }
                if let newMode = HestiaMode(rawValue: mode) {
                    if newMode != appState.currentMode {
                        appState.switchMode(to: newMode)
                    }
                }
                isTyping = false
                currentTypingText = nil

            case .toolCall(let toolName, _, let result):
                // Append tool result to message
                if let result = result {
                    messages[messageIndex].content += result
                    currentTypingText = (currentTypingText ?? "") + result
                }

            case .error(_, let message):
                throw HestiaError.serverError(statusCode: 0, message: message)

            case .insight(_, _):
                break // Optional future use
            }
        }

    } catch let error as HestiaError {
        handleError(error)
    } catch {
        handleError(.unknown(error.localizedDescription))
    }

    isLoading = false
    isTyping = false
    currentTypingText = nil
}
```

**Key design decisions:**
- The typewriter effect (`displayResponseWithTypewriter`) is **removed** — real streaming replaces fake typewriter. Tokens arrive at LLM generation speed (~15-25 tok/s), which is a natural reading pace.
- A placeholder assistant message is added to `messages` immediately and updated in-place as tokens arrive. This means the message bubble appears instantly with content growing.
- `isTyping` is set true during streaming (drives the typing indicator in the UI).
- The existing REST `sendMessage` in `HestiaClientProtocol` is kept for fallback/compatibility — the streaming path is the new default.

#### macOS: MacChatViewModel Changes

The macOS `MacChatViewModel` follows the same pattern as the iOS one. It currently calls `client.sendMessage()` the same way. Apply the identical streaming logic. Both ViewModels share `HestiaClientProtocol`, so the `sendMessageStream` method is available to both.

#### Protocol Update

```swift
// HestiaClientProtocol.swift
protocol HestiaClientProtocol {
    // Existing
    func sendMessage(_ message: String, sessionId: String?, forceLocal: Bool) async throws -> HestiaResponse

    // New: streaming
    func sendMessageStream(_ message: String, sessionId: String?, forceLocal: Bool) -> AsyncThrowingStream<ChatStreamEvent, Error>

    // ... rest unchanged ...
}
```

#### MockHestiaClient Update

```swift
func sendMessageStream(_ message: String, sessionId: String?, forceLocal: Bool) -> AsyncThrowingStream<ChatStreamEvent, Error> {
    AsyncThrowingStream { continuation in
        Task {
            // Simulate streaming with fake tokens
            let words = "This is a mock streaming response for your message.".split(separator: " ")
            for word in words {
                try? await Task.sleep(nanoseconds: 50_000_000) // 50ms per word
                continuation.yield(.token(content: String(word) + " ", requestId: "mock-req"))
            }
            continuation.yield(.done(requestId: "mock-req", metrics: nil, mode: "tia", sessionId: sessionId))
            continuation.finish()
        }
    }
}
```

#### Certificate Pinning Compatibility

The `URLSession.bytes(for:)` method uses the same `URLSession` instance configured with the `CertificatePinningDelegate`. Verify in testing that the streaming response works with the self-signed cert. If `bytes` doesn't trigger the delegate properly, fall back to `URLSession.dataTask` with manual stream parsing.

#### Fallback Strategy

If SSE streaming fails (network error, server doesn't support it), fall back to the existing REST endpoint:

```swift
func sendMessage(_ text: String, appState: AppState) async {
    // Try streaming first
    do {
        try await sendMessageStreaming(text, appState: appState)
        return
    } catch {
        #if DEBUG
        print("[ChatVM] Streaming failed, falling back to REST: \(error)")
        #endif
    }

    // Fallback to REST
    await sendMessageREST(text, appState: appState)
}
```

### Tests for O3

| Test | Location | What |
|------|----------|------|
| SSE endpoint responds with event-stream | `tests/test_chat_routes.py` | HTTP content type, auth |
| SSE events are properly framed | `tests/test_chat_routes.py` | `event:` + `data:` + blank line |
| Token events contain content | `tests/test_chat_routes.py` | Mock handler yields tokens |
| Done event contains metrics | `tests/test_chat_routes.py` | Duration, token counts |
| Error events on handler failure | `tests/test_chat_routes.py` | Mock exception -> error SSE |
| iOS builds clean | `xcodebuild` | Both schemes compile |

---

## O4: Client-Side ETag Caching

**Goal:** Add ETag headers to read-heavy endpoints so iOS/macOS clients can skip redundant data transfers.

### Target Endpoints

| Endpoint | Staleness | ETag Source |
|----------|-----------|-------------|
| `GET /v1/wiki/articles` | Hours-days | Hash of article list (IDs + updated_at) |
| `GET /v1/wiki/articles/{id}` | Hours-days | Article content hash |
| `GET /v1/tools` | Until deploy | Hash of tool registry |
| `GET /v1/tools/{name}` | Until deploy | Hash of tool schema |
| `GET /v1/user/profile` | Minutes-hours | Hash of profile data |
| `GET /v1/agents` | Until user edit | Hash of agent configs |
| `GET /v1/health_data/summary` | Hours | Hash of day's data |

### Files to Modify

| File | Change |
|------|--------|
| `hestia/api/middleware/etag.py` | **New file**: ETag middleware |
| `hestia/api/server.py` | Register ETag middleware |
| `hestia/api/routes/wiki.py` | Add ETag to list/detail responses |
| `hestia/api/routes/tools.py` | Add ETag to list/detail responses |
| `HestiaApp/Shared/Services/APIClient.swift` | Add conditional GET with `If-None-Match` |

### Backend Implementation

**Option A: Per-route ETag (simpler, more control)**

Add a utility function and use it in individual routes:

```python
# hestia/api/utils.py
import hashlib
from fastapi import Request, Response

def add_etag(response: Response, data: str) -> str:
    """Compute and set ETag header. Returns the ETag value."""
    etag = hashlib.md5(data.encode()).hexdigest()[:16]
    response.headers["ETag"] = f'"{etag}"'
    return etag

def check_etag(request: Request, etag: str) -> bool:
    """Check If-None-Match header against computed ETag."""
    if_none_match = request.headers.get("if-none-match", "")
    return if_none_match.strip('"') == etag
```

Usage in wiki routes:

```python
@router.get("/articles", response_model=WikiArticleListResponse)
async def list_articles(
    request: Request,
    response: Response,
    device_id: str = Depends(get_device_token),
    ...
):
    articles = await wiki_mgr.list_articles(...)

    # Compute ETag from article metadata
    etag_source = "|".join(f"{a.id}:{a.generated_at}" for a in articles)
    etag = add_etag(response, etag_source)

    if check_etag(request, etag):
        return Response(status_code=304)

    return WikiArticleListResponse(articles=articles, count=len(articles))
```

**Option B: Middleware-based ETag (global, less control)**

Not recommended — response body hashing in middleware is expensive and defeats the purpose. Per-route is better because we can hash metadata (fast) instead of full response bodies.

### iOS Implementation

Add conditional GET support to `APIClient`:

```swift
// In APIClient.swift

/// In-memory ETag cache: [URL path: ETag value]
private var etagCache: [String: (etag: String, data: Data)] = [:]

func get<T: Decodable>(_ path: String, useETag: Bool = false) async throws -> T {
    var request = URLRequest(url: URL(string: "\(baseURL)\(path)")!)
    request.httpMethod = "GET"
    addHeaders(to: &request)

    // Add If-None-Match if we have a cached ETag
    if useETag, let cached = etagCache[path] {
        request.setValue("\"\(cached.etag)\"", forHTTPHeaderField: "If-None-Match")
    }

    let (data, response) = try await session.data(for: request)
    let httpResponse = response as! HTTPURLResponse

    if httpResponse.statusCode == 304, let cached = etagCache[path] {
        // Serve from cache
        return try decoder.decode(T.self, from: cached.data)
    }

    // Store new ETag
    if useETag, let etag = httpResponse.value(forHTTPHeaderField: "ETag") {
        etagCache[path] = (etag: etag.trimmingCharacters(in: CharacterSet(charactersIn: "\"")), data: data)
    }

    return try decoder.decode(T.self, from: data)
}
```

ViewModels that fetch wiki articles, tools, etc. would pass `useETag: true`:

```swift
// In MacWikiViewModel
let articles: WikiArticleListResponse = try await APIClient.shared.get("/wiki/articles", useETag: true)
```

### Memory Considerations

The ETag cache stores response data in memory. For the target endpoints:
- Wiki article list: ~10-50KB
- Tool schemas: ~5-10KB
- User profile: ~2-5KB

Total: <100KB — negligible on any device. Could add LRU eviction at 50 entries if needed.

### Tests

- Test ETag header is present on target endpoints
- Test `If-None-Match` with matching ETag returns 304
- Test `If-None-Match` with stale ETag returns 200 with new ETag
- Test iOS ETag cache stores and retrieves correctly

---

## O5: MLX Benchmark (Research Only)

**Goal:** Establish baseline performance numbers for Ollama vs MLX on M1 16GB to inform future hardware/framework decisions. No code changes to Hestia.

### Benchmark Plan

| Test | Ollama (current) | MLX (test) |
|------|-----------------|------------|
| Model | qwen3.5:9b Q4_K_M | qwen3.5:9b MLX 4-bit |
| Prompt | Standardized 500-token input | Same |
| Metric | Tokens/sec generation | Same |
| Metric | Time to first token (TTFT) | Same |
| Metric | Memory usage (RSS) | Same |
| Metric | Model load time (cold start) | Same |
| Iterations | 10 runs, discard first (warm-up) | Same |

### Steps

1. Install `mlx-lm` in a separate virtualenv (not Hestia's .venv)
2. Convert Qwen 3.5 9B to MLX format: `mlx_lm.convert --hf-path Qwen/Qwen3.5-9B-Instruct --mlx-path ./qwen35-9b-mlx -q`
3. Run benchmark with standardized prompts
4. Record results in `docs/discoveries/mlx-benchmark-results-YYYY-MM-DD.md`
5. Make go/no-go recommendation for MLX migration

### Decision Criteria

| Metric | Adopt MLX If... | Stay with Ollama If... |
|--------|----------------|----------------------|
| tok/s | >1.5x improvement | <1.3x improvement |
| TTFT | <500ms | >1s or equivalent |
| Memory | Same or less | Significantly more |
| Stability | No crashes in 10 runs | Any crash |

### No Hestia Code Changes

This is a standalone benchmark. If the results justify MLX migration, that becomes a separate sprint with its own plan (new `InferenceBackend` abstraction in `client.py`).

---

## Sprint Schedule

### Session 1: Quick Wins (O1 + O2)

**Duration:** ~2 hours
**Goal:** Measurable latency reduction with zero risk

| Task | Time | Files |
|------|------|-------|
| O1: Extract `_load_user_profile_context()` | 20 min | `handler.py` |
| O1: Wrap steps 5-6.5 in `asyncio.gather` in `handle()` | 20 min | `handler.py` |
| O1: Same refactor in `handle_streaming()` | 15 min | `handler.py` |
| O1: Add timing telemetry | 5 min | `handler.py` |
| O2: Define `TOOL_TRIGGER_KEYWORDS` | 5 min | `council/manager.py` |
| O2: Add fast-path in `classify_intent()` | 10 min | `council/manager.py` |
| Tests + validation | 30 min | `test_handler.py`, `test_council.py` |
| Full test suite | 15 min | All |

### Session 2: SSE Backend (O3A)

**Duration:** ~3 hours
**Goal:** Working SSE endpoint

| Task | Time | Files |
|------|------|-------|
| Add `POST /v1/chat/stream` endpoint | 45 min | `routes/chat.py` |
| Add outcome tracking to SSE path | 15 min | `routes/chat.py` |
| Wire up json import + StreamingResponse | 10 min | `routes/chat.py` |
| Write SSE endpoint tests | 45 min | `test_chat_routes.py` |
| Manual test with curl | 15 min | — |
| Full test suite | 15 min | All |

### Session 3: iOS/macOS Streaming (O3B)

**Duration:** ~3 hours
**Goal:** Both clients stream chat responses

| Task | Time | Files |
|------|------|-------|
| Add `ChatStreamEvent` model | 15 min | `APIModels.swift` or new file |
| Add `sendMessageStream()` to APIClient | 30 min | `APIClient.swift` |
| Add to protocol + mock | 15 min | `HestiaClientProtocol.swift`, `MockHestiaClient.swift` |
| Update iOS `ChatViewModel.sendMessage()` | 30 min | `ChatViewModel.swift` |
| Update macOS `MacChatViewModel.sendMessage()` | 20 min | `MacChatViewModel.swift` |
| Test cert pinning with streaming | 15 min | Manual |
| Build both targets | 15 min | `xcodebuild` |

### Session 4: ETag Caching (O4)

**Duration:** ~2 hours
**Goal:** Conditional GET for read-heavy endpoints

| Task | Time | Files |
|------|------|-------|
| Add `add_etag()` / `check_etag()` utilities | 15 min | `api/utils.py` (new) |
| Add ETags to wiki routes | 20 min | `routes/wiki.py` |
| Add ETags to tools routes | 15 min | `routes/tools.py` |
| Add ETags to user profile route | 10 min | `routes/user_profile.py` |
| iOS: Add ETag cache to APIClient | 20 min | `APIClient.swift` |
| iOS: Wire `useETag: true` in ViewModels | 15 min | Various ViewModels |
| Tests | 20 min | Backend + build |

### Session 5 (Optional): MLX Benchmark (O5)

**Duration:** ~2 hours
**Goal:** Data-driven MLX decision

| Task | Time |
|------|------|
| Set up MLX virtualenv | 15 min |
| Convert model | 20 min |
| Run benchmark (10 iterations x 2 frameworks) | 45 min |
| Document results | 20 min |

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| `asyncio.gather` exception in one coroutine breaks all | `return_exceptions=True` + per-result error checking |
| Council bypass misclassifies a tool request | Conservative keyword list + word count threshold (8) |
| SSE stream drops mid-response | iOS falls back to REST `sendMessage` |
| URLSession.bytes doesn't work with cert pinning | Test early in Session 3; fallback to dataTask if needed |
| ETag cache grows unbounded on iOS | LRU cap at 50 entries; entries are small (<100KB total) |
| MLX model conversion fails for Qwen 3.5 | This is research-only; no Hestia code depends on it |

---

## Success Metrics

| Metric | Before | After | How to Measure |
|--------|--------|-------|---------------|
| Time to first visible token (iOS) | 3-8s | <500ms | Stopwatch from send to first character |
| Pre-inference pipeline latency | 200-400ms | 100-200ms | Server logs (`parallel_ms`) |
| Council calls for short messages | 100% | ~30% | Council bypass counter logs |
| Wiki view load (repeat visit) | ~200ms | <10ms (304) | Network inspector |
| Tool schema load (repeat visit) | ~100ms | <5ms (304) | Network inspector |

---

## ADR

If approved, this plan warrants **ADR-042: Architecture Efficiency Optimizations** covering:
- SSE as the primary iOS/macOS chat protocol (REST kept as fallback)
- Parallel pre-inference as standard pipeline pattern
- Council bypass heuristic criteria
- ETag caching policy for stable endpoints
