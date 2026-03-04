import SwiftUI
import HestiaShared

// MARK: - macOS Design Tokens — Exact Figma Values

enum MacColors {
    // MARK: - Backgrounds & Surfaces (from Figma node data)
    static let windowBackground = Color(hex: "0D0802")
    static let sidebarBackground = Color(hex: "0A0603")
    static let panelBackground = Color(hex: "110B03")
    static let chatInputBackground = Color(hex: "261302")
    static let activeNavBackground = Color(hex: "2F1C03")

    // MARK: - Borders
    static let navBorder = Color(hex: "B7874A")
    static let primaryBorder = Color(red: 226/255, green: 166/255, blue: 92/255).opacity(0.8)
    static let activeNavBorder = Color(hex: "583502")
    static let cardBorder = Color(red: 254/255, green: 154/255, blue: 0).opacity(0.08)
    static let cardBorderStrong = Color(red: 254/255, green: 154/255, blue: 0).opacity(0.15)
    static let sidebarBorder = Color(red: 254/255, green: 154/255, blue: 0).opacity(0.1)
    static let subtleBorder = Color(red: 254/255, green: 154/255, blue: 0).opacity(0.06)
    static let divider = Color(red: 182/255, green: 165/255, blue: 145/255).opacity(0.15)
    static let avatarBorder = Color(red: 254/255, green: 154/255, blue: 0).opacity(0.25)
    static let aiAvatarBorder = Color(red: 182/255, green: 165/255, blue: 145/255).opacity(0.2)

    // MARK: - Accent / Brand
    static let amberAccent = Color(hex: "E0A050")
    static let amberBright = Color(hex: "FFB900")
    static let amberDark = Color(hex: "FF8904")

    // MARK: - Card Gradients
    static var cardGradient: LinearGradient {
        LinearGradient(
            colors: [
                Color(red: 70/255, green: 25/255, blue: 1/255).opacity(0.45),
                Color(red: 12/255, green: 10/255, blue: 9/255).opacity(0.35)
            ],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
    }

    static var logoGradient: LinearGradient {
        LinearGradient(
            colors: [Color(hex: "E17100"), Color(hex: "F54900")],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
    }

    static var activeIndicatorGradient: LinearGradient {
        LinearGradient(
            colors: [Color(hex: "FFB900"), Color(hex: "FF8904")],
            startPoint: .top,
            endPoint: .bottom
        )
    }

    // MARK: - Interactive Surfaces
    static let searchInputBackground = Color(red: 235/255, green: 223/255, blue: 209/255).opacity(0.08)
    static let activeTabBackground = Color(red: 238/255, green: 203/255, blue: 160/255).opacity(0.15)
    static let aiBubbleBackground = Color(red: 224/255, green: 206/255, blue: 184/255).opacity(0.12)
    static let aiAvatarBackground = Color(red: 238/255, green: 203/255, blue: 160/255).opacity(0.2)
    static let innerPillBackground = Color(red: 70/255, green: 25/255, blue: 1/255).opacity(0.2)

    // MARK: - Text Colors
    static let textPrimary = Color(hex: "E4DFD7")
    static let textPrimaryAlt = Color(hex: "EBDFD1")
    static let textSender = Color(red: 235/255, green: 223/255, blue: 209/255).opacity(0.62)
    static let textSecondary = Color(red: 235/255, green: 223/255, blue: 209/255).opacity(0.5)
    static let textPlaceholder = Color(red: 235/255, green: 223/255, blue: 209/255).opacity(0.4)
    static let textFaint = Color(red: 235/255, green: 223/255, blue: 209/255).opacity(0.3)
    static let textInactive = Color(red: 235/255, green: 223/255, blue: 209/255).opacity(0.45)
    static let userBubbleText = Color(red: 29/255, green: 14/255, blue: 1/255).opacity(0.8)
    static let userBubbleTextShort = Color(hex: "442B11")
    static let buttonTextDark = Color(hex: "040301")

    // MARK: - Health Colors
    static let healthGreen = Color(hex: "00D492")
    static let healthRed = Color(hex: "FF6467")
    static let healthGold = Color(hex: "FEE685")
    static let healthAmber = Color(hex: "FFB900")
    static let healthGreenBg = Color(hex: "00D492").opacity(0.15)
    static let healthRedBg = Color(red: 255/255, green: 100/255, blue: 103/255).opacity(0.08)
    static let healthRedBorder = Color(red: 255/255, green: 100/255, blue: 103/255).opacity(0.15)
    static let healthAmberBg = Color(hex: "FFB900").opacity(0.1)
    static let healthAmberBorder = Color(hex: "FFB900").opacity(0.2)

    // MARK: - Health Text
    static let healthGoldText = Color(red: 254/255, green: 230/255, blue: 133/255).opacity(0.5)
    static let healthAmberText = Color(red: 255/255, green: 185/255, blue: 0).opacity(0.4)
    static let healthDimText = Color(red: 255/255, green: 185/255, blue: 0).opacity(0.35)
    static let healthLabelText = Color(red: 254/255, green: 230/255, blue: 133/255).opacity(0.55)

    // MARK: - Status (semantic)
    static let statusGreen = Color(hex: "72F69E")
    static let statusWarning = Color(hex: "FF9800")
    static let statusCritical = Color(hex: "D32F2F")
    static let statusInfo = amberAccent

    // MARK: - Interactive States
    static let hoverBackground = amberAccent.opacity(0.08)
    static let pressedBackground = amberAccent.opacity(0.20)
    static let disabledForeground = Color.white.opacity(0.3)
    static let focusRing = amberAccent.opacity(0.5)

    // MARK: - Diagram Semantic Colors
    static let diagramApple = Color(hex: "007AFF")       // Apple ecosystem nodes
    static let diagramExternal = Color(hex: "007AFF")     // External/client nodes
    static let diagramCloud = Color(hex: "5AC8FA")        // Cloud provider nodes

    // MARK: - Unread Indicator
    static let unreadDot = amberBright                    // Replaces Color.blue for unread dots

    // MARK: - Animation Timing
    static let animationFast: Double = 0.15
    static let animationNormal: Double = 0.25
    static let animationSlow: Double = 0.4

    // MARK: - Mode Accents
    static func accentColor(for mode: HestiaMode) -> Color {
        switch mode {
        case .tia: return amberAccent
        case .mira: return Color(hex: "026DFF")
        case .olly: return Color(hex: "2CC295")
        }
    }
}
