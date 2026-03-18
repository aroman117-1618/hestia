import Foundation
import HestiaShared

/// Investigation API methods for macOS.
extension APIClient {
    func getInvestigationHistory(limit: Int = 20) async throws -> InvestigationListResponse {
        return try await get("/investigate/history?limit=\(limit)")
    }
}
