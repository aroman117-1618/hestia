import SwiftUI

/// Shared selection state between sidebar and canvas
@MainActor
@Observable
class SelectedTab {
    var current: WorkspaceTab = .calendar
}

/// Workspace tab definitions for the macOS sidebar and canvas
enum WorkspaceTab: String, CaseIterable, Identifiable {
    case calendar
    case mail
    case notes
    case files
    case health
    case agents

    var id: String { rawValue }

    var title: String {
        switch self {
        case .calendar: return "Calendar"
        case .mail: return "Mail"
        case .notes: return "Notes"
        case .files: return "Files"
        case .health: return "Health"
        case .agents: return "Agents"
        }
    }

    var icon: String {
        switch self {
        case .calendar: return "calendar"
        case .mail: return "envelope"
        case .notes: return "note.text"
        case .files: return "folder"
        case .health: return "heart.text.square"
        case .agents: return "person.3"
        }
    }

    var phaseLabel: String {
        switch self {
        case .calendar: return "Phase 1.0"
        case .mail: return "Phase 1.0"
        case .notes: return "Phase 1.0"
        case .files: return "Phase 1.0"
        case .health: return "Phase 1.5"
        case .agents: return "Phase 2.0"
        }
    }
}
