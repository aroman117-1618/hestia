import SwiftUI

// MARK: - Search Debounce

/// Debounces text changes with configurable delay. Cancels pending action on new input.
/// Use for search fields to prevent excessive recomputation during rapid typing.
struct DebouncedChangeModifier: ViewModifier {
    let text: String
    let delay: TimeInterval
    let action: (String) -> Void

    @State private var debounceTask: Task<Void, Never>?

    func body(content: Content) -> some View {
        content
            .onChange(of: text) { _, newValue in
                debounceTask?.cancel()
                debounceTask = Task {
                    try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                    guard !Task.isCancelled else { return }
                    await MainActor.run {
                        action(newValue)
                    }
                }
            }
    }
}

extension View {
    /// Debounces text changes before invoking an action.
    /// - Parameters:
    ///   - text: The text value to observe
    ///   - delay: Debounce delay in seconds (default 0.25)
    ///   - action: Closure called with the debounced text value
    func debounced(_ text: String, delay: TimeInterval = 0.25, action: @escaping (String) -> Void) -> some View {
        modifier(DebouncedChangeModifier(text: text, delay: delay, action: action))
    }
}
