import AVFoundation
import HestiaShared
import Speech

/// Service wrapping Apple's SpeechAnalyzer (iOS 26+) for on-device speech-to-text.
///
/// Pipeline: AVAudioEngine (mic) → buffer conversion → SpeechAnalyzer → transcript results
///
/// Usage:
/// ```
/// let service = SpeechService()
/// try await service.startTranscription { text, isFinal in
///     // Update UI with live transcript
/// }
/// let finalTranscript = await service.stopTranscription()
/// ```
@MainActor
class SpeechService: ObservableObject {
    // MARK: - Published State

    @Published var isRecording: Bool = false
    @Published var currentTranscript: String = ""
    @Published var recordingDuration: TimeInterval = 0
    @Published var hasPermission: Bool = false
    @Published var audioLevel: CGFloat = 0

    /// Called on each audio buffer with the normalized audio level (0.0-1.0).
    /// Used by VoiceActivityDetector for silence detection.
    var onAudioLevel: ((CGFloat) -> Void)?

    // MARK: - Private State

    private var audioEngine: AVAudioEngine?
    private var analyzer: SpeechAnalyzer?
    private var transcriber: SpeechTranscriber?
    private var inputContinuation: AsyncStream<AnalyzerInput>.Continuation?
    private var resultTask: Task<Void, Never>?
    private var durationTimer: Timer?
    private var onResultCallback: ((String, Bool) -> Void)?

    // MARK: - Initialization

    init() {
        Task {
            await checkPermissions()
        }
    }

    // MARK: - Permissions

    /// Check and request microphone + speech recognition permissions.
    func checkPermissions() async {
        let speechStatus = SFSpeechRecognizer.authorizationStatus()
        if speechStatus == .notDetermined {
            await withCheckedContinuation { continuation in
                SFSpeechRecognizer.requestAuthorization { _ in
                    continuation.resume()
                }
            }
        }

        let micStatus = AVAudioApplication.shared.recordPermission
        if micStatus == .undetermined {
            await AVAudioApplication.requestRecordPermission()
        }

        let finalSpeech = SFSpeechRecognizer.authorizationStatus()
        let finalMic = AVAudioApplication.shared.recordPermission
        hasPermission = (finalSpeech == .authorized && finalMic == .granted)
    }

    // MARK: - Transcription Lifecycle

    /// Start live transcription from the device microphone.
    ///
    /// - Parameter onResult: Callback invoked on each transcript update.
    ///   `text` is the current transcript, `isFinal` indicates segment completion.
    func startTranscription(onResult: @escaping (String, Bool) -> Void) async throws {
        guard hasPermission else {
            throw SpeechServiceError.permissionDenied
        }
        guard !isRecording else { return }

        onResultCallback = onResult
        currentTranscript = ""
        recordingDuration = 0

        // Create transcriber and analyzer
        let transcriber = SpeechTranscriber(
            locale: Locale.current,
            transcriptionOptions: [],
            reportingOptions: [.volatileResults],
            attributeOptions: []
        )
        self.transcriber = transcriber

        let analyzer = SpeechAnalyzer(modules: [transcriber])
        self.analyzer = analyzer

        // Create async stream for audio input
        let (inputSequence, continuation) = AsyncStream<AnalyzerInput>.makeStream()
        self.inputContinuation = continuation

        // Start reading results in background
        resultTask = Task { [weak self] in
            do {
                for try await result in transcriber.results {
                    guard let self else { return }
                    let text = String(result.text.characters)
                    await MainActor.run {
                        self.currentTranscript = text
                        self.onResultCallback?(text, result.isFinal)
                    }
                }
            } catch {
                #if DEBUG
                print("[SpeechService] Result stream error: \(error)")
                #endif
            }
        }

        // Start the analyzer with the input stream
        try await analyzer.start(inputSequence: inputSequence)

        // Start audio engine
        try startAudioEngine()

        isRecording = true
        startDurationTimer()
    }

    /// Stop transcription and return the final transcript.
    ///
    /// - Returns: The final transcribed text.
    func stopTranscription() async -> String {
        guard isRecording else { return currentTranscript }

        stopDurationTimer()
        stopAudioEngine()

        // Signal end of input
        inputContinuation?.finish()
        inputContinuation = nil

        // Wait for analyzer to finalize
        do {
            try await analyzer?.finalizeAndFinishThroughEndOfInput()
        } catch {
            #if DEBUG
            print("[SpeechService] Finalize error: \(error)")
            #endif
        }

        // Cancel result task
        resultTask?.cancel()
        resultTask = nil

        // Cleanup
        analyzer = nil
        transcriber = nil
        isRecording = false

        return currentTranscript
    }

    // MARK: - Audio Engine

    private func startAudioEngine() throws {
        let engine = AVAudioEngine()
        let inputNode = engine.inputNode
        let inputFormat = inputNode.outputFormat(forBus: 0)

        // Install tap to capture mic audio
        // Audio tap runs on a realtime thread — must not access @MainActor state directly
        let continuation = inputContinuation
        inputNode.installTap(
            onBus: 0,
            bufferSize: 4096,
            format: inputFormat
        ) { [weak self] buffer, _ in
            // Feed buffer to speech analyzer (thread-safe via AsyncStream)
            let input = AnalyzerInput(buffer: buffer)
            continuation?.yield(input)

            // Extract audio level for waveform visualization
            guard let channelData = buffer.floatChannelData?[0] else { return }
            let frameCount = Int(buffer.frameLength)
            var sum: Float = 0
            for i in 0..<frameCount {
                sum += abs(channelData[i])
            }
            let avg = sum / Float(max(frameCount, 1))
            let normalized = CGFloat(min(avg * 10, 1.0))
            Task { @MainActor [weak self] in
                self?.audioLevel = normalized
                self?.onAudioLevel?(normalized)
            }
        }

        engine.prepare()
        try engine.start()
        self.audioEngine = engine
    }

    private func stopAudioEngine() {
        audioEngine?.inputNode.removeTap(onBus: 0)
        audioEngine?.stop()
        audioEngine = nil
    }

    // processAudioBuffer logic moved inline into installTap closure
    // to avoid @MainActor isolation crash on audio realtime thread

    // MARK: - Duration Timer

    private func startDurationTimer() {
        durationTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.recordingDuration += 0.1
            }
        }
    }

    private func stopDurationTimer() {
        durationTimer?.invalidate()
        durationTimer = nil
    }
}

// MARK: - Errors

enum SpeechServiceError: LocalizedError {
    case permissionDenied
    case engineStartFailed
    case analyzerFailed

    var errorDescription: String? {
        switch self {
        case .permissionDenied:
            return "Microphone or speech recognition permission not granted."
        case .engineStartFailed:
            return "Failed to start audio engine."
        case .analyzerFailed:
            return "Speech analysis failed."
        }
    }
}
