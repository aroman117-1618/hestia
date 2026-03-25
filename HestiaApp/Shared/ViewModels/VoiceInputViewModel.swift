import SwiftUI
import HestiaShared

/// ViewModel managing the voice journaling flow.
///
/// Flow: tap mic → recording → stop → quality check → review transcript → confirm → send as chat message
@MainActor
class VoiceInputViewModel: ObservableObject {
    // MARK: - Published State

    /// Current phase of the voice input flow
    @Published var phase: VoicePhase = .idle

    /// The raw transcript from SpeechAnalyzer
    @Published var rawTranscript: String = ""

    /// The user-editable transcript shown during review
    @Published var editableTranscript: String = ""

    /// Flagged words from quality check
    @Published var flaggedWords: [VoiceFlaggedWordResponse] = []

    /// Overall confidence from quality check
    @Published var overallConfidence: Double = 1.0

    /// Whether quality check found issues needing review
    @Published var needsReview: Bool = false

    /// Error message to display
    @Published var error: String?
    @Published var showError: Bool = false

    // MARK: - Private State

    private let speechService = SpeechService()
    private var apiClient: APIClient?

    // MARK: - Computed Properties

    var isRecording: Bool { phase == .recording }
    var isProcessing: Bool { phase == .qualityChecking || phase == .analyzing }

    var recordingDuration: TimeInterval {
        speechService.recordingDuration
    }

    var currentLiveTranscript: String {
        speechService.currentTranscript
    }

    var hasPermission: Bool {
        speechService.hasPermission
    }

    var audioLevel: CGFloat {
        speechService.audioLevel
    }

    // MARK: - Configuration

    func configure(client: APIClient) {
        self.apiClient = client
    }

    // MARK: - Recording Flow

    /// Start voice recording.
    func startRecording() async {
        guard phase == .idle else { return }

        error = nil
        showError = false
        rawTranscript = ""
        editableTranscript = ""
        flaggedWords = []

        do {
            await speechService.checkPermissions()
            guard speechService.hasPermission else {
                showErrorMessage("Microphone and speech recognition permissions are required.")
                return
            }

            phase = .recording

            try await speechService.startTranscription { [weak self] text, isFinal in
                Task { @MainActor [weak self] in
                    self?.rawTranscript = text
                }
            }
        } catch {
            phase = .idle
            showErrorMessage("Failed to start recording: \(error.localizedDescription)")
        }
    }

    /// Stop recording and run quality check (journal/default flow).
    func stopRecording() async {
        guard phase == .recording else { return }

        let transcript = await speechService.stopTranscription()
        rawTranscript = transcript
        editableTranscript = transcript

        guard !transcript.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            phase = .idle
            showErrorMessage("No speech detected. Try again.")
            return
        }

        // Run quality check
        await runQualityCheck(transcript: transcript)
    }

    /// Stop recording and return transcript immediately (voice conversation flow).
    /// Skips quality check and review — transcript is sent as a chat message directly.
    func stopAndReturnTranscript() async -> String? {
        guard phase == .recording else { return nil }

        let transcript = await speechService.stopTranscription()
        rawTranscript = transcript

        guard !transcript.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            resetState()
            return nil
        }

        resetState()
        return transcript
    }

    /// Skip quality review and send the transcript as-is.
    func skipReview() -> String {
        let transcript = editableTranscript
        resetState()
        return transcript
    }

    /// Accept the edited transcript and return it.
    func acceptTranscript() -> String {
        let transcript = editableTranscript
        resetState()
        return transcript
    }

    /// Cancel the voice input flow entirely.
    func cancel() {
        Task {
            if phase == .recording {
                _ = await speechService.stopTranscription()
            }
            resetState()
        }
    }

    /// Apply a suggestion for a flagged word using position-aware replacement.
    func applySuggestion(for flaggedWord: VoiceFlaggedWordResponse, suggestion: String) {
        let position = flaggedWord.position
        let word = flaggedWord.word

        // Use position to find the exact occurrence
        guard position >= 0,
              position + word.count <= editableTranscript.count else { return }

        let startIndex = editableTranscript.index(editableTranscript.startIndex, offsetBy: position)
        let endIndex = editableTranscript.index(startIndex, offsetBy: word.count)
        let range = startIndex..<endIndex

        // Verify the word at this position matches what we expect
        guard editableTranscript[range] == word else {
            // Position shifted due to prior edits — fall back to first-match
            guard let fallbackRange = editableTranscript.range(of: word) else { return }
            editableTranscript.replaceSubrange(fallbackRange, with: suggestion)
            flaggedWords.removeAll { $0.word == word && $0.position == flaggedWord.position }
            return
        }

        editableTranscript.replaceSubrange(range, with: suggestion)
        flaggedWords.removeAll { $0.word == word && $0.position == flaggedWord.position }
    }

    // MARK: - Private Methods

    private func runQualityCheck(transcript: String) async {
        guard let client = apiClient else {
            // No API client — skip quality check, go straight to review
            phase = .reviewing
            return
        }

        phase = .qualityChecking

        do {
            let response = try await client.voiceQualityCheck(transcript: transcript)
            flaggedWords = response.flaggedWords
            overallConfidence = response.overallConfidence
            needsReview = response.needsReview

            phase = .reviewing
        } catch {
            // Quality check failed — still allow user to review raw transcript
            #if DEBUG
            print("[VoiceInput] Quality check failed: \(error)")
            #endif
            phase = .reviewing
        }
    }

    private func resetState() {
        phase = .idle
        rawTranscript = ""
        editableTranscript = ""
        flaggedWords = []
        overallConfidence = 1.0
        needsReview = false
        error = nil
        showError = false
    }

    private func showErrorMessage(_ message: String) {
        error = message
        showError = true
    }
}

// MARK: - Voice Phase

enum VoicePhase {
    case idle
    case recording
    case qualityChecking
    case reviewing
    case analyzing
}
