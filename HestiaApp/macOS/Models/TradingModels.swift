import Foundation

// MARK: - Trading API Response Types
// No explicit CodingKeys — APIClient uses convertFromSnakeCase.
// AnyCodableValue is defined in HealthDataModels.swift (macOS target).

struct TradingBotResponse: Codable, Identifiable {
    let id: String
    let name: String
    let strategy: String
    let pair: String
    let status: String
    let capitalAllocated: Double
    let createdAt: String
    let updatedAt: String
}

struct TradingBotListResponse: Codable {
    let bots: [TradingBotResponse]
    let total: Int
}

struct TradingTradeResponse: Codable, Identifiable {
    let id: String
    let botId: String
    let side: String
    let orderType: String
    let price: Double
    let quantity: Double
    let fee: Double
    let pair: String
    let taxLotId: String?
    let timestamp: String
    let confidenceScore: Double?
    let decisionTrail: [TrailStep]?
}

struct TradingTradeListResponse: Codable {
    let trades: [TradingTradeResponse]
    let total: Int
}

struct TradingTradeTrailResponse: Codable {
    let tradeId: String
    let decisionTrail: [TrailStep]
    let confidenceScore: Double?
}

struct TrailStep: Codable {
    let step: String?
    let result: AnyCodableValue?
}

struct TradingRiskStatusResponse: Codable {
    let killSwitch: KillSwitchState
    let anyBreakerActive: Bool
}

struct KillSwitchState: Codable {
    let active: Bool
    let reason: String?
    let activatedAt: String?
}

struct TradingPortfolioResponse: Codable {
    let totalValue: Double
    let cash: Double
    let positionsValue: Double
    let dailyPnl: Double
}

struct TradingPositionEntry: Codable, Identifiable {
    var id: String { currency }
    let currency: String
    let quantity: Double
    let hold: Double
    let price: Double
    let value: Double
}

struct TradingPositionsResponse: Codable {
    let positions: [String: TradingPositionEntry]
    let totalExposure: Double
}

struct TradingWatchlistItem: Codable, Identifiable {
    let id: String
    let pair: String
    let notes: String
    let addedAt: String
}

struct TradingWatchlistResponse: Codable {
    let items: [TradingWatchlistItem]
    let total: Int
}

struct TradingKillSwitchResponse: Codable {
    let success: Bool
    let active: Bool
    let reason: String?
}

// MARK: - Dashboard Summary (Sprint 31)

struct TradingSummary: Codable {
    let activeBots: Int
    let totalPnl: Double
    let winRate: Double
    let totalTrades: Int
    let killSwitchActive: Bool
}

// MARK: - Decision Feed

struct DecisionFeedEntry: Identifiable {
    let id = UUID()
    let timestamp: Date
    let source: String
    let message: String

    var timeString: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss"
        return formatter.string(from: timestamp)
    }

    var sourceIcon: String {
        switch source {
        case "MarketData": return "chart.line.uptrend.xyaxis"
        case "RiskManager": return "shield"
        case "Executor": return "arrow.left.arrow.right"
        case "Hestia": return "brain"
        default: return "gearshape"
        }
    }
}
