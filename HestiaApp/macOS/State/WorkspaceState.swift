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
    static let chatMode = "hestia.workspace.chatMode"
}

@MainActor
@Observable
class WorkspaceState {
    var currentView: WorkspaceView {
        didSet {
            UserDefaults.standard.set(currentView.rawValue, forKey: WorkspaceDefaults.currentView)
        }
    }

    /// Which sub-tab is active in the Command tab
    var commandSubTab: CommandSubTab = .dashboard

    enum CommandSubTab: String, CaseIterable {
        case dashboard = "Dashboard"
        case activity = "Activity"
        case orders = "Orders"
    }

    enum ChatMode: String {
        case floating   // Notion-style overlay panel (default)
        case sidebar    // NSSplitViewItem docked right
        case detached   // Standalone NSWindow
        case hidden     // No chat visible
    }

    var chatMode: ChatMode {
        didSet {
            UserDefaults.standard.set(chatMode.rawValue, forKey: WorkspaceDefaults.chatMode)
        }
    }

    // Convenience computed properties (backward compat for existing code that READS these)
    var isChatPanelVisible: Bool {
        chatMode == .sidebar
    }

    var isChatDetached: Bool {
        chatMode == .detached
    }

    var isChatFloating: Bool {
        chatMode == .floating
    }

    var isChatVisible: Bool {
        chatMode != .hidden
    }

    init() {
        // Restore persisted state with migration for removed views
        let savedRaw = UserDefaults.standard.string(forKey: WorkspaceDefaults.currentView) ?? "command"
        // Migration: old values (.orders, .explorer, .workflow, .research, etc.) fall back to .command
        self.currentView = WorkspaceView(rawValue: savedRaw) ?? .command

        // Migrate from old boolean to new enum
        if let savedMode = UserDefaults.standard.string(forKey: WorkspaceDefaults.chatMode),
           let mode = ChatMode(rawValue: savedMode) {
            self.chatMode = mode
        } else if UserDefaults.standard.object(forKey: WorkspaceDefaults.chatPanelVisible) != nil {
            // Migration: old boolean → new enum
            let wasVisible = UserDefaults.standard.bool(forKey: WorkspaceDefaults.chatPanelVisible)
            self.chatMode = wasVisible ? .floating : .hidden
        } else {
            // First launch: default to hidden (user clicks avatar to open)
            self.chatMode = .hidden
        }
    }
}
