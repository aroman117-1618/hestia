import SwiftUI

// MARK: - Accessibility Helpers

/// Centralized accessibility labels for Hestia interactive elements.
/// Ensures consistent VoiceOver experience across the app.

extension View {
    /// Apply standard accessibility for a navigation icon button.
    func navIconAccessibility(for view: WorkspaceView, shortcutIndex: Int) -> some View {
        self
            .accessibilityLabel(view.accessibilityLabel)
            .accessibilityHint("Keyboard shortcut: Command \(shortcutIndex)")
            .accessibilityAddTraits(.isButton)
    }

    /// Apply standard accessibility for an action button.
    func actionButtonAccessibility(title: String, hint: String? = nil) -> some View {
        self
            .accessibilityLabel(title)
            .accessibilityHint(hint ?? "")
            .accessibilityAddTraits(.isButton)
    }

    /// Apply standard accessibility for a search field.
    func searchFieldAccessibility(context: String = "content") -> some View {
        self
            .accessibilityLabel("Search \(context)")
            .accessibilityAddTraits(.isSearchField)
    }
}

// MARK: - WorkspaceView Accessibility

extension WorkspaceView {
    var accessibilityLabel: String {
        switch self {
        case .command: "Command Center"
        case .health: "Vitals"
        case .research: "Memory"
        case .explorer: "Explorer"
        case .workflow: "Orders"
        case .settings: "Settings"
        }
    }
}
