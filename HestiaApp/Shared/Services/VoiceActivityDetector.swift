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

    /// Feed an audio level sample (0.0-1.0 normalized).
    func update(audioLevel: CGFloat) {
        guard isMonitoring else { return }

        if audioLevel > silenceThreshold {
            isSpeechDetected = true
            hasSpeechOccurred = true
            silenceStartTime = nil
        } else if hasSpeechOccurred {
            isSpeechDetected = false
            if silenceStartTime == nil {
                silenceStartTime = Date()
            }
            if let start = silenceStartTime,
               Date().timeIntervalSince(start) >= silenceDuration {
                isMonitoring = false
                silenceStartTime = nil
                onSilenceDetected?()
            }
        }
    }

    /// Reset silence timer without stopping monitoring.
    func resetSilenceTimer() {
        silenceStartTime = nil
    }
}
