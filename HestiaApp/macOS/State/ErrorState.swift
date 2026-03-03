import SwiftUI

// MARK: - App Error Model

struct AppError: Identifiable, Equatable {
    let id = UUID()
    let message: String
    let severity: Severity

    enum Severity {
        case warning
        case error
        case info
    }

    var icon: String {
        switch severity {
        case .warning: "exclamationmark.triangle.fill"
        case .error: "xmark.octagon.fill"
        case .info: "info.circle.fill"
        }
    }

    var accentColor: Color {
        switch severity {
        case .warning: MacColors.amberAccent
        case .error: MacColors.healthRed
        case .info: Color(hex: "00D7FF")
        }
    }
}

// MARK: - Error State

@MainActor
@Observable
class ErrorState {
    var currentError: AppError?
    private var dismissTask: Task<Void, Never>?

    /// Show an error that auto-dismisses after the given duration.
    func show(_ message: String, severity: AppError.Severity = .error, duration: TimeInterval = 4.0) {
        dismissTask?.cancel()
        currentError = AppError(message: message, severity: severity)

        dismissTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(duration))
            guard !Task.isCancelled else { return }
            withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                self?.currentError = nil
            }
        }
    }

    /// Manually dismiss the current error.
    func dismiss() {
        dismissTask?.cancel()
        withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
            currentError = nil
        }
    }
}
