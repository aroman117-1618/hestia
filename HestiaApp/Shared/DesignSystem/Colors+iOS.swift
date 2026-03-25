import SwiftUI
import HestiaShared

/// iOS Liquid Glass Design System color tokens.
/// Extends the base HestiaShared color palette with semantic tokens.
extension Color {
    // MARK: - Primary Accent

    /// Primary amber accent — #FF9F0A
    static let accent = Color(hex: "FF9F0A")

    // MARK: - Text Colors

    /// Primary text — warm cream #E8E2D9
    static let textPrimary = Color(hex: "E8E2D9")
    /// Secondary text — warm cream @ 55% (#807B74 equivalent)
    static let textSecondary = Color(hex: "807B74")
    /// Tertiary text — warm cream @ 35% (#514E4A equivalent)
    static let textTertiary = Color(hex: "514E4A")
    /// Inverse text for light backgrounds — #1A1005
    static let textInverse = Color(hex: "1A1005")
    /// Link text — amber accent
    static let textLink = Color(hex: "FF9F0A")

    // MARK: - Background Colors

    /// Base background — near-black warm #080503
    static let bgBase = Color(hex: "080503")
    /// Surface background — slightly lighter #0D0802
    static let bgSurface = Color(hex: "0D0802")
    /// Elevated background — card level #110B03
    static let bgElevated = Color(hex: "110B03")
    /// Overlay background — #1A1005
    static let bgOverlay = Color(hex: "1A1005")
    /// Input field background — #1E1308
    static let bgInput = Color(hex: "1E1308")

    // MARK: - Status Colors

    /// Healthy / success green
    static let statusHealthy = Color(hex: "34C759")
    /// Warning — amber accent
    static let statusWarning = Color(hex: "FF9F0A")
    /// Error — iOS red
    static let statusError = Color(hex: "FF453A")
    /// Info — iOS blue
    static let statusInfo = Color(hex: "0A84FF")
    /// Neutral — iOS gray
    static let statusNeutral = Color(hex: "8E8E93")

    // MARK: - Card Colors

    /// Card background for mobile command and settings cards (alias of bgElevated)
    static let iosCardBackground = Color(hex: "110B03")
    /// Card border — subtle amber tint (#1A1408 equivalent)
    static let iosCardBorder = Color(hex: "1A1408")

    // MARK: - Legacy Agent Colors (kept for backend compatibility)

    /// Hestia — conversation, voice mode
    static let agentAmber = Color(hex: "FF9F0A")
    /// Artemis — analysis, journal, transcription
    static let agentTeal = Color(hex: "30D5C8")
    /// Apollo — execution, projects
    static let agentPurple = Color(hex: "BF5AF2")

    // MARK: - System Blue

    /// iOS system blue for chat mode
    static let systemBlue = Color(hex: "0A84FF")
}
