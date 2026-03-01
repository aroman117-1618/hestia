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
        window.minSize = NSSize(width: 1200, height: 700)
        window.title = "Hestia Workspace"
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
        window.backgroundColor = NSColor(red: 13/255, green: 8/255, blue: 2/255, alpha: 1)
        window.setFrameAutosaveName("HestiaWorkspaceMainWindow")
        window.contentViewController = splitVC
        window.center()

        self.init(window: window)
    }

    // MARK: - Chat Panel Toggle

    @IBAction func toggleChatPanel(_ sender: Any?) {
        guard let splitVC = contentViewController as? MainSplitViewController else { return }
        splitVC.toggleChatPanel()
    }
}

// MARK: - Notification for keyboard-driven view switching

extension Notification.Name {
    static let workspaceViewSwitch = Notification.Name("workspaceViewSwitch")
}
