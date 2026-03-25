import Foundation

/// A segment of transcribed speech within a journal entry.
/// Multi-speaker ready: speakerId and speakerLabel are nullable for future diarization support.
struct TranscriptSegment: Codable, Identifiable, Equatable {
    let id: String
    let text: String
    let startTime: TimeInterval
    let endTime: TimeInterval
    let speakerId: String?
    let speakerLabel: String?
    let confidence: Double
    let isParagraphBreak: Bool

    init(
        id: String = UUID().uuidString,
        text: String,
        startTime: TimeInterval,
        endTime: TimeInterval,
        speakerId: String? = nil,
        speakerLabel: String? = nil,
        confidence: Double = 1.0,
        isParagraphBreak: Bool = false
    ) {
        self.id = id
        self.text = text
        self.startTime = startTime
        self.endTime = endTime
        self.speakerId = speakerId
        self.speakerLabel = speakerLabel
        self.confidence = confidence
        self.isParagraphBreak = isParagraphBreak
    }
}

/// Metadata attached to a journal entry for backend routing and analysis.
struct JournalMetadata: Codable, Equatable {
    let inputMode: String   // "journal"
    let duration: TimeInterval
    let speakerCount: Int
    let prompt: String?     // Optional guided prompt

    init(duration: TimeInterval, speakerCount: Int = 1, prompt: String? = nil) {
        self.inputMode = "journal"
        self.duration = duration
        self.speakerCount = speakerCount
        self.prompt = prompt
    }

    /// Convert to metadata dict for the chat API request.
    var asDictionary: [String: Any] {
        var dict: [String: Any] = [
            "source": "journal",
            "input_mode": inputMode,
            "agent_hint": "artemis",
            "duration": duration,
        ]
        if speakerCount > 1 {
            dict["speaker_count"] = speakerCount
        }
        if let prompt = prompt {
            dict["prompt"] = prompt
        }
        return dict
    }
}
