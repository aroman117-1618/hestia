import Foundation

/// Protocol defining the Hestia backend client interface
@MainActor
public protocol HestiaClientProtocol {
    // MARK: - Chat

    /// Send a message to Hestia and get a response
    func sendMessage(_ message: String, sessionId: String?, forceLocal: Bool) async throws -> HestiaResponse

    /// Send a message and receive an SSE token stream for real-time display
    func sendMessageStream(_ message: String, sessionId: String?, forceLocal: Bool) -> AsyncThrowingStream<ChatStreamEvent, Error>

    // MARK: - Mode Management

    /// Get the current mode
    func getCurrentMode() async throws -> HestiaMode

    /// Switch to a different mode
    func switchMode(to mode: HestiaMode) async throws

    // MARK: - Health

    /// Get system health status
    func getSystemHealth() async throws -> SystemHealth

    // MARK: - Memory (ADR-002)

    /// Get pending memory reviews
    func getPendingMemoryReviews() async throws -> [MemoryChunk]

    /// Approve a staged memory update
    func approveMemory(chunkId: String, notes: String?) async throws

    /// Reject a staged memory update
    func rejectMemory(chunkId: String) async throws

    /// Search memory chunks (for Neural Net graph)
    func searchMemory(query: String, limit: Int) async throws -> [MemorySearchResult]

    // MARK: - Session

    /// Create a new session
    func createSession(mode: HestiaMode) async throws -> String

    /// Get conversation history for a session
    func getSessionHistory(sessionId: String) async throws -> [ConversationMessage]
}

// MARK: - Default Implementations

extension HestiaClientProtocol {
    /// Send message with automatic session management
    public func sendMessage(_ message: String) async throws -> HestiaResponse {
        try await sendMessage(message, sessionId: nil, forceLocal: false)
    }

    /// Send message without forceLocal
    public func sendMessage(_ message: String, sessionId: String?) async throws -> HestiaResponse {
        try await sendMessage(message, sessionId: sessionId, forceLocal: false)
    }

    /// Send message stream with metadata (for journal entries, etc.)
    public func sendMessageStream(_ message: String, sessionId: String?, forceLocal: Bool, metadata: [String: String]?) -> AsyncThrowingStream<ChatStreamEvent, Error> {
        // Default: ignore metadata, fall back to base implementation
        sendMessageStream(message, sessionId: sessionId, forceLocal: forceLocal)
    }

    /// Approve memory without notes
    public func approveMemory(chunkId: String) async throws {
        try await approveMemory(chunkId: chunkId, notes: nil)
    }
}
