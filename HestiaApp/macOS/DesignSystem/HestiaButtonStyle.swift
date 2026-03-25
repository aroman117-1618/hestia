import SwiftUI

// MARK: - Standard Button Style

/// Reusable button style with press animation, expanded hit target, and hover feedback.
/// Replaces `.buttonStyle(.plain)` across the app for consistent interaction feel.
struct HestiaButtonStyle: ButtonStyle {
    var expandHitTarget: Bool = true

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.96 : 1.0)
            .animation(MacAnimation.fastSpring, value: configuration.isPressed)
            .contentShape(expandHitTarget ? .rect : .rect)
    }
}

// MARK: - Navigation Icon Button Style

/// Variant for sidebar nav icons — expands 40pt visual to 44pt+ hit area,
/// preserves existing indicator pill and icon styling.
struct HestiaNavButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.94 : 1.0)
            .animation(MacAnimation.fastSpring, value: configuration.isPressed)
            .padding(2) // Expand 40pt → 44pt hit area
            .contentShape(Rectangle())
    }
}

// MARK: - Icon Action Button Style

/// For small icon-only buttons (reactions, close, clear) — subtle press feedback.
struct HestiaIconButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.90 : 1.0)
            .opacity(configuration.isPressed ? 0.85 : 1.0)
            .animation(MacAnimation.fastSpring, value: configuration.isPressed)
            .contentShape(Rectangle())
    }
}

// MARK: - Convenience Extensions

extension ButtonStyle where Self == HestiaButtonStyle {
    static var hestia: HestiaButtonStyle { HestiaButtonStyle() }
    static var hestiaCompact: HestiaButtonStyle { HestiaButtonStyle(expandHitTarget: false) }
}

extension ButtonStyle where Self == HestiaNavButtonStyle {
    static var hestiaNav: HestiaNavButtonStyle { HestiaNavButtonStyle() }
}

extension ButtonStyle where Self == HestiaIconButtonStyle {
    static var hestiaIcon: HestiaIconButtonStyle { HestiaIconButtonStyle() }
}
