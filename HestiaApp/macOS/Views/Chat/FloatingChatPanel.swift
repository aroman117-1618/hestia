import SwiftUI
import HestiaShared

struct FloatingChatOverlay: View {
    @Environment(WorkspaceState.self) private var workspace
    @EnvironmentObject var appState: AppState
    @State private var isHoveredClose = false

    private let overlayWidth: CGFloat = 400
    private let overlayHeight: CGFloat = 520

    var body: some View {
        VStack(spacing: 0) {
            // Header bar
            floatingHeader

            MacColors.divider.frame(height: 0.5)

            // Chat content (reuse existing chat view)
            MacChatPanelView()
                .environmentObject(appState)
        }
        .frame(width: overlayWidth, height: overlayHeight)
        .background(floatingBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .strokeBorder(MacColors.divider.opacity(0.4), lineWidth: 1)
        }
        .shadow(color: .black.opacity(0.4), radius: 20, x: 0, y: 8)
        .padding(.trailing, MacSpacing.lg)
        .padding(.bottom, MacSpacing.lg)
        .transition(.asymmetric(
            insertion: .scale(scale: 0.9, anchor: .bottomTrailing).combined(with: .opacity),
            removal: .scale(scale: 0.95, anchor: .bottomTrailing).combined(with: .opacity)
        ))
    }

    // MARK: - Header

    private var floatingHeader: some View {
        HStack {
            Text("Hestia")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(MacColors.textPrimary)

            Spacer()

            // Mode switcher buttons
            Button {
                NotificationCenter.default.post(
                    name: .hestiaChatModeSwitch,
                    object: nil,
                    userInfo: ["mode": "sidebar"]
                )
            } label: {
                Image(systemName: "sidebar.trailing")
                    .font(.system(size: 11))
                    .foregroundStyle(MacColors.textSecondary)
            }
            .buttonStyle(.hestiaIcon)
            .help("Dock as sidebar")

            Button {
                NotificationCenter.default.post(
                    name: .hestiaChatModeSwitch,
                    object: nil,
                    userInfo: ["mode": "detached"]
                )
            } label: {
                Image(systemName: "rectangle.portrait.on.rectangle.portrait")
                    .font(.system(size: 11))
                    .foregroundStyle(MacColors.textSecondary)
            }
            .buttonStyle(.hestiaIcon)
            .help("Detach to window")

            Button {
                withAnimation(MacAnimation.fastSpring) {
                    workspace.chatMode = .hidden
                }
            } label: {
                Image(systemName: "minus")
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(isHoveredClose ? MacColors.amberAccent : MacColors.textSecondary)
            }
            .buttonStyle(.hestiaIcon)
            .onHover { isHoveredClose = $0 }
            .help("Minimize chat")
        }
        .padding(.horizontal, MacSpacing.md)
        .padding(.vertical, MacSpacing.sm)
    }

    // MARK: - Background

    private var floatingBackground: some View {
        ZStack {
            MacColors.windowBackground
            MacColors.panelBackground.opacity(0.5)
        }
    }
}
