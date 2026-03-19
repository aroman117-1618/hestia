import AppKit
import HestiaShared
import Sparkle

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
    private var updaterController: SPUStandardUpdaterController!

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Configure shared package with macOS device info
        APIClient.configure(deviceInfo: MacDeviceInfoProvider())

        // Initialize Sparkle auto-updater
        updaterController = SPUStandardUpdaterController(
            startingUpdater: true,
            updaterDelegate: nil,
            userDriverDelegate: nil
        )

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
        let checkForUpdatesItem = NSMenuItem(
            title: "Check for Updates...",
            action: #selector(checkForUpdates(_:)),
            keyEquivalent: ""
        )
        checkForUpdatesItem.target = self
        appMenu.addItem(checkForUpdatesItem)
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

        // View menu — matches sidebar order (⌘1-3 + ⌘5 settings)
        // Health tab archived — data surfaces via Internal activity feed (Sprint 25.5)
        let viewMenuItem = NSMenuItem(title: "View", action: nil, keyEquivalent: "")
        let viewMenu = NSMenu(title: "View")

        let cmdItem = NSMenuItem(title: "Command Center", action: #selector(showCommandView), keyEquivalent: "1")
        cmdItem.target = self
        viewMenu.addItem(cmdItem)

        let researchItem = NSMenuItem(title: "Research", action: #selector(showResearchView), keyEquivalent: "2")
        researchItem.target = self
        viewMenu.addItem(researchItem)

        let expItem = NSMenuItem(title: "Explorer", action: #selector(showExplorerView), keyEquivalent: "3")
        expItem.target = self
        viewMenu.addItem(expItem)

        viewMenu.addItem(.separator())

        let settingsItem = NSMenuItem(title: "Settings", action: #selector(showSettingsView), keyEquivalent: "5")
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
            // ⌘2 was Health — archived (Sprint 25.5)
            case "2":
                self?.switchView(to: .research)
                return nil
            case "3":
                self?.switchView(to: .explorer)
                return nil
            case "5":
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

    @objc private func checkForUpdates(_ sender: Any?) {
        updaterController.checkForUpdates(nil)
    }

    @objc private func showCommandView() { switchView(to: .command) }
    @objc private func showHealthView() { switchView(to: .health) }
    @objc private func showResearchView() { switchView(to: .research) }
    @objc private func showExplorerView() { switchView(to: .explorer) }
    @objc private func showSettingsView() { switchView(to: .settings) }
    @objc private func toggleChatPanel() { mainWindowController?.toggleChatPanel(nil) }
}
