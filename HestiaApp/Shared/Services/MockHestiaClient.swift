import Foundation

/// Mock implementation of HestiaClientProtocol for development and testing
class MockHestiaClient: HestiaClientProtocol {
    // MARK: - State

    private var currentMode: HestiaMode = .tia
    private var sessionId: String?
    private var messages: [ConversationMessage] = []
    private var pendingReviews: [MemoryChunk] = MemoryChunk.mockPendingReviews

    /// Simulated network delay range in seconds
    var networkDelayRange: ClosedRange<Double> = 0.5...2.0

    /// Whether to simulate errors randomly
    var simulateErrors: Bool = false

    // MARK: - Chat

    func sendMessage(_ message: String, sessionId: String?, forceLocal: Bool = false) async throws -> HestiaResponse {
        // Simulate network delay
        let delay = Double.random(in: networkDelayRange)
        try await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))

        // Randomly simulate errors if enabled
        if simulateErrors && Int.random(in: 1...10) == 1 {
            throw HestiaError.requestTimeout
        }

        // Generate response based on message content
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

    // MARK: - Mode Management

    func getCurrentMode() async throws -> HestiaMode {
        try await simulateDelay()
        return currentMode
    }

    func switchMode(to mode: HestiaMode) async throws {
        try await simulateDelay()
        currentMode = mode
    }

    // MARK: - Health

    func getSystemHealth() async throws -> SystemHealth {
        try await simulateDelay()
        return SystemHealth.mockHealthy
    }

    // MARK: - Memory

    func getPendingMemoryReviews() async throws -> [MemoryChunk] {
        try await simulateDelay()
        return pendingReviews.filter { $0.status == .staged }
    }

    func approveMemory(chunkId: String, notes: String?) async throws {
        try await simulateDelay()
        if let index = pendingReviews.firstIndex(where: { $0.id == chunkId }) {
            pendingReviews.remove(at: index)
        }
    }

    func rejectMemory(chunkId: String) async throws {
        try await simulateDelay()
        if let index = pendingReviews.firstIndex(where: { $0.id == chunkId }) {
            pendingReviews.remove(at: index)
        }
    }

    func searchMemory(query: String, limit: Int) async throws -> [MemorySearchResult] {
        try await simulateDelay()
        return MemorySearchResult.mockResults
    }

    // MARK: - Session

    func createSession(mode: HestiaMode) async throws -> String {
        try await simulateDelay()
        let newSessionId = "session-\(UUID().uuidString.prefix(8))"
        self.sessionId = newSessionId
        self.currentMode = mode
        return newSessionId
    }

    func getSessionHistory(sessionId: String) async throws -> [ConversationMessage] {
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

        // Meeting-related
        if lowercased.contains("meeting") || lowercased.contains("calendar") {
            return "Your meeting with Gavin is in 12 minutes. It's in Conference Room A."
        }

        // Greeting
        if lowercased.contains("hello") || lowercased.contains("hi") || lowercased.contains("hey") {
            return greetingForCurrentTime()
        }

        // Weather
        if lowercased.contains("weather") {
            return "It's currently 72°F and sunny in your area. Perfect day for a walk!"
        }

        // Reminders
        if lowercased.contains("reminder") {
            return "You have 3 reminders due today: pick up dry cleaning, call mom, and submit expense report."
        }

        // Email
        if lowercased.contains("email") {
            return "You have 5 unread emails. The most recent is from Sarah about the Q4 budget review."
        }

        // Help
        if lowercased.contains("help") || lowercased.contains("what can you do") {
            return "I can help with calendar, reminders, email, and general questions. Try asking about your schedule or setting a reminder!"
        }

        // Mode switch acknowledgment
        if lowercased.contains("@mira") {
            return "Switching to learning mode. What would you like to explore today?"
        }
        if lowercased.contains("@olly") {
            return "Project mode activated. Let's focus. What are we working on?"
        }
        if lowercased.contains("@tia") {
            return "Back to daily ops mode. What do you need?"
        }

        // Default response
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
