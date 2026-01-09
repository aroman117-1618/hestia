import Foundation

/// A message in the conversation
struct ConversationMessage: Codable, Identifiable, Equatable {
    let id: String
    let role: MessageRole
    let content: String
    let timestamp: Date
    let mode: HestiaMode?

    enum MessageRole: String, Codable {
        case user
        case assistant
    }

    /// Create a user message
    static func userMessage(_ content: String) -> ConversationMessage {
        ConversationMessage(
            id: UUID().uuidString,
            role: .user,
            content: content,
            timestamp: Date(),
            mode: nil
        )
    }

    /// Create an assistant message
    static func assistantMessage(_ content: String, mode: HestiaMode) -> ConversationMessage {
        ConversationMessage(
            id: UUID().uuidString,
            role: .assistant,
            content: content,
            timestamp: Date(),
            mode: mode
        )
    }
}

// MARK: - Conversation Session

/// A conversation session containing messages
struct ConversationSession: Codable, Identifiable {
    let sessionId: String
    let mode: String
    let startedAt: Date
    let lastActivity: Date
    let turnCount: Int
    let deviceId: String?

    var id: String { sessionId }

    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
        case mode
        case startedAt = "started_at"
        case lastActivity = "last_activity"
        case turnCount = "turn_count"
        case deviceId = "device_id"
    }
}

// MARK: - Mock Data

extension ConversationMessage {
    static let mockMessages: [ConversationMessage] = [
        ConversationMessage(
            id: "1",
            role: .assistant,
            content: "Hi Boss, ready for some good trouble?",
            timestamp: Date().addingTimeInterval(-120),
            mode: .tia
        ),
        ConversationMessage(
            id: "2",
            role: .user,
            content: "What time is my next meeting?",
            timestamp: Date().addingTimeInterval(-60),
            mode: nil
        ),
        ConversationMessage(
            id: "3",
            role: .assistant,
            content: "Your meeting with Gavin is in 12 minutes. It's in Conference Room A.",
            timestamp: Date(),
            mode: .tia
        )
    ]
}
