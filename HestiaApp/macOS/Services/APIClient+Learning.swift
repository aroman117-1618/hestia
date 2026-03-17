import Foundation
import HestiaShared

/// Learning metrics API methods for macOS target
extension APIClient {
    func getLatestMetaMonitorReport(userId: String = "default") async throws -> MetaMonitorReportResponse {
        return try await get("/learning/report?user_id=\(userId)")
    }

    func getMemoryHealth(userId: String = "default") async throws -> MemoryHealthResponse {
        return try await get("/learning/memory-health?user_id=\(userId)")
    }

    func getTriggerAlerts(userId: String = "default") async throws -> TriggerAlertsResponse {
        return try await get("/learning/alerts?user_id=\(userId)")
    }
}
