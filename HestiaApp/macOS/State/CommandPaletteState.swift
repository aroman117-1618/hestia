import SwiftUI

// MARK: - Command Palette State

@MainActor
@Observable
class CommandPaletteState {
    var isOpen: Bool = false
    var searchText: String = ""

    var filteredCommands: [PaletteCommand] {
        if searchText.isEmpty { return PaletteCommand.allCommands }
        let query = searchText.lowercased()
        return PaletteCommand.allCommands.filter { cmd in
            cmd.title.lowercased().contains(query) ||
            cmd.keywords.contains(where: { $0.contains(query) })
        }
    }

    func toggle() {
        withAnimation(.spring(response: 0.25, dampingFraction: 0.9)) {
            if isOpen {
                close()
            } else {
                isOpen = true
                searchText = ""
            }
        }
    }

    func close() {
        withAnimation(.spring(response: 0.2, dampingFraction: 0.9)) {
            isOpen = false
            searchText = ""
        }
    }

    func execute(_ command: PaletteCommand) {
        close()
        command.action()
    }
}

// MARK: - Palette Command

@MainActor
struct PaletteCommand: Identifiable {
    let id: String
    let title: String
    let icon: String
    let shortcut: String?
    let keywords: [String]
    let action: () -> Void

    static let allCommands: [PaletteCommand] = [
        PaletteCommand(
            id: "nav.command", title: "Go to Command Center",
            icon: "house", shortcut: "⌘1",
            keywords: ["home", "dashboard", "command"],
            action: { switchView(.command) }
        ),
        PaletteCommand(
            id: "nav.memory", title: "Go to Memory",
            icon: "brain.head.profile", shortcut: "⌘2",
            keywords: ["memory", "research", "knowledge"],
            action: { switchView(.memory) }
        ),
        PaletteCommand(
            id: "nav.settings", title: "Go to Settings",
            icon: "gearshape", shortcut: "⌘3",
            keywords: ["settings", "profile", "agents", "resources", "field guide", "wiki"],
            action: { switchView(.settings) }
        ),
        PaletteCommand(
            id: "action.toggleChat", title: "Toggle Chat Panel",
            icon: "bubble.left.and.bubble.right", shortcut: "⌘\\",
            keywords: ["chat", "panel", "toggle", "hide", "show"],
            action: {
                NotificationCenter.default.post(name: .hestiaChatPanelToggle, object: nil)
            }
        ),
    ]

    private static func switchView(_ view: WorkspaceView) {
        NotificationCenter.default.post(
            name: .workspaceViewSwitch,
            object: nil,
            userInfo: ["view": view.rawValue]
        )
    }
}
