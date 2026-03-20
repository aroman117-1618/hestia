import SwiftUI
import HestiaShared
import Combine

/// macOS chat ViewModel — adapted from iOS ChatViewModel.
/// Removes voice recording, adds per-message reactions state.
@MainActor
class MacChatViewModel: ObservableObject {
    // MARK: - Published State

    @Published var messages: [ConversationMessage] = []
    @Published var isLoading: Bool = false
    @Published var isTyping: Bool = false
    @Published var currentTypingText: String?
    @Published var errorState: HestiaError?
    @Published var showError: Bool = false
    @Published var modeSwitchTrigger: Bool = false
    @Published var forceLocal: Bool = false

    /// Per-message reaction state: [messageId: Set of reaction names]
    @Published var reactions: [String: Set<String>] = [:]

    /// Per-message outcome feedback state: [messageId: feedback type ("positive"/"negative")]
    @Published var feedbackState: [String: String] = [:]

    // MARK: - Public Accessors

    /// Current session ID, exposed for background session support.
    var currentSessionId: String? { sessionId }

    // MARK: - Private State

    private var client: HestiaClientProtocol
    private var sessionId: String?
    private var cancellables = Set<AnyCancellable>()
    private var isConfigured: Bool = false
    private let typewriterSpeed: Double = 0.03

    // MARK: - Initialization

    init(client: HestiaClientProtocol = APIClient.shared) {
        self.client = client
        self.isConfigured = true
    }

    /// Configure with a real API client when available
    func configure(client: HestiaClientProtocol) {
        guard !isConfigured else { return }
        self.client = client
        self.isConfigured = true
    }

    // MARK: - Public Methods

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

    func sendMessage(_ text: String, appState: AppState) async {
        guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }

        errorState = nil
        showError = false

        // Check for mode invocation
        if let detectedMode = appState.detectModeFromText(text) {
            if detectedMode != appState.currentMode {
                await switchMode(to: detectedMode, appState: appState)
            }
        }

        let userMessage = ConversationMessage.userMessage(text)
        messages.append(userMessage)
        isLoading = true

        do {
            let wasForceLocal = forceLocal
            forceLocal = false

            // Try streaming first, fall back to REST
            do {
                try await sendMessageStreaming(text, sessionId: sessionId, forceLocal: wasForceLocal, appState: appState)
            } catch {
                #if DEBUG
                print("[MacChatVM] Streaming failed, falling back to REST: \(error)")
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

    func switchMode(to mode: HestiaMode, appState: AppState) async {
        guard mode != appState.currentMode else { return }

        do {
            try await client.switchMode(to: mode)
            modeSwitchTrigger = true
            appState.switchMode(to: mode)

            DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) { [weak self] in
                self?.modeSwitchTrigger = false
            }

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

    func startNewConversation(appState: AppState) async {
        do {
            sessionId = try await client.createSession(mode: appState.currentMode)
            messages.removeAll()
            reactions.removeAll()
            feedbackState.removeAll()
            loadInitialGreeting(mode: appState.currentMode)
        } catch {
            handleError(.unknown("Failed to create session"))
        }
    }

    func dismissError() {
        showError = false
        errorState = nil
    }

    // MARK: - Reactions

    func toggleReaction(_ reaction: String, for messageId: String) {
        var set = reactions[messageId] ?? []
        if set.contains(reaction) {
            set.remove(reaction)
        } else {
            set.insert(reaction)
        }
        reactions[messageId] = set
    }

    // MARK: - Outcome Feedback

    /// Submit feedback for a message via the outcomes API.
    /// Looks up the outcome by session + message, then submits feedback.
    func submitFeedback(messageId: String, feedback: String, note: String?) async {
        // Optimistically update UI
        feedbackState[messageId] = feedback

        do {
            // 1. Get outcomes for this session to find the outcome_id
            guard let sid = sessionId else {
                #if DEBUG
                print("[MacChatVM] No session ID — cannot submit feedback")
                #endif
                return
            }

            let outcomes = try await APIClient.shared.getOutcomes(sessionId: sid)

            // Find the outcome matching this message_id
            guard let outcome = outcomes.outcomes.first(where: { $0.messageId == messageId }) else {
                #if DEBUG
                print("[MacChatVM] No outcome found for message \(messageId)")
                #endif
                return
            }

            // 2. Submit feedback
            _ = try await APIClient.shared.submitOutcomeFeedback(
                outcomeId: outcome.id,
                feedback: feedback,
                note: note
            )

            #if DEBUG
            print("[MacChatVM] Feedback submitted: \(feedback) for outcome \(outcome.id)")
            #endif
        } catch {
            // Revert optimistic update on failure
            feedbackState.removeValue(forKey: messageId)
            #if DEBUG
            print("[MacChatVM] Feedback submission failed: \(error)")
            #endif
        }
    }

    // MARK: - Background Session

    /// Move the current session to a background order, then start a new session.
    func moveSessionToBackground(sessionId: String, appState: AppState) async {
        do {
            _ = try await APIClient.shared.createOrderFromSession(sessionId: sessionId)

            // Start a fresh session
            await startNewConversation(appState: appState)
        } catch {
            handleError(.unknown("Failed to move session to background"))
        }
    }

    // MARK: - Private Methods

    /// Send via SSE streaming — tokens appear in real-time.
    private func sendMessageStreaming(
        _ text: String,
        sessionId: String?,
        forceLocal: Bool,
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

        // Don't set isTyping yet — let thinking dots show (isLoading && !isTyping)
        // isTyping transitions to true on first token arrival

        defer {
            isTyping = false
            currentTypingText = nil
        }

        let stream = client.sendMessageStream(text, sessionId: sessionId, forceLocal: forceLocal)

        for try await event in stream {
            switch event {
            case .token(let content, _):
                // Start typing indicator on first token
                if !isTyping {
                    isTyping = true
                    currentTypingText = ""
                }
                currentTypingText = (currentTypingText ?? "") + content
                messages[messageIndex].content += content

            case .clearStream:
                currentTypingText = ""
                messages[messageIndex].content = ""

            case .toolResult(_, _, _, _):
                break  // Tool results followed by synthesis tokens

            case .status(_, let detail):
                #if DEBUG
                print("[MacChatVM] \(detail)")
                #endif

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

        if messages.count > Constants.Limits.maxConversationHistory {
            messages.removeFirst(messages.count - Constants.Limits.maxConversationHistory)
        }
    }

    /// Fallback: send via REST with typewriter effect.
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
        isTyping = true
        currentTypingText = ""

        for character in content {
            currentTypingText?.append(character)
            let delay = UInt64(typewriterSpeed * 1_000_000_000)
            try? await Task.sleep(nanoseconds: delay)
            if isLoading { break }
        }

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
        case .tia: return "Back to daily ops mode. What do you need?"
        case .mira: return "Switching to learning mode. What would you like to explore?"
        case .olly: return "Project mode activated. Let's focus. What are we working on?"
        }
    }
}
