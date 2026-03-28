import SwiftUI
import HestiaShared

/// ViewModel for the Newsfeed sub-tab of Command.
/// Loads trading data, orders, and investigations with lookback filtering.
@MainActor
class NewsfeedTabViewModel: ObservableObject {

    // MARK: - Lookback Period

    enum LookbackPeriod: String, CaseIterable, Identifiable {
        case twentyFourHour = "24H"
        case sevenDay = "7D"
        case thirtyDay = "30D"
        case all = "ALL"

        var id: String { rawValue }

        var displayName: String { rawValue }
    }

    // MARK: - Published State

    @Published var tradingSummary: TradingSummary?
    @Published var positions: [TradingPositionEntry] = []
    @Published var bots: [TradingBotResponse] = []
    @Published var orders: [OrderResponse] = []
    @Published var investigations: [Investigation] = []
    @Published var lookbackPeriod: LookbackPeriod = .twentyFourHour
    @Published var isLoading = false

    // MARK: - Public API

    func loadData() async {
        isLoading = true
        defer { isLoading = false }

        async let trading: () = loadTrading()
        async let fetchOrders: () = loadOrders()
        async let fetchInvestigations: () = loadInvestigations()
        _ = await (trading, fetchOrders, fetchInvestigations)
    }

    // MARK: - Trading

    private func loadTrading() async {
        let (summary, _) = await CacheFetcher.load(
            key: CacheKey.tradingSummary,
            ttl: CacheTTL.realtime
        ) {
            try await APIClient.shared.getTradingSummary()
        }
        tradingSummary = summary

        let (positionsResponse, _) = await CacheFetcher.load(
            key: CacheKey.tradingPositions,
            ttl: CacheTTL.realtime
        ) {
            try await APIClient.shared.getTradingPositions()
        }
        positions = positionsResponse.map { Array($0.positions.values) } ?? []

        let (botsResponse, _) = await CacheFetcher.load(
            key: CacheKey.tradingBots,
            ttl: CacheTTL.frequent
        ) {
            try await APIClient.shared.getTradingBots()
        }
        bots = botsResponse?.bots ?? []
    }

    // MARK: - Orders

    private func loadOrders() async {
        let (response, _) = await CacheFetcher.load(
            key: CacheKey.orders,
            ttl: CacheTTL.frequent
        ) {
            try await APIClient.shared.listOrders(limit: 20)
        }
        orders = response?.orders ?? []
    }

    // MARK: - Investigations

    private func loadInvestigations() async {
        let (response, _) = await CacheFetcher.load(
            key: CacheKey.investigations,
            ttl: CacheTTL.standard
        ) {
            try await APIClient.shared.getInvestigationHistory(limit: 20)
        }
        investigations = response?.investigations ?? []
    }
}
