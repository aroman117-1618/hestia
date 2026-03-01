import SwiftUI
import HestiaShared

// MARK: - Workspace Navigation State

enum WorkspaceView: String, CaseIterable {
    case command
    case health
    case research
    case explorer
    case profile
    case wiki
    case resources
}

@MainActor
@Observable
class WorkspaceState {
    var currentView: WorkspaceView = .command
    var isChatPanelVisible: Bool = true
}
