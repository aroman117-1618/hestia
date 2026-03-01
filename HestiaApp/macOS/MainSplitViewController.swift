import AppKit
import SwiftUI
import HestiaShared

class MainSplitViewController: NSSplitViewController {
    private let mainItem: NSSplitViewItem
    private let chatItem: NSSplitViewItem

    private let workspaceState = WorkspaceState()
    private let appState = AppState()
    private let authService = AuthService()

    override init(nibName nibNameOrNil: NSNib.Name?, bundle nibBundleOrNil: Bundle?) {
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

        super.init(nibName: nibNameOrNil, bundle: nibBundleOrNil)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()

        splitView.isVertical = true
        splitView.dividerStyle = .thin

        addSplitViewItem(mainItem)
        addSplitViewItem(chatItem)
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
        NSAnimationContext.runAnimationGroup { context in
            context.duration = 0.25
            context.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
            chatItem.animator().isCollapsed.toggle()
        }
        workspaceState.isChatPanelVisible = !chatItem.isCollapsed
    }
}
