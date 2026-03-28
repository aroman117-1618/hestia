import SwiftUI
import HestiaShared

/// Hestia notification names — centralized for SwiftUI ↔ AppKit bridges.
extension Notification.Name {
    static let workspaceViewSwitch = Notification.Name("workspaceViewSwitch")
    static let hestiaChatPanelToggle = Notification.Name("hestia.chatPanel.toggle")
    static let hestiaChatPanelDetach = Notification.Name("hestia.chatPanel.detach")
    static let hestiaCommandPaletteToggle = Notification.Name("hestia.commandPalette.toggle")
    static let activityTabSwitch = Notification.Name("hestia.activityTab.switch")
    static let hestiaServerReconnected = Notification.Name("hestia.server.reconnected")
    static let hestiaDeepLink = Notification.Name("hestia.deepLink")
    static let hestiaSendToChat = Notification.Name("hestia.sendToChat")
    static let hestiaChatModeSwitch = Notification.Name("hestia.chatPanel.modeSwitch")
}

// MARK: - Header Chat Toggle (compact button in chat panel header)

/// Compact collapse button (28x28) for the chat panel header bar.
/// Provides a visible "close this panel" affordance inside the panel itself.
struct HeaderChatToggle: View {
    @State private var isHovered = false

    var body: some View {
        Button {
            NotificationCenter.default.post(name: .hestiaChatPanelToggle, object: nil)
        } label: {
            Image(systemName: "chevron.right.2")
                .font(MacTypography.smallMedium)
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
