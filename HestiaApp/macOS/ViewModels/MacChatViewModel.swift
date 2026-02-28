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

            let response = try await client.sendMessage(text, sessionId: sessionId, forceLocal: wasForceLocal)

            if sessionId == nil {
                sessionId = response.sessionId
            }

            if let newMode = HestiaMode(rawValue: response.mode),
               newMode != appState.currentMode {
                appState.switchMode(to: newMode)
            }

            switch response.responseType {
            case .text, .clarification:
                await displayResponseWithTypewriter(response, mode: appState.currentMode)
            case .error:
                if let error = response.error {
                    throw HestiaError.from(responseError: error)
                }
            case .toolCall:
                addAssistantMessage(response.content, mode: appState.currentMode)
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

    // MARK: - Private Methods

    private func displayResponseWithTypewriter(_ response: HestiaResponse, mode: HestiaMode) async {
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
