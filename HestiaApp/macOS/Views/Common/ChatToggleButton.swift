import SwiftUI
import HestiaShared

/// Hestia notification names — centralized for SwiftUI ↔ AppKit bridges.
extension Notification.Name {
    static let workspaceViewSwitch = Notification.Name("workspaceViewSwitch")
    static let hestiaChatPanelToggle = Notification.Name("hestia.chatPanel.toggle")
    static let hestiaCommandPaletteToggle = Notification.Name("hestia.commandPalette.toggle")
}

// MARK: - Sidebar Chat Toggle (Option C — bottom of icon sidebar)

/// Full-size chat toggle button matching nav icon styling (40x40, amber active state, indicator pill).
/// Placed at the bottom of IconSidebar below the profile button.
struct SidebarChatToggle: View {
    @Environment(WorkspaceState.self) private var workspace
    @State private var isHovered = false

    var body: some View {
        let isVisible = workspace.isChatPanelVisible

        Button {
            NotificationCenter.default.post(name: .hestiaChatPanelToggle, object: nil)
        } label: {
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: MacCornerRadius.navIcon)
                    .fill(isVisible ? MacColors.activeNavBackground : (isHovered ? MacColors.activeNavBackground.opacity(0.5) : Color.clear))
                    .overlay {
                        if isVisible {
                            RoundedRectangle(cornerRadius: MacCornerRadius.navIcon)
                                .strokeBorder(MacColors.activeNavBorder, lineWidth: 1)
                        }
                    }
                    .frame(width: MacSize.navIconButton, height: MacSize.navIconButton)

                // Active indicator pill (left edge) — matches nav icons
                if isVisible {
                    UnevenRoundedRectangle(
                        topLeadingRadius: 0,
                        bottomLeadingRadius: 0,
                        bottomTrailingRadius: 8,
                        topTrailingRadius: 8
                    )
                    .fill(MacColors.activeIndicatorGradient)
                    .frame(width: MacSize.activeIndicatorWidth, height: MacSize.activeIndicatorHeight)
                    .offset(x: -1)
                }

                Image(systemName: "bubble.left")
                    .font(.system(size: MacSize.navIcon))
                    .foregroundStyle(isVisible ? MacColors.amberAccent : (isHovered ? MacColors.textPrimary : MacColors.textSecondary))
                    .frame(width: MacSize.navIconButton, height: MacSize.navIconButton)
            }
        }
        .buttonStyle(.hestiaNav)
        .onHover { hovering in
            withAnimation(.easeInOut(duration: 0.15)) {
                isHovered = hovering
            }
        }
        .help("Toggle Chat (⌘\\)")
        .accessibilityLabel("Toggle chat panel")
        .accessibilityHint("Keyboard shortcut: Command backslash")
        .accessibilityAddTraits(workspace.isChatPanelVisible ? .isSelected : [])
    }
}

// MARK: - Header Chat Toggle (Option A — compact button in chat panel header)

/// Compact collapse button (28x28) for the chat panel header bar.
/// Provides a visible "close this panel" affordance inside the panel itself.
struct HeaderChatToggle: View {
    @State private var isHovered = false

    var body: some View {
        Button {
            NotificationCenter.default.post(name: .hestiaChatPanelToggle, object: nil)
        } label: {
            Image(systemName: "chevron.right.2")
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(isHovered ? MacColors.amberAccent : MacColors.textSecondary)
                .frame(width: 28, height: 28)
                .background(isHovered ? MacColors.activeNavBackground : Color.clear)
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
        }
        .buttonStyle(.hestiaIcon)
        .onHover { hovering in
            withAnimation(.easeInOut(duration: 0.15)) {
                isHovered = hovering
            }
        }
        .help("Hide Chat (⌘\\)")
        .accessibilityLabel("Hide chat panel")
    }
}
