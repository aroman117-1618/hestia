import SwiftUI

// MARK: - macOS Spacing & Sizing — Liquid Glass Design System

enum MacSpacing {
    static let xs: CGFloat = 4
    static let sm: CGFloat = 8
    static let md: CGFloat = 12
    static let lg: CGFloat = 16
    static let xl: CGFloat = 20
    static let xxl: CGFloat = 24
    static let xxxl: CGFloat = 32
}

enum MacCornerRadius {
    static let panel: CGFloat = 16
    static let md: CGFloat = 12
    static let navIcon: CGFloat = 14
    static let tab: CGFloat = 10
    static let search: CGFloat = 8
    static let treeItem: CGFloat = 8
    static let chatBubble: CGFloat = 16
    static let chatInput: CGFloat = 28
    static let sendButton: CGFloat = 16
    static let gene: CGFloat = 14
    static let xl: CGFloat = 20
}

enum MacSize {
    // MARK: - Layout Zones (Liquid Glass spec §4.3)
    static let iconSidebarWidth: CGFloat = 64
    static let chatPanelWidth: CGFloat = 480
    static let chatWindowWidth: CGFloat = 480
    static let fileSidebarWidth: CGFloat = 260
    static let zoneGap: CGFloat = 13
    static let windowPadding: CGFloat = 23
    static let topNavHeight: CGFloat = 44
    static let commandPaletteWidth: CGFloat = 520
    static let commandPaletteHeight: CGFloat = 400

    // MARK: - Sidebar (spec §5.2)
    static let logoSize: CGFloat = 28
    static let navIconButton: CGFloat = 36
    static let navIcon: CGFloat = 20
    static let activeIndicatorWidth: CGFloat = 3
    static let activeIndicatorHeight: CGFloat = 14

    // MARK: - Content
    static let progressRingSize: CGFloat = 100
    static let statCardWidth: CGFloat = 176
    static let statCardHeight: CGFloat = 145
    static let statCardIconCircle: CGFloat = 40
    static let calendarDayWidth: CGFloat = 98
    static let feedItemHeight: CGFloat = 58
    static let feedItemIconSize: CGFloat = 32
    static let statusDotSize: CGFloat = 8
    static let eventDotSize: CGFloat = 5
    static let activeDayCircle: CGFloat = 28
    static let orderCardWidth: CGFloat = 278
    static let orderProgressHeight: CGFloat = 4

    // MARK: - File Tree
    static let treeItemHeight: CGFloat = 32
    static let treeIndent: CGFloat = 20
    static let treeChevronSize: CGFloat = 20
    static let treeIconSize: CGFloat = 20
    static let searchBarHeight: CGFloat = 32

    // MARK: - Chat
    static let chatAvatarSize: CGFloat = 32
    static let agentTabAvatarSize: CGFloat = 24
    static let sendButtonSize: CGFloat = 32
    static let reactionIconSize: CGFloat = 16
    static let chatBubbleMaxWidth: CGFloat = 600

    // MARK: - User Avatar
    static let userAvatarSize: CGFloat = 32

    // MARK: - Profile
    static let profilePhotoSize: CGFloat = 80
    static let agentCardWidth: CGFloat = 200
    static let agentCardHeight: CGFloat = 180
    static let settingsMaxWidth: CGFloat = 720
}

// MARK: - Animation Timing Tokens (spec §7.1)

enum MacAnimation {
    static let fast: Double = 0.15
    static let normal: Double = 0.25
    static let slow: Double = 0.4
    static let gentle: Double = 0.6
    static let orb: Double = 4.0

    static var fastSpring: Animation {
        .spring(response: 0.2, dampingFraction: 0.85)
    }

    static var normalSpring: Animation {
        .spring(response: 0.3, dampingFraction: 0.8)
    }

    static var slowSpring: Animation {
        .spring(response: 0.45, dampingFraction: 0.75)
    }

    static var gentleEase: Animation {
        .easeInOut(duration: gentle)
    }
}
