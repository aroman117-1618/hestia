import Foundation

/// A message in the conversation
public struct ConversationMessage: Codable, Identifiable, Equatable, Sendable {
    public let id: String
    public let role: MessageRole
    public var content: String
    public let timestamp: Date
    public let mode: HestiaMode?
    public var bylines: [AgentByline]?

    public init(id: String, role: MessageRole, content: String, timestamp: Date, mode: HestiaMode?, bylines: [AgentByline]? = nil) {
        self.id = id
        self.role = role
        self.content = content
        self.timestamp = timestamp
        self.mode = mode
        self.bylines = bylines
    }

    public enum MessageRole: String, Codable, Sendable {
        case user
        case assistant
    }

    /// Create a user message
    public static func userMessage(_ content: String) -> ConversationMessage {
        ConversationMessage(
            id: UUID().uuidString,
            role: .user,
            content: content,
            timestamp: Date(),
            mode: nil
        )
    }

    /// Create an assistant message
    public static func assistantMessage(_ content: String, mode: HestiaMode) -> ConversationMessage {
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
public struct ConversationSession: Codable, Identifiable, Sendable {
    public let sessionId: String
    public let mode: String
    public let startedAt: Date
    public let lastActivity: Date
    public let turnCount: Int
    public let deviceId: String?

    public var id: String { sessionId }

    public init(sessionId: String, mode: String, startedAt: Date, lastActivity: Date, turnCount: Int, deviceId: String?) {
        self.sessionId = sessionId
        self.mode = mode
        self.startedAt = startedAt
        self.lastActivity = lastActivity
        self.turnCount = turnCount
        self.deviceId = deviceId
    }

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
    public static let mockMessages: [ConversationMessage] = [
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
