import Foundation
import HestiaShared

private struct NewsfeedEmptyBody: Codable {}

/// Newsfeed API methods added as local extension to HestiaShared's APIClient.
/// These use local NewsfeedModels/BriefingModels types (not in HestiaShared) so they live here.
extension APIClient {
    func getNewsfeedTimeline(
        type: NewsfeedItemType? = nil,
        source: NewsfeedItemSource? = nil,
        includeDismissed: Bool = false,
        limit: Int = 50,
        offset: Int = 0
    ) async throws -> NewsfeedTimelineResponse {
        var path = "/v1/newsfeed/timeline?limit=\(limit)&offset=\(offset)"
        if let type = type { path += "&type=\(type.rawValue)" }
        if let source = source { path += "&source=\(source.rawValue)" }
        if includeDismissed { path += "&include_dismissed=true" }
        return try await get(path)
    }

    func getNewsfeedUnreadCount() async throws -> NewsfeedUnreadResponse {
        return try await get("/v1/newsfeed/unread-count")
    }

    func markNewsfeedItemRead(itemId: String) async throws -> NewsfeedActionResponse {
        let encoded = itemId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? itemId
        return try await post("/v1/newsfeed/items/\(encoded)/read", body: NewsfeedEmptyBody())
    }

    func dismissNewsfeedItem(itemId: String) async throws -> NewsfeedActionResponse {
        let encoded = itemId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? itemId
        return try await post("/v1/newsfeed/items/\(encoded)/dismiss", body: NewsfeedEmptyBody())
    }

    func refreshNewsfeed() async throws -> NewsfeedRefreshResponse {
        return try await post("/v1/newsfeed/refresh", body: NewsfeedEmptyBody())
    }

    func getBriefing() async throws -> BriefingResponse {
        return try await get("/v1/proactive/briefing")
    }
}
