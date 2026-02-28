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
        window.setFrameAutosaveName("HestiaWorkspaceMainWindow")
        window.contentViewController = splitVC
        window.center()

        self.init(window: window)
    }

    // MARK: - Keyboard Shortcuts

    @IBAction func toggleSidebar(_ sender: Any?) {
        guard let splitVC = contentViewController as? MainSplitViewController else { return }
        splitVC.toggleSidebar()
    }

    @IBAction func toggleChatPanel(_ sender: Any?) {
        guard let splitVC = contentViewController as? MainSplitViewController else { return }
        splitVC.toggleChatPanel()
    }

    override func keyDown(with event: NSEvent) {
        // Cmd+B: toggle sidebar
        if event.modifierFlags.contains(.command) && event.charactersIgnoringModifiers == "b" {
            toggleSidebar(nil)
            return
        }
        // Cmd+\: toggle chat panel
        if event.modifierFlags.contains(.command) && event.charactersIgnoringModifiers == "\\" {
            toggleChatPanel(nil)
            return
        }
        super.keyDown(with: event)
    }
}
