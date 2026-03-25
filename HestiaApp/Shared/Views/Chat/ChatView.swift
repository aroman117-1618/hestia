import SwiftUI
import HestiaShared

/// Main chat interface view with bottom-anchored messages (like iMessage)
struct ChatView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var apiClientProvider: APIClientProvider
    @EnvironmentObject var authService: AuthService
    @StateObject private var viewModel = ChatViewModel()
    @StateObject private var voiceViewModel = VoiceInputViewModel()
    @StateObject private var conversationManager = VoiceConversationManager()
    @State private var showConversationOverlay = false
    @State private var conversationConfigured = false

    @State private var messageText = ""
    @State private var inputMode: ChatInputMode = .chat
    @State private var avatarPosition: CGPoint = .zero
    @State private var scrollViewContentSize: CGSize = .zero
    @State private var showVoiceReview = false
    @State private var showJournalSheet = false
    @State private var liveTranscriptId: String?
    @FocusState private var isInputFocused: Bool

    var body: some View {
        ZStack {
            // Background gradient with mode transition
            GradientBackground(mode: appState.currentMode)
                .animation(.modeSwitch, value: appState.currentMode)
                .ignoresSafeArea()

            // Ripple effect overlay - allowsHitTesting(false) ensures it doesn't block touches
            if viewModel.modeSwitchTrigger {
                Circle()
                    .fill(appState.currentMode.gradientColors.first?.opacity(0.3) ?? Color.white.opacity(0.2))
                    .frame(width: 20, height: 20)
                    .position(avatarPosition)
                    .modifier(ExpandingRipple())
                    .allowsHitTesting(false)
            }

            VStack(spacing: 0) {
                // Header
                header
                    .background(
                        GeometryReader { headerGeo in
                            Color.clear.onAppear {
                                // Calculate avatar center position
                                let frame = headerGeo.frame(in: .global)
                                avatarPosition = CGPoint(
                                    x: Spacing.lg + Size.Avatar.medium / 2,
                                    y: frame.minY + frame.height / 2
                                )
                            }
                        }
                    )

                // Messages - bottom anchored
                messageList

                // Thinking indicator (visible reasoning stages)
                if let stage = viewModel.currentStage, !viewModel.isTyping {
                    ThinkingIndicator(stage: stage)
                        .transition(.opacity)
                }

                // Typewriter text (if typing, only when content has arrived)
                if viewModel.isTyping, let typingText = viewModel.currentTypingText, !typingText.isEmpty {
                    typewriterView(text: typingText)
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                }

                // Input bar - always at bottom
                inputBar
            }

            // Voice conversation overlay
            if showConversationOverlay {
                VoiceConversationOverlay(
                    manager: conversationManager,
                    onStop: {
                        stopVoiceConversation()
                    }
                )
            }
        }
        .onAppear {
            // Configure with real API client when available
            if apiClientProvider.isReady {
                viewModel.configure(client: apiClientProvider.client)
                voiceViewModel.configure(client: apiClientProvider.client)
            }
            // Empty state — user generates the first message
            if !conversationConfigured {
                conversationManager.configure(
                    speechService: voiceViewModel.speechService,
                    chatViewModel: viewModel,
                    appState: appState
                )
                conversationConfigured = true
            }
        }
        .onChange(of: apiClientProvider.isReady) { isReady in
            // Also configure when client becomes ready later
            if isReady {
                viewModel.configure(client: apiClientProvider.client)
                voiceViewModel.configure(client: apiClientProvider.client)
            }
        }
        .alert("Error", isPresented: $viewModel.showError) {
            if viewModel.errorState?.isRetryable == true {
                Button("Retry") {
                    Task {
                        await viewModel.retryLastMessage(appState: appState)
                    }
                }
            }
            // Handle unauthorized error - clear token and re-register
            if case .unauthorized = viewModel.errorState {
                Button("Re-register Device") {
                    authService.unregisterDevice()
                }
            }
            Button("OK", role: .cancel) {
                viewModel.dismissError()
            }
        } message: {
            Text(viewModel.errorState?.userMessage ?? "An error occurred")
        }
        // Voice recording overlay — only for journal/chat modes (voice conversation is inline)
        .fullScreenCover(isPresented: .init(
            get: { voiceViewModel.phase == .recording && inputMode != .voice },
            set: { _ in }
        )) {
            VoiceRecordingOverlay(
                viewModel: voiceViewModel,
                onStop: {
                    Task {
                        await voiceViewModel.stopRecording()
                        // Brief delay lets fullScreenCover dismiss before sheet presents
                        try? await Task.sleep(nanoseconds: 300_000_000)
                        showVoiceReview = true
                    }
                },
                onCancel: {
                    voiceViewModel.cancel()
                }
            )
            .background(ClearBackgroundView())
        }
        // Transcript review sheet (journal/chat modes only)
        .sheet(isPresented: $showVoiceReview) {
            TranscriptReviewView(
                viewModel: voiceViewModel,
                onAccept: { transcript in
                    showVoiceReview = false
                    sendVoiceTranscript(transcript)
                },
                onCancel: {
                    showVoiceReview = false
                    voiceViewModel.cancel()
                }
            )
        }
        // Voice conversation: update live transcript bubble as speech is recognized
        .onChange(of: voiceViewModel.rawTranscript) { transcript in
            guard inputMode == .voice, let id = liveTranscriptId else { return }
            if let index = viewModel.messages.firstIndex(where: { $0.id == id }) {
                viewModel.messages[index].content = transcript
            }
        }
        // Voice journal sheet
        .sheet(isPresented: $showJournalSheet) {
            VoiceJournalView(
                voiceViewModel: voiceViewModel,
                onSubmit: { transcript, duration in
                    showJournalSheet = false
                    submitJournalEntry(transcript: transcript, duration: duration)
                },
                onCancel: {
                    showJournalSheet = false
                    voiceViewModel.cancel()
                }
            )
        }
        // Voice error alert
        .alert("Voice Error", isPresented: $voiceViewModel.showError) {
            Button("OK", role: .cancel) {
                voiceViewModel.error = nil
                voiceViewModel.showError = false
            }
        } message: {
            Text(voiceViewModel.error ?? "An error occurred")
        }
    }

    // MARK: - Header

    private var header: some View {
        HStack(alignment: .center, spacing: Spacing.md) {
            // Avatar
            avatarImage
                .frame(width: Size.Avatar.medium, height: Size.Avatar.medium)
                .clipShape(Circle())

            VStack(alignment: .leading, spacing: Spacing.xs) {
                Text(greetingText)
                    .greetingStyle()
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)

                if voiceViewModel.phase == .recording && inputMode == .voice {
                    // Voice conversation active — show listening indicator
                    HStack(spacing: Spacing.xs) {
                        Circle()
                            .fill(ChatInputMode.voice.color)
                            .frame(width: 6, height: 6)
                        Text("Listening...")
                            .font(.caption)
                            .foregroundColor(ChatInputMode.voice.color)
                        Text(formatDuration(voiceViewModel.recordingDuration))
                            .font(.caption.monospacedDigit())
                            .foregroundColor(.white.opacity(0.5))
                    }
                } else {
                    ModeIndicator(mode: appState.currentMode) {
                        // Mode tap action - show mode picker
                    }
                }
            }

            Spacer()

            // Menu button
            Menu {
                ForEach(HestiaMode.allCases) { mode in
                    Button {
                        Task {
                            await viewModel.switchMode(to: mode, appState: appState)
                        }
                    } label: {
                        Label(mode.displayName, systemImage: mode == appState.currentMode ? "checkmark" : "")
                    }
                }

                Divider()

                Button {
                    Task {
                        await viewModel.startNewConversation(appState: appState)
                    }
                } label: {
                    Label("New Conversation", systemImage: "plus.message")
                }
            } label: {
                Image(systemName: "ellipsis.circle.fill")
                    .font(.system(size: 24))
                    .foregroundColor(.white.opacity(0.7))
            }
            .accessibilityLabel("Options menu")
        }
        .padding(.horizontal, Spacing.lg)
        .padding(.vertical, Spacing.md)
    }

    // MARK: - Avatar

    @ViewBuilder
    private var avatarImage: some View {
        if let image = appState.currentMode.avatarImage {
            // Use custom profile image
            image
                .resizable()
                .scaledToFill()
        } else {
            // Fallback to letter placeholder
            Circle()
                .fill(Color.white.opacity(0.2))
                .overlay(
                    Text(appState.currentMode.displayName.prefix(1))
                        .font(.system(size: 24, weight: .bold))
                        .foregroundColor(.white)
                )
        }
    }

    // MARK: - Message List (Bottom Anchored)

    private var messageList: some View {
        GeometryReader { geometry in
            ScrollViewReader { proxy in
                ScrollView(.vertical, showsIndicators: true) {
                    VStack(spacing: 0) {
                        // Spacer pushes content to bottom when there are few messages
                        Spacer(minLength: 0)

                        // Messages container
                        LazyVStack(spacing: Spacing.md) {
                            ForEach(viewModel.messages) { message in
                                MessageBubble(message: message)
                                    .id(message.id)
                            }

                            // Loading indicator
                            if viewModel.isLoading && !viewModel.isTyping {
                                loadingIndicator
                                    .id("loading")
                            }
                        }
                        .padding(.vertical, Spacing.lg)
                        .padding(.horizontal, Spacing.xs)
                    }
                    .frame(minHeight: geometry.size.height, alignment: .bottom)
                    .background(
                        GeometryReader { contentGeo in
                            Color.clear.preference(
                                key: ScrollViewContentSizeKey.self,
                                value: contentGeo.size
                            )
                        }
                    )
                }
                .onPreferenceChange(ScrollViewContentSizeKey.self) { size in
                    scrollViewContentSize = size
                }
                .onChange(of: viewModel.messages.count) { _ in
                    scrollToBottom(proxy: proxy, animated: true)
                }
                .onChange(of: viewModel.isLoading) { _ in
                    scrollToBottom(proxy: proxy, animated: true)
                }
                .onAppear {
                    // Scroll to bottom on initial load
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                        scrollToBottom(proxy: proxy, animated: false)
                    }
                }
            }
        }
    }

    private var loadingIndicator: some View {
        HStack(spacing: 4) {
            ForEach(0..<3) { index in
                Circle()
                    .fill(Color.white.opacity(0.5))
                    .frame(width: 8, height: 8)
                    .modifier(BouncingDot(delay: Double(index) * 0.15))
            }
        }
        .padding(Spacing.md)
        .background(Color.assistantBubbleBackground)
        .cornerRadius(CornerRadius.standard)
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, Spacing.md)
    }

    // MARK: - Typewriter View

    private func typewriterView(text: String) -> some View {
        HStack {
            Text(text)
                .font(.messageBody)
                .foregroundColor(.white)
                .padding(Spacing.md)
                .background(Color.assistantBubbleBackground)
                .cornerRadius(CornerRadius.standard)

            Spacer()
        }
        .padding(.horizontal, Spacing.md)
        .padding(.bottom, Spacing.sm)
    }

    // MARK: - Input Bar

    private var inputBar: some View {
        ChatInputBar(
            messageText: $messageText,
            inputMode: $inputMode,
            isInputFocused: $isInputFocused,
            isLoading: viewModel.isLoading,
            isRecording: voiceViewModel.phase == .recording,
            audioLevel: voiceViewModel.audioLevel,
            forceLocal: viewModel.forceLocal,
            currentModeName: appState.currentMode.displayName,
            onSend: { _ in
                if inputMode == .voice && voiceViewModel.phase == .recording {
                    // Stop recording and send transcript
                    stopVoiceConversation()
                } else {
                    sendMessage()
                }
            },
            onToggleLocal: {
                viewModel.forceLocal.toggle()
            },
            onStartVoice: {
                if inputMode == .voice {
                    startVoiceConversation()
                } else if inputMode == .journal {
                    startJournalRecording()
                } else {
                    Task {
                        await voiceViewModel.startRecording()
                    }
                }
            }
        )
    }

    // MARK: - Helpers

    private func formatDuration(_ duration: TimeInterval) -> String {
        let minutes = Int(duration) / 60
        let seconds = Int(duration) % 60
        return String(format: "%d:%02d", minutes, seconds)
    }

    private var greetingText: String {
        let hour = Calendar.current.component(.hour, from: Date())
        if hour < 12 {
            return "Morning, Boss."
        } else if hour < 17 {
            return "Afternoon, Boss."
        } else {
            return "Evening, Boss."
        }
    }

    private var canSend: Bool {
        !messageText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
        !viewModel.isLoading
    }

    private func sendMessage() {
        guard canSend else { return }

        let text = messageText
        messageText = ""
        isInputFocused = false

        Task {
            await viewModel.sendMessage(text, appState: appState)
        }
    }

    private func sendVoiceTranscript(_ transcript: String) {
        guard !transcript.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        Task {
            await viewModel.sendMessage(transcript, appState: appState)
        }
    }

    // MARK: - Voice Conversation Mode

    /// Start inline voice conversation — delegates to VoiceConversationManager.
    private func startVoiceConversation() {
        showConversationOverlay = true
        Task {
            await conversationManager.start()
        }
    }

    // MARK: - Voice Journal Mode

    /// Open the journal sheet and start recording.
    private func startJournalRecording() {
        showJournalSheet = true
        Task {
            await voiceViewModel.startRecording()
        }
    }

    /// Submit a completed journal entry as a chat message with Artemis routing metadata.
    private func submitJournalEntry(transcript: String, duration: TimeInterval) {
        guard !transcript.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }

        // Add a condensed journal message to the chat
        let journalMessage = ConversationMessage(
            id: UUID().uuidString,
            role: .user,
            content: transcript,
            timestamp: Date(),
            mode: nil,
            inputMode: "journal"
        )
        viewModel.messages.append(journalMessage)

        // Send with journal metadata for Artemis routing
        let metadata = JournalMetadata(duration: duration)
        Task {
            await viewModel.sendJournalEntry(transcript, metadata: metadata, appState: appState)
        }
    }

    /// Stop voice conversation — delegates to VoiceConversationManager.
    private func stopVoiceConversation() {
        Task {
            await conversationManager.stop()
        }
        showConversationOverlay = false
    }

    private func scrollToBottom(proxy: ScrollViewProxy, animated: Bool) {
        let targetId: String?

        if viewModel.isLoading && !viewModel.isTyping {
            targetId = "loading"
        } else if let lastId = viewModel.messages.last?.id {
            targetId = lastId
        } else {
            targetId = nil
        }

        guard let id = targetId else { return }

        if animated {
            withAnimation(.hestiaStandard) {
                proxy.scrollTo(id, anchor: .bottom)
            }
        } else {
            proxy.scrollTo(id, anchor: .bottom)
        }
    }
}

// MARK: - Preference Key for Content Size

private struct ScrollViewContentSizeKey: PreferenceKey {
    nonisolated(unsafe) static var defaultValue: CGSize = .zero
    static func reduce(value: inout CGSize, nextValue: () -> CGSize) {
        value = nextValue()
    }
}

// MARK: - Clear Background (for fullScreenCover transparency)

private struct ClearBackgroundView: UIViewRepresentable {
    func makeUIView(context: Context) -> UIView {
        let view = UIView()
        DispatchQueue.main.async {
            view.superview?.superview?.backgroundColor = .clear
        }
        return view
    }

    func updateUIView(_ uiView: UIView, context: Context) {}
}

// MARK: - Bouncing Dot Animation

private struct BouncingDot: ViewModifier {
    let delay: Double
    @State private var isAnimating = false

    func body(content: Content) -> some View {
        content
            .offset(y: isAnimating ? -5 : 0)
            .animation(
                Animation.easeInOut(duration: 0.4)
                    .repeatForever(autoreverses: true)
                    .delay(delay),
                value: isAnimating
            )
            .onAppear {
                isAnimating = true
            }
    }
}

// MARK: - Preview

struct ChatView_Previews: PreviewProvider {
    static var previews: some View {
        ChatView()
            .environmentObject(AppState())
            .environmentObject(APIClientProvider())
            .environmentObject(AuthService())
    }
}
