# Discovery Report: Hestia Architecture Efficiency

**Date:** 2026-03-15
**Confidence:** High
**Decision:** Focus on 5 targeted optimizations (SSE streaming, parallel pre-inference, speculative prefetch, MLX migration path, council bypass) rather than a full architecture overhaul. The Mac Mini hub model is correct for this usage profile.

## Hypothesis

Can Hestia's architecture be fundamentally improved for efficiency, performance, and user experience? Specifically: should inference move to user devices, what are the latency bottlenecks, is the M1 16GB the right hub, what can be precomputed, and which protocol should be used for which interaction type?

---

## Current Request Lifecycle (Bottleneck Map)

Traced from `handler.handle()` in `hestia/orchestration/handler.py`:

| Step | Operation | Est. Latency | Blocking? |
|------|-----------|-------------|-----------|
| 1 | Request validation | <1ms | No |
| 2 | Mode switching + routing decision | <1ms | No |
| 3 | Session TTL check + `get_session_timeout()` (DB read) | ~5ms | Yes |
| 4 | Response cache lookup | <1ms | No |
| 5 | **Memory search** (ChromaDB vector + SQLite filter + decay) | **50-200ms** | **Yes** |
| 5b | Recent memory fetch (`get_recent`) | ~20-50ms | Yes |
| 6 | User profile config loading (8 markdown files) | ~10-30ms | Yes |
| 6b | Prompt building + token counting (tiktoken) | ~5-15ms | Yes |
| 6.5 | **Council intent classification** (SLM `qwen2.5:0.5b`) | **80-150ms** | **Yes** |
| 7 | **LLM inference** (Qwen 3.5 9B via Ollama) | **2000-8000ms** | **Yes, dominant** |
| 7.25 | Council post-inference (Analyzer + Validator) — skipped for CHAT | 0-300ms | Sometimes |
| 7.5 | Tool execution (if tool call detected) | 100-5000ms | Sometimes |
| 8 | Memory storage (ChromaDB + SQLite write) | ~50-100ms | Yes (post-response) |
| 9 | Conversation history update | <1ms | No |

**Total typical latency: 2.5-9 seconds** (dominated by LLM inference at ~80% of wall time).

**Key finding:** Steps 5, 6, and 6.5 are all sequential but independent. They could run in parallel, saving ~150-300ms per request.

---

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Well-structured pipeline with clear separation (validation, memory, prompt, inference, tools). Response cache (1hr TTL) eliminates redundant calls. WebSocket streaming already built for CLI. Parallel manager init at startup. CHAT optimization skips 3 council roles. Hardware adaptation auto-detects and downgrades model. | **Weaknesses:** iOS app uses blocking REST (no streaming) — user sees nothing for 3-8s. Memory search + user profile + council intent are sequential despite being independent. ChromaDB runs in-process (shared GIL with FastAPI). No client-side caching beyond server Cache-Control headers. 120-150s iOS timeouts indicate accepted sluggishness. No request-level telemetry dashboard. |
| **External** | **Opportunities:** MLX framework is 50% faster than Ollama on Apple Silicon. SSE/streaming for iOS would dramatically improve perceived latency. M5 Ultra Mac Studio would allow concurrent model loading (no swap penalty). Client-side embedding on iPhone 15+ (Apple Intelligence MLX runtime). Edge-cloud hybrid split for latency-sensitive vs quality-sensitive tasks. | **Threats:** ChromaDB memory growth — HNSW index must fit in RAM (M1 16GB constraint). Ollama single-model GPU occupancy means council SLM calls force model swap (~1s). Python GIL limits true parallelism for CPU-bound token counting. Growing endpoint count (154) increases surface area for regression. |

---

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | **1. iOS SSE/streaming for chat** (perceived latency drops from 5s to <500ms TTFB). **2. Parallel pre-inference pipeline** (memory + profile + council intent in `asyncio.gather`). | **3. Client-side response caching** (ETags/304 for read-heavy endpoints like wiki, tools). |
| **Low Priority** | **4. MLX migration path** (50% inference speedup, but requires Ollama replacement). **5. Dedicated vector DB process** (eliminates GIL contention with ChromaDB). | Council SLM warm-keeping (model swap avoidance — diminishing returns at ~6hrs/week usage). Hardware upgrade to M5 (overkill for single-user ~6hrs/week). Moving inference to client devices (complexity explosion for marginal gain). |

---

## The 5 Recommendations

### 1. iOS SSE Streaming for Chat (HIGH PRIORITY, HIGH IMPACT)

**Problem:** The iOS app sends a REST POST to `/v1/chat` and blocks for 3-8 seconds with no feedback beyond a typing indicator animation. The CLI already has WebSocket streaming with token-by-token delivery via `handler.handle_streaming()`.

**Solution:** Add an SSE (Server-Sent Events) endpoint — `GET /v1/chat/stream` or `POST /v1/chat` with `Accept: text/event-stream`. SSE is simpler than WebSocket for iOS (native `URLSession` bytes streaming, no library needed), works through HTTP proxies, and requires no connection state management.

**Why SSE over WebSocket for iOS:**
- iOS `URLSession` natively supports streaming response bytes — zero dependencies
- The iOS chat is request-response (not bidirectional like CLI tool approval)
- SSE works through all HTTP middleware (rate limiting, auth, logging) unchanged
- WebSocket would require a separate auth flow (the CLI already handles this complexity)

**Estimated effort:** ~2 sessions (backend SSE endpoint + iOS `ChatViewModel` streaming integration)
**Estimated impact:** Perceived latency drops from 5s to <500ms time-to-first-byte. Users see tokens appear in real-time instead of staring at a loading animation.

### 2. Parallel Pre-Inference Pipeline (HIGH PRIORITY, HIGH IMPACT)

**Problem:** In `handler.handle()`, steps 5-6.5 run sequentially:
```
memory.build_context()  →  user_config_loader.load()  →  council.classify_intent()
```
These are independent operations that could overlap.

**Solution:** Wrap in `asyncio.gather()`:
```python
memory_context, user_profile_result, intent = await asyncio.gather(
    memory.build_context(query=request.content, ...),
    self._load_user_profile(request),
    council.classify_intent(request.content),
    return_exceptions=True,
)
```

**Estimated effort:** ~1 hour (refactor the sequential block in `handle()` and `handle_streaming()`)
**Estimated impact:** Saves 150-350ms per request (memory search + council intent overlap). On a 5s request, that is a 3-7% improvement — modest but free.

### 3. Client-Side Response Caching with ETags (HIGH PRIORITY, LOW IMPACT)

**Problem:** Read-heavy endpoints (wiki articles, tool schemas, health summaries, newsfeed) are fetched fresh every time the iOS/macOS app opens a view. The server already has `Cache-Control` headers for `/v1/ping` (10s), `/v1/tools` (60s), and `/v1/wiki/articles` (30s), but clients don't leverage conditional requests.

**Solution:**
- Backend: Add `ETag` headers to stable endpoints (wiki, tools, agents, user profile)
- iOS/macOS: Implement `If-None-Match` conditional GET — on 304, serve from local cache
- Especially impactful for wiki articles (AI-generated, rarely change) and tool schemas (static until deploy)

**Estimated effort:** ~1 session
**Estimated impact:** Eliminates redundant data transfer for ~40% of non-chat API calls. Reduces perceived load times for settings/wiki/tools views to near-zero on repeat visits.

### 4. MLX Migration Path (LOW PRIORITY, HIGH IMPACT)

**Problem:** Ollama adds a Python-to-Go-to-llama.cpp translation layer. Research shows MLX (Apple's native framework) is **50% faster** than Ollama GGUF on Apple Silicon, with MLX achieving ~230 tok/s vs Ollama's ~20-40 tok/s on comparable models. On M1, the gap is smaller but still meaningful.

**Current Ollama performance on M1 16GB with Qwen 3.5 9B:**
- Estimated ~15-25 tok/s generation (constrained by 16GB unified memory)
- Model swap penalty when switching between primary (9B) and SLM (0.5B): ~1-2s

**MLX potential on M1:**
- Estimated ~30-45 tok/s for equivalent quantized model
- Native Metal integration, no IPC overhead
- MLX `mlx-lm` package is pip-installable, Python-native (no Go service)

**Why LOW priority:** The migration is non-trivial:
- Ollama provides model management, quantization, and a clean API — MLX requires building this yourself
- `mlx-lm` model format differs from GGUF — would need model reconversion
- The inference client (`hestia/inference/client.py`) is tightly coupled to Ollama's HTTP API
- At ~6hrs/week usage, the absolute time saved is small (~30 min/week of cumulative inference time)

**Recommendation:** Wait for either (a) an M5 hardware upgrade (which makes Ollama fast enough) or (b) a stable MLX-compatible Ollama backend (in development). Don't build custom MLX integration for the current hardware.

### 5. Council Bypass for Low-Complexity Messages (LOW PRIORITY, MEDIUM IMPACT)

**Problem:** Every chat message runs council intent classification via the SLM (`qwen2.5:0.5b`), which takes 80-150ms. For simple greetings, short questions, and follow-ups, this classification adds latency without changing behavior (they all classify as CHAT with high confidence).

**Current optimization:** CHAT intent with >0.8 confidence already skips post-inference council roles. But the initial classification itself is never skipped.

**Solution:** Add a fast-path heuristic before the SLM call:
```python
# Skip council for trivially simple messages
if len(request.content.split()) < 8 and not any(kw in request.content.lower() for kw in TOOL_TRIGGER_KEYWORDS):
    intent = IntentClassification.create(primary_intent=IntentType.CHAT, confidence=0.9, reasoning="fast-path: short message")
```

**Estimated effort:** ~30 minutes
**Estimated impact:** Saves 80-150ms for ~60-70% of messages (short conversational exchanges). Combined with recommendation #2, this means most chat messages skip both the SLM call and the council post-inference, saving 200-400ms total.

---

## What NOT To Do

### Don't Move Inference to Client Devices

**The argument for:** iPhone 15 Pro has a Neural Engine capable of running 3B models. iPad M-series can run 7B models. Moving inference to client devices would eliminate network latency entirely.

**Why it's wrong for Hestia:**
1. **Memory is centralized.** ChromaDB + SQLite live on the Mac Mini. If inference runs on iPhone but memory lives on Mac Mini, you still need a network round-trip for context retrieval — you've just moved the bottleneck, not eliminated it.
2. **Model management complexity explodes.** You'd need to ship, update, and cache models on every client device. Ollama handles this on the server today.
3. **Context window is the real value.** Hestia's power is its 32K context with memory + user profile + conversation history + tool definitions. A 3B on-device model can't match a 9B server model with full context.
4. **Single user, single server.** There's no scaling problem to solve. The M1 is not under contention.
5. **Power consumption.** Running a 7B model on iPhone drains battery aggressively. Running it on a plugged-in Mac Mini costs nothing.

**The one exception:** If Apple Intelligence exposes an on-device embedding API, using it for client-side semantic search of cached data (notes, calendar, recent conversations) would be genuinely useful as a pre-filter before hitting the server. But that's an additive optimization, not an architecture shift.

### Don't Replace the Mac Mini Yet

At ~6 hours/week usage, the M1 16GB is underutilized. An M5 Ultra Mac Studio (~$4K-8K) would provide:
- 192GB unified memory (run 70B models, multiple models simultaneously)
- ~4x inference throughput
- Eliminate model swap penalty

But the cost-per-hour-of-use is terrible. Wait until either (a) usage increases significantly (daily driver vs weekly) or (b) an M5 Mac Mini ships at the $600-1000 price point.

### Don't Replace REST with WebSocket for Everything

The iOS app has 154 endpoints. Converting them to WebSocket would be an enormous effort with no benefit for request-response operations (settings, wiki, tools, health). WebSocket is right for the CLI (bidirectional tool approval). SSE is right for iOS chat streaming. REST is right for everything else.

---

## Third-Party Evidence

- [Production-Grade Local LLM Inference on Apple Silicon](https://arxiv.org/abs/2511.05502): MLX achieves ~230 tok/s with 5-7ms P99 latency. Ollama achieves 20-40 tok/s. Both on Apple Silicon.
- [Streaming in 2026: SSE vs WebSockets](https://jetbi.com/blog/streaming-architecture-2026-beyond-websockets): "If your use case is user requests completion, server streams tokens back, SSE is a better default than WebSocket."
- [FastAPI SSE for LLM Streaming](https://medium.com/@2nick2patel2/fastapi-server-sent-events-for-llm-streaming-smooth-tokens-low-latency-1b211c94cff5): Documented pattern for FastAPI + Ollama streaming via SSE.
- [ChromaDB Performance](https://docs.trychroma.com/guides/deploy/performance): HNSW index must fit in RAM. On M1 16GB with ~5GB for OS/apps, practical limit is ~500K-1M embeddings before performance degrades.
- [Edge vs Cloud TCO](https://www.cio.com/article/4109609/edge-vs-cloud-tco-the-strategic-tipping-point-for-ai-inference.html): Hybrid edge-cloud achieves up to 75% energy savings and 80% cost reduction vs cloud-only.

---

## Final Critiques

### The Skeptic: "Why won't this work?"

**Challenge:** SSE streaming is cosmetic — it doesn't make inference faster, just makes the wait feel shorter. The real bottleneck is still 3-8s of Ollama inference.

**Response:** Correct — and that's exactly why it's high priority. Perceived latency is the user experience. Showing tokens arriving at 15-25 tok/s (one every 40-65ms) feels instantaneous compared to a 5-second blank screen. Every major LLM product (ChatGPT, Claude, Gemini) uses streaming for this reason. The total time doesn't change, but the experience transforms from "is it broken?" to "it's thinking." The parallel pre-inference pipeline (#2) and council bypass (#5) do reduce actual latency by 200-400ms, which is the achievable improvement given that inference dominates.

### The Pragmatist: "Is the effort worth it?"

**Challenge:** 6 hours/week of usage. Is it worth 2-3 sessions of development for a few hundred milliseconds?

**Response:** The SSE streaming recommendation is not about milliseconds — it's about interaction quality. Currently the iOS app is the primary interface, and every message involves staring at a loading animation for 3-8 seconds. That's the single biggest UX friction point in the entire system. Fixing it transforms Hestia from "a tool you query" to "an assistant you converse with." The parallel pipeline and council bypass are essentially free (30min-1hr of work) and compound over every single request. At ~6hrs/week, even 300ms savings per message across hundreds of messages per week adds up.

### The Long-Term Thinker: "What happens in 6 months?"

**Challenge:** These are tactical fixes. What about when you upgrade to M5, add more users, or increase usage?

**Response:** All five recommendations are **directionally correct regardless of hardware:**
- SSE streaming is required for any good chat UX — hardware doesn't change this
- Parallel pre-inference is an obvious win on any hardware
- Client caching reduces load regardless of server capacity
- MLX is the path Apple is investing in — Ollama may adopt it natively
- Council bypass reduces unnecessary computation at any scale

The "don't do" list is what protects the long-term: don't fragment the architecture (edge inference), don't overspend on hardware (M5 Ultra), don't over-engineer protocols (WebSocket everywhere). The current hub-and-spoke model (Mac Mini serves, clients consume) scales cleanly to M5 hardware and higher usage without architectural changes.

---

## Open Questions

1. **Ollama streaming API compatibility:** Does `handler.handle_streaming()` currently yield tokens at the Ollama generation rate, or does it buffer? Need to verify the `_call_ollama_stream()` path delivers true token-by-token events.
2. **ChromaDB collection size:** How many embeddings are currently stored? If approaching the M1 RAM ceiling, the HNSW rebuild/compaction strategy becomes urgent.
3. **iOS `URLSession` streaming:** Need to verify that `URLSession.bytes(for:)` works cleanly with the self-signed cert pinning delegate for SSE consumption.
4. **Council SLM model swap frequency:** How often does the Ollama model swap between `qwen3.5:9b` and `qwen2.5:0.5b`? If every request triggers a swap, the council bypass (#5) has higher impact than estimated.
5. **Actual tok/s on Mac Mini:** The M1 performance with Qwen 3.5 9B under real conditions (with OS overhead, ChromaDB, FastAPI) should be benchmarked to establish a baseline before any optimization work.

---

## Implementation Sequence

| Order | Recommendation | Effort | Sessions |
|-------|---------------|--------|----------|
| 1 | Parallel pre-inference pipeline (#2) | Trivial | 0.5 |
| 2 | Council bypass heuristic (#5) | Trivial | 0.5 |
| 3 | iOS SSE streaming for chat (#1) | Medium | 2 |
| 4 | Client-side ETag caching (#3) | Small | 1 |
| 5 | MLX evaluation (benchmark only) (#4) | Research | 1 |

Start with #2 and #5 in the same session (combined 1hr of work, immediate measurable improvement). Then tackle SSE streaming as a focused sprint.
