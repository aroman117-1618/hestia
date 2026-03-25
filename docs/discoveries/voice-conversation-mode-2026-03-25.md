# Discovery Report: Voice Conversation Mode

**Date:** 2026-03-25
**Confidence:** High
**Decision:** Build a two-phase voice conversation mode: Phase 1 uses AVSpeechSynthesizer for instant TTS with sentence-level streaming from SSE tokens; Phase 2 upgrades to Kokoro TTS (CoreML) for natural voice quality once the pipeline is proven.

## Hypothesis

We can build a compelling bidirectional voice conversation experience (speak to Hestia, hear Hestia respond) using on-device iOS speech synthesis combined with our existing SpeechService (SpeechAnalyzer) for STT, SSE streaming responses from the backend, and voice activity detection for natural turn-taking.

## Current State Assessment

### What We Already Have
- **STT:** `SpeechService.swift` using iOS 26 `SpeechAnalyzer` — real-time on-device transcription with live transcript callbacks
- **Voice Mode UI:** `ChatInputMode.voice` already exists as a distinct input mode with inline recording (no fullscreen overlay), live transcript bubble in chat, waveform visualization
- **Streaming Pipeline:** SSE streaming via `POST /v1/chat/stream` — tokens arrive in real-time, `ChatViewModel.sendMessageStreaming()` handles them
- **Voice ViewModel:** `VoiceInputViewModel` with `stopAndReturnTranscript()` — fast path that skips quality check (already built for voice conversation)
- **Backend Handler:** `handle_streaming()` with parallel pre-inference (memory + profile + council in `asyncio.gather`) — optimized for low latency

### What We Need to Build
1. **TTS Engine** — synthesize Hestia's response text into audio
2. **Voice Activity Detection (VAD)** — auto-detect when user stops speaking
3. **Audio Session Management** — simultaneous recording + playback
4. **Conversation Flow Controller** — orchestrate the STT → send → stream → TTS → listen cycle
5. **Interruption Handling** — let user interrupt Hestia mid-response

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** STT already works, SSE streaming pipeline proven, voice mode UI scaffolded, `stopAndReturnTranscript()` fast-path exists, backend optimized with parallel pre-inference (saves 150-350ms) | **Weaknesses:** No TTS infrastructure, no VAD, audio level monitoring is basic (RMS average, not VAD), local LLM has inherent latency (~2-5s for first token), no interruption handling |
| **External** | **Opportunities:** iOS 26 Personal Voice (10-prompt setup), Kokoro TTS 82M CoreML (~45ms ANE inference, 50 voices), `speech-swift` all-in-one toolkit, `.playAndRecord` + `.voiceChat` mode handles echo cancellation automatically | **Threats:** Kokoro cold start 2-3.5s on first inference, AVSpeechSynthesizer voices sound robotic, model download size (~350MB for Kokoro), Apple Neural Engine contention if running multiple CoreML models |

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | TTS engine integration (core feature), VAD auto-stop (conversation flow), audio session `.playAndRecord` setup | Interruption handling (nice-to-have for v1) |
| **Low Priority** | Kokoro TTS upgrade (Phase 2), Personal Voice support, speaker diarization | Custom wake word, multi-language TTS |

## Argue (Best Case)

**Evidence supporting feasibility:**

1. **The hardest parts are already built.** STT (SpeechAnalyzer), streaming pipeline (SSE), voice mode UI, and the fast-path transcript flow all exist. The remaining work is additive — no refactoring needed.

2. **AVSpeechSynthesizer is free, instant, and sufficient for Phase 1.** It ships with iOS, requires zero setup, handles sentence-level streaming natively via `AVSpeechUtterance`, and has ~50-150ms time-to-first-audio. For proving the conversation flow, this is ideal.

3. **iOS handles the audio session problem.** Using `.playAndRecord` category with `.voiceChat` mode enables hardware-accelerated Acoustic Echo Cancellation. No manual audio routing needed — the system prevents TTS playback from being picked up by the mic.

4. **SSE tokens can be sentence-buffered for TTS.** As streaming tokens arrive, accumulate until a sentence boundary (`.`, `!`, `?`, newline), then immediately speak that sentence while continuing to accumulate the next. This gives perceived-instant voice response — the first sentence starts speaking as soon as it's complete, typically 1-2s after first token.

5. **VAD is a solved problem.** Silero VAD v5 runs in real-time with ~1.8s silence detection. Multiple Swift packages exist (`ios-vad`, `RealTimeCutVADLibrary`). Even a simple RMS-threshold approach (which we already compute in `processAudioBuffer`) can work for v1.

6. **Upgrade path to neural TTS is clear.** Kokoro TTS via CoreML/MLX delivers near-human quality at 82M params. `speech-swift` wraps it in a clean Swift API. When ready, swap `AVSpeechSynthesizer` for Kokoro with a protocol abstraction.

**Upside scenario:** Voice conversation mode ships in ~20-25 hours with AVSpeechSynthesizer. Users can talk to Hestia naturally with ~3-4s total latency (silence detect + transcript + LLM first token + TTS first audio). Phase 2 (Kokoro) adds another ~8-10 hours for dramatically better voice quality.

## Refute (Devil's Advocate)

**Arguments against, or risks:**

1. **Local LLM latency is the bottleneck, not TTS.** Qwen 3.5 9B on M1 takes 2-5 seconds for first token. Combined with VAD silence detection (~1.8s) and STT finalization (~0.5s), total latency could be 4-8 seconds. This is noticeably worse than ChatGPT's voice mode (~1-2s). Mitigation: (a) this is a local-first system, users accept the tradeoff; (b) cloud routing (`enabled_smart` or `enabled_full`) can reduce LLM latency to ~1s; (c) visual thinking indicator bridges the gap.

2. **AVSpeechSynthesizer sounds robotic.** For a "Jarvis-like" assistant, the stock voices may underwhelm. The gap between "it works" and "it feels good" is significant for voice UX. Mitigation: (a) use the highest-quality "Enhanced" or "Premium" voices available on iOS 26; (b) Phase 2 with Kokoro addresses this directly; (c) Personal Voice (user's own voice clone) is available on iOS 26 with only 10 prompts setup.

3. **Audio session management is tricky in practice.** Switching between STT and TTS, handling Bluetooth, phone calls, and other audio interruptions adds complexity. Edge cases: what happens when a call comes in mid-conversation? When AirPods disconnect? Mitigation: `AVAudioSession` interruption notifications are well-documented; `.voiceChat` mode handles most cases automatically.

4. **Conversation flow state machine is complex.** States: idle → listening → processing → speaking → (interrupt → listening | finished → listening). Each transition has edge cases (empty transcript, error responses, TTS failures). Mitigation: the existing `VoicePhase` enum provides a starting point; extend it rather than rebuild.

5. **Kokoro model size (~350MB) is a concern for iOS.** Downloaded on first use, stored in app sandbox. Users on limited storage may object. Mitigation: Phase 1 uses AVSpeechSynthesizer (0MB extra); Kokoro is opt-in in Phase 2.

## Third-Party Evidence

### Alternative Approaches Considered

1. **Cloud TTS (OpenAI, ElevenLabs, Google):** Highest quality, but adds cloud dependency, latency, cost, and privacy concerns. Contradicts Hestia's local-first architecture. Rejected for default path, but could be an option when cloud routing is `enabled_full`.

2. **Speech-to-Speech (PersonaPlex from speech-swift):** Full-duplex audio-in/audio-out model. Eliminates the STT→LLM→TTS cascade. However: requires a separate model (~2GB), doesn't leverage our existing LLM personality/memory/tools pipeline. Interesting for future exploration but overkill for v1.

3. **WebSocket instead of SSE for chat:** Would enable true bidirectional streaming (send audio chunks upstream while receiving TTS chunks downstream). However, our SSE pipeline is proven and the turn-based model is sufficient. WebSocket adds protocol complexity without proportional UX benefit for turn-based conversation.

4. **Server-side TTS (on Mac Mini):** Run TTS on the Mac Mini and stream audio to iOS. Lower latency for TTS generation (Apple Silicon M1 is faster than iPhone for Kokoro). But: adds bandwidth, audio codec complexity, and means voice conversation only works when connected to the backend. Rejected — on-device TTS is more resilient.

## Gemini Web-Grounded Validation

**Model:** Gemini 2.5 Pro (thinking + google_web_search)

### Confirmed Findings

- **AVSpeechSynthesizer latency is indeed low (50-150ms to first audio)** — confirmed as highly optimized system framework
- **Kokoro CoreML warm inference ~280ms on ANE, cold start 2-3.5s** — confirms need for model pre-warming strategy
- **`.playAndRecord` + `.voiceChat` mode handles echo cancellation automatically** — confirmed as the standard approach, no manual audio routing needed
- **Kokoro generates audio ~3.3x faster than real-time on iPhone 13 Pro** (MLX path); ANE path is even faster (~15-17x real-time)
- **Production apps using Kokoro exist:** Ghost Reader AI, Locally AI, Koro Voices

### Contradicted Findings

- **Initial assumption that audio session switching (STT↔TTS) would be complex is wrong.** Gemini confirms you do NOT need to switch categories — `.playAndRecord` allows simultaneous I/O. The key insight is using `.voiceChat` mode which enables hardware AEC, meaning the mic can stay hot while TTS plays. This simplifies the architecture significantly.

### New Evidence

- **Kokoro on ANE runs in a single forward pass (~45ms) regardless of output length** — non-autoregressive architecture. This is much faster than originally assumed for the inference step itself; the overhead is in preprocessing and audio buffer setup.
- **speech-swift toolkit includes built-in Silero VAD v5** — means we could get TTS + VAD from a single dependency
- **Model pre-warming strategy:** Load the CoreML model at app launch (in background) to avoid cold-start penalty during conversation. Standard practice in production apps.

### Sources

- [Kokoro CoreML conversion pipeline](https://github.com/mattmireles/kokoro-coreml)
- [speech-swift toolkit](https://github.com/soniqo/speech-swift)
- [FluidAudio (Kokoro CoreML)](https://github.com/FluidInference/FluidAudio)
- [kokoro-ios Swift package](https://github.com/mlalma/kokoro-ios)
- [ios-vad library](https://github.com/baochuquan/ios-vad)
- [RealTimeCutVADLibrary (Silero VAD)](https://github.com/helloooideeeeea/RealTimeCutVADLibrary)
- [iOS 26 Personal Voice improvements](https://9to5mac.com/2026/03/19/ios-26-made-one-of-iphones-wildest-most-unique-features-a-lot-better/)
- [Picovoice iOS Streaming TTS tutorial](https://picovoice.ai/blog/ios-streaming-text-to-speech/)
- [LiveKit Voice Agent Architecture](https://livekit.com/blog/voice-agent-architecture-stt-llm-tts-pipelines-explained)
- [WWDC25 SpeechAnalyzer](https://developer.apple.com/videos/play/wwdc2025/277/)

## Proposed Architecture

### Turn-Based Conversation Flow

```
User taps mic → [LISTENING]
  ├─ SpeechAnalyzer streams live transcript to chat bubble
  ├─ Audio level → waveform visualization (existing)
  └─ VAD detects ~1.8s silence → auto-stop
        ↓
[PROCESSING]
  ├─ Final transcript sent via POST /v1/chat/stream (SSE)
  ├─ Thinking indicator shown
  └─ SSE tokens start arriving
        ↓
[SPEAKING]
  ├─ Tokens accumulated into sentence buffer
  ├─ Each complete sentence → AVSpeechUtterance (Phase 1) or Kokoro (Phase 2)
  ├─ TTS plays sentences sequentially
  ├─ User can interrupt (tap mic or start speaking → VAD detects voice)
  └─ When TTS finishes all sentences → auto-transition to [LISTENING]
        ↓
[LISTENING] (cycle continues)
```

### Key Components to Build

#### 1. TTSService (Protocol + AVSpeechSynthesizer Implementation)

```swift
protocol TTSEngine {
    func speak(_ text: String) async
    func stop()
    var isSpeaking: Bool { get }
    var onFinished: (() -> Void)? { get set }
}

class SystemTTSEngine: TTSEngine {
    // AVSpeechSynthesizer wrapper
    // Sentence-level queuing
    // Delegate for completion callbacks
}

// Phase 2:
class KokoroTTSEngine: TTSEngine {
    // CoreML/MLX Kokoro wrapper
    // Model pre-warming on init
    // Audio buffer → AVAudioPlayerNode playback
}
```

#### 2. VoiceConversationManager

```swift
@MainActor
class VoiceConversationManager: ObservableObject {
    @Published var state: ConversationState = .idle

    enum ConversationState {
        case idle
        case listening       // STT active, VAD monitoring
        case processing      // Transcript sent, waiting for response
        case speaking        // TTS playing response
    }

    // Orchestrates: SpeechService (STT) + TTSEngine + ChatViewModel (API)
    // Handles transitions, interruptions, auto-continue
    // VAD integration for auto-stop and interruption detection
}
```

#### 3. Audio Session Setup

```swift
// One-time setup when entering voice conversation mode
try AVAudioSession.sharedInstance().setCategory(
    .playAndRecord,
    mode: .voiceChat,
    options: [.defaultToSpeaker, .allowBluetooth]
)
```

#### 4. Sentence Buffer (SSE Token Accumulator)

```swift
class SentenceBuffer {
    private var buffer = ""

    func append(_ token: String) -> String? {
        buffer += token
        // Check for sentence boundary
        if let range = buffer.range(of: #"[.!?\n](\s|$)"#, options: .regularExpression) {
            let sentence = String(buffer[buffer.startIndex...range.lowerBound])
            buffer = String(buffer[range.upperBound...])
            return sentence
        }
        return nil
    }

    func flush() -> String? {
        guard !buffer.isEmpty else { return nil }
        let remaining = buffer
        buffer = ""
        return remaining
    }
}
```

#### 5. Simple VAD (Phase 1 — RMS threshold)

We already compute audio level in `processAudioBuffer()`. For v1, track consecutive low-level frames:

```swift
// In SpeechService or VoiceConversationManager
private var silenceFrameCount = 0
private let silenceThreshold: Float = 0.01
private let silenceFramesRequired = 45 // ~1.5s at 30fps buffer rate

func checkVAD(audioLevel: Float) -> Bool {
    if audioLevel < silenceThreshold {
        silenceFrameCount += 1
    } else {
        silenceFrameCount = 0
    }
    return silenceFrameCount >= silenceFramesRequired
}
```

### Latency Budget (Local Inference Path)

| Stage | Estimated | Notes |
|-------|-----------|-------|
| VAD silence detection | ~1.5-2.0s | Configurable threshold |
| SpeechAnalyzer finalization | ~0.3-0.5s | On-device, fast |
| Network to backend | ~5-20ms | Local network / Tailscale |
| Council intent classification | ~100ms | SLM qwen2.5:0.5b |
| Memory retrieval | ~50-100ms | Parallel with council |
| LLM first token | ~2-4s | Qwen 3.5 9B on M1 |
| Token accumulation (first sentence) | ~0.5-1.5s | Depends on sentence length |
| TTS first audio | ~50-150ms | AVSpeechSynthesizer |
| **Total: speak → hear** | **~4.5-8s** | Local path |
| **Total with cloud LLM** | **~2.5-4.5s** | Cloud path (enabled_full) |

### Phase Plan

**Phase 1: AVSpeechSynthesizer + Simple VAD (~20-25h)**
- TTSService protocol + SystemTTSEngine (AVSpeechSynthesizer)
- VoiceConversationManager state machine
- Audio session setup (`.playAndRecord` + `.voiceChat`)
- Sentence buffer for SSE token → TTS sentence queuing
- Simple RMS-based VAD for auto-stop
- UI: conversation mode indicator, speaking animation
- Auto-continue cycle (TTS finishes → resume listening)
- Interruption handling (user speaks while TTS playing → stop TTS, process new input)

**Phase 2: Kokoro TTS Upgrade (~8-12h)**
- Add `speech-swift` or `kokoro-ios` SPM dependency
- KokoroTTSEngine implementation
- Model download/management (background download, ~350MB)
- Model pre-warming at app launch
- Settings toggle: System Voice vs Neural Voice
- Voice selection UI (Kokoro has 50 voices)

**Phase 3: Advanced Features (~10-15h, optional)**
- Silero VAD v5 (more accurate than RMS threshold)
- Barge-in detection (user interrupts mid-TTS with new speech)
- Conversation history context (backend already handles via session_id)
- Haptic feedback on state transitions
- Personal Voice integration (iOS 26)
- Cloud TTS option (when cloud routing is enabled_full)

## Philosophical Layer

### Ethical Check
Voice conversation is ethically sound — it improves accessibility, enables hands-free use, and keeps data on-device (local STT, local TTS, local LLM when cloud is disabled). No user audio leaves the device. The Personal Voice feature requires explicit user consent.

### First Principles Challenge
**Why turn-based?** The simplest architecture that works. Full-duplex speech-to-speech (like PersonaPlex) would eliminate the STT→LLM→TTS cascade but would bypass our entire memory/tool/agent pipeline. Turn-based conversation leverages all existing infrastructure.

**Why on-device TTS first?** Aligns with Hestia's local-first principle. Cloud TTS would be faster and higher quality but introduces dependency. On-device TTS means voice conversation works even without internet.

### Moonshot: Full-Duplex Speech-to-Speech
**What it is:** Skip STT and TTS entirely. Feed raw audio to a speech-to-speech model that understands and generates speech natively — like GPT-4o's native voice mode.

**Technical viability:** PersonaPlex from speech-swift supports this on Apple Silicon. However, it uses its own language model, meaning it wouldn't have access to Hestia's memory, tools, personality, or agent system.

**Verdict: SHELVE.** The turn-based cascade approach (STT→LLM→TTS) is the right architecture because it keeps our LLM (with memory, tools, personality) in the loop. Speech-to-speech models would require a fundamentally different backend. Revisit when speech-to-speech models can be augmented with external tool/memory systems — likely 2027+.

## Key Principles Score

| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 5 | All processing on-device, no audio leaves device, aligns with local-first |
| Empathy | 5 | Voice is the most natural interface; accessibility win for hands-free use |
| Simplicity | 4 | Turn-based model is simple; sentence buffer adds some complexity |
| Joy | 5 | Talking to Hestia and hearing her respond is the Jarvis dream |

## Recommendation

**Build voice conversation mode in two phases.**

**Phase 1 (High confidence, ~20-25h):** Use AVSpeechSynthesizer for TTS. It's free, instant (~100ms), and lets us prove the entire conversation flow — VAD, sentence buffering, audio session management, interruption handling — without any external dependencies. The voice quality won't be amazing, but it will work, and we'll validate the UX before investing in neural TTS.

**Phase 2 (High confidence, ~8-12h):** Swap in Kokoro TTS via CoreML for dramatically better voice quality. The protocol abstraction from Phase 1 makes this a clean swap. Pre-warm the model at app launch to avoid cold-start latency.

**What would change this recommendation:**
- If AVSpeechSynthesizer quality on iOS 26 "Premium" voices is unexpectedly good, Phase 2 becomes lower priority
- If local LLM latency proves too high for conversational flow (>8s consistently), consider making cloud routing the default for voice mode
- If speech-swift releases a stable, integrated STT+TTS+VAD package before we start, consider using it as the all-in-one solution instead of building piecemeal

## Final Critiques

- **Skeptic:** "4.5-8s latency with local inference will feel sluggish compared to ChatGPT's ~1-2s." **Response:** Valid concern. Three mitigations: (1) visual thinking indicator bridges the gap psychologically; (2) cloud routing reduces to ~2.5-4.5s for users who enable it; (3) the M5 Ultra upgrade (summer 2026) will dramatically reduce local inference latency. Users who chose a local-first assistant accept this tradeoff.

- **Pragmatist:** "Is 20-25 hours of effort worth it when text chat works fine?" **Response:** Voice conversation is the defining feature of a Jarvis-like assistant. It transforms Hestia from "a chat app with an AI backend" to "a voice assistant that lives on your phone." The marginal effort is justified by the transformative UX improvement. Also, 80% of the infrastructure (STT, streaming, voice mode) already exists.

- **Long-Term Thinker:** "Will this architecture scale when we add multi-turn context, proactive voice notifications, and always-on listening?" **Response:** The turn-based model is extensible. Multi-turn context already works via `session_id`. Proactive voice notifications are a separate feature that uses TTS without STT. Always-on listening would require wake-word detection (a Phase 3+ feature), but the VoiceConversationManager state machine can accommodate it without restructuring.

## Open Questions

1. **Which AVSpeechSynthesizer voice sounds best on iOS 26?** Need to test the "Premium" tier voices and any new iOS 26 voices. The `com.apple.voice.premium.en-US.Zoe` or similar may be acceptable for Phase 1.
2. **Should auto-continue be the default?** After TTS finishes speaking, should we auto-start listening again, or wait for user to tap mic? Suggestion: auto-continue with a 2s grace period (show "Tap to end conversation" affordance).
3. **How should voice conversation mode interact with tool calls?** If Hestia executes a tool (e.g., "check my calendar"), should the tool result be spoken? Probably yes — speak the synthesis, not the raw tool output.
4. **Kokoro model management:** Download on first use of neural voice? Bundle in app? On-demand download with progress indicator is likely best.
5. **VAD sensitivity tuning:** The RMS threshold approach needs real-world testing. Background noise (coffee shop, car) may cause false positives. Silero VAD would be more robust but adds a dependency.
