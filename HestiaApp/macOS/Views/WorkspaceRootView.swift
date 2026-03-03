import SwiftUI
import HestiaShared

struct WorkspaceRootView: View {
    @Environment(WorkspaceState.self) private var workspace
    @Environment(ErrorState.self) private var errorState
    @Environment(CommandPaletteState.self) private var palette
    @EnvironmentObject var appState: AppState

    var body: some View {
        GeometryReader { geo in
            let layoutMode = LayoutMode.from(width: geo.size.width - MacSize.iconSidebarWidth)

            ZStack {
                HStack(spacing: 0) {
                    // Left: Icon sidebar (68px)
                    IconSidebar()

                    // Center: Content area (flex)
                    ZStack(alignment: .top) {
                        Group {
                            switch workspace.currentView {
                            case .command:
                                CommandView()
                            case .health:
                                HealthView()
                            case .research:
                                ResearchView()
                            case .explorer:
                                ExplorerView()
                            case .settings:
                                MacSettingsView()
                            }
                        }
                        .frame(maxWidth: .infinity, maxHeight: .infinity)

                        // Global error banner overlay
                        GlobalErrorBanner()
                    }
                    .environment(\.layoutMode, layoutMode)
                    .animation(.hestiaNavSwitch, value: workspace.currentView)
                }
                .background(MacColors.windowBackground)

                // Command palette overlay (⌘K)
                CommandPaletteView()
            }
            // Haptic feedback on navigation switch
            .sensoryFeedback(.impact(weight: .light), trigger: workspace.currentView)
            .onReceive(NotificationCenter.default.publisher(for: .workspaceViewSwitch)) { notification in
                if let rawValue = notification.userInfo?["view"] as? String,
                   let view = WorkspaceView(rawValue: rawValue) {
                    withAnimation(.hestiaNavSwitch) {
                        workspace.currentView = view
                    }
                }
            }
            .onReceive(NotificationCenter.default.publisher(for: .hestiaCommandPaletteToggle)) { _ in
                palette.toggle()
            }
        }
    }
}
