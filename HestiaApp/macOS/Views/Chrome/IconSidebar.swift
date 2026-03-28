import SwiftUI
import HestiaShared

struct IconSidebar: View {
    @Environment(WorkspaceState.self) private var workspace
    @State private var hoveredView: WorkspaceView?
    @State private var hoveredChat = false
    @Namespace private var indicatorNamespace

    var body: some View {
        VStack(spacing: 0) {
            // Avatar (top, sticky — navigates to Settings)
            avatarButton
                .padding(.top, MacSpacing.xl)

            // Nav icons (middle section, fixed order per design spec)
            VStack(spacing: 6) {
                navIcon(.command, systemName: "house", shortcut: 1)
                    .padding(.top, MacSpacing.lg)
                navIcon(.memory, systemName: "brain.head.profile", shortcut: 2)
            }
            .padding(.top, MacSpacing.xxl)

            Spacer()

            // Chat toggle (bottom, sticky — Cursor-style sidebar panel icon)
            chatToggleButton
                .padding(.bottom, MacSpacing.xxl)
        }
        .frame(width: MacSize.iconSidebarWidth)
        .background(MacColors.sidebarBackground)
        .overlay(alignment: .trailing) {
            MacColors.sidebarBorder.frame(width: 1)
        }
    }

    // MARK: - Avatar (Settings entry)

    private var avatarButton: some View {
        let isActive = workspace.currentView == .settings
        let isHovered = hoveredView == .settings

        return Button {
            withAnimation(MacAnimation.normalSpring) {
                workspace.currentView = .settings
            }
        } label: {
            ZStack {
                // Avatar circle with gradient
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [
                                Color(red: 70/255, green: 25/255, blue: 1/255).opacity(0.8),
                                Color(red: 254/255, green: 154/255, blue: 0).opacity(0.3)
                            ],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                Circle()
                    .strokeBorder(
                        isActive ? MacColors.amberAccent : MacColors.avatarBorder,
                        lineWidth: isActive ? 1.5 : 1
                    )

                Text("HS")
                    .font(MacTypography.caption)
                    .tracking(0.065)
                    .foregroundStyle(MacColors.textPrimary)
            }
            .frame(width: MacSize.navIconButton, height: MacSize.navIconButton)
            .opacity(isHovered && !isActive ? 0.85 : 1.0)
        }
        .buttonStyle(.hestiaNav)
        .onHover { hovering in
            withAnimation(.easeInOut(duration: MacAnimation.fast)) {
                hoveredView = hovering ? .settings : nil
            }
        }
        .accessibilityLabel("Settings")
        .accessibilityHint("Keyboard shortcut: Command 3")
        .hoverCursor()
    }

    // MARK: - Nav Icon

    private func navIcon(_ view: WorkspaceView, systemName: String, shortcut: Int) -> some View {
        let isActive = workspace.currentView == view
        let isHovered = hoveredView == view

        return Button {
            withAnimation(MacAnimation.normalSpring) {
                workspace.currentView = view
            }
        } label: {
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: MacCornerRadius.navIcon)
                    .fill(isActive ? MacColors.activeNavBackground : (isHovered ? MacColors.activeNavBackground.opacity(0.5) : Color.clear))
                    .overlay {
                        if isActive {
                            RoundedRectangle(cornerRadius: MacCornerRadius.navIcon)
                                .strokeBorder(MacColors.activeNavBorder, lineWidth: 1)
                        }
                    }
                    .frame(width: MacSize.navIconButton, height: MacSize.navIconButton)

                // Active indicator pill (left edge) — slides between nav items
                if isActive {
                    UnevenRoundedRectangle(
                        topLeadingRadius: 0,
                        bottomLeadingRadius: 0,
                        bottomTrailingRadius: 8,
                        topTrailingRadius: 8
                    )
                    .fill(MacColors.activeIndicatorGradient)
                    .frame(width: MacSize.activeIndicatorWidth, height: MacSize.activeIndicatorHeight)
                    .offset(x: -1, y: 0)
                    .matchedGeometryEffect(id: "activeIndicator", in: indicatorNamespace)
                }

                Image(systemName: systemName)
                    .font(.system(size: MacSize.navIcon))
                    .foregroundStyle(isActive ? MacColors.amberAccent : (isHovered ? MacColors.textPrimary : MacColors.textSecondary))
                    .frame(width: MacSize.navIconButton, height: MacSize.navIconButton)
            }
        }
        .buttonStyle(.hestiaNav)
        .onHover { hovering in
            withAnimation(.easeInOut(duration: MacAnimation.fast)) {
                hoveredView = hovering ? view : nil
            }
        }
        .accessibilityLabel(accessibilityLabel(for: view))
        .accessibilityHint("Keyboard shortcut: Command \(shortcut)")
        .hoverCursor()
    }

    private func accessibilityLabel(for view: WorkspaceView) -> String {
        switch view {
        case .command: "Command Center"
        case .memory: "Memory"
        case .settings: "Settings"
        }
    }

    // MARK: - Chat Toggle Button (bottom, Cursor-style)

    private var chatToggleButton: some View {
        let iconName = workspace.isChatDetached
            ? "rectangle.portrait.on.rectangle.portrait"
            : "sidebar.trailing"

        return Button {
            NotificationCenter.default.post(name: .hestiaChatPanelToggle, object: nil)
        } label: {
            Image(systemName: iconName)
                .font(.system(size: MacSize.navIcon))
                .foregroundStyle(
                    workspace.isChatPanelVisible
                        ? MacColors.amberAccent
                        : (hoveredChat ? MacColors.textPrimary : MacColors.textSecondary)
                )
                .frame(width: MacSize.navIconButton, height: MacSize.navIconButton)
                .background(
                    RoundedRectangle(cornerRadius: MacCornerRadius.navIcon)
                        .fill(hoveredChat ? MacColors.activeNavBackground.opacity(0.5) : Color.clear)
                )
        }
        .buttonStyle(.hestiaNav)
        .onHover { hovering in
            withAnimation(.easeInOut(duration: MacAnimation.fast)) {
                hoveredChat = hovering
            }
        }
        .accessibilityLabel(workspace.isChatPanelVisible ? "Hide Chat Panel" : "Show Chat Panel")
        .accessibilityHint("Keyboard shortcut: Command Backslash")
        .hoverCursor()
    }
}

// MARK: - Haptic feedback on nav switch

extension IconSidebar {
    // Haptic feedback is provided via .sensoryFeedback on the parent VStack,
    // triggered by workspace.currentView changes. See WorkspaceRootView.
}
