import SwiftUI
import HestiaShared

/// Floating toggle button at the bottom-right of the main content area.
/// Always visible — shows/hides the right chat panel via notification.
struct ChatPanelToggleOverlay: View {
    @Environment(WorkspaceState.self) private var workspace
    @State private var isHovered = false

    private var isVisible: Bool { workspace.isChatPanelVisible }

    var body: some View {
        Button {
            NotificationCenter.default.post(name: .hestiaChatPanelToggle, object: nil)
        } label: {
            Image(systemName: isVisible ? "sidebar.right" : "sidebar.right")
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(isHovered ? MacColors.amberAccent : MacColors.textSecondary)
                .frame(width: 28, height: 28)
                .background(
                    RoundedRectangle(cornerRadius: 6)
                        .fill(isHovered ? MacColors.activeNavBackground : MacColors.windowBackground.opacity(0.8))
                )
                .overlay {
                    RoundedRectangle(cornerRadius: 6)
                        .strokeBorder(MacColors.sidebarBorder, lineWidth: 0.5)
                }
        }
        .buttonStyle(.hestiaIcon)
        .onHover { hovering in
            withAnimation(.easeInOut(duration: 0.15)) {
                isHovered = hovering
            }
        }
        .help(isVisible ? "Hide right sidebar (\u{2318}\\)" : "Show right sidebar (\u{2318}\\)")
        .accessibilityLabel(isVisible ? "Hide chat panel" : "Show chat panel")
        .accessibilityHint("Keyboard shortcut: Command backslash")
        .hoverCursor()
        .padding(MacSpacing.md)
    }
}
