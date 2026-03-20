import Foundation

// MARK: - Loadable State

/// Generic loading state for ViewModels. Replaces ad-hoc `isLoading` + `errorMessage`
/// patterns with a single, type-safe state machine.
///
/// Usage:
/// ```swift
/// @Published var healthState: LoadableState<SystemHealth> = .idle
///
/// func loadHealth() async {
///     healthState = .loading
///     do {
///         let data = try await APIClient.shared.getSystemHealth()
///         healthState = .loaded(data)
///     } catch {
///         healthState = .failed(error)
///     }
/// }
/// ```
enum LoadableState<T> {
    case idle
    case loading
    case loaded(T)
    case failed(Error)

    var isLoading: Bool {
        if case .loading = self { return true }
        return false
    }

    var value: T? {
        if case .loaded(let data) = self { return data }
        return nil
    }

    var error: Error? {
        if case .failed(let error) = self { return error }
        return nil
    }

    var hasLoaded: Bool {
        if case .loaded = self { return true }
        return false
    }
}
