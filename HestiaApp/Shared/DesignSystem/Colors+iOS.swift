import SwiftUI
import HestiaShared

/// iOS-specific color tokens for the refreshed mobile UI.
/// Extends the base HestiaShared color palette with card, agent, and status colors.
extension Color {
    // MARK: - Card Colors (Liquid Glass)

    /// Card background — bg.elevated
    static let iosCardBackground = Color(hex: "110B03")
    /// Card border — border.subtle (amber-tinted)
    static let iosCardBorder = Color(hex: "FF9F0A").opacity(0.06)

    // MARK: - Primary Accent

    /// Primary amber accent — canonical Hestia amber
    static let accent = Color(hex: "FF9F0A")

    // MARK: - Agent Colors (deprecated — use .accent)

    /// Hestia — conversation, voice mode
    @available(*, deprecated, renamed: "accent")
    static let agentAmber = Color(hex: "FF9F0A")
    /// Artemis — deprecated, use .accent
    @available(*, deprecated, message: "Agent colors removed — use .accent")
    static let agentTeal = Color(hex: "FF9F0A")
    /// Apollo — deprecated, use .accent
    @available(*, deprecated, message: "Agent colors removed — use .accent")
    static let agentPurple = Color(hex: "FF9F0A")

    // MARK: - System Blue

    /// iOS system blue for info state
    static let systemBlue = Color(hex: "0A84FF")

    // MARK: - Liquid Glass Text Tokens

    static let textPrimary = Color(hex: "E8E2D9")
    static let textSecondary = Color(hex: "E8E2D9").opacity(0.55)
    static let textTertiary = Color(hex: "E8E2D9").opacity(0.35)
    static let textInverse = Color(hex: "1A1005")
    static let textLink = Color(hex: "FF9F0A")

    // MARK: - Liquid Glass Background Tiers

    static let bgBase = Color(hex: "080503")
    static let bgSurface = Color(hex: "0D0802")
    static let bgElevated = Color(hex: "110B03")
    static let bgOverlay = Color(hex: "1A1005")
    static let bgInput = Color(hex: "1E1308")

    // MARK: - Liquid Glass Status

    static let statusHealthy = Color(hex: "34C759")
    static let statusWarning = Color(hex: "FF9F0A")
    static let statusError = Color(hex: "FF453A")
    static let statusInfo = Color(hex: "0A84FF")
    static let statusNeutral = Color(hex: "8E8E93")
}
