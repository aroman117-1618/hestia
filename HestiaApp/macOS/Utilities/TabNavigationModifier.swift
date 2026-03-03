import SwiftUI

// MARK: - Tab Navigation Focus Areas

/// Enables keyboard Tab/Shift+Tab cycling through focusable areas within a view.
/// Wraps SwiftUI FocusState for consistent tab-order management.
///
/// Usage:
///   enum ChatFocus: Hashable, CaseIterable { case input, sendButton, modeToggle }
///
///   @FocusState private var focus: ChatFocus?
///
///   TextField(...)
///       .focused($focus, equals: .input)
///       .tabFocusOrder($focus, area: .input)
///
/// Tab cycles forward through CaseIterable order; Shift+Tab cycles backward.
struct TabFocusModifier<FocusArea: Hashable & CaseIterable>: ViewModifier where FocusArea.AllCases: RandomAccessCollection {
    @FocusState.Binding var focus: FocusArea?
    let area: FocusArea

    func body(content: Content) -> some View {
        content
            .focused($focus, equals: area)
            .onKeyPress(.tab, phases: .down) { keyPress in
                advanceFocus(reverse: keyPress.modifiers.contains(.shift))
                return .handled
            }
    }

    private func advanceFocus(reverse: Bool) {
        let all = Array(FocusArea.allCases)
        guard let current = focus,
              let index = all.firstIndex(of: current) else {
            focus = all.first
            return
        }

        let nextIndex: Int
        if reverse {
            nextIndex = (index - 1 + all.count) % all.count
        } else {
            nextIndex = (index + 1) % all.count
        }
        focus = all[nextIndex]
    }
}

extension View {
    /// Attach tab-cycling focus to this view within a FocusState-driven group.
    func tabFocusOrder<F: Hashable & CaseIterable>(
        _ focus: FocusState<F?>.Binding,
        area: F
    ) -> some View where F.AllCases: RandomAccessCollection {
        modifier(TabFocusModifier(focus: focus, area: area))
    }
}
