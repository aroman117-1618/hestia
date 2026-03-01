import Foundation
import HestiaShared

/// Health data API methods for macOS.
extension APIClient {
    func getHealthSummary(date: String? = nil) async throws -> MacHealthSummaryResponse {
        if let date = date {
            return try await get("/v1/health_data/summary/\(date)")
        }
        return try await get("/v1/health_data/summary")
    }

    func getHealthTrend(metricType: String, days: Int = 7) async throws -> MacHealthTrendResponse {
        return try await get("/v1/health_data/trend/\(metricType)?days=\(days)")
    }
}
