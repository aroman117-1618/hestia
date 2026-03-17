import SwiftUI

/// Centralized app state shared across all views via EnvironmentObject.
///
/// This resolves the issue where each ViewModel had its own `currentMode` property
/// that was never synchronized across tabs.
@MainActor
public class AppState: ObservableObject {
    /// The currently active Hestia mode/persona
    @Published public var currentMode: HestiaMode = .tia

    public init() {}

    /// Switch to a new mode with animation
    /// - Parameter mode: The new mode to switch to
    public func switchMode(to mode: HestiaMode) {
        withAnimation(.easeInOut(duration: 0.3)) {
            currentMode = mode
        }
    }

    /// Detect mode switch requests from message text (e.g., "@mira" or "@olly")
    /// - Parameter text: The message text to scan
    /// - Returns: The detected mode, or nil if no mode trigger found
    public func detectModeFromText(_ text: String) -> HestiaMode? {
        let lowercased = text.lowercased().trimmingCharacters(in: .whitespaces)

        for mode in HestiaMode.allCases {
            if lowercased.hasPrefix(mode.invokePattern) || lowercased == mode.invokePattern {
                return mode
            }
        }

        return nil
    }
}
