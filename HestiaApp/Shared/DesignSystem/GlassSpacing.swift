import SwiftUI

/// Liquid Glass Design System spacing tokens.
/// Use these for new/migrated views. Old `Spacing` tokens remain for unmigrated views.
public enum GlassSpacing {
    public static let xs: CGFloat = 4
    public static let sm: CGFloat = 8
    public static let md: CGFloat = 12
    public static let lg: CGFloat = 16
    public static let xl: CGFloat = 20
    public static let xxl: CGFloat = 24
    public static let xxxl: CGFloat = 32
}

/// Liquid Glass corner radii.
public enum GlassRadius {
    /// Badges, pills, input fields
    public static let sm: CGFloat = 8
    /// Buttons, list items
    public static let md: CGFloat = 12
    /// Cards, panels, popovers
    public static let lg: CGFloat = 16
    /// Modal dialogs, large containers
    public static let xl: CGFloat = 20
    /// Capsule shapes (chat input, search, nav pills)
    public static let pill: CGFloat = 9999
    /// Alias for pill — used by GlassMaterial
    public static let capsule: CGFloat = 9999
}
