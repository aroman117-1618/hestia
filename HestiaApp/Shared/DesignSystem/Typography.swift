import SwiftUI

extension Font {
    // MARK: - Volkhov (Personality/Branding)

    /// Greeting text - Bold Volkhov, 32pt
    static let greeting = Font.custom("Volkhov-Bold", size: 32)

    /// Subheading - Regular Volkhov, 18pt
    static let subheading = Font.custom("Volkhov-Regular", size: 18)

    // MARK: - SF Pro (UI/System)

    /// Message body text
    static let messageBody = Font.system(size: 17, weight: .regular)

    /// Message timestamp
    static let messageTimestamp = Font.system(size: 12, weight: .regular)

    /// Mode indicator label
    static let modeLabel = Font.system(size: 13, weight: .semibold)

    /// Card title
    static let cardTitle = Font.system(size: 16, weight: .semibold)

    /// Card body text
    static let cardBody = Font.system(size: 14, weight: .regular)

    /// Input field text
    static let inputField = Font.system(size: 17, weight: .regular)

    /// Section header
    static let sectionHeader = Font.system(size: 13, weight: .semibold)

    /// Button text
    static let buttonText = Font.system(size: 17, weight: .semibold)
}

// MARK: - Font Registration Helper

struct FontLoader {
    /// Call this on app launch to verify fonts are loaded
    /// Volkhov fonts must be added to project + Info.plist
    /// Download from Google Fonts: https://fonts.google.com/specimen/Volkhov
    /// Add to "Fonts provided by application" in Info.plist:
    ///   - Volkhov-Regular.ttf
    ///   - Volkhov-Bold.ttf
    static func loadFonts() {
        // Fonts are automatically loaded from Info.plist
        // This function exists for documentation and potential future manual loading
        #if DEBUG
        print("FontLoader: Expected fonts - Volkhov-Regular, Volkhov-Bold")
        #endif
    }
}

// MARK: - Text Style Modifiers

extension View {
    /// Apply greeting style (Volkhov Bold, white)
    func greetingStyle() -> some View {
        self
            .font(.greeting)
            .foregroundColor(.white)
    }

    /// Apply subheading style (Volkhov Regular, white 70%)
    func subheadingStyle() -> some View {
        self
            .font(.subheading)
            .foregroundColor(.white.opacity(0.7))
    }

    /// Apply card title style
    func cardTitleStyle() -> some View {
        self
            .font(.cardTitle)
            .foregroundColor(.white)
    }

    /// Apply card body style
    func cardBodyStyle() -> some View {
        self
            .font(.cardBody)
            .foregroundColor(.white.opacity(0.7))
    }
}
