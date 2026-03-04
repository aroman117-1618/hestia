import SwiftUI
import HestiaShared

// MARK: - Floating Avatar View

/// Centered avatar above the message scroll area showing the active agent.
/// Animates between user and agent avatars during conversation flow,
/// with a pulsing glow ring while the agent is generating a response.
struct FloatingAvatarView: View {
    let currentMode: HestiaMode
    let isTyping: Bool
    let isLoading: Bool
    let onModePick: (HestiaMode) -> Void
    let onNewSession: () -> Void

    @State private var showingUser = false
    @State private var glowOpacity: Double = 0.2
    @State private var showModePicker = false

    var body: some View {
        HStack(spacing: MacSpacing.md) {
            // New session button (left side)
            Button {
                onNewSession()
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

            Spacer()

            // Central avatar + name
            VStack(spacing: MacSpacing.xs) {
                ZStack {
                    // Glow ring (visible when typing)
                    if isTyping {
                        Circle()
                            .strokeBorder(
                                MacColors.amberAccent.opacity(glowOpacity),
                                lineWidth: 3
                            )
                            .frame(width: 68, height: 68)
                    }

                    // Avatar content with cross-dissolve
                    avatarContent
                        .frame(width: 60, height: 60)
                        .clipShape(Circle())
                        .overlay {
                            Circle().strokeBorder(MacColors.aiAvatarBorder, lineWidth: 1.5)
                        }
                        .animation(.easeInOut(duration: 0.3), value: showingUser)
                }

                // Agent name + mode indicator
                HStack(spacing: MacSpacing.xs) {
                    Text(currentMode.displayName)
                        .font(MacTypography.labelMedium)
                        .foregroundStyle(MacColors.textPrimaryAlt)

                    // Mode picker dots
                    Button {
                        showModePicker.toggle()
                    } label: {
                        Image(systemName: "chevron.down")
                            .font(.system(size: 9, weight: .bold))
                            .foregroundStyle(MacColors.textSecondary)
                    }
                    .buttonStyle(.hestiaIcon)
                    .popover(isPresented: $showModePicker, arrowEdge: .bottom) {
                        modePickerPopover
                    }
                    .accessibilityLabel("Switch agent mode")
                }
            }

            Spacer()

            // Collapse button (right side)
            HeaderChatToggle()
        }
        .padding(.vertical, MacSpacing.sm)
        .frame(height: 90)
        .overlay(alignment: .bottom) {
            MacColors.primaryBorder.frame(height: 1)
        }
        .padding(.horizontal, MacSpacing.lg)
        .onChange(of: isLoading) { _, newValue in
            if newValue {
                // User just sent — show user avatar briefly
                showingUser = true
            }
        }
        .onChange(of: isTyping) { _, newValue in
            if newValue {
                // Agent started typing — cross-dissolve back to agent
                withAnimation(.easeInOut(duration: 0.3)) {
                    showingUser = false
                }
                startGlowPulse()
            } else {
                stopGlowPulse()
            }
        }
    }

    // MARK: - Avatar Content

    @ViewBuilder
    private var avatarContent: some View {
        if showingUser {
            // User avatar
            Circle()
                .fill(Color.gray.opacity(0.3))
                .overlay {
                    Image(systemName: "person.fill")
                        .font(.system(size: 22))
                        .foregroundStyle(MacColors.textSecondary)
                }
                .transition(.opacity)
        } else {
            // Agent avatar
            agentAvatarImage(for: currentMode)
                .transition(.opacity)
        }
    }

    private func agentAvatarImage(for mode: HestiaMode) -> some View {
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
                            .font(.system(size: 24, weight: .bold))
                            .foregroundStyle(MacColors.amberAccent)
                    }
            }
        }
    }

    // MARK: - Mode Picker Popover

    private var modePickerPopover: some View {
        VStack(spacing: MacSpacing.xs) {
            ForEach(HestiaMode.allCases) { mode in
                Button {
                    showModePicker = false
                    onModePick(mode)
                } label: {
                    HStack(spacing: MacSpacing.sm) {
                        // Mode dot
                        Circle()
                            .fill(MacColors.accentColor(for: mode))
                            .frame(width: 8, height: 8)

                        Text(mode.displayName)
                            .font(MacTypography.label)
                            .foregroundStyle(
                                mode == currentMode
                                    ? MacColors.textPrimaryAlt
                                    : MacColors.textSecondary
                            )

                        Spacer()

                        if mode == currentMode {
                            Image(systemName: "checkmark")
                                .font(.system(size: 10, weight: .bold))
                                .foregroundStyle(MacColors.amberAccent)
                        }
                    }
                    .padding(.horizontal, MacSpacing.md)
                    .padding(.vertical, MacSpacing.sm)
                    .background(
                        mode == currentMode
                            ? MacColors.activeTabBackground
                            : Color.clear
                    )
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                }
                .buttonStyle(.hestia)
            }
        }
        .padding(MacSpacing.sm)
        .frame(width: 160)
    }

    // MARK: - Glow Pulse Animation

    private func startGlowPulse() {
        withAnimation(
            .easeInOut(duration: 0.8)
            .repeatForever(autoreverses: true)
        ) {
            glowOpacity = 0.6
        }
    }

    private func stopGlowPulse() {
        withAnimation(.easeOut(duration: 0.3)) {
            glowOpacity = 0.2
        }
    }
}
