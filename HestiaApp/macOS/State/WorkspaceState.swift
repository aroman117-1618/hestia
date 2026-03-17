import SwiftUI
import HestiaShared

// MARK: - Workspace Navigation State

enum WorkspaceView: String, CaseIterable {
    case command
    case health
    case research
    case explorer
    case settings
}

// MARK: - Persistence Keys

private enum WorkspaceDefaults {
    static let currentView = "hestia.workspace.currentView"
    static let chatPanelVisible = "hestia.workspace.chatPanelVisible"
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

    init() {
        // Restore persisted state with migration for removed views
        if let savedView = UserDefaults.standard.string(forKey: WorkspaceDefaults.currentView),
           let view = WorkspaceView(rawValue: savedView) {
            self.currentView = view
        } else {
            // Migrate legacy values: wiki/resources/profile → settings
            let savedRaw = UserDefaults.standard.string(forKey: WorkspaceDefaults.currentView)
            if savedRaw == "wiki" || savedRaw == "resources" || savedRaw == "profile" || savedRaw == "memory" {
                self.currentView = .settings
            } else {
                self.currentView = .command
            }
        }

        // Default to chat visible if never set (first launch)
        if UserDefaults.standard.object(forKey: WorkspaceDefaults.chatPanelVisible) != nil {
            self.isChatPanelVisible = UserDefaults.standard.bool(forKey: WorkspaceDefaults.chatPanelVisible)
        } else {
            self.isChatPanelVisible = true
        }
    }
}
