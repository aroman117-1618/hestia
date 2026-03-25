import SwiftUI
import HestiaShared

/// Input modes for the chat interface — each maps to a distinct UX and agent routing behavior.
enum ChatInputMode: String, CaseIterable, Identifiable {
    case chat
    case voice
    case journal

    var id: String { rawValue }

    /// SF Symbol for the mode toggle button
    var icon: String {
        switch self {
        case .chat: return "text.bubble"
        case .voice: return "waveform"
        case .journal: return "book"
        }
    }

    /// Agent-mapped color: blue = chat, amber = Hestia/voice, teal = Artemis/journal
    var color: Color {
        switch self {
        case .chat: return Color(hex: "0A84FF")     // iOS system blue
        case .voice: return Color(hex: "FF9F0A")     // Amber — Hestia
        case .journal: return Color(hex: "30D5C8")   // Teal — Artemis
        }
    }

    /// Placeholder text for the input field
    var placeholder: String {
        switch self {
        case .chat: return "Message"
        case .voice: return "Tap mic to talk"
        case .journal: return "Tap mic to journal"
        }
    }

    /// Next mode in the cycle (tap to advance)
    var next: ChatInputMode {
        switch self {
        case .chat: return .voice
        case .voice: return .journal
        case .journal: return .chat
        }
    }

    /// Agent hint passed to the backend for routing
    var agentHint: String? {
        switch self {
        case .chat: return nil
        case .voice: return nil         // Hestia handles conversation
        case .journal: return "artemis" // Artemis handles transcription analysis
        }
    }
}
