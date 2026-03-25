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

    private nonisolated static let defaultVoiceLanguage = "en-US"
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
    func queueSentence(_ sentence: String) {
        let trimmed = sentence.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }

        pendingSentences.append(trimmed)
        totalSentenceCount += 1

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
        let speechString = utterance.speechString
        Task { @MainActor in
            onSentenceFinished?(speechString)
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
