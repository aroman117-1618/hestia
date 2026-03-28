import SwiftUI
import HestiaShared

struct MacChatPanelView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = MacChatViewModel()
    @State private var messageText: String = ""
    @State private var isAnimatingThinking = false

    var body: some View {
        VStack(spacing: 0) {
            // Chat window
            ScrollViewReader { proxy in
                ScrollView {
                    // Empty state — greeting opener
                    if viewModel.messages.isEmpty && !viewModel.isLoading {
                        VStack(spacing: MacSpacing.lg) {
                            Spacer()

                            if let image = appState.currentMode.avatarImage {
                                image
                                    .resizable()
                                    .scaledToFill()
                                    .frame(width: 48, height: 48)
                                    .clipShape(Circle())
                                    .overlay {
                                        Circle().strokeBorder(MacColors.amberAccent.opacity(0.5), lineWidth: 1)
                                    }
                            }

                            Text(chatGreeting)
                                .font(.system(size: 18, weight: .semibold))
                                .foregroundStyle(MacColors.textPrimaryAlt)

                            Text("What can I help you with?")
                                .font(.system(size: 13))
                                .foregroundStyle(MacColors.textSecondary)

                            Spacer()
                        }
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .padding(.horizontal, MacSpacing.xxl)
                    }

                    LazyVStack(spacing: 0) {
                        ForEach(viewModel.messages) { message in
                            MacMessageBubble(
                                message: message,
                                reactions: viewModel.reactions[message.id] ?? [],
                                onReaction: { reaction in
                                    viewModel.toggleReaction(reaction, for: message.id)
                                },
                                feedbackState: viewModel.feedbackState[message.id],
                                onFeedback: { messageId, feedback, note in
                                    Task {
                                        await viewModel.submitFeedback(
                                            messageId: messageId,
                                            feedback: feedback,
                                            note: note
                                        )
                                    }
                                },
                                canShowFeedback: viewModel.currentSessionId != nil
                            )
                            .id(message.id)
                        }

                        // Thinking indicator (before tokens start streaming)
                        if viewModel.isLoading && !viewModel.isTyping {
                            thinkingBubble
                        }

                        // Typing indicator (only when content has arrived)
                        if viewModel.isTyping, let typingText = viewModel.currentTypingText, !typingText.isEmpty {
                            typingBubble(typingText)
                        }
                    }
                    .padding(.horizontal, 15)
                }
                .onChange(of: viewModel.messages.count) {
                    if let lastId = viewModel.messages.last?.id {
                        withAnimation(.easeOut(duration: 0.2)) {
                            proxy.scrollTo(lastId, anchor: .bottom)
                        }
                    }
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

            // Error banner
            if viewModel.showError, let error = viewModel.errorState {
                errorBanner(error)
            }

            // Input bar
            MacMessageInputBar(
                messageText: $messageText,
                hasMessages: !viewModel.messages.isEmpty,
                sessionId: viewModel.currentSessionId,
                onMoveToBackground: { sessionId in
                    await viewModel.moveSessionToBackground(
                        sessionId: sessionId,
                        appState: appState
                    )
                },
                onNewSession: {
                    Task {
                        await viewModel.startNewConversation(appState: appState)
                    }
                }
            ) {
                let text = messageText
                messageText = ""
                Task {
                    await viewModel.sendMessage(text, appState: appState)
                }
            }
        }
        .frame(minWidth: 320)
        .background(chatBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
        .overlay(alignment: .leading) {
            // Divider grabber indicator
            VStack(spacing: 3) {
                ForEach(0..<3, id: \.self) { _ in
                    Circle()
                        .fill(MacColors.textSecondary.opacity(0.5))
                        .frame(width: 4, height: 4)
                }
            }
            .padding(.leading, 4)
        }
        .task {
            // Empty state — user generates the first message
        }
        .onReceive(NotificationCenter.default.publisher(for: .hestiaSendToChat)) { notification in
            if let context = notification.userInfo?["context"] as? String {
                messageText = context
            }
        }
    }

    // MARK: - Thinking Bubble

    private var thinkingBubble: some View {
        HStack(alignment: .top, spacing: MacSpacing.sm) {
            aiAvatar

            HStack(spacing: 4) {
                ForEach(0..<3, id: \.self) { index in
                    Circle()
                        .fill(MacColors.amberAccent)
                        .frame(width: 6, height: 6)
                        .opacity(thinkingDotOpacity(for: index))
                        .animation(
                            .easeInOut(duration: 0.6)
                            .repeatForever()
                            .delay(Double(index) * 0.2),
                            value: isAnimatingThinking
                        )
                }
            }
            .padding(.horizontal, MacSpacing.md)
            .padding(.vertical, MacSpacing.sm)
            .background(MacColors.aiBubbleBackground)
            .clipShape(RoundedRectangle(cornerRadius: 12))

            Spacer()
        }
        .padding(.leading, 4)
        .transition(.opacity.combined(with: .move(edge: .bottom)))
        .onAppear { isAnimatingThinking = true }
        .onDisappear { isAnimatingThinking = false }
    }

    private func thinkingDotOpacity(for index: Int) -> Double {
        isAnimatingThinking ? 1.0 : 0.3
    }

    // MARK: - Typing Bubble

    private func typingBubble(_ text: String) -> some View {
        HStack(alignment: .top, spacing: MacSpacing.lg) {
            aiAvatar
            VStack(alignment: .leading, spacing: MacSpacing.xs) {
                Text(appState.currentMode.displayName)
                    .font(MacTypography.senderLabel)
                    .foregroundStyle(MacColors.textSender)
                    .padding(.horizontal, MacSpacing.sm)
                Text(text)
                    .font(MacTypography.chatMessage)
                    .foregroundStyle(MacColors.textPrimary)
                    .padding(.horizontal, MacSpacing.lg)
                    .padding(.vertical, MacSpacing.md)
                    .background(MacColors.aiBubbleBackground)
                    .clipShape(UnevenRoundedRectangle(
                        topLeadingRadius: MacCornerRadius.chatBubble,
                        bottomLeadingRadius: 0,
                        bottomTrailingRadius: MacCornerRadius.chatBubble,
                        topTrailingRadius: MacCornerRadius.chatBubble
                    ))
            }
            Spacer(minLength: 96)
        }
        .padding(.vertical, MacSpacing.sm)
    }

    private var aiAvatar: some View {
        Group {
            if let image = appState.currentMode.avatarImage {
                image
                    .resizable()
                    .scaledToFill()
            } else {
                Circle()
                    .fill(MacColors.aiAvatarBackground)
                    .overlay {
                        Text(appState.currentMode.displayName.prefix(1))
                            .font(.system(size: MacSize.chatAvatarSize * 0.45, weight: .bold))
                            .foregroundStyle(MacColors.amberAccent)
                    }
            }
        }
        .frame(width: MacSize.chatAvatarSize, height: MacSize.chatAvatarSize)
        .clipShape(Circle())
        .overlay {
            Circle().strokeBorder(MacColors.aiAvatarBorder, lineWidth: 1)
        }
    }

    // MARK: - Error Banner

    private func errorBanner(_ error: HestiaError) -> some View {
        HStack {
            Image(systemName: "exclamationmark.triangle")
                .foregroundStyle(MacColors.healthRed)
            Text(error.localizedDescription)
                .font(MacTypography.metadata)
                .foregroundStyle(MacColors.textSecondary)
                .lineLimit(1)
            Spacer()
            Button("Dismiss") { viewModel.dismissError() }
                .font(MacTypography.metadata)
                .buttonStyle(.hestia)
                .foregroundStyle(MacColors.amberAccent)
        }
        .padding(.horizontal, MacSpacing.md)
        .padding(.vertical, MacSpacing.sm)
        .background(MacColors.healthRedBg)
    }

    // MARK: - Greeting

    private var chatGreeting: String {
        let hour = Calendar.current.component(.hour, from: Date())
        if hour < 12 { return "Good morning, Andrew" }
        else if hour < 17 { return "Good afternoon, Andrew" }
        else { return "Good evening, Andrew" }
    }

    // MARK: - Chat Background

    private var chatBackground: some View {
        ZStack {
            MacColors.windowBackground
            RadialGradient(
                colors: [
                    MacColors.panelBackground,
                    MacColors.amberDark.opacity(0.15)
                ],
                center: .center,
                startRadius: 0,
                endRadius: 400
            )
            .opacity(0.2)
            MacColors.sidebarBackground.opacity(0.15)
        }
    }
}
