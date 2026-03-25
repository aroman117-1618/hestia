import SwiftUI
import HestiaShared

/// iOS-specific color tokens for the refreshed mobile UI.
/// Extends the base HestiaShared color palette with card, agent, and status colors.
extension Color {
    // MARK: - Card Colors

    /// Card background for mobile command and settings cards
    static let iosCardBackground = Color(hex: "1C1C1E")
    /// Card border for subtle definition
    static let iosCardBorder = Color(hex: "2C2C2E")

    // MARK: - Agent Colors

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
