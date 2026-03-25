import Foundation

// MARK: - Trading Models (iOS-compatible subset)
// Mirrors macOS TradingModels but drops AnyCodableValue dependency.

struct MobileTradingSummary: Codable {
    let activeBots: Int
    let totalPnl: Double
    let winRate: Double
    let totalTrades: Int
    let killSwitchActive: Bool
}

struct MobileTradingBot: Codable, Identifiable {
    let id: String
    let name: String
    let strategy: String
    let pair: String
    let status: String
    let capitalAllocated: Double
}

struct MobileTradingBotList: Codable {
    let bots: [MobileTradingBot]
    let total: Int
}

struct MobileRiskStatus: Codable {
    let killSwitch: MobileKillSwitchState
    let anyBreakerActive: Bool
}

struct MobileKillSwitchState: Codable {
    let active: Bool
    let reason: String?
    let activatedAt: String?
}

struct MobileKillSwitchResponse: Codable {
    let success: Bool
    let active: Bool
    let reason: String?
}

// MARK: - Workflow Models (iOS-compatible subset)

struct MobileWorkflow: Codable, Identifiable {
    let id: String
    let name: String
    let status: String
    let createdAt: String?
    let updatedAt: String?
}

struct MobileWorkflowList: Codable {
    let workflows: [MobileWorkflow]
    let total: Int
}

// MARK: - Newsfeed Models (iOS-compatible subset)

struct MobileNewsfeedItem: Codable, Identifiable {
    let id: String
    let title: String
    let summary: String?
    let source: String
    let type: String
    let isRead: Bool?
    let createdAt: String?
}

struct MobileNewsfeedTimeline: Codable {
    let items: [MobileNewsfeedItem]
    let total: Int
}
