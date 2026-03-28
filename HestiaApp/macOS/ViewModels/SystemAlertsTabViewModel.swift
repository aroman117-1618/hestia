import SwiftUI
import HestiaShared

/// ViewModel for the System Alerts sub-tab of Command.
/// Categorizes alerts into success, errors, and atlas (sentinel) sections.
@MainActor
class SystemAlertsTabViewModel: ObservableObject {

    // MARK: - Alert Model

    struct SystemAlert: Identifiable {
        let id = UUID()
        let icon: String
        let iconColor: Color
        let title: String
        let detail: String
        let timestamp: Date
    }

    // MARK: - Published State

    @Published var successAlerts: [SystemAlert] = []
    @Published var errorAlerts: [SystemAlert] = []
    @Published var atlasAlerts: [SystemAlert] = []
    @Published var isLoading = false

    // MARK: - Public API

    func loadData() async {
        isLoading = true
        defer { isLoading = false }

        async let orderAlerts: () = loadOrderAlerts()
        async let sentinelAlerts: () = loadSentinelAlerts()
        _ = await (orderAlerts, sentinelAlerts)
    }

    // MARK: - Order Alert Categorization

    private func loadOrderAlerts() async {
        let (response, _) = await CacheFetcher.load(
            key: CacheKey.orders,
            ttl: CacheTTL.frequent
        ) {
            try await APIClient.shared.listOrders(limit: 50)
        }

        guard let orders = response?.orders else { return }
        categorizeOrderAlerts(orders)
    }

    private func categorizeOrderAlerts(_ orders: [OrderResponse]) {
        var success: [SystemAlert] = []
        var errors: [SystemAlert] = []

        for order in orders {
            guard let execution = order.lastExecution else { continue }

            switch execution.status {
            case .success:
                success.append(SystemAlert(
                    icon: "checkmark.circle.fill",
                    iconColor: .green,
                    title: order.name,
                    detail: "Completed successfully",
                    timestamp: execution.timestamp
                ))
            case .failed:
                errors.append(SystemAlert(
                    icon: "xmark.circle.fill",
                    iconColor: .red,
                    title: order.name,
                    detail: "Execution failed",
                    timestamp: execution.timestamp
                ))
            case .scheduled, .running:
                break
            }
        }

        successAlerts = success.sorted { $0.timestamp > $1.timestamp }
        errorAlerts = errors.sorted { $0.timestamp > $1.timestamp }
    }

    // MARK: - Sentinel (Atlas) Alerts

    private func loadSentinelAlerts() async {
        // Sentinel may not be deployed — wrap in do/catch and default to empty
        do {
            let status: SentinelStatusResponse = try await APIClient.shared.get("/sentinel/status")
            var alerts: [SystemAlert] = []

            if status.healthy {
                alerts.append(SystemAlert(
                    icon: "shield.checkered",
                    iconColor: .green,
                    title: "Sentinel Active",
                    detail: "All layers operational",
                    timestamp: Date()
                ))
            } else {
                alerts.append(SystemAlert(
                    icon: "shield.slash",
                    iconColor: .red,
                    title: "Sentinel Degraded",
                    detail: "One or more layers reporting issues",
                    timestamp: Date()
                ))
            }

            atlasAlerts = alerts
        } catch {
            #if DEBUG
            print("[SystemAlertsTab] Sentinel status unavailable: \(error)")
            #endif
            atlasAlerts = []
        }
    }
}

// MARK: - Sentinel Response (local to this file — no shared model yet)

private struct SentinelStatusResponse: Codable {
    let healthy: Bool
    let layers: [String: LayerStatus]?

    struct LayerStatus: Codable {
        let status: String
    }
}
