import SwiftUI

// MARK: - Spacing Constants

enum Spacing {
    /// Extra small: 4pt
    static let xs: CGFloat = 4

    /// Small: 8pt
    static let sm: CGFloat = 8

    /// Medium: 16pt
    static let md: CGFloat = 16

    /// Large: 24pt
    static let lg: CGFloat = 24

    /// Extra large: 32pt
    static let xl: CGFloat = 32

    /// Extra extra large: 48pt
    static let xxl: CGFloat = 48
}

// MARK: - Corner Radius Constants

enum CornerRadius {
    /// Standard corner radius: 25pt (message bubbles, cards)
    static let standard: CGFloat = 25

    /// Button corner radius: 25pt
    static let button: CGFloat = 25

    /// Card corner radius: 25pt
    static let card: CGFloat = 25

    /// Avatar corner radius: 40pt (half of 80pt avatar)
    static let avatar: CGFloat = 40

    /// Small corner radius: 12pt (badges, pills)
    static let small: CGFloat = 12

    /// Input field corner radius: 20pt
    static let input: CGFloat = 20
}

// MARK: - Size Constants

enum Size {
    /// Avatar sizes
    enum Avatar {
        static let small: CGFloat = 40
        static let medium: CGFloat = 60
        static let large: CGFloat = 80
        static let xlarge: CGFloat = 120
    }

    /// Icon sizes
    enum Icon {
        static let small: CGFloat = 16
        static let medium: CGFloat = 24
        static let large: CGFloat = 32
        static let xlarge: CGFloat = 48
    }

    /// Button heights
    enum Button {
        static let standard: CGFloat = 50
        static let small: CGFloat = 36
    }

    /// Input field height
    static let inputHeight: CGFloat = 50

    /// Tab bar height
    static let tabBarHeight: CGFloat = 83
}

// MARK: - Layout Modifiers

extension View {
    /// Standard horizontal padding
    func horizontalPadding() -> some View {
        self.padding(.horizontal, Spacing.lg)
    }

    /// Standard vertical padding
    func verticalPadding() -> some View {
        self.padding(.vertical, Spacing.md)
    }

    /// Card padding
    func cardPadding() -> some View {
        self.padding(Spacing.md)
    }

    /// Standard card style with background and corner radius
    func cardStyle() -> some View {
        self
            .padding(Spacing.md)
            .background(Color.cardBackground)
            .cornerRadius(CornerRadius.card)
    }
}
