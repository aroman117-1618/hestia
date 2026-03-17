import SwiftUI

// MARK: - Spacing Constants

public enum Spacing {
    /// Extra small: 4pt
    public static let xs: CGFloat = 4

    /// Small: 8pt
    public static let sm: CGFloat = 8

    /// Medium: 16pt
    public static let md: CGFloat = 16

    /// Large: 24pt
    public static let lg: CGFloat = 24

    /// Extra large: 32pt
    public static let xl: CGFloat = 32

    /// Extra extra large: 48pt
    public static let xxl: CGFloat = 48
}

// MARK: - Corner Radius Constants

public enum CornerRadius {
    /// Standard corner radius: 25pt (message bubbles, cards)
    public static let standard: CGFloat = 25

    /// Button corner radius: 25pt
    public static let button: CGFloat = 25

    /// Card corner radius: 25pt
    public static let card: CGFloat = 25

    /// Avatar corner radius: 40pt (half of 80pt avatar)
    public static let avatar: CGFloat = 40

    /// Small corner radius: 12pt (badges, pills)
    public static let small: CGFloat = 12

    /// Input field corner radius: 20pt
    public static let input: CGFloat = 20
}

// MARK: - Size Constants

public enum Size {
    /// Avatar sizes
    public enum Avatar {
        public static let small: CGFloat = 40
        public static let medium: CGFloat = 60
        public static let large: CGFloat = 80
        public static let xlarge: CGFloat = 120
    }

    /// Icon sizes
    public enum Icon {
        public static let small: CGFloat = 16
        public static let medium: CGFloat = 24
        public static let large: CGFloat = 32
        public static let xlarge: CGFloat = 48
    }

    /// Button heights
    public enum Button {
        public static let standard: CGFloat = 50
        public static let small: CGFloat = 36
    }

    /// Input field height
    public static let inputHeight: CGFloat = 50

    /// Tab bar height
    public static let tabBarHeight: CGFloat = 83
}

// MARK: - Layout Modifiers

extension View {
    /// Standard horizontal padding
    public func horizontalPadding() -> some View {
        self.padding(.horizontal, Spacing.lg)
    }

    /// Standard vertical padding
    public func verticalPadding() -> some View {
        self.padding(.vertical, Spacing.md)
    }

    /// Card padding
    public func cardPadding() -> some View {
        self.padding(Spacing.md)
    }

    /// Standard card style with background and corner radius
    public func cardStyle() -> some View {
        self
            .padding(Spacing.md)
            .background(Color.cardBackground)
            .cornerRadius(CornerRadius.card)
    }
}
