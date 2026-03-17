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

        // View menu — matches sidebar order (⌘1-5 + ⌘6 settings)
        let viewMenuItem = NSMenuItem(title: "View", action: nil, keyEquivalent: "")
        let viewMenu = NSMenu(title: "View")

        let cmdItem = NSMenuItem(title: "Command Center", action: #selector(showCommandView), keyEquivalent: "1")
        cmdItem.target = self
        viewMenu.addItem(cmdItem)

        let healthItem = NSMenuItem(title: "Vitals", action: #selector(showHealthView), keyEquivalent: "2")
        healthItem.target = self
        viewMenu.addItem(healthItem)

        let researchItem = NSMenuItem(title: "Research", action: #selector(showResearchView), keyEquivalent: "3")
        researchItem.target = self
        viewMenu.addItem(researchItem)

        let expItem = NSMenuItem(title: "Explorer", action: #selector(showExplorerView), keyEquivalent: "4")
        expItem.target = self
        viewMenu.addItem(expItem)

        let memoryItem = NSMenuItem(title: "Memory Browser", action: #selector(showMemoryView), keyEquivalent: "5")
        memoryItem.target = self
        viewMenu.addItem(memoryItem)

        viewMenu.addItem(.separator())

        let settingsItem = NSMenuItem(title: "Settings", action: #selector(showSettingsView), keyEquivalent: "6")
        settingsItem.target = self
        viewMenu.addItem(settingsItem)

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
                self?.switchView(to: .health)
                return nil
            case "3":
                self?.switchView(to: .research)
                return nil
            case "4":
                self?.switchView(to: .explorer)
                return nil
            case "5":
                self?.switchView(to: .memory)
                return nil
            case "6":
                self?.switchView(to: .settings)
                return nil
            case "\\":
                self?.mainWindowController?.toggleChatPanel(nil)
                return nil
            case "k":
                NotificationCenter.default.post(name: .hestiaCommandPaletteToggle, object: nil)
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
    @objc private func showHealthView() { switchView(to: .health) }
    @objc private func showResearchView() { switchView(to: .research) }
    @objc private func showExplorerView() { switchView(to: .explorer) }
    @objc private func showMemoryView() { switchView(to: .memory) }
    @objc private func showSettingsView() { switchView(to: .settings) }
    @objc private func toggleChatPanel() { mainWindowController?.toggleChatPanel(nil) }
}
