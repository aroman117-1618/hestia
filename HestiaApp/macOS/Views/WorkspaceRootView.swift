import SwiftUI
import HestiaShared

struct WorkspaceRootView: View {
    @Environment(WorkspaceState.self) private var workspace
    @EnvironmentObject var appState: AppState

    var body: some View {
        HStack(spacing: 0) {
            // Left: Icon sidebar (68px)
            IconSidebar()

            // Center: Content area (flex)
            Group {
                switch workspace.currentView {
                case .command:
                    CommandView()
                case .explorer:
                    ExplorerView()
                case .health:
                    HealthView()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .animation(.easeInOut(duration: 0.2), value: workspace.currentView)
        }
        .background(MacColors.windowBackground)
        .onReceive(NotificationCenter.default.publisher(for: .workspaceViewSwitch)) { notification in
            if let rawValue = notification.userInfo?["view"] as? String,
               let view = WorkspaceView(rawValue: rawValue) {
                withAnimation(.easeInOut(duration: 0.2)) {
                    workspace.currentView = view
                }
            }
        }
    }
}
