import AppKit
import SwiftUI
import HestiaShared

class MainSplitViewController: NSSplitViewController {
    private let sidebarItem: NSSplitViewItem
    private let canvasItem: NSSplitViewItem
    private let chatItem: NSSplitViewItem

    @MainActor
    private let selectedTab = SelectedTab()

    override init(nibName nibNameOrNil: NSNib.Name?, bundle nibBundleOrNil: Bundle?) {
        // Sidebar
        let sidebarView = SidebarView(selectedTab: selectedTab)
        let sidebarHost = NSHostingController(rootView: sidebarView)
        sidebarItem = NSSplitViewItem(sidebarWithViewController: sidebarHost)
        sidebarItem.minimumThickness = 200
        sidebarItem.maximumThickness = 400
        sidebarItem.canCollapse = true
        sidebarItem.collapseBehavior = .preferResizingSplitViewWithFixedSiblings

        // Canvas
        let canvasView = CanvasView(selectedTab: selectedTab)
        let canvasHost = NSHostingController(rootView: canvasView)
        canvasItem = NSSplitViewItem(contentListWithViewController: canvasHost)
        canvasItem.minimumThickness = 400

        // Chat panel
        let chatView = ChatPanelView()
        let chatHost = NSHostingController(rootView: chatView)
        chatItem = NSSplitViewItem(contentListWithViewController: chatHost)
        chatItem.minimumThickness = 280
        chatItem.maximumThickness = 500
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

        addSplitViewItem(sidebarItem)
        addSplitViewItem(canvasItem)
        addSplitViewItem(chatItem)
    }

    // MARK: - Panel Toggle

    func toggleSidebar() {
        NSAnimationContext.runAnimationGroup { context in
            context.duration = 0.25
            context.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
            sidebarItem.animator().isCollapsed.toggle()
        }
    }

    func toggleChatPanel() {
        NSAnimationContext.runAnimationGroup { context in
            context.duration = 0.25
            context.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
            chatItem.animator().isCollapsed.toggle()
        }
    }
}
