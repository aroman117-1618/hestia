import SwiftUI
import HestiaShared

/// Input modes for the chat interface.
/// Simplified to chat (text) and transcription (voice-to-text).
enum ChatInputMode: String, CaseIterable, Identifiable {
    case chat
    case transcription

    var id: String { rawValue }

    /// SF Symbol for the mode
    var icon: String {
        switch self {
        case .chat: return "text.bubble"
        case .transcription: return "waveform"
        }
    }

    /// Placeholder text for the input field
    var placeholder: String {
        switch self {
        case .chat: return "Message"
        case .transcription: return "Tap mic to talk"
        }
    }

    /// Agent hint passed to the backend for routing
    var agentHint: String? {
        return nil
    }
}
