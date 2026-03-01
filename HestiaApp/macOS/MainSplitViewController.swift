import AppKit
import SwiftUI
import HestiaShared

class MainSplitViewController: NSSplitViewController {
    private var mainItem: NSSplitViewItem!
    private var chatItem: NSSplitViewItem!
    private var onboardingItem: NSSplitViewItem?

    private let workspaceState = WorkspaceState()
    private let appState = AppState()
    private let authService = AuthService()
    private var registrationObserver: NSObjectProtocol?

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
            .environmentObject(appState)
        let mainHost = NSHostingController(rootView: rootView)
        mainItem = NSSplitViewItem(contentListWithViewController: mainHost)
        mainItem.minimumThickness = 600

        // Chat panel (520px from Figma)
        let chatView = MacChatPanelView()
            .environment(workspaceState)
            .environmentObject(appState)
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
        }
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
        NSAnimationContext.runAnimationGroup { context in
            context.duration = 0.25
            context.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
            chatItem.animator().isCollapsed.toggle()
        }
        workspaceState.isChatPanelVisible = !chatItem.isCollapsed
    }

}
