import SwiftUI
import HestiaShared
import Combine

/// ViewModel for the main chat interface
@MainActor
class ChatViewModel: ObservableObject {
    // MARK: - Published State

    @Published var messages: [ConversationMessage] = []
    @Published var isLoading: Bool = false
    @Published var isTyping: Bool = false
    @Published var currentTypingText: String?
    @Published var errorState: HestiaError?
    @Published var showError: Bool = false
    @Published var modeSwitchTrigger: Bool = false  // For ripple animation
    @Published var forceLocal: Bool = false  // Per-message private mode toggle
    @Published var currentStage: String?  // Pipeline stage for ThinkingIndicator

    // MARK: - Private State

    private var client: HestiaClientProtocol
    private var sessionId: String?
    private var cancellables = Set<AnyCancellable>()
    private var isConfigured: Bool = false

    /// Characters per second for typewriter effect
    private let typewriterSpeed: Double = 0.03

    // MARK: - Initialization

    init(client: HestiaClientProtocol = APIClient.shared) {
        self.client = client
    }

    /// Configure with a real API client when available
    func configure(client: HestiaClientProtocol) {
        guard !isConfigured else { return }
        self.client = client
        self.isConfigured = true
        #if DEBUG
        print("[ChatViewModel] Configured with real API client")
        #endif
    }

    // MARK: - Public Methods

    /// Load initial greeting message
    func loadInitialGreeting(mode: HestiaMode = .tia) {
        guard messages.isEmpty else { return }

        let greeting = ConversationMessage(
            id: UUID().uuidString,
            role: .assistant,
            content: greetingForCurrentTime(),
            timestamp: Date(),
            mode: mode
        )
        messages.append(greeting)
    }

    /// Load mock messages for preview/testing
    func loadMockMessages() {
        messages = ConversationMessage.mockMessages
    }

    /// Send a message to Hestia
    func sendMessage(_ text: String, appState: AppState) async {
        guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return
        }

        // Clear any previous error
        errorState = nil
        showError = false

        // Check for mode invocation in the message BEFORE sending
        if let detectedMode = detectModeInvocation(in: text) {
            if detectedMode != appState.currentMode {
                await switchMode(to: detectedMode, appState: appState)
                // Remove the @mention from the message for cleaner display
                let cleanedText = removeModeInvocation(from: text)
                if cleanedText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    // User only typed @tia/@mira/@olly with nothing else
                    return
                }
            }
        }

        // Add user message immediately
        let userMessage = ConversationMessage.userMessage(text)
        messages.append(userMessage)

        // Show loading state
        isLoading = true

        do {
            // Capture and reset private mode toggle
            let wasForceLocal = forceLocal
            forceLocal = false

            // Try streaming first, fall back to REST
            do {
                try await sendMessageStreaming(text, sessionId: sessionId, forceLocal: wasForceLocal, appState: appState)
            } catch {
                #if DEBUG
                print("[ChatVM] Streaming failed, falling back to REST: \(error)")
                #endif
                // Remove empty streaming placeholder before REST fallback
                if let lastMsg = messages.last, lastMsg.role == .assistant,
                   lastMsg.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    messages.removeLast()
                }
                isTyping = false
                currentTypingText = nil
                try await sendMessageREST(text, sessionId: sessionId, forceLocal: wasForceLocal, appState: appState)
            }

        } catch let error as HestiaError {
            handleError(error)
        } catch {
            handleError(.unknown(error.localizedDescription))
        }

        isLoading = false
    }

    /// Switch to a different mode
    func switchMode(to mode: HestiaMode, appState: AppState) async {
        guard mode != appState.currentMode else { return }

        do {
            try await client.switchMode(to: mode)

            // Trigger ripple animation
            modeSwitchTrigger = true

            appState.switchMode(to: mode)

            // Reset trigger after animation (use weak self to prevent retain cycle)
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) { [weak self] in
                self?.modeSwitchTrigger = false
            }

            // Add a system-like message about the switch
            let switchMessage = ConversationMessage(
                id: UUID().uuidString,
                role: .assistant,
                content: modeSwitchMessage(mode),
                timestamp: Date(),
                mode: mode
            )
            messages.append(switchMessage)

        } catch {
            handleError(.unknown("Failed to switch mode"))
        }
    }

    /// Start a new conversation
    func startNewConversation(appState: AppState) async {
        do {
            sessionId = try await client.createSession(mode: appState.currentMode)
            messages.removeAll()
            loadInitialGreeting(mode: appState.currentMode)
        } catch {
            handleError(.unknown("Failed to create session"))
        }
    }

    /// Send a journal entry with Artemis routing metadata.
    func sendJournalEntry(_ text: String, metadata: JournalMetadata, appState: AppState) async {
        guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }

        errorState = nil
        showError = false
        isLoading = true

        do {
            let wasForceLocal = forceLocal
            forceLocal = false

            // Convert metadata to string dict for the API
            let metadataDict: [String: String] = [
                "source": "journal",
                "input_mode": "journal",
                "agent_hint": "artemis",
                "duration": String(format: "%.1f", metadata.duration),
            ]

            // Use streaming with metadata
            do {
                try await sendMessageStreamingWithMetadata(
                    text,
                    sessionId: sessionId,
                    forceLocal: wasForceLocal,
                    metadata: metadataDict,
                    appState: appState
                )
            } catch {
                #if DEBUG
                print("[ChatVM] Journal streaming failed, falling back to REST: \(error)")
                #endif
                if let lastMsg = messages.last, lastMsg.role == .assistant,
                   lastMsg.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    messages.removeLast()
                }
                isTyping = false
                currentTypingText = nil
                try await sendMessageREST(text, sessionId: sessionId, forceLocal: wasForceLocal, appState: appState)
            }
        } catch let error as HestiaError {
            handleError(error)
        } catch {
            handleError(.unknown(error.localizedDescription))
        }

        isLoading = false
    }

    /// Dismiss the current error
    func dismissError() {
        showError = false
        errorState = nil
    }

    /// Retry the last failed message
    func retryLastMessage(appState: AppState) async {
        guard let lastUserMessage = messages.last(where: { $0.role == .user }) else {
            return
        }
        // Remove the failed message indication and retry
        await sendMessage(lastUserMessage.content, appState: appState)
    }

    // MARK: - Private Methods

    /// Send via SSE streaming with optional metadata (journal entries, etc.)
    private func sendMessageStreamingWithMetadata(
        _ text: String,
        sessionId: String?,
        forceLocal: Bool,
        metadata: [String: String],
        appState: AppState
    ) async throws {
        let assistantMessage = ConversationMessage(
            id: UUID().uuidString,
            role: .assistant,
            content: "",
            timestamp: Date(),
            mode: appState.currentMode
        )
        messages.append(assistantMessage)
        let messageIndex = messages.count - 1

        defer {
            isTyping = false
            currentTypingText = nil
            currentStage = nil
        }

        let stream = client.sendMessageStream(text, sessionId: sessionId, forceLocal: forceLocal, metadata: metadata)

        for try await event in stream {
            switch event {
            case .token(let content, _):
                if !isTyping {
                    isTyping = true
                    currentTypingText = ""
                    currentStage = nil
                }
                currentTypingText = (currentTypingText ?? "") + content
                messages[messageIndex].content += content

            case .clearStream:
                currentTypingText = ""
                messages[messageIndex].content = ""

            case .status(let stage, _):
                currentStage = stage

            case .done(_, _, let mode, let returnedSessionId, let bylines):
                if self.sessionId == nil, let sid = returnedSessionId {
                    self.sessionId = sid
                }
                if let newMode = HestiaMode(rawValue: mode),
                   newMode != appState.currentMode {
                    appState.switchMode(to: newMode)
                }
                if let bylines = bylines, !bylines.isEmpty {
                    messages[messageIndex].bylines = bylines
                }

            case .reasoning(let aspect, let summary, _):
                if messages[messageIndex].reasoningSteps == nil {
                    messages[messageIndex].reasoningSteps = []
                }
                messages[messageIndex].reasoningSteps?.append(
                    ReasoningStep(aspect: aspect, summary: summary)
                )

            case .verification(let risk):
                messages[messageIndex].hallucinationRisk = risk

            case .toolResult, .insight:
                break

            case .error(_, let message):
                throw HestiaError.serverError(statusCode: 0, message: message)
            }
        }

        if messages[messageIndex].content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            messages[messageIndex].content = "Sorry, I ran into a problem processing that. Want me to try again?"
        }

        if messages.count > Constants.Limits.maxConversationHistory {
            messages.removeFirst(messages.count - Constants.Limits.maxConversationHistory)
        }
    }

    /// Send via SSE streaming — tokens appear in real-time as the LLM generates them.
    private func sendMessageStreaming(
        _ text: String,
        sessionId: String?,
        forceLocal: Bool,
        appState: AppState
    ) async throws {
        // Create a placeholder assistant message for streaming
        let assistantMessage = ConversationMessage(
            id: UUID().uuidString,
            role: .assistant,
            content: "",
            timestamp: Date(),
            mode: appState.currentMode
        )
        messages.append(assistantMessage)
        let messageIndex = messages.count - 1

        // Don't set isTyping yet — let loading indicator show
        // isTyping transitions to true on first token arrival

        defer {
            isTyping = false
            currentTypingText = nil
            currentStage = nil
        }

        let stream = client.sendMessageStream(text, sessionId: sessionId, forceLocal: forceLocal)

        for try await event in stream {
            switch event {
            case .token(let content, _):
                // Start typing indicator on first token — clear thinking stage
                if !isTyping {
                    isTyping = true
                    currentTypingText = ""
                    currentStage = nil
                }
                currentTypingText = (currentTypingText ?? "") + content
                messages[messageIndex].content += content

            case .clearStream:
                // Tool re-synthesis: discard previous tokens
                currentTypingText = ""
                messages[messageIndex].content = ""

            case .toolResult(_, let toolName, _, let result):
                #if DEBUG
                print("[ChatVM] Tool result: \(toolName)")
                #endif
                // Tool results are followed by synthesis tokens — don't display raw result
                _ = result

            case .status(let stage, let detail):
                currentStage = stage
                #if DEBUG
                print("[ChatVM] \(detail)")
                #endif

            case .done(_, _, let mode, let returnedSessionId, let bylines):
                if self.sessionId == nil, let sid = returnedSessionId {
                    self.sessionId = sid
                }
                if let newMode = HestiaMode(rawValue: mode),
                   newMode != appState.currentMode {
                    appState.switchMode(to: newMode)
                }
                // Attach bylines to the assistant message
                if let bylines = bylines, !bylines.isEmpty {
                    messages[messageIndex].bylines = bylines
                }

            case .reasoning(let aspect, let summary, _):
                if messages[messageIndex].reasoningSteps == nil {
                    messages[messageIndex].reasoningSteps = []
                }
                messages[messageIndex].reasoningSteps?.append(
                    ReasoningStep(aspect: aspect, summary: summary)
                )

            case .verification(let risk):
                messages[messageIndex].hallucinationRisk = risk

            case .insight(_, _):
                break

            case .error(_, let message):
                throw HestiaError.serverError(statusCode: 0, message: message)
            }
        }

        // Guard against empty content (clearStream with no follow-up tokens)
        if messages[messageIndex].content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            messages[messageIndex].content = "Sorry, I ran into a problem processing that. Want me to try again?"
        }

        // Enforce message limit
        if messages.count > Constants.Limits.maxConversationHistory {
            messages.removeFirst(messages.count - Constants.Limits.maxConversationHistory)
        }
    }

    /// Fallback: send via REST and display with typewriter effect.
    private func sendMessageREST(
        _ text: String,
        sessionId: String?,
        forceLocal: Bool,
        appState: AppState
    ) async throws {
        let response = try await client.sendMessage(text, sessionId: sessionId, forceLocal: forceLocal)

        if self.sessionId == nil {
            self.sessionId = response.sessionId
        }

        if let newMode = HestiaMode(rawValue: response.mode),
           newMode != appState.currentMode {
            appState.switchMode(to: newMode)
        }

        switch response.responseType {
        case .text, .clarification:
            await displayResponseWithTypewriter(response, mode: appState.currentMode, bylines: response.bylines, hallucinationRisk: response.hallucinationRisk)
        case .error:
            if let error = response.error {
                throw HestiaError.from(responseError: error)
            }
        case .toolCall:
            addAssistantMessage(response.content, mode: appState.currentMode, bylines: response.bylines, hallucinationRisk: response.hallucinationRisk)
        }
    }

    private func displayResponseWithTypewriter(_ response: HestiaResponse, mode: HestiaMode, bylines: [AgentByline]? = nil, hallucinationRisk: String? = nil) async {
        let content = response.content

        // Start typewriter
        isTyping = true
        currentTypingText = ""

        // Animate character by character
        for (_, character) in content.enumerated() {
            currentTypingText?.append(character)

            // Small delay between characters
            let delay = UInt64(typewriterSpeed * 1_000_000_000)
            try? await Task.sleep(nanoseconds: delay)

            // Cancel if message changed (user sent new message)
            if isLoading { break }
        }

        // Typewriter complete - add as regular message
        isTyping = false
        currentTypingText = nil

        addAssistantMessage(content, mode: mode, bylines: bylines, hallucinationRisk: hallucinationRisk)
    }

    private func addAssistantMessage(_ content: String, mode: HestiaMode, bylines: [AgentByline]? = nil, hallucinationRisk: String? = nil) {
        let message = ConversationMessage(
            id: UUID().uuidString,
            role: .assistant,
            content: content,
            timestamp: Date(),
            mode: mode,
            bylines: bylines,
            hallucinationRisk: hallucinationRisk
        )
        messages.append(message)

        // Enforce message limit to prevent unbounded memory growth
        if messages.count > Constants.Limits.maxConversationHistory {
            messages.removeFirst(messages.count - Constants.Limits.maxConversationHistory)
        }
    }

    private func handleError(_ error: HestiaError) {
        errorState = error
        showError = true
    }

    private func greetingForCurrentTime() -> String {
        let hour = Calendar.current.component(.hour, from: Date())

        if hour < 12 {
            return "Morning, Boss. Ready to get after it?"
        } else if hour < 17 {
            return "Afternoon, Boss. How's the day treating you?"
        } else {
            return "Evening, Boss. Winding down or ramping up?"
        }
    }

    private func modeSwitchMessage(_ mode: HestiaMode) -> String {
        switch mode {
        case .tia:
            return "Back to daily ops mode. What do you need?"
        case .mira:
            return "Switching to learning mode. What would you like to explore?"
        case .olly:
            return "Project mode activated. Let's focus. What are we working on?"
        }
    }

    // MARK: - Mode Detection

    /// Detect mode invocation patterns in text (@tia, @mira, @olly, @hestia, @artemis, @apollo, or "hey/hi/hello [name]")
    private func detectModeInvocation(in text: String) -> HestiaMode? {
        let lowercased = text.lowercased()

        // Check for @mentions (with word boundary)
        let exactPatterns: [(String, HestiaMode)] = [
            ("@tia", .tia),
            ("@hestia", .tia),
            ("@mira", .mira),
            ("@artemis", .mira),
            ("@olly", .olly),
            ("@apollo", .olly)
        ]

        for (pattern, mode) in exactPatterns {
            // Check if pattern exists and is at word boundary
            if let range = lowercased.range(of: pattern) {
                // Check character after pattern (if any) is not alphanumeric
                let afterIndex = range.upperBound
                if afterIndex == lowercased.endIndex ||
                   !lowercased[afterIndex].isLetter {
                    return mode
                }
            }
        }

        // Check for "hey/hi/hello [name]" patterns
        let greetingPatterns: [(String, HestiaMode)] = [
            ("hey tia", .tia),
            ("hi tia", .tia),
            ("hello tia", .tia),
            ("hey mira", .mira),
            ("hi mira", .mira),
            ("hello mira", .mira),
            ("hey olly", .olly),
            ("hi olly", .olly),
            ("hello olly", .olly)
        ]

        for (pattern, mode) in greetingPatterns {
            if lowercased.contains(pattern) {
                return mode
            }
        }

        return nil
    }

    /// Remove mode invocation patterns from text
    private func removeModeInvocation(from text: String) -> String {
        var result = text

        // @mention patterns
        let mentionPatterns = ["@tia", "@hestia", "@mira", "@artemis", "@olly", "@apollo"]
        for pattern in mentionPatterns {
            if let range = result.range(of: pattern, options: .caseInsensitive) {
                result.removeSubrange(range)
            }
        }

        // Greeting patterns
        let greetingPatterns = ["hey tia", "hi tia", "hello tia",
                                "hey mira", "hi mira", "hello mira",
                                "hey olly", "hi olly", "hello olly"]
        for pattern in greetingPatterns {
            if let range = result.range(of: pattern, options: .caseInsensitive) {
                result.removeSubrange(range)
            }
        }

        return result.trimmingCharacters(in: .whitespacesAndNewlines)
    }
}
