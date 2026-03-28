import SwiftUI
import HestiaShared

// MARK: - Workspace Navigation State

enum WorkspaceView: String {
    case command
    case memory
    case settings
}

// MARK: - Persistence Keys

private enum WorkspaceDefaults {
    static let currentView = "hestia.workspace.currentView"
    static let chatPanelVisible = "hestia.workspace.chatPanelVisible"
    static let isChatDetached = "hestia.workspace.chatDetached"
}

@MainActor
@Observable
class WorkspaceState {
    var currentView: WorkspaceView {
        didSet {
            UserDefaults.standard.set(currentView.rawValue, forKey: WorkspaceDefaults.currentView)
        }
    }

    var isChatPanelVisible: Bool {
        didSet {
            UserDefaults.standard.set(isChatPanelVisible, forKey: WorkspaceDefaults.chatPanelVisible)
        }
    }

    var isChatDetached: Bool = false

    /// Which sub-tab is active in the Command tab
    var commandSubTab: CommandSubTab = .dashboard

    enum CommandSubTab: String, CaseIterable {
        case dashboard = "Dashboard"
        case activity = "Activity"
        case orders = "Orders"
    }

    init() {
        // Restore persisted state with migration for removed views
        let savedRaw = UserDefaults.standard.string(forKey: WorkspaceDefaults.currentView) ?? "command"
        // Migration: old values (.orders, .explorer, .workflow, .research, etc.) fall back to .command
        self.currentView = WorkspaceView(rawValue: savedRaw) ?? .command

        // Default to chat visible if never set (first launch)
        if UserDefaults.standard.object(forKey: WorkspaceDefaults.chatPanelVisible) != nil {
            self.isChatPanelVisible = UserDefaults.standard.bool(forKey: WorkspaceDefaults.chatPanelVisible)
        } else {
            self.isChatPanelVisible = true
        }
    }
}
