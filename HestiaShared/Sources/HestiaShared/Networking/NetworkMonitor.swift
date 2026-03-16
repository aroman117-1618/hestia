import Foundation
import Network

/// Monitors network connectivity
@MainActor
public class NetworkMonitor: ObservableObject, @unchecked Sendable {
    // MARK: - Published State

    @Published public private(set) var isConnected: Bool = true
    @Published public private(set) var connectionType: ConnectionType = .unknown

    // MARK: - Types

    public enum ConnectionType: Sendable {
        case wifi
        case cellular
        case ethernet
        case unknown

        public var displayName: String {
            switch self {
            case .wifi: return "Wi-Fi"
            case .cellular: return "Cellular"
            case .ethernet: return "Ethernet"
            case .unknown: return "Unknown"
            }
        }

        public var iconName: String {
            switch self {
            case .wifi: return "wifi"
            case .cellular: return "antenna.radiowaves.left.and.right"
            case .ethernet: return "cable.connector"
            case .unknown: return "questionmark.circle"
            }
        }
    }

    // MARK: - Private

    private let monitor = NWPathMonitor()
    private let queue = DispatchQueue(label: "NetworkMonitor")

    // MARK: - Initialization

    public init() {
        startMonitoring()
    }

    nonisolated deinit {
        monitor.cancel()
    }

    // MARK: - Public Methods

    /// Start monitoring network changes
    public func startMonitoring() {
        monitor.pathUpdateHandler = { [weak self] path in
            Task { @MainActor in
                self?.updateStatus(path)
            }
        }
        monitor.start(queue: queue)
    }

    /// Stop monitoring network changes
    public func stopMonitoring() {
        monitor.cancel()
    }

    // MARK: - Private Methods

    private func updateStatus(_ path: NWPath) {
        isConnected = path.status == .satisfied

        if path.usesInterfaceType(.wifi) {
            connectionType = .wifi
        } else if path.usesInterfaceType(.cellular) {
            connectionType = .cellular
        } else if path.usesInterfaceType(.wiredEthernet) {
            connectionType = .ethernet
        } else {
            connectionType = .unknown
        }
    }
}
