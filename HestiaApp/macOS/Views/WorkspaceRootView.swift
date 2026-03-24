import SwiftUI
import HestiaShared

struct WorkspaceRootView: View {
    @Environment(WorkspaceState.self) private var workspace
    @Environment(ErrorState.self) private var errorState
    @Environment(CommandPaletteState.self) private var palette
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var networkMonitor: NetworkMonitor

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
                            case .workflow:
                                MacWorkflowView()
                            case .settings:
                                MacSettingsView()
                            }
                        }
                        .frame(maxWidth: .infinity, maxHeight: .infinity)

                        // Offline banner (persistent while disconnected)
                        OfflineBanner(
                            hasCachedData: CacheManager.shared.has(forKey: CacheKey.systemHealth),
                            lastCacheDate: CacheManager.shared.cachedAt(forKey: CacheKey.systemHealth)
                        )

                        // Global error banner overlay (transient, auto-dismisses)
                        GlobalErrorBanner()
                    }
                    .overlay(alignment: .topTrailing) {
                        ChatPanelToggleOverlay()
                    }
                    .environment(\.layoutMode, layoutMode)
                    .animation(.hestiaNavSwitch, value: workspace.currentView)
                }
                .background(MacColors.windowBackground)
                .tint(MacColors.amberAccent)

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
            .onChange(of: networkMonitor.isConnected) { wasConnected, isConnected in
                // Auto-refresh when connectivity restores
                if !wasConnected && isConnected {
                    NotificationCenter.default.post(name: .hestiaServerReconnected, object: nil)
                }
            }
        }
    }
}
