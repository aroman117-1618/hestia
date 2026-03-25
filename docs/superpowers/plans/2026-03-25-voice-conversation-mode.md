# Voice Conversation Mode — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the existing voice mode into a real-time bidirectional voice conversation — user speaks, Hestia responds with voice, conversation loops automatically.

**Architecture:** Three new services (`TTSService`, `VoiceActivityDetector`, `VoiceConversationManager`) layered on top of existing `SpeechService` and `ChatViewModel` SSE streaming. The conversation manager orchestrates a state machine: `idle → listening → processing → speaking → listening`. TTS is always on-device (AVSpeechSynthesizer Phase 1, Kokoro CoreML Phase 2). LLM inference routes through the existing 3-tier cloud routing (disabled/enabled_smart/enabled_full). Audio session uses `.playAndRecord` + `.voiceChat` for hardware echo cancellation.

**Tech Stack:** AVSpeechSynthesizer, AVAudioSession, AVAudioEngine (existing), SpeechAnalyzer (existing), SSE streaming (existing)

**Discovery:** `docs/discoveries/voice-conversation-mode-2026-03-25.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `HestiaApp/Shared/Services/TTSService.swift` | Create | AVSpeechSynthesizer wrapper — sentence splitting, voice selection, delegate callbacks |
| `HestiaApp/Shared/Services/VoiceActivityDetector.swift` | Create | RMS-based silence detection — monitors audio levels, fires callback after configurable silence duration |
| `HestiaApp/Shared/Services/VoiceConversationManager.swift` | Create | State machine orchestrating the listen→process→speak→listen loop |
| `HestiaApp/Shared/Views/Chat/VoiceConversationOverlay.swift` | Create | Full-screen conversation UI — orb animation, live transcript, Hestia's response text |
| `HestiaApp/Shared/Views/Settings/VoiceSettingsView.swift` | Create | Voice picker, VAD sensitivity slider, auto-continue toggle |
| `HestiaApp/Shared/Services/SpeechService.swift` | Modify | Add `onAudioLevel` callback for VAD to consume |
| `HestiaApp/Shared/Views/Chat/ChatView.swift` | Modify | Wire up VoiceConversationManager; present overlay in voice mode |
| `HestiaApp/Shared/ViewModels/ChatViewModel.swift` | Modify | Add `sendAndStreamResponse()` that returns an `AsyncThrowingStream` of tokens for TTS consumption |
| `HestiaApp/Shared/Views/Settings/MobileSettingsView.swift` | Modify | Add "Voice & Audio" settings block |
| `HestiaApp/Shared/Models/ChatInputMode.swift` | Modify | No structural changes — voice mode semantics change from "record + send" to "conversation" |

---

## Task 1: TTSService — Text-to-Speech Engine

**Files:**
- Create: `HestiaApp/Shared/Services/TTSService.swift`
- Test: Manual — TTS requires audio hardware, no unit test for audio output

The TTS service wraps AVSpeechSynthesizer with sentence-level streaming and voice management.

- [ ] **Step 1: Create TTSService with basic speak/stop API**

```swift
// HestiaApp/Shared/Services/TTSService.swift
import AVFoundation

/// Text-to-speech engine wrapping AVSpeechSynthesizer.
/// Splits text into sentences and speaks them sequentially,
/// enabling sentence-level streaming from SSE tokens.
@MainActor
final class TTSService: NSObject, ObservableObject {
    // MARK: - Published State

    @Published private(set) var isSpeaking: Bool = false
    @Published private(set) var currentUtterance: String = ""

    // MARK: - Callbacks

    /// Called when all queued speech finishes
    var onFinishedSpeaking: (() -> Void)?

    /// Called when an individual sentence finishes
    var onSentenceFinished: ((String) -> Void)?

    // MARK: - Private

    private let synthesizer = AVSpeechSynthesizer()
    private var selectedVoice: AVSpeechSynthesisVoice?
    private var pendingSentences: [String] = []
    private var totalSentenceCount: Int = 0

    // MARK: - Constants

    private static let defaultVoiceLanguage = "en-US"
    private static let voiceIdentifierKey = "hestia_tts_voice_identifier"

    // MARK: - Initialization

    override init() {
        super.init()
        synthesizer.delegate = self
        loadSelectedVoice()
    }

    // MARK: - Public API

    /// Speak a complete text, splitting into sentences.
    func speak(_ text: String) {
        let sentences = splitIntoSentences(text)
        guard !sentences.isEmpty else { return }

        pendingSentences = sentences
        totalSentenceCount = sentences.count
        isSpeaking = true
        speakNextSentence()
    }

    /// Queue a sentence for speaking (used with SSE streaming).
    /// Call as sentences arrive; they'll be spoken in order.
    func queueSentence(_ sentence: String) {
        let trimmed = sentence.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }

        pendingSentences.append(trimmed)
        totalSentenceCount += 1

        // If not currently speaking, start
        if !synthesizer.isSpeaking && !synthesizer.isPaused {
            isSpeaking = true
            speakNextSentence()
        }
    }

    /// Immediately stop all speech.
    func stop() {
        synthesizer.stopSpeaking(at: .immediate)
        pendingSentences.removeAll()
        totalSentenceCount = 0
        isSpeaking = false
        currentUtterance = ""
    }

    /// Get all available voices for the current language.
    func availableVoices(language: String = defaultVoiceLanguage) -> [AVSpeechSynthesisVoice] {
        AVSpeechSynthesisVoice.speechVoices()
            .filter { $0.language.hasPrefix(language.prefix(2).lowercased()) }
            .sorted { ($0.quality.rawValue, $0.name) > ($1.quality.rawValue, $1.name) }
    }

    /// Select a voice by identifier. Persists to UserDefaults.
    func selectVoice(identifier: String) {
        selectedVoice = AVSpeechSynthesisVoice(identifier: identifier)
        UserDefaults.standard.set(identifier, forKey: Self.voiceIdentifierKey)
    }

    /// Current voice name for display.
    var currentVoiceName: String {
        selectedVoice?.name ?? "System Default"
    }

    // MARK: - Private

    private func loadSelectedVoice() {
        if let id = UserDefaults.standard.string(forKey: Self.voiceIdentifierKey) {
            selectedVoice = AVSpeechSynthesisVoice(identifier: id)
        }
        // Fall back to best available Premium/Enhanced voice
        if selectedVoice == nil {
            selectedVoice = availableVoices()
                .first { $0.quality == .premium }
                ?? availableVoices()
                    .first { $0.quality == .enhanced }
        }
    }

    private func speakNextSentence() {
        guard let sentence = pendingSentences.first else {
            isSpeaking = false
            currentUtterance = ""
            onFinishedSpeaking?()
            return
        }

        pendingSentences.removeFirst()
        currentUtterance = sentence

        let utterance = AVSpeechUtterance(string: sentence)
        utterance.voice = selectedVoice
        utterance.rate = AVSpeechUtteranceDefaultSpeechRate
        utterance.pitchMultiplier = 1.0
        utterance.preUtteranceDelay = 0.05
        utterance.postUtteranceDelay = 0.1

        synthesizer.speak(utterance)
    }

    /// Split text into sentences at punctuation boundaries.
    private func splitIntoSentences(_ text: String) -> [String] {
        var sentences: [String] = []
        text.enumerateSubstrings(
            in: text.startIndex...,
            options: .bySentences
        ) { substring, _, _, _ in
            if let s = substring?.trimmingCharacters(in: .whitespacesAndNewlines), !s.isEmpty {
                sentences.append(s)
            }
        }
        // If no sentence boundaries found, return the whole text
        if sentences.isEmpty && !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            sentences.append(text.trimmingCharacters(in: .whitespacesAndNewlines))
        }
        return sentences
    }
}

// MARK: - AVSpeechSynthesizerDelegate

extension TTSService: AVSpeechSynthesizerDelegate {
    nonisolated func speechSynthesizer(
        _ synthesizer: AVSpeechSynthesizer,
        didFinish utterance: AVSpeechUtterance
    ) {
        Task { @MainActor in
            onSentenceFinished?(utterance.speechString)
            speakNextSentence()
        }
    }

    nonisolated func speechSynthesizer(
        _ synthesizer: AVSpeechSynthesizer,
        didCancel utterance: AVSpeechUtterance
    ) {
        Task { @MainActor in
            isSpeaking = false
            currentUtterance = ""
        }
    }
}
```

- [ ] **Step 2: Verify TTSService compiles**

Run: `cd HestiaApp && xcodebuild -scheme HestiaApp -destination 'generic/platform=iOS' build CODE_SIGNING_ALLOWED=NO 2>&1 | tail -3`
Expected: BUILD SUCCEEDED

- [ ] **Step 3: Commit**

```bash
git add HestiaApp/Shared/Services/TTSService.swift
git commit -m "feat(voice): add TTSService — AVSpeechSynthesizer wrapper with sentence streaming"
```

---

## Task 2: VoiceActivityDetector — Silence Detection

**Files:**
- Create: `HestiaApp/Shared/Services/VoiceActivityDetector.swift`

Monitors audio levels from SpeechService and fires a callback when sustained silence is detected.

- [ ] **Step 1: Create VoiceActivityDetector**

```swift
// HestiaApp/Shared/Services/VoiceActivityDetector.swift
import Foundation
import Combine

/// Detects when the user stops speaking by monitoring audio levels.
/// Uses a simple RMS threshold + silence duration approach.
@MainActor
final class VoiceActivityDetector: ObservableObject {
    // MARK: - Published State

    @Published private(set) var isSpeechDetected: Bool = false

    // MARK: - Configuration

    /// Audio level below this threshold is considered silence (0.0-1.0 normalized).
    /// Default 0.015 corresponds to ~-32 dB, suitable for most environments.
    var silenceThreshold: CGFloat = 0.015

    /// Seconds of continuous silence before triggering onSilenceDetected.
    var silenceDuration: TimeInterval = 1.5

    /// Whether detection is active.
    private(set) var isMonitoring: Bool = false

    // MARK: - Callbacks

    /// Fired when sustained silence is detected after speech.
    var onSilenceDetected: (() -> Void)?

    // MARK: - Private

    private var silenceStartTime: Date?
    private var hasSpeechOccurred: Bool = false
    private var monitorTask: Task<Void, Never>?

    // MARK: - Public API

    /// Start monitoring audio levels. Call `update(audioLevel:)` on each frame.
    func startMonitoring() {
        isMonitoring = true
        silenceStartTime = nil
        hasSpeechOccurred = false
        isSpeechDetected = false
    }

    /// Stop monitoring.
    func stopMonitoring() {
        isMonitoring = false
        monitorTask?.cancel()
        monitorTask = nil
        silenceStartTime = nil
        hasSpeechOccurred = false
        isSpeechDetected = false
    }

    /// Feed an audio level sample (0.0-1.0 normalized). Call from SpeechService's audio tap.
    func update(audioLevel: CGFloat) {
        guard isMonitoring else { return }

        if audioLevel > silenceThreshold {
            // Speech detected
            isSpeechDetected = true
            hasSpeechOccurred = true
            silenceStartTime = nil
        } else if hasSpeechOccurred {
            // Silence after speech
            isSpeechDetected = false

            if silenceStartTime == nil {
                silenceStartTime = Date()
            }

            if let start = silenceStartTime,
               Date().timeIntervalSince(start) >= silenceDuration {
                // Sustained silence — trigger callback
                isMonitoring = false
                silenceStartTime = nil
                onSilenceDetected?()
            }
        }
        // If no speech has occurred yet, don't trigger on initial silence
    }

    /// Reset silence timer without stopping monitoring.
    /// Use when TTS starts playing to avoid false triggers from echo.
    func resetSilenceTimer() {
        silenceStartTime = nil
    }
}
```

- [ ] **Step 2: Verify build**

Run: `cd HestiaApp && xcodebuild -scheme HestiaApp -destination 'generic/platform=iOS' build CODE_SIGNING_ALLOWED=NO 2>&1 | tail -3`
Expected: BUILD SUCCEEDED

- [ ] **Step 3: Commit**

```bash
git add HestiaApp/Shared/Services/VoiceActivityDetector.swift
git commit -m "feat(voice): add VoiceActivityDetector — RMS-based silence detection"
```

---

## Task 3: SpeechService + VoiceInputViewModel Modifications

**Files:**
- Modify: `HestiaApp/Shared/Services/SpeechService.swift`
- Modify: `HestiaApp/Shared/ViewModels/VoiceInputViewModel.swift`

Add an `onAudioLevel` callback so the VAD can consume audio levels, and expose the SpeechService instance for the conversation manager to share.

**Design note:** No pause/resume needed. The `.voiceChat` audio session mode provides hardware acoustic echo cancellation. The VAD's `stopMonitoring()` is sufficient to prevent false triggers during TTS playback. The audio engine is torn down by `stopTranscription()` and recreated by `startTranscription()` each conversation turn.

- [ ] **Step 1: Expose SpeechService on VoiceInputViewModel**

In `VoiceInputViewModel.swift` (~line 35), change:
```swift
private let speechService = SpeechService()
```
to:
```swift
let speechService = SpeechService()
```

This gives `VoiceConversationManager` access to the shared instance via `voiceViewModel.speechService`, avoiding duplicate audio engines.

- [ ] **Step 2: Add onAudioLevel callback to SpeechService**

Add a public callback property after the existing published properties (~line 18):
```swift
/// Called on each audio buffer with the normalized audio level (0.0-1.0).
/// Used by VoiceActivityDetector for silence detection.
var onAudioLevel: ((CGFloat) -> Void)?
```

In `processAudioBuffer(_:)` (~line 206), after the line `self.audioLevel = normalized`, add:
```swift
self.onAudioLevel?(normalized)
```

- [ ] **Step 2: Verify build**

Run: `cd HestiaApp && xcodebuild -scheme HestiaApp -destination 'generic/platform=iOS' build CODE_SIGNING_ALLOWED=NO 2>&1 | tail -3`
Expected: BUILD SUCCEEDED

- [ ] **Step 3: Commit**

```bash
git add HestiaApp/Shared/Services/SpeechService.swift
git commit -m "feat(voice): add audio level callback and pause/resume to SpeechService"
```

---

## Task 4: ChatViewModel — Streaming Response Method

**Files:**
- Modify: `HestiaApp/Shared/ViewModels/ChatViewModel.swift`

Add a method that sends a message and returns the SSE token stream for the conversation manager to consume and feed to TTS.

- [ ] **Step 1: Add sendAndStreamResponse method**

Add after the existing `sendMessage()` method (~line 120). **Important:** The `ChatStreamEvent` enum has 9 cases — match the pattern in `sendMessageStreamingWithMetadata()` (line 264):

```swift
/// Send a message and return SSE tokens via callbacks.
/// Used by VoiceConversationManager to feed tokens to TTS in real-time.
/// Also populates the chat history (user + assistant messages).
func sendAndStreamResponse(
    _ text: String,
    appState: AppState,
    onToken: @escaping (String) -> Void,
    onClearStream: @escaping () -> Void,
    onComplete: @escaping (String) -> Void,
    onError: @escaping (String) -> Void
) async {
    guard !isLoading else { return }
    isLoading = true
    currentStage = "thinking"

    // Add user message to chat
    let userMessage = ConversationMessage(
        id: UUID().uuidString,
        role: .user,
        content: text,
        timestamp: Date(),
        mode: appState.currentMode,
        inputMode: "voice"
    )
    messages.append(userMessage)

    // Create assistant placeholder
    let assistantMessage = ConversationMessage(
        id: UUID().uuidString,
        role: .assistant,
        content: "",
        timestamp: Date(),
        mode: appState.currentMode
    )
    messages.append(assistantMessage)
    let messageIndex = messages.count - 1

    var fullResponse = ""

    defer {
        isLoading = false
        isTyping = false
        currentTypingText = nil
        currentStage = nil
    }

    do {
        let stream = client.sendMessageStream(
            text,
            sessionId: sessionId,
            forceLocal: forceLocal,
            metadata: ["input_mode": "voice"]
        )

        for try await event in stream {
            switch event {
            case .token(let content, _):
                if !isTyping {
                    isTyping = true
                    currentTypingText = ""
                    currentStage = nil
                }
                fullResponse += content
                currentTypingText = (currentTypingText ?? "") + content
                messages[messageIndex].content = fullResponse
                onToken(content)

            case .clearStream:
                fullResponse = ""
                currentTypingText = ""
                messages[messageIndex].content = ""
                onClearStream()

            case .status(let stage, _):
                currentStage = stage

            case .done(_, _, let mode, let returnedSessionId, let bylines):
                if self.sessionId == nil, let sid = returnedSessionId {
                    self.sessionId = sid
                }
                if let newMode = HestiaMode(rawValue: mode),
                   newMode != appState.currentMode {
                    appState.switchMode(to: newMode)
                }
                if let bylines = bylines, !bylines.isEmpty {
                    messages[messageIndex].bylines = bylines
                }

            case .reasoning(let aspect, let summary, _):
                if messages[messageIndex].reasoningSteps == nil {
                    messages[messageIndex].reasoningSteps = []
                }
                messages[messageIndex].reasoningSteps?.append(
                    ReasoningStep(aspect: aspect, summary: summary)
                )

            case .verification(let risk):
                messages[messageIndex].hallucinationRisk = risk

            case .error(_, let message):
                onError(message)

            case .toolResult, .insight:
                break
            }
        }

        if fullResponse.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            fullResponse = "Sorry, I ran into a problem processing that."
            messages[messageIndex].content = fullResponse
        }

        onComplete(fullResponse)
    } catch {
        let message = error.localizedDescription
        onError(message)
        messages[messageIndex].content = "Sorry, I couldn't process that. Please try again."
    }
}
```

- [ ] **Step 2: Verify build**

Run: `cd HestiaApp && xcodebuild -scheme HestiaApp -destination 'generic/platform=iOS' build CODE_SIGNING_ALLOWED=NO 2>&1 | tail -3`
Expected: BUILD SUCCEEDED

- [ ] **Step 3: Commit**

```bash
git add HestiaApp/Shared/ViewModels/ChatViewModel.swift
git commit -m "feat(voice): add sendAndStreamResponse for voice conversation token streaming"
```

---

## Task 5: VoiceConversationManager — State Machine

**Files:**
- Create: `HestiaApp/Shared/Services/VoiceConversationManager.swift`

The core orchestrator. Manages the conversation loop: listen → detect silence → send to backend → stream response to TTS → listen again.

**Design notes from second-opinion review (must-fixes applied):**
- `SpeechService`, `ChatViewModel`, and `AppState` **injected** at `configure()` time — manager owns the full loop internally
- `processWithLLM()` called internally from `transitionToProcessing()` — NOT triggered from ChatView's onChange
- `llmTask` stored for cancellation — `stop()` and `interrupt()` cancel in-flight LLM requests
- `interrupt()` works in both `.processing` AND `.speaking` states (not just speaking)
- **Dead-air solved:** immediate "Hmm..." TTS acknowledgment before LLM processing starts
- **60s watchdog timer:** auto-stops listening if VAD never triggers (safety net for noisy environments)
- **3s sentence flush timeout:** prevents long silences during unpunctuated LLM output
- Handle `.clearStream` events by flushing the TTS sentence buffer
- Handle `AVAudioSession.interruptionNotification` (phone calls, Siri) to reset state
- Deactivate audio session on `stop()`

- [ ] **Step 1: Create VoiceConversationManager**

```swift
// HestiaApp/Shared/Services/VoiceConversationManager.swift
import AVFoundation
import Combine

/// Conversation state machine for voice mode.
enum VoiceConversationState: Equatable {
    case idle
    case listening
    case processing
    case speaking
}

/// Orchestrates the voice conversation loop:
/// idle → listening → processing → speaking → listening → ...
///
/// Coordinates SpeechService (STT), TTSService (TTS), VoiceActivityDetector (VAD),
/// and ChatViewModel (LLM inference via SSE).
@MainActor
final class VoiceConversationManager: ObservableObject {
    // MARK: - Published State

    @Published private(set) var state: VoiceConversationState = .idle
    @Published private(set) var isActive: Bool = false
    @Published private(set) var currentTranscript: String = ""
    @Published private(set) var currentResponse: String = ""
    @Published private(set) var error: String?

    // MARK: - Dependencies (injected at configure-time)

    private var speechService: SpeechService?
    private weak var chatViewModel: ChatViewModel?
    private weak var appState: AppState?
    private let ttsService: TTSService
    private let vad: VoiceActivityDetector

    // MARK: - Configuration

    /// Whether to auto-continue listening after TTS finishes.
    var autoContinue: Bool = true

    // MARK: - Private

    private var sentenceBuffer: String = ""
    private var llmTask: Task<Void, Never>?
    private var watchdogTask: Task<Void, Never>?
    private var sentenceFlushTask: Task<Void, Never>?
    private var cancellables = Set<AnyCancellable>()

    // MARK: - Constants

    private static let watchdogTimeout: TimeInterval = 60 // seconds
    private static let sentenceFlushTimeout: TimeInterval = 3 // seconds

    // MARK: - Initialization

    init(
        ttsService: TTSService = TTSService(),
        vad: VoiceActivityDetector = VoiceActivityDetector()
    ) {
        self.ttsService = ttsService
        self.vad = vad

        setupTTSCallbacks()
        setupInterruptionHandling()
    }

    /// Inject all dependencies. Call from ChatView's onAppear.
    func configure(speechService: SpeechService, chatViewModel: ChatViewModel, appState: AppState) {
        self.speechService = speechService
        self.chatViewModel = chatViewModel
        self.appState = appState
        setupSpeechCallbacks()
    }

    // MARK: - Public API

    /// Start a voice conversation session.
    func start() async {
        guard state == .idle, speechService != nil else { return }

        configureAudioSession()
        isActive = true
        error = nil
        await transitionToListening()
    }

    /// End the voice conversation session.
    func stop() async {
        llmTask?.cancel()
        llmTask = nil
        watchdogTask?.cancel()
        watchdogTask = nil
        sentenceFlushTask?.cancel()
        sentenceFlushTask = nil
        ttsService.stop()
        vad.stopMonitoring()
        _ = await speechService?.stopTranscription()

        state = .idle
        isActive = false
        currentTranscript = ""
        currentResponse = ""
        sentenceBuffer = ""

        // Release audio session
        try? AVAudioSession.sharedInstance().setActive(
            false,
            options: .notifyOthersOnDeactivation
        )
    }

    /// Interrupt Hestia mid-speech or cancel processing. Works in both .processing and .speaking.
    func interrupt() async {
        guard state == .speaking || state == .processing else { return }
        llmTask?.cancel()
        llmTask = nil
        ttsService.stop()
        await transitionToListening()
    }

    // MARK: - State Transitions

    private func transitionToListening() async {
        state = .listening
        currentTranscript = ""
        sentenceBuffer = ""

        vad.startMonitoring()

        // Watchdog: auto-stop after 60s if VAD never triggers (noisy environment safety net)
        watchdogTask?.cancel()
        watchdogTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: UInt64(Self.watchdogTimeout * 1_000_000_000))
            guard !Task.isCancelled else { return }
            guard let self, self.state == .listening else { return }
            // Force-process whatever we have, or stop if empty
            let transcript = await self.speechService?.stopTranscription() ?? ""
            let trimmed = transcript.trimmingCharacters(in: .whitespacesAndNewlines)
            if !trimmed.isEmpty {
                await self.transitionToProcessing(transcript: trimmed)
            } else {
                await self.stop()
            }
        }

        do {
            try await speechService?.startTranscription { [weak self] transcript, _ in
                Task { @MainActor in
                    self?.currentTranscript = transcript
                }
            }
        } catch {
            self.error = "Microphone not available"
            await stop()
        }
    }

    private func transitionToProcessing(transcript: String) async {
        state = .processing
        vad.stopMonitoring()
        watchdogTask?.cancel()
        currentTranscript = transcript
        currentResponse = ""

        // Dead-air fix: immediate audio acknowledgment before LLM processes
        ttsService.speak("Hmm...")

        // Manager owns the full loop — process LLM internally
        guard let chatViewModel, let appState else {
            error = "Not configured"
            await stop()
            return
        }
        await processWithLLM(chatViewModel: chatViewModel, appState: appState)
    }

    private func transitionToSpeaking() {
        state = .speaking
        // VAD already stopped in transitionToProcessing
        // AEC handles echo cancellation — no need to pause mic
    }

    private func transitionAfterSpeaking() async {
        if autoContinue && isActive {
            await transitionToListening()
        } else {
            await stop()
        }
    }

    // MARK: - Callbacks

    private func setupSpeechCallbacks() {
        // Audio level updates → feed to VAD
        speechService?.onAudioLevel = { [weak self] level in
            Task { @MainActor in
                self?.vad.update(audioLevel: level)
            }
        }

        // VAD detected silence → stop listening, process
        vad.onSilenceDetected = { [weak self] in
            Task { @MainActor [weak self] in
                guard let self, self.state == .listening else { return }

                let transcript = await self.speechService?.stopTranscription() ?? ""
                let trimmed = transcript.trimmingCharacters(in: .whitespacesAndNewlines)

                guard !trimmed.isEmpty else {
                    await self.transitionToListening()
                    return
                }

                self.transitionToProcessing(transcript: trimmed)
            }
        }
    }

    private func setupTTSCallbacks() {
        ttsService.onFinishedSpeaking = { [weak self] in
            Task { @MainActor [weak self] in
                guard let self, self.state == .speaking else { return }
                await self.transitionAfterSpeaking()
            }
        }
    }

    private func setupInterruptionHandling() {
        NotificationCenter.default.addObserver(
            forName: AVAudioSession.interruptionNotification,
            object: nil,
            queue: .main
        ) { [weak self] notification in
            Task { @MainActor [weak self] in
                guard let self, self.isActive else { return }

                guard let info = notification.userInfo,
                      let typeValue = info[AVAudioSessionInterruptionTypeKey] as? UInt,
                      let type = AVAudioSession.InterruptionType(rawValue: typeValue) else {
                    return
                }

                if type == .began {
                    // Phone call, Siri, etc. — stop gracefully
                    await self.stop()
                }
            }
        }
    }

    // MARK: - LLM Integration

    /// Process transcript through LLM. Called internally from transitionToProcessing.
    /// Feeds SSE tokens to TTS as sentences are completed.
    private func processWithLLM(
        chatViewModel: ChatViewModel,
        appState: AppState
    ) async {
        transitionToSpeaking()

        llmTask?.cancel()
        llmTask = Task { [weak self] in
            guard let self else { return }
            await chatViewModel.sendAndStreamResponse(
            currentTranscript,
            appState: appState,
            onToken: { [weak self] token in
                Task { @MainActor in
                    self?.handleStreamToken(token)
                }
            },
            onClearStream: { [weak self] in
                Task { @MainActor in
                    // Tool re-synthesis: discard partial speech, reset buffer
                    self?.ttsService.stop()
                    self?.sentenceBuffer = ""
                    self?.currentResponse = ""
                }
            },
            onComplete: { [weak self] fullResponse in
                Task { @MainActor in
                    self?.currentResponse = fullResponse
                    // Flush remaining buffered text to TTS
                    if let self, !self.sentenceBuffer.isEmpty {
                        self.ttsService.queueSentence(self.sentenceBuffer)
                        self.sentenceBuffer = ""
                    }
                }
            },
            onError: { [weak self] message in
                Task { @MainActor in
                    self?.error = message
                    self?.ttsService.stop()
                    if let self, self.isActive {
                        await self.transitionToListening()
                    }
                }
            }
        )
        } // end llmTask
    }

    /// Buffer SSE tokens and flush to TTS at sentence boundaries.
    /// Uses Foundation's linguistic sentence detection for accuracy.
    /// Includes a 3-second timeout flush for unpunctuated LLM output.
    private func handleStreamToken(_ token: String) {
        sentenceBuffer += token
        currentResponse += token

        // Reset sentence flush timeout on each token
        sentenceFlushTask?.cancel()
        sentenceFlushTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: UInt64(Self.sentenceFlushTimeout * 1_000_000_000))
            guard !Task.isCancelled else { return }
            guard let self, !self.sentenceBuffer.isEmpty else { return }
            // Flush buffer after timeout — LLM output may not have punctuation
            let text = self.sentenceBuffer.trimmingCharacters(in: .whitespacesAndNewlines)
            if !text.isEmpty {
                self.ttsService.queueSentence(text)
            }
            self.sentenceBuffer = ""
        }

        // Use linguistic sentence detection (handles abbreviations, decimals, etc.)
        var extractedSentences: [String] = []
        sentenceBuffer.enumerateSubstrings(
            in: sentenceBuffer.startIndex...,
            options: .bySentences
        ) { substring, _, _, _ in
            if let s = substring?.trimmingCharacters(in: .whitespacesAndNewlines), !s.isEmpty {
                extractedSentences.append(s)
            }
        }

        // If we found complete sentences, speak all but the last chunk
        // (last chunk might be an incomplete sentence still being streamed)
        if extractedSentences.count > 1 {
            for sentence in extractedSentences.dropLast() {
                ttsService.queueSentence(sentence)
            }
            // Keep the last chunk as the buffer (might be incomplete)
            sentenceBuffer = extractedSentences.last ?? ""
            sentenceFlushTask?.cancel() // Reset flush timer since we just flushed
        }
    }

    // MARK: - Audio Session

    private func configureAudioSession() {
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(
                .playAndRecord,
                mode: .voiceChat,
                options: [.defaultToSpeaker, .allowBluetooth]
            )
            try session.setActive(true)
        } catch {
            #if DEBUG
            print("[VoiceConversation] Audio session config failed: \(error)")
            #endif
        }
    }
}
```

- [ ] **Step 2: Verify build**

Run: `cd HestiaApp && xcodebuild -scheme HestiaApp -destination 'generic/platform=iOS' build CODE_SIGNING_ALLOWED=NO 2>&1 | tail -3`
Expected: BUILD SUCCEEDED

- [ ] **Step 3: Commit**

```bash
git add HestiaApp/Shared/Services/VoiceConversationManager.swift
git commit -m "feat(voice): add VoiceConversationManager — conversation loop state machine"
```

---

## Task 6: VoiceConversationOverlay — Conversation UI

**Files:**
- Create: `HestiaApp/Shared/Views/Chat/VoiceConversationOverlay.swift`

A full-screen overlay shown during voice conversation. Shows the orb, live transcript (user), and response text (Hestia), with a stop button.

- [ ] **Step 1: Create VoiceConversationOverlay**

```swift
// HestiaApp/Shared/Views/Chat/VoiceConversationOverlay.swift
#if os(iOS)
import SwiftUI
import HestiaShared

/// Full-screen overlay for active voice conversations.
/// Shows orb state, live transcript, Hestia's response, and stop button.
struct VoiceConversationOverlay: View {
    @ObservedObject var manager: VoiceConversationManager
    let onStop: () -> Void

    var body: some View {
        ZStack {
            // Background
            Color.black.opacity(0.95)
                .ignoresSafeArea()

            VStack(spacing: 0) {
                Spacer()

                // Orb
                HestiaOrbView(state: orbState, size: 160)
                    .padding(.bottom, Spacing.xl)

                // State label
                stateLabel
                    .padding(.bottom, Spacing.lg)

                // Transcript area
                transcriptArea
                    .frame(maxHeight: 200)
                    .padding(.horizontal, Spacing.xl)

                Spacer()

                // Stop button
                Button(action: onStop) {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 48))
                        .foregroundColor(.white.opacity(0.6))
                }
                .padding(.bottom, 60)
            }
        }
        .transition(.opacity)
    }

    // MARK: - Subviews

    private var orbState: HestiaOrbState {
        switch manager.state {
        case .idle: return .idle
        case .listening: return .listening
        case .processing: return .thinking
        case .speaking: return .speaking
        }
    }

    private var stateLabel: some View {
        Group {
            switch manager.state {
            case .idle:
                Text("Ready")
                    .foregroundColor(.white.opacity(0.4))
            case .listening:
                Text("Listening...")
                    .foregroundColor(.white.opacity(0.6))
            case .processing:
                Text("Thinking...")
                    .foregroundColor(.white.opacity(0.6))
            case .speaking:
                Text("Speaking")
                    .foregroundColor(.white.opacity(0.6))
            }
        }
        .font(.system(size: 15))
    }

    @ViewBuilder
    private var transcriptArea: some View {
        VStack(spacing: Spacing.md) {
            // User's transcript (while listening or after)
            if !manager.currentTranscript.isEmpty {
                Text(manager.currentTranscript)
                    .font(.system(size: 16))
                    .foregroundColor(.white.opacity(0.5))
                    .multilineTextAlignment(.center)
                    .lineLimit(4)
            }

            // Hestia's response (while speaking)
            if !manager.currentResponse.isEmpty && manager.state == .speaking {
                Text(manager.currentResponse)
                    .font(.system(size: 17, weight: .medium))
                    .foregroundColor(.white.opacity(0.9))
                    .multilineTextAlignment(.center)
                    .lineLimit(6)
            }

            // Error
            if let error = manager.error {
                Text(error)
                    .font(.system(size: 14))
                    .foregroundColor(.red.opacity(0.8))
            }
        }
    }
}
#endif
```

- [ ] **Step 2: Verify build**

Run: `cd HestiaApp && xcodebuild -scheme HestiaApp -destination 'generic/platform=iOS' build CODE_SIGNING_ALLOWED=NO 2>&1 | tail -3`
Expected: BUILD SUCCEEDED

- [ ] **Step 3: Check if HestiaOrbState has `.listening` and `.speaking` cases**

Grep for `enum HestiaOrbState` and verify. If missing, add the cases. The orb view needs to visually differentiate listening (pulsing) from speaking (flowing animation). If these states don't exist, add them to the enum and provide default visual behavior (can match existing states like `.idle` and `.thinking` initially).

- [ ] **Step 4: Commit**

```bash
git add HestiaApp/Shared/Views/Chat/VoiceConversationOverlay.swift
git commit -m "feat(voice): add VoiceConversationOverlay — full-screen conversation UI"
```

---

## Task 7: ChatView Integration — Wire Up Conversation Manager

**Files:**
- Modify: `HestiaApp/Shared/Views/Chat/ChatView.swift`

Replace the current voice mode behavior (record → send transcript) with the conversation manager loop.

- [ ] **Step 1: Add VoiceConversationManager to ChatView**

Add a new `@StateObject` after the existing `voiceViewModel` (~line 10):
```swift
@StateObject private var conversationManager = VoiceConversationManager()
@State private var showConversationOverlay = false
@State private var conversationConfigured = false
```

In the view's `.onAppear` block, add (after existing `viewModel.configure` / `voiceViewModel.configure` calls):
```swift
if !conversationConfigured {
    conversationManager.configure(
        speechService: voiceViewModel.speechService,
        chatViewModel: viewModel,
        appState: appState
    )
    conversationConfigured = true
}
```

**Prerequisite:** Task 3 exposes `speechService` on `VoiceInputViewModel` (changed from `private` to `internal`).

- [ ] **Step 2: Replace startVoiceConversation() and stopVoiceConversation()**

Replace the existing `startVoiceConversation()` (~line 436) with:
```swift
private func startVoiceConversation() {
    showConversationOverlay = true
    Task {
        await conversationManager.start()
    }
}
```

Replace the existing `stopVoiceConversation()` (~line 487) with:
```swift
private func stopVoiceConversation() {
    Task {
        await conversationManager.stop()
    }
    showConversationOverlay = false
}
```

- [ ] **Step 3: Add conversation overlay to the view body**

In the `body` ZStack, add after the existing content (before the closing `}`):
```swift
// Voice conversation overlay
if showConversationOverlay {
    VoiceConversationOverlay(
        manager: conversationManager,
        onStop: {
            stopVoiceConversation()
        }
    )
}
```

- [ ] **Step 4: Verify build**

Run: `cd HestiaApp && xcodebuild -scheme HestiaApp -destination 'generic/platform=iOS' build CODE_SIGNING_ALLOWED=NO 2>&1 | tail -3`
Expected: BUILD SUCCEEDED

- [ ] **Step 5: Commit**

```bash
git add HestiaApp/Shared/Views/Chat/ChatView.swift
git commit -m "feat(voice): integrate VoiceConversationManager into ChatView"
```

---

## Task 8: Voice Settings UI

**Files:**
- Create: `HestiaApp/Shared/Views/Settings/VoiceSettingsView.swift`
- Modify: `HestiaApp/Shared/Views/Settings/MobileSettingsView.swift`

Voice picker, VAD sensitivity, and auto-continue toggle.

- [ ] **Step 1: Create VoiceSettingsView**

```swift
// HestiaApp/Shared/Views/Settings/VoiceSettingsView.swift
#if os(iOS)
import SwiftUI
import AVFoundation
import HestiaShared

/// Settings for voice conversation: TTS voice, VAD sensitivity, auto-continue.
struct VoiceSettingsView: View {
    @StateObject private var ttsService = TTSService()
    @State private var selectedVoiceId: String = ""
    @State private var silenceDuration: Double = 1.5
    @State private var autoContinue: Bool = true
    @State private var voices: [AVSpeechSynthesisVoice] = []

    private static let silenceDurationKey = "hestia_vad_silence_duration"
    private static let autoContinueKey = "hestia_voice_auto_continue"

    var body: some View {
        List {
            // Voice Selection
            Section {
                ForEach(voices, id: \.identifier) { voice in
                    Button {
                        selectedVoiceId = voice.identifier
                        ttsService.selectVoice(identifier: voice.identifier)
                    } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(voice.name)
                                    .foregroundColor(.white)
                                Text(qualityLabel(voice.quality))
                                    .font(.caption)
                                    .foregroundColor(.white.opacity(0.4))
                            }
                            Spacer()
                            if voice.identifier == selectedVoiceId {
                                Image(systemName: "checkmark")
                                    .foregroundColor(.blue)
                            }
                        }
                    }
                }
            } header: {
                Text("Hestia's Voice")
            } footer: {
                Text("Premium voices sound most natural. Download more in Settings > Accessibility > Spoken Content > Voices.")
            }

            // Preview
            Section {
                Button("Preview Voice") {
                    ttsService.speak("Hello, I'm Hestia. How can I help you today?")
                }
            }

            // VAD Sensitivity
            Section {
                VStack(alignment: .leading) {
                    Text("Pause Detection: \(String(format: "%.1f", silenceDuration))s")
                    Slider(value: $silenceDuration, in: 0.8...3.0, step: 0.1)
                        .onChange(of: silenceDuration) { value in
                            UserDefaults.standard.set(value, forKey: Self.silenceDurationKey)
                        }
                }
            } header: {
                Text("Sensitivity")
            } footer: {
                Text("How long to wait after you stop speaking before Hestia responds. Shorter = snappier, longer = more room for natural pauses.")
            }

            // Auto-Continue
            Section {
                Toggle("Auto-Continue", isOn: $autoContinue)
                    .onChange(of: autoContinue) { value in
                        UserDefaults.standard.set(value, forKey: Self.autoContinueKey)
                    }
            } header: {
                Text("Conversation")
            } footer: {
                Text("When enabled, Hestia automatically listens for your next message after speaking. When disabled, conversation ends after each response.")
            }
        }
        .navigationTitle("Voice & Audio")
        .listStyle(.insetGrouped)
        .onAppear {
            voices = ttsService.availableVoices()
            selectedVoiceId = UserDefaults.standard.string(forKey: "hestia_tts_voice_identifier") ?? ""
            silenceDuration = UserDefaults.standard.object(forKey: Self.silenceDurationKey) as? Double ?? 1.5
            autoContinue = UserDefaults.standard.object(forKey: Self.autoContinueKey) as? Bool ?? true
        }
    }

    private func qualityLabel(_ quality: AVSpeechSynthesisVoiceQuality) -> String {
        switch quality {
        case .premium: return "Premium"
        case .enhanced: return "Enhanced"
        default: return "Default"
        }
    }
}
#endif
```

- [ ] **Step 2: Add Voice & Audio block to MobileSettingsView**

In `MobileSettingsView.swift`, add a new `HestiaSettingsBlock` after the existing blocks (before the closing of the VStack/List):

```swift
NavigationLink {
    VoiceSettingsView()
} label: {
    HestiaSettingsBlock(
        icon: "waveform.circle.fill",
        iconColor: .orange,
        title: "Voice & Audio",
        subtitle: "Hestia's voice, conversation settings"
    )
}
```

- [ ] **Step 3: Verify build**

Run: `cd HestiaApp && xcodebuild -scheme HestiaApp -destination 'generic/platform=iOS' build CODE_SIGNING_ALLOWED=NO 2>&1 | tail -3`
Expected: BUILD SUCCEEDED

- [ ] **Step 4: Commit**

```bash
git add HestiaApp/Shared/Views/Settings/VoiceSettingsView.swift HestiaApp/Shared/Views/Settings/MobileSettingsView.swift
git commit -m "feat(voice): add Voice & Audio settings — voice picker, VAD sensitivity, auto-continue"
```

---

## Task 9: Load Settings into Conversation Manager

**Files:**
- Modify: `HestiaApp/Shared/Views/Chat/ChatView.swift`
- Modify: `HestiaApp/Shared/Services/VoiceConversationManager.swift`

Wire UserDefaults settings (silence duration, auto-continue) into the conversation manager.

- [ ] **Step 1: Add loadSettings method to VoiceConversationManager**

```swift
/// Load user preferences from UserDefaults.
func loadSettings() {
    if let duration = UserDefaults.standard.object(forKey: "hestia_vad_silence_duration") as? Double {
        vad.silenceDuration = duration
    }
    if let autoValue = UserDefaults.standard.object(forKey: "hestia_voice_auto_continue") as? Bool {
        autoContinue = autoValue
    }
}
```

- [ ] **Step 2: Call loadSettings in ChatView before starting conversation**

In `startVoiceConversation()`, add before `await conversationManager.start()`:
```swift
conversationManager.loadSettings()
```

- [ ] **Step 3: Verify build and commit**

```bash
git add HestiaApp/Shared/Views/Chat/ChatView.swift HestiaApp/Shared/Services/VoiceConversationManager.swift
git commit -m "feat(voice): load voice settings into conversation manager"
```

---

## Task 10: HestiaOrbState — Add Speaking State

**Files:**
- Modify: `HestiaApp/Shared/Views/Common/HestiaOrbView.swift`

The enum already has `.idle`, `.thinking`, `.success`, and `.listening`. Only `.speaking` is missing.

- [ ] **Step 1: Add `.speaking` case to HestiaOrbState**

In `HestiaApp/Shared/Views/Common/HestiaOrbView.swift` (line 6), add after the `.listening` case:
```swift
case speaking
```

- [ ] **Step 2: Handle `.speaking` in HestiaOrbView's body**

Find the `switch` on `state` in the view body. Add a case for `.speaking` — for Phase 1, reuse the `.thinking` animation with a different color tint (e.g., amber). The exact visual design can be refined later.

- [ ] **Step 3: Verify build and commit**

```bash
git commit -am "feat(voice): add speaking state to HestiaOrbState"
```

---

## Task 11: End-to-End Integration Test (Manual)

No automated tests for audio pipeline — this requires real hardware.

- [ ] **Step 1: Build and run on iPhone via Xcode**

1. Select iPhone target, run from Xcode
2. Grant microphone + speech recognition permissions
3. Switch to voice mode (amber icon)
4. Tap mic — conversation overlay should appear with "Listening..."
5. Speak a sentence — live transcript should appear
6. Pause for 1.5 seconds — should transition to "Thinking..."
7. Backend responds — Hestia should speak the response
8. After response finishes — should auto-start listening again
9. Tap X to stop conversation

- [ ] **Step 2: Test interruption**

1. Start a conversation
2. While Hestia is speaking, start talking
3. Hestia should stop mid-sentence and start listening

- [ ] **Step 3: Test voice settings**

1. Go to Settings > Voice & Audio
2. Change voice — preview should play
3. Change silence duration — test with next conversation
4. Toggle auto-continue off — conversation should end after one response

- [ ] **Step 4: Test cloud routing**

1. Verify conversation works with cloud routing set to `enabled_full`
2. Test with `enabled_smart` — should still work (just slower)
3. Test with `disabled` — should use local model (slower latency)

---

## Summary

| Task | Component | Files | Effort |
|------|-----------|-------|--------|
| 1 | TTSService | 1 new | 3-4h |
| 2 | VoiceActivityDetector | 1 new | 1-2h |
| 3 | SpeechService mods | 1 modified | 1h |
| 4 | ChatViewModel streaming | 1 modified | 2h |
| 5 | VoiceConversationManager | 1 new | 4-5h |
| 6 | VoiceConversationOverlay | 1 new | 2-3h |
| 7 | ChatView integration | 1 modified | 2h |
| 8 | Voice settings UI | 2 files | 2-3h |
| 9 | Settings integration | 2 modified | 0.5h |
| 10 | Orb states | 1-2 modified | 1h |
| 11 | Manual E2E testing | — | 2-3h |
| | **Total** | **6 new, 6 modified** | **~22-27h** |
