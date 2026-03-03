import SwiftUI
import HestiaShared

struct MacChatPanelView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = MacChatViewModel()
    @State private var messageText: String = ""

    var body: some View {
        VStack(spacing: MacSpacing.md) {
            // Agent tab bar
            agentTabBar

            // Chat window
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 0) {
                        ForEach(viewModel.messages) { message in
                            MacMessageBubble(
                                message: message,
                                reactions: viewModel.reactions[message.id] ?? [],
                                onReaction: { reaction in
                                    viewModel.toggleReaction(reaction, for: message.id)
                                }
                            )
                            .id(message.id)
                        }

                        // Typing indicator
                        if viewModel.isTyping, let typingText = viewModel.currentTypingText {
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
            MacMessageInputBar(messageText: $messageText) {
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
            viewModel.loadInitialGreeting(mode: appState.currentMode)
        }
    }

    // MARK: - Agent Tab Bar

    private var agentTabBar: some View {
        HStack(spacing: MacSpacing.md) {
            // New session button (left side)
            Button {
                Task {
                    await viewModel.startNewConversation(appState: appState)
                }
            } label: {
                Image(systemName: "plus")
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(MacColors.textSecondary)
                    .frame(width: 28, height: 28)
                    .background(MacColors.textPrimary.opacity(0.06))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            }
            .buttonStyle(.hestiaIcon)
            .accessibilityLabel("New chat session")
            .hoverCursor(.pointingHand)

            // Agent tabs (active agent prominent, others faded)
            HStack(spacing: 5) {
                agentTab(mode: .tia, isActive: appState.currentMode == .tia)
                agentTab(mode: .mira, isActive: appState.currentMode == .mira)
                agentTab(mode: .olly, isActive: appState.currentMode == .olly)
            }

            Spacer()

            // Collapse button (Option A — visible in-panel toggle)
            HeaderChatToggle()
        }
        .padding(.vertical, 2)
        .frame(height: 69)
        .overlay(alignment: .bottom) {
            MacColors.primaryBorder.frame(height: 1)
        }
        .padding(.horizontal, MacSpacing.lg)
    }

    private func agentTab(mode: HestiaMode, isActive: Bool) -> some View {
        Button {
            Task {
                await viewModel.switchMode(to: mode, appState: appState)
            }
        } label: {
            HStack(spacing: MacSpacing.sm) {
                // Agent avatar (centered, prominent for active)
                agentTabAvatar(for: mode)
                    .frame(
                        width: isActive ? MacSize.agentTabAvatarSize : MacSize.agentTabAvatarSize - 2,
                        height: isActive ? MacSize.agentTabAvatarSize : MacSize.agentTabAvatarSize - 2
                    )

                Text(mode.displayName)
                    .font(MacTypography.label)
                    .foregroundStyle(isActive ? MacColors.textPrimaryAlt : MacColors.textSecondary)
            }
            .padding(.horizontal, MacSpacing.sm)
            .padding(.vertical, MacSpacing.xs)
            .background(isActive ? MacColors.activeTabBackground : Color.clear)
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.tab))
            .opacity(isActive ? 1 : 0.5)
        }
        .buttonStyle(.hestia)
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

    private func agentTabAvatar(for mode: HestiaMode) -> some View {
        Group {
            if let image = mode.avatarImage {
                image
                    .resizable()
                    .scaledToFill()
            } else {
                Circle()
                    .fill(MacColors.aiAvatarBackground)
                    .overlay {
                        Text(mode.displayName.prefix(1))
                            .font(.system(size: MacSize.agentTabAvatarSize * 0.45, weight: .bold))
                            .foregroundStyle(MacColors.amberAccent)
                    }
            }
        }
        .frame(width: MacSize.agentTabAvatarSize, height: MacSize.agentTabAvatarSize)
        .clipShape(Circle())
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

    // MARK: - Chat Background

    private var chatBackground: some View {
        ZStack {
            MacColors.windowBackground
            RadialGradient(
                colors: [
                    Color(red: 28/255, green: 12/255, blue: 2/255),
                    Color(red: 225/255, green: 113/255, blue: 0).opacity(0.15)
                ],
                center: .center,
                startRadius: 0,
                endRadius: 400
            )
            .opacity(0.2)
            Color.black.opacity(0.15)
        }
    }
}
