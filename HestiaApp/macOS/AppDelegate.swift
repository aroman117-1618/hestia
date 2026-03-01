import AppKit
import HestiaShared

@main
enum HestiaWorkspaceApp {
    static func main() {
        let app = NSApplication.shared
        app.setActivationPolicy(.regular)
        let delegate = AppDelegate()
        app.delegate = delegate
        app.run()
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    private var mainWindowController: MainWindowController?
    private var keyMonitor: Any?

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Configure shared package with macOS device info
        APIClient.configure(deviceInfo: MacDeviceInfoProvider())

        buildMainMenu()
        installKeyboardShortcuts()

        // Create and show main window
        mainWindowController = MainWindowController()
        mainWindowController?.showWindow(nil)
        mainWindowController?.window?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    func applicationSupportsSecureRestorableState(_ app: NSApplication) -> Bool {
        true
    }

    // MARK: - Menu Bar

    private func buildMainMenu() {
        let mainMenu = NSMenu()

        // App menu
        let appMenuItem = NSMenuItem()
        let appMenu = NSMenu(title: "Hestia")
        appMenu.addItem(withTitle: "About Hestia", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Quit Hestia", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appMenuItem.submenu = appMenu
        mainMenu.addItem(appMenuItem)

        // Edit menu
        let editMenuItem = NSMenuItem(title: "Edit", action: nil, keyEquivalent: "")
        let editMenu = NSMenu(title: "Edit")
        editMenu.addItem(withTitle: "Cut", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        editMenu.addItem(withTitle: "Copy", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        editMenu.addItem(withTitle: "Paste", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        editMenu.addItem(withTitle: "Select All", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        editMenuItem.submenu = editMenu
        mainMenu.addItem(editMenuItem)

        // View menu
        let viewMenuItem = NSMenuItem(title: "View", action: nil, keyEquivalent: "")
        let viewMenu = NSMenu(title: "View")

        let cmdItem = NSMenuItem(title: "Command Center", action: #selector(showCommandView), keyEquivalent: "1")
        cmdItem.target = self
        viewMenu.addItem(cmdItem)

        let expItem = NSMenuItem(title: "Explorer", action: #selector(showExplorerView), keyEquivalent: "2")
        expItem.target = self
        viewMenu.addItem(expItem)

        let healthItem = NSMenuItem(title: "Health", action: #selector(showHealthView), keyEquivalent: "3")
        healthItem.target = self
        viewMenu.addItem(healthItem)

        viewMenu.addItem(.separator())

        let chatItem = NSMenuItem(title: "Toggle Chat Panel", action: #selector(toggleChatPanel), keyEquivalent: "\\")
        chatItem.target = self
        viewMenu.addItem(chatItem)

        viewMenuItem.submenu = viewMenu
        mainMenu.addItem(viewMenuItem)

        NSApp.mainMenu = mainMenu
    }

    // MARK: - Keyboard Shortcuts (Local Event Monitor)

    private func installKeyboardShortcuts() {
        keyMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            guard event.modifierFlags.contains(.command),
                  !event.modifierFlags.contains(.shift),
                  !event.modifierFlags.contains(.option) else {
                return event
            }

            switch event.charactersIgnoringModifiers {
            case "1":
                self?.switchView(to: .command)
                return nil
            case "2":
                self?.switchView(to: .explorer)
                return nil
            case "3":
                self?.switchView(to: .health)
                return nil
            case "\\":
                self?.mainWindowController?.toggleChatPanel(nil)
                return nil
            default:
                return event
            }
        }
    }

    private func switchView(to view: WorkspaceView) {
        NotificationCenter.default.post(
            name: .workspaceViewSwitch,
            object: nil,
            userInfo: ["view": view.rawValue]
        )
    }

    // MARK: - Menu Actions

    @objc private func showCommandView() { switchView(to: .command) }
    @objc private func showExplorerView() { switchView(to: .explorer) }
    @objc private func showHealthView() { switchView(to: .health) }
    @objc private func toggleChatPanel() { mainWindowController?.toggleChatPanel(nil) }
}
