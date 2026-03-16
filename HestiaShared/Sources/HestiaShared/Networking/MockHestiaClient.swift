import Foundation

/// Mock implementation of HestiaClientProtocol for development and testing
public class MockHestiaClient: HestiaClientProtocol {
    // MARK: - State

    private var currentMode: HestiaMode = .tia
    private var sessionId: String?
    private var messages: [ConversationMessage] = []
    private var pendingReviews: [MemoryChunk] = MemoryChunk.mockPendingReviews

    /// Simulated network delay range in seconds
    public var networkDelayRange: ClosedRange<Double> = 0.5...2.0

    /// Whether to simulate errors randomly
    public var simulateErrors: Bool = false

    public init() {}

    // MARK: - Chat

    public func sendMessage(_ message: String, sessionId: String?, forceLocal: Bool = false) async throws -> HestiaResponse {
        let delay = Double.random(in: networkDelayRange)
        try await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))

        if simulateErrors && Int.random(in: 1...10) == 1 {
            throw HestiaError.requestTimeout
        }

        let responseContent = generateResponse(for: message)
        let tokensIn = message.count / 4
        let tokensOut = responseContent.count / 4

        return HestiaResponse(
            requestId: UUID().uuidString,
            content: responseContent,
            responseType: .text,
            mode: currentMode.rawValue,
            sessionId: self.sessionId ?? UUID().uuidString,
            timestamp: Date(),
            metrics: ResponseMetrics(
                tokensIn: tokensIn,
                tokensOut: tokensOut,
                durationMs: delay * 1000
            ),
            toolCalls: nil,
            error: nil
        )
    }

    public func sendMessageStream(_ message: String, sessionId: String?, forceLocal: Bool = false) -> AsyncThrowingStream<ChatStreamEvent, Error> {
        AsyncThrowingStream { continuation in
            Task { [weak self] in
                guard let self else {
                    continuation.finish()
                    return
                }
                do {
                    // Simulate streaming: emit tokens word by word
                    let response = try await self.sendMessage(message, sessionId: sessionId, forceLocal: forceLocal)
                    let words = response.content.split(separator: " ")
                    for (index, word) in words.enumerated() {
                        let token = (index > 0 ? " " : "") + word
                        continuation.yield(.token(content: String(token), requestId: response.requestId))
                        try await Task.sleep(nanoseconds: 50_000_000) // 50ms per token
                    }
                    continuation.yield(.done(
                        requestId: response.requestId,
                        metrics: response.metrics,
                        mode: response.mode,
                        sessionId: response.sessionId
                    ))
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
        }
    }

    // MARK: - Mode Management

    public func getCurrentMode() async throws -> HestiaMode {
        try await simulateDelay()
        return currentMode
    }

    public func switchMode(to mode: HestiaMode) async throws {
        try await simulateDelay()
        currentMode = mode
    }

    // MARK: - Health

    public func getSystemHealth() async throws -> SystemHealth {
        try await simulateDelay()
        return SystemHealth.mockHealthy
    }

    // MARK: - Memory

    public func getPendingMemoryReviews() async throws -> [MemoryChunk] {
        try await simulateDelay()
        return pendingReviews.filter { $0.status == .staged }
    }

    public func approveMemory(chunkId: String, notes: String?) async throws {
        try await simulateDelay()
        if let index = pendingReviews.firstIndex(where: { $0.id == chunkId }) {
            pendingReviews.remove(at: index)
        }
    }

    public func rejectMemory(chunkId: String) async throws {
        try await simulateDelay()
        if let index = pendingReviews.firstIndex(where: { $0.id == chunkId }) {
            pendingReviews.remove(at: index)
        }
    }

    public func searchMemory(query: String, limit: Int) async throws -> [MemorySearchResult] {
        try await simulateDelay()
        return MemorySearchResult.mockResults
    }

    // MARK: - Session

    public func createSession(mode: HestiaMode) async throws -> String {
        try await simulateDelay()
        let newSessionId = "session-\(UUID().uuidString.prefix(8))"
        self.sessionId = newSessionId
        self.currentMode = mode
        return newSessionId
    }

    public func getSessionHistory(sessionId: String) async throws -> [ConversationMessage] {
        try await simulateDelay()
        return messages
    }

    // MARK: - Private Helpers

    private func simulateDelay() async throws {
        let delay = Double.random(in: 0.2...0.5)
        try await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
    }

    private func generateResponse(for message: String) -> String {
        let lowercased = message.lowercased()

        if lowercased.contains("meeting") || lowercased.contains("calendar") {
            return "Your meeting with Gavin is in 12 minutes. It's in Conference Room A."
        }

        if lowercased.contains("hello") || lowercased.contains("hi") || lowercased.contains("hey") {
            return greetingForCurrentTime()
        }

        if lowercased.contains("weather") {
            return "It's currently 72\u{00B0}F and sunny in your area. Perfect day for a walk!"
        }

        if lowercased.contains("reminder") {
            return "You have 3 reminders due today: pick up dry cleaning, call mom, and submit expense report."
        }

        if lowercased.contains("email") {
            return "You have 5 unread emails. The most recent is from Sarah about the Q4 budget review."
        }

        if lowercased.contains("help") || lowercased.contains("what can you do") {
            return "I can help with calendar, reminders, email, and general questions. Try asking about your schedule or setting a reminder!"
        }

        if lowercased.contains("@mira") {
            return "Switching to learning mode. What would you like to explore today?"
        }
        if lowercased.contains("@olly") {
            return "Project mode activated. Let's focus. What are we working on?"
        }
        if lowercased.contains("@tia") {
            return "Back to daily ops mode. What do you need?"
        }

        return modeSpecificDefaultResponse()
    }

    private func greetingForCurrentTime() -> String {
        let hour = Calendar.current.component(.hour, from: Date())

        let greetings: [(ClosedRange<Int>, [String])] = [
            (0...11, [
                "Morning, Boss.",
                "Ready to get after it?",
                "Early start today. Coffee's brewing metaphorically."
            ]),
            (12...16, [
                "Afternoon, Boss.",
                "How's the day treating you?",
                "Making progress?"
            ]),
            (17...23, [
                "Evening, Boss.",
                "Winding down or ramping up?",
                "Long day. Ready when you are."
            ])
        ]

        for (range, options) in greetings {
            if range.contains(hour) {
                return options.randomElement() ?? "Hi Boss."
            }
        }

        return "Hi Boss, ready for some good trouble?"
    }

    private func modeSpecificDefaultResponse() -> String {
        switch currentMode {
        case .tia:
            return "I'm here to help with daily tasks. What do you need?"
        case .mira:
            return "Interesting question. Let me think about that... What aspect would you like to explore first?"
        case .olly:
            return "Got it. Let's break that down into actionable steps."
        }
    }
}
