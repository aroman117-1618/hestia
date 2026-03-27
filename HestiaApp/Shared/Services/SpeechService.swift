import AVFoundation
import HestiaShared
import Speech

/// Service wrapping SFSpeechRecognizer for on-device speech-to-text.
/// Uses the stable SFSpeechRecognizer API (not the iOS 26 SpeechAnalyzer which crashes).
///
/// Pipeline: AVAudioEngine (mic) → SFSpeechAudioBufferRecognitionRequest → transcript results
@MainActor
class SpeechService: ObservableObject {
    // MARK: - Published State

    @Published var isRecording: Bool = false
    @Published var currentTranscript: String = ""
    @Published var recordingDuration: TimeInterval = 0
    @Published var hasPermission: Bool = false
    @Published var audioLevel: CGFloat = 0

    var onAudioLevel: ((CGFloat) -> Void)?

    // MARK: - Private State

    private var audioEngine: AVAudioEngine?
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private let speechRecognizer = SFSpeechRecognizer(locale: Locale.current)
    private var currentTapHandler: AudioTapHandler?
    private var durationTimer: Timer?
    private var onResultCallback: ((String, Bool) -> Void)?

    // MARK: - Initialization

    init() {
        Task {
            await checkPermissions()
        }
    }

    // MARK: - Permissions

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

    func startTranscription(onResult: @escaping (String, Bool) -> Void) async throws {
        guard hasPermission else {
            throw SpeechServiceError.permissionDenied
        }
        guard !isRecording else { return }
        guard let speechRecognizer, speechRecognizer.isAvailable else {
            throw SpeechServiceError.analyzerFailed
        }

        onResultCallback = onResult
        currentTranscript = ""
        recordingDuration = 0

        // Create recognition request
        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        request.requiresOnDeviceRecognition = true
        self.recognitionRequest = request

        // Start recognition task
        recognitionTask = speechRecognizer.recognitionTask(with: request) { [weak self] result, error in
            Task { @MainActor [weak self] in
                guard let self else { return }

                if let result {
                    let text = result.bestTranscription.formattedString
                    self.currentTranscript = text
                    self.onResultCallback?(text, result.isFinal)
                }

                if error != nil || result?.isFinal == true {
                    // Recognition ended — don't stop engine here,
                    // stopTranscription() handles cleanup
                }
            }
        }

        // Start audio engine with tap
        try startAudioEngine()

        isRecording = true
        startDurationTimer()
    }

    func stopTranscription() async -> String {
        guard isRecording else { return currentTranscript }

        stopDurationTimer()
        stopAudioEngine()

        // End recognition
        recognitionRequest?.endAudio()
        recognitionTask?.cancel()
        recognitionRequest = nil
        recognitionTask = nil
        isRecording = false

        return currentTranscript
    }

    // MARK: - Audio Engine

    private func startAudioEngine() throws {
        let engine = AVAudioEngine()
        let inputNode = engine.inputNode
        let inputFormat = inputNode.outputFormat(forBus: 0)

        // Non-isolated tap handler — feeds audio to SFSpeechRecognitionRequest
        let request = recognitionRequest
        let tapHandler = AudioTapHandler(
            recognitionRequest: request,
            audioLevelCallback: { [weak self] level in
                Task { @MainActor in
                    self?.audioLevel = level
                    self?.onAudioLevel?(level)
                }
            }
        )
        self.currentTapHandler = tapHandler

        inputNode.installTap(
            onBus: 0,
            bufferSize: 4096,
            format: inputFormat,
            block: tapHandler.handleBuffer
        )

        engine.prepare()
        try engine.start()
        self.audioEngine = engine
    }

    private func stopAudioEngine() {
        audioEngine?.inputNode.removeTap(onBus: 0)
        audioEngine?.stop()
        audioEngine = nil
        currentTapHandler = nil
    }

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
            return "Speech recognition is not available."
        }
    }
}

// MARK: - Audio Tap Handler (Non-Isolated)

/// Handles audio tap callbacks on the realtime audio thread.
/// Completely decoupled from @MainActor — feeds buffers to SFSpeechRecognitionRequest.
private final class AudioTapHandler: @unchecked Sendable {
    private let recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private let audioLevelCallback: @Sendable (CGFloat) -> Void

    init(
        recognitionRequest: SFSpeechAudioBufferRecognitionRequest?,
        audioLevelCallback: @escaping @Sendable (CGFloat) -> Void
    ) {
        self.recognitionRequest = recognitionRequest
        self.audioLevelCallback = audioLevelCallback
    }

    func handleBuffer(_ buffer: AVAudioPCMBuffer, _ when: AVAudioTime) {
        // Feed to speech recognizer
        recognitionRequest?.append(buffer)

        // Extract audio level
        guard let channelData = buffer.floatChannelData?[0] else { return }
        let frameCount = Int(buffer.frameLength)
        var sum: Float = 0
        for i in 0..<frameCount {
            sum += abs(channelData[i])
        }
        let avg = sum / Float(max(frameCount, 1))
        let normalized = CGFloat(min(avg * 10, 1.0))
        audioLevelCallback(normalized)
    }
}
