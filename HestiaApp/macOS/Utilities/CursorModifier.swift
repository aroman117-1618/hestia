import SwiftUI
import AppKit

// MARK: - Cursor Feedback

/// Provides cursor feedback (pointing hand) on interactive regions.
/// macOS only — silently ignored on other platforms.
struct HoverCursorModifier: ViewModifier {
    let cursor: NSCursor

    func body(content: Content) -> some View {
        content
            .onHover { hovering in
                if hovering {
                    cursor.push()
                } else {
                    NSCursor.pop()
                }
            }
    }
}

extension View {
    /// Show a pointing-hand cursor on hover — use on clickable rows, toggles, nav items.
    func hoverCursor(_ cursor: NSCursor = .pointingHand) -> some View {
        modifier(HoverCursorModifier(cursor: cursor))
    }
}
