import SwiftUI
import HestiaShared

struct IconSidebar: View {
    @Environment(WorkspaceState.self) private var workspace
    @State private var hoveredView: WorkspaceView?
    @Namespace private var indicatorNamespace

    var body: some View {
        VStack(spacing: 0) {
            // Logo (top, sticky — navigates to Command Center)
            logoButton
                .padding(.top, MacSpacing.xl)

            // Nav icons (middle section, fixed order per design spec)
            VStack(spacing: 6) {
                navIcon(.command, systemName: "house", shortcut: 1)
                    .padding(.top, MacSpacing.lg)
                // Health tab archived — data surfaces via Internal activity feed (Sprint 25.5)
                // navIcon(.health, systemName: "waveform.path.ecg", shortcut: 2)
                navIcon(.research, systemName: "point.3.connected.trianglepath.dotted", shortcut: 2)
                navIcon(.explorer, systemName: "magnifyingglass", shortcut: 3)
                navIcon(.workflow, systemName: "arrow.triangle.branch", shortcut: 4)
            }
            .padding(.top, MacSpacing.xxl)

            Spacer()

            // Settings (bottom, sticky — profile avatar)
            settingsButton
                .padding(.bottom, MacSpacing.xxl)
        }
        .frame(width: MacSize.iconSidebarWidth)
        .background(MacColors.sidebarBackground)
        .overlay(alignment: .trailing) {
            MacColors.sidebarBorder.frame(width: 1)
        }
    }

    // MARK: - Logo

    private var logoButton: some View {
        Image("HestiaLogo")
            .resizable()
            .scaledToFit()
            .frame(width: MacSize.logoSize, height: MacSize.logoSize)
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.navIcon))
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
        case .health: "Vitals"
        case .research: "Research"
        case .explorer: "Explorer"
        case .workflow: "Workflows"
        case .settings: "Settings"
        }
    }

    // MARK: - Settings Button (bottom avatar)

    private var settingsButton: some View {
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
                    .font(.system(size: 11))
                    .tracking(0.065)
                    .foregroundStyle(.white)
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
        .accessibilityHint("Keyboard shortcut: Command 5")
        .hoverCursor()
    }
}

// MARK: - Haptic feedback on nav switch

extension IconSidebar {
    // Haptic feedback is provided via .sensoryFeedback on the parent VStack,
    // triggered by workspace.currentView changes. See WorkspaceRootView.
}
