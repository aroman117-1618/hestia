import Foundation
import HestiaShared

/// Trading API methods for macOS dashboard.
extension APIClient {

    // MARK: - Dashboard Summary

    func getTradingSummary(period: String? = nil) async throws -> TradingSummary {
        var path = "/trading/summary"
        if let period {
            path += "?period=\(period)"
        }
        return try await get(path)
    }

    // MARK: - Portfolio & Positions

    func getTradingPortfolio() async throws -> TradingPortfolioResponse {
        return try await get("/trading/portfolio")
    }

    func getTradingPositions() async throws -> TradingPositionsResponse {
        return try await get("/trading/positions")
    }

    // MARK: - Bots

    func getTradingBots() async throws -> TradingBotListResponse {
        return try await get("/trading/bots")
    }

    // MARK: - Trades

    func getTradingTrades(limit: Int = 20) async throws -> TradingTradeListResponse {
        return try await get("/trading/trades?limit=\(limit)")
    }

    func getTradeTrail(tradeId: String) async throws -> TradingTradeTrailResponse {
        return try await get("/trading/trades/\(tradeId)/trail")
    }

    func submitTradeFeedback(tradeId: String, rating: String, note: String = "") async throws {
        struct FeedbackRequest: Codable {
            let rating: String
            let note: String
        }
        let _: EmptyResponse = try await post(
            "/trading/trades/\(tradeId)/feedback",
            body: FeedbackRequest(rating: rating, note: note)
        )
    }

    // MARK: - Risk & Kill Switch

    func getTradingRiskStatus() async throws -> TradingRiskStatusResponse {
        return try await get("/trading/risk/status")
    }

    func activateKillSwitch(reason: String = "Manual activation") async throws -> TradingKillSwitchResponse {
        struct KillSwitchRequest: Codable {
            let action: String
            let reason: String
        }
        return try await post(
            "/trading/kill-switch",
            body: KillSwitchRequest(action: "activate", reason: reason)
        )
    }

    func deactivateKillSwitch() async throws -> TradingKillSwitchResponse {
        struct KillSwitchRequest: Codable {
            let action: String
            let reason: String
        }
        return try await post(
            "/trading/kill-switch",
            body: KillSwitchRequest(action: "deactivate", reason: "")
        )
    }

    // MARK: - Watchlist

    func getTradingWatchlist() async throws -> TradingWatchlistResponse {
        return try await get("/trading/watchlist")
    }

    func addToWatchlist(pair: String, notes: String = "") async throws -> TradingWatchlistItem {
        struct AddRequest: Codable {
            let pair: String
            let notes: String
        }
        return try await post(
            "/trading/watchlist",
            body: AddRequest(pair: pair, notes: notes)
        )
    }

    func removeFromWatchlist(itemId: String) async throws {
        // APIClient.delete() is private to the HestiaShared module.
        // Use a POST request to a delete alias endpoint, matching Files pattern.
        struct EmptyBody: Codable {}
        let _: EmptyResponse = try await post("/trading/watchlist/\(itemId)/delete", body: EmptyBody())
    }
}
