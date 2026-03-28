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
                            case .memory:
                                ResearchView()
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
            .onReceive(NotificationCenter.default.publisher(for: .hestiaDeepLink)) { notification in
                if let link = notification.userInfo?["deepLink"] as? HestiaDeepLink {
                    navigate(to: link)
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

    // MARK: - Deep Link Navigation

    /// Navigate to a deep link destination, switching tabs and forwarding
    /// context to the relevant child view via secondary notifications.
    private func navigate(to link: HestiaDeepLink) {
        switch link {
        case .entity(let id):
            withAnimation(.hestiaNavSwitch) { workspace.currentView = .memory }
            NotificationCenter.default.post(
                name: .hestiaResearchNavigate,
                object: nil,
                userInfo: ["mode": "canvas", "entityId": id]
            )

        case .fact(let id):
            withAnimation(.hestiaNavSwitch) { workspace.currentView = .memory }
            NotificationCenter.default.post(
                name: .hestiaResearchNavigate,
                object: nil,
                userInfo: ["mode": "graph", "factId": id]
            )

        case .workflow(let id, let stepId):
            // Orders tab removed — redirect to Command and switch to Newsfeed sub-tab
            withAnimation(.hestiaNavSwitch) { workspace.currentView = .command }
            workspace.commandSubTab = .newsfeed
            var info: [String: String] = ["workflowId": id]
            if let step = stepId { info["stepId"] = step }
            NotificationCenter.default.post(
                name: .hestiaWorkflowNavigate,
                object: nil,
                userInfo: info
            )

        case .researchCanvas(let boardId, let entityId):
            withAnimation(.hestiaNavSwitch) { workspace.currentView = .memory }
            var info: [String: String] = ["mode": "canvas", "boardId": boardId]
            if let eid = entityId { info["entityId"] = eid }
            NotificationCenter.default.post(
                name: .hestiaResearchNavigate,
                object: nil,
                userInfo: info
            )

        case .chat:
            // Placeholder — chat panel is a floating overlay, not a tab.
            // Future: open the chat panel and scroll to the target message.
            break
        }
    }
}

// MARK: - Deep Link Notification Names

extension Notification.Name {
    /// Posted by WorkspaceRootView after switching to the Research tab.
    /// userInfo keys: "mode" (graph|canvas), "entityId"?, "boardId"?, "factId"?
    static let hestiaResearchNavigate = Notification.Name("hestia.research.navigate")

    /// Posted by WorkspaceRootView after switching to the Workflow tab.
    /// userInfo keys: "workflowId", "stepId"?
    static let hestiaWorkflowNavigate = Notification.Name("hestia.workflow.navigate")
}
