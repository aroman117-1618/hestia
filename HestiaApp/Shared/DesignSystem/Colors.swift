import SwiftUI

extension Color {
    // MARK: - Mode Gradients (from Figma mockups)

    /// Tia (Default) - Orange/Brown gradient
    static let tiaGradientColors: [Color] = [
        Color(hex: "E0A050"),  // Light orange
        Color(hex: "A54B17"),  // Medium brown
        Color(hex: "8B3A0F")   // Dark brown
    ]

    /// Mira (Learning) - Blue gradient
    static let miraGradientColors: [Color] = [
        Color(hex: "090F26"),  // Deep navy
        Color(hex: "026DFF"),  // Electric blue
        Color(hex: "00D7FF")   // Cyan
    ]

    /// Olly (Projects) - Green gradient
    static let ollyGradientColors: [Color] = [
        Color(hex: "03624C"),  // Dark teal
        Color(hex: "187403"),  // Forest green
        Color(hex: "2CC295")   // Mint green
    ]

    // MARK: - Semantic Colors

    static let userBubbleBackground = Color.white.opacity(0.15)
    static let assistantBubbleBackground = Color.white.opacity(0.08)
    static let cardBackground = Color.white.opacity(0.1)
    static let surfaceBackground = Color.white.opacity(0.05)

    // MARK: - Cloud Provider Colors

    static let anthropicBrand = Color(hex: "D4A574")
    static let openAIBrand = Color(hex: "10A37F")
    static let googleBrand = Color(hex: "4285F4")

    // MARK: - Status Colors

    static let healthyGreen = Color(hex: "34C759")
    static let warningYellow = Color(hex: "FFCC00")
    static let errorRed = Color(hex: "FF3B30")

    // MARK: - Hex Initializer

    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3: // RGB (12-bit)
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6: // RGB (24-bit)
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: // ARGB (32-bit)
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 128, 128, 128)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}
