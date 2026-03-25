import Foundation
import HestiaShared

/// Trading, workflow, and system API methods for iOS Mobile Command dashboard.
extension APIClient {

    // MARK: - Trading

    func getMobileTradingSummary() async throws -> MobileTradingSummary {
        return try await get("/trading/summary")
    }

    func getMobileTradingBots() async throws -> MobileTradingBotList {
        return try await get("/trading/bots")
    }

    func getMobileRiskStatus() async throws -> MobileRiskStatus {
        return try await get("/trading/risk/status")
    }

    func activateMobileKillSwitch(reason: String = "Mobile kill switch") async throws -> MobileKillSwitchResponse {
        struct KillSwitchRequest: Codable {
            let action: String
            let reason: String
        }
        return try await post(
            "/trading/kill-switch",
            body: KillSwitchRequest(action: "activate", reason: reason)
        )
    }

    func deactivateMobileKillSwitch() async throws -> MobileKillSwitchResponse {
        struct KillSwitchRequest: Codable {
            let action: String
            let reason: String
        }
        return try await post(
            "/trading/kill-switch",
            body: KillSwitchRequest(action: "deactivate", reason: "")
        )
    }

    // MARK: - Workflows (Orders)

    func getMobileWorkflows(limit: Int = 10) async throws -> MobileWorkflowList {
        return try await get("/workflows?limit=\(limit)&status=active")
    }

    // MARK: - Newsfeed

    func getMobileNewsfeed(limit: Int = 5) async throws -> MobileNewsfeedTimeline {
        return try await get("/newsfeed/timeline?limit=\(limit)")
    }

    // MARK: - Cloud State

    func getCloudState() async throws -> CloudStateResponse {
        return try await get("/cloud/state")
    }

    func cycleCloudState() async throws -> CloudStateResponse {
        struct EmptyBody: Codable {}
        return try await post("/cloud/cycle", body: EmptyBody())
    }
}

struct CloudStateResponse: Codable {
    let state: String
}
