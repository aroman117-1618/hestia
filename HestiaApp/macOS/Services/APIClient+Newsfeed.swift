import Foundation
import HestiaShared

/// Newsfeed API methods for macOS target
extension APIClient {
    func getNewsfeedTimeline(limit: Int = 50) async throws -> NewsfeedTimelineResponse {
        return try await get("/v1/newsfeed/timeline?limit=\(limit)")
    }
}
