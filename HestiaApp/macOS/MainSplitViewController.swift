import AppKit
import SwiftUI
import HestiaShared

class MainSplitViewController: NSSplitViewController, NSWindowDelegate {
    private var mainItem: NSSplitViewItem!
    private var chatItem: NSSplitViewItem!
    private var onboardingItem: NSSplitViewItem?

    private let workspaceState = WorkspaceState()
    private let appState = AppState()
    private let errorState = ErrorState()
    private let commandPaletteState = CommandPaletteState()
    private let networkMonitor = NetworkMonitor()
    private let authService = AuthService()
    private var registrationObserver: NSObjectProtocol?
    private nonisolated(unsafe) var chatToggleObserver: NSObjectProtocol?
    private nonisolated(unsafe) var detachObserver: NSObjectProtocol?
    private var detachedChatWindow: NSWindow?

    override init(nibName nibNameOrNil: NSNib.Name?, bundle nibBundleOrNil: Bundle?) {
        super.init(nibName: nibNameOrNil, bundle: nibBundleOrNil)

        if authService.isDeviceRegistered {
            setupWorkspaceLayout()
        } else {
            setupOnboardingLayout()
            // Watch for registration to complete
            registrationObserver = NotificationCenter.default.addObserver(
                forName: .hestiaConfigurationChanged,
                object: nil,
                queue: .main
            ) { [weak self] _ in
                Task { @MainActor in
                    guard let self = self, self.authService.isDeviceRegistered else { return }
                    self.transitionToWorkspace()
                }
            }
        }
    }

    private func setupWorkspaceLayout() {
        // Load stored device token into APIClient before any views make API calls.
        // Without this, all initial requests get 401 and race on auto-reregistration.
        if let token = authService.getDeviceToken() {
            APIClient.shared.setDeviceToken(token)
        }

        // Main content: icon sidebar + content area
        let rootView = WorkspaceRootView()
            .environment(workspaceState)
            .environment(errorState)
            .environment(commandPaletteState)
            .environmentObject(appState)
            .environmentObject(networkMonitor)
        let mainHost = NSHostingController(rootView: rootView)
        mainItem = NSSplitViewItem(contentListWithViewController: mainHost)
        mainItem.minimumThickness = 600

        // Chat panel (520px from Figma)
        let chatView = MacChatPanelView()
            .environment(workspaceState)
            .environmentObject(appState)
            .environmentObject(networkMonitor)
        let chatHost = NSHostingController(rootView: chatView)
        chatItem = NSSplitViewItem(contentListWithViewController: chatHost)
        chatItem.minimumThickness = 340
        chatItem.maximumThickness = MacSize.chatPanelWidth + 30
        chatItem.canCollapse = true
        chatItem.collapseBehavior = .preferResizingSplitViewWithFixedSiblings
    }

    private func setupOnboardingLayout() {
        let onboardingView = MacOnboardingView(authService: authService)
        let host = NSHostingController(rootView: onboardingView)
        onboardingItem = NSSplitViewItem(viewController: host)
    }

    private func transitionToWorkspace() {
        if let observer = registrationObserver {
            NotificationCenter.default.removeObserver(observer)
            registrationObserver = nil
        }

        // Remove onboarding
        if let item = onboardingItem {
            removeSplitViewItem(item)
            onboardingItem = nil
        }

        // Set up and add workspace
        setupWorkspaceLayout()
        addSplitViewItem(mainItem)
        addSplitViewItem(chatItem)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()

        splitView.isVertical = true
        splitView.dividerStyle = .thin

        if let item = onboardingItem {
            addSplitViewItem(item)
        } else {
            addSplitViewItem(mainItem)
            addSplitViewItem(chatItem)

            // Restore persisted panel state
            if !workspaceState.isChatPanelVisible {
                chatItem.isCollapsed = true
            }
        }

        // Bridge: SwiftUI ChatToggleButton → AppKit panel toggle
        chatToggleObserver = NotificationCenter.default.addObserver(
            forName: .hestiaChatPanelToggle,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            self?.toggleChatPanel()
        }

        // Bridge: SwiftUI double-click → detach chat to standalone window
        detachObserver = NotificationCenter.default.addObserver(
            forName: .hestiaChatPanelDetach,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            self?.detachChatPanel()
        }
    }

    deinit {
        if let observer = chatToggleObserver {
            NotificationCenter.default.removeObserver(observer)
        }
        if let observer = detachObserver {
            NotificationCenter.default.removeObserver(observer)
        }
        detachedChatWindow?.close()
        detachedChatWindow = nil
    }

    // MARK: - Divider Hit Area

    override func splitView(
        _ splitView: NSSplitView,
        effectiveRect proposedEffectiveRect: NSRect,
        forDrawnRect drawnRect: NSRect,
        ofDividerAt dividerIndex: Int
    ) -> NSRect {
        var rect = proposedEffectiveRect
        rect.origin.x -= 4
        rect.size.width = 9
        return rect
    }

    // MARK: - Panel Toggle

    func toggleChatPanel() {
        guard chatItem != nil else { return }

        // If chat is detached, bring the detached window to front instead of toggling
        if workspaceState.isChatDetached, let window = detachedChatWindow {
            window.makeKeyAndOrderFront(nil)
            return
        }

        NSAnimationContext.runAnimationGroup { context in
            context.duration = 0.25
            context.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
            chatItem.animator().isCollapsed.toggle()
        }
        workspaceState.chatMode = chatItem.isCollapsed ? .hidden : .sidebar
    }

    // MARK: - Chat Panel Detach/Re-dock

    private func detachChatPanel() {
        // If already detached, just bring to front
        if let existingWindow = detachedChatWindow {
            existingWindow.makeKeyAndOrderFront(nil)
            return
        }

        guard chatItem != nil else { return }

        // Collapse the chat panel in the split view (hide from main window)
        if !chatItem.isCollapsed {
            NSAnimationContext.runAnimationGroup { context in
                context.duration = 0.25
                context.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
                chatItem.animator().isCollapsed = true
            }
        }

        // Create a new NSWindow for the detached chat
        let detachedWindow = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 480, height: 700),
            styleMask: [.titled, .closable, .resizable, .miniaturizable],
            backing: .buffered,
            defer: false
        )
        detachedWindow.minSize = NSSize(width: 400, height: 500)
        detachedWindow.title = "Hestia Chat"
        detachedWindow.titleVisibility = .hidden
        detachedWindow.titlebarAppearsTransparent = true
        detachedWindow.backgroundColor = NSColor(red: 13/255, green: 8/255, blue: 2/255, alpha: 1)
        detachedWindow.setFrameAutosaveName("HestiaChatDetached")
        detachedWindow.isReleasedWhenClosed = false

        // Create a new hosting controller with same environment objects (Option 3: fresh VM is fine)
        let chatView = MacChatPanelView()
            .environment(workspaceState)
            .environmentObject(appState)
            .environmentObject(networkMonitor)
        let chatHost = NSHostingController(rootView: chatView)
        detachedWindow.contentViewController = chatHost

        // Make it a child of the main window so closing main cascades
        if let mainWindow = view.window {
            mainWindow.addChildWindow(detachedWindow, ordered: .above)
        }

        // Register as delegate to detect close
        detachedWindow.delegate = self

        // Update state
        workspaceState.chatMode = .detached
        detachedChatWindow = detachedWindow

        // Position near the right edge of the main window if no saved frame
        if !detachedWindow.setFrameUsingName("HestiaChatDetached"),
           let mainFrame = view.window?.frame {
            let x = mainFrame.maxX + 8
            let y = mainFrame.origin.y
            detachedWindow.setFrameOrigin(NSPoint(x: x, y: y))
        }

        detachedWindow.makeKeyAndOrderFront(nil)
    }

    // MARK: - NSWindowDelegate (detached chat window lifecycle)

    func windowWillClose(_ notification: Notification) {
        guard let closingWindow = notification.object as? NSWindow,
              closingWindow === detachedChatWindow else { return }

        // Re-dock: uncollapse the chat panel in the split view
        detachedChatWindow = nil

        guard chatItem != nil else {
            workspaceState.chatMode = .hidden
            return
        }

        NSAnimationContext.runAnimationGroup { context in
            context.duration = 0.25
            context.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
            chatItem.animator().isCollapsed = false
        }
        workspaceState.chatMode = .sidebar
    }

}
