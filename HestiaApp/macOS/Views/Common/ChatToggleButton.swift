import SwiftUI
import HestiaShared

/// Hestia notification names — centralized for SwiftUI ↔ AppKit bridges.
extension Notification.Name {
    static let workspaceViewSwitch = Notification.Name("workspaceViewSwitch")
    static let hestiaChatPanelToggle = Notification.Name("hestia.chatPanel.toggle")
    static let hestiaCommandPaletteToggle = Notification.Name("hestia.commandPalette.toggle")
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
