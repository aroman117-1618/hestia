import SwiftUI
import HestiaShared

// MARK: - Workspace Navigation State

enum WorkspaceView: String, CaseIterable {
    case command
    case explorer
    case health
}

@MainActor
@Observable
class WorkspaceState {
    var currentView: WorkspaceView = .command
    var isChatPanelVisible: Bool = true
}
