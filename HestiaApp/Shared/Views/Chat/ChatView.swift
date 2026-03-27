import SwiftUI
import HestiaShared

/// Main chat interface view with wavelength particle background.
/// Idle state: full-screen wavelength + greeting at bottom.
/// Conversation state: wavelength in top 45%, messages in bottom half.
struct ChatView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var apiClientProvider: APIClientProvider
    @EnvironmentObject var authService: AuthService
    @StateObject private var viewModel = ChatViewModel()
    @StateObject private var voiceViewModel = VoiceInputViewModel()
    @StateObject private var conversationManager = VoiceConversationManager()
    @State private var conversationConfigured = false

    @State private var messageText = ""
    @State private var inputMode: ChatInputMode = .chat
    @State private var scrollViewContentSize: CGSize = .zero
    @State private var showVoiceReview = false
    @State private var showJournalSheet = false
    @State private var liveTranscriptId: String?
    @FocusState private var isInputFocused: Bool

    @Namespace private var wavelengthNamespace
    @State private var keyboardHeight: CGFloat = 0

    // MARK: - Computed State

    private var isIdleState: Bool {
        viewModel.messages.isEmpty && !viewModel.isLoading
    }

    private var wavelengthMode: WavelengthMode {
        if conversationManager.isActive {
            switch conversationManager.state {
            case .idle: return .idle
            case .listening: return .listening
            case .processing: return .thinking
            case .speaking: return .speaking
            }
        }
        if viewModel.isLoading || viewModel.isTyping { return .speaking }
        return .idle
    }

    private var greetingText: String {
        let hour = Calendar.current.component(.hour, from: Date())
        switch hour {
        case 5..<12: return "Good morning, Boss"
        case 12..<17: return "Good afternoon, Boss"
        case 17..<22: return "Good evening, Boss"
        default: return "Hello, Boss"
        }
    }

    // MARK: - Body

    var body: some View {
        GeometryReader { geo in
            ZStack {
                // Gradient background — matches Command/Settings tabs
                GradientBackground(mode: appState.currentMode)
                    .ignoresSafeArea()

                if isIdleState {
                    idleLayout(geo: geo)
                } else {
                    conversationLayout(geo: geo)
                }
            }
            .animation(.spring(response: 0.6, dampingFraction: 0.8), value: isIdleState)
            .onTapGesture {
                // Tap anywhere to dismiss keyboard
                isInputFocused = false
            }
        }
        .ignoresSafeArea(.keyboard)  // We handle keyboard manually
        .onChange(of: isIdleState) { _ in
            // Dismiss keyboard on state change
            isInputFocused = false
        }
        .onReceive(NotificationCenter.default.publisher(for: UIResponder.keyboardWillShowNotification)) { notification in
            if let frame = notification.userInfo?[UIResponder.keyboardFrameEndUserInfoKey] as? CGRect {
                withAnimation(.easeOut(duration: 0.25)) {
                    keyboardHeight = frame.height
                }
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: UIResponder.keyboardWillHideNotification)) { _ in
            withAnimation(.easeOut(duration: 0.25)) {
                keyboardHeight = 0
            }
        }
        .onAppear {
            if apiClientProvider.isReady {
                viewModel.configure(client: apiClientProvider.client)
                voiceViewModel.configure(client: apiClientProvider.client)
            }
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
        // Voice recording overlay
        .fullScreenCover(isPresented: .init(
            get: { voiceViewModel.phase == .recording && inputMode == .chat },
            set: { _ in }
        )) {
            VoiceRecordingOverlay(
                viewModel: voiceViewModel,
                onStop: {
                    Task {
                        await voiceViewModel.stopRecording()
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
        // Transcript review sheet
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
        // Voice conversation: update live transcript bubble
        .onChange(of: voiceViewModel.rawTranscript) { transcript in
            guard inputMode == .transcription, let id = liveTranscriptId else { return }
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

    // MARK: - Idle Layout (full-screen wavelength + greeting)

    private func idleLayout(geo: GeometryProxy) -> some View {
        ZStack {
            // Full-screen wavelength — explicit frame to prevent zero-size from GeometryReader
            HestiaWavelengthView(mode: wavelengthMode)
                .frame(width: geo.size.width, height: geo.size.height)
                .ignoresSafeArea()

            // Greeting + input at bottom
            VStack {
                Spacer()

                // Greeting text positioned above input
                if keyboardHeight == 0 {
                    VStack(spacing: 8) {
                        Text(greetingText)
                            .font(.system(size: 28, weight: .semibold))
                            .foregroundColor(.white)

                        Text("How can I help you today?")
                            .font(.system(size: 16))
                            .foregroundColor(.white.opacity(0.5))
                    }
                    .padding(.bottom, 100)
                }

                // Input bar — rides above keyboard like Messages
                inputBar
                    .padding(.bottom, keyboardHeight > 0 ? keyboardHeight - 34 : 0) // 34 = safe area bottom
            }
        }
    }

    // MARK: - Conversation Layout (wavelength top, messages bottom)

    private func conversationLayout(geo: GeometryProxy) -> some View {
        ZStack(alignment: .top) {
            // Wavelength covers top 50% — particles taper to nothing before the edge
            // Gradient background (from body) flows seamlessly below
            HestiaWavelengthView(mode: wavelengthMode, waveScale: 0.5)
                .frame(width: geo.size.width, height: geo.size.height * 0.5)
                .allowsHitTesting(false)

            // Amber gradient header with constellation + underline (above wavelength)
            HestiaHeaderView()
                .padding(.top, 44)
                .zIndex(1)

            // Chat area starts at ~39% — overlaps wavelength bottom with fade
            VStack(spacing: 0) {
                Spacer()
                    .frame(height: geo.size.height * 0.39)

                ZStack(alignment: .top) {
                    VStack(spacing: 0) {
                        // Messages
                        messageList

                        // Thinking indicator
                        if let stage = viewModel.currentStage, !viewModel.isTyping {
                            ThinkingIndicator(stage: stage)
                                .transition(.opacity)
                        }

                        // Typewriter text
                        if viewModel.isTyping, let typingText = viewModel.currentTypingText, !typingText.isEmpty {
                            typewriterView(text: typingText)
                                .transition(.move(edge: .bottom).combined(with: .opacity))
                        }

                        // Input bar — rides above keyboard like Messages
                        inputBar
                            .padding(.bottom, keyboardHeight > 0 ? keyboardHeight - 34 : 0)
                    }

                    // Tall, soft fade — messages dissolve into background
                    LinearGradient(
                        stops: [
                            .init(color: Color.black.opacity(0.85), location: 0),
                            .init(color: Color.black.opacity(0.5), location: 0.4),
                            .init(color: Color.black.opacity(0.15), location: 0.7),
                            .init(color: Color.clear, location: 1.0),
                        ],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                    .frame(height: 120)
                    .allowsHitTesting(false)
                }
            }
        }
    }

    // MARK: - Message List (Bottom Anchored)

    private var messageList: some View {
        GeometryReader { geometry in
            ScrollViewReader { proxy in
                ScrollView(.vertical, showsIndicators: true) {
                    VStack(spacing: 0) {
                        Spacer(minLength: 0)

                        LazyVStack(spacing: Spacing.md) {
                            ForEach(viewModel.messages) { message in
                                MessageBubble(message: message)
                                    .id(message.id)
                            }

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
                    .fill(Color.accent.opacity(0.5))
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
                .foregroundColor(.textPrimary)
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
                sendMessage()
            },
            onToggleLocal: {
                viewModel.forceLocal.toggle()
            },
            onStartVoice: {
                Task {
                    await voiceViewModel.startRecording()
                }
            },
            onStartConversation: {
                startVoiceConversation()
            }
        )
    }

    // MARK: - Helpers

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

    private func startVoiceConversation() {
        conversationManager.loadSettings()
        Task {
            await conversationManager.start()
        }
    }

    private func stopVoiceConversation() {
        Task {
            await conversationManager.stop()
        }
    }

    // MARK: - Voice Journal Mode

    private func startJournalRecording() {
        showJournalSheet = true
        Task {
            await voiceViewModel.startRecording()
        }
    }

    private func submitJournalEntry(transcript: String, duration: TimeInterval) {
        guard !transcript.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }

        let journalMessage = ConversationMessage(
            id: UUID().uuidString,
            role: .user,
            content: transcript,
            timestamp: Date(),
            mode: nil,
            inputMode: "journal"
        )
        viewModel.messages.append(journalMessage)

        let metadata = JournalMetadata(duration: duration)
        Task {
            await viewModel.sendJournalEntry(transcript, metadata: metadata, appState: appState)
        }
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
