import Foundation
import HestiaShared

private struct ResearchEmptyBody: Codable {}

// MARK: - Research API Extensions

extension APIClient {
    /// Fetch the knowledge graph from the server.
    /// - Parameters:
    ///   - limit: Max nodes to return.
    ///   - nodeTypes: Comma-separated node types (memory,topic,entity,principle,fact,community,episode).
    ///   - centerTopic: Focus graph on this topic (legacy mode).
    ///   - mode: Graph mode — "legacy" (co-occurrence) or "facts" (entity-fact).
    ///   - sources: Comma-separated MemorySource values (conversation,mail,calendar,reminders,notes,health).
    ///   - centerEntity: Center entity ID for BFS filtering (facts mode).
    ///   - pointInTime: ISO datetime for bi-temporal fact filtering (facts mode).
    func getResearchGraph(
        limit: Int = 200,
        nodeTypes: String? = nil,
        centerTopic: String? = nil,
        mode: String = "legacy",
        sources: String? = nil,
        centerEntity: String? = nil,
        pointInTime: String? = nil,
        sourceCategories: String? = nil
    ) async throws -> ResearchGraphResponse {
        var path = "/research/graph?limit=\(limit)&mode=\(mode)"
        if let types = nodeTypes {
            path += "&node_types=\(types)"
        }
        if let topic = centerTopic, !topic.isEmpty {
            path += "&center_topic=\(topic.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? topic)"
        }
        if let src = sources, !src.isEmpty {
            path += "&sources=\(src)"
        }
        if let entity = centerEntity, !entity.isEmpty {
            path += "&center_entity=\(entity.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? entity)"
        }
        if let pit = pointInTime, !pit.isEmpty {
            path += "&point_in_time=\(pit.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? pit)"
        }
        if let sc = sourceCategories, !sc.isEmpty {
            path += "&source_categories=\(sc)"
        }
        return try await get(path)
    }

    /// Trigger principle distillation from recent memory.
    func distillPrinciples(timeRangeDays: Int = 7) async throws -> DistillResponse {
        return try await post("/research/principles/distill", body: ["time_range_days": timeRangeDays])
    }

    /// List principles with optional filters.
    func getPrinciples(status: String? = nil, domain: String? = nil, limit: Int = 50) async throws -> PrincipleListResponse {
        var path = "/research/principles?limit=\(limit)"
        if let s = status {
            path += "&status=\(s)"
        }
        if let d = domain {
            path += "&domain=\(d)"
        }
        return try await get(path)
    }

    /// Approve a pending principle.
    func approvePrinciple(_ id: String) async throws -> PrincipleActionResponse {
        return try await post("/research/principles/\(id)/approve", body: ResearchEmptyBody())
    }

    /// Reject a pending principle.
    func rejectPrinciple(_ id: String) async throws -> PrincipleActionResponse {
        return try await post("/research/principles/\(id)/reject", body: ResearchEmptyBody())
    }

    /// Update a principle's content.
    func updatePrinciple(_ id: String, content: String) async throws -> PrincipleActionResponse {
        return try await put("/research/principles/\(id)", body: ["content": content])
    }
}
