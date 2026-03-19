import SwiftUI
import HestiaShared

private struct TradingEmptyBody: Codable {}

/// ViewModel for the Trading Monitor dashboard.
/// Loads data via REST endpoints, subscribes to SSE for real-time updates.
@MainActor
class MacTradingViewModel: ObservableObject {

    // MARK: - Published State

    @Published var portfolio: TradingPortfolioResponse?
    @Published var positions: [String: TradingPositionEntry] = [:]
    @Published var trades: [TradingTradeResponse] = []
    @Published var riskStatus: TradingRiskStatusResponse?
    @Published var watchlist: [TradingWatchlistItem] = []
    @Published var bots: [TradingBotResponse] = []

    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var killSwitchActive = false
    @Published var isConnected = false

    // MARK: - Autonomous Trading State

    @Published var autonomousTradingEnabled = false
    @Published var showFirstRunModal = false
    @Published var decisionFeed: [DecisionFeedEntry] = []

    // MARK: - SSE State

    private var sseTask: Task<Void, Never>?
    private var refreshTimer: Timer?
    private var hasEverEnabled = false

    // MARK: - Data Loading

    func loadAllData() async {
        isLoading = true
        errorMessage = nil

        async let portfolioTask: () = loadPortfolio()
        async let positionsTask: () = loadPositions()
        async let tradesTask: () = loadTrades()
        async let riskTask: () = loadRiskStatus()
        async let watchlistTask: () = loadWatchlist()
        async let botsTask: () = loadBots()

        _ = await (portfolioTask, positionsTask, tradesTask, riskTask, watchlistTask, botsTask)
        isLoading = false
    }

    private func loadPortfolio() async {
        do {
            portfolio = try await APIClient.shared.getTradingPortfolio()
        } catch {
            #if DEBUG
            print("[Trading] Portfolio load failed: \(error)")
            #endif
        }
    }

    private func loadPositions() async {
        do {
            let response = try await APIClient.shared.getTradingPositions()
            positions = response.positions
        } catch {
            #if DEBUG
            print("[Trading] Positions load failed: \(error)")
            #endif
        }
    }

    private func loadTrades() async {
        do {
            let response = try await APIClient.shared.getTradingTrades(limit: 20)
            trades = response.trades
        } catch {
            #if DEBUG
            print("[Trading] Trades load failed: \(error)")
            #endif
        }
    }

    private func loadRiskStatus() async {
        do {
            riskStatus = try await APIClient.shared.getTradingRiskStatus()
            killSwitchActive = riskStatus?.killSwitch.active ?? false
        } catch {
            #if DEBUG
            print("[Trading] Risk status load failed: \(error)")
            #endif
        }
    }

    private func loadWatchlist() async {
        do {
            let response = try await APIClient.shared.getTradingWatchlist()
            watchlist = response.items
        } catch {
            #if DEBUG
            print("[Trading] Watchlist load failed: \(error)")
            #endif
        }
    }

    private func loadBots() async {
        do {
            let response = try await APIClient.shared.getTradingBots()
            bots = response.bots
            // Sync autonomous trading state from actual bot statuses
            autonomousTradingEnabled = bots.contains { $0.status == "running" }
        } catch {
            #if DEBUG
            print("[Trading] Bots load failed: \(error)")
            #endif
        }
    }

    // MARK: - Kill Switch

    func toggleKillSwitch() async {
        do {
            if killSwitchActive {
                let response = try await APIClient.shared.deactivateKillSwitch()
                killSwitchActive = response.active
            } else {
                let response = try await APIClient.shared.activateKillSwitch(reason: "Manual activation from dashboard")
                killSwitchActive = response.active
            }
        } catch {
            errorMessage = "Kill switch operation failed"
            #if DEBUG
            print("[Trading] Kill switch failed: \(error)")
            #endif
        }
    }

    // MARK: - Trade Feedback

    func submitFeedback(tradeId: String, rating: String) async {
        do {
            try await APIClient.shared.submitTradeFeedback(tradeId: tradeId, rating: rating)
            // Reload trades to reflect feedback
            await loadTrades()
        } catch {
            #if DEBUG
            print("[Trading] Feedback submission failed: \(error)")
            #endif
        }
    }

    // MARK: - Watchlist

    func addToWatchlist(pair: String, notes: String = "") async {
        do {
            _ = try await APIClient.shared.addToWatchlist(pair: pair, notes: notes)
            await loadWatchlist()
        } catch {
            #if DEBUG
            print("[Trading] Add watchlist failed: \(error)")
            #endif
        }
    }

    func removeFromWatchlist(itemId: String) async {
        do {
            try await APIClient.shared.removeFromWatchlist(itemId: itemId)
            watchlist.removeAll { $0.id == itemId }
        } catch {
            #if DEBUG
            print("[Trading] Remove watchlist failed: \(error)")
            #endif
        }
    }

    // MARK: - Autonomous Trading Toggle

    func toggleAutonomousTrading() {
        if autonomousTradingEnabled {
            // Disable — no confirmation needed
            Task { await disableTrading() }
        } else {
            // Enable — show first-run confirmation
            showFirstRunModal = true
        }
    }

    func confirmEnableTrading(strategy: String = "mean_reversion", pair: String = "BTC-USD", capital: Double = 25.0) async {
        showFirstRunModal = false
        do {
            struct EnableRequest: Codable {
                let strategy: String
                let pair: String
                let capitalAllocated: Double
                let name: String
                let config: [String: String]
            }
            // Create bot
            let bot: TradingBotResponse = try await APIClient.shared.post(
                "/trading/bots",
                body: EnableRequest(
                    strategy: strategy, pair: pair, capitalAllocated: capital,
                    name: "\(strategy.replacingOccurrences(of: "_", with: " ").capitalized) — \(pair)",
                    config: [:]
                )
            )
            // Start bot (this launches the BotRunner)
            let _: TradingBotResponse = try await APIClient.shared.post(
                "/trading/bots/\(bot.id)/start",
                body: TradingEmptyBody()
            )
            autonomousTradingEnabled = true
            addDecisionEntry(source: "Hestia", message: "Autonomous trading enabled — \(strategy) on \(pair) with $\(String(format: "%.0f", capital))")
            await loadAllData()
        } catch {
            errorMessage = "Failed to enable trading"
            #if DEBUG
            print("[Trading] Enable failed: \(error)")
            #endif
        }
    }

    private func disableTrading() async {
        do {
            // Stop all running bots
            for bot in bots where bot.status == "running" {
                let _: TradingBotResponse = try await APIClient.shared.post(
                    "/trading/bots/\(bot.id)/stop",
                    body: TradingEmptyBody()
                )
            }
            autonomousTradingEnabled = false
            addDecisionEntry(source: "Hestia", message: "Autonomous trading disabled — all bots stopped")
            await loadAllData()
        } catch {
            errorMessage = "Failed to disable trading"
            #if DEBUG
            print("[Trading] Disable failed: \(error)")
            #endif
        }
    }

    // MARK: - Decision Feed

    func addDecisionEntry(source: String, message: String) {
        let entry = DecisionFeedEntry(
            timestamp: Date(),
            source: source,
            message: message
        )
        decisionFeed.insert(entry, at: 0)
        // Keep last 100 entries
        if decisionFeed.count > 100 {
            decisionFeed = Array(decisionFeed.prefix(100))
        }
    }

    // MARK: - Periodic Refresh

    func startPeriodicRefresh() {
        stopPeriodicRefresh()
        refreshTimer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { [weak self] _ in
            guard let self = self else { return }
            Task { @MainActor [weak self] in
                await self?.loadAllData()
            }
        }
    }

    func stopPeriodicRefresh() {
        refreshTimer?.invalidate()
        refreshTimer = nil
    }

    func cleanup() {
        sseTask?.cancel()
        stopPeriodicRefresh()
    }
}
