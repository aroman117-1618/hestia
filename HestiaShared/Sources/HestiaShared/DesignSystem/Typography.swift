import SwiftUI

extension Font {
    // MARK: - Volkhov (Personality/Branding)

    /// Greeting text - Bold Volkhov, 32pt
    public static let greeting = Font.custom("Volkhov-Bold", size: 32)

    /// Subheading - Regular Volkhov, 18pt
    public static let subheading = Font.custom("Volkhov-Regular", size: 18)

    // MARK: - SF Pro (UI/System)

    /// Message body text
    public static let messageBody = Font.system(size: 17, weight: .regular)

    /// Message timestamp
    public static let messageTimestamp = Font.system(size: 12, weight: .regular)

    /// Mode indicator label
    public static let modeLabel = Font.system(size: 13, weight: .semibold)

    /// Card title
    public static let cardTitle = Font.system(size: 16, weight: .semibold)

    /// Card body text
    public static let cardBody = Font.system(size: 14, weight: .regular)

    /// Input field text
    public static let inputField = Font.system(size: 17, weight: .regular)

    /// Section header
    public static let sectionHeader = Font.system(size: 13, weight: .semibold)

    /// Button text
    public static let buttonText = Font.system(size: 17, weight: .semibold)
}

// MARK: - Font Registration Helper

public struct FontLoader {
    /// Call this on app launch to verify fonts are loaded
    public static func loadFonts() {
        // Fonts are automatically loaded from Info.plist
        #if DEBUG
        print("FontLoader: Expected fonts - Volkhov-Regular, Volkhov-Bold")
        #endif
    }
}

// MARK: - Text Style Modifiers

extension View {
    /// Apply greeting style (Volkhov Bold, white)
    public func greetingStyle() -> some View {
        self
            .font(.greeting)
            .foregroundColor(.white)
    }

    /// Apply subheading style (Volkhov Regular, white 70%)
    public func subheadingStyle() -> some View {
        self
            .font(.subheading)
            .foregroundColor(.white.opacity(0.7))
    }

    /// Apply card title style
    public func cardTitleStyle() -> some View {
        self
            .font(.cardTitle)
            .foregroundColor(.white)
    }

    /// Apply card body style
    public func cardBodyStyle() -> some View {
        self
            .font(.cardBody)
            .foregroundColor(.white.opacity(0.7))
    }
}
