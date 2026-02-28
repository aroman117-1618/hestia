import AppKit

class MainWindowController: NSWindowController {
    convenience init() {
        let splitVC = MainSplitViewController()

        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1400, height: 900),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.minSize = NSSize(width: 1000, height: 600)
        window.title = "Hestia Workspace"
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
        window.backgroundColor = NSColor(red: 13/255, green: 8/255, blue: 2/255, alpha: 1)
        window.setFrameAutosaveName("HestiaWorkspaceMainWindow")
        window.contentViewController = splitVC
        window.center()

        self.init(window: window)
    }

    // MARK: - Keyboard Shortcuts

    @IBAction func toggleChatPanel(_ sender: Any?) {
        guard let splitVC = contentViewController as? MainSplitViewController else { return }
        splitVC.toggleChatPanel()
    }

    override func keyDown(with event: NSEvent) {
        guard event.modifierFlags.contains(.command) else {
            super.keyDown(with: event)
            return
        }

        switch event.charactersIgnoringModifiers {
        case "\\":
            toggleChatPanel(nil)
        case "1":
            switchView(to: .command)
        case "2":
            switchView(to: .explorer)
        case "3":
            switchView(to: .health)
        default:
            super.keyDown(with: event)
        }
    }

    private func switchView(to view: WorkspaceView) {
        guard let splitVC = contentViewController as? MainSplitViewController else { return }
        // Access the workspace state through the split view controller isn't ideal,
        // but we post a notification that the SwiftUI views can observe
        NotificationCenter.default.post(
            name: .workspaceViewSwitch,
            object: nil,
            userInfo: ["view": view.rawValue]
        )
    }
}

// MARK: - Notification for keyboard-driven view switching

extension Notification.Name {
    static let workspaceViewSwitch = Notification.Name("workspaceViewSwitch")
}
