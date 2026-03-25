// HestiaApp/Shared/Services/VoiceConversationManager.swift
import AVFoundation
import Combine
import HestiaShared

enum VoiceConversationState: Equatable, Sendable {
    case idle
    case listening
    case processing
    case speaking
}

@MainActor
final class VoiceConversationManager: ObservableObject {
    // MARK: - Published State

    @Published private(set) var state: VoiceConversationState = .idle
    @Published private(set) var isActive: Bool = false
    @Published private(set) var currentTranscript: String = ""
    @Published private(set) var currentResponse: String = ""
    @Published private(set) var error: String?

    // MARK: - Dependencies

    private var speechService: SpeechService?
    private weak var chatViewModel: ChatViewModel?
    private weak var appState: AppState?
    private let ttsService: TTSService
    private let vad: VoiceActivityDetector

    // MARK: - Configuration

    var autoContinue: Bool = true

    // MARK: - Internal State

    private var sentenceBuffer: String = ""
    private var llmTask: Task<Void, Never>?
    private var watchdogTask: Task<Void, Never>?
    private var sentenceFlushTask: Task<Void, Never>?

    // MARK: - Constants

    nonisolated static let watchdogTimeout: TimeInterval = 60
    nonisolated static let sentenceFlushTimeout: TimeInterval = 3

    // MARK: - Initialization

    init(ttsService: TTSService = TTSService(), vad: VoiceActivityDetector = VoiceActivityDetector()) {
        self.ttsService = ttsService
        self.vad = vad
        setupTTSCallbacks()
        setupInterruptionHandling()
    }

    /// Inject dependencies after init (view models are created separately).
    func configure(speechService: SpeechService, chatViewModel: ChatViewModel, appState: AppState) {
        self.speechService = speechService
        self.chatViewModel = chatViewModel
        self.appState = appState
        setupSpeechCallbacks()
    }

    // MARK: - Public API

    func start() async {
        guard state == .idle, speechService != nil else { return }
        configureAudioSession()
        isActive = true
        error = nil
        await transitionToListening()
    }

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
        deactivateAudioSession()
    }

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

        watchdogTask?.cancel()
        watchdogTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: UInt64(Self.watchdogTimeout * 1_000_000_000))
            guard !Task.isCancelled else { return }
            guard let self, self.state == .listening else { return }
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

        // Dead-air fix: immediate audio acknowledgment while LLM processes
        ttsService.speak("Hmm...")

        guard let chatViewModel, let appState else {
            error = "Not configured"
            await stop()
            return
        }
        await processWithLLM(chatViewModel: chatViewModel, appState: appState)
    }

    private func transitionToSpeaking() {
        state = .speaking
    }

    private func transitionAfterSpeaking() async {
        if autoContinue && isActive {
            await transitionToListening()
        } else {
            await stop()
        }
    }

    // MARK: - Callback Setup

    private func setupSpeechCallbacks() {
        speechService?.onAudioLevel = { [weak self] level in
            Task { @MainActor in
                self?.vad.update(audioLevel: level)
            }
        }

        vad.onSilenceDetected = { [weak self] in
            Task { @MainActor [weak self] in
                guard let self, self.state == .listening else { return }
                let transcript = await self.speechService?.stopTranscription() ?? ""
                let trimmed = transcript.trimmingCharacters(in: .whitespacesAndNewlines)
                guard !trimmed.isEmpty else {
                    // No speech captured — restart listening
                    await self.transitionToListening()
                    return
                }
                await self.transitionToProcessing(transcript: trimmed)
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
                      let type = AVAudioSession.InterruptionType(rawValue: typeValue) else { return }
                if type == .began {
                    await self.stop()
                }
            }
        }
    }

    // MARK: - LLM Integration

    private func processWithLLM(chatViewModel: ChatViewModel, appState: AppState) async {
        transitionToSpeaking()

        llmTask?.cancel()
        llmTask = Task { [weak self] in
            guard let self else { return }
            await chatViewModel.sendAndStreamResponse(
                self.currentTranscript,
                appState: appState,
                onToken: { [weak self] token in
                    Task { @MainActor in
                        self?.handleStreamToken(token)
                    }
                },
                onClearStream: { [weak self] in
                    Task { @MainActor in
                        self?.ttsService.stop()
                        self?.sentenceBuffer = ""
                        self?.currentResponse = ""
                    }
                },
                onComplete: { [weak self] fullResponse in
                    Task { @MainActor in
                        self?.currentResponse = fullResponse
                        if let self, !self.sentenceBuffer.isEmpty {
                            self.ttsService.queueSentence(self.sentenceBuffer)
                            self.sentenceBuffer = ""
                        }
                    }
                },
                onError: { [weak self] message in
                    Task { @MainActor in
                        guard let self else { return }
                        self.error = message
                        self.ttsService.stop()
                        if self.isActive {
                            await self.transitionToListening()
                        }
                    }
                }
            )
        }
    }

    private func handleStreamToken(_ token: String) {
        sentenceBuffer += token
        currentResponse += token

        // Reset the flush timer on each token
        sentenceFlushTask?.cancel()
        sentenceFlushTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: UInt64(Self.sentenceFlushTimeout * 1_000_000_000))
            guard !Task.isCancelled else { return }
            guard let self, !self.sentenceBuffer.isEmpty else { return }
            let text = self.sentenceBuffer.trimmingCharacters(in: .whitespacesAndNewlines)
            if !text.isEmpty {
                self.ttsService.queueSentence(text)
            }
            self.sentenceBuffer = ""
        }

        // Extract complete sentences from the buffer
        var extractedSentences: [String] = []
        sentenceBuffer.enumerateSubstrings(
            in: sentenceBuffer.startIndex...,
            options: .bySentences
        ) { substring, _, _, _ in
            if let s = substring?.trimmingCharacters(in: .whitespacesAndNewlines), !s.isEmpty {
                extractedSentences.append(s)
            }
        }

        // If we have 2+ sentences, speak all but the last (which may be incomplete)
        if extractedSentences.count > 1 {
            for sentence in extractedSentences.dropLast() {
                ttsService.queueSentence(sentence)
            }
            sentenceBuffer = extractedSentences.last ?? ""
            sentenceFlushTask?.cancel()
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

    private func deactivateAudioSession() {
        do {
            try AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        } catch {
            #if DEBUG
            print("[VoiceConversation] Audio session deactivation failed: \(error)")
            #endif
        }
    }
}
