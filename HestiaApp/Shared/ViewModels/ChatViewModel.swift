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

            // Send to backend
            let response = try await client.sendMessage(text, sessionId: sessionId, forceLocal: wasForceLocal)

            // Store session ID if new
            if sessionId == nil {
                sessionId = response.sessionId
            }

            // Update mode if changed
            if let newMode = HestiaMode(rawValue: response.mode) {
                if newMode != appState.currentMode {
                    appState.switchMode(to: newMode)
                }
            }

            // Handle response type
            switch response.responseType {
            case .text, .clarification:
                await displayResponseWithTypewriter(response, mode: appState.currentMode)
            case .error:
                if let error = response.error {
                    throw HestiaError.from(responseError: error)
                }
            case .toolCall:
                // Tool calls display immediately without typewriter
                addAssistantMessage(response.content, mode: appState.currentMode)
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

    private func displayResponseWithTypewriter(_ response: HestiaResponse, mode: HestiaMode) async {
        let content = response.content

        // Start typewriter
        isTyping = true
        currentTypingText = ""

        // Animate character by character
        for (index, character) in content.enumerated() {
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

        addAssistantMessage(content, mode: mode)
    }

    private func addAssistantMessage(_ content: String, mode: HestiaMode) {
        let message = ConversationMessage(
            id: UUID().uuidString,
            role: .assistant,
            content: content,
            timestamp: Date(),
            mode: mode
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
